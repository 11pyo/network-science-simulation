# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 11pyo
"""
P1-industry gate 2 (spec locked in 98e957d, mapping in 8813afd/63823eb).

Structural-consistency check, not a forecast: given the realised 2019->2020
domestic final-demand change, does the 2019 domestic structure's indirect
propagation match an independent production index better than the direct
effect alone? Model and direct baseline both benefit from the same leakage,
so the meaningful number is their difference.

Outcome guard: the 2020 table's output / intermediate-demand columns (9290,
9090) are never read. Only final-demand columns are requested from it.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from cxsim import io_table

DOMESTIC_FLOW_SHEET_HINT = "국산거래표"
FD_MAIN = ("9111", "9112", "9121", "9122", "9140")          # excl. inventories 9131, valuables 9132
FD_ALL_ITEMS = ("9111", "9112", "9121", "9122", "9131", "9132", "9140")
FD_TOTAL = "9190"
OUTPUT_COL = "9290"
# [SECURE] Columns that must never be read from the outcome-year table (Category 1, leakage guard)
FORBIDDEN_OUTCOME_COLS = frozenset({"9290", "9090"})
_COL_CODE = re.compile(r"^\d{4}$")

LEAD_RHO = 0.10
BOOTSTRAP_B = 10000
BOOTSTRAP_SEED = 20261112


def read_flow_columns(path: Path, columns: tuple[str, ...], outcome_year: bool) -> dict[str, dict[str, float]]:
    """{column_code: {sector_code: value}} from the domestic flow sheet (rows = 33 sectors)."""
    if outcome_year and FORBIDDEN_OUTCOME_COLS & set(columns):
        raise ValueError("Refusing to read output/intermediate totals from the outcome-year table.")
    name = flow_sheet_name(io_table.sheet_names(path))
    return parse_flow_rows(io_table.read_sheets(path, [name])[name], columns, outcome_year)


def flow_sheet_name(names: list[str]) -> str:
    found = [s for s in names if DOMESTIC_FLOW_SHEET_HINT in s]
    if len(found) != 1:
        raise ValueError("Domestic flow sheet not found uniquely.")
    return found[0]


def parse_flow_rows(rows: list[tuple], columns: tuple[str, ...], outcome_year: bool) -> dict[str, dict[str, float]]:
    # [SECURE] Leakage guard repeated at the parsing layer (Category 1)
    if outcome_year and FORBIDDEN_OUTCOME_COLS & set(columns):
        raise ValueError("Refusing to read output/intermediate totals from the outcome-year table.")
    header = rows[io_table.HEADER_CODE_ROW - 1]
    col_at = {}
    for c, v in enumerate(header):
        code = str(v).strip() if v is not None else ""
        if code in columns:
            col_at[code] = c
    missing = set(columns) - set(col_at)
    if missing:
        raise ValueError(f"Columns not found: {sorted(missing)}")
    out = {c: {} for c in columns}
    for r in rows[io_table.FIRST_DATA_ROW - 1:]:
        code = str(r[0]).strip() if r and r[0] is not None else ""
        if not io_table._SECTOR_CODE.fullmatch(code):
            continue
        for c, idx in col_at.items():
            out[c][code] = io_table._number(r[idx] if idx < len(r) else None)
    return out


def final_demand(cols: dict[str, dict[str, float]], items: tuple[str, ...], codes: tuple[str, ...]) -> np.ndarray:
    return np.array([sum(cols[i][s] for i in items) for s in codes], dtype=float)


def rescale_items(cols19: dict[str, dict[str, float]], cols20: dict[str, dict[str, float]],
                  items: tuple[str, ...], codes: tuple[str, ...], growth: dict[str, float]) -> np.ndarray:
    """
    Amendment 1, option A: keep the 2020 sector composition of each item k but set the
    item total to FD2019_k * (1 + g_k), g_k = nominal NA growth (same base year, no break).
    Returns the adjusted 2020 final demand per sector (sum over items).
    """
    out = np.zeros(len(codes))
    for k in items:
        if k not in growth:
            raise ValueError(f"No national-accounts growth for item {k}.")
        g = float(growth[k])
        if not math.isfinite(g) or g <= -1.0:
            raise ValueError("Growth must be finite and > -100%.")
        v20 = np.array([cols20[k][s] for s in codes], dtype=float)
        t19 = sum(cols19[k][s] for s in codes)
        t20 = v20.sum()
        if t20 == 0.0:
            raise ValueError(f"Item {k} has zero 2020 total; cannot rescale.")
        out += v20 * (t19 * (1.0 + g) / t20)
    return out


def fixed_composition_shock(cols19: dict[str, dict[str, float]], items: tuple[str, ...],
                            codes: tuple[str, ...], real_growth: dict[str, float]) -> np.ndarray:
    """Amendment 1, option B: df_j = sum_k FD2019_jk * r_k (real NA growth); the 2020 table is not used."""
    out = np.zeros(len(codes))
    for k in items:
        if k not in real_growth:
            raise ValueError(f"No national-accounts real growth for item {k}.")
        r = float(real_growth[k])
        if not math.isfinite(r):
            raise ValueError("Growth must be finite.")
        out += np.array([cols19[k][s] for s in codes], dtype=float) * r
    return out


def combine_verdicts(main: str, fixed_composition: str) -> str:
    """Amendment 1 rule: if option A and option B verdicts differ, mark as unstable."""
    if main != fixed_composition:
        return f"불안정 — 충격 구성 방식에 따라 달라짐 (안 A: {main} / 안 B: {fixed_composition})"
    return main


def shock(fd19: np.ndarray, fd20: np.ndarray, price_ratio: np.ndarray | None) -> np.ndarray:
    """Real change: FD2020 / p - FD2019 (p = 2020/2019 producer-price ratio); nominal if price_ratio is None."""
    if price_ratio is None:
        return fd20 - fd19
    p = np.asarray(price_ratio, dtype=float)
    if np.any(~np.isfinite(p)) or np.any(p <= 0):
        raise ValueError("Price ratios must be finite and positive.")
    return fd20 / p - fd19


@dataclass(frozen=True)
class Predictions:
    model: np.ndarray     # (I - Ad)^-1 df / x19
    direct: np.ndarray    # df / x19
    uniform: float        # sum(df) / sum(FD19)


def predict(ad19: np.ndarray, df: np.ndarray, x19: np.ndarray, fd19: np.ndarray) -> Predictions:
    x19 = np.asarray(x19, dtype=float)
    if np.any(x19 <= 0):
        raise ValueError("2019 output must be positive for growth rates.")
    L = io_table.engine_inverse(ad19)
    return Predictions(model=(L @ df) / x19, direct=df / x19, uniform=float(df.sum() / fd19.sum()))


def aggregate_growth(index19: dict[str, float], index20: dict[str, float], weights: dict[str, float],
                     mapping: dict[str, str]) -> dict[str, float]:
    """IO-sector growth from KSIC-division indices: (sum w*I20)/(sum w*I19) - 1 per IO sector."""
    num, den = {}, {}
    for div, sector in mapping.items():
        if div not in index19 or div not in index20 or div not in weights:
            raise ValueError(f"Missing index or weight for division {div}.")
        w = float(weights[div])
        if not math.isfinite(w) or w <= 0:
            raise ValueError("Weights must be positive.")
        num[sector] = num.get(sector, 0.0) + w * float(index20[div])
        den[sector] = den.get(sector, 0.0) + w * float(index19[div])
    return {s: num[s] / den[s] - 1.0 for s in num}


@dataclass(frozen=True)
class Metrics:
    n: int
    rho_model: float
    rho_direct: float
    mae_model: float
    mae_direct: float
    mae_uniform: float
    rho_diff_ci90: tuple[float, float]
    verdict: str
    notes: list[str] = field(default_factory=list)


def _rho(a, b) -> float:
    # Lazy import: scipy.stats costs ~5 s to import and is only needed for gate-2 evaluation,
    # not for the scenario calculator that reuses this module's readers.
    from scipy.stats import spearmanr

    r = spearmanr(a, b).statistic
    return float(r) if np.isfinite(r) else float("nan")


def evaluate(pred: Predictions, actual: dict[str, float], codes: tuple[str, ...], sectors: tuple[str, ...]) -> Metrics:
    idx = [codes.index(s) for s in sectors]
    m, d = pred.model[idx], pred.direct[idx]
    y = np.array([actual[s] for s in sectors], dtype=float)
    n = len(sectors)
    rho_m, rho_d = _rho(m, y), _rho(d, y)
    mae_m = float(np.mean(np.abs(m - y)) * 100)
    mae_d = float(np.mean(np.abs(d - y)) * 100)
    mae_u = float(np.mean(np.abs(pred.uniform - y)) * 100)

    # Simulation randomness, not security randomness; seeded for reproducibility.
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    diffs = []
    # [SECURE] Fixed number of resamples - bounded loop (Category 3)
    for _ in range(BOOTSTRAP_B):
        k = rng.integers(0, n, n)
        if len(set(k)) < 3:
            continue
        a, b = _rho(m[k], y[k]), _rho(d[k], y[k])
        if np.isfinite(a) and np.isfinite(b):
            diffs.append(a - b)
    lo, hi = (float(np.percentile(diffs, 5)), float(np.percentile(diffs, 95))) if diffs else (float("nan"),) * 2

    passes = (rho_m - rho_d >= LEAD_RHO) and (mae_m <= mae_d) and (mae_m < mae_u)
    verdict = "파급이 설명력을 더한다" if passes else "더한다고 볼 수 없다"
    notes = []
    if not (math.isfinite(lo) and math.isfinite(hi)) or lo <= 0.0 <= hi:
        notes.append("부트스트랩 90% 구간이 0을 포함: 방향만 확인, 우연과 구별되지 않음")
        if passes:
            verdict = "방향만 확인, 우연과 구별되지 않음"
    return Metrics(n, rho_m, rho_d, mae_m, mae_d, mae_u, (lo, hi), verdict, notes)


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Leakage guard: outcome-year output/intermediate columns cannot be requested (Category 1)
#   - Input validation: unique sheet, required columns present, sector-code whitelist, finite numbers,
#     positive prices/weights/outputs (Category 1)
#   - Resource release: workbook closed in finally (Category 5); bounded bootstrap loop (Category 3)
# Not Applied:
#   - [WARN] Improper random value: numpy default_rng on purpose - statistical resampling, seeded for
#     reproducibility, not a security decision
# --------------------------------------------------
