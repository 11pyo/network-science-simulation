"""
Declarative model specification (replaces the per-preset Python modules).

A model is a directed, signed influence graph. Every edge weight and the
node self-decay are given as ranges [low, high] rather than point values,
together with an evidence grade, so uncertainty is explicit from the start.

Fixed definitions (agreed design v2, section 2):

- Edge direction: an edge `source -> target` ALWAYS means "a change in
  `source` affects `target`". For SAP where-used data ("X uses Y") the
  edge must be written Y -> X. Converters own this flip, never the engine.
- Linear engine update: x[t+1] = (1 - lam) * x[t] + A @ x[t] + u[t],
  with A[target, source] = weight and lam = self_decay.
  Stability requires spectral_radius((1 - lam) I + A) < 1.
  Sufficient check (Gershgorin): incoming |weight| sum of every node < lam.
- DebtRank engine accepts only non-negative weights in [0, 1]; a signed
  spec is rejected by that engine at run time.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

# [SECURE] Strict ID pattern - whitelist of characters for node IDs (Category 1)
NODE_ID_PATTERN = r"^[a-z][a-z0-9_]{0,39}$"
MAX_NODES = 20000
MAX_EDGES = 200000
# [SECURE] Size cap on spec files - prevents resource exhaustion from huge inputs (Category 1)
MAX_SPEC_BYTES = 512 * 1024

EvidenceGrade = Literal["A", "B", "C", "D", "legacy"]


class Range(BaseModel):
    """Closed interval [low, high] used for every uncertain parameter."""

    # [SECURE] Reject unknown fields - prevents silent acceptance of malformed input (Category 1)
    model_config = ConfigDict(extra="forbid", frozen=True)

    low: float = Field(ge=-1.0, le=1.0)
    high: float = Field(ge=-1.0, le=1.0)

    @model_validator(mode="after")
    def _ordered(self) -> "Range":
        if self.low > self.high:
            raise ValueError("Range low must not exceed high.")
        return self

    @property
    def mid(self) -> float:
        return (self.low + self.high) / 2.0


class NodeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(pattern=NODE_ID_PATTERN)
    label: str = Field(min_length=1, max_length=60)
    group: str | None = Field(default=None, max_length=40)
    color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    # Economic value used by DebtRank to weight distress (normalised to shares).
    value: float = Field(default=1.0, ge=0.0, le=1e12)


class EdgeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    source: str = Field(pattern=NODE_ID_PATTERN)
    target: str = Field(pattern=NODE_ID_PATTERN)
    weight: Range
    evidence: EvidenceGrade = "D"
    note: str = Field(default="", max_length=300)

    @model_validator(mode="after")
    def _no_self_loop(self) -> "EdgeSpec":
        if self.source == self.target:
            raise ValueError("Self loops are not allowed; use self_decay instead.")
        return self


class Sampling(BaseModel):
    """How parameter ranges are sampled; fixed seed makes runs reproducible."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    distribution: Literal["uniform"] = "uniform"
    seed: int = Field(default=20261112, ge=0, le=2**32 - 1)


class ModelSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=2000)
    legacy: bool = False
    # Declared weight normalization. "legacy_in_strength" means the original
    # undirected correlations were rescaled so every node's incoming |weight|
    # sum stays below 0.9 * self_decay.low; weights then mean "share of
    # influence", not correlation.
    normalization: Literal["none", "legacy_in_strength"] = "none"
    sampling: Sampling = Sampling()
    # Design v2.1: spectral radius only guarantees convergence, not size. A run whose
    # max |impact| exceeds this multiple of the total |shock| is rejected as explosive.
    max_amplification: float = Field(default=1000.0, gt=1.0, le=1e9)
    # Share of its own deviation a node loses each step (linear engine).
    self_decay: Range
    nodes: tuple[NodeSpec, ...] = Field(min_length=2, max_length=MAX_NODES)
    edges: tuple[EdgeSpec, ...] = Field(max_length=MAX_EDGES)

    @field_validator("self_decay")
    @classmethod
    def _decay_positive(cls, v: Range) -> Range:
        if v.low <= 0.0:
            raise ValueError("self_decay must be strictly positive.")
        return v

    @model_validator(mode="after")
    def _consistent(self) -> "ModelSpec":
        ids = [n.id for n in self.nodes]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate node id.")
        known = set(ids)
        seen = set()
        for e in self.edges:
            # [SECURE] Edges may only reference declared nodes - whitelist check (Category 1)
            if e.source not in known or e.target not in known:
                raise ValueError("Edge references an undeclared node.")
            key = (e.source, e.target)
            if key in seen:
                raise ValueError("Duplicate edge.")
            seen.add(key)
        return self

    @property
    def node_ids(self) -> list[str]:
        # [SECURE] Return a new list - prevents mutation of internal state (Category 6)
        return [n.id for n in self.nodes]

    def index(self) -> dict[str, int]:
        return {nid: i for i, nid in enumerate(self.node_ids)}


def load_spec(name: str, base_dir: Path) -> ModelSpec:
    """
    Load a model spec by bare file stem from a fixed directory.

    Only names that resolve to `<base_dir>/<name>.yaml` are accepted.
    """
    # [SECURE] Bare-name whitelist pattern - prevents path traversal (Category 1)
    if not isinstance(name, str) or not _is_safe_stem(name):
        raise ValueError("Invalid scenario name.")
    base = base_dir.resolve()
    path = (base / f"{name}.yaml").resolve()
    # [SECURE] Resolved path must stay inside base_dir - prevents path traversal (Category 1)
    if path.parent != base or not path.is_file():
        raise ValueError("Scenario not found.")
    if path.stat().st_size > MAX_SPEC_BYTES:
        raise ValueError("Scenario file too large.")
    # [SECURE] Context manager guarantees file handle release (Category 5)
    with path.open("r", encoding="utf-8") as f:
        # [SECURE] safe_load only - prevents unsafe deserialization of YAML tags (Category 5)
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError("Scenario file must contain a mapping.")
    return ModelSpec.model_validate(raw)


def list_specs(base_dir: Path) -> list[str]:
    """Return available scenario stems in base_dir (sorted)."""
    base = base_dir.resolve()
    if not base.is_dir():
        return []
    return sorted(p.stem for p in base.glob("*.yaml") if _is_safe_stem(p.stem))


def _is_safe_stem(name: str) -> bool:
    import re

    return re.fullmatch(r"[a-z0-9_]{1,60}", name) is not None


# --------------------------------------------------
# Security Checklist
# Applied:
#   - Input validation: pydantic schema with extra="forbid", ID regex, value bounds, size caps (Category 1)
#   - Path traversal: bare-stem whitelist plus resolved-parent check in load_spec (Category 1)
#   - Unsafe deserialization: yaml.safe_load only, result re-validated by schema (Category 5)
#   - Resource release: file opened with context manager (Category 5)
#   - Encapsulation: frozen models, node_ids returns a new list (Category 6)
# Not Applied:
#   - [WARN] Authentication/authorization: not applicable - local file-based specs, no user accounts
#   - [WARN] Integrity signature on spec files: specs are repo-controlled; add HMAC/signing if specs are ever uploaded by users
# --------------------------------------------------
