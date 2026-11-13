# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 11pyo
"""
Download Bank of Korea input-output tables (producer prices) without a browser.

    python scripts/fetch_bok_io.py --years 2020 --levels large            # what the calculator needs
    python scripts/fetch_bok_io.py --years 2015-2024 --levels medium,small --out D:/io

UNOFFICIAL: this uses the file service behind the ECOS website (https://ecos.bok.or.kr), not the
Bank of Korea's official Open API. It may change without notice. One request per second.
Existing files are never overwritten. Each new file's SHA-256 is appended to a provenance record,
which the calculator checks before reading a workbook.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ENDPOINT = "https://ecos.bok.or.kr/serviceEndpoint/httpService/request.json"
DOWNLOAD = "https://ecos.bok.or.kr/serviceEndpoint/fileDownload?"
# ECOS statistic nodes that offer the yearly input-output files
NODES = {2015: "271Y005", 2016: "271Y004", 2017: "271Y003", 2018: "271Y002", 2019: "271Y001",
         2020: "271Y105", 2021: "271Y104", 2022: "271Y103", 2023: "271Y102", 2024: "271Y101"}
LEVELS = {"large": "통합대분류", "medium": "통합중분류", "small": "통합소분류", "basic": "기본부문"}
TIMEOUT = 60                      # [SECURE] Every network call has a timeout (Category 3)
MAX_BYTES = 80 * 1024 * 1024      # [SECURE] Size cap for one downloaded file (Category 1)


def call(trx: str, data: dict) -> dict:
    head = {"guidSeq": 1, "trxCd": trx, "scrId": "IECOSPC", "sysCd": "03", "fstChnCd": "WEB", "langDvsnCd": "KO",
            "envDvsnCd": "D", "sndRspnDvsnCd": "S", "sndDtm": datetime.now().strftime("%Y%m%d"),
            "ipAddr": "0.0.0.0", "usrId": "IECOSPC", "pageNum": 1, "pageCnt": 1000}
    req = urllib.request.Request(ENDPOINT, data=json.dumps({"header": head, "data": data}).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0",
                                          "Referer": "https://ecos.bok.or.kr/"})
    # [SECURE] Fixed HTTPS host with certificate verification left on (Category 2)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        res = json.loads(r.read().decode("utf-8"))
    time.sleep(1.0)
    return res.get("data") or {}


def parse_years(text: str) -> list[int]:
    out: list[int] = []
    for part in text.split(","):
        if "-" in part:
            a, b = (int(x) for x in part.split("-"))
            out.extend(range(a, b + 1))
        else:
            out.append(int(part))
    bad = [y for y in out if y not in NODES]
    if bad:
        raise ValueError(f"No table offered for {bad}; available {min(NODES)}-{max(NODES)}.")
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--years", default="2020")
    ap.add_argument("--levels", default="large", help="comma list of: " + ", ".join(LEVELS))
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    ap.add_argument("--out", type=Path, default=Path(base) / "nss-renewal-data" / "io_bok" / "downloads")
    ap.add_argument("--provenance", default="PROVENANCE_ecos_files.txt")
    a = ap.parse_args(argv)
    try:
        years = parse_years(a.years)
        levels = [LEVELS[x.strip()] for x in a.levels.split(",")]
    except (ValueError, KeyError) as e:
        print(f"Bad argument: {e}")
        return 2
    a.out.mkdir(parents=True, exist_ok=True)
    lines, bad = [], 0
    for y in years:
        ds = NODES[y]
        for item in call("OSUUA01R02", {"dsId": ds, "fileOfrYn": "Y"}).get("statClfItmList", []):
            codes = call("OSUUA01R03", dict(item, dsId=ds, fileOfrYn="Y")).get("statClfItmCdList", [])
            name = {c["cd"]: c["cdNm"] for c in codes}
            up = {c["cd"]: c["uppCd"] for c in codes}
            for c in codes:
                if (c["cdNm"] not in levels or name.get(c["uppCd"]) != "생산자가격"
                        or name.get(up.get(c["uppCd"], "")) != "투입산출표"):
                    continue
                res = call("OSDFA01R03", dict(c, dsId=ds, statItmId=item["statItmId"], langCd="KO"))
                fp, fn = res.get("attFilePath"), res.get("attFileNm")
                if not fp or not fn:
                    print(f"no file offered: {y} {c['cdNm']}")
                    bad += 1
                    continue
                # [SECURE] Server-supplied file name reduced to its base name - no path traversal (Category 1)
                safe = os.path.basename(fn.replace("\\", "/"))
                dst = a.out / safe
                if dst.exists():
                    print(f"exists, kept: {safe}")
                    continue
                url = DOWNLOAD + urllib.parse.urlencode({"filePath": fp, "fileName": fn})
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": "https://ecos.bok.or.kr/"})
                with urllib.request.urlopen(req, timeout=TIMEOUT * 2) as r:
                    blob = r.read(MAX_BYTES + 1)
                time.sleep(1.0)
                # [SECURE] Accept only a plausible xlsx container (Category 1)
                if len(blob) > MAX_BYTES or len(blob) < 20000 or blob[:4] != b"PK\x03\x04":
                    print(f"rejected (not an xlsx or odd size {len(blob)}): {safe}")
                    bad += 1
                    continue
                tmp = dst.with_name(dst.name + ".part")
                tmp.write_bytes(blob)
                os.replace(tmp, dst)      # [SECURE] Atomic placement (Category 3)
                digest = hashlib.sha256(blob).hexdigest()
                when = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                lines.append(f"- file: {safe}\n  size_bytes: {len(blob)}\n  sha256: {digest}\n  downloaded_at_utc: {when}\n"
                             f"  source: ECOS file service, node {ds}, item {c['cd']}\n")
                print(f"OK {len(blob):>9} bytes  {safe}")
    if lines:
        # [SECURE] Append-only provenance record (Category 3, 5)
        with open(a.out / a.provenance, "a", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
    print(f"done: {len(lines)} new file(s) in {a.out}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

# --------------------------------------------------
# Security Checklist
# Applied:
#   - Network: fixed HTTPS host, certificate verification on, timeouts, bounded reads, 1 s pacing (Category 2, 3)
#   - Untrusted downloads: size cap, zip magic check, base-name only, atomic write, never overwrite (Category 1, 3)
#   - Integrity: SHA-256 appended to the provenance record the calculator checks (Category 5)
# Not Applied:
#   - [WARN] Code Download Without Integrity Check: the publisher offers no checksum; authenticity rests on HTTPS
#   - [WARN] Undocumented web endpoint: request format may change without notice
# --------------------------------------------------
