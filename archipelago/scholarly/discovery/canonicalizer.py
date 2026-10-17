"""Canonicalization & Deduplication Engine.

Merges multi-source candidate records into authoritative canonical paper objects
using exact identifier matching and conservative title/author normalization.
"""

from __future__ import annotations

import logging
import re
from typing import Any
import uuid

from archipelago.scholarly.contracts.okf_models import (
    PaperIdentifiers,
    PaperRecord,
)

logger = logging.getLogger("archipelago.scholarly.canonicalizer")


def normalize_title(title: str) -> str:
    """Normalize paper title for fuzzy token comparison."""
    clean = re.sub(r"[^\w\s]", "", title.lower())
    return " ".join(clean.split())


class Canonicalizer:
    """Multi-source canonicalizer with conservative merging rules."""

    def __init__(self, title_threshold: float = 0.90):
        self.title_threshold = title_threshold

    def canonicalize_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate and merge a list of discovered candidate dictionaries.

        Returns merged unified objects with consolidated identifiers,
        provenance links, and canonical paper records.
        """
        canonical_pool: list[dict[str, Any]] = []

        for candidate in candidates:
            match_index, signals = self._find_match(candidate, canonical_pool)
            if match_index is not None:
                # Merge into existing canonical record
                canonical_pool[match_index] = self._merge_records(
                    canonical_pool[match_index], candidate, signals
                )
            else:
                # Add as a new canonical record
                candidate_copy = dict(candidate)
                candidate_copy["paper"] = candidate["paper"].model_copy(deep=True)
                candidate_copy["merge_history"] = []
                candidate_copy["identity_review"] = self._possible_matches(
                    candidate, canonical_pool
                )
                candidate_copy["paper"].paper_id = self._stable_id(candidate_copy)
                canonical_pool.append(candidate_copy)

        return canonical_pool

    def _find_match(
        self, candidate: dict[str, Any], pool: list[dict[str, Any]]
    ) -> tuple[int | None, dict[str, Any]]:
        """Merge only exact identifiers with no conflicting known identifier."""
        cand_paper: PaperRecord = candidate["paper"]
        cand_ids = cand_paper.identifiers
        for idx, existing in enumerate(pool):
            exist_paper: PaperRecord = existing["paper"]
            exist_ids = exist_paper.identifiers

            if self._conflicting_ids(cand_ids, exist_ids):
                continue
            # Rule 1: Exact DOI match
            if (
                cand_ids.doi
                and exist_ids.doi
                and cand_ids.doi.lower().strip() == exist_ids.doi.lower().strip()
            ):
                return idx, {
                    "decision": "merge",
                    "reason": "exact_doi_match",
                    "doi": cand_ids.doi,
                }

            # Rule 2: Exact arXiv ID match
            if cand_ids.arxiv_id and exist_ids.arxiv_id:
                clean_cand_arx = re.sub(r"v\d+$", "", cand_ids.arxiv_id.lower().strip())
                clean_exist_arx = re.sub(r"v\d+$", "", exist_ids.arxiv_id.lower().strip())
                if clean_cand_arx == clean_exist_arx:
                    return idx, {
                        "decision": "merge",
                        "reason": "exact_arxiv_match",
                        "arxiv_id": clean_cand_arx,
                    }

        return None, {}

    @staticmethod
    def _conflicting_ids(left: PaperIdentifiers, right: PaperIdentifiers) -> bool:
        """Reject a merge when an identifier type has two different values."""
        for name in ("doi", "arxiv_id", "openalex_id", "semantic_scholar_id"):
            a, b = getattr(left, name), getattr(right, name)
            if not a or not b or a.lower().strip() == b.lower().strip():
                continue
            if name != "arxiv_id" or re.sub(r"v\d+$", "", a.lower()) != re.sub(
                r"v\d+$", "", b.lower()
            ):
                return True
        return False

    @staticmethod
    def _stable_id(candidate: dict[str, Any]) -> str:
        paper: PaperRecord = candidate["paper"]
        ids = paper.identifiers
        identity = ids.doi or ids.arxiv_id or ids.openalex_id or ids.semantic_scholar_id
        if not identity:
            provenance = candidate.get("provenance")
            identity = f"{candidate.get('source')}:{getattr(provenance, 'source_record_id', '')}"
        if not identity.endswith(":"):
            return str(uuid.uuid5(uuid.NAMESPACE_URL, identity.lower().strip()))
        return paper.paper_id

    def _possible_matches(self, candidate: dict[str, Any], pool: list[dict[str, Any]]) -> list[str]:
        """Queue ambiguous title and author matches for later human review."""
        paper: PaperRecord = candidate["paper"]
        title = normalize_title(paper.title)
        authors = {author.name.lower().strip() for author in paper.authors}
        review: list[str] = []
        for existing in pool:
            other: PaperRecord = existing["paper"]
            other_authors = {author.name.lower().strip() for author in other.authors}
            if title and title == normalize_title(other.title) and authors & other_authors:
                review.append(other.paper_id)
        return review

    def _merge_records(
        self, base: dict[str, Any], incoming: dict[str, Any], signals: dict[str, Any]
    ) -> dict[str, Any]:
        """Merge incoming candidate into base canonical record."""
        merged = dict(base)
        base_paper: PaperRecord = merged["paper"]
        in_paper: PaperRecord = incoming["paper"]

        # Merge identifiers
        doi = base_paper.identifiers.doi or in_paper.identifiers.doi
        arxiv_id = base_paper.identifiers.arxiv_id or in_paper.identifiers.arxiv_id
        openalex_id = base_paper.identifiers.openalex_id or in_paper.identifiers.openalex_id
        s2_id = (
            base_paper.identifiers.semantic_scholar_id or in_paper.identifiers.semantic_scholar_id
        )

        base_paper.identifiers = PaperIdentifiers(
            doi=doi,
            arxiv_id=arxiv_id,
            openalex_id=openalex_id,
            semantic_scholar_id=s2_id,
        )

        # Merge abstract if missing
        if not base_paper.abstract and in_paper.abstract:
            base_paper.abstract = in_paper.abstract

        # Merge authors if base has none
        if not base_paper.authors and in_paper.authors:
            base_paper.authors = in_paper.authors

        # Prefer longest title
        if len(in_paper.title) > len(base_paper.title) and len(in_paper.title) < 300:
            base_paper.title = in_paper.title

        # Preserve PDF URL
        if not merged.get("pdf_url") and incoming.get("pdf_url"):
            merged["pdf_url"] = incoming["pdf_url"]

        # Update citation counts (keep maximum observed)
        observed_counts = [
            count
            for count in (merged.get("citation_count"), incoming.get("citation_count"))
            if count is not None
        ]
        merged["citation_count"] = max(observed_counts) if observed_counts else None

        # Merge history audit
        merged["merge_history"].append(
            {
                "source": incoming.get("source"),
                "signals": signals,
            }
        )
        base_paper.canonical_version += 1

        return merged
