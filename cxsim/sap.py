"""
SAP where-used extract -> impact graph (dependency-graph evaluation).

Raw files keep SAP's own "uses" relation (user uses used). The impact
direction is the reverse: a change in `used` affects `user`. This module is
the ONLY place where that flip happens (design v2 section 2).

Raw files live outside the repository and outside Google Drive
(default: %LOCALAPPDATA%/nss-renewal-data/sap_extract/raw).
"""

from __future__ import annotations

import csv
import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import scipy.sparse as sp

logger = logging.getLogger(__name__)

# [SECURE] Fixed set of interpreted file names read by this module - no user-controlled paths (Category 1)
RAW_FILES = ("uses.csv", "objects.csv", "transports.csv", "labels.csv")
REQUIRED_FILES = ("uses.csv", "objects.csv", "transports.csv")
_MANIFEST_NAME = re.compile(r"^[a-z0-9_]{1,60}\.csv$")
USES_COLUMNS = ("user_type", "user_name", "used_type", "used_name", "source", "ref_kind")
OBJECT_COLUMNS = ("obj_type", "obj_name", "devclass", "created_on")
TRANSPORT_COLUMNS = ("trkorr", "as4date", "obj_type", "obj_name", "request_obj_count", "raw_pgmid", "raw_object")
LABEL_COLUMNS = ("case_id", "trkorr", "affected_type", "affected_name", "label_source", "label_date", "note")
VALID_SOURCES = frozenset({"D010TAB", "WBCROSSGT", "CROSS", "TSTC", "D010INC", "ENLFDIR"})
VALID_LABEL_SOURCES = frozenset({"card", "inquiry", "rework"})
# [SECURE] Row and field caps - prevents resource exhaustion from oversized extracts (Category 1)
MAX_ROWS = 2_000_000
MAX_FIELD_LEN = 200
_SAP_NAME = re.compile(r"^[A-Za-z0-9_/=\-\.%$]{1,120}$")
_SAP_TYPE = re.compile(r"^[A-Z0-9]{1,8}$")


def default_data_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        raise EnvironmentError("LOCALAPPDATA is not set; pass the data directory explicitly.")
    return Path(base) / "nss-renewal-data" / "sap_extract"


def node_id(obj_type: str, obj_name: str) -> str:
    """
    Deterministic, collision-resistant node id within the spec ID pattern:
    {type letter}_{sanitised lower-case name, first 28 chars}_{sha256("TYPE:NAME")[:6]}
    """
    t = _clean_type(obj_type)
    n = _clean_name(obj_name)
    letter = t[0].lower()
    if not letter.isalpha():
        letter = "o"
    slug = re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_")[:28] or "x"
    digest = hashlib.sha256(f"{t}:{n}".encode("utf-8")).hexdigest()[:6]
    return f"{letter}_{slug}_{digest}"


def _clean_type(v: str) -> str:
    v = (v or "").strip().upper()
    # [SECURE] Whitelist pattern for SAP object types (Category 1)
    if not _SAP_TYPE.fullmatch(v):
        raise ValueError("Invalid SAP object type.")
    return v


def _try_clean(obj_type: str, obj_name: str) -> tuple[str, str] | None:
    """
    (type, name) if both pass the whitelist, else None. Used where a non-matching
    row cannot be a graph node anyway (composite TADIR keys such as SUSH/SICF/TOBJ,
    stray names like 'Z>EBO'); callers COUNT these, they are never dropped silently.
    """
    try:
        return _clean_type(obj_type), _clean_name(obj_name)
    except ValueError:
        return None


def _clean_name(v: str) -> str:
    v = (v or "").strip()
    # [SECURE] Whitelist pattern for SAP object names (Category 1)
    if not _SAP_NAME.fullmatch(v):
        raise ValueError("Invalid SAP object name.")
    return v


def read_csv(path: Path, columns: tuple[str, ...]) -> list[dict[str, str]]:
    """Read a raw CSV with an exact header; rows are capped and fields length-checked."""
    rows: list[dict[str, str]] = []
    # [SECURE] Context manager guarantees file handle release (Category 5)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != columns:
            raise ValueError(f"{path.name}: unexpected header.")
        for i, row in enumerate(reader):
            # [SECURE] Row cap (Category 3)
            if i >= MAX_ROWS:
                raise ValueError(f"{path.name}: too many rows.")
            if any(len(v or "") > MAX_FIELD_LEN for v in row.values()):
                raise ValueError(f"{path.name}: field too long at row {i + 2}.")
            rows.append(row)
    return rows


def verify_manifest(raw_dir: Path) -> dict[str, str]:
    """
    Check SHA-256 of every CSV in raw_dir against MANIFEST.sha256 before use.
    Every CSV present must be listed, every listed file must exist, and the
    interpreted files this module reads (REQUIRED_FILES) must be present.
    """
    manifest = raw_dir / "MANIFEST.sha256"
    if not manifest.is_file():
        raise ValueError("MANIFEST.sha256 is missing.")
    expected: dict[str, str] = {}
    with manifest.open("r", encoding="utf-8") as f:
        for line in f:
            m = re.fullmatch(r"([0-9a-fA-F]{64})\s+\*?(\S+)\s*", line)
            # [SECURE] Only bare, whitelisted file names from the manifest - prevents path traversal (Category 1)
            if m and _MANIFEST_NAME.fullmatch(m.group(2)):
                expected[m.group(2)] = m.group(1).lower()
    present = {p.name for p in raw_dir.glob("*.csv")}
    unlisted = sorted(present - set(expected))
    if unlisted:
        raise ValueError(f"CSV files not listed in MANIFEST: {', '.join(unlisted)}")
    for name in REQUIRED_FILES:
        if name not in expected:
            raise ValueError(f"{name} is required but not listed in MANIFEST.")
    for name, digest in expected.items():
        p = raw_dir / name
        if not p.is_file():
            raise ValueError(f"{name} is listed in MANIFEST but missing.")
        h = hashlib.sha256()
        with p.open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        # [SECURE] Integrity check before parsing externally produced data (Category 5)
        if h.hexdigest() != digest:
            raise ValueError(f"{name}: SHA-256 does not match MANIFEST.")
    return expected


@dataclass
class ImpactGraph:
    """Directed graph in IMPACT direction: edge used -> user."""

    ids: list[str]
    labels: list[str]                      # "TYPE:NAME"
    devclass: list[str]                    # "" when unknown
    adjacency: sp.csr_matrix               # adjacency[source, target] = 1
    skipped: dict[str, int] = field(default_factory=dict)  # rows not usable as nodes, by reason
    index: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.index = {nid: i for i, nid in enumerate(self.ids)}

    @property
    def n(self) -> int:
        return len(self.ids)

    def in_degree(self) -> np.ndarray:
        return np.asarray(self.adjacency.sum(axis=0)).ravel()

    def id_of(self, obj_type: str, obj_name: str) -> str | None:
        """Node id if the object is in the graph; None for unknown or non-node names."""
        if _try_clean(obj_type, obj_name) is None:
            return None
        nid = node_id(obj_type, obj_name)
        return nid if nid in self.index else None


def build_impact_graph(uses: list[dict[str, str]], objects: list[dict[str, str]] | None = None) -> ImpactGraph:
    ids: list[str] = []
    labels: list[str] = []
    index: dict[str, int] = {}

    def add(t: str, n: str) -> int:
        t, n = _clean_type(t), _clean_name(n)
        nid = node_id(t, n)
        if nid not in index:
            index[nid] = len(ids)
            ids.append(nid)
            labels.append(f"{t}:{n}")
        elif labels[index[nid]] != f"{t}:{n}":
            # [SECURE] Detect hash-prefix collision instead of silently merging objects (Category 1)
            raise ValueError("Node id collision; lengthen the hash suffix.")
        return index[nid]

    src, dst = [], []
    skipped = {"uses_invalid_name": 0, "objects_invalid_name": 0, "uses_self_reference": 0}
    for r in uses:
        if r["source"] not in VALID_SOURCES:
            raise ValueError("Unknown uses source.")
        a, b = _try_clean(r["user_type"], r["user_name"]), _try_clean(r["used_type"], r["used_name"])
        if a is None or b is None:
            skipped["uses_invalid_name"] += 1
            continue
        user = add(*a)
        used = add(*b)
        if user == used:
            skipped["uses_self_reference"] += 1  # carries no cross-object impact
            continue
        # Flip: SAP "user uses used" -> impact edge used -> user.
        src.append(used)
        dst.append(user)

    pkg = [""] * len(ids)
    for o in objects or []:
        tn = _try_clean(o["obj_type"], o["obj_name"])
        if tn is None:
            skipped["objects_invalid_name"] += 1
            continue
        nid = node_id(*tn)
        if nid in index:
            pkg[index[nid]] = (o.get("devclass") or "").strip()[:30]

    n = len(ids)
    A = sp.csr_matrix((np.ones(len(src)), (src, dst)), shape=(n, n))
    A.sum_duplicates()
    A.data[:] = 1.0  # the same pair found by several sources collapses to one edge
    return ImpactGraph(ids=ids, labels=labels, devclass=pkg, adjacency=A, skipped=skipped)


def rework_labels(transports, window_days: int = 14, bulk_threshold: int = 50,
                  stats: dict | None = None) -> list[dict[str, str]]:
    """
    Proxy labels from transport history (design v2.1, limitation stated in every row):
    if request T2 is released within `window_days` after T1 and shares at least one
    object with T1, the OTHER objects in T2 are treated as affected by T1's change.
    Objects re-sent in T2 that were already in T1 are rework of the same object, not
    impact, and are excluded. Bulk requests (> bulk_threshold objects) are ignored.
    """
    from datetime import date, timedelta

    reqs: dict[str, dict] = {}
    for t in transports:
        tr = (t["trkorr"] or "").strip()
        if not re.fullmatch(r"[A-Z0-9]{4,20}", tr):
            raise ValueError("transports.csv: invalid trkorr.")
        d = (t["as4date"] or "").strip()
        if not re.fullmatch(r"\d{8}", d):
            raise ValueError("transports.csv: as4date must be YYYYMMDD.")
        if int(t["request_obj_count"]) > bulk_threshold:
            continue
        r = reqs.setdefault(tr, {"date": date(int(d[:4]), int(d[4:6]), int(d[6:])), "objs": set()})
        tn = _try_clean(t["obj_type"], t["obj_name"])
        if tn is None:
            if stats is not None:
                stats["transport_rows_invalid_name"] = stats.get("transport_rows_invalid_name", 0) + 1
            continue
        r["objs"].add(tn)

    order = sorted(reqs.items(), key=lambda kv: (kv[1]["date"], kv[0]))
    window = timedelta(days=window_days)
    out = []
    for i, (t1, r1) in enumerate(order):
        # [SECURE] Inner scan bounded by the sorted list and the time window (Category 3)
        for t2, r2 in order[i + 1:]:
            if r2["date"] - r1["date"] > window:
                break
            if not (r1["objs"] & r2["objs"]):
                continue
            for ot, on in sorted(r2["objs"] - r1["objs"]):
                out.append({
                    "case_id": f"rw_{t1}_{t2}", "trkorr": t1, "affected_type": ot, "affected_name": on,
                    "label_source": "rework", "label_date": r2["date"].strftime("%Y%m%d"),
                    "note": "proxy: follow-up request touching the same object within window; not an incident record",
                })
    return out


def write_id_map(graph: ImpactGraph, path: Path) -> None:
    """id_map.csv: node_id,type,name,devclass (derived output, stays outside the repo)."""
    _atomic_write_csv(
        path,
        ("node_id", "obj_type", "obj_name", "devclass"),
        ((nid, *lab.split(":", 1), pkg) for nid, lab, pkg in zip(graph.ids, graph.labels, graph.devclass)),
    )


def _atomic_write_csv(path: Path, header, rows) -> None:
    import tempfile

    fd, tmp = tempfile.mkstemp(prefix=f".{path.stem}.", suffix=".tmp", dir=path.parent)
    try:
        # [SECURE] Context manager + atomic replace - no partial files on failure (Category 3, 5)
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: exact CSV headers, whitelist patterns for SAP types/names, row and field caps (Category 1)
#   - Path traversal: only fixed raw file names inside a caller-given data directory (Category 1)
#   - Integrity: SHA-256 of raw files checked against MANIFEST before parsing (Category 5)
#   - Hash collision on node ids detected and rejected, never merged silently (Category 1)
#   - Resource release and atomic writes for derived files (Category 3, 5)
# Not Applied:
#   - [WARN] Sensitive data at rest: raw/derived files are plain CSV under the user profile; they contain
#     object names, not personal data. Encrypt the folder (EFS/BitLocker) if policy requires it
#   - [WARN] MANIFEST itself is not signed; it guards against corruption, not against a malicious local user
# --------------------------------------------------
