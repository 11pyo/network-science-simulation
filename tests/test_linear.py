import numpy as np
import pytest

from conftest import make_spec
from cxsim.engines import linear
from cxsim.engines.linear import UnstableModelError, simulate


def test_direction_source_affects_target_only():
    spec = make_spec(["a", "b"], [("a", "b", 0.3, 0.3)])
    from_a = simulate(spec, {"a": 0.5}).total
    from_b = simulate(spec, {"b": 0.5}).total
    assert from_a[1] > 0          # a -> b carries the shock
    assert from_b[0] == 0.0       # nothing flows b -> a


def test_dag_downstream_shock_never_reaches_upstream(chain):
    total = simulate(chain, {"c": 0.7}).total
    assert total[0] == 0.0 and total[1] == 0.0


def test_closed_form_matches_iteration(chain):
    imp = simulate(chain, {"a": 0.5}, mode="impulse", steps=400)
    assert imp.output_name == "cumulative_impulse_impact"
    np.testing.assert_allclose(imp.trajectory.sum(axis=0), imp.total, atol=1e-9)
    per = simulate(chain, {"a": 0.5}, mode="persistent", steps=400)
    assert per.output_name == "persistent_steady_state"
    np.testing.assert_allclose(per.trajectory[-1], per.total, atol=1e-9)


def test_chain_hand_values(chain):
    # lam = 0.5: a = s/lam = 1.0 ; b = 0.4 * a / lam = 0.8 ; c = 0.4 * b / lam = 0.64
    total = simulate(chain, {"a": 0.5}).total
    np.testing.assert_allclose(total, [1.0, 0.8, 0.64], atol=1e-12)


def test_no_clamp_isolated_node_amplifies():
    spec = make_spec(["a", "b"], [], decay=(0.5, 0.5))
    total = simulate(spec, {"a": 0.8}).total
    assert total[0] == pytest.approx(1.6)  # s / lam > 1 must not be clipped


def test_linearity_and_sign_symmetry(chain):
    base = simulate(chain, {"a": 0.1}).total
    np.testing.assert_allclose(simulate(chain, {"a": 0.2}).total, 2 * base, atol=1e-12)
    np.testing.assert_allclose(simulate(chain, {"a": -0.1}).total, -base, atol=1e-12)


def test_multiple_shocks_superpose(chain):
    both = simulate(chain, {"a": 0.2, "c": -0.3}).total
    sep = simulate(chain, {"a": 0.2}).total + simulate(chain, {"c": -0.3}).total
    np.testing.assert_allclose(both, sep, atol=1e-12)


def test_unstable_model_rejected():
    # 2-cycle: eigenvalues of M are (1 - 0.3) +- 0.9 -> rho = 1.6
    spec = make_spec(["a", "b"], [("a", "b", 0.9, 0.9), ("b", "a", 0.9, 0.9)], decay=(0.3, 0.3))
    with pytest.raises(UnstableModelError) as ei:
        simulate(spec, {"a": 0.1})
    assert ei.value.rho == pytest.approx(1.6)


def test_stable_graph_with_large_in_strength_accepted():
    # Gershgorin would fail (0.8 > lam) but rho = 0.5: must NOT be rejected
    spec = make_spec(["a", "b"], [("a", "b", 0.8, 0.8)], decay=(0.5, 0.5))
    res = simulate(spec, {"a": 0.5})
    assert res.spectral_radius == pytest.approx(0.5)


@pytest.mark.parametrize("bad", [{"zz": 0.1}, {"a": 1.5}, {"a": float("nan")}, {}, {"a": 0.0}, {"a": 0.0, "b": 0.0}])
def test_bad_shocks_rejected(chain, bad):
    with pytest.raises(ValueError):
        simulate(chain, bad)


def test_steps_capped(chain):
    with pytest.raises(ValueError):
        simulate(chain, {"a": 0.1}, steps=linear.MAX_STEPS + 1)


def test_sparse_path_matches_dense():
    rng = np.random.default_rng(3)
    n = 600
    nodes = [f"n{i}" for i in range(n)]
    edges = set()
    while len(edges) < 2400:
        s, t = rng.integers(0, n, 2)
        if s != t:
            edges.add((int(s), int(t)))
    edge_list = [(f"n{s}", f"n{t}", w, w) for (s, t), w in zip(sorted(edges), rng.uniform(0.0, 0.1, len(edges)))]
    spec = make_spec(nodes, edge_list, decay=(0.6, 0.6))
    dense_A = linear.build_matrix(spec, sparse=False)
    sparse_A = linear.build_matrix(spec, sparse=True)
    s = linear.shock_vector(spec, {"n0": 0.5, "n10": -0.2})
    np.testing.assert_allclose(linear.total_impact(sparse_A, 0.6, s), linear.total_impact(dense_A, 0.6, s), atol=1e-10)
    assert linear.spectral_radius(sparse_A, 0.6) == pytest.approx(linear.spectral_radius(dense_A, 0.6), rel=1e-6)
    res = simulate(spec, {"n0": 0.5}, steps=5)  # n > DENSE_MAX -> sparse path end to end
    assert np.isfinite(res.total).all()



# ---- Review fixes (P0 review: H1 large non-normal graphs, M1 explosive models) ----

def _chain(n, w, lam):
    nodes = [f"n{i}" for i in range(n)]
    return make_spec(nodes, [(f"n{i}", f"n{i+1}", w, w) for i in range(n - 1)], decay=(lam, lam))


def _layered(layers, width, fan, w, lam):
    nodes = [f"l{a}_{b}" for a in range(layers) for b in range(width)]
    edges = [(f"l{a}_{b}", f"l{a+1}_{(b + j) % width}", w, w)
             for a in range(layers - 1) for b in range(width) for j in range(fan)]
    return make_spec(nodes, edges, decay=(lam, lam))


@pytest.mark.parametrize("n,w,lam", [(600, 1.0, 0.5), (600, 0.9, 0.5), (2000, 1.0, 0.3), (400, 1.0, 0.5)])
def test_acyclic_spectral_radius_is_exactly_one_minus_lam(n, w, lam):
    spec = _chain(n, w, lam)
    for sparse in (True, False) if n <= 600 else (True,):
        A = linear.build_matrix(spec, sparse=sparse)
        assert linear.spectral_radius(A, lam) == pytest.approx(1.0 - lam, abs=1e-12)


def test_layered_acyclic_radius_and_determinism():
    spec = _layered(30, 30, 3, 0.6, 0.5)
    A = linear.build_matrix(spec)
    r1, r2 = linear.spectral_radius(A, 0.5), linear.spectral_radius(A, 0.5)
    assert r1 == 0.5 and r1 == r2


def test_large_stable_chain_accepted_not_rejected():
    # in-strength = lam (Gershgorin borderline), 1x per hop: stable and not explosive -> accepted
    res = simulate(_chain(600, 0.5, 0.5), {"n0": 0.5}, steps=5)  # sparse path
    assert res.spectral_radius == pytest.approx(0.5)
    assert res.max_amplification == pytest.approx(2.0)


def test_large_stable_but_explosive_chain_passes_stability_then_hits_cap():
    # w = 1.0, lam = 0.5: stable (rho = 0.5), so NOT UnstableModelError, but 2x per hop explodes
    with pytest.raises(linear.AmplificationExceededError):
        simulate(_chain(600, 1.0, 0.5), {"n0": 0.001}, steps=5)


def test_cycle_inside_large_graph_still_rejected():
    spec = _chain(600, 0.1, 0.3)
    edges = list(spec.edges) + [
        type(spec.edges[0])(source="n301", target="n300", weight={"low": 0.95, "high": 0.95}),
    ]
    spec = spec.model_copy(update={"edges": tuple(edges)})
    spec = type(spec).model_validate(spec.model_dump())
    # 2-cycle n300 <-> n301 with weights 0.1 and 0.95: rho = 0.7 + sqrt(0.095) ~ 1.008 -> unstable
    with pytest.raises(UnstableModelError):
        simulate(spec, {"n0": 0.1}, steps=5)


def test_explosive_layered_model_rejected_by_amplification_cap():
    spec = _layered(30, 30, 3, 0.3, 0.5)  # stable (rho = 0.5) but ~1.8x per layer over 29 layers
    with pytest.raises(linear.AmplificationExceededError) as ei:
        simulate(spec, {"l0_0": 0.1}, steps=5)
    assert ei.value.amplification > spec.max_amplification


def test_singular_dense_solve_raises_typed_error_not_linalgerror():
    spec = _chain(400, 1.0, 0.1)  # true solution ~10^400, beyond float range
    with pytest.raises((linear.NumericalBlowupError, linear.AmplificationExceededError)):
        simulate(spec, {"n0": 0.5}, steps=5)


def test_result_reports_amplification(chain):
    res = simulate(chain, {"a": 0.5})
    assert res.max_amplification == pytest.approx(2.0)  # a = s / lam = 1.0 over |s| = 0.5


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: tests assert that invalid ids, ranges, paths and shocks are rejected (Category 1)
#   - Leftover debug code: no credentials, accounts or debug hooks; test-only module (Category 6)
# Not Applied:
#   - [WARN] Authentication: not applicable - offline unit tests
# --------------------------------------------------
