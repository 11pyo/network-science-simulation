# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 11pyo
"""
Stable linear propagation engine (signed, directed).

    x[t+1] = (1 - lam) * x[t] + A @ x[t] + u[t]
    A[target, source] = weight of edge source -> target

Modes
- "impulse":    one-time shock, x[0] = s, u[t>0] = 0.
                Output `cumulative_impulse_impact` = sum_t x[t] = (lam I - A)^-1 s
- "persistent": shock held every step, x[0] = 0, u[t] = s.
                Output `persistent_steady_state` = lim x[t] = (lam I - A)^-1 s

Both outputs share a formula but answer different questions, so they carry
different names. No clamping is applied: an unstable model is rejected
instead of being silently saturated (the defect of the legacy engine).
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from typing import Literal

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla
from scipy.sparse.csgraph import connected_components

from cxsim.spec import ModelSpec

Mode = Literal["impulse", "persistent"]
OUTPUT_NAMES = {
    "impulse": "cumulative_impulse_impact",
    "persistent": "persistent_steady_state",
}
# [SECURE] Hard cap on trajectory length - prevents unbounded loops (Category 3)
MAX_STEPS = 500
STABILITY_TOL = 1e-9
# Above this node count matrices are sparse and solved with sparse solvers.
DENSE_MAX = 500
# Strongly connected components up to this size use dense eigvals; larger ones use
# ARPACK with a fixed start vector (deterministic) and fail closed on non-convergence.
SCC_DENSE_MAX = 2000


class UnstableModelError(ValueError):
    """Raised when spectral_radius((1 - lam) I + A) >= 1."""

    def __init__(self, rho: float):
        super().__init__(f"Model is unstable (spectral radius {rho:.3f} >= 1).")
        self.rho = rho


class AmplificationExceededError(ValueError):
    """Stable but explosive: max |impact| exceeds spec.max_amplification x total |shock|."""

    def __init__(self, amplification: float, cap: float):
        super().__init__(f"Impact amplification {amplification:.3g}x exceeds the declared cap {cap:.3g}x.")
        self.amplification = amplification
        self.cap = cap


class NumericalBlowupError(ValueError):
    """The linear solve failed or produced non-finite values (singular or overflowing system)."""


@dataclass(frozen=True)
class LinearResult:
    node_ids: tuple[str, ...]
    mode: Mode
    output_name: str
    trajectory: np.ndarray  # shape (steps + 1, n)
    total: np.ndarray       # shape (n,), meaning given by output_name
    spectral_radius: float
    lam: float
    max_amplification: float  # max |total| / sum |shock|


def edge_mids(spec: ModelSpec) -> np.ndarray:
    return np.array([e.weight.mid for e in spec.edges], dtype=float)


def build_matrix(spec: ModelSpec, weights: np.ndarray | None = None, sparse: bool | None = None):
    """Return A with A[target, source] = weight (dense ndarray, or CSR when sparse)."""
    n = len(spec.nodes)
    w = edge_mids(spec) if weights is None else np.asarray(weights, dtype=float)
    if w.shape != (len(spec.edges),):
        raise ValueError("Weight vector length does not match edge count.")
    if sparse is None:
        sparse = n > DENSE_MAX
    idx = spec.index()
    rows = np.fromiter((idx[e.target] for e in spec.edges), dtype=np.int64, count=len(spec.edges))
    cols = np.fromiter((idx[e.source] for e in spec.edges), dtype=np.int64, count=len(spec.edges))
    if sparse:
        return sp.csr_matrix((w, (rows, cols)), shape=(n, n))
    A = np.zeros((n, n), dtype=float)
    A[rows, cols] = w
    return A


def _identity(A, n: int):
    return sp.identity(n, format="csr") if sp.issparse(A) else np.eye(n)


def spectral_radius(A, lam: float) -> float:
    """
    Spectral radius of M = (1 - lam) I + A. Rejection decisions use this, not Gershgorin.

    M is block triangular in the order of strongly connected components (SCC), so
    rho(M) = max over components. A single-node component (no self loops) contributes
    exactly |1 - lam|. Computing per component avoids the ill-conditioned eigenvalues
    of large non-normal (near-acyclic) matrices, where a global eigensolver is wrong.
    """
    n = A.shape[0]
    As = A.tocsr(copy=True) if sp.issparse(A) else sp.csr_matrix(A)
    As.eliminate_zeros()
    n_comp, labels = connected_components(As, directed=True, connection="strong")
    rho = abs(1.0 - lam)
    sizes = np.bincount(labels, minlength=n_comp)
    for comp in np.flatnonzero(sizes > 1):
        members = np.flatnonzero(labels == comp)
        sub = As[members][:, members]
        m = len(members)
        if m <= SCC_DENSE_MAX:
            Msub = (1.0 - lam) * np.eye(m) + sub.toarray()
            r = float(np.max(np.abs(np.linalg.eigvals(Msub))))
        else:
            Msub = (1.0 - lam) * sp.identity(m, format="csr") + sub
            v0 = np.full(m, 1.0 / math.sqrt(m))
            try:
                vals = spla.eigs(Msub, k=1, which="LM", v0=v0, return_eigenvectors=False,
                                 maxiter=10000, tol=1e-10)
            except spla.ArpackNoConvergence as exc:
                # [SECURE] Fail closed: undetermined stability is treated as an error, not as stable (Category 4)
                raise ValueError("Could not determine model stability.") from exc
            r = float(np.max(np.abs(vals)))
        rho = max(rho, r)
    return rho


def shock_vector(spec: ModelSpec, shocks: dict[str, float]) -> np.ndarray:
    if not shocks:
        raise ValueError("At least one shock is required.")
    idx = spec.index()
    s = np.zeros(len(spec.nodes), dtype=float)
    for nid, val in shocks.items():
        # [SECURE] Node must be declared in the spec - whitelist check (Category 1)
        if nid not in idx:
            raise ValueError("Unknown shock node.")
        # [SECURE] Finite, bounded shock size - rejects NaN/inf and out-of-range input (Category 1)
        if not isinstance(val, (int, float)) or not math.isfinite(val) or abs(val) > 1.0:
            raise ValueError("Shock must be a finite number in [-1, 1].")
        s[idx[nid]] = float(val)
    # [SECURE] Reject an all-zero shock - amplification would be 0/0 = NaN and slip past the cap (Category 1)
    if not np.any(s):
        raise ValueError("At least one shock must be non-zero.")
    return s


def total_impact(A, lam: float, s: np.ndarray) -> np.ndarray:
    """
    (lam I - A)^-1 s via a linear solve (sparse solver for large graphs); caller checks stability.
    Singular or overflowing systems raise NumericalBlowupError instead of leaking LinAlgError/inf.
    """
    n = A.shape[0]
    K = lam * _identity(A, n) - A
    try:
        with warnings.catch_warnings(), np.errstate(over="ignore", invalid="ignore", divide="ignore"):
            warnings.simplefilter("ignore", spla.MatrixRankWarning)
            if sp.issparse(K):
                x = np.asarray(spla.spsolve(K.tocsc(), s), dtype=float)
            else:
                x = np.linalg.solve(K, s)
    except np.linalg.LinAlgError as exc:
        # [SECURE] Explicit, typed failure instead of a leaked library error (Category 4)
        raise NumericalBlowupError("Linear system is singular or numerically unsolvable.") from exc
    if not np.all(np.isfinite(x)):
        raise NumericalBlowupError("Impact is not finite (numerical overflow).")
    return x


def amplification(total: np.ndarray, s: np.ndarray) -> float:
    """max |impact| relative to the total size of the direct shock."""
    return float(np.max(np.abs(total)) / np.sum(np.abs(s)))


def simulate(
    spec: ModelSpec,
    shocks: dict[str, float],
    mode: Mode = "impulse",
    steps: int = 50,
    weights: np.ndarray | None = None,
    lam: float | None = None,
) -> LinearResult:
    if mode not in OUTPUT_NAMES:
        raise ValueError("Unknown mode.")
    # [SECURE] Bounded step count (Category 3)
    if not isinstance(steps, int) or not 1 <= steps <= MAX_STEPS:
        raise ValueError(f"steps must be an integer in [1, {MAX_STEPS}].")
    lam = spec.self_decay.mid if lam is None else float(lam)
    if not 0.0 < lam <= 1.0:
        raise ValueError("self_decay must be in (0, 1].")

    A = build_matrix(spec, weights)
    rho = spectral_radius(A, lam)
    if rho >= 1.0 - STABILITY_TOL:
        raise UnstableModelError(rho)

    s = shock_vector(spec, shocks)
    total = total_impact(A, lam, s)
    amp = amplification(total, s)
    # [SECURE] Declared amplification cap - stable-but-explosive models fail explicitly (Category 1)
    if amp > spec.max_amplification:
        raise AmplificationExceededError(amp, spec.max_amplification)

    M = (1.0 - lam) * _identity(A, A.shape[0]) + A
    traj = np.zeros((steps + 1, A.shape[0]), dtype=float)
    if mode == "impulse":
        traj[0] = s
        for t in range(steps):
            traj[t + 1] = M @ traj[t]
    else:
        for t in range(steps):
            traj[t + 1] = M @ traj[t] + s

    return LinearResult(
        node_ids=tuple(spec.node_ids),
        mode=mode,
        output_name=OUTPUT_NAMES[mode],
        trajectory=traj,
        total=total,
        spectral_radius=rho,
        lam=lam,
        max_amplification=amp,
    )


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: shock nodes whitelisted against spec, shock values finite and bounded (Category 1)
#   - Infinite loop prevention: steps capped at MAX_STEPS (Category 3)
#   - Runaway prevention: unstable models rejected via per-SCC spectral radius instead of clamping (Category 1)
#   - Explosive models: declared max_amplification cap; singular/overflowing solves raise typed errors (Category 4)
#   - Encapsulation: frozen result dataclass (Category 6)
# Not Applied:
#   - [WARN] Authentication: not applicable - pure computation module
#   - [WARN] Precision loss below the amplification cap: ill-conditioned but finite solves are not
#     flagged; add a condition-number estimate if P1 graphs show it matters
# --------------------------------------------------
