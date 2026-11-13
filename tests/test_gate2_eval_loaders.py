"""Gate 2 evaluator loaders on synthetic KOSIS-shaped CSVs (PM review R1)."""

import csv
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import p1_industry_gate2_evaluate as ev  # noqa: E402
from cxsim import gate2  # noqa: E402


def _write(path, rows):
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f).writerows(rows)
    return path


def test_mm_index_skips_suppressed_and_dash_cells(tmp_path):
    p = _write(tmp_path / "mm.csv", [
        ["A 시도별", "B 산업별", "Y2019 2019", "Y2020 2020"],
        ["A 시도별", "B 산업별", "T10 생산지수(원지수)", "T10 생산지수(원지수)"],
        ["00 전국", "C10 식료품 제조업", "98.361", "100.0"],
        ["00 전국", "C34 산업용 기계 및 장비 수리업", "-", "100.0"],
        ["00 전국", "B06 금속 광업", "X", "100.0"],
    ])
    a, b = ev.load_mm_index(p)
    assert a == {"C10": 98.361} and b == {"C10": 100.0}


def test_service_index_uses_constant_price_column_of_each_year(tmp_path):
    p = _write(tmp_path / "sv.csv", [
        ["A 업종별", "Y2019 2019", "Y2019 2019", "Y2020 2020", "Y2020 2020"],
        ["A 업종별", "T1 경상지수", "T2 불변지수", "T1 경상지수", "T2 불변지수"],
        ["G 도매 및 소매업", "999.0", "102.7", "888.0", "100.0"],
    ])
    a, b = ev.load_service_index(p)
    assert a == {"G": 102.7} and b == {"G": 100.0}          # never the current-price column


def test_service_index_without_constant_columns_is_rejected(tmp_path):
    p = _write(tmp_path / "sv.csv", [
        ["A 업종별", "Y2019 2019", "Y2020 2020"],
        ["A 업종별", "T1 경상지수", "T1 경상지수"],
        ["G 도매 및 소매업", "1", "2"],
    ])
    with pytest.raises(ValueError):
        ev.load_service_index(p)


def test_one_to_one_sectors_ignore_missing_weights(tmp_path):
    w = _write(tmp_path / "w.csv", [
        ["A 시도별", "B 산업별", "Y2019 2019", "Y2019 2019"],
        ["A 시도별", "B 산업별", "T07 생산액", "T08 부가가치"],
        ["00 전국", "C10 식료품 제조업", "300", "30"],
        ["00 전국", "C11 음료 제조업", "100", "10"],
        ["00 전국", "B06 금속 광업", "X", "X"],
    ])
    va, out = ev.load_weights(w)
    assert va == {"C10": 30.0, "C11": 10.0} and out == {"C10": 300.0, "C11": 100.0}
    mapping = {"B": "B", "C10": "C01", "C11": "C01", "D": "D"}
    for k in ("B", "D"):                       # what run() does for 1:1 sectors
        va.setdefault(k, 1.0)
    g = gate2.aggregate_growth({"B": 101.486, "C10": 98.0, "C11": 104.0, "D": 101.9},
                               {"B": 100.0, "C10": 100.0, "C11": 100.0, "D": 100.0}, va, mapping)
    assert g["B"] == pytest.approx(100.0 / 101.486 - 1)
    assert g["C01"] == pytest.approx((30 * 100 + 10 * 100) / (30 * 98 + 10 * 104) - 1)


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: suppressed ('X') and missing ('-') cells, wrong column kinds are covered (Category 1)
#   - Leftover debug code: synthetic files only (Category 6)
# Not Applied:
#   - [WARN] Authentication: not applicable - offline unit tests
# --------------------------------------------------
