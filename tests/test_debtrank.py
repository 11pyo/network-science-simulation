import numpy as np
import pytest

from conftest import make_spec
from cxsim.engines import debtrank


def test_chain_hand_values():
    spec = make_spec(["a", "b", "c"], [("a", "b", 0.5, 0.5), ("b", "c", 0.5, 0.5)])
    r = debtrank.run(spec, {"a": 1.0})
    np.testing.assert_allclose(r.h, [1.0, 0.5, 0.25])
    assert r.rounds == 3
    # uniform values: total = 1.75 / 3, induced = total - 1/3
    assert r.total_distress == pytest.approx(1.75 / 3)
    assert r.debtrank == pytest.approx(0.75 / 3)


def test_inactive_nodes_keep_accumulating_but_do_not_repropagate():
    spec = make_spec(["a", "b"], [("a", "b", 0.5, 0.5), ("b", "a", 0.5, 0.5)])
    r = debtrank.run(spec, {"a": 0.4})
    # round1: b = 0.2 ; round2: a (inactive) += 0.5*0.2 -> 0.5 ; a never propagates again
    np.testing.assert_allclose(r.h, [0.5, 0.2])
    assert r.rounds == 2


def test_distress_capped_at_one():
    spec = make_spec(["a", "b", "c"], [("a", "c", 1.0, 1.0), ("b", "c", 1.0, 1.0)])
    r = debtrank.run(spec, {"a": 0.8, "b": 0.8})
    assert r.h[2] == 1.0


def test_values_weight_the_result():
    spec = make_spec(["a", "b"], [("a", "b", 0.5, 0.5)], values={"a": 1.0, "b": 3.0})
    r = debtrank.run(spec, {"a": 1.0})
    # shares 0.25 / 0.75 ; induced = 0.5 * 0.75
    assert r.debtrank == pytest.approx(0.375)


def test_negative_edges_rejected():
    spec = make_spec(["a", "b"], [("a", "b", -0.2, -0.2)])
    with pytest.raises(ValueError):
        debtrank.run(spec, {"a": 0.5})


@pytest.mark.parametrize("bad", [{"a": 1.2}, {"a": -0.1}, {"zz": 0.5}, {}])
def test_bad_initial_distress_rejected(bad):
    spec = make_spec(["a", "b"], [("a", "b", 0.5, 0.5)])
    with pytest.raises(ValueError):
        debtrank.run(spec, bad)


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: tests assert that invalid ids, ranges, paths and shocks are rejected (Category 1)
#   - Leftover debug code: no credentials, accounts or debug hooks; test-only module (Category 6)
# Not Applied:
#   - [WARN] Authentication: not applicable - offline unit tests
# --------------------------------------------------
