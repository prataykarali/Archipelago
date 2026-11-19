"""Loader for Corpus v3 JSONL passage metadata (no raw text exported)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .constants import HASH_READ_CHUNK_BYTES
from .schema import CorpusPassageMeta


def compute_file_sha256(path: Path) -> str:
    """Compute hex SHA-256 digest of a file."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_READ_CHUNK_BYTES), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_corpus_metadata(jsonl_path: Path) -> dict[str, CorpusPassageMeta]:
    """Load passage_id -> CorpusPassageMeta index from Corpus v3 JSONL."""
    index: dict[str, CorpusPassageMeta] = {}
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            passage_id = str(record["passage_id"])
            if passage_id in index:
                msg = f"Duplicate passage_id {passage_id} at line {line_no}"
                raise ValueError(msg)
            source_doc_id = str(record["source_doc_id"])
            page_start = int(record["page_start"])
            page_end = int(record["page_end"])
            passage_sha = str(
                record.get("passage_sha256")
                or record.get("normalized_sha256")
                or record.get("text_sha256")
                or ""
            )
            if not passage_sha:
                msg = f"Missing passage sha256 for {passage_id} at line {line_no}"
                raise ValueError(msg)
            index[passage_id] = CorpusPassageMeta(
                passage_id=passage_id,
                source_doc_id=source_doc_id,
                page_start=page_start,
                page_end=page_end,
                passage_sha256=passage_sha,
            )
    return index
