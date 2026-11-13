"""P1-industry gate 1 parser and pair detection on synthetic ECOS-shaped workbooks."""

import numpy as np
import pytest

openpyxl = pytest.importorskip("openpyxl")

from cxsim import io_table as io  # noqa: E402

CODES = ["A", "B", "C01"]
NAMES = ["농림수산품", "광산품", "음식료품"]
AD = np.array([[0.10, 0.02, 0.20], [0.01, 0.05, -0.001], [0.15, 0.00, 0.12]])   # one scrap-style negative
AM = np.array([[0.02, 0.01, 0.05], [0.03, 0.01, 0.002], [0.01, 0.00, 0.03]])


def _sheet(wb, name, M, extra_rows=True):
    ws = wb.create_sheet(name)
    ws.append([f"투입산출표_{name}"])
    ws.append(["2020년"])
    ws.append(["생산자가격"])
    ws.append([])
    ws.append(["", ""] + CODES + ["9590"])            # row 5: codes (+ a summary column to ignore)
    ws.append(["", ""] + NAMES + ["계"])              # row 6: names
    for code, nm, row in zip(CODES, NAMES, M):
        ws.append([code, nm] + [float(x) for x in row] + [float(sum(row))])
    if extra_rows:
        ws.append(["9590", "계"] + [float(x) for x in M.sum(axis=0)] + [0.0])


def make_book(path, inducement):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    _sheet(wb, io.SHEET_TOTAL, AD + AM)
    _sheet(wb, io.SHEET_DOMESTIC, AD)
    _sheet(wb, io.SHEET_IMPORT, AM)
    _sheet(wb, io.SHEET_INDUCEMENT, inducement)
    wb.save(path)
    return path


def test_parser_reads_square_block_and_skips_summary(tmp_path):
    p = make_book(tmp_path / "b.xlsx", np.linalg.inv(np.eye(3) - AD))
    t = io.read_coefficient_sheet(p, io.SHEET_DOMESTIC)
    assert t.codes == tuple(CODES) and t.names == tuple(NAMES)
    np.testing.assert_allclose(t.matrix, AD)


def test_engine_inverse_is_leontief_with_published_orientation():
    L = io.engine_inverse(AD)
    np.testing.assert_allclose(L, np.linalg.inv(np.eye(3) - AD), atol=1e-14)
    # column j = output required in every sector per unit final demand of j (not the transpose)
    np.testing.assert_allclose(L[:, 2], np.linalg.solve(np.eye(3) - AD, [0, 0, 1]), atol=1e-14)


def test_gate1_identifies_domestic_pair_and_reports_negatives(tmp_path):
    p = make_book(tmp_path / "b.xlsx", np.linalg.inv(np.eye(3) - AD))
    r = io.gate1(p)
    assert r.matched == "domestic_Ad" and r.passed
    assert r.candidates["domestic_Ad"] < 1e-12 < r.candidates["total_A"]
    assert r.sanity["domestic_negative_cells"] == [{"from": "B", "to": "C01", "value": -0.001}]


def test_gate1_identifies_total_pair_when_published_is_competitive_type(tmp_path):
    p = make_book(tmp_path / "b.xlsx", np.linalg.inv(np.eye(3) - (AD + AM)))
    assert io.gate1(p).matched == "total_A"


def test_gate1_fails_when_nothing_matches(tmp_path):
    p = make_book(tmp_path / "b.xlsx", np.linalg.inv(np.eye(3) - AD) + 1e-6)
    r = io.gate1(p)
    assert r.matched is None and not r.passed


def test_gate1_fails_when_transposed_published(tmp_path):
    p = make_book(tmp_path / "b.xlsx", np.linalg.inv(np.eye(3) - AD).T)
    assert io.gate1(p).matched is None


@pytest.mark.parametrize("bad", ["x", None, float("nan")])
def test_non_numeric_cells_rejected(tmp_path, bad):
    M = AD.astype(object).copy()
    M[1, 1] = bad
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet(io.SHEET_DOMESTIC)
    for _ in range(4):
        ws.append([])
    ws.append(["", ""] + CODES)
    ws.append(["", ""] + NAMES)
    for code, nm, row in zip(CODES, NAMES, M):
        ws.append([code, nm] + list(row))
    wb.save(tmp_path / "bad.xlsx")
    with pytest.raises(ValueError):
        io.read_coefficient_sheet(tmp_path / "bad.xlsx", io.SHEET_DOMESTIC)


def test_missing_sheet_rejected(tmp_path):
    p = make_book(tmp_path / "b.xlsx", np.linalg.inv(np.eye(3) - AD))
    with pytest.raises(ValueError, match="Sheet not found"):
        io.read_coefficient_sheet(p, "없는시트")


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: tests cover non-numeric/NaN cells, missing sheets, summary rows skipped (Category 1)
#   - Leftover debug code: synthetic workbooks only, no real data or credentials (Category 6)
# Not Applied:
#   - [WARN] Authentication: not applicable - offline unit tests
# --------------------------------------------------
