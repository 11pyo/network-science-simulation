from pathlib import Path

import pytest
from pydantic import ValidationError

from conftest import make_spec
from cxsim.spec import ModelSpec, list_specs, load_spec

SCEN = Path(__file__).resolve().parent.parent / "scenarios"


def test_valid_spec_builds():
    spec = make_spec(["a", "b"], [("a", "b", 0.1, 0.2)])
    assert spec.node_ids == ["a", "b"]


@pytest.mark.parametrize(
    "nodes,edges,decay",
    [
        (["a", "a"], [], (0.5, 0.5)),                      # duplicate node
        (["a", "b"], [("a", "x", 0.1, 0.1)], (0.5, 0.5)),  # undeclared node
        (["a", "b"], [("a", "b", 0.3, 0.1)], (0.5, 0.5)),  # low > high
        (["a", "b"], [("a", "a", 0.1, 0.1)], (0.5, 0.5)),  # self loop
        (["a", "b"], [], (0.0, 0.5)),                      # self_decay must be > 0
        (["a", "b"], [], (0.5, 1.5)),                      # self_decay <= 1
        (["A!", "b"], [], (0.5, 0.5)),                     # bad id characters
        (["a", "b"], [("a", "b", 0.1, 0.1), ("a", "b", 0.2, 0.2)], (0.5, 0.5)),  # duplicate edge
    ],
)
def test_invalid_specs_rejected(nodes, edges, decay):
    with pytest.raises((ValidationError, ValueError)):
        make_spec(nodes, edges, decay)


def test_unknown_field_rejected():
    with pytest.raises(ValidationError):
        ModelSpec.model_validate(
            {"name": "x", "self_decay": {"low": 0.5, "high": 0.5},
             "nodes": [{"id": "a", "label": "a"}, {"id": "b", "label": "b"}],
             "edges": [], "evil": 1}
        )


@pytest.mark.parametrize("name", ["../app", "..\\app", "legacy_sap/../x", "/etc/passwd", "LEGACY", ""])
def test_load_spec_rejects_unsafe_names(name):
    with pytest.raises(ValueError):
        load_spec(name, SCEN)


def test_shipped_scenarios_load():
    names = list_specs(SCEN)
    assert {"legacy_sap", "legacy_macro"} <= set(names)
    for n in names:
        spec = load_spec(n, SCEN)
        assert spec.legacy and spec.normalization == "legacy_in_strength"


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: tests assert that invalid ids, ranges, paths and shocks are rejected (Category 1)
#   - Leftover debug code: no credentials, accounts or debug hooks; test-only module (Category 6)
# Not Applied:
#   - [WARN] Authentication: not applicable - offline unit tests
# --------------------------------------------------
