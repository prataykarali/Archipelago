"""Frozen eligible corpus index and strict search/inspection engine.

Strictly restricts all search, document listing, passage inspection, and evidence
verification to the frozen eligible corpus (e.g., `s5a_eval_corpus_v1`). Any
index-only, invalid-page, or out-of-corpus document is explicitly excluded and
rejected on lookup or citation.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
import json
from pathlib import Path
import re
from typing import Any

from .constants import (
    DEFAULT_SEARCH_LIMIT,
    ELIGIBILITY_ELIGIBLE,
    ELIGIBILITY_EXCLUDED_INDEX_ONLY,
    ELIGIBILITY_EXCLUDED_INVALID_PAGE,
    ELIGIBILITY_EXCLUDED_MANIFEST,
    ELIGIBILITY_OUT_OF_CORPUS,
    EXCERPT_CONTEXT_CHARS,
    EXPECTED_CORPUS_PASSAGE_COUNT,
    EXPECTED_CORPUS_SHA256,
    FROZEN_CORPUS_VERSION,
    INVALID_PAGE_EXCLUDED_PASSAGE_ID,
    MAX_SEARCH_LIMIT,
    SEARCH_MODE_REGEX,
    SEARCH_MODE_SUBSTRING,
    SEARCH_MODE_TOKENS,
    TIER_PAPER_OR_UPLOAD_CHUNK,
    VALID_SEARCH_MODES,
)
from .corpus_models import (
    CorpusEligibilityError,
    EligiblePassage,
    SearchHit,
    SearchResult,
    compute_corpus_sha256,
    compute_text_sha256,
    derive_source_title,
    is_index_only_passage,
    load_provenance_tier_map,
)


class CorpusIndex:
    """Read-only index strictly restricted to the frozen eligible corpus."""

    def __init__(
        self,
        eligible_passages: Sequence[EligiblePassage],
        *,
        excluded_reasons: dict[str, str] | None = None,
        corpus_version: str = FROZEN_CORPUS_VERSION,
    ) -> None:
        self._passages: tuple[EligiblePassage, ...] = tuple(eligible_passages)
        self._by_id: dict[str, EligiblePassage] = {p.passage_id: p for p in self._passages}
        self._excluded_reasons: dict[str, str] = dict(excluded_reasons or {})
        self.corpus_version = corpus_version
        self.corpus_sha256 = compute_corpus_sha256(self._passages)
        self._doc_counts: Counter[str] = Counter(p.doc_id for p in self._passages)

    @property
    def passage_count(self) -> int:
        return len(self._passages)

    @property
    def document_count(self) -> int:
        return len(self._doc_counts)

    @property
    def excluded_count(self) -> int:
        return len(self._excluded_reasons)

    def get_eligibility_status(self, passage_id: str) -> str:
        """Return eligibility status for any passage_id."""
        if passage_id in self._by_id:
            return ELIGIBILITY_ELIGIBLE
        if passage_id in self._excluded_reasons:
            return self._excluded_reasons[passage_id]
        return ELIGIBILITY_OUT_OF_CORPUS

    def inspect_passage(self, passage_id: str) -> EligiblePassage:
        """Return an eligible passage or raise CorpusEligibilityError if excluded/absent."""
        if passage_id in self._by_id:
            return self._by_id[passage_id]
        status = self.get_eligibility_status(passage_id)
        raise CorpusEligibilityError(
            f"Passage '{passage_id}' is not in the frozen eligible corpus ({status}).",
            status=status,
        )

    def list_documents(self) -> list[dict[str, Any]]:
        """Return sorted inventory of all eligible documents and passage counts."""
        return [
            {
                "doc_id": doc_id,
                "source_title": derive_source_title(doc_id, ""),
                "passage_count": self._doc_counts[doc_id],
                "corpus_eligibility_status": ELIGIBILITY_ELIGIBLE,
            }
            for doc_id in sorted(self._doc_counts)
        ]

    def get_document_passages(self, doc_id: str) -> list[EligiblePassage]:
        """Return all eligible passages for a document, rejecting ineligible docs."""
        if doc_id not in self._doc_counts:
            raise CorpusEligibilityError(
                f"Document '{doc_id}' is not in the frozen eligible corpus.",
                status=ELIGIBILITY_OUT_OF_CORPUS,
            )
        return [p for p in self._passages if p.doc_id == doc_id]

    def search(
        self,
        query: str,
        *,
        mode: str = SEARCH_MODE_SUBSTRING,
        doc_id: str | None = None,
        limit: int = DEFAULT_SEARCH_LIMIT,
    ) -> SearchResult:
        """Search strictly within the frozen eligible corpus."""
        cleaned_query = query.strip()
        if not cleaned_query:
            raise ValueError("Search query must not be empty.")
        if mode not in VALID_SEARCH_MODES:
            raise ValueError(
                f"Unsupported search mode '{mode}'. Valid: {sorted(VALID_SEARCH_MODES)}"
            )
        if limit < 1 or limit > MAX_SEARCH_LIMIT:
            raise ValueError(f"Search limit must be between 1 and {MAX_SEARCH_LIMIT}.")
        if doc_id is not None and doc_id not in self._doc_counts:
            raise CorpusEligibilityError(
                f"Filter document '{doc_id}' is not in the frozen eligible corpus.",
                status=ELIGIBILITY_OUT_OF_CORPUS,
            )

        candidates = (
            [p for p in self._passages if p.doc_id == doc_id]
            if doc_id is not None
            else list(self._passages)
        )
        compiled_regex: re.Pattern[str] | None = None
        tokens: list[str] = []
        if mode == SEARCH_MODE_REGEX:
            try:
                compiled_regex = re.compile(cleaned_query, re.IGNORECASE)
            except re.error as exc:
                raise ValueError(f"Invalid regular expression: {exc}") from exc
        elif mode == SEARCH_MODE_TOKENS:
            tokens = [tok.lower() for tok in re.findall(r"\S+", cleaned_query)]

        hits: list[SearchHit] = []
        lower_query = cleaned_query.lower()
        for passage in candidates:
            match_count, span_start, span_end = _match_passage(
                passage.text,
                mode=mode,
                lower_query=lower_query,
                tokens=tokens,
                compiled_regex=compiled_regex,
            )
            if match_count <= 0:
                continue
            excerpt = _extract_context_excerpt(passage.text, span_start, span_end)
            hits.append(
                SearchHit(
                    passage_id=passage.passage_id,
                    doc_id=passage.doc_id,
                    source_title=passage.source_title,
                    content_sha256=passage.content_sha256,
                    chunk_id=passage.chunk_id,
                    page_number=passage.page_number,
                    corpus_eligibility_status=passage.corpus_eligibility_status,
                    provenance_tier=passage.provenance_tier,
                    matched_excerpt=excerpt,
                    full_text=passage.text,
                    match_count=match_count,
                )
            )

        hits.sort(key=lambda h: (-h.match_count, h.passage_id))
        return SearchResult(
            query_used=cleaned_query,
            mode=mode,
            doc_filter=doc_id,
            corpus_version=self.corpus_version,
            corpus_sha256=self.corpus_sha256,
            total_hits=len(hits),
            hits=tuple(hits[:limit]),
        )

    def verify_evidence_citation(
        self,
        passage_id: str,
        verbatim_excerpt: str,
        *,
        expected_passage_sha256: str | None = None,
    ) -> EligiblePassage:
        """Verify that a cited passage is eligible and contains the exact verbatim excerpt."""
        passage = self.inspect_passage(passage_id)
        if expected_passage_sha256 and passage.content_sha256 != expected_passage_sha256:
            raise ValueError(
                f"Passage SHA-256 mismatch for '{passage_id}': "
                f"expected '{expected_passage_sha256}', canonical is '{passage.content_sha256}'."
            )
        if not verbatim_excerpt or not verbatim_excerpt.strip():
            raise ValueError(f"Verbatim excerpt must be non-empty for '{passage_id}'.")
        if verbatim_excerpt not in passage.text:
            raise ValueError(
                f"Verbatim excerpt is not an exact substring of canonical passage '{passage_id}'."
            )
        return passage

    @classmethod
    def from_raw_records(
        cls,
        raw_records: Sequence[dict[str, Any]],
        *,
        corpus_version: str = FROZEN_CORPUS_VERSION,
        allowed_doc_ids: frozenset[str] | None = None,
        provenance_tier_map: dict[str, str] | None = None,
        expected_sha256: str | None = None,
        expected_count: int | None = None,
    ) -> CorpusIndex:
        """Build a strictly filtered CorpusIndex from raw passage dictionaries."""
        tier_map = provenance_tier_map or {}
        eligible: list[EligiblePassage] = []
        excluded: dict[str, str] = {}

        for rec in raw_records:
            pid = str(rec["passage_id"])
            doc_id = str(rec["doc_id"])
            chunk_id = str(rec.get("chunk_id") or pid.split("::", maxsplit=1)[-1])
            page_number = int(rec.get("page_number", 0))
            section_title = str(rec.get("section_title") or "")
            text = str(rec.get("text") or "")
            content_sha = str(rec.get("content_sha256") or compute_text_sha256(text))

            explicit_status = str(rec.get("corpus_eligibility_status") or "").strip()
            if explicit_status and explicit_status != ELIGIBILITY_ELIGIBLE:
                excluded[pid] = explicit_status
                continue
            if pid == INVALID_PAGE_EXCLUDED_PASSAGE_ID:
                excluded[pid] = ELIGIBILITY_EXCLUDED_INVALID_PAGE
                continue
            if is_index_only_passage(doc_id, section_title, text):
                excluded[pid] = ELIGIBILITY_EXCLUDED_INDEX_ONLY
                continue
            if allowed_doc_ids is not None and doc_id not in allowed_doc_ids:
                excluded[pid] = ELIGIBILITY_EXCLUDED_MANIFEST
                continue

            eligible.append(
                EligiblePassage(
                    passage_id=pid,
                    doc_id=doc_id,
                    chunk_id=chunk_id,
                    page_number=page_number,
                    section_title=section_title,
                    text=text,
                    content_sha256=content_sha,
                    source_title=str(
                        rec.get("source_title") or derive_source_title(doc_id, section_title)
                    ),
                    provenance_tier=str(
                        rec.get("provenance_tier")
                        or tier_map.get(pid, TIER_PAPER_OR_UPLOAD_CHUNK)
                    ),
                    corpus_eligibility_status=ELIGIBILITY_ELIGIBLE,
                )
            )

        index = cls(eligible, excluded_reasons=excluded, corpus_version=corpus_version)
        if expected_count is not None and index.passage_count != expected_count:
            raise RuntimeError(
                f"Frozen corpus passage count mismatch: got {index.passage_count}, "
                f"expected {expected_count}."
            )
        if expected_sha256 is not None and index.corpus_sha256 != expected_sha256:
            raise RuntimeError(
                f"Frozen corpus SHA-256 mismatch: got {index.corpus_sha256}, "
                f"expected {expected_sha256}."
            )
        return index

    @classmethod
    def from_json(
        cls,
        json_path: Path,
        *,
        manifest_path: Path | None = None,
        provenance_registry_path: Path | None = None,
        expected_sha256: str | None = None,
        expected_count: int | None = None,
    ) -> CorpusIndex:
        """Load CorpusIndex from a JSON fixture or snapshot (supports list or dict wrapper)."""
        payload = json.loads(json_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            raw_records = payload
            corpus_version = FROZEN_CORPUS_VERSION
        elif isinstance(payload, dict) and isinstance(payload.get("passages"), list):
            raw_records = payload["passages"]
            corpus_version = str(payload.get("corpus_version") or FROZEN_CORPUS_VERSION)
        else:
            raise ValueError(f"Unsupported corpus JSON structure in '{json_path}'.")

        allowed_docs: frozenset[str] | None = None
        if manifest_path is not None and manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(manifest.get("documents"), dict):
                allowed_docs = frozenset(str(k) for k in manifest["documents"])

        tier_map = load_provenance_tier_map(provenance_registry_path)
        return cls.from_raw_records(
            raw_records,
            corpus_version=corpus_version,
            allowed_doc_ids=allowed_docs,
            provenance_tier_map=tier_map,
            expected_sha256=expected_sha256,
            expected_count=expected_count,
        )

    @classmethod
    def from_kuzu(
        cls,
        db_path: Path,
        *,
        manifest_path: Path | None = None,
        provenance_registry_path: Path | None = None,
        verify_frozen_hash: bool = True,
    ) -> CorpusIndex:
        """Load the frozen eligible corpus directly from canonical Kuzu `okf_graph.db`."""
        if not db_path.exists():
            raise FileNotFoundError(
                f"Kuzu database not found at '{db_path}'. Pass --db-path or --corpus-json."
            )
        from archipelago.eval.retrieval_baselines import build_fixed_corpus_from_kuzu

        passages, _ = build_fixed_corpus_from_kuzu(str(db_path))
        raw_records = [p.to_dict() for p in passages]

        allowed_docs: frozenset[str] | None = None
        if manifest_path is not None and manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if isinstance(manifest.get("documents"), dict):
                allowed_docs = frozenset(str(k) for k in manifest["documents"])

        tier_map = load_provenance_tier_map(provenance_registry_path)
        return cls.from_raw_records(
            raw_records,
            corpus_version=FROZEN_CORPUS_VERSION,
            allowed_doc_ids=allowed_docs,
            provenance_tier_map=tier_map,
            expected_sha256=EXPECTED_CORPUS_SHA256 if verify_frozen_hash else None,
            expected_count=EXPECTED_CORPUS_PASSAGE_COUNT if verify_frozen_hash else None,
        )


def _match_passage(
    text: str,
    *,
    mode: str,
    lower_query: str,
    tokens: Sequence[str],
    compiled_regex: re.Pattern[str] | None,
) -> tuple[int, int, int]:
    """Return (match_count, first_span_start, first_span_end) for a passage."""
    if mode == SEARCH_MODE_SUBSTRING:
        lower_text = text.lower()
        first = lower_text.find(lower_query)
        if first < 0:
            return (0, 0, 0)
        return (lower_text.count(lower_query), first, first + len(lower_query))

    if mode == SEARCH_MODE_TOKENS:
        lower_text = text.lower()
        total = 0
        first_pos = len(text)
        first_len = 0
        for tok in tokens:
            pos = lower_text.find(tok)
            if pos < 0:
                return (0, 0, 0)
            total += lower_text.count(tok)
            if pos < first_pos:
                first_pos = pos
                first_len = len(tok)
        return (total, first_pos, first_pos + first_len)

    assert compiled_regex is not None
    matches = list(compiled_regex.finditer(text))
    if not matches:
        return (0, 0, 0)
    first_match = matches[0]
    return (len(matches), first_match.start(), first_match.end())


def _extract_context_excerpt(text: str, start: int, end: int) -> str:
    """Return an exact verbatim substring surrounding [start, end]."""
    lo = max(0, start - EXCERPT_CONTEXT_CHARS)
    hi = min(len(text), end + EXCERPT_CONTEXT_CHARS)
    return text[lo:hi]
