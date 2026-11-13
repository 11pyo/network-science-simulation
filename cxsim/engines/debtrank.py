# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 11pyo
"""
DebtRank distress propagation (Battiston et al., 2012, Sci. Rep. 2:541).

    h_i(t) = min(1, h_i(t-1) + sum_{j in D(t-1)} W[i, j] * h_j(t-1))

States: S (undistressed), D (distressed, propagates once in the next round),
I (inactive, already propagated). A node propagates at most once, so the
process ends after at most n + 1 rounds.

Variant notes (as in the original paper): nodes in state I keep accumulating
distress from later rounds but never propagate again. Node values v come from
NodeSpec.value (normalised to shares) unless overridden by `values`.

W[target, source] = weight of edge source -> target and must lie in [0, 1].
Signed specs (negative weights = buffers) are rejected here; use the linear
engine for those.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp

from cxsim.engines.linear import build_matrix
from cxsim.spec import ModelSpec

S, D, I = 0, 1, 2


@dataclass(frozen=True)
class DebtRankResult:
    node_ids: tuple[str, ...]
    h: np.ndarray            # final distress per node, in [0, 1]
    history: np.ndarray      # shape (rounds + 1, n)
    values: np.ndarray       # economic value share per node, sums to 1
    total_distress: float    # sum_i h_i(T) v_i
    debtrank: float          # induced distress: total_distress - sum_i h_i(0) v_i
    rounds: int


def run(
    spec: ModelSpec,
    initial_distress: dict[str, float],
    weights: np.ndarray | None = None,
    values: dict[str, float] | None = None,
) -> DebtRankResult:
    W = build_matrix(spec, weights)
    if sp.issparse(W):
        W = W.tocsc()  # column slicing per round on large graphs
    vals = W.data if sp.issparse(W) else W
    # [SECURE] Reject signed or out-of-range impacts explicitly - prevents invalid model use (Category 1)
    if np.any(vals < 0.0) or np.any(vals > 1.0):
        raise ValueError("DebtRank requires all edge weights in [0, 1]; negative edges are not supported.")

    n = W.shape[0]
    idx = spec.index()
    h = np.zeros(n, dtype=float)
    if not initial_distress:
        raise ValueError("At least one distressed node is required.")
    for nid, val in initial_distress.items():
        # [SECURE] Whitelist node id and bound value (Category 1)
        if nid not in idx:
            raise ValueError("Unknown node.")
        if not isinstance(val, (int, float)) or not math.isfinite(val) or not 0.0 <= val <= 1.0:
            raise ValueError("Initial distress must be in [0, 1].")
        h[idx[nid]] = float(val)

    v = _value_shares(spec, values)
    state = np.where(h > 0.0, D, S)
    history = [h.copy()]
    h0 = h.copy()

    rounds = 0
    # [SECURE] Explicit iteration cap - each node propagates once, so n + 1 rounds suffice (Category 3)
    for _ in range(n + 1):
        active = state == D
        if not active.any():
            break
        cols = np.flatnonzero(active)
        h_new = np.minimum(1.0, h + np.asarray(W[:, cols] @ h[cols]).ravel())
        new_state = state.copy()
        new_state[active] = I
        new_state[(state == S) & (h_new > 0.0)] = D
        h, state = h_new, new_state
        history.append(h.copy())
        rounds += 1

    total = float(h @ v)
    return DebtRankResult(
        node_ids=tuple(spec.node_ids),
        h=h,
        history=np.array(history),
        values=v,
        total_distress=total,
        debtrank=total - float(h0 @ v),
        rounds=rounds,
    )


def _value_shares(spec: ModelSpec, values: dict[str, float] | None) -> np.ndarray:
    n = len(spec.nodes)
    if values is None:
        v = np.array([nd.value for nd in spec.nodes], dtype=float)
        if v.sum() <= 0.0:
            raise ValueError("Node values must not all be zero.")
        return v / v.sum()
    idx = spec.index()
    v = np.zeros(n, dtype=float)
    for nid, val in values.items():
        if nid not in idx:
            raise ValueError("Unknown node in values.")
        if not isinstance(val, (int, float)) or not math.isfinite(val) or val < 0.0:
            raise ValueError("Node values must be finite and non-negative.")
        v[idx[nid]] = float(val)
    total = v.sum()
    if total <= 0.0:
        raise ValueError("Node values must not all be zero.")
    return v / total


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: weights in [0, 1], node ids whitelisted, distress and values bounded and finite (Category 1)
#   - Infinite loop prevention: at most n + 1 rounds (Category 3)
#   - Encapsulation: history stores copies, result is a frozen dataclass (Category 6)
# Not Applied:
#   - [WARN] Authentication: not applicable - pure computation module
# --------------------------------------------------
