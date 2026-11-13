"""
P1-industry gate 2, phase 1: compute and FREEZE predictions (no outcome data is read).

Specs (pre-registered in RENEWAL_DESIGN.md, 98e957d + aa265ac + c09c3de):
  main  : option A (2020 composition rescaled to NA nominal item growth), FD excl. inventories, real (PPI)
  s1    : as main, nominal (no PPI deflation)
  s2    : as main, final demand incl. inventories/valuables (9131, 9132)
  s3    : main shock, 14 sectors (D excluded)          -> same predictions as main; sector set differs
  s4    : option B, fixed 2019 composition x NA real item growth (2020 table not used)
  aux   : main shock, service sectors

Writes <data-dir>/derived/gate2_predictions.json and prints its SHA-256 so it can be
recorded (committed) before the outcome files are opened.
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

from cxsim import gate2, io_table  # noqa: E402

F2019 = "2019_투입산출표_생산자가격_통합대분류.xlsx"
F2020 = "(표)(2020실측)투입산출표_생산자가격_통합대분류.xlsx"
NA_FILE = "na_expenditure_nominal_real_annual_2013_2025.csv"
PPI_RAW = "ppi_basic_annual_2013_2025.csv"
PPI_MAP = ROOT / "data" / "ppi_to_io33_gate2.csv"

# National-accounts rows (2020 base) used per IO final-demand item; recorded in amendment 2.
NA_ITEM_ROWS = {
    "9111": "민간",
    "9112": "정부",
    "9121": "총고정자본형성(민간)",
    "9122": "총고정자본형성(정부)",
    "9131": "재고증감 및 귀중품 순취득",
    "9132": "재고증감 및 귀중품 순취득",
    "9140": "재화와 서비스의 수출",
}
NOMINAL_TABLE, REAL_TABLE = "2.1.2.2.3", "2.1.2.2.4"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def na_growth(path: Path) -> tuple[dict[str, float], dict[str, float]]:
    """(nominal, real) 2019->2020 growth per IO item code from the NA expenditure CSV."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    h = rows[0]
    i19, i20 = h.index("2019"), h.index("2020")
    found: dict[tuple[str, str], float] = {}
    for r in rows[1:]:
        table, name = r[0].strip(), r[1].strip()
        try:
            a, b = float(r[i19].replace(",", "")), float(r[i20].replace(",", ""))
        except ValueError:
            continue
        if a == 0.0:
            continue  # e.g. statistical discrepancy row; not an expenditure item used here
        key = (table[:9], name)
        # First occurrence wins: "민간" appears first under 최종소비지출 (private consumption).
        found.setdefault(key, b / a - 1.0)
    nominal, real = {}, {}
    for item, name in NA_ITEM_ROWS.items():
        for tab, out in ((NOMINAL_TABLE, nominal), (REAL_TABLE, real)):
            if (tab, name) not in found:
                raise ValueError(f"NA row not found: {tab} {name}")
            out[item] = found[(tab, name)]
    return nominal, real


def ppi_ratios(codes: tuple[str, ...], raw_ppi: Path | None = None) -> np.ndarray:
    """
    p_j = I_2020 / I_2019. The mapping file stores I_2019 only because the series is 2020=100;
    when raw_ppi is given, that assumption is checked against the raw 2020 column (PM review R2).
    """
    raw2020 = {}
    if raw_ppi is not None:
        with raw_ppi.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
        h = rows[0]
        i19, i20 = h.index("2019"), h.index("2020")
        for r in rows[1:]:
            try:
                v = (float(r[i19]), float(r[i20]))
            except ValueError:
                continue  # items without values in these years are not used by the mapping
            raw2020.setdefault(r[1].strip(), v)
    ratios = {}
    with PPI_MAP.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(line for line in f if not line.startswith("#")):
            i19 = float(r["ppi_2019"])
            i20 = 100.0
            if raw_ppi is not None:
                raw19, raw20 = raw2020[r["ppi_item"]]
                if abs(raw19 - i19) > 1e-9 or abs(raw20 - 100.0) > 1e-9:
                    raise ValueError(f"PPI mapping disagrees with raw file for {r['ppi_item']}.")
                i20 = raw20
            ratios[r["io_sector"]] = i20 / i19
    missing = set(codes) - set(ratios)
    if missing:
        raise ValueError(f"No PPI mapping for {sorted(missing)}")
    return np.array([ratios[c] for c in codes])


def run(data_dir: Path) -> tuple[Path, dict]:
    dl, g2, derived = data_dir / "downloads", data_dir / "gate2", data_dir / "derived"
    derived.mkdir(exist_ok=True)
    prov_dl = (dl / "PROVENANCE_ecos_files.txt").read_text(encoding="utf-8")
    prov_g2 = (g2 / "PROVENANCE_gate2_files.txt").read_text(encoding="utf-8")
    # [SECURE] Integrity check of every input against recorded provenance (Category 5)
    for p, prov in ((dl / F2019, prov_dl), (dl / F2020, prov_dl), (g2 / NA_FILE, prov_g2)):
        if _sha(p) not in prov:
            raise ValueError(f"{p.name}: SHA-256 not in provenance.")

    ad = io_table.read_coefficient_sheet(dl / F2019, io_table.SHEET_DOMESTIC)
    codes = ad.codes
    c19 = gate2.read_flow_columns(dl / F2019, gate2.FD_ALL_ITEMS + (gate2.OUTPUT_COL,), outcome_year=False)
    # [SECURE] Outcome-year table: final-demand columns only (leakage guard enforced in gate2) (Category 1)
    c20 = gate2.read_flow_columns(dl / F2020, gate2.FD_ALL_ITEMS, outcome_year=True)
    x19 = np.array([c19[gate2.OUTPUT_COL][s] for s in codes])
    g_nom, g_real = na_growth(g2 / NA_FILE)
    p = ppi_ratios(codes, g2 / PPI_RAW)

    def spec_a(items, real):
        fd19 = gate2.final_demand(c19, items, codes)
        fd20 = gate2.rescale_items(c19, c20, items, codes, g_nom)
        df = gate2.shock(fd19, fd20, p if real else None)
        return fd19, df

    specs = {}
    for name, items, real in (("main", gate2.FD_MAIN, True), ("s1_nominal", gate2.FD_MAIN, False),
                              ("s2_incl_inventories", gate2.FD_ALL_ITEMS, True)):
        fd19, df = spec_a(items, real)
        specs[name] = (fd19, df)
    fd19_b = gate2.final_demand(c19, gate2.FD_MAIN, codes)
    specs["s4_fixed_composition"] = (fd19_b, gate2.fixed_composition_shock(c19, gate2.FD_MAIN, codes, g_real))

    out = {"codes": list(codes), "na_growth_nominal": g_nom, "na_growth_real": g_real,
           "ppi_ratio": dict(zip(codes, p.tolist())), "specs": {}}
    for name, (fd19, df) in specs.items():
        pr = gate2.predict(ad.matrix, df, x19, fd19)
        out["specs"][name] = {"shock": df.tolist(), "model": pr.model.tolist(), "direct": pr.direct.tolist(),
                              "uniform": pr.uniform}
    out["inputs_sha256"] = {F2019: _sha(dl / F2019), F2020: _sha(dl / F2020), NA_FILE: _sha(g2 / NA_FILE),
                            "data/ppi_to_io33_gate2.csv": _sha(PPI_MAP)}
    target = derived / "gate2_predictions.json"
    fd, tmp = tempfile.mkstemp(prefix=".gate2pred.", suffix=".tmp", dir=derived)
    try:
        # [SECURE] Atomic write (Category 3, 5)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=1, sort_keys=True)
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return target, out


def main() -> int:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        print("LOCALAPPDATA is not set.", file=sys.stderr)
        return 2
    try:
        target, out = run(Path(base) / "nss-renewal-data" / "io_bok")
    except (ValueError, OSError) as e:
        # [SECURE] Short reason, no stack trace for expected input problems (Category 4)
        print(f"Gate 2 prediction stopped: {e}", file=sys.stderr)
        return 1
    print("NA nominal growth:", {k: round(v * 100, 1) for k, v in out["na_growth_nominal"].items()})
    print("NA real growth:   ", {k: round(v * 100, 1) for k, v in out["na_growth_real"].items()})
    print("predictions written:", target.name, "sha256", _sha(target))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Integrity: all inputs checked against provenance hashes before use (Category 5)
#   - Leakage guard: outcome-year table read for final-demand columns only; outcome files not opened (Category 1)
#   - Error handling: short messages, non-zero exit (Category 4); atomic output write (Category 3)
# Not Applied:
#   - [WARN] Authentication: not applicable - local developer script
# --------------------------------------------------
