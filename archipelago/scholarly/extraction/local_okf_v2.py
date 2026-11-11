"""Export one complete OKF v2 JSON object from a locally ingested paper."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

from archipelago.scholarly.contracts.okf_models import PaperRecord
from archipelago.scholarly.extraction.structured_okf import build_paper_okf

MAX_EVIDENCE_TEXT = 500


def _evidence_span(
    parsed_doc: dict[str, Any], provenance: Any, needle: str
) -> dict[str, Any] | None:
    """Find a PDF span that actually contains the proposed extracted value."""
    if not needle.strip():
        return None
    sections = parsed_doc.get("sections") or {}
    if not isinstance(sections, dict):
        return None
    for section, spans in sections.items():
        if provenance.section_id and section != provenance.section_id:
            continue
        for span in spans:
            if not isinstance(span, dict) or span.get("page") != provenance.page:
                continue
            text = str(span.get("text") or "")
            if needle.casefold() in text.casefold():
                return {
                    "pdf_page": provenance.page,
                    "section": section,
                    "evidence_text": text[:MAX_EVIDENCE_TEXT],
                    "pdf_sha256": provenance.artifact_sha256,
                }
    return None


def verified_fields_from_extraction(
    extraction: dict[str, Any], parsed_doc: dict[str, Any]
) -> list[dict[str, Any]]:
    if extraction.get("verification_state") != "validated":
        return []
    provenance = {
        pointer.provenance_id: pointer
        for pointer in extraction.get("provenance") or []
        if getattr(pointer, "provenance_id", None)
    }
    fields: list[dict[str, Any]] = []

    def add(group: str, field: str, value: Any, ids: list[str], needle: str) -> None:
        for identifier in ids:
            pointer = provenance.get(identifier)
            if pointer is None:
                continue
            evidence = _evidence_span(parsed_doc, pointer, needle)
            if evidence:
                fields.append(
                    {
                        "group": group,
                        "field": field,
                        "value": value,
                        "verification_status": "verified",
                        "source_api": "local_pdf_extractor",
                        "source_timestamp": pointer.fetched_at,
                        **evidence,
                    }
                )
                return

    for dataset in extraction.get("datasets") or []:
        add("experiments", "datasets", dataset.name, dataset.provenance_ids, dataset.name)
    for claim in extraction.get("claims") or []:
        add("evidence", "extracted_claims", claim.text, claim.provenance_ids, claim.text)
    code_url = extraction.get("code_url")
    if code_url:
        for identifier, pointer in provenance.items():
            if pointer.source_url == code_url:
                add("reproducibility", "code_availability", code_url, [identifier], code_url)
                break
    for slm_item in extraction.get("slm_fields") or []:
        if isinstance(slm_item, dict) and slm_item.get("verification_status") in {
            "verified",
            "quote_matched",
            "abstract_quote_matched",
        }:
            fields.append(slm_item)
    return fields


def export_local_paper_okf(
    item: dict[str, Any],
    topic: str,
    extraction: dict[str, Any] | None = None,
    parsed_doc: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Keep unverified full-text claims unknown while exporting all fields."""
    paper: PaperRecord = item["paper"]
    source_pointer = item.get("provenance")
    fetched_at = getattr(source_pointer, "fetched_at", None) or datetime.now(UTC).isoformat()
    source_url = getattr(source_pointer, "source_url", None) or paper.oa_url
    source_name = str(item.get("source") or getattr(source_pointer, "source_type", "unknown"))
    metadata: dict[str, Any] = {
        "doi": paper.identifiers.doi,
        "arxiv_id": paper.identifiers.arxiv_id,
        "authors": [author.model_dump(mode="json") for author in paper.authors],
        "institutions": sorted({name for author in paper.authors for name in author.institutions}),
        "venue": paper.venue,
        "paper_type": paper.publication_type,
        "is_open_access": paper.is_open_access,
        "citation_count": item.get("citation_count"),
        "source_timestamp": fetched_at,
    }
    if paper.license:
        metadata["licenses"] = paper.license
    if paper.retraction_status != "unknown":
        metadata["retraction_status"] = paper.retraction_status
    if extraction and parsed_doc:
        if extraction.get("verification_state") == "validated":
            metadata["fulltext_verified"] = True
            pdf_hashes = {
                pointer.artifact_sha256
                for pointer in extraction.get("provenance") or []
                if getattr(pointer, "source_type", None) == "pdf"
            }
            if len(pdf_hashes) == 1:
                metadata["pdf_sha256"] = next(iter(pdf_hashes))
        metadata["verified_extractions"] = [
            *verified_fields_from_extraction(extraction, parsed_doc),
            *(extraction.get("slm_fields") or []),
        ]
    record = {
        "kind": "paper",
        "record_key": paper.paper_id,
        "title": paper.title,
        "source_name": source_name,
        "source_url": source_url,
        "topic": topic,
        "content": paper.abstract or "",
        "published_at": paper.publication_date,
        "metadata": metadata,
    }
    return cast(dict[str, Any], build_paper_okf(record, topic))
