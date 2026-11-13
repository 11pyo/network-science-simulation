"""Gate 2 computations on synthetic data (no real outcome data is touched)."""

import numpy as np
import pytest

openpyxl = pytest.importorskip("openpyxl")

from cxsim import gate2  # noqa: E402

CODES = ("A", "B", "C01")


def _flow_book(path, cols, values):
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("A표_국산거래표(생산자)")
    for _ in range(4):
        ws.append([])
    ws.append(["", ""] + list(CODES) + list(cols))
    ws.append(["", ""] + ["n"] * (len(CODES) + len(cols)))
    for i, c in enumerate(CODES):
        ws.append([c, "name"] + [0.0] * len(CODES) + [float(v) for v in values[i]])
    ws.append(["9090", "계"] + [0.0] * (len(CODES) + len(cols)))
    wb.save(path)
    return path


def test_outcome_guard_refuses_output_columns(tmp_path):
    p = _flow_book(tmp_path / "f.xlsx", ("9111", "9290"), [[1, 9], [2, 9], [3, 9]])
    with pytest.raises(ValueError, match="Refusing"):
        gate2.read_flow_columns(p, ("9111", "9290"), outcome_year=True)
    cols = gate2.read_flow_columns(p, ("9111", "9290"), outcome_year=False)   # allowed for 2019
    assert cols["9290"] == {"A": 9.0, "B": 9.0, "C01": 9.0}


def test_final_demand_excludes_inventories_in_main_spec(tmp_path):
    cols = ("9111", "9112", "9121", "9122", "9131", "9132", "9140")
    vals = [[1, 1, 1, 1, 100, 100, 1]] * 3
    p = _flow_book(tmp_path / "f.xlsx", cols, vals)
    got = gate2.read_flow_columns(p, cols, outcome_year=True)
    np.testing.assert_allclose(gate2.final_demand(got, gate2.FD_MAIN, CODES), [5, 5, 5])
    np.testing.assert_allclose(gate2.final_demand(got, gate2.FD_ALL_ITEMS, CODES), [205, 205, 205])


def test_option_a_rescales_item_totals_keeps_2020_composition():
    codes = ("A", "B")
    c19 = {"9111": {"A": 60.0, "B": 40.0}, "9140": {"A": 10.0, "B": 10.0}}
    c20 = {"9111": {"A": 90.0, "B": 30.0}, "9140": {"A": 5.0, "B": 15.0}}   # level-inflated 2020 table
    out = gate2.rescale_items(c19, c20, ("9111", "9140"), codes, {"9111": -0.05, "9140": 0.10})
    # 9111 total 100 * 0.95 = 95 split 3:1 ; 9140 total 20 * 1.1 = 22 split 1:3
    np.testing.assert_allclose(out, [95 * 0.75 + 22 * 0.25, 95 * 0.25 + 22 * 0.75])
    with pytest.raises(ValueError):
        gate2.rescale_items(c19, c20, ("9111",), codes, {})


def test_option_b_uses_2019_composition_only():
    c19 = {"9111": {"A": 60.0, "B": 40.0}, "9140": {"A": 10.0, "B": 30.0}}
    out = gate2.fixed_composition_shock(c19, ("9111", "9140"), ("A", "B"), {"9111": -0.05, "9140": 0.10})
    np.testing.assert_allclose(out, [60 * -0.05 + 10 * 0.10, 40 * -0.05 + 30 * 0.10])


def test_instability_rule():
    assert gate2.combine_verdicts("더한다고 볼 수 없다", "더한다고 볼 수 없다") == "더한다고 볼 수 없다"
    assert gate2.combine_verdicts("파급이 설명력을 더한다", "더한다고 볼 수 없다").startswith("불안정")


def test_shock_real_and_nominal():
    fd19, fd20 = np.array([100.0, 50.0]), np.array([110.0, 40.0])
    np.testing.assert_allclose(gate2.shock(fd19, fd20, None), [10, -10])
    np.testing.assert_allclose(gate2.shock(fd19, fd20, np.array([1.1, 0.8])), [0, 0], atol=1e-9)
    with pytest.raises(ValueError):
        gate2.shock(fd19, fd20, np.array([1.0, 0.0]))


def test_predict_model_vs_direct():
    ad = np.array([[0.0, 0.5], [0.0, 0.0]])           # sector 1 buys from sector 0
    df = np.array([0.0, 10.0])
    p = gate2.predict(ad, df, x19=np.array([100.0, 100.0]), fd19=np.array([50.0, 50.0]))
    np.testing.assert_allclose(p.direct, [0.0, 0.10])
    np.testing.assert_allclose(p.model, [0.05, 0.10])   # indirect: supplier gains 0.5*10
    assert p.uniform == pytest.approx(0.10)


def test_aggregate_growth_weighted_laspeyres():
    g = gate2.aggregate_growth({"10": 100, "11": 100}, {"10": 110, "11": 90}, {"10": 3, "11": 1},
                               {"10": "C01", "11": "C01"})
    assert g["C01"] == pytest.approx((3 * 110 + 90) / 400 - 1)
    with pytest.raises(ValueError):
        gate2.aggregate_growth({"10": 100}, {"10": 110}, {}, {"10": "C01"})


def _pred(model, direct, uniform=0.0):
    return gate2.Predictions(np.array(model, float), np.array(direct, float), uniform)


def test_verdict_passes_only_with_clear_lead():
    sectors = tuple(f"S{i}" for i in range(15))
    y = np.linspace(-0.2, 0.2, 15)
    rng = np.random.default_rng(1)
    direct = rng.permutation(y)                      # uninformative ranking
    model = y + 0.001                                # near-perfect
    m = gate2.evaluate(_pred(model, direct, 0.5), dict(zip(sectors, y)), sectors, sectors)
    assert m.rho_model > 0.99 and m.rho_model - m.rho_direct >= gate2.LEAD_RHO
    assert m.verdict == "파급이 설명력을 더한다" and m.rho_diff_ci90[0] > 0


def test_bootstrap_rule_overrides_threshold():
    sectors = tuple(f"S{i}" for i in range(15))
    y = np.linspace(-0.2, 0.2, 15)
    noise = np.random.default_rng(2).normal(0, 0.15, 15)
    model = y + noise
    direct = y + noise * 1.05                        # almost the same ranking
    m = gate2.evaluate(_pred(model, direct, 0.5), dict(zip(sectors, y)), sectors, sectors)
    assert m.rho_diff_ci90[0] <= 0 <= m.rho_diff_ci90[1]
    assert m.verdict in ("더한다고 볼 수 없다", "방향만 확인, 우연과 구별되지 않음")
    assert any("0을 포함" in n for n in m.notes)


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Leakage guard covered by a test (outcome-year output columns refused) (Category 1)
#   - Leftover debug code: synthetic data only (Category 6)
# Not Applied:
#   - [WARN] Authentication: not applicable - offline unit tests
# --------------------------------------------------
