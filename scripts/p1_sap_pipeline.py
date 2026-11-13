"""
P1-SAP pipeline: verify extract -> impact graph -> SCC report -> gate evaluation.

Usage (data stays outside the repo and outside Google Drive):
    python scripts/p1_sap_pipeline.py                 # default %LOCALAPPDATA%/nss-renewal-data/sap_extract
    python scripts/p1_sap_pipeline.py --data-dir D:/somewhere/sap_extract
    python scripts/p1_sap_pipeline.py --scope-prefix ZPKGA

Reads  <data-dir>/raw/{uses,objects,transports[,labels]}.csv + MANIFEST.sha256
Writes <data-dir>/derived/{id_map.csv, scc_report.json, evaluation.json}
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cxsim import evaluation as ev  # noqa: E402
from cxsim import sap  # noqa: E402

logger = logging.getLogger("p1_sap")


def run(data_dir: Path, scope_prefixes: tuple[str, ...] = (), window_days: int = 14,
        bulk_threshold: int = ev.DEFAULT_BULK_THRESHOLD) -> dict:
    raw, derived = data_dir / "raw", data_dir / "derived"
    if not raw.is_dir():
        raise ValueError("raw/ directory not found under the data directory.")
    derived.mkdir(exist_ok=True)

    sap.verify_manifest(raw)
    uses = sap.read_csv(raw / "uses.csv", sap.USES_COLUMNS)
    objects = sap.read_csv(raw / "objects.csv", sap.OBJECT_COLUMNS)
    transports = sap.read_csv(raw / "transports.csv", sap.TRANSPORT_COLUMNS)
    labels = sap.read_csv(raw / "labels.csv", sap.LABEL_COLUMNS) if (raw / "labels.csv").is_file() else []

    graph = sap.build_impact_graph(uses, objects)
    sap.write_id_map(graph, derived / "id_map.csv")
    scc = ev.scc_report(graph)
    _atomic_json(derived / "scc_report.json", scc)

    label_stats: dict = {}
    rework = sap.rework_labels(transports, window_days=window_days, bulk_threshold=bulk_threshold, stats=label_stats)
    result: dict = {"scc": scc, "label_sets": {}, "skipped_rows": {**graph.skipped, **label_stats}}
    rankers = ev.default_rankers(graph)
    for name, rows in (("labels", labels), ("rework_proxy", rework)):
        cases, dropped = ev.build_cases(graph, transports, rows, bulk_threshold=bulk_threshold)
        if scope_prefixes:
            cases = [c for c in cases if any(graph.devclass[i].startswith(scope_prefixes) for i in c.changed)]
        res = ev.evaluate(graph, cases, rankers) if cases else {"n_cases": 0, "verdict": "inconclusive"}
        res["dropped"] = dropped
        result["label_sets"][name] = res
    result["settings"] = {"scope_prefixes": list(scope_prefixes), "window_days": window_days,
                          "bulk_threshold": bulk_threshold, "small_sample": ev.SMALL_SAMPLE,
                          "primary_k": ev.PRIMARY_K, "lead_margin": ev.LEAD_MARGIN}
    _atomic_json(derived / "evaluation.json", result)
    return result


def _atomic_json(path: Path, data: dict) -> None:
    fd, tmp = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".tmp", dir=path.parent)
    try:
        # [SECURE] Atomic write with context manager - no partial outputs (Category 3, 5)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=float)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--data-dir", type=Path, default=None)
    ap.add_argument("--scope-prefix", action="append", default=[],
                    help="devclass prefix of changed objects to keep (e.g. ZPKGA); repeatable")
    ap.add_argument("--window-days", type=int, default=14)
    ap.add_argument("--bulk-threshold", type=int, default=ev.DEFAULT_BULK_THRESHOLD)
    args = ap.parse_args(argv)
    # [SECURE] Bounded numeric options (Category 1)
    if not 1 <= args.window_days <= 365 or not 1 <= args.bulk_threshold <= 100000:
        logger.error("window-days must be 1..365 and bulk-threshold 1..100000.")
        return 2
    try:
        data_dir = (args.data_dir or sap.default_data_dir()).resolve()
        res = run(data_dir, tuple(args.scope_prefix), args.window_days, args.bulk_threshold)
    except (ValueError, OSError) as e:
        # [SECURE] Report a short reason; no stack trace for expected input problems (Category 4)
        logger.error("Pipeline stopped: %s", e)
        return 1
    scc = res["scc"]
    print(f"graph: {scc['n_nodes']:,} nodes, {scc['n_edges']:,} edges; largest SCC {scc['largest_component']:,} "
          f"(over dense limit: {scc['components_over_dense_max']})")
    print(f"skipped rows (not usable as nodes, by reason): {res['skipped_rows']}")
    for name, r in res["label_sets"].items():
        print(f"{name}: {r['n_cases']} cases, verdict={r['verdict']}, dropped={r.get('dropped')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Integrity: MANIFEST SHA-256 verified before any file is parsed (Category 5)
#   - Input validation: fixed file names, bounded CLI options, schema checks in cxsim.sap (Category 1)
#   - Error handling: expected failures logged with a short reason and non-zero exit, no silent skips (Category 4)
#   - Atomic writes for derived outputs (Category 3)
# Not Applied:
#   - [WARN] Data at rest: derived files are plain text under the user profile; encrypt the folder if policy requires
#   - [WARN] Authentication: not applicable - local developer script
# --------------------------------------------------
