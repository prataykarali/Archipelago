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
ARXIV_DOI_PREFIX = "10.48550/arxiv."


def normalize_title(title: str) -> str:
    """Normalize paper title for fuzzy token comparison."""
    clean = re.sub(r"[^\w\s]", "", title.lower())
    return " ".join(clean.split())


def canonical_arxiv_id(identifiers: PaperIdentifiers) -> str | None:
    """Resolve arXiv versions and arXiv DOI aliases to one paper identity."""
    value = identifiers.arxiv_id
    if not value and identifiers.doi and identifiers.doi.lower().startswith(ARXIV_DOI_PREFIX):
        value = identifiers.doi[len(ARXIV_DOI_PREFIX) :]
    return re.sub(r"v\d+$", "", value.lower().strip()) if value else None


def canonical_paper_identity(identifiers: PaperIdentifiers) -> str | None:
    """Return an identifier stable across arXiv and OpenAlex source order."""
    arxiv_id = canonical_arxiv_id(identifiers)
    if arxiv_id:
        return f"{ARXIV_DOI_PREFIX}{arxiv_id}"
    return (
        identifiers.doi
        or identifiers.datacite_doi
        or identifiers.openalex_id
        or identifiers.semantic_scholar_id
        or (f"pmid:{identifiers.pmid}" if identifiers.pmid else None)
        or (f"pmcid:{identifiers.pmcid}" if identifiers.pmcid else None)
        or (f"dblp:{identifiers.dblp_key}" if identifiers.dblp_key else None)
        or (f"openaire:{identifiers.openaire_id}" if identifiers.openaire_id else None)
    )


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
                candidate_copy["source_metadata_sources"] = {
                    key: {
                        "source_api": candidate.get("source"),
                        "source_url": getattr(candidate.get("provenance"), "source_url", None),
                        "source_timestamp": getattr(
                            candidate.get("provenance"), "fetched_at", None
                        ),
                    }
                    for key, value in (candidate.get("source_metadata") or {}).items()
                    if value is not None
                }
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
            clean_cand_arx = canonical_arxiv_id(cand_ids)
            clean_exist_arx = canonical_arxiv_id(exist_ids)
            if clean_cand_arx and clean_exist_arx and clean_cand_arx == clean_exist_arx:
                return idx, {
                    "decision": "merge",
                    "reason": "exact_arxiv_match",
                    "arxiv_id": clean_cand_arx,
                }

            # Rule 3: Exact secondary persistent IDs (PMID, PMCID, DBLP key, OpenAIRE, DataCite)
            for field_name in ("pmid", "pmcid", "dblp_key", "openaire_id", "datacite_doi"):
                cval, eval_ = getattr(cand_ids, field_name), getattr(exist_ids, field_name)
                if cval and eval_ and cval.lower().strip() == eval_.lower().strip():
                    return idx, {
                        "decision": "merge",
                        "reason": f"exact_{field_name}_match",
                        field_name: cval,
                    }

        return None, {}

    @staticmethod
    def _conflicting_ids(left: PaperIdentifiers, right: PaperIdentifiers) -> bool:
        """Reject a merge when an identifier type has two different values."""
        for name in (
            "doi",
            "arxiv_id",
            "openalex_id",
            "semantic_scholar_id",
            "pmid",
            "pmcid",
            "dblp_key",
            "openaire_id",
            "datacite_doi",
        ):
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
        identity = canonical_paper_identity(ids)
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
        base_paper.identifiers = PaperIdentifiers(
            doi=base_paper.identifiers.doi or in_paper.identifiers.doi,
            arxiv_id=base_paper.identifiers.arxiv_id or in_paper.identifiers.arxiv_id,
            isbn=base_paper.identifiers.isbn or in_paper.identifiers.isbn,
            openalex_id=base_paper.identifiers.openalex_id or in_paper.identifiers.openalex_id,
            semantic_scholar_id=(
                base_paper.identifiers.semantic_scholar_id
                or in_paper.identifiers.semantic_scholar_id
            ),
            pmid=base_paper.identifiers.pmid or in_paper.identifiers.pmid,
            pmcid=base_paper.identifiers.pmcid or in_paper.identifiers.pmcid,
            dblp_key=base_paper.identifiers.dblp_key or in_paper.identifiers.dblp_key,
            openaire_id=base_paper.identifiers.openaire_id or in_paper.identifiers.openaire_id,
            datacite_doi=(
                base_paper.identifiers.datacite_doi or in_paper.identifiers.datacite_doi
            ),
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
        base_metadata = dict(merged.get("source_metadata") or {})
        field_sources = dict(merged.get("source_metadata_sources") or {})
        for name, value in (incoming.get("source_metadata") or {}).items():
            if value is not None and base_metadata.get(name) in (None, "", []):
                base_metadata[name] = value
                field_sources[name] = {
                    "source_api": incoming.get("source"),
                    "source_url": getattr(incoming.get("provenance"), "source_url", None),
                    "source_timestamp": getattr(incoming.get("provenance"), "fetched_at", None),
                }
        merged["source_metadata"] = base_metadata
        merged["source_metadata_sources"] = field_sources

        # Merge history audit
        merged["merge_history"].append(
            {
                "source": incoming.get("source"),
                "signals": signals,
                "provenance": incoming.get("provenance"),
                "citation_count": incoming.get("citation_count"),
            }
        )
        base_paper.canonical_version += 1

        return merged
