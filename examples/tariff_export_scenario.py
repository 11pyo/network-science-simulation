# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 11pyo
"""
Export-shock scenario without the web screen: how does a fall in one sector's exports propagate
through the Korean economy (Bank of Korea 2020 benchmark table, 33 sectors, domestic)?

    python examples/tariff_export_scenario.py --sector C12 --percent -10 --out result.csv

The shock is entered as a percent of the sector's 2020 domestic final demand (exports are part of
final demand). This is a scenario calculator, not a forecast.
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # also works from a clone without installing
from cxsim import io_scenario as sc  # noqa: E402


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sector", default="C12", help="sector code, e.g. C12 (transport equipment)")
    ap.add_argument("--percent", type=float, default=-10.0, help="change in %% of the 2020 final demand")
    ap.add_argument("--data", type=Path, default=sc.default_dir(), help="folder holding the Bank of Korea workbook")
    ap.add_argument("--out", type=Path, default=Path("scenario_result.csv"))
    a = ap.parse_args(argv)

    if a.data is None or not (a.data / sc.BENCHMARK_FILE).is_file():
        print("Bank of Korea table not found. Download it first:\n"
              "    python scripts/fetch_bok_io.py --years 2020 --levels large\n"
              f"(expected: {sc.BENCHMARK_FILE} in the data folder)")
        return 1
    try:
        tables = sc.load_tables(a.data)
    except (OSError, ValueError) as err:
        # [SECURE] Short reason only (Category 4)
        print(f"Could not load the table ({err}). Re-run scripts/fetch_bok_io.py so the file and its hash are recorded.")
        return 1
    if a.sector not in tables.codes:
        print(f"Unknown sector {a.sector}. Codes: {', '.join(tables.codes)}")
        return 2
    try:
        shock = sc.percent_to_trillion(tables, {a.sector: a.percent})
    except ValueError as e:
        # [SECURE] Short reason only (Category 4)
        print(f"Input rejected: {e}")
        return 2
    r = sc.run_scenario(tables, shock)

    # [SECURE] Context manager releases the output file (Category 5)
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sector", "name", "direct_trn_krw", "indirect_trn_krw", "total_trn_krw", "pct_of_2020_output"])
        for i, c in enumerate(r.codes):
            w.writerow([c, tables.names[i], f"{r.direct[i]:.4f}", f"{r.indirect[i]:.4f}",
                        f"{r.total[i]:.4f}", f"{r.pct_of_output[i]:.3f}"])
    top = sorted(range(len(r.codes)), key=lambda i: abs(r.total[i]), reverse=True)[:5]
    print(f"Shock: {a.sector} {a.percent:+.1f}% of 2020 final demand = {shock[a.sector]:+.2f} trillion KRW")
    print(f"Total output change: {r.total.sum():+.2f} trillion KRW"
          + (f" (multiplier {r.multiplier:.3f})" if r.multiplier is not None else ""))
    for i in top:
        print(f"  {r.codes[i]:4s} {tables.names[i][:20]:20s} {r.total[i]:+8.3f}  ({r.pct_of_output[i]:+.2f}% of output)")
    print(f"Written: {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: sector whitelist and bounded percent checked in cxsim (Category 1)
#   - Resource release: output file via context manager (Category 5)
# Not Applied:
#   - [WARN] Path Traversal: output path is chosen by the local user running the script
# --------------------------------------------------
