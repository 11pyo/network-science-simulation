"""P1-SAP converter, baselines and gate metrics on a small synthetic extract."""

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

from cxsim import evaluation as ev
from cxsim import sap
from cxsim.spec import NODE_ID_PATTERN

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

USES = [
    # user uses used  ->  impact edge used -> user
    ("PROG", "ZP_A", "TABL", "ZT_1", "D010TAB", ""),
    ("PROG", "ZP_B", "TABL", "ZT_1", "D010TAB", ""),
    ("FUNC", "Z_F1", "TABL", "ZT_1", "D010TAB", ""),
    ("PROG", "ZP_C", "FUNC", "Z_F1", "CROSS", "F"),
    ("TRAN", "ZTX", "PROG", "ZP_A", "TSTC", ""),
    ("PROG", "ZP_A", "TABL", "ZT_1", "WBCROSSGT", "DA"),  # duplicate pair from another source
]
OBJECTS = [
    ("TABL", "ZT_1", "ZPKGA", ""), ("PROG", "ZP_A", "ZPKGA", ""), ("PROG", "ZP_B", "ZPKGB", ""),
    ("FUNC", "Z_F1", "ZPKGA", ""), ("PROG", "ZP_C", "ZPKGC", ""), ("TRAN", "ZTX", "ZPKGA", ""),
]


def _rows(cols, data):
    return [dict(zip(cols, r)) for r in data]


@pytest.fixture
def graph():
    return sap.build_impact_graph(_rows(sap.USES_COLUMNS, USES), _rows(sap.OBJECT_COLUMNS, OBJECTS))


def ix(graph, t, n):
    return graph.index[sap.node_id(t, n)]


# ---------------------------------------------------------------- ids and graph

def test_node_id_deterministic_valid_and_type_aware():
    a = sap.node_id("PROG", "ZSD_ORDER")
    assert a == sap.node_id("prog", " ZSD_ORDER ")
    assert re.fullmatch(NODE_ID_PATTERN, a)
    assert sap.node_id("TABL", "ZSD_ORDER") != a
    for name in ("/ABC/CL_PRICING=====CP", "SAPLZAB_FG01", "Z" * 40):
        assert re.fullmatch(NODE_ID_PATTERN, sap.node_id("CLAS", name))


@pytest.mark.parametrize("t,n", [("PROG", "ZP;DROP"), ("PROG", ""), ("P R", "ZP"), ("PROG", "../x y")])
def test_invalid_sap_names_rejected(t, n):
    with pytest.raises(ValueError):
        sap.node_id(t, n)


def test_flip_used_to_user_and_duplicates_collapse(graph):
    A = graph.adjacency
    assert A[ix(graph, "TABL", "ZT_1"), ix(graph, "PROG", "ZP_A")] == 1.0   # table change affects program
    assert A[ix(graph, "PROG", "ZP_A"), ix(graph, "TABL", "ZT_1")] == 0.0   # never the reverse
    assert A.nnz == 5                                                      # 6 rows, one duplicate pair
    assert graph.devclass[ix(graph, "PROG", "ZP_C")] == "ZPKGC"


def test_unknown_source_rejected():
    rows = _rows(sap.USES_COLUMNS, [("PROG", "ZP_A", "TABL", "ZT_1", "GUESS", "")])
    with pytest.raises(ValueError):
        sap.build_impact_graph(rows)


# ---------------------------------------------------------------- files and manifest

def _write(dirpath, name, cols, data):
    with (dirpath / name).open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(data)


def _manifest(dirpath, names):
    lines = []
    for n in names:
        lines.append(f"{hashlib.sha256((dirpath / n).read_bytes()).hexdigest()}  {n}")
    (dirpath / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


TRANSPORTS = [
    ("ABCK900001", "20260301", "TABL", "ZT_1", "2", "R3TR", "TABL"),
    ("ABCK900001", "20260301", "PROG", "ZP_A", "2", "R3TR", "PROG"),
    ("ABCK900002", "20260305", "PROG", "ZP_A", "3", "LIMU", "REPS"),  # follow-up within 14 days sharing ZP_A
    ("ABCK900002", "20260305", "PROG", "ZP_C", "3", "R3TR", "PROG"),
    ("ABCK900002", "20260305", "SUSH", "Z_ABC_COMPOSITE_KEY                RF", "3", "R3TR", "SUSH"),  # composite key
    ("ABCK900003", "20260401", "PROG", "ZP_A", "1", "R3TR", "PROG"),  # outside the window
    ("ABCK900009", "20260302", "PROG", "ZP_B", "900", "R3TR", "PROG"),  # bulk migration request
]


@pytest.fixture
def data_dir(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    _write(raw, "uses.csv", sap.USES_COLUMNS, USES)
    _write(raw, "objects.csv", sap.OBJECT_COLUMNS, OBJECTS)
    _write(raw, "transports.csv", sap.TRANSPORT_COLUMNS, TRANSPORTS)
    _write(raw, "raw_tstc.csv", ("TCODE", "PGMNA"), [("ZTX", "ZP_A")])
    _manifest(raw, ["uses.csv", "objects.csv", "transports.csv", "raw_tstc.csv"])
    return tmp_path


def test_manifest_ok(data_dir):
    assert "uses.csv" in sap.verify_manifest(data_dir / "raw")


def test_manifest_detects_tampering(data_dir):
    with (data_dir / "raw" / "uses.csv").open("a", encoding="utf-8") as f:
        f.write("PROG,ZEVIL,TABL,ZT_1,D010TAB,\n")
    with pytest.raises(ValueError, match="SHA-256"):
        sap.verify_manifest(data_dir / "raw")


def test_manifest_rejects_unlisted_csv(data_dir):
    _write(data_dir / "raw", "extra.csv", ("a",), [("1",)])
    with pytest.raises(ValueError, match="not listed"):
        sap.verify_manifest(data_dir / "raw")


def test_manifest_ignores_traversal_entries_and_requires_core_files(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "MANIFEST.sha256").write_text("0" * 64 + "  ../uses.csv\n", encoding="utf-8")
    with pytest.raises(ValueError, match="required"):
        sap.verify_manifest(raw)


def test_read_csv_rejects_wrong_header(data_dir):
    with pytest.raises(ValueError, match="header"):
        sap.read_csv(data_dir / "raw" / "objects.csv", sap.USES_COLUMNS)


# ---------------------------------------------------------------- baselines and model

def test_closure_orders_by_hops_then_id(graph):
    rank = ev.rank_closure(graph, [ix(graph, "TABL", "ZT_1")])
    hop1 = sorted([ix(graph, "PROG", "ZP_A"), ix(graph, "PROG", "ZP_B"), ix(graph, "FUNC", "Z_F1")],
                  key=lambda i: graph.ids[i])
    hop2 = sorted([ix(graph, "PROG", "ZP_C"), ix(graph, "TRAN", "ZTX")], key=lambda i: graph.ids[i])
    assert rank == hop1 + hop2


def test_closure_from_leaf_is_empty(graph):
    assert ev.rank_closure(graph, [ix(graph, "PROG", "ZP_C")]) == []


def test_package_baseline(graph):
    rank = ev.rank_package(graph, [ix(graph, "TABL", "ZT_1")])
    assert set(rank) == {ix(graph, "PROG", "ZP_A"), ix(graph, "FUNC", "Z_F1"), ix(graph, "TRAN", "ZTX")}


def test_model_ranker_reached_only_and_stable(graph):
    m = ev.ModelRanker(graph)
    assert m.rho == pytest.approx(1 - m.lam)                # acyclic
    rank = m([ix(graph, "TABL", "ZT_1")])
    assert set(rank) == set(ev.rank_closure(graph, [ix(graph, "TABL", "ZT_1")]))
    assert rank.index(ix(graph, "PROG", "ZP_A")) < rank.index(ix(graph, "TRAN", "ZTX"))  # attenuates per hop
    assert m([ix(graph, "PROG", "ZP_C")]) == []


def test_scc_report_counts_cycles():
    uses = _rows(sap.USES_COLUMNS, USES + [("TABL", "ZT_1", "PROG", "ZP_C", "CROSS", "S")])  # closes a cycle
    g = sap.build_impact_graph(uses)
    rep = ev.scc_report(g)
    assert rep["n_nontrivial_components"] == 1 and rep["largest_component"] == 3


# ---------------------------------------------------------------- metrics and labels

def test_metrics_by_hand():
    rank, truth = [5, 2, 9, 7], frozenset({2, 7, 11})
    assert ev.precision_at_k(rank, truth, 2) == 0.5
    assert ev.recall_at_k(rank, truth, 4) == pytest.approx(2 / 3)
    assert ev.inspect_to_recall(rank, truth, 0.5) == 4     # need ceil(1.5) = 2 hits
    assert ev.inspect_to_recall(rank, truth, 1.0) is None  # 11 never listed


def test_rework_labels_window_overlap_and_bulk():
    rows = _rows(sap.TRANSPORT_COLUMNS, TRANSPORTS)
    labs = sap.rework_labels(rows, window_days=14, bulk_threshold=50)
    assert {(l["case_id"], l["affected_name"]) for l in labs} == {("rw_ABCK900001_ABCK900002", "ZP_C")}
    assert all("not an incident" in l["note"] for l in labs)


def test_build_cases_and_drop_reasons(graph):
    tr = _rows(sap.TRANSPORT_COLUMNS, TRANSPORTS)
    labels = sap.rework_labels(tr) + [
        {"case_id": "c_bulk", "trkorr": "ABCK900009", "affected_type": "PROG", "affected_name": "ZP_C",
         "label_source": "card", "label_date": "", "note": ""},
        {"case_id": "c_none", "trkorr": "ABCK900001", "affected_type": "PROG", "affected_name": "ZP_A",
         "label_source": "card", "label_date": "", "note": ""},
    ]
    cases, dropped = ev.build_cases(graph, tr, labels)
    assert [c.case_id for c in cases] == ["rw_ABCK900001_ABCK900002"]
    assert dropped == {"bulk_transport": 1, "no_affected_in_graph": 1}
    assert cases[0].truth == {ix(graph, "PROG", "ZP_C")}


def test_bad_label_source_rejected(graph):
    bad = [{"case_id": "x", "trkorr": "ABCK900001", "affected_type": "PROG", "affected_name": "ZP_C",
            "label_source": "guess", "label_date": "", "note": ""}]
    with pytest.raises(ValueError):
        ev.build_cases(graph, _rows(sap.TRANSPORT_COLUMNS, TRANSPORTS), bad)


def test_verdict_rules():
    base = {"rankers": {"closure": {"recall@10": 0.50}, "package": {"recall@10": 0.30}}}
    assert ev.verdict({**base, "n_cases": 10}) == "inconclusive"            # small sample, always
    r = {"n_cases": 40, "rankers": {**base["rankers"], "model": {"recall@10": 0.56}}}
    assert ev.verdict(r) == "model_ahead"
    r["rankers"]["model"]["recall@10"] = 0.53                                 # inside the margin
    assert ev.verdict(r) == "baseline_not_beaten"


def test_pipeline_end_to_end(data_dir):
    import p1_sap_pipeline as pipe

    res = pipe.run(data_dir)
    assert res["scc"]["n_nodes"] == 6
    ev_rw = res["label_sets"]["rework_proxy"]
    assert ev_rw["n_cases"] == 1 and ev_rw["verdict"] == "inconclusive"
    assert ev_rw["rankers"]["closure"]["max_recall"] == 1.0
    out = json.loads((data_dir / "derived" / "evaluation.json").read_text(encoding="utf-8"))
    assert out["settings"]["primary_k"] == ev.PRIMARY_K
    assert (data_dir / "derived" / "id_map.csv").is_file()
    assert pipe.main(["--data-dir", str(data_dir), "--window-days", "0"]) == 2


def test_pipeline_stops_on_tampered_input(data_dir):
    import p1_sap_pipeline as pipe

    (data_dir / "raw" / "objects.csv").write_text("x", encoding="utf-8")
    assert pipe.main(["--data-dir", str(data_dir)]) == 1



# ---------------------------------------------------------------- real-extract adaptations (2026-11-12)

def test_new_sources_accepted_and_invalid_names_counted_not_fatal():
    uses = _rows(sap.USES_COLUMNS, USES + [
        ("FUGR", "ZFG01", "PROG", "LZFG01F01", "D010INC", ""),
        ("FUNC", "Z_FM1", "FUGR", "ZFG01", "ENLFDIR", ""),
        ("PROG", "/SDF/LCCMS_DLU06", "PROG", "Z>EBO", "CROSS", "R"),     # stray name
    ])
    objs = _rows(sap.OBJECT_COLUMNS, OBJECTS + [("SICF", "ZSVC      0001", "ZPKGA", "")])  # composite key
    g = sap.build_impact_graph(uses, objs)
    assert g.skipped["uses_invalid_name"] == 1 and g.skipped["objects_invalid_name"] == 1
    assert g.id_of("PROG", "Z>EBO") is None and g.id_of("SUSH", "A    B") is None
    assert g.adjacency[ix(g, "FUGR", "ZFG01"), ix(g, "FUNC", "Z_FM1")] == 1.0   # group change affects member FM


def test_rework_counts_composite_transport_rows():
    stats = {}
    labs = sap.rework_labels(_rows(sap.TRANSPORT_COLUMNS, TRANSPORTS), stats=stats)
    assert stats == {"transport_rows_invalid_name": 1}
    assert {l["affected_name"] for l in labs} == {"ZP_C"}


def test_custom_basis_ignores_standard_sources_in_in_degree():
    uses = _rows(sap.USES_COLUMNS, [
        ("PROG", "ZP_A", "TABL", "ZT_1", "D010TAB", ""),
        ("PROG", "ZP_A", "TABL", "VBAK", "D010TAB", ""),
        ("PROG", "ZP_A", "TABL", "MARA", "D010TAB", ""),
    ])
    g = sap.build_impact_graph(uses)
    a, t = ix(g, "PROG", "ZP_A"), ix(g, "TABL", "ZT_1")
    m_custom = ev.ModelRanker(g, lam=0.4, share=0.9, basis="custom")
    m_all = ev.ModelRanker(g, lam=0.4, share=0.9, basis="all")
    assert m_custom.A[a, t] == pytest.approx(0.36)        # in-degree 1 (only ZT_1 is custom)
    assert m_all.A[a, t] == pytest.approx(0.12)           # in-degree 3 dilutes the weight
    assert m_custom.A[a, ix(g, "TABL", "VBAK")] == 0.0     # standard source dropped
    with pytest.raises(ValueError):
        ev.ModelRanker(g, basis="weird")


def test_reference_model_never_counts_as_baseline():
    r = {"n_cases": 40, "rankers": {
        "closure": {"recall@10": 0.50}, "package": {"recall@10": 0.30},
        "model": {"recall@10": 0.56}, "model_all_indegree": {"recall@10": 0.90}}}
    assert ev.verdict(r) == "model_ahead"


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: tests cover invalid SAP names, unknown sources, wrong headers, bad label sources (Category 1)
#   - Integrity: tests cover tampered, unlisted and traversal manifest entries (Category 5)
#   - Leftover debug code: synthetic data only, no credentials or real SAP extracts (Category 6)
# Not Applied:
#   - [WARN] Authentication: not applicable - offline unit tests
# --------------------------------------------------
