# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 11pyo
"""
Conversion of the legacy presets into the new declarative spec.

Legacy weights are undirected "correlations" whose sources are unverified
and whose direction cannot be recovered. They are imported as:
- two directed edges per pair (a -> b and b -> a), evidence "legacy";
- rescaled so every node's incoming |weight| sum (at the range's high end)
  stays below 0.9 * self_decay.low. By Gershgorin this keeps EVERY sample
  stable; the weights then mean "share of influence", not correlation;
- given a range [0.5 w, 1.0 w] to show they are not point estimates.
"""

from __future__ import annotations

from collections import defaultdict

from cxsim.spec import EdgeSpec, ModelSpec, NodeSpec, Range

STABILITY_SHARE = 0.9
RANGE_WIDTH = (0.5, 1.0)


def from_legacy_preset(
    preset: dict,
    name: str,
    self_decay: Range = Range(low=0.3, high=0.5),
) -> ModelSpec:
    nodes = tuple(
        NodeSpec(id=nid, label=ko, color=color) for nid, ko, _en, color in preset["nodes"]
    )
    corr = {tuple(k): float(v) for k, v in preset["default_weights"].items() if float(v) != 0.0}

    in_strength: dict[str, float] = defaultdict(float)
    for (a, b), r in corr.items():
        in_strength[a] += abs(r)
        in_strength[b] += abs(r)
    peak = max(in_strength.values()) if in_strength else 1.0
    scale = STABILITY_SHARE * self_decay.low / peak

    edges = []
    for (a, b), r in sorted(corr.items()):
        w = r * scale
        lo, hi = sorted((w * RANGE_WIDTH[0], w * RANGE_WIDTH[1]))
        note = f"legacy undirected correlation r={r:.2f}, rescaled x{scale:.4f}; source unverified"
        for src, dst in ((a, b), (b, a)):
            edges.append(
                EdgeSpec(
                    source=src,
                    target=dst,
                    weight=Range(low=round(lo, 6), high=round(hi, 6)),
                    evidence="legacy",
                    note=note,
                )
            )

    return ModelSpec(
        name=name,
        description=(
            "Imported from the legacy preset. Directions are symmetric because the original "
            "weights were undirected; magnitudes are relative only. Not validated against data."
        ),
        legacy=True,
        normalization="legacy_in_strength",
        self_decay=self_decay,
        nodes=nodes,
        edges=tuple(edges),
    )


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: every converted node and edge re-validated by the pydantic spec (Category 1)
# Not Applied:
#   - [WARN] Authentication: not applicable - offline conversion helper over repo-controlled presets
# --------------------------------------------------
