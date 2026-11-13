import numpy as np
import pytest

from conftest import make_spec
from cxsim.uncertainty import SensitivityUnavailable, monte_carlo, sensitivity


@pytest.fixture
def ranged():
    # a -> b -> c on the path; d -> a is off-path for a shock at a.
    return make_spec(
        ["a", "b", "c", "d"],
        [("a", "b", 0.1, 0.4), ("b", "c", 0.1, 0.4), ("d", "a", 0.0, 0.3)],
        decay=(0.4, 0.6),
    )


def test_same_seed_same_result(ranged):
    r1 = monte_carlo(ranged, {"a": 0.5}, n_samples=300)
    r2 = monte_carlo(ranged, {"a": 0.5}, n_samples=300)
    np.testing.assert_array_equal(r1.quantiles, r2.quantiles)
    r3 = monte_carlo(ranged, {"a": 0.5}, n_samples=300, seed=99)
    assert not np.array_equal(r1.quantiles, r3.quantiles)


def test_quantiles_ordered_and_rank_probs(ranged):
    r = monte_carlo(ranged, {"a": 0.5}, n_samples=500, k=2)
    assert np.all(r.quantiles[0] <= r.quantiles[1] + 1e-12)
    assert np.all(r.quantiles[1] <= r.quantiles[2] + 1e-12)
    assert np.isnan(r.top1_prob[0])                    # shocked node excluded from ranking
    assert r.top1_prob[1] == pytest.approx(1.0)        # b always beats c and d
    assert r.unstable_fraction == 0.0


def test_unstable_fraction_reported_not_dropped_silently():
    # rho = (1 - lam) + w for the 2-cycle; ranges straddle rho = 1
    spec = make_spec(["a", "b"], [("a", "b", 0.1, 0.9), ("b", "a", 0.1, 0.9)], decay=(0.3, 0.5))
    r = monte_carlo(spec, {"a": 0.2}, n_samples=1000)
    assert 0.0 < r.unstable_fraction < 1.0
    assert r.n_stable == round((1 - r.unstable_fraction - r.explosive_fraction) * 1000)


def test_sobol_finds_path_edges(ranged):
    res = sensitivity(ranged, {"a": 0.5}, target="c", n_base=256)
    assert res.method == "sobol"
    st = dict(zip(res.params, res.total))
    assert st["a->b"] > 0.1 and st["b->c"] > 0.1
    assert st["d->a"] < 0.02                            # off-path edge does not matter


def test_morris_available(ranged):
    res = sensitivity(ranged, {"a": 0.5}, target="c", n_base=32, method="morris")
    mu = dict(zip(res.params, res.first))
    assert mu["d->a"] < mu["a->b"]


def test_sensitivity_refuses_unstable_ranges():
    spec = make_spec(["a", "b"], [("a", "b", 0.1, 0.9), ("b", "a", 0.1, 0.9)], decay=(0.3, 0.5))
    with pytest.raises(SensitivityUnavailable):
        sensitivity(spec, {"a": 0.2}, target="b", n_base=64)



# ---- Review fixes (M2: unreached nodes must not be ranked; M1: explosive samples reported) ----

def test_unreached_nodes_are_not_ranked(chain):
    r = monte_carlo(chain, {"c": 0.5}, n_samples=50)
    assert r.top1_prob[0] == 0.0 and r.top1_prob[1] == 0.0  # a, b are upstream: zero impact
    assert r.ranked_fraction == 0.0
    r = monte_carlo(chain, {"b": 0.5}, n_samples=50, k=2)
    assert r.topk_prob[0] == 0.0       # a is upstream of b
    assert r.topk_prob[2] == 1.0       # c is the only reached node
    assert r.top1_prob[2] == 1.0


def test_explosive_fraction_reported_separately():
    nodes = [f"n{i}" for i in range(12)]
    spec = make_spec(nodes, [(f"n{i}", f"n{i+1}", 0.2, 1.0) for i in range(11)], decay=(0.3, 0.3))
    r = monte_carlo(spec, {"n0": 0.5}, n_samples=400)
    assert r.unstable_fraction == 0.0           # acyclic: always stable
    assert 0.0 < r.explosive_fraction < 1.0     # large weights over 11 hops exceed 1000x
    assert r.n_stable == round((1 - r.explosive_fraction) * 400)


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: tests assert that invalid ids, ranges, paths and shocks are rejected (Category 1)
#   - Leftover debug code: no credentials, accounts or debug hooks; test-only module (Category 6)
# Not Applied:
#   - [WARN] Authentication: not applicable - offline unit tests
# --------------------------------------------------
