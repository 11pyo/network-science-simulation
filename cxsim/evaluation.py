"""
P1-SAP gate: does the propagation model rank affected objects better than
plain baselines? (design v2.1 section 4, P1-SAP)

Rankers (each returns reached, non-changed nodes in inspection order):
- closure: every node reachable from the changed set, ordered by hop count
           (where-used transitive closure, the main baseline)
- package: every object in the same package (devclass) as a changed object
- model:   linear engine impact with in-degree normalised weights

Metrics per case: precision@k, recall@k, how many objects must be inspected
to reach a recall level, and scope reduction against the closure baseline.
The verdict is descriptive. With fewer than SMALL_SAMPLE cases it is always
"inconclusive"; no significance is claimed for the retrospective set.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

from cxsim.engines import linear
from cxsim.sap import VALID_LABEL_SOURCES, ImpactGraph, node_id

SMALL_SAMPLE = 30
DEFAULT_BULK_THRESHOLD = 50
# Declared decision thresholds (provisional, design v2.1): the model must lead the
# closure baseline by this much in mean recall@PRIMARY_K to count as "ahead".
PRIMARY_K = 10
LEAD_MARGIN = 0.05
IMPACT_TOL = 1e-12
BASELINES = ("closure", "package")
# Customer objects (Z/Y namespace, incl. function-group / module-pool main programs).
_CUSTOM_PREFIXES = ("Z", "Y", "SAPLZ", "SAPLY", "SAPMZ", "SAPMY", "LZ", "LY")


def is_custom(label: str) -> bool:
    """label is "TYPE:NAME"."""
    return label.split(":", 1)[1].startswith(_CUSTOM_PREFIXES)


@dataclass(frozen=True)
class Case:
    case_id: str
    trkorr: str
    changed: tuple[int, ...]
    truth: frozenset[int]
    label_sources: tuple[str, ...]


# ---------------------------------------------------------------- cases

def build_cases(graph: ImpactGraph, transports, labels, bulk_threshold: int = DEFAULT_BULK_THRESHOLD):
    """Return (cases, dropped_counts). Bulk migration requests are excluded."""
    by_tr: dict[str, set[int]] = defaultdict(set)
    bulk: set[str] = set()
    for t in transports:
        tr = (t["trkorr"] or "").strip()
        try:
            count = int(t["request_obj_count"])
        except (TypeError, ValueError):
            raise ValueError("transports.csv: request_obj_count must be an integer.")
        if count > bulk_threshold:
            bulk.add(tr)
            continue
        nid = graph.id_of(t["obj_type"], t["obj_name"])
        if nid is not None:
            by_tr[tr].add(graph.index[nid])

    grouped: dict[str, dict] = {}
    for lab in labels:
        src = (lab["label_source"] or "").strip()
        # [SECURE] Whitelist label source values (Category 1)
        if src not in VALID_LABEL_SOURCES:
            raise ValueError("labels.csv: unknown label_source.")
        cid = (lab["case_id"] or "").strip()
        g = grouped.setdefault(cid, {"trkorr": (lab["trkorr"] or "").strip(), "affected": set(), "sources": set(), "missing": 0})
        nid = graph.id_of(lab["affected_type"], lab["affected_name"])
        if nid is None:
            g["missing"] += 1
        else:
            g["affected"].add(graph.index[nid])
        g["sources"].add(src)

    cases, dropped = [], defaultdict(int)
    for cid, g in sorted(grouped.items()):
        tr = g["trkorr"]
        if tr in bulk:
            dropped["bulk_transport"] += 1
            continue
        changed = by_tr.get(tr, set())
        if not changed:
            dropped["changed_not_in_graph"] += 1
            continue
        truth = g["affected"] - changed
        if not truth:
            dropped["no_affected_in_graph"] += 1
            continue
        cases.append(Case(cid, tr, tuple(sorted(changed)), frozenset(truth), tuple(sorted(g["sources"]))))
    return cases, dict(dropped)


# ---------------------------------------------------------------- structure

def scc_report(graph: ImpactGraph) -> dict:
    n_comp, labels = connected_components(graph.adjacency, directed=True, connection="strong")
    sizes = np.bincount(labels, minlength=n_comp)
    big = np.sort(sizes[sizes > 1])[::-1]
    return {
        "n_nodes": int(graph.n),
        "n_edges": int(graph.adjacency.nnz),
        "n_components": int(n_comp),
        "n_nontrivial_components": int(len(big)),
        "largest_component": int(big[0]) if len(big) else 1,
        "top_component_sizes": [int(x) for x in big[:10]],
        "components_over_dense_max": int((big > linear.SCC_DENSE_MAX).sum()),
        "scc_dense_max": linear.SCC_DENSE_MAX,
    }


# ---------------------------------------------------------------- rankers

def rank_closure(graph: ImpactGraph, changed) -> list[int]:
    """Multi-source BFS in impact direction; order by (hops, node id)."""
    A = graph.adjacency
    n = graph.n
    dist = np.full(n, -1, dtype=np.int64)
    frontier = np.array(sorted(set(changed)), dtype=np.int64)
    dist[frontier] = 0
    hop = 0
    # [SECURE] BFS ends after at most n levels (Category 3)
    while frontier.size and hop < n:
        hop += 1
        nxt = np.unique(A[frontier].indices)
        nxt = nxt[dist[nxt] < 0]
        dist[nxt] = hop
        frontier = nxt
    reached = np.flatnonzero(dist > 0)
    return sorted(reached.tolist(), key=lambda i: (dist[i], graph.ids[i]))


def rank_package(graph: ImpactGraph, changed) -> list[int]:
    pkgs = {graph.devclass[i] for i in changed if graph.devclass[i]}
    ch = set(changed)
    return sorted((i for i in range(graph.n) if graph.devclass[i] in pkgs and i not in ch),
                  key=lambda i: graph.ids[i])


class ModelRanker:
    """
    Linear engine on the where-used graph. Weights are normalised by the target's
    in-degree: w(source -> target) = share * lam / in_degree(target), so every
    node's incoming sum is share * lam < lam (stable, bounded amplification).

    basis="custom" (design v2.1 primary, method B): only edges whose SOURCE is a
    customer (Z/Y) object are kept and counted in the in-degree. Standard objects
    cannot be a change origin here and would only dilute every weight.
    basis="all" (method A, reference): every edge counts.
    """

    def __init__(self, graph: ImpactGraph, lam: float = 0.4, share: float = 0.9, basis: str = "custom"):
        if not 0.0 < lam <= 1.0 or not 0.0 < share < 1.0:
            raise ValueError("lam must be in (0, 1] and share in (0, 1).")
        if basis not in ("custom", "all"):
            raise ValueError("basis must be 'custom' or 'all'.")
        self.graph, self.lam, self.basis = graph, lam, basis
        coo = graph.adjacency.tocoo()
        if basis == "custom":
            custom = np.fromiter((is_custom(lab) for lab in graph.labels), dtype=bool, count=graph.n)
            keep = custom[coo.row]
            coo = sp.coo_matrix((coo.data[keep], (coo.row[keep], coo.col[keep])), shape=coo.shape)
        indeg = np.bincount(coo.col, minlength=graph.n).astype(float)
        w = share * lam / indeg[coo.col]
        # A[target, source] = weight (engine convention)
        self.A = sp.csr_matrix((w, (coo.col, coo.row)), shape=(graph.n, graph.n))
        self.rho = linear.spectral_radius(self.A, lam)
        if self.rho >= 1.0 - linear.STABILITY_TOL:
            raise linear.UnstableModelError(self.rho)

    def __call__(self, changed) -> list[int]:
        s = np.zeros(self.graph.n)
        s[list(changed)] = 1.0
        x = np.abs(linear.total_impact(self.A, self.lam, s))
        ch = set(changed)
        idx = [i for i in np.flatnonzero(x > IMPACT_TOL * len(ch)) if i not in ch]
        return sorted(idx, key=lambda i: (-x[i], self.graph.ids[i]))


# ---------------------------------------------------------------- metrics

def precision_at_k(rank, truth, k: int) -> float:
    return len(set(rank[:k]) & truth) / k


def recall_at_k(rank, truth, k: int) -> float:
    return len(set(rank[:k]) & truth) / len(truth)


def inspect_to_recall(rank, truth, level: float) -> int | None:
    need = math.ceil(level * len(truth))
    hits = 0
    for m, node in enumerate(rank, start=1):
        if node in truth:
            hits += 1
            if hits >= need:
                return m
    return None


def default_rankers(graph: ImpactGraph, lam: float = 0.4, share: float = 0.9) -> dict:
    """name -> callable(changed) returning the inspection order."""
    return {
        "closure": lambda ch: rank_closure(graph, ch),
        "package": lambda ch: rank_package(graph, ch),
        "model": ModelRanker(graph, lam=lam, share=share, basis="custom"),       # primary (B)
        "model_all_indegree": ModelRanker(graph, lam=lam, share=share, basis="all"),  # reference (A)
    }


def evaluate(graph: ImpactGraph, cases, rankers: dict, ks=(5, 10, 20), levels=(0.5, 0.8)) -> dict:
    """rankers: name -> callable(changed) -> ordered node indices; must include "closure"."""
    if "closure" not in rankers:
        raise ValueError("The closure baseline is required.")
    out: dict = {"n_cases": len(cases), "rankers": {}}
    per_case: dict[str, list] = {name: [] for name in rankers}
    for c in cases:
        for name, fn in rankers.items():
            per_case[name].append(fn(c.changed))

    for name in rankers:
        ranks = per_case[name]
        r: dict = {}
        for k in ks:
            r[f"precision@{k}"] = _mean([precision_at_k(rk, c.truth, k) for rk, c in zip(ranks, cases)])
            r[f"recall@{k}"] = _mean([recall_at_k(rk, c.truth, k) for rk, c in zip(ranks, cases)])
        r["max_recall"] = _mean([len(set(rk) & c.truth) / len(c.truth) for rk, c in zip(ranks, cases)])
        r["mean_list_length"] = _mean([len(rk) for rk in ranks])
        for lv in levels:
            m = [inspect_to_recall(rk, c.truth, lv) for rk, c in zip(ranks, cases)]
            got = [x for x in m if x is not None]
            r[f"reach_recall_{lv}"] = len(got) / len(cases) if cases else float("nan")
            r[f"median_inspect_for_recall_{lv}"] = float(np.median(got)) if got else None
            if name != "closure":
                base = [inspect_to_recall(rk, c.truth, lv) for rk, c in zip(per_case["closure"], cases)]
                red = [1 - a / b for a, b in zip(m, base) if a is not None and b]
                r[f"scope_reduction_vs_closure_{lv}"] = _mean(red) if red else None
        out["rankers"][name] = r
    out["verdict"] = verdict(out)
    return out


def verdict(results: dict) -> str:
    """Descriptive three-way outcome from the design: ahead / not ahead / inconclusive."""
    if results["n_cases"] < SMALL_SAMPLE or "model" not in results["rankers"]:
        return "inconclusive"
    key = f"recall@{PRIMARY_K}"
    model = results["rankers"]["model"].get(key, float("nan"))
    # Only the declared baselines count; reference model variants never act as a baseline.
    best_base = max(v.get(key, float("nan")) for k, v in results["rankers"].items() if k in BASELINES)
    if math.isnan(model) or math.isnan(best_base):
        return "inconclusive"
    return "model_ahead" if model >= best_base + LEAD_MARGIN else "baseline_not_beaten"


def _mean(xs) -> float:
    return float(np.mean(xs)) if len(xs) else float("nan")


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: label_source whitelist, integer request counts, objects resolved only via node_id map (Category 1)
#   - Infinite loop prevention: BFS bounded by node count (Category 3)
#   - Error handling: malformed inputs raise explicit ValueError, never skipped silently; dropped cases counted (Category 4)
# Not Applied:
#   - [WARN] Statistical significance: deliberately not computed for the small retrospective set (design v2.1)
#   - [WARN] Authentication: not applicable - offline evaluation module
# --------------------------------------------------
