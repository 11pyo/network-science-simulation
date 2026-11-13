# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 11pyo
"""
Industry shock scenario page (산업연관 시나리오 계산기).

A calculator, not a forecaster. Reads the 2020 benchmark domestic table from the
local data folder (never from the repository) and shows direct / indirect /
total output changes for user-entered final-demand changes.
"""

import logging

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from cxsim import io_scenario as sc

logger = logging.getLogger(__name__)
MAX_SECTORS = 8


@st.cache_resource(show_spinner=False)
def _tables(path_str: str):
    from pathlib import Path

    return sc.load_tables(Path(path_str))


DATA_DIR_PS = r"$env:LOCALAPPDATA\nss-renewal-data\io_bok\downloads"
SHA_CMD = (
    f'$f = "{DATA_DIR_PS}\\{sc.BENCHMARK_FILE}"; '
    f'"- file: {sc.BENCHMARK_FILE}`n  sha256: $((Get-FileHash -Algorithm SHA256 $f).Hash.ToLower())" | '
    f'Add-Content -Encoding utf8 "{DATA_DIR_PS}\\{sc.PROVENANCE_FILE}"'
)


def _empty_state(reason: str) -> None:
    st.info(
        "산업연관표 파일이 없어 계산할 수 없습니다.\n\n"
        "1. 한국은행 ECOS(https://ecos.bok.or.kr) → 통계검색 → 2. 국민계정 → 2.2 산업연관표 → "
        "2.2.1 2020년 실측표 기준 → 2.2.1.1 파일 다운로드 → **2020 실측표** → 투입산출표 → 생산자가격 → 통합대분류\n"
        f"2. 받은 파일 `{sc.BENCHMARK_FILE}`를 `%LOCALAPPDATA%\\nss-renewal-data\\io_bok\\downloads\\`에 둡니다.\n"
        f"3. 아래 PowerShell 한 줄로 파일의 SHA-256을 `{sc.PROVENANCE_FILE}`에 기록합니다.\n\n"
        "파일은 저장소에 넣지 않습니다."
    )
    st.code(SHA_CMD, language="powershell")
    st.caption(f"사유: {reason}")


def render_industry_view() -> None:
    st.title("산업연관 시나리오 계산기")
    st.caption("2020 실측표 국산 투입계수(33부문) · 수요 모드 · 예측기가 아닌 시나리오 계산기입니다.")
    st.info(sc.FIXED_NOTE)

    d = sc.default_dir()
    if d is None:
        _empty_state("LOCALAPPDATA 환경변수가 없습니다.")
        return
    try:
        # Title and notice are already on screen; show progress while the workbook is read (F3).
        with st.spinner("산업연관표를 읽는 중…"):
            t = _tables(str(d))
    except FileNotFoundError:
        _empty_state("파일 없음")
        return
    except ValueError as e:
        # [SECURE] Detail logged server-side, generic message to the user (Category 4)
        logger.error("IO tables failed to load: %s", e)
        st.error("산업연관표 파일을 검증하지 못했습니다(해시 또는 공표값 불일치). 파일을 다시 받아 주세요.")
        return

    labels = {c: f"{c} {n}" for c, n in zip(t.codes, t.names)}
    c1, c2 = st.columns([3, 2])
    # [SECURE] Options limited to the 33 sector codes; count capped (Category 1)
    picked = c1.multiselect("최종수요가 변하는 부문", list(t.codes), max_selections=MAX_SECTORS,
                            format_func=labels.get, key="io_sectors")
    unit = c2.radio("입력 단위", ["조원", "% (2020 해당 부문 최종수요 대비)"], key="io_unit", horizontal=True)
    use_range = st.toggle("범위로 입력(최소~최대)", key="io_range")
    if not picked:
        st.info("부문을 하나 이상 고르세요.")
        return

    pct = unit.startswith("%")
    if pct:
        base_ok = sc.percent_base_ok(t)
        bad = [c for c in picked if not base_ok[c]]
        if bad:
            # F1: a zero/negative % base would flip the sign of the shock - refuse with sector names
            st.warning("다음 부문은 2020년 국산 최종수요가 0 이하라 %로 입력할 수 없습니다. 조원으로 입력하세요: "
                       + ", ".join(labels[c] for c in bad))
            return

    lo_in, hi_in = {}, {}
    h1, h2, h3 = st.columns([3, 2, 2])
    h2.caption("변화" if not use_range else "최소")
    if use_range:
        h3.caption("최대")
    for code in picked:
        a, b, c = st.columns([3, 2, 2])
        a.markdown(f"**{labels[code]}**")
        # F6: the accessible label carries the sector code; the visible header stays short
        lo = b.number_input(f"{code} {'변화' if not use_range else '최소'}", value=-1.0, step=0.5,
                            min_value=-1000.0, max_value=1000.0, key=f"io_lo_{code}",
                            label_visibility="collapsed")
        lo_in[code] = lo
        if use_range:
            hi_in[code] = c.number_input(f"{code} 최대", value=max(lo, 0.0), step=0.5,
                                         min_value=-1000.0, max_value=1000.0, key=f"io_hi_{code}",
                                         label_visibility="collapsed")
    try:
        lo_t = sc.percent_to_trillion(t, lo_in) if pct else lo_in
        hi_t = (sc.percent_to_trillion(t, hi_in) if pct else hi_in) if use_range else None
        r = sc.run_scenario(t, lo_t, hi_t)
    except ValueError as e:
        logger.warning("Scenario input rejected: %s", e)
        st.error("입력을 확인해 주세요(최소가 최대보다 크거나 허용 범위를 벗어났습니다).")
        return

    tag = ", 중앙" if use_range else ""                      # F4: short tag; explained in the caption below
    if use_range:
        st.caption("범위 입력: 지표·막대·표의 직접/간접/합계는 **범위 중앙** 기준입니다.")
    m1, m2, m3 = st.columns(3)
    m1.metric(f"직접 변화(조원{tag})", f"{r.direct.sum():+,.2f}")
    m2.metric(f"총 생산 변화(조원{tag})", f"{r.total.sum():+,.2f}")
    m3.metric("생산유발 배수" + (" (중앙)" if use_range else ""), "—" if r.multiplier is None else f"{r.multiplier:.3f}",
              help="총 생산 변화 ÷ 최종수요 변화. 충격의 부호가 모두 같을 때만 표시합니다"
                   "(늘어나는 부문과 줄어드는 부문이 섞이면 의미가 없습니다).")
    if use_range:
        st.caption(f"총 생산 변화 범위: {r.total_low.sum():+,.2f} ~ {r.total_high.sum():+,.2f} 조원 "
                   "(부문별 최소·최대를 각각 합한 값)")

    mid_col = "(조원, 범위 중앙)" if use_range else "(조원)"
    df = pd.DataFrame({
        "부문": [labels[c] for c in r.codes],
        f"직접{mid_col}": r.direct, f"간접{mid_col}": r.indirect, f"합계{mid_col}": r.total,
        "2020 산출 대비 %" + (" (중앙)" if use_range else ""): r.pct_of_output,
    })
    if use_range:
        df["합계 최소(조원)"] = r.total_low
        df["합계 최대(조원)"] = r.total_high
    total_col = f"합계{mid_col}"
    df = df.reindex(df[total_col].abs().sort_values(ascending=False).index)
    df = df[np.abs(df[total_col]) > 1e-9]

    top = df.head(10).iloc[::-1]
    fig = go.Figure()
    fig.add_bar(y=top["부문"], x=top[f"직접{mid_col}"], name="직접", orientation="h", marker_color="#4C78A8")
    fig.add_bar(y=top["부문"], x=top[f"간접{mid_col}"], name="간접", orientation="h", marker_color="#F58518")
    if use_range:
        # F5: total point with an error bar, in a colour that contrasts with light and dark backgrounds
        mid = top[total_col]
        fig.add_scatter(
            y=top["부문"], x=mid, mode="markers", name="합계(범위)",
            marker=dict(symbol="diamond", size=10, color="#E45756", line=dict(width=1, color="#FFFFFF")),
            error_x=dict(type="data", symmetric=False, array=top["합계 최대(조원)"] - mid,
                         arrayminus=mid - top["합계 최소(조원)"], color="#E45756", thickness=2, width=6),
        )
    fig.update_layout(barmode="relative",
                      title="상위 10개 부문 생산 변화 (조원)",
                      height=440, margin=dict(t=60, b=30, l=10, r=10), legend_orientation="h")
    st.plotly_chart(fig, width="stretch")
    st.caption("막대 = 직접(파랑) + 간접(주황)" + (" · 범위 중앙 기준, 빨간 점과 선 = 합계와 최소~최대" if use_range else ""))
    st.dataframe(df.style.format(precision=3), width="stretch", hide_index=True)
    st.caption(f"엔진 역행렬과 공표 생산유발계수의 최대 오차: {t.max_abs_error:.1e} (불러올 때마다 다시 확인)")


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: sector whitelist, bounded number inputs, range checked in cxsim.io_scenario (Category 1)
#   - Error message exposure: details logged server-side, generic messages on screen (Category 4)
#   - Data handling: tables read from the local data folder only, hash-checked, never written (Category 5)
# Not Applied:
#   - [WARN] Authentication: local single-user Streamlit app
# --------------------------------------------------
