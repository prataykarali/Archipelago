"""Produce an evidence-aware OKF paper record without filling missing metrics."""

from __future__ import annotations

from datetime import UTC, datetime
import math
from typing import Any

from .research_abstract_fallback import extract_fallback_abstract_fields
from .research_author_observations import add_author_observations
from .research_citation_observations import add_citation_observations
from .research_contract import expand_contract
from .research_evidence_guard import valid_evidence_item
from .research_graph_novelty_observations import (
    add_experiment_performance_observations,
    add_graph_observations,
    add_novelty_observations,
)
from .research_okf_fields import FULLTEXT_CATEGORIES, OKF_VERSION, PARAMETER_FIELDS
from .research_relevance_observations import add_relevance_observations
from .research_similarity import similarity, tokens

MAX_EVIDENCE_CHARS = 500
MIN_YEAR = 1800
EXTRACTOR_VERSION = "archipelago-metadata-2.1.0"
MULTI_VALUE_FIELDS = frozenset({("experiments", "datasets"), ("evidence", "extracted_claims")})


def _provenance(
    record: dict[str, Any],
    *,
    pointer: str | None = None,
    formula: str | None = None,
    evidence: str | None = None,
    verification: str = "source_reported",
) -> dict[str, Any]:
    metadata = record.get("metadata") or {}
    return {
        "source_api": record.get("source_name") or "unknown",
        "source_url": record.get("source_url") or None,
        "source_timestamp": metadata.get("source_timestamp") or record.get("updated_at"),
        "json_pointer": pointer,
        "pdf_page": None,
        "section": None,
        "table": None,
        "figure": None,
        "evidence_text": evidence[:MAX_EVIDENCE_CHARS] if evidence else None,
        "extraction_confidence": None if verification == "not_available" else 1.0,
        "verification_status": verification,
        "formula": formula,
    }


def _observation(
    value: Any,
    status: str,
    record: dict[str, Any],
    *,
    pointer: str | None = None,
    formula: str | None = None,
    evidence: str | None = None,
) -> dict[str, Any]:
    return {
        "value": value,
        "status": status,
        "confidence": None if value is None else 1.0,
        "extractor_version": EXTRACTOR_VERSION,
        "observed_at": datetime.now(UTC).isoformat(),
        "provenance": [
            _provenance(
                record,
                pointer=pointer,
                formula=formula,
                evidence=evidence,
                verification=(
                    "not_available"
                    if value is None
                    else "computed"
                    if status == "derived"
                    else "source_reported"
                ),
            )
        ],
    }


def _set(
    parameters: dict[str, dict[str, dict[str, Any]]],
    group: str,
    field: str,
    value: Any,
    record: dict[str, Any],
    *,
    pointer: str | None = None,
    formula: str | None = None,
    evidence: str | None = None,
) -> None:
    if value is None or value == "" or value == []:
        return
    parameters[group][field] = _observation(
        value,
        "derived" if formula else "observed",
        record,
        pointer=pointer,
        formula=formula,
        evidence=evidence,
    )
    source_field = pointer.removeprefix("/metadata/") if pointer else None
    source = ((record.get("metadata") or {}).get("field_sources") or {}).get(source_field)
    if isinstance(source, dict):
        parameters[group][field]["provenance"][0].update(
            {name: value for name, value in source.items() if value is not None}
        )


def _number(value: object) -> int | float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(value) and value >= 0:
        return value
    if isinstance(value, str) and value.isdecimal():
        return int(value)
    return None


def _apply_verified_extractions(
    parameters: dict[str, dict[str, dict[str, Any]]], record: dict[str, Any]
) -> None:
    """Accept only checked PDF page quotes or literal abstract quotes."""
    metadata = record.get("metadata") or {}
    extractions = metadata.get("verified_extractions") or []
    if not extractions and record.get("content"):
        extractions = extract_fallback_abstract_fields(str(record["content"]))
    if not isinstance(extractions, list):
        return
    for item in extractions:
        if not isinstance(item, dict):
            continue
        group, field = item.get("group"), item.get("field")
        page, evidence = item.get("pdf_page"), item.get("evidence_text")
        if (
            group not in PARAMETER_FIELDS
            or field not in PARAMETER_FIELDS[group]
            or not valid_evidence_item(item, record)
        ):
            continue
        status = "observed" if item["verification_status"] == "verified" else "inferred"
        observation = _observation(item["value"], status, record, evidence=evidence)
        pointer = observation["provenance"][0]
        pointer.update(
            {
                "source_api": item.get("source_api") or "verified_pdf_extraction",
                "source_timestamp": item.get("source_timestamp") or pointer["source_timestamp"],
                "pdf_page": page,
                "section": item.get("section"),
                "json_pointer": item.get("json_pointer") or pointer["json_pointer"],
                "table": item.get("table"),
                "figure": item.get("figure"),
                "extraction_confidence": item.get("extraction_confidence"),
                "verification_status": item["verification_status"],
            }
        )
        observation["confidence"] = item.get("extraction_confidence")
        observation["extractor_version"] = item.get("extractor_version") or EXTRACTOR_VERSION
        previous = parameters[group][field]
        if (group, field) in MULTI_VALUE_FIELDS:
            if (
                previous["status"] == status
                and previous["provenance"][0]["verification_status"] == item["verification_status"]
            ):
                previous["value"].append(item["value"])
                previous["provenance"].extend(observation["provenance"])
                continue
            observation["value"] = [item["value"]]
        parameters[group][field] = observation


def build_paper_okf(record: dict[str, Any], query: str | None = None) -> dict[str, Any]:
    """Map verified API fields and supported formulas into all OKF sections."""
    if record.get("kind") != "paper" or not record.get("record_key"):
        raise ValueError("A persisted paper record with a stable key is required")
    metadata = record.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}
    parameters = {
        group: {
            name: _observation(
                None,
                "not_reported"
                if group in FULLTEXT_CATEGORIES and metadata.get("fulltext_verified") is True
                else "unknown",
                record,
            )
            for name in names
        }
        for group, names in PARAMETER_FIELDS.items()
    }
    identity = "paper_identity"
    direct = (
        ("title", record.get("title"), "/title"),
        ("doi", metadata.get("doi"), "/metadata/doi"),
        ("arxiv_id", metadata.get("arxiv_id"), "/metadata/arxiv_id"),
        ("openalex_id", metadata.get("openalex_id"), "/metadata/openalex_id"),
        (
            "semantic_scholar_id",
            metadata.get("semantic_scholar_id"),
            "/metadata/semantic_scholar_id",
        ),
        ("authors", metadata.get("authors"), "/metadata/authors"),
        ("institution", metadata.get("institutions"), "/metadata/institutions"),
        ("journal_or_conference", metadata.get("venue"), "/metadata/venue"),
        ("publisher", metadata.get("publisher"), "/metadata/publisher"),
        ("publication_date", record.get("published_at"), "/published_at"),
        ("paper_type", metadata.get("paper_type"), "/metadata/paper_type"),
        ("keywords", metadata.get("keywords"), "/metadata/keywords"),
        ("research_domain", metadata.get("research_domain"), "/metadata/research_domain"),
        ("abstract", record.get("content"), "/content"),
        ("open_access_status", metadata.get("is_open_access"), "/metadata/is_open_access"),
        ("pdf_url", metadata.get("open_access_pdf"), "/metadata/open_access_pdf"),
        ("license", metadata.get("license"), "/metadata/license"),
    )
    for field, value, pointer in direct:
        _set(parameters, identity, field, value, record, pointer=pointer)
    authors = metadata.get("authors") or []
    orcids = [
        author.get("orcid")
        for author in authors
        if isinstance(author, dict) and author.get("orcid")
    ]
    _set(parameters, identity, "orcid", orcids, record, pointer="/metadata/authors")
    _set(
        parameters,
        "author_metrics",
        "author_name",
        [a.get("name") for a in authors if isinstance(a, dict) and a.get("name")],
        record,
        pointer="/metadata/authors",
    )
    _set(
        parameters,
        "author_metrics",
        "author_institution",
        metadata.get("institutions"),
        record,
        pointer="/metadata/institutions",
    )
    add_author_observations(parameters, record, _set, _number)
    published = str(record.get("published_at") or "")
    year = int(published[:4]) if published[:4].isdigit() else None
    if year is None:
        raw_year = metadata.get("publication_year") or metadata.get("year")
        if isinstance(raw_year, int):
            year = raw_year
        elif isinstance(raw_year, str) and raw_year[:4].isdigit():
            year = int(raw_year[:4])
        elif isinstance(metadata.get("published"), dict):
            parts = metadata["published"].get("date-parts")
            if (
                isinstance(parts, list)
                and parts
                and isinstance(parts[0], list)
                and parts[0]
                and isinstance(parts[0][0], int)
            ):
                year = parts[0][0]
    if year is not None and MIN_YEAR <= year <= datetime.now(UTC).year:
        _set(parameters, identity, "publication_year", year, record, pointer="/published_at")
        _set(
            parameters,
            "integrity",
            "research_age",
            max(0, datetime.now(UTC).year - year),
            record,
            formula="current_year - publication_year",
        )
    _set(
        parameters,
        "integrity",
        "publication_date",
        record.get("published_at"),
        record,
        pointer="/published_at",
    )
    add_citation_observations(parameters, record, year, _set, _number)
    add_relevance_observations(parameters, record, query, _set, similarity, tokens)
    add_graph_observations(parameters, record, _set, _number)
    add_novelty_observations(parameters, record, _set, _number)
    add_experiment_performance_observations(parameters, record, _set, _number)

    references_list = metadata.get("referenced_works") or []
    if isinstance(references_list, list) and references_list:
        _set(
            parameters,
            "research_relationships",
            "cites",
            references_list,
            record,
            pointer="/metadata/referenced_works",
        )
        _set(
            parameters,
            "research_relationships",
            "cited_papers",
            references_list,
            record,
            pointer="/metadata/referenced_works",
        )
    if "is_open_access" in metadata:
        _set(
            parameters,
            "integrity",
            "open_access_status",
            metadata["is_open_access"],
            record,
            pointer="/metadata/is_open_access",
        )
    for field in ("retraction_status", "corrections", "publication_versions", "revision_dates"):
        _set(
            parameters,
            "integrity",
            field,
            metadata.get(field),
            record,
            pointer=f"/metadata/{field}",
        )
    _set(
        parameters,
        "integrity",
        "correction_status",
        metadata.get("correction_status"),
        record,
        pointer="/metadata/correction_status",
    )
    _set(
        parameters,
        "integrity",
        "version_status",
        metadata.get("version_status"),
        record,
        pointer="/metadata/version_status",
    )
    _apply_verified_extractions(parameters, record)
    _set(
        parameters,
        "provenance",
        "source_api",
        record.get("source_name"),
        record,
        pointer="/source_name",
    )
    _set(
        parameters,
        "provenance",
        "source_timestamp",
        metadata.get("source_timestamp") or record.get("updated_at"),
        record,
        pointer="/updated_at",
    )
    _set(
        parameters,
        "provenance",
        "source_document_id",
        metadata.get("openalex_id") or metadata.get("doi") or metadata.get("arxiv_id"),
        record,
        pointer="/metadata",
    )
    _set(
        parameters,
        "provenance",
        "extractor_version",
        EXTRACTOR_VERSION,
        record,
        pointer="/okf_version",
    )
    result = expand_contract(
        {
            "okf_version": OKF_VERSION,
            "paper_key": record["record_key"],
            "generated_at": datetime.now(UTC).isoformat(),
            "parameters": parameters,
        },
        record,
    )
    result["search_topic"] = record.get("topic")
    result["verified_evidence"] = [
        {
            key: item.get(key)
            for key in (
                "group",
                "field",
                "value",
                "evidence_text",
                "pdf_page",
                "source_api",
                "verification_status",
            )
        }
        for item in metadata.get("verified_extractions") or []
        if isinstance(item, dict) and valid_evidence_item(item, record)
    ]
    return result
