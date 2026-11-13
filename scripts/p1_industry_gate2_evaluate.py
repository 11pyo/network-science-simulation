# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 11pyo
"""
P1-industry gate 2, phase 2: evaluate the FROZEN predictions against outcome data.

Only pre-registered specs are evaluated (RENEWAL_DESIGN.md: 98e957d, aa265ac, c09c3de, 2c3eb45).
The predictions file must match the hash recorded before the outcome was opened.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cxsim import gate2  # noqa: E402

FROZEN_PRED_SHA = "512f059813268b976566392d492071b98a95629062229d1d6d44997f1df087bd"
MAP_FILE = ROOT / "data" / "ksic_to_io33_gate2.csv"
MM_FILE = "outcome/mining_manufacturing_production_index_annual_2015_2023.csv"
SV_FILE = "outcome/service_production_index_annual_2015_2023.csv"
W_FILE = "weights_va_2019_ksic2_mining_manufacturing.csv"

MAIN_15 = ("B", "C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "C09", "C10", "C11", "C12", "C13", "D")
MAIN_14 = tuple(s for s in MAIN_15 if s != "D")
SERVICES_12 = ("G", "H", "I", "J", "K", "L", "M", "N", "P", "Q", "R", "S")


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _code(cell: str) -> str:
    return cell.strip().split()[0]


def _num(x: str) -> float:
    x = x.strip().replace(",", "")
    if x in ("", "-", "X"):
        raise ValueError("missing value")
    return float(x)


def load_mapping() -> dict[str, str]:
    """outcome industry code (B, C10..C33, D) -> IO sector, main comparison rows only."""
    out = {}
    with MAP_FILE.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(line for line in f if not line.startswith("#")):
            if r["in_main_comparison"] != "yes":
                continue
            div = r["ksic_div"]
            if div == "05+06+07":
                out["B"] = "B"
            elif div == "35":
                out["D"] = "D"
            else:
                out[f"C{div}"] = r["io_sector"]
    return out


def load_mm_index(path: Path) -> tuple[dict[str, float], dict[str, float]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    h = rows[0]
    i19 = next(i for i, c in enumerate(h) if c.strip().endswith("2019"))
    i20 = next(i for i, c in enumerate(h) if c.strip().endswith("2020"))
    a, b = {}, {}
    for r in rows[2:]:
        c = _code(r[1])
        try:
            a[c], b[c] = _num(r[i19]), _num(r[i20])
        except ValueError:
            continue
    return a, b


def load_service_index(path: Path) -> tuple[dict[str, float], dict[str, float]]:
    """Constant-price (불변) index; columns come in (경상, 불변) pairs per year."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    h, kind = rows[0], rows[1]
    col = {}
    for i, (y, k) in enumerate(zip(h, kind)):
        if "불변" in k and y.strip()[-4:] in ("2019", "2020"):
            col[y.strip()[-4:]] = i
    if set(col) != {"2019", "2020"}:
        raise ValueError("Service index constant-price columns not found.")
    a, b = {}, {}
    for r in rows[2:]:
        c = _code(r[0])
        try:
            a[c], b[c] = _num(r[col["2019"]]), _num(r[col["2020"]])
        except ValueError:
            continue
    return a, b


def load_weights(path: Path) -> tuple[dict[str, float], dict[str, float]]:
    """(value added 2019, output 2019) by outcome code."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    va, out = {}, {}
    for r in rows[2:]:
        c = _code(r[1])
        try:
            out[c], va[c] = _num(r[2]), _num(r[3])
        except ValueError:
            continue
    return va, out


def run(data_dir: Path) -> dict:
    derived, g2 = data_dir / "derived", data_dir / "gate2"
    pred_path = derived / "gate2_predictions.json"
    # [SECURE] Frozen-prediction integrity check: refuse to evaluate altered predictions (Category 5)
    if _sha(pred_path) != FROZEN_PRED_SHA:
        raise ValueError("Predictions file does not match the frozen hash.")
    prov = (g2 / "PROVENANCE_gate2_files.txt").read_text(encoding="utf-8")
    for f in (MM_FILE, SV_FILE, W_FILE):
        if _sha(g2 / f) not in prov:
            raise ValueError(f"{f}: SHA-256 not in provenance.")

    with pred_path.open(encoding="utf-8") as f:
        P = json.load(f)
    codes = tuple(P["codes"])
    mapping = load_mapping()
    i19, i20 = load_mm_index(g2 / MM_FILE)
    s19, s20 = load_service_index(g2 / SV_FILE)
    va, outw = load_weights(g2 / W_FILE)
    ones = {k: 1.0 for k in mapping}
    for k in ("B", "D"):           # 1:1 sectors: weight irrelevant
        va.setdefault(k, 1.0)
        outw.setdefault(k, 1.0)

    actual = {
        "va": gate2.aggregate_growth(i19, i20, va, mapping),
        "output": gate2.aggregate_growth(i19, i20, outw, mapping),
        "simple": gate2.aggregate_growth(i19, i20, ones, mapping),
    }
    svc_actual = {s: s20[s] / s19[s] - 1.0 for s in SERVICES_12}

    def pred(name):
        d = P["specs"][name]
        return gate2.Predictions(np.array(d["model"]), np.array(d["direct"]), d["uniform"])

    runs = {
        "main": (pred("main"), actual["va"], MAIN_15),
        "s1_nominal": (pred("s1_nominal"), actual["va"], MAIN_15),
        "s2_incl_inventories": (pred("s2_incl_inventories"), actual["va"], MAIN_15),
        "s3_14_sectors": (pred("main"), actual["va"], MAIN_14),
        "s4_fixed_composition": (pred("s4_fixed_composition"), actual["va"], MAIN_15),
        "w_output_weights": (pred("main"), actual["output"], MAIN_15),
        "w_simple_average": (pred("main"), actual["simple"], MAIN_15),
        "aux_services": (pred("main"), svc_actual, SERVICES_12),
    }
    results = {}
    for name, (pr, act, sectors) in runs.items():
        m = gate2.evaluate(pr, act, codes, sectors)
        results[name] = {"n": m.n, "rho_model": m.rho_model, "rho_direct": m.rho_direct,
                         "rho_diff": m.rho_model - m.rho_direct, "rho_diff_ci90": list(m.rho_diff_ci90),
                         "mae_model_pp": m.mae_model, "mae_direct_pp": m.mae_direct,
                         "mae_uniform_pp": m.mae_uniform, "verdict": m.verdict, "notes": m.notes}

    final = gate2.combine_verdicts(results["main"]["verdict"], results["s4_fixed_composition"]["verdict"])
    if results["s1_nominal"]["verdict"] != results["main"]["verdict"]:
        final += " / 불안정(명목 민감도에서 판정이 뒤집힘)"

    main_p = P["specs"]["main"]
    table = []
    for s in MAIN_15 + SERVICES_12:
        j = codes.index(s)
        act = actual["va"].get(s, svc_actual.get(s))
        table.append({"sector": s, "shock_trillion_krw": main_p["shock"][j] / 1e6,
                      "direct_pct": main_p["direct"][j] * 100, "model_pct": main_p["model"][j] * 100,
                      "actual_pct": act * 100, "group": "main" if s in MAIN_15 else "services"})
    out = {"final_verdict": final, "results": results, "sector_table": table,
           "weights_used_main": "2019 value added (KOSIS DT_1FS1004, 10+ employees)",
           "predictions_sha256": FROZEN_PRED_SHA}
    fd, tmp = tempfile.mkstemp(prefix=".gate2res.", suffix=".tmp", dir=derived)
    try:
        # [SECURE] Atomic write (Category 3, 5)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1)
        os.replace(tmp, derived / "gate2_results.json")
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return out


def main() -> int:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        print("LOCALAPPDATA is not set.", file=sys.stderr)
        return 2
    try:
        out = run(Path(base) / "nss-renewal-data" / "io_bok")
    except (ValueError, OSError, KeyError) as e:
        # [SECURE] Short reason, no stack trace (Category 4)
        print(f"Gate 2 evaluation stopped: {e}", file=sys.stderr)
        return 1
    print("FINAL:", out["final_verdict"])
    for k, r in out["results"].items():
        lo, hi = r["rho_diff_ci90"]
        print(f"{k:22s} n={r['n']:2d} rho M={r['rho_model']:+.3f} D={r['rho_direct']:+.3f} diff={r['rho_diff']:+.3f} "
              f"CI90=[{lo:+.3f},{hi:+.3f}] MAE M={r['mae_model_pp']:.2f} D={r['mae_direct_pp']:.2f} "
              f"U={r['mae_uniform_pp']:.2f} | {r['verdict']}")
    print("sector  shock(조)  direct%  model%  actual%")
    for t in out["sector_table"]:
        print(f"{t['sector']:4s} {t['shock_trillion_krw']:+8.2f} {t['direct_pct']:+7.2f} {t['model_pct']:+7.2f} "
              f"{t['actual_pct']:+7.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Integrity: frozen predictions hash enforced; outcome/weight files checked against provenance (Category 5)
#   - Input validation: missing/suppressed cells ('-', 'X') skipped explicitly; required columns checked (Category 1)
#   - Error handling: short messages, non-zero exit; atomic output write (Category 3, 4)
# Not Applied:
#   - [WARN] Authentication: not applicable - local developer script
# --------------------------------------------------
