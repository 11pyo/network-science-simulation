"""
Sidebar controls: correlation coefficient sliders, shock configuration.
"""

import streamlit as st

from config.constants import (
    NODES, NODE_IDS, NODE_LABELS_KO,
    WEIGHT_MIN, WEIGHT_MAX, WEIGHT_STEP,
    SHOCK_MIN, SHOCK_MAX,
    MAX_SIMULATION_STEPS, DEFAULT_SIMULATION_STEPS,
    DAMPING_FACTOR,
)
from config.defaults import DEFAULT_WEIGHTS


def _get_pair_key(a: str, b: str) -> str:
    """Generate a deterministic session state key for a node pair."""
    return f"weight_{min(a, b)}_{max(a, b)}"


def _get_default_weight(a: str, b: str) -> float:
    """Look up default weight for a node pair."""
    if (a, b) in DEFAULT_WEIGHTS:
        return DEFAULT_WEIGHTS[(a, b)]
    if (b, a) in DEFAULT_WEIGHTS:
        return DEFAULT_WEIGHTS[(b, a)]
    return 0.0


def render_sidebar() -> dict:
    """
    Render the sidebar with all controls and return user configuration.

    Returns:
        dict with keys: weights, shock_node, shock_intensity, steps, damping
    """
    st.sidebar.title("SAP System Impact Simulation")
    st.sidebar.markdown("---")

    # --- System Correlation Coefficients ---
    st.sidebar.subheader("System Correlations")

    weights = {}

    for i, (src_id, src_ko, _, _) in enumerate(NODES):
        with st.sidebar.expander(f"{src_ko} ({src_id.upper()}) Connections"):
            for j in range(i + 1, len(NODES)):
                dst_id, dst_ko, _, _ = NODES[j]
                pair_key = _get_pair_key(src_id, dst_id)
                default_val = _get_default_weight(src_id, dst_id)

                # [SECURE] Slider range bounded by constants - user cannot exceed bounds (Category 1)
                val = st.slider(
                    f"{src_ko} - {dst_ko}",
                    min_value=WEIGHT_MIN,
                    max_value=WEIGHT_MAX,
                    value=default_val,
                    step=WEIGHT_STEP,
                    key=pair_key,
                )
                weights[(src_id, dst_id)] = val

    st.sidebar.markdown("---")

    # --- Shock Configuration ---
    st.sidebar.subheader("Shock Configuration")

    # Help dialog for shock configuration
    @st.dialog("How to Set Shock Configuration", width="large")
    def _show_help():
        st.markdown("""
### Shock Intensity (충격 강도) — 0.0 ~ 1.0

| Value | Meaning | When to Use |
|-------|---------|-------------|
| **0.1 ~ 0.3** | Minor incident | Slow response, intermittent errors |
| **0.4 ~ 0.6** | Moderate failure | Partial module down, batch failure |
| **0.7 ~ 0.9** | Major outage | Service unavailable, critical failure |
| **1.0** | Full shutdown | Physical server down, complete stop |

---

### Simulation Steps (시뮬레이션 단계) — 1 ~ 20

| Value | Meaning | When to Use |
|-------|---------|-------------|
| **3 ~ 5** | Short-term | Immediate impact scope |
| **8 ~ 10** | Mid-term | General analysis **(recommended)** |
| **15 ~ 20** | Long-term | Observe stabilization point |

> Lower Damping → increase Steps for meaningful observation.

---

### Damping Factor (감쇠 계수) — 0.1 ~ 0.9

**Formula: S(t+1) = Damping × W × S(t)**

| Value | Meaning | When to Use |
|-------|---------|-------------|
| **0.1 ~ 0.3** | Fast decay | Well-isolated, strong self-recovery |
| **0.4 ~ 0.6** | Realistic | **Typical SAP environment (recommended)** |
| **0.7 ~ 0.9** | Slow decay | Legacy, strongly coupled systems |

---

### Recommended Presets

| Scenario | Intensity | Steps | Damping |
|----------|-----------|-------|---------|
| Daily incident analysis | 0.4 | 10 | 0.5 |
| Worst-case scenario | 1.0 | 10 | 0.7 |
| Well-isolated environment | 0.6 | 10 | 0.3 |
| Heavy legacy integration | 0.5 | 15 | 0.8 |
""")

    if st.sidebar.button("ℹ How to Set?", use_container_width=True):
        _show_help()

    # [SECURE] Selectbox only offers predefined node IDs (Category 1)
    shock_node = st.sidebar.selectbox(
        "Target Node",
        options=NODE_IDS,
        format_func=lambda x: f"{NODE_LABELS_KO[x]} ({x.upper()})",
        key="shock_node",
    )

    shock_intensity = st.sidebar.slider(
        "Shock Intensity",
        min_value=SHOCK_MIN,
        max_value=SHOCK_MAX,
        value=0.8,
        step=0.05,
        key="shock_intensity",
    )

    steps = st.sidebar.slider(
        "Simulation Steps",
        min_value=1,
        max_value=MAX_SIMULATION_STEPS,
        value=DEFAULT_SIMULATION_STEPS,
        step=1,
        key="sim_steps",
    )

    damping = st.sidebar.slider(
        "Damping Factor",
        min_value=0.1,
        max_value=0.9,
        value=DAMPING_FACTOR,
        step=0.05,
        key="damping",
    )

    st.sidebar.markdown("---")

    run_sim = st.sidebar.button("Run Simulation", type="primary", use_container_width=True)

    if st.sidebar.button("Reset to Defaults", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key.startswith("weight_"):
                del st.session_state[key]
        st.rerun()

    return {
        "weights": weights,
        "shock_node": shock_node,
        "shock_intensity": shock_intensity,
        "steps": steps,
        "damping": damping,
        "run_simulation": run_sim,
    }


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: All sliders bounded by constants (Category 1)
#   - Whitelist input: Selectbox only offers predefined NODE_IDS (Category 1)
# Not Applied:
#   - [WARN] SQL Injection: Not applicable - no database
#   - [WARN] CSRF: Streamlit handles internally
# --------------------------------------------------
