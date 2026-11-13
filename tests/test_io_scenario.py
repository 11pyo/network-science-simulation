"""Industry scenario calculator: synthetic tables + optional check on the real BOK workbook."""

import numpy as np
import pytest

from cxsim import io_scenario as sc

CODES = ("A", "B", "C01")
AD = np.array([[0.10, 0.02, 0.20], [0.01, 0.05, -0.001], [0.15, 0.00, 0.12]])


@pytest.fixture
def tables():
    inv = np.linalg.inv(np.eye(3) - AD)
    return sc.IOTables(CODES, ("a", "b", "c"), AD, inv,
                       output=np.array([100e6, 50e6, 80e6]), final_demand=np.array([40e6, 10e6, 60e6]),
                       max_abs_error=0.0)


def test_unit_shock_equals_inducement_column(tables):
    r = sc.run_scenario(tables, {"C01": 1.0})
    np.testing.assert_allclose(r.total, tables.inverse[:, 2], atol=1e-14)
    assert r.multiplier == pytest.approx(tables.inverse[:, 2].sum())


def test_total_is_direct_plus_indirect(tables):
    r = sc.run_scenario(tables, {"A": 2.0, "B": -0.5})
    np.testing.assert_allclose(r.direct + r.indirect, r.total, atol=1e-14)
    np.testing.assert_allclose(r.direct, [2.0, -0.5, 0.0])


def test_zero_shock_is_zero_and_has_no_multiplier(tables):
    r = sc.run_scenario(tables, {})
    assert np.all(r.total == 0) and r.multiplier is None


def test_negative_shock_is_mirror(tables):
    p, n = sc.run_scenario(tables, {"A": 3.0}), sc.run_scenario(tables, {"A": -3.0})
    np.testing.assert_allclose(n.total, -p.total, atol=1e-14)


def test_range_bounds_are_exact_and_contain_samples(tables):
    r = sc.run_scenario(tables, {"A": -1.0, "C01": 2.0}, {"A": 1.0, "C01": 4.0})
    rng = np.random.default_rng(0)
    for _ in range(500):
        s = {"A": rng.uniform(-1, 1), "C01": rng.uniform(2, 4)}
        t = sc.run_scenario(tables, s).total
        assert np.all(t >= r.total_low - 1e-12) and np.all(t <= r.total_high + 1e-12)
    corner = sc.run_scenario(tables, {"A": 1.0, "C01": 4.0}).total      # all-max corner (L >= 0 here except tiny)
    assert np.all(corner <= r.total_high + 1e-12)
    with pytest.raises(ValueError):
        sc.run_scenario(tables, {"A": 2.0}, {"A": 1.0})


def test_percent_conversion_uses_2020_final_demand(tables):
    assert sc.percent_to_trillion(tables, {"B": -10})["B"] == pytest.approx(-1.0)   # 10 trillion * -10%


@pytest.mark.parametrize("bad", [{"ZZ": 1.0}, {"A": float("nan")}, {"A": 1e9}])
def test_bad_inputs_rejected(tables, bad):
    with pytest.raises(ValueError):
        sc.run_scenario(tables, bad)


def test_missing_data_raises_file_not_found(tmp_path):
    with pytest.raises(FileNotFoundError):
        sc.load_tables(tmp_path)


def test_real_workbook_unit_shock_matches_published_column_if_available():
    d = sc.default_dir()
    if d is None or not (d / sc.BENCHMARK_FILE).is_file():
        pytest.skip("BOK workbook not present on this machine")
    from cxsim import io_table

    t = sc.load_tables(d)
    pub = io_table.read_coefficient_sheet(d / sc.BENCHMARK_FILE, io_table.SHEET_INDUCEMENT).matrix
    j = t.codes.index("C12")
    r = sc.run_scenario(t, {"C12": 1.0})
    np.testing.assert_allclose(r.total, pub[:, j], atol=1e-12)
    assert len(t.codes) == 33 and t.max_abs_error < 1e-12



# ---------------------------------------------------------------- PM review F1-F3 (2026-11-12)

def test_f2_multiplier_only_for_same_sign_shocks(tables):
    assert sc.run_scenario(tables, {"A": 2.0, "B": -1.0}).multiplier is None
    r = sc.run_scenario(tables, {"A": -2.0, "B": -1.0})
    assert r.multiplier == pytest.approx(r.total.sum() / -3.0)


def test_f1_percent_refused_for_non_positive_final_demand(tables):
    t = sc.IOTables(tables.codes, tables.names, tables.ad, tables.inverse, tables.output,
                    np.array([40e6, -1e6, 60e6]), 0.0)
    assert sc.percent_base_ok(t) == {"A": True, "B": False, "C01": True}
    with pytest.raises(sc.NonPositiveBaseError) as ei:
        sc.percent_to_trillion(t, {"A": -1.0, "B": -1.0})
    assert ei.value.codes == ["B"]


def _benchmark_book(dirpath, inducement_offset=0.0):
    openpyxl = pytest.importorskip("openpyxl")
    from cxsim import io_table

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    def sheet(name, M, extra_cols=(), extra_vals=None):
        ws = wb.create_sheet(name)
        for _ in range(4):
            ws.append([])
        ws.append(["", ""] + list(CODES) + list(extra_cols))
        ws.append(["", ""] + ["n"] * (len(CODES) + len(extra_cols)))
        for i, c in enumerate(CODES):
            ws.append([c, "name"] + [float(x) for x in M[i]] + (list(extra_vals[i]) if extra_vals else []))

    sheet(io_table.SHEET_DOMESTIC, AD)
    sheet(io_table.SHEET_INDUCEMENT, np.linalg.inv(np.eye(3) - AD) + inducement_offset)
    sheet("A표_국산거래표(생산자)", np.zeros((3, 3)), ("9190", "9290"),
          [(40e6, 100e6), (-1e6, 50e6), (60e6, 80e6)])
    p = dirpath / sc.BENCHMARK_FILE
    wb.save(p)
    import hashlib

    (dirpath / sc.PROVENANCE_FILE).write_text(
        "sha256: " + hashlib.sha256(p.read_bytes()).hexdigest() + "\n", encoding="utf-8")
    return p


def test_f3_cache_created_reused_and_invalidated(tmp_path):
    dl = tmp_path / "downloads"
    dl.mkdir()
    _benchmark_book(dl)
    t1 = sc.load_tables(dl)
    caches = list((tmp_path / "derived").glob("io_scenario_cache_*.npz"))
    assert len(caches) == 1
    t2 = sc.load_tables(dl)                                    # served from cache
    np.testing.assert_array_equal(t1.inverse, t2.inverse)
    assert t2.codes == CODES and t2.final_demand[1] == -1e6
    # different workbook -> different hash -> new cache file, old one ignored
    _benchmark_book(dl, inducement_offset=0.0)
    p = dl / sc.BENCHMARK_FILE
    import openpyxl

    wb = openpyxl.load_workbook(p)
    wb["A표_국산거래표(생산자)"]["F7"] = 41e6              # change 9190 of sector A
    wb.save(p)
    import hashlib

    (dl / sc.PROVENANCE_FILE).write_text("sha256: " + hashlib.sha256(p.read_bytes()).hexdigest(), encoding="utf-8")
    t3 = sc.load_tables(dl)
    assert t3.final_demand[0] == 41e6
    assert len(list((tmp_path / "derived").glob("io_scenario_cache_*.npz"))) == 2


def test_f3_corrupt_cache_is_rebuilt_and_published_check_still_runs(tmp_path):
    dl = tmp_path / "downloads"
    dl.mkdir()
    _benchmark_book(dl)
    sc.load_tables(dl)
    cache = next((tmp_path / "derived").glob("io_scenario_cache_*.npz"))
    cache.write_bytes(b"not a zip")
    assert sc.load_tables(dl).codes == CODES                   # damaged cache ignored and rebuilt
    bad = tmp_path / "bad"
    (bad / "downloads").mkdir(parents=True)
    _benchmark_book(bad / "downloads", inducement_offset=1e-6)  # published sheet disagrees with engine
    with pytest.raises(ValueError, match="published"):
        sc.load_tables(bad / "downloads")


def test_real_workbook_mining_percent_refused_if_available():
    d = sc.default_dir()
    if d is None or not (d / sc.BENCHMARK_FILE).is_file():
        pytest.skip("BOK workbook not present on this machine")
    t = sc.load_tables(d)
    assert sc.percent_base_ok(t)["B"] is False and sc.percent_base_ok(t)["T"] is False
    with pytest.raises(sc.NonPositiveBaseError):
        sc.percent_to_trillion(t, {"C12": -1.0, "B": -1.0})


def test_xlsx_lite_matches_openpyxl_values(tmp_path):
    openpyxl = pytest.importorskip("openpyxl")
    from cxsim import xlsx_lite

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "시트1"
    ws.append(["코드", "이름", 1000, 0.049300016606809, None, "0111"])
    ws.append([None, None, -3.8e-05, 2, True, "가나다"])
    ws["H5"] = 7
    p = tmp_path / "x.xlsx"
    wb.save(p)
    ref = [tuple(r) for r in openpyxl.load_workbook(p, read_only=True, data_only=True)["시트1"].iter_rows(values_only=True)]
    got = xlsx_lite.read_sheets(p, ["시트1"])["시트1"]
    w = max(len(r) for r in ref + got)
    pad = lambda rows: [tuple(list(r) + [None] * (w - len(r))) for r in rows]
    assert pad(got) == pad(ref)
    assert xlsx_lite.sheet_names(p) == ["시트1"]



def test_xlsx_lite_refuses_cells_without_reference(tmp_path):
    import zipfile
    from cxsim import xlsx_lite

    openpyxl = pytest.importorskip("openpyxl")
    wb = openpyxl.Workbook()
    wb.active.title = "S"
    wb.active.append([1, 2])
    src = tmp_path / "a.xlsx"
    wb.save(src)
    dst = tmp_path / "b.xlsx"
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename.startswith("xl/worksheets/sheet"):
                data = data.replace(b' r="B1"', b"")          # drop one cell reference (allowed by the spec)
            zout.writestr(item, data)
    with pytest.raises(ValueError, match="reference"):
        xlsx_lite.read_sheets(dst, ["S"])


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation tests: unknown codes, NaN, oversized shocks, inverted ranges (Category 1)
#   - Leftover debug code: synthetic data; the real-data test only reads and skips when absent (Category 6)
# Not Applied:
#   - [WARN] Authentication: not applicable - offline unit tests
# --------------------------------------------------
