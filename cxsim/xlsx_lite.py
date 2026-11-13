# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 11pyo
"""
Minimal, value-only .xlsx reader (standard library only).

Why: the ECOS workbooks carry a 7 MB styles.xml; openpyxl parses it on every open
(~12 s) although only cell values are needed. This reader skips styles entirely and
returns the same row tuples as openpyxl's iter_rows(values_only=True) for the cell
types used in these files (shared strings, inline strings, numbers, booleans).
Equality with openpyxl is covered by tests.
"""

from __future__ import annotations

import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
_CELL_REF = re.compile(r"^([A-Z]{1,3})(\d+)$")
# [SECURE] Caps on archive members - guards against zip bombs in untrusted workbooks (Category 1)
MAX_MEMBER_BYTES = 64 * 1024 * 1024
MAX_ROWS = 100_000
MAX_COLS = 2_000


def _read(z: zipfile.ZipFile, name: str) -> bytes:
    info = z.getinfo(name)
    if info.file_size > MAX_MEMBER_BYTES:
        raise ValueError("Workbook part too large.")
    return z.read(name)


def _col_index(letters: str) -> int:
    n = 0
    for ch in letters:
        n = n * 26 + (ord(ch) - 64)
    return n - 1


def _text(si: ET.Element) -> str:
    # Note: phonetic runs (rPh) would also be concatenated here, unlike openpyxl.
    # The ECOS workbooks contain none; revisit if such files are ever read (PM review N2).
    return "".join(t.text or "" for t in si.iter(f"{{{_NS['m']}}}t"))


def _number(s: str):
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    return float(s)


def _sheet_targets(z: zipfile.ZipFile) -> dict[str, str]:
    wb = ET.fromstring(_read(z, "xl/workbook.xml"))
    rels = ET.fromstring(_read(z, "xl/_rels/workbook.xml.rels"))
    by_id = {r.get("Id"): r.get("Target") for r in rels.iter(f"{{{_PKG_REL}}}Relationship")}
    out = {}
    for s in wb.iter(f"{{{_NS['m']}}}sheet"):
        target = by_id[s.get(f"{{{_REL_NS}}}id")]
        target = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
        out[s.get("name")] = target
    return out


def sheet_names(path: Path) -> list[str]:
    with zipfile.ZipFile(path) as z:
        return list(_sheet_targets(z))


def read_sheets(path: Path, sheets: list[str]) -> dict[str, list[tuple]]:
    """{sheet name: list of row tuples (None for empty cells)} for the requested sheets."""
    # [SECURE] Context manager closes the archive on every path (Category 5)
    with zipfile.ZipFile(path) as z:
        targets = _sheet_targets(z)
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            sst = ET.fromstring(_read(z, "xl/sharedStrings.xml"))
            shared = [_text(si) for si in sst.iter(f"{{{_NS['m']}}}si")]
        out = {}
        for name in sheets:
            if name not in targets:
                raise ValueError(f"Sheet not found: {name}")
            root = ET.fromstring(_read(z, targets[name]))
            rows: dict[int, dict[int, object]] = {}
            for row in root.iter(f"{{{_NS['m']}}}row"):
                if row.get("r") is None:
                    # [SECURE] Fail loudly instead of misplacing rows (PM review N1) (Category 4)
                    raise ValueError("Row without a reference (r) attribute is not supported.")
                r_idx = int(row.get("r")) - 1
                if r_idx >= MAX_ROWS:
                    raise ValueError("Too many rows.")
                cells = rows.setdefault(r_idx, {})
                for c in row.iter(f"{{{_NS['m']}}}c"):
                    m = _CELL_REF.match(c.get("r", ""))
                    if not m:
                        # [SECURE] The r attribute may be omitted by the spec; never drop values silently (N1)
                        raise ValueError("Cell without a valid reference (r) attribute is not supported.")
                    col = _col_index(m.group(1))
                    if col >= MAX_COLS:
                        raise ValueError("Too many columns.")
                    t = c.get("t")
                    v = c.find("m:v", _NS)
                    if t == "s" and v is not None:
                        cells[col] = shared[int(v.text)]
                    elif t == "inlineStr":
                        is_ = c.find("m:is", _NS)
                        cells[col] = _text(is_) if is_ is not None else None
                    elif t == "str" and v is not None:
                        cells[col] = v.text
                    elif t == "b" and v is not None:
                        cells[col] = v.text == "1"
                    elif v is not None and v.text is not None:
                        cells[col] = _number(v.text)
            if not rows:
                out[name] = []
                continue
            width = max((max(c) + 1 for c in rows.values() if c), default=0)
            n_rows = max(rows) + 1
            out[name] = [tuple(rows.get(i, {}).get(j) for j in range(width)) for i in range(n_rows)]
        return out


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Resource limits: per-part size cap, row/column caps (Category 1)
#   - Resource release: ZipFile closed via context manager (Category 5)
#   - Unsafe deserialization: XML parsed as data only; no formulas evaluated, no macros (Category 5)
# Not Applied:
#   - [WARN] XML entity-expansion hardening relies on the stdlib expat defaults (billion-laughs
#     protection in current Python); workbooks are hash-verified against provenance before use.
#     Install and switch to defusedxml if untrusted workbooks are ever accepted
# --------------------------------------------------
