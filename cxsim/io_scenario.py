# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 11pyo
"""
Industry shock scenario calculator (P1-industry product, PM decision 2026-11-12).

A scenario CALCULATOR, not a forecaster: given final-demand changes by sector,
it computes output changes with the 2020 benchmark domestic structure using the
engine in demand mode (lam = 1), whose inverse equals the published
production-inducement coefficients (gate 1).

Ranges: the calculation is linear in the shock, so for independent sector
ranges [lo_j, hi_j] the exact output range of sector i is obtained by interval
arithmetic (sum of L_ij * lo_j or L_ij * hi_j, whichever is smaller/larger).
"""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cxsim import gate2, io_table

BENCHMARK_FILE = "(표)(2020실측)투입산출표_생산자가격_통합대분류.xlsx"
PROVENANCE_FILE = "PROVENANCE_ecos_files.txt"
UNIT_TO_TRILLION = 1e-6  # tables are in million KRW
logger = logging.getLogger(__name__)
# Fixed wording required on every screen/document (PM decision, RENEWAL_DESIGN.md).
FIXED_NOTE = (
    "공표 생산유발계수와 일치하는 계산입니다(관문 1). 2020년 되맞히기에서 간접 파급은 부문 순위 설명을 "
    "문턱 이상 높이지 못했고, 오차 크기는 직접 효과만 볼 때보다 0.3~0.7%p 작았습니다"
    "(15부문, 사건 1개, 유의성 주장 없음)."
)
# [SECURE] Bounded shock size in trillion KRW - rejects absurd inputs (Category 1)
MAX_ABS_SHOCK_TRILLION = 1000.0


@dataclass(frozen=True)
class IOTables:
    codes: tuple[str, ...]
    names: tuple[str, ...]
    ad: np.ndarray
    inverse: np.ndarray           # engine (I - Ad)^-1, checked against the published sheet
    output: np.ndarray            # 2020 total output (million KRW), 9290
    final_demand: np.ndarray      # 2020 domestic final demand (million KRW), 9190
    max_abs_error: float          # engine vs published inducement coefficients


def default_dir() -> Path | None:
    import os

    # LOCALAPPDATA on Windows; the home folder elsewhere (same rule as scripts/fetch_bok_io.py)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "nss-renewal-data" / "io_bok" / "downloads"


# Cache layout revision; bump when the cached array layout changes.
_TABLE_LAYOUT_REV = "k33-28bab052"


def cache_path(downloads: Path, digest: str) -> Path:
    return Path(downloads).parent / "derived" / f"io_scenario_cache_{digest[:16]}_{_TABLE_LAYOUT_REV}.npz"


def load_tables(downloads: Path, use_cache: bool = True) -> IOTables:
    """
    Read the benchmark workbook (hash-checked). The parsed arrays are cached next to the
    data, keyed by the workbook SHA-256; a different workbook (different hash) is re-read.
    The engine-vs-published check runs on every load, cached or not (PM review F3).
    """
    path = Path(downloads) / BENCHMARK_FILE
    prov = Path(downloads) / PROVENANCE_FILE
    if not path.is_file() or not prov.is_file():
        raise FileNotFoundError("Benchmark workbook or provenance file not found.")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    # [SECURE] Integrity check against recorded provenance before parsing (Category 5)
    if digest not in prov.read_text(encoding="utf-8"):
        raise ValueError("Workbook hash does not match the provenance record.")

    cpath = cache_path(downloads, digest)
    arrays = _read_cache(cpath, digest) if use_cache else None
    if arrays is None:
        arrays = _read_workbook(path)
        if use_cache:
            _write_cache(cpath, digest, arrays)
    codes, names, ad, pub, x, fd = arrays

    inv = io_table.engine_inverse(ad)
    err = float(np.max(np.abs(inv - pub)))
    if err > io_table.DEFAULT_TOL:
        raise ValueError("Engine inverse does not match the published coefficients.")
    return IOTables(codes, names, ad, inv, x, fd, err)


def _read_workbook(path: Path):
    flow = gate2.flow_sheet_name(io_table.sheet_names(path))
    sheets = io_table.read_sheets(path, [io_table.SHEET_DOMESTIC, io_table.SHEET_INDUCEMENT, flow])
    ad = io_table.parse_coefficient_rows(sheets[io_table.SHEET_DOMESTIC], io_table.SHEET_DOMESTIC)
    pub = io_table.parse_coefficient_rows(sheets[io_table.SHEET_INDUCEMENT], io_table.SHEET_INDUCEMENT)
    if pub.codes != ad.codes:
        raise ValueError("Sector codes differ between sheets.")
    cols = gate2.parse_flow_rows(sheets[flow], (gate2.FD_TOTAL, gate2.OUTPUT_COL), outcome_year=False)
    x = np.array([cols[gate2.OUTPUT_COL][c] for c in ad.codes])
    fd = np.array([cols[gate2.FD_TOTAL][c] for c in ad.codes])
    return ad.codes, ad.names, ad.matrix, pub.matrix, x, fd


def _read_cache(cpath: Path, digest: str):
    if not cpath.is_file():
        return None
    try:
        # [SECURE] allow_pickle=False - no code execution from the cache file (Category 5)
        with np.load(cpath, allow_pickle=False) as z:
            if str(z["sha256"]) != digest:
                return None
            return (tuple(str(c) for c in z["codes"]), tuple(str(n) for n in z["names"]),
                    z["ad"].astype(float), z["pub"].astype(float), z["x"].astype(float), z["fd"].astype(float))
    except (OSError, KeyError, ValueError):
        # [SECURE] A damaged cache is ignored and rebuilt, never trusted (Category 4)
        return None


def _write_cache(cpath: Path, digest: str, arrays) -> None:
    import os
    import tempfile

    codes, names, ad, pub, x, fd = arrays
    try:
        cpath.parent.mkdir(exist_ok=True)
        fd_, tmp = tempfile.mkstemp(prefix=".io_cache.", suffix=".npz", dir=cpath.parent)
        os.close(fd_)
        try:
            np.savez(tmp, sha256=np.array(digest), codes=np.array(codes), names=np.array(names),
                     ad=ad, pub=pub, x=x, fd=fd)
            # [SECURE] Atomic replace - readers never see a partial cache (Category 3)
            os.replace(tmp, cpath)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    except OSError as e:
        # [SECURE] Logged, not swallowed; caching is an optimisation and the tables are still returned (Category 4)
        logger.warning("IO scenario cache not written: %s", e)


@dataclass(frozen=True)
class ScenarioResult:
    codes: tuple[str, ...]
    direct: np.ndarray            # trillion KRW (= the shock itself)
    indirect: np.ndarray          # trillion KRW
    total: np.ndarray             # trillion KRW
    total_low: np.ndarray         # exact range bounds (equal to total when no range given)
    total_high: np.ndarray
    pct_of_output: np.ndarray     # total / 2020 output * 100
    multiplier: float | None      # sum(total) / sum(shock); None unless all shocks share one sign


def _vector(tables: IOTables, shocks: dict[str, float]) -> np.ndarray:
    idx = {c: i for i, c in enumerate(tables.codes)}
    v = np.zeros(len(tables.codes))
    for code, val in shocks.items():
        # [SECURE] Whitelisted sector codes and bounded finite values (Category 1)
        if code not in idx:
            raise ValueError("Unknown sector code.")
        if not isinstance(val, (int, float)) or not math.isfinite(val) or abs(val) > MAX_ABS_SHOCK_TRILLION:
            raise ValueError("Shock must be finite and within the allowed range.")
        v[idx[code]] = float(val)
    return v


def run_scenario(tables: IOTables, low: dict[str, float], high: dict[str, float] | None = None) -> ScenarioResult:
    """low/high: final-demand change per sector in trillion KRW. high=None means a point scenario."""
    lo = _vector(tables, low)
    hi = lo.copy() if high is None else _vector(tables, high)
    if np.any(hi < lo):
        raise ValueError("Range maximum is below its minimum.")
    mid = (lo + hi) / 2.0
    L = tables.inverse
    total = L @ mid
    Lp, Ln = np.clip(L, 0, None), np.clip(L, None, 0)
    t_low = Lp @ lo + Ln @ hi
    t_high = Lp @ hi + Ln @ lo
    x_trillion = tables.output * UNIT_TO_TRILLION
    nonzero = mid[np.abs(mid) > 1e-12]
    # Multiplier only when every shock has the same sign (PM review F2); mixed signs make it meaningless.
    same_sign = nonzero.size > 0 and (np.all(nonzero > 0) or np.all(nonzero < 0))
    return ScenarioResult(
        codes=tables.codes,
        direct=mid,
        indirect=total - mid,
        total=total,
        total_low=t_low,
        total_high=t_high,
        pct_of_output=np.divide(total, x_trillion, out=np.zeros_like(total), where=x_trillion > 0) * 100,
        multiplier=float(total.sum() / nonzero.sum()) if same_sign else None,
    )


class NonPositiveBaseError(ValueError):
    """% input requested for sectors whose 2020 domestic final demand is <= 0 (PM review F1)."""

    def __init__(self, codes: list[str]):
        super().__init__(f"Final demand <= 0 for: {', '.join(codes)}")
        self.codes = codes


def percent_base_ok(tables: IOTables) -> dict[str, bool]:
    return {c: bool(v > 0) for c, v in zip(tables.codes, tables.final_demand)}


def percent_to_trillion(tables: IOTables, pct: dict[str, float]) -> dict[str, float]:
    """Convert '% of the sector's 2020 domestic final demand' into trillion KRW."""
    idx = {c: i for i, c in enumerate(tables.codes)}
    bad = [c for c in pct if c in idx and tables.final_demand[idx[c]] <= 0]
    # [SECURE] Refuse a % base that is zero or negative - it would flip the sign of the shock (Category 1)
    if bad:
        raise NonPositiveBaseError(bad)
    out = {}
    for code, p in pct.items():
        if code not in idx:
            raise ValueError("Unknown sector code.")
        if not isinstance(p, (int, float)) or not math.isfinite(p) or abs(p) > 1000:
            raise ValueError("Percent must be finite and within +-1000.")
        out[code] = tables.final_demand[idx[code]] * UNIT_TO_TRILLION * p / 100.0
    return out


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Integrity: workbook hash checked against provenance; engine inverse re-verified against the
#     published sheet on every load (Category 5)
#   - Input validation: sector-code whitelist, finite and bounded shocks/percents, min <= max (Category 1)
#   - Error handling: explicit exceptions for missing files and mismatches (Category 4)
# Not Applied:
#   - [WARN] Authentication: not applicable - local single-user calculator
#   - [WARN] Cache integrity: the cached output and final-demand arrays are not re-verified against
#     published values (only the inverse is); accepted for a local single-user tool (PM review N4).
#     Delete derived/io_scenario_cache_*.npz to force a re-read if the cache may have been altered
# --------------------------------------------------
