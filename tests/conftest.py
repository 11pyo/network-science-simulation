import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cxsim.spec import EdgeSpec, ModelSpec, NodeSpec, Range  # noqa: E402


def make_spec(nodes, edges, decay=(0.5, 0.5), seed=7, values=None):
    """edges: list of (source, target, low, high)."""
    values = values or {}
    return ModelSpec(
        name="test",
        self_decay=Range(low=decay[0], high=decay[1]),
        sampling={"seed": seed},
        nodes=tuple(NodeSpec(id=n, label=n, value=values.get(n, 1.0)) for n in nodes),
        edges=tuple(
            EdgeSpec(source=s, target=t, weight=Range(low=lo, high=hi)) for s, t, lo, hi in edges
        ),
    )


@pytest.fixture
def chain():
    # a -> b -> c, fixed weights
    return make_spec(["a", "b", "c"], [("a", "b", 0.4, 0.4), ("b", "c", 0.4, 0.4)])


def is_saturated(values, tol=1e-3):
    """Defect signature of the legacy engine: every node pinned at the same +-1 bound."""
    import numpy as np

    v = np.asarray(list(values), dtype=float)
    return bool(np.all(np.abs(np.abs(v) - 1.0) < tol))


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: tests assert that invalid ids, ranges, paths and shocks are rejected (Category 1)
#   - Leftover debug code: no credentials, accounts or debug hooks; test-only module (Category 6)
# Not Applied:
#   - [WARN] Authentication: not applicable - offline unit tests
# --------------------------------------------------
