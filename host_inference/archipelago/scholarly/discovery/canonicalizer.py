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


def _norm_doi(doi: str | None) -> str | None:
    if not doi:
        return None
    clean = doi.strip().lower().removeprefix("https://doi.org/").removeprefix("http://doi.org/")
    return clean or None


def _norm_openalex(oa_id: str | None) -> str | None:
    if not oa_id:
        return None
    return oa_id.strip().rsplit("/", 1)[-1].upper() or None


def _author_surnames(paper: PaperRecord) -> set[str]:
    surnames: set[str] = set()
    for a in paper.authors:
        parts = re.findall(r"[a-z]+", (a.name or "").lower())
        if parts:
            surnames.add(parts[-1])
    return surnames


def _extract_year(pub_date: str | None) -> int | None:
    if pub_date and len(pub_date) >= 4 and pub_date[:4].isdigit():
        return int(pub_date[:4])
    return None


def _provider_snapshot(candidate: dict[str, Any]) -> dict[str, Any]:
    paper: PaperRecord = candidate["paper"]
    prov = candidate.get("provenance")
    return {
        "source": candidate.get("source"),
        "source_record_id": getattr(prov, "source_record_id", None),
        "source_url": getattr(prov, "source_url", None),
        "fetched_at": getattr(prov, "fetched_at", None),
        "doi": _norm_doi(paper.identifiers.doi),
        "title": paper.title,
        "venue": paper.venue,
        "publication_date": paper.publication_date,
        "citation_count": candidate.get("citation_count"),
        "is_open_access": paper.is_open_access,
    }


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
                src = candidate.get("source")
                prov = candidate.get("provenance")
                prov_meta = {
                    "source_api": src,
                    "source_url": getattr(prov, "source_url", None),
                    "source_timestamp": getattr(prov, "fetched_at", None),
                }
                candidate_copy["source_metadata_sources"] = {
                    key: dict(prov_meta)
                    for key, value in (candidate.get("source_metadata") or {}).items()
                    if value is not None
                }
                candidate_copy["paper"] = candidate["paper"].model_copy(deep=True)
                p = candidate_copy["paper"]
                candidate_copy["primary_provider"] = src
                candidate_copy["contributing_providers"] = [src] if src else []
                candidate_copy["provider_records"] = {src: _provider_snapshot(candidate_copy)} if src else {}
                candidate_copy["field_provenance"] = {
                    fname: dict(prov_meta)
                    for fname, fval in (
                        ("title", p.title),
                        ("abstract", p.abstract),
                        ("authors", p.authors),
                        ("venue", p.venue),
                        ("publication_date", p.publication_date),
                        ("doi", p.identifiers.doi),
                        ("license", p.license),
                        ("oa_url", p.oa_url),
                        ("citation_count", candidate.get("citation_count")),
                    )
                    if fval
                }
                candidate_copy["conflicting_observations"] = []
                candidate_copy["version_relationships"] = []
                candidate_copy["identity_match_confidence"] = "single_provider"
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
        """Merge by reliable identity evidence with no conflicting known identifier."""
        cand_paper: PaperRecord = candidate["paper"]
        cand_ids = cand_paper.identifiers
        cand_doi = _norm_doi(cand_ids.doi)
        cand_oa = _norm_openalex(cand_ids.openalex_id)
        cand_title = normalize_title(cand_paper.title)
        cand_surnames = _author_surnames(cand_paper)
        cand_year = _extract_year(cand_paper.publication_date)

        for idx, existing in enumerate(pool):
            exist_paper: PaperRecord = existing["paper"]
            exist_ids = exist_paper.identifiers

            if self._conflicting_ids(cand_ids, exist_ids):
                continue
            # Rule 1: Exact normalized DOI match
            exist_doi = _norm_doi(exist_ids.doi)
            if cand_doi and exist_doi and cand_doi == exist_doi:
                return idx, {
                    "decision": "merge",
                    "reason": "exact_doi_match",
                    "confidence": "exact_doi",
                    "doi": cand_doi,
                }

            # Rule 2: Exact arXiv ID match
            clean_cand_arx = canonical_arxiv_id(cand_ids)
            clean_exist_arx = canonical_arxiv_id(exist_ids)
            if clean_cand_arx and clean_exist_arx and clean_cand_arx == clean_exist_arx:
                return idx, {
                    "decision": "merge",
                    "reason": "exact_arxiv_match",
                    "confidence": "exact_arxiv",
                    "arxiv_id": clean_cand_arx,
                }

            # Rule 3: Exact OpenAlex ID match
            exist_oa = _norm_openalex(exist_ids.openalex_id)
            if cand_oa and exist_oa and cand_oa == exist_oa:
                return idx, {
                    "decision": "merge",
                    "reason": "exact_openalex_id_match",
                    "confidence": "exact_openalex_id",
                    "openalex_id": cand_oa,
                }

            # Rule 4: Exact Semantic Scholar ID match
            if (
                cand_ids.semantic_scholar_id
                and exist_ids.semantic_scholar_id
                and cand_ids.semantic_scholar_id.strip() == exist_ids.semantic_scholar_id.strip()
            ):
                return idx, {
                    "decision": "merge",
                    "reason": "exact_semantic_scholar_id_match",
                    "confidence": "exact_s2_id",
                    "semantic_scholar_id": cand_ids.semantic_scholar_id,
                }

            # Rule 5: Exact secondary persistent IDs (PMID, PMCID, DBLP key, OpenAIRE, DataCite)
            for field_name in ("pmid", "pmcid", "dblp_key", "openaire_id", "datacite_doi"):
                cval, eval_ = getattr(cand_ids, field_name), getattr(exist_ids, field_name)
                if cval and eval_ and cval.lower().strip() == eval_.lower().strip():
                    return idx, {
                        "decision": "merge",
                        "reason": f"exact_{field_name}_match",
                        "confidence": f"exact_{field_name}",
                        field_name: cval,
                    }

            # Rule 6: Verified title + author surname + publication year match
            exist_title = normalize_title(exist_paper.title)
            if cand_title and exist_title and len(cand_title.split()) >= 3:
                title_exact = cand_title == exist_title
                if not title_exact:
                    ctoks, etoks = set(cand_title.split()), set(exist_title.split())
                    if len(ctoks) >= 5 and len(etoks) >= 5:
                        jaccard = len(ctoks & etoks) / len(ctoks | etoks)
                        title_exact = jaccard >= 0.96
                if title_exact:
                    exist_surnames = _author_surnames(exist_paper)
                    shared_authors = bool(cand_surnames and exist_surnames and (cand_surnames & exist_surnames))
                    exist_year = _extract_year(exist_paper.publication_date)
                    year_ok = (
                        cand_year is not None
                        and exist_year is not None
                        and abs(cand_year - exist_year) <= 1
                    )
                    if shared_authors and year_ok:
                        return idx, {
                            "decision": "merge",
                            "reason": "verified_title_author_year_match",
                            "confidence": "verified_title_author_year",
                            "shared_surnames": sorted(cand_surnames & exist_surnames),
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
            if not a or not b:
                continue
            if name == "doi" and _norm_doi(a) == _norm_doi(b):
                continue
            if name == "openalex_id" and _norm_openalex(a) == _norm_openalex(b):
                continue
            if a.lower().strip() == b.lower().strip():
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
        """Merge incoming candidate into base canonical record while preserving all provider evidence."""
        merged = dict(base)
        base_paper: PaperRecord = merged["paper"]
        in_paper: PaperRecord = incoming["paper"]
        in_src = incoming.get("source")
        in_prov = incoming.get("provenance")
        in_prov_meta = {
            "source_api": in_src,
            "source_url": getattr(in_prov, "source_url", None),
            "source_timestamp": getattr(in_prov, "fetched_at", None),
        }

        # Track contributing providers & per-provider snapshots
        contribs = list(merged.get("contributing_providers") or [])
        if in_src and in_src not in contribs:
            contribs.append(in_src)
        merged["contributing_providers"] = contribs
        prov_records = dict(merged.get("provider_records") or {})
        if in_src:
            prov_records[in_src] = _provider_snapshot(incoming)
        merged["provider_records"] = prov_records

        field_prov = dict(merged.get("field_provenance") or {})
        conflicts = list(merged.get("conflicting_observations") or [])

        def _record_conflict(field: str, base_val: Any, in_val: Any) -> None:
            if base_val is None or in_val is None or base_val == in_val:
                return
            if isinstance(base_val, str) and isinstance(in_val, str) and base_val.strip().casefold() == in_val.strip().casefold():
                return
            conflicts.append(
                {
                    "field": field,
                    "base_provider": (field_prov.get(field) or {}).get("source_api") or merged.get("primary_provider"),
                    "base_value": base_val,
                    "incoming_provider": in_src,
                    "incoming_value": in_val,
                }
            )

        # Track preprint / published version relationships
        ver_rels = list(merged.get("version_relationships") or [])
        base_arx = canonical_arxiv_id(base_paper.identifiers)
        in_arx = canonical_arxiv_id(in_paper.identifiers)
        base_doi = _norm_doi(base_paper.identifiers.doi)
        in_doi = _norm_doi(in_paper.identifiers.doi)
        if (base_arx or in_arx) and (base_doi or in_doi):
            rel_entry = {
                "relationship": "preprint_published_link",
                "arxiv_id": base_arx or in_arx,
                "published_doi": base_doi or in_doi,
                "providers": sorted({p for p in (merged.get("primary_provider"), in_src) if p}),
            }
            if rel_entry not in ver_rels:
                ver_rels.append(rel_entry)
        merged["version_relationships"] = ver_rels

        # Upgrade identity match confidence
        conf_rank = {
            "single_provider": 0,
            "verified_title_author_year": 1,
            "exact_openaire_id": 2,
            "exact_dblp_key": 2,
            "exact_datacite_doi": 2,
            "exact_pmid": 3,
            "exact_pmcid": 3,
            "exact_s2_id": 4,
            "exact_openalex_id": 4,
            "exact_arxiv": 5,
            "exact_doi": 6,
        }
        cur_conf = str(merged.get("identity_match_confidence") or "single_provider")
        new_conf = str(signals.get("confidence") or "verified_title_author_year")
        if conf_rank.get(new_conf, 0) > conf_rank.get(cur_conf, 0):
            merged["identity_match_confidence"] = new_conf

        # Merge identifiers
        if not base_paper.identifiers.doi and in_paper.identifiers.doi:
            field_prov["doi"] = dict(in_prov_meta)
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

        # Merge abstract, venue, publication_date, license, oa_url
        if not base_paper.abstract and in_paper.abstract:
            base_paper.abstract = in_paper.abstract
            field_prov["abstract"] = dict(in_prov_meta)
        if not base_paper.venue and in_paper.venue:
            base_paper.venue = in_paper.venue
            field_prov["venue"] = dict(in_prov_meta)
        else:
            _record_conflict("venue", base_paper.venue, in_paper.venue)
        if not base_paper.publication_date and in_paper.publication_date:
            base_paper.publication_date = in_paper.publication_date
            field_prov["publication_date"] = dict(in_prov_meta)
        else:
            _record_conflict("publication_date", base_paper.publication_date, in_paper.publication_date)
        if not base_paper.license and in_paper.license:
            base_paper.license = in_paper.license
            field_prov["license"] = dict(in_prov_meta)
        if not base_paper.oa_url and in_paper.oa_url:
            base_paper.oa_url = in_paper.oa_url
            field_prov["oa_url"] = dict(in_prov_meta)
        if base_paper.is_open_access is None and in_paper.is_open_access is not None:
            base_paper.is_open_access = in_paper.is_open_access

        # Merge authors if base has none, or enrich missing ORCID/institutions on matching authors
        if not base_paper.authors and in_paper.authors:
            base_paper.authors = in_paper.authors
            field_prov["authors"] = dict(in_prov_meta)
        elif base_paper.authors and in_paper.authors:
            by_name = {a.name.casefold().strip(): a for a in in_paper.authors if a.name}
            for idx, ba in enumerate(base_paper.authors):
                ia = by_name.get(ba.name.casefold().strip())
                if ia is None and idx < len(in_paper.authors) and len(base_paper.authors) == len(in_paper.authors):
                    ia = in_paper.authors[idx]
                if ia:
                    if not ba.orcid and ia.orcid:
                        ba.orcid = ia.orcid
                    if not ba.institutions and ia.institutions:
                        ba.institutions = list(ia.institutions)

        # Prefer longest title (up to 300 chars)
        if len(in_paper.title) > len(base_paper.title) and len(in_paper.title) < 300:
            _record_conflict("title", base_paper.title, in_paper.title)
            base_paper.title = in_paper.title
            field_prov["title"] = dict(in_prov_meta)

        # Preserve PDF URL
        if not merged.get("pdf_url") and incoming.get("pdf_url"):
            merged["pdf_url"] = incoming["pdf_url"]

        # Update citation counts (keep maximum observed, record conflicts)
        _record_conflict("citation_count", merged.get("citation_count"), incoming.get("citation_count"))
        observed_counts = [
            count
            for count in (merged.get("citation_count"), incoming.get("citation_count"))
            if count is not None
        ]
        if observed_counts:
            new_max = max(observed_counts)
            if new_max != merged.get("citation_count"):
                field_prov["citation_count"] = dict(in_prov_meta)
            merged["citation_count"] = new_max
        else:
            merged["citation_count"] = None

        base_metadata = dict(merged.get("source_metadata") or {})
        field_sources = dict(merged.get("source_metadata_sources") or {})
        for name, value in (incoming.get("source_metadata") or {}).items():
            if value is None or value == "" or value == []:
                continue
            if base_metadata.get(name) in (None, "", []):
                base_metadata[name] = value
                field_sources[name] = dict(in_prov_meta)
            elif name in ("grants", "referenced_works", "topics", "keywords") and isinstance(value, list) and isinstance(base_metadata.get(name), list):
                existing_items = base_metadata[name]
                for item in value:
                    if item not in existing_items:
                        existing_items.append(item)
        merged["source_metadata"] = base_metadata
        merged["source_metadata_sources"] = field_sources
        merged["field_provenance"] = field_prov
        merged["conflicting_observations"] = conflicts

        # Merge history audit
        merged["merge_history"].append(
            {
                "source": in_src,
                "signals": signals,
                "provenance": in_prov,
                "citation_count": incoming.get("citation_count"),
            }
        )
        base_paper.canonical_version += 1

        return merged
