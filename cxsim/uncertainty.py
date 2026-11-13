# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 11pyo
"""
Range-based uncertainty for the linear engine.

- monte_carlo(): samples every edge weight and self_decay from its range,
  reports quantiles, rank probabilities, and the share of unstable samples
  and of explosive samples (stable but above spec.max_amplification).
  Nodes whose |impact| is ~0 are never ranked (unreachable nodes get no rank).
  Unstable samples are never dropped silently: `unstable_fraction` is part
  of the result and is itself a fragility indicator.
- sensitivity(): which uncertain assumptions drive the impact on one node.
  Sobol (S1, ST) up to SOBOL_MAX_PARAMS parameters, Morris screening above.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from cxsim.engines.linear import (
    STABILITY_TOL,
    Mode,
    NumericalBlowupError,
    OUTPUT_NAMES,
    amplification,
    build_matrix,
    shock_vector,
    spectral_radius,
    total_impact,
)
from cxsim.spec import ModelSpec

SOBOL_MAX_PARAMS = 60
# [SECURE] Caps on sample counts - prevents resource exhaustion from user-chosen sizes (Category 3)
MAX_MC_SAMPLES = 20000
MAX_SOBOL_BASE = 2048
# |impact| at or below RANK_TOL x total |shock| counts as "not reached" and is not ranked.
RANK_TOL = 1e-12


@dataclass(frozen=True)
class MonteCarloResult:
    node_ids: tuple[str, ...]
    output_name: str
    quantile_levels: tuple[float, ...]
    quantiles: np.ndarray        # shape (len(levels), n); NaN when no stable sample
    mean: np.ndarray             # shape (n,)
    top1_prob: np.ndarray        # P(node has the largest |impact| among reached, non-shocked nodes)
    topk_prob: np.ndarray        # P(node is within the top k of those)
    k: int
    n_samples: int
    n_stable: int                # samples used for statistics (stable and within the amplification cap)
    unstable_fraction: float     # spectral radius >= 1
    explosive_fraction: float    # stable but above max_amplification, or numerically unsolvable
    ranked_fraction: float       # share of used samples in which at least one node was reached


@dataclass(frozen=True)
class SensitivityResult:
    method: str                  # "sobol" or "morris"
    target: str
    params: tuple[str, ...]
    first: np.ndarray            # Sobol S1 or Morris mu_star
    total: np.ndarray            # Sobol ST or Morris sigma
    fixed_params: tuple[str, ...]


class SensitivityUnavailable(ValueError):
    """Raised when sampled ranges include unstable models (Sobol needs every sample)."""


def param_names(spec: ModelSpec) -> list[str]:
    return [f"{e.source}->{e.target}" for e in spec.edges] + ["self_decay"]


def _bounds(spec: ModelSpec) -> np.ndarray:
    rows = [(e.weight.low, e.weight.high) for e in spec.edges]
    rows.append((spec.self_decay.low, spec.self_decay.high))
    return np.array(rows, dtype=float)


def sample_parameters(spec: ModelSpec, n: int, seed: int | None = None) -> np.ndarray:
    """Uniform samples, shape (n, edges + 1); last column is self_decay."""
    b = _bounds(spec)
    # Simulation randomness, not security randomness; seeded for reproducibility.
    rng = np.random.default_rng(spec.sampling.seed if seed is None else seed)
    return b[:, 0] + rng.random((n, b.shape[0])) * (b[:, 1] - b[:, 0])


def _evaluate(spec: ModelSpec, theta: np.ndarray, s: np.ndarray) -> tuple[str, np.ndarray | None]:
    """Return ("ok", impact), ("unstable", None) or ("explosive", None)."""
    A = build_matrix(spec, theta[:-1])
    lam = float(theta[-1])
    if spectral_radius(A, lam) >= 1.0 - STABILITY_TOL:
        return "unstable", None
    try:
        out = total_impact(A, lam, s)
    except NumericalBlowupError:
        return "explosive", None
    if amplification(out, s) > spec.max_amplification:
        return "explosive", None
    return "ok", out


def monte_carlo(
    spec: ModelSpec,
    shocks: dict[str, float],
    n_samples: int = 1000,
    mode: Mode = "impulse",
    quantile_levels: tuple[float, ...] = (0.1, 0.5, 0.9),
    k: int = 3,
    seed: int | None = None,
) -> MonteCarloResult:
    if mode not in OUTPUT_NAMES:
        raise ValueError("Unknown mode.")
    # [SECURE] Bounded sample count (Category 3)
    if not isinstance(n_samples, int) or not 1 <= n_samples <= MAX_MC_SAMPLES:
        raise ValueError(f"n_samples must be in [1, {MAX_MC_SAMPLES}].")
    s = shock_vector(spec, shocks)
    n = len(spec.nodes)
    k = max(1, min(int(k), n))

    totals = []
    counts = {"ok": 0, "unstable": 0, "explosive": 0}
    for theta in sample_parameters(spec, n_samples, seed):
        status, out = _evaluate(spec, theta, s)
        counts[status] += 1
        if out is not None:
            totals.append(out)

    n_stable = len(totals)
    levels = tuple(float(q) for q in quantile_levels)
    unstable_fraction = counts["unstable"] / n_samples
    explosive_fraction = counts["explosive"] / n_samples
    if n_stable == 0:
        nan = np.full(n, np.nan)
        return MonteCarloResult(
            tuple(spec.node_ids), OUTPUT_NAMES[mode], levels,
            np.full((len(levels), n), np.nan), nan, nan.copy(), nan.copy(), k,
            n_samples, 0, unstable_fraction, explosive_fraction, 0.0,
        )

    T = np.array(totals)
    shocked = s != 0.0
    mag = np.abs(T)
    # Rank only nodes that were not shocked directly AND were actually reached.
    mag[:, shocked] = -np.inf
    mag[mag <= RANK_TOL * np.sum(np.abs(s))] = -np.inf
    order = np.argsort(-mag, axis=1)
    reached_sorted = np.isfinite(np.take_along_axis(mag, order, axis=1))
    k_eff = max(1, min(k, int((~shocked).sum()))) if (~shocked).any() else 1
    top1 = np.bincount(order[reached_sorted[:, 0], 0], minlength=n) / n_stable
    topk = np.zeros(n)
    for col in range(min(k_eff, n)):
        sel = reached_sorted[:, col]
        topk += np.bincount(order[sel, col], minlength=n)
    topk /= n_stable
    top1[shocked] = np.nan
    topk[shocked] = np.nan

    return MonteCarloResult(
        node_ids=tuple(spec.node_ids),
        output_name=OUTPUT_NAMES[mode],
        quantile_levels=levels,
        quantiles=np.quantile(T, levels, axis=0),
        mean=T.mean(axis=0),
        top1_prob=top1,
        topk_prob=topk,
        k=k_eff,
        n_samples=n_samples,
        n_stable=n_stable,
        unstable_fraction=unstable_fraction,
        explosive_fraction=explosive_fraction,
        ranked_fraction=float(reached_sorted[:, 0].mean()),
    )


def sensitivity(
    spec: ModelSpec,
    shocks: dict[str, float],
    target: str,
    n_base: int = 256,
    method: str | None = None,
) -> SensitivityResult:
    """Sensitivity of the target node's total impact to every uncertain parameter."""
    from SALib.analyze import morris as morris_analyze
    from SALib.analyze import sobol as sobol_analyze
    from SALib.sample import morris as morris_sample
    from SALib.sample import sobol as sobol_sample

    idx = spec.index()
    # [SECURE] Target must be a declared node (Category 1)
    if target not in idx:
        raise ValueError("Unknown target node.")
    if not isinstance(n_base, int) or not 8 <= n_base <= MAX_SOBOL_BASE:
        raise ValueError(f"n_base must be in [8, {MAX_SOBOL_BASE}].")
    s = shock_vector(spec, shocks)

    names = param_names(spec)
    b = _bounds(spec)
    free = b[:, 1] > b[:, 0]
    free_names = [nm for nm, f in zip(names, free) if f]
    fixed_names = tuple(nm for nm, f in zip(names, free) if not f)
    if not free_names:
        raise SensitivityUnavailable("All parameters are fixed; nothing to analyse.")

    if method is None:
        method = "sobol" if len(free_names) <= SOBOL_MAX_PARAMS else "morris"
    if method not in ("sobol", "morris"):
        raise ValueError("Unknown sensitivity method.")

    problem = {"num_vars": len(free_names), "names": free_names, "bounds": b[free].tolist()}
    if method == "sobol":
        X = sobol_sample.sample(problem, n_base, calc_second_order=False, seed=spec.sampling.seed)
    else:
        X = morris_sample.sample(problem, n_base, num_levels=4, seed=spec.sampling.seed)

    base = b[:, 0].copy()
    y = np.empty(len(X))
    unstable = 0
    for r, row in enumerate(X):
        theta = base.copy()
        theta[free] = row
        status, out = _evaluate(spec, theta, s)
        if out is None:
            unstable += 1
            y[r] = np.nan
        else:
            y[r] = out[idx[target]]
    if unstable:
        # [SECURE] Explicit failure instead of silently dropping samples (Category 4)
        raise SensitivityUnavailable(
            f"{unstable / len(X):.1%} of sensitivity samples are unstable or explosive; narrow the ranges first."
        )

    if method == "sobol":
        res = sobol_analyze.analyze(problem, y, calc_second_order=False, seed=spec.sampling.seed)
        first, total = np.asarray(res["S1"]), np.asarray(res["ST"])
    else:
        res = morris_analyze.analyze(problem, X, y, num_levels=4, seed=spec.sampling.seed)
        first, total = np.asarray(res["mu_star"]), np.asarray(res["sigma"])

    return SensitivityResult(method, target, tuple(free_names), first, total, fixed_names)


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: target and shock nodes whitelisted, sample sizes bounded (Category 1, 3)
#   - Error handling: unstable samples reported (unstable_fraction) or raised explicitly, never swallowed (Category 4)
#   - Encapsulation: frozen result dataclasses (Category 6)
# Not Applied:
#   - [WARN] Improper random value: numpy default_rng is used on purpose - simulation sampling, not a
#     security decision; reproducibility requires a seeded generator
#   - [WARN] Authentication: not applicable - pure computation module
# --------------------------------------------------
