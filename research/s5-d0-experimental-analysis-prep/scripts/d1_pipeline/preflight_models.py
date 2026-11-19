"""Data models and pool loaders for S5-D1 preflight validation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from pathlib import Path
from typing import Any

from d1_pipeline.constants import PLACEHOLDER_ID_MARKERS


class PreflightError(ValueError):
    """Raised when S5-D1 preflight validation fails."""


@dataclass(frozen=True)
class PoolEntry:
    """Canonical blinded pool entry."""

    pair_id: str
    query_id: str
    passage_id: str
    passage_sha256: str | None


@dataclass
class PreflightFinding:
    """Single categorized validation error or warning."""

    category: str
    message: str


@dataclass
class PreflightResult:
    """Structured result of S5-D1 preflight validation."""

    passed: bool
    schema_mode: str
    is_synthetic: bool
    pool_version: str | None = None
    pool_sha256: str | None = None
    rankings_sha256: str | None = None
    gold_labels_sha256: str | None = None
    neg_control_sha256: str | None = None
    verified_negative_controls: list[str] = field(default_factory=list)
    reclassified_answerable_controls: list[str] = field(default_factory=list)
    excluded_negative_controls: list[str] = field(default_factory=list)
    negative_control_classifications: dict[str, str] = field(default_factory=dict)
    errors: list[PreflightFinding] = field(default_factory=list)
    warnings: list[PreflightFinding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return asdict(self)


def sha256_file(path: Path) -> str:
    """Compute hex SHA-256 digest of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_valid_human_id(value: Any) -> bool:
    """Return True if value is a non-empty, non-placeholder human identifier."""
    if not isinstance(value, str):
        return False
    cleaned = value.strip()
    if not cleaned:
        return False
    return cleaned.upper() not in PLACEHOLDER_ID_MARKERS


def load_pool_manifest(pool_path: Path) -> tuple[dict[str, PoolEntry], str, str, set[str]]:
    """Load pool index, version, SHA-256, and set of query IDs."""
    raw = pool_path.read_bytes()
    pool_sha = hashlib.sha256(raw).hexdigest()
    payload = json.loads(raw.decode("utf-8"))
    index: dict[str, PoolEntry] = {}
    query_ids: set[str] = set()
    for q in payload["queries"]:
        qid = q["query_id"]
        query_ids.add(qid)
        for cand in q["candidates"]:
            index[cand["pair_id"]] = PoolEntry(
                pair_id=cand["pair_id"],
                query_id=qid,
                passage_id=cand["candidate_passage_id"],
                passage_sha256=cand.get("passage_sha256"),
            )
    return index, payload["version"], pool_sha, query_ids
