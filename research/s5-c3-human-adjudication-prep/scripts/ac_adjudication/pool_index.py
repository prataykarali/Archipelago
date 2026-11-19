"""Frozen pool loading and SHA-256 helpers for S5-C3 A/C adjudication."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .constants import SHA256_HEX_LENGTH


@dataclass(frozen=True)
class PoolEntry:
    """Single immutable candidate pair from the frozen 254-pair blinded pool."""

    pair_id: str
    query_id: str
    domain: str
    query_text: str
    passage_id: str
    doc_id: str
    chunk_id: str
    page_number: int
    passage_sha256: str
    passage_text: str | None = None


@dataclass(frozen=True)
class FrozenPool:
    """Indexed representation of the frozen blinded candidate pool."""

    version: str
    pool_sha256: str
    entries_by_pair_id: dict[str, PoolEntry]
    ordered_pair_ids: tuple[str, ...]

    @property
    def pair_count(self) -> int:
        """Return total number of candidate pairs in the pool."""
        return len(self.ordered_pair_ids)


def sha256_bytes(data: bytes) -> str:
    """Compute lowercase hexadecimal SHA-256 digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    """Compute lowercase hexadecimal SHA-256 digest of UTF-8 text."""
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    """Compute lowercase hexadecimal SHA-256 digest of a file."""
    return sha256_bytes(path.read_bytes())


def is_valid_sha256_hex(value: Any) -> bool:
    """Return True if value is a valid 64-character lowercase hex SHA-256 string."""
    if not isinstance(value, str) or len(value) != SHA256_HEX_LENGTH:
        return False
    return all(ch in "0123456789abcdef" for ch in value)


def load_frozen_pool(
    pool_path: Path,
    passage_texts: dict[str, str] | None = None,
) -> FrozenPool:
    """Load and index the frozen blinded candidate pool JSON.

    Args:
        pool_path: Path to `retrieval_query_pool_blinded.json`.
        passage_texts: Optional private mapping of `passage_id` -> canonical text.

    Returns:
        FrozenPool instance with deterministic pair ordering and SHA-256 digest.
    """
    raw_bytes = pool_path.read_bytes()
    pool_sha = sha256_bytes(raw_bytes)
    payload = json.loads(raw_bytes.decode("utf-8"))

    entries: dict[str, PoolEntry] = {}
    ordered: list[str] = []
    text_map = passage_texts or {}

    for query in payload["queries"]:
        qid = str(query["query_id"])
        domain = str(query.get("domain", ""))
        qtext = str(query.get("query_text", ""))
        for cand in query["candidates"]:
            pair_id = str(cand["pair_id"])
            passage_id = str(cand["candidate_passage_id"])
            entries[pair_id] = PoolEntry(
                pair_id=pair_id,
                query_id=qid,
                domain=domain,
                query_text=qtext,
                passage_id=passage_id,
                doc_id=str(cand.get("candidate_doc_id", "")),
                chunk_id=str(cand.get("candidate_chunk_id", "")),
                page_number=int(cand.get("candidate_page_number", 0)),
                passage_sha256=str(cand["passage_sha256"]),
                passage_text=text_map.get(passage_id),
            )
            ordered.append(pair_id)

    return FrozenPool(
        version=str(payload["version"]),
        pool_sha256=pool_sha,
        entries_by_pair_id=entries,
        ordered_pair_ids=tuple(ordered),
    )
