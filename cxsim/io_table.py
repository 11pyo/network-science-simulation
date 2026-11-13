"""
Bank of Korea input-output tables (ECOS xlsx) -> engine matrices (P1-industry).

Demand mode (design v2.1, PM decision): with lam = 1 the linear engine's
(lam I - A)^-1 s is exactly the Leontief inverse. A sector j's final-demand
shock flows to its suppliers i, so source = j, target = i and
A[target=i, source=j] = a_ij (input of i per unit output of j). That is the
input-coefficient matrix as published, used without transposition.

Gate 1: the engine's inverse must equal the published production-inducement
coefficient table element by element. The published sheet does not say which
type it is, so every candidate coefficient matrix in the same workbook is
tried and the matching pair is reported (or none, which stops the stage).
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from cxsim.engines import linear

# Sheet names in the ECOS "통합대분류" workbooks (2019 extended and 2020 benchmark).
SHEET_TOTAL = "총투입계수(A)"
SHEET_DOMESTIC = "국산투입계수(Ad)"
SHEET_IMPORT = "수입투입계수(Am)"
SHEET_INDUCEMENT = "생산유발계수"
CANDIDATES = {"total_A": SHEET_TOTAL, "domestic_Ad": SHEET_DOMESTIC}

HEADER_CODE_ROW = 5
FIRST_DATA_ROW = 7
FIRST_DATA_COL = 3
# [SECURE] Whitelisted sector-code pattern (A, B, C01..C14, ...) - rejects summary rows like 9590 (Category 1)
_SECTOR_CODE = re.compile(r"^[A-Z](\d{2})?$")
# [SECURE] Size and shape caps on untrusted workbook input (Category 1)
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_SECTORS = 400
DEFAULT_TOL = 1e-9


@dataclass(frozen=True)
class CoefficientTable:
    sheet: str
    codes: tuple[str, ...]
    names: tuple[str, ...]
    matrix: np.ndarray  # rows = supplying sector i, cols = using sector j


def read_sheets(path: Path, sheets: list[str]) -> dict[str, list[tuple]]:
    """
    Read the raw rows of the requested sheets (exact names) in one pass.
    Uses the value-only reader (cxsim.xlsx_lite): the ECOS workbooks carry a 7 MB styles part
    that openpyxl parses on every open (~12 s); values are identical (tested).
    """
    from cxsim import xlsx_lite

    path = Path(path)
    # [SECURE] Size cap before opening an untrusted archive (Category 1)
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Workbook missing or too large.")
    return xlsx_lite.read_sheets(path, sheets)


def sheet_names(path: Path) -> list[str]:
    from cxsim import xlsx_lite

    path = Path(path)
    if not path.is_file() or path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("Workbook missing or too large.")
    return xlsx_lite.sheet_names(path)


def read_coefficient_sheet(path: Path, sheet: str) -> CoefficientTable:
    """Read the square sector x sector block of one ECOS coefficient sheet."""
    return parse_coefficient_rows(read_sheets(path, [sheet])[sheet], sheet)


def parse_coefficient_rows(rows: list[tuple], sheet: str) -> CoefficientTable:
    header = rows[HEADER_CODE_ROW - 1]
    col_codes, col_idx = [], []
    for c in range(FIRST_DATA_COL - 1, len(header)):
        code = str(header[c]).strip() if header[c] is not None else ""
        if _SECTOR_CODE.fullmatch(code):
            col_codes.append(code)
            col_idx.append(c)
    row_codes, row_names, values = [], [], []
    for r in rows[FIRST_DATA_ROW - 1:]:
        code = str(r[0]).strip() if r and r[0] is not None else ""
        if not _SECTOR_CODE.fullmatch(code):
            continue
        row_codes.append(code)
        row_names.append(str(r[1]).strip() if len(r) > 1 and r[1] is not None else "")
        values.append([_number(r[c] if c < len(r) else None) for c in col_idx])

    if not row_codes or len(row_codes) > MAX_SECTORS:
        raise ValueError("Unexpected number of sector rows.")
    if row_codes != col_codes:
        raise ValueError("Row and column sector codes differ; the block is not square.")
    if len(set(row_codes)) != len(row_codes):
        raise ValueError("Duplicate sector code.")
    return CoefficientTable(sheet, tuple(row_codes), tuple(row_names), np.array(values, dtype=float))


def _number(v) -> float:
    if isinstance(v, (int, float)) and math.isfinite(v):
        return float(v)
    if isinstance(v, str):
        try:
            x = float(v.replace(",", ""))
        except ValueError:
            raise ValueError("Non-numeric coefficient cell.") from None
        if math.isfinite(x):
            return x
    raise ValueError("Missing or non-finite coefficient cell.")


def engine_inverse(coeff: np.ndarray) -> np.ndarray:
    """
    Leontief inverse computed THROUGH the engine (demand mode, lam = 1):
    column j = engine total impact of a unit final-demand shock on sector j.
    """
    A = np.asarray(coeff, dtype=float)  # A[target=i, source=j] = a_ij
    lam = 1.0
    rho = linear.spectral_radius(A, lam)
    if rho >= 1.0 - linear.STABILITY_TOL:
        raise linear.UnstableModelError(rho)
    n = A.shape[0]
    out = np.empty_like(A)
    for j in range(n):
        s = np.zeros(n)
        s[j] = 1.0
        out[:, j] = linear.total_impact(A, lam, s)
    return out


@dataclass(frozen=True)
class Gate1Result:
    file: str
    n_sectors: int
    codes: tuple[str, ...]
    sanity: dict
    candidates: dict           # name -> max abs error vs published inducement
    matched: str | None        # candidate within tol, None if none
    tol: float
    passed: bool


def gate1(path: Path, tol: float = DEFAULT_TOL) -> Gate1Result:
    published = read_coefficient_sheet(path, SHEET_INDUCEMENT)
    errors, tables = {}, {}
    for name, sheet in CANDIDATES.items():
        t = read_coefficient_sheet(path, sheet)
        if t.codes != published.codes:
            raise ValueError(f"{sheet}: sector codes differ from the inducement sheet.")
        tables[name] = t
        errors[name] = float(np.max(np.abs(engine_inverse(t.matrix) - published.matrix)))

    ad = tables["domestic_Ad"].matrix
    a_tot = tables["total_A"].matrix
    neg = np.argwhere(ad < 0.0)
    sanity = {
        "domestic_col_sum_max": float(ad.sum(axis=0).max()),     # must be < 1 (value added > 0)
        "total_col_sum_max": float(a_tot.sum(axis=0).max()),
        "domestic_le_total": bool(np.all(ad <= a_tot + 1e-12)),  # domestic share never exceeds total
        "inducement_diag_ge_1": bool(np.all(np.diag(published.matrix) >= 1.0 - 1e-12)),
        # Reported, not gated: the BOK records scrap/by-products as NEGATIVE inputs
        # (Stone method, 2020 benchmark report). They are legitimate, signed weights.
        "domestic_negative_cells": [
            {"from": published.codes[i], "to": published.codes[j], "value": float(ad[i, j])} for i, j in neg
        ],
        "domestic_min": float(ad.min()),
    }
    ok = [k for k, e in sorted(errors.items(), key=lambda kv: kv[1]) if e <= tol]
    matched = ok[0] if ok else None
    passed = (matched is not None and sanity["domestic_col_sum_max"] < 1.0
              and sanity["domestic_le_total"] and sanity["inducement_diag_ge_1"])
    return Gate1Result(Path(path).name, len(published.codes), published.codes, sanity, errors, matched, tol, passed)


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: file size cap, exact sheet names, sector-code whitelist, square/duplicate checks,
#     finite numeric cells only (Category 1)
#   - Unsafe deserialization: value-only XML reading, no formula evaluation, no macros (Category 5)
#   - Resource release: archive closed by context manager in xlsx_lite (Category 5)
#   - Runaway prevention: engine stability check before inversion (Category 1)
# Not Applied:
#   - [WARN] XML bomb hardening: openpyxl uses defusedxml only if installed; workbooks come from the
#     Bank of Korea and are hash-recorded, install defusedxml if untrusted workbooks are ever accepted
# --------------------------------------------------
