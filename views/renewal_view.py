# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 11pyo
"""
Renewal P0 view: stable engines, range-based uncertainty, sensitivity.

Results are shown as "x times the direct shock" because the stable engine
does not clip values; a node can legitimately exceed the shock it received.
"""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cxsim.engines import debtrank, linear
from cxsim.spec import list_specs, load_spec
from cxsim.uncertainty import MAX_MC_SAMPLES, SensitivityUnavailable, monte_carlo, sensitivity

logger = logging.getLogger(__name__)

SCENARIO_DIR = Path(__file__).resolve().parent.parent / "scenarios"
MAX_SHOCK_NODES = 5
ENGINES = {"linear": "선형 전파 (부호 있음)", "debtrank": "DebtRank (손실 연쇄, 음수 불가)"}
MODES = {"impulse": "일회성 충격 → 누적 영향", "persistent": "지속 충격 → 정상상태"}
GENERIC_ERROR = "계산을 완료하지 못했습니다. 입력을 확인해 주세요."


def render_renewal_view() -> None:
    st.title("네트워크 스트레스 테스트 (새 엔진 P0)")

    names = list_specs(SCENARIO_DIR)
    if not names:
        st.error("시나리오 파일이 없습니다.")
        return

    c1, c2 = st.columns([2, 1])
    # [SECURE] Selectbox constrained to whitelisted scenario stems (Category 1)
    name = c1.selectbox("시나리오", names, key="rn_scenario")
    engine = c2.radio("엔진", list(ENGINES), format_func=ENGINES.get, key="rn_engine")

    try:
        spec = load_spec(name, SCENARIO_DIR)
    except ValueError as e:
        # [SECURE] Detail logged server-side, generic message to user (Category 4)
        logger.error("Scenario load failed: %s", e)
        st.error("시나리오를 불러오지 못했습니다.")
        return

    if spec.legacy:
        st.warning(
            "기존 프리셋에서 옮긴 미검증 모형입니다. 방향은 원래 무방향이라 양방향으로 넣었고, "
            "가중치는 안정성을 위해 재조정한 상대값(영향의 몫)입니다. 실제 데이터로 검증되지 않았습니다."
        )

    labels = {n.id: n.label for n in spec.nodes}
    shocks = _shock_inputs(spec, labels, engine)
    if not shocks:
        st.info("충격을 줄 노드를 하나 이상 고르세요.")
        return

    if engine == "linear":
        _render_linear(spec, labels, shocks)
    else:
        _render_debtrank(spec, labels, shocks)

    if name in _LEGACY_PRESET_OF:
        _render_legacy_defect(name, shocks)


def _sticky_button(label: str, key: str, signature: tuple, primary: bool = False) -> bool:
    """
    Streamlit buttons are true for one rerun only, so results vanished on the
    next interaction (e.g. opening sensitivity). Keep showing results while the
    inputs that produced them are unchanged; any input change requires a new run.
    """
    if st.button(label, key=key, type="primary" if primary else "secondary"):
        st.session_state[f"{key}__sig"] = signature
    return st.session_state.get(f"{key}__sig") == signature


def _shock_inputs(spec, labels, engine) -> dict:
    # [SECURE] Options limited to spec node ids, count capped (Category 1)
    picked = st.multiselect(
        "충격 노드", spec.node_ids, max_selections=MAX_SHOCK_NODES,
        format_func=lambda x: f"{labels[x]} ({x})", key=f"rn_nodes_{spec.name}",
    )
    lo = 0.0 if engine == "debtrank" else -1.0
    shocks = {}
    cols = st.columns(max(1, len(picked)))
    for col, nid in zip(cols, picked):
        shocks[nid] = col.slider(
            labels[nid], min_value=lo, max_value=1.0, value=0.3, step=0.05, key=f"rn_s_{engine}_{nid}"
        )
    return {k: v for k, v in shocks.items() if v != 0.0}


def _render_linear(spec, labels, shocks) -> None:
    c1, c2 = st.columns(2)
    mode = c1.radio("충격 방식", list(MODES), format_func=MODES.get, horizontal=True, key="rn_mode")
    n_samples = c2.slider("표본 수 (가중치 범위 몬테카를로)", 200, min(5000, MAX_MC_SAMPLES), 1000, 100, key="rn_n")

    sig = (spec.name, tuple(sorted(shocks.items())), mode, n_samples)
    if not _sticky_button("실행", "rn_run_linear", sig, primary=True):
        return
    try:
        nominal = linear.simulate(spec, shocks, mode=mode, steps=60)
        mc = monte_carlo(spec, shocks, n_samples=n_samples, mode=mode)
    except linear.UnstableModelError as e:
        logger.warning("Unstable nominal model: rho=%.3f", e.rho)
        st.error(f"중앙값 가중치에서 모형이 불안정합니다 (스펙트럼 반경 {e.rho:.2f} ≥ 1). 범위를 좁혀 주세요.")
        return
    except linear.AmplificationExceededError as e:
        logger.warning("Explosive nominal model: %.3g x", e.amplification)
        st.error(
            f"모형은 수렴하지만 영향이 직접 충격의 {e.amplification:.3g}배로 폭발합니다 "
            f"(허용 상한 {e.cap:.3g}배). 가중치를 정규화하거나 범위를 좁혀 주세요."
        )
        return
    except linear.NumericalBlowupError as e:
        logger.warning("Numerical blowup: %s", e)
        st.error("수치적으로 풀 수 없는 모형입니다(특이 또는 오버플로). 가중치를 정규화해 주세요.")
        return
    except ValueError as e:
        logger.error("Linear run failed: %s", e)
        st.error(GENERIC_ERROR)
        return

    ref = sum(abs(v) for v in shocks.values())
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("스펙트럼 반경 (중앙값)", f"{nominal.spectral_radius:.3f}")
    m2.metric("불안정 표본 비율", f"{mc.unstable_fraction:.1%}", help="이 비율 자체가 취약도 지표입니다.")
    m3.metric("폭발 표본 비율", f"{mc.explosive_fraction:.1%}",
              help=f"수렴은 하지만 영향이 직접 충격의 {spec.max_amplification:.3g}배를 넘는 표본")
    m4.metric("사용 표본 수", f"{mc.n_stable:,}", help=f"전체 {mc.n_samples:,}개 중")
    if mc.n_stable == 0:
        st.error("사용할 수 있는 표본이 없습니다(전부 불안정 또는 폭발). 가중치 범위나 자기 감쇠를 조정해야 합니다.")
        return
    if mc.ranked_fraction == 0.0:
        st.info("충격이 다른 노드에 도달하지 않아 순위가 없습니다(하류 노드 없음).")

    q = mc.quantiles / ref
    order = np.argsort(-np.abs(q[1]))
    ids = [mc.node_ids[i] for i in order]
    fig = go.Figure(go.Bar(
        x=[labels[i] for i in ids], y=q[1][order],
        error_y=dict(type="data", symmetric=False,
                     array=(q[2] - q[1])[order], arrayminus=(q[1] - q[0])[order]),
        marker_color=[("#888" if i in shocks else "#4C78A8") for i in ids],
    ))
    title = "누적 영향" if mode == "impulse" else "정상상태"
    fig.update_layout(
        title=f"{title}: 직접 충격 1 대비 배수 (막대=중앙값, 선=10~90% 범위)",
        yaxis_title="배수", height=420, margin=dict(t=60, b=40),
    )
    st.plotly_chart(fig, width="stretch")

    table = pd.DataFrame({
        "노드": [labels[i] for i in mc.node_ids],
        "p10 배수": q[0], "p50 배수": q[1], "p90 배수": q[2],
        "최대 영향 확률": _pct_or_shock(mc.top1_prob), f"상위 {mc.k} 확률": _pct_or_shock(mc.topk_prob),
    }).iloc[order]
    st.dataframe(table.style.format(precision=3), width="stretch", hide_index=True)

    traj = pd.DataFrame(nominal.trajectory / ref, columns=[labels[i] for i in nominal.node_ids])
    with st.expander("시간 경로 (중앙값 가중치)"):
        st.line_chart(traj)

    _render_sensitivity(spec, labels, shocks)


def _pct_or_shock(values) -> list:
    # Shocked nodes are excluded from ranking (NaN); label them instead of showing "None".
    return ["충격 노드" if np.isnan(v) else f"{v:.1%}" for v in values]


def _render_sensitivity(spec, labels, shocks) -> None:
    with st.expander("무엇이 결과를 좌우하나 (민감도)"):
        others = [n for n in spec.node_ids if n not in shocks] or spec.node_ids
        # [SECURE] Target limited to spec node ids (Category 1)
        target = st.selectbox("관심 노드", others, format_func=lambda x: labels[x], key="rn_sens_target")
        sig = (spec.name, tuple(sorted(shocks.items())), target)
        if not _sticky_button("민감도 계산", "rn_sens_run", sig):
            return
        try:
            res = sensitivity(spec, shocks, target=target, n_base=128)
        except SensitivityUnavailable as e:
            st.warning(str(e))
            return
        except ValueError as e:
            logger.error("Sensitivity failed: %s", e)
            st.error(GENERIC_ERROR)
            return
        if res.method == "sobol":
            df = pd.DataFrame({"가정": res.params, "총효과 ST": res.total, "1차 S1": res.first})
            df = df.sort_values("총효과 ST", ascending=False)
            note = "Sobol: ST가 클수록 그 가정의 불확실성이 결과 범위를 많이 만듭니다."
        else:
            df = pd.DataFrame({"가정": res.params, "mu*": res.first, "sigma": res.total})
            df = df.sort_values("mu*", ascending=False)
            note = "매개변수가 많아 Morris 선별을 썼습니다. mu*가 클수록 영향이 큽니다."
        st.caption(note)
        st.dataframe(df.head(10).style.format(precision=3), width="stretch", hide_index=True)


def _render_debtrank(spec, labels, shocks) -> None:
    sig = (spec.name, tuple(sorted(shocks.items())))
    if not _sticky_button("실행", "rn_run_dr", sig, primary=True):
        return
    try:
        r = debtrank.run(spec, shocks)
    except ValueError as e:
        logger.error("DebtRank failed: %s", e)
        st.error("DebtRank는 음수 간선(완충)을 지원하지 않거나 입력이 잘못되었습니다. 선형 엔진을 쓰세요.")
        return
    m1, m2, m3 = st.columns(3)
    m1.metric("총 손실 (가치 가중)", f"{r.total_distress:.3f}")
    m2.metric("유발 손실 DebtRank", f"{r.debtrank:.3f}")
    m3.metric("전파 라운드", r.rounds)
    order = np.argsort(-r.h)
    fig = go.Figure(go.Bar(
        x=[labels[r.node_ids[i]] for i in order], y=r.h[order],
        marker_color=[("#888" if r.node_ids[i] in shocks else "#E45756") for i in order],
    ))
    fig.update_layout(title="최종 손실 정도 h (0~1, 중앙값 가중치)", height=400, yaxis_range=[0, 1.05])
    st.plotly_chart(fig, width="stretch")


# Legacy defect reproduction (regression evidence only, never a selectable engine)
_LEGACY_PRESET_OF = {"legacy_sap": "SAP Impact", "legacy_macro": "Macro System"}


def _render_legacy_defect(name, shocks) -> None:
    from config.preset_registry import PRESETS
    from models.network import NetworkModel
    from models.simulation import ShockSimulator

    with st.expander("기존 엔진 결함 재현 (비교용, 사용 금지)"):
        st.caption("같은 충격을 기존 엔진에 넣으면 충격 크기와 무관하게 모든 노드가 ±1로 포화됩니다.")
        p = PRESETS[_LEGACY_PRESET_OF[name]]
        node, val = next(iter(shocks.items()))
        try:
            net = NetworkModel(p["node_ids"], p["default_weights"])
            res = ShockSimulator(net, damping=p["damping_default"], max_steps=20).simulate(node, val)
        except ValueError as e:
            logger.error("Legacy reproduction failed: %s", e)
            st.error(GENERIC_ERROR)
            return
        final = ShockSimulator.get_final_impacts(res)
        st.dataframe(
            pd.DataFrame({"노드": list(final), "기존 엔진 최종값": list(final.values())}),
            width="stretch", hide_index=True,
        )


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: scenario, nodes, target chosen only from whitelists; shock sliders bounded (Category 1)
#   - Error message exposure: details logged server-side, generic Korean messages to users (Category 4)
#   - Exception handling: no empty except blocks; each failure path logged and reported (Category 4)
#   - Resource limits: shock node count, sample count and sensitivity base size capped (Category 3)
# Not Applied:
#   - [WARN] Authentication/CSRF: local single-user Streamlit app; Streamlit XSRF protection left enabled
#   - [WARN] File upload: intentionally not offered in P0 (scenarios are repo files only)
# --------------------------------------------------
