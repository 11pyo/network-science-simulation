"""
P1-industry gate 1: engine Leontief inverse == published production-inducement
coefficients, for each Bank of Korea workbook.

Usage:
    python scripts/p1_industry_gate1.py            # default %LOCALAPPDATA%/nss-renewal-data/io_bok
    python scripts/p1_industry_gate1.py --data-dir D:/somewhere/io_bok

Reads  <data-dir>/downloads/<fixed workbook names> (hashes checked against PROVENANCE_ecos_files.txt)
Writes <data-dir>/derived/gate1_report.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import tempfile
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cxsim import io_table  # noqa: E402

logger = logging.getLogger("p1_industry_gate1")

# [SECURE] Fixed workbook names - no user-controlled paths (Category 1)
WORKBOOKS = (
    "(표)(2020실측)투입산출표_생산자가격_통합대분류.xlsx",
    "(표)(2020실측)투입산출표_기초가격_통합대분류.xlsx",
    "2019_투입산출표_생산자가격_통합대분류.xlsx",
)
PROVENANCE = "PROVENANCE_ecos_files.txt"


def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(data_dir: Path, tol: float = io_table.DEFAULT_TOL) -> dict:
    dl, derived = data_dir / "downloads", data_dir / "derived"
    prov = (dl / PROVENANCE).read_text(encoding="utf-8")
    derived.mkdir(exist_ok=True)
    out = {"tol": tol, "results": []}
    for name in WORKBOOKS:
        p = dl / name
        digest = _sha256(p)
        # [SECURE] Integrity check against recorded provenance before parsing (Category 5)
        if digest not in prov:
            raise ValueError(f"{name}: SHA-256 not found in {PROVENANCE}.")
        res = asdict(io_table.gate1(p, tol=tol))
        res["sha256"] = digest
        out["results"].append(res)
    out["all_passed"] = all(r["passed"] for r in out["results"])
    fd, tmp = tempfile.mkstemp(prefix=".gate1.", suffix=".tmp", dir=derived)
    try:
        # [SECURE] Atomic write (Category 3, 5)
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        os.replace(tmp, derived / "gate1_report.json")
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise
    return out


def main(argv=None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(description="P1-industry gate 1")
    ap.add_argument("--data-dir", type=Path, default=None)
    args = ap.parse_args(argv)
    base = os.environ.get("LOCALAPPDATA")
    if args.data_dir is None and not base:
        logger.error("LOCALAPPDATA is not set; pass --data-dir.")
        return 2
    data_dir = (args.data_dir or Path(base) / "nss-renewal-data" / "io_bok").resolve()
    try:
        out = run(data_dir)
    except (ValueError, OSError) as e:
        # [SECURE] Short reason, no stack trace for expected input problems (Category 4)
        logger.error("Gate 1 stopped: %s", e)
        return 1
    for r in out["results"]:
        errs = ", ".join(f"{k}={v:.2e}" for k, v in r["candidates"].items())
        print(f"{r['file']}: n={r['n_sectors']} matched={r['matched']} passed={r['passed']} | max|err| {errs}")
        print(f"    sanity: {r['sanity']}")
    print(f"ALL PASSED: {out['all_passed']}")
    return 0 if out["all_passed"] else 3


if __name__ == "__main__":
    sys.exit(main())


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Path traversal: fixed workbook names inside the data directory (Category 1)
#   - Integrity: SHA-256 checked against the provenance record before parsing (Category 5)
#   - Error handling: expected failures give a short message and non-zero exit (Category 4)
#   - Atomic write of the report (Category 3)
# Not Applied:
#   - [WARN] Provenance file itself is not signed; it guards against corruption, not a malicious local user
# --------------------------------------------------
