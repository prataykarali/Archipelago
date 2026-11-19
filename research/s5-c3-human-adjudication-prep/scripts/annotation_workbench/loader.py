"""Read-only loader for the frozen 254-pair blinded pool and verified passage text."""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

from .constants import (
    DEFAULT_BLANK_WORKBOOK,
    DEFAULT_BLANK_WORKBOOK_BACKUP,
    DEFAULT_KUZU_DB_PATH,
    DEFAULT_POOL_JSON,
    EXCLUDED_CORPUS_PASSAGE_ID,
    EXPECTED_POOL_SHA256,
    FORBIDDEN_BLINDING_TOKENS,
)
from .models import CandidatePair, LoadedPool, content_hash, sha256_file

_WORKBOOK_PAIR_SPLIT_RE = re.compile(
    r"(?m)^### Candidate Pair `(S5B21-PAIR-\d+)`\s*$"
)
_WORKBOOK_TEXT_RE = re.compile(
    r"\*\*Candidate Passage Text:\*\*\n\n(.*?)\n\n\*\*Human Judgment Fields",
    re.DOTALL,
)


class PoolIntegrityError(RuntimeError):
    """Raised when the frozen pool or hydrated passage text fails integrity checks."""


def _strip_blockquote_prefix(raw_block: str) -> str:
    """Strip Markdown blockquote prefix without altering inner passage characters."""
    lines: list[str] = []
    for line in raw_block.splitlines():
        if line.startswith("> "):
            lines.append(line[2:])
        elif line.startswith(">"):
            lines.append(line[1:])
        else:
            lines.append(line)
    return "\n".join(lines)


def load_passages_from_markdown_workbook(workbook_path: Path) -> dict[str, str]:
    """Extract verbatim candidate passage text keyed by pair_id from a blank workbook."""
    if not workbook_path.exists():
        raise FileNotFoundError(f"Blank workbook not found: {workbook_path}")

    raw = workbook_path.read_text(encoding="utf-8").replace("\r\n", "\n")
    blocks = _WORKBOOK_PAIR_SPLIT_RE.split(raw)
    passages_by_pair: dict[str, str] = {}
    for idx in range(1, len(blocks), 2):
        pair_id = blocks[idx].strip()
        body = blocks[idx + 1]
        match = _WORKBOOK_TEXT_RE.search(body)
        if not match:
            raise PoolIntegrityError(
                f"Could not extract Candidate Passage Text for {pair_id} in {workbook_path}"
            )
        passages_by_pair[pair_id] = _strip_blockquote_prefix(match.group(1))
    return passages_by_pair


def load_passages_from_json(json_path: Path) -> dict[str, str]:
    """Load passage text mapping from a JSON file ({pair_id: text} or {passage_id: text})."""
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and "passages" in payload and isinstance(payload["passages"], dict):
        payload = payload["passages"]
    if not isinstance(payload, dict):
        raise PoolIntegrityError(
            f"Passage JSON must map pair_id/passage_id to text: {json_path}"
        )
    return {str(k): str(v) for k, v in payload.items()}


def load_passages_from_kuzu(db_path: Path) -> dict[str, str]:
    """Load canonical eligible corpus passage text keyed by passage_id from Kuzu."""
    from archipelago.eval.retrieval_baselines import (
        _is_index_only_passage,
        build_fixed_corpus_from_kuzu,
    )

    passages, _ = build_fixed_corpus_from_kuzu(str(db_path))
    return {
        p.passage_id: p.text
        for p in passages
        if not _is_index_only_passage(p.doc_id, p.section_title, p.text)
        and p.passage_id != EXCLUDED_CORPUS_PASSAGE_ID
    }


def _resolve_passage_lookup(
    passage_source: Path | None,
) -> tuple[dict[str, str], str]:
    """Resolve passage text lookup from explicit source or default private artifacts."""
    if passage_source is not None:
        if passage_source.suffix.lower() == ".json":
            return load_passages_from_json(passage_source), str(passage_source)
        if passage_source.suffix.lower() == ".md":
            return load_passages_from_markdown_workbook(passage_source), str(passage_source)
        return load_passages_from_kuzu(passage_source), str(passage_source)

    if DEFAULT_BLANK_WORKBOOK_BACKUP.exists():
        return (
            load_passages_from_markdown_workbook(DEFAULT_BLANK_WORKBOOK_BACKUP),
            str(DEFAULT_BLANK_WORKBOOK_BACKUP),
        )
    if DEFAULT_BLANK_WORKBOOK.exists():
        return (
            load_passages_from_markdown_workbook(DEFAULT_BLANK_WORKBOOK),
            str(DEFAULT_BLANK_WORKBOOK),
        )
    if DEFAULT_KUZU_DB_PATH.exists():
        return load_passages_from_kuzu(DEFAULT_KUZU_DB_PATH), str(DEFAULT_KUZU_DB_PATH)

    raise FileNotFoundError(
        "No canonical passage source found. Expected one of: "
        f"{DEFAULT_BLANK_WORKBOOK_BACKUP}, {DEFAULT_BLANK_WORKBOOK}, or {DEFAULT_KUZU_DB_PATH}."
    )


def assert_blinding_clean(text: str, context: str) -> None:
    """Raise PoolIntegrityError if any forbidden blinding token appears in UI/metadata."""
    lowered = text.lower()
    for token in FORBIDDEN_BLINDING_TOKENS:
        if token in lowered:
            raise PoolIntegrityError(
                f"Blinding violation in {context}: forbidden token {token!r} detected"
            )


def load_blinded_pool(
    *,
    pool_path: Path = DEFAULT_POOL_JSON,
    passage_source: Path | None = None,
    verify_canonical_pool_sha: bool = True,
) -> LoadedPool:
    """Load the frozen blinded pool and hydrate verified verbatim passage text.

    Strictly read-only: never modifies pool JSON or source passage text.
    """
    if not pool_path.exists():
        raise FileNotFoundError(f"Blinded pool JSON not found: {pool_path}")

    pool_sha = sha256_file(pool_path)
    if (
        verify_canonical_pool_sha
        and pool_path.resolve() == DEFAULT_POOL_JSON.resolve()
        and pool_sha != EXPECTED_POOL_SHA256
    ):
        raise PoolIntegrityError(
            f"Canonical pool SHA-256 mismatch: {pool_sha} != {EXPECTED_POOL_SHA256}"
        )

    raw_pool: dict[str, Any] = json.loads(pool_path.read_text(encoding="utf-8"))
    passage_lookup, resolved_source = _resolve_passage_lookup(passage_source)

    pairs: list[CandidatePair] = []
    seen_pair_ids: set[str] = set()
    query_order: list[str] = []

    for query_obj in raw_pool.get("queries", []):
        qid = str(query_obj["query_id"])
        domain = str(query_obj["domain"])
        query_text = str(query_obj["query_text"])
        if qid not in query_order:
            query_order.append(qid)

        assert_blinding_clean(f"{qid} {domain} {query_text}", f"query {qid}")

        for cand in query_obj.get("candidates", []):
            pair_id = str(cand["pair_id"])
            if pair_id in seen_pair_ids:
                raise PoolIntegrityError(f"Duplicate pair_id in pool: {pair_id}")
            seen_pair_ids.add(pair_id)

            passage_id = str(cand["candidate_passage_id"])
            expected_sha = str(cand["passage_sha256"])

            passage_text = passage_lookup.get(pair_id)
            if passage_text is None:
                passage_text = passage_lookup.get(passage_id)
            if passage_text is None:
                raise PoolIntegrityError(
                    f"Missing canonical passage text for {pair_id} ({passage_id}) "
                    f"in {resolved_source}"
                )

            actual_sha = content_hash(passage_text)
            if actual_sha != expected_sha:
                raise PoolIntegrityError(
                    f"Passage SHA-256 mismatch for {pair_id} ({passage_id}): "
                    f"computed {actual_sha} != expected {expected_sha}"
                )

            pairs.append(
                CandidatePair(
                    pair_id=pair_id,
                    pair_index=len(pairs) + 1,
                    presentation_order=int(cand["presentation_order"]),
                    query_id=qid,
                    domain=domain,
                    query_text=query_text,
                    candidate_passage_id=passage_id,
                    candidate_doc_id=str(cand["candidate_doc_id"]),
                    candidate_chunk_id=str(cand["candidate_chunk_id"]),
                    candidate_page_number=int(cand["candidate_page_number"]),
                    passage_sha256=expected_sha,
                    passage_text=passage_text,
                )
            )

    expected_total = int(raw_pool.get("total_candidate_pairs", len(pairs)))
    if len(pairs) != expected_total:
        raise PoolIntegrityError(
            f"Loaded pair count {len(pairs)} != declared total_candidate_pairs {expected_total}"
        )

    return LoadedPool(
        pool_path=pool_path,
        pool_version=str(raw_pool.get("version") or ""),
        pool_sha256=pool_sha,
        randomization_seed=int(raw_pool.get("randomization_seed", 0)),
        passage_source=resolved_source,
        pairs=tuple(pairs),
        pairs_by_id={pair.pair_id: pair for pair in pairs},
        query_order=tuple(query_order),
    )
