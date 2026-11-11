"""Fetch and extract authorized full text for a bounded research session."""

from __future__ import annotations

import logging
from typing import Any

import requests

from archipelago.scholarly.acquisition.artifact_fetcher import ArtifactFetcher
from archipelago.scholarly.acquisition.indra_parser import indra_available, parse_with_indra
from archipelago.scholarly.acquisition.rights_resolver import RightsResolver
from archipelago.scholarly.extraction.abstract_fields import extract_abstract_fields
from archipelago.scholarly.extraction.research_abstract_fallback import (
    extract_fallback_abstract_fields,
)
from archipelago.scholarly.extraction.semantic_guard import valid_evidence_item
from archipelago.scholarly.extraction.slm_paper_fields import extract_slm_paper_fields

LOGGER = logging.getLogger(__name__)
MAX_FULLTEXT_PAPERS = 30
MIN_ABSTRACT_SPAN_CHARS = 50
MAX_FALLBACK_SPANS = 3


def enrich_fulltext(item: dict[str, Any], record: dict[str, Any]) -> str:
    """Add quote-checked PDF observations without publishing the PDF itself."""
    paper = item["paper"]
    url = item.get("pdf_url")
    access = RightsResolver().resolve_access(paper.is_open_access, paper.license, url)
    if not access["can_fetch_fulltext"]:
        return "METADATA_ONLY"
    if not indra_available():
        return "OCR_UNAVAILABLE"
    artifact = ArtifactFetcher().fetch_pdf(str(url), paper.paper_id)
    if not artifact:
        return "PDF_FETCH_FAILED"
    try:
        parsed = parse_with_indra(artifact["file_path"], artifact["sha256"])
        try:
            fields = extract_slm_paper_fields(parsed)
            record["metadata"]["fulltext_slm_status"] = (
                "verified" if fields else "no_accepted_fields"
            )
        except (OSError, RuntimeError, ValueError, requests.RequestException) as exc:
            LOGGER.warning(
                "PDF SLM extraction failed for %s: %s", paper.paper_id, type(exc).__name__
            )
            fields = []
            record["metadata"]["fulltext_slm_status"] = f"error:{type(exc).__name__}"
        record["metadata"]["slm_pdf_field_count"] = len(fields)
        sections = parsed.get("sections") or {}
        fallback_spans = list(sections.get("abstract") or [])[:MAX_FALLBACK_SPANS]
        if not fallback_spans:
            first_page = [
                span for spans in sections.values() for span in spans if span.get("page") == 1
            ]
            fallback_spans = sorted(
                first_page, key=lambda span: len(str(span.get("text") or "")), reverse=True
            )[:MAX_FALLBACK_SPANS]
        record["metadata"]["pdf_sha256"] = artifact["sha256"]
        known = {
            (field["group"], field["field"], field["value"], field["pdf_page"]) for field in fields
        }
        for span in fallback_spans:
            span_text = str(span.get("text") or "")
            if len(span_text) < MIN_ABSTRACT_SPAN_CHARS:
                continue
            for candidate in extract_fallback_abstract_fields(span_text):
                fact = {
                    **candidate,
                    "pdf_page": span["page"],
                    "pdf_sha256": artifact["sha256"],
                    "section": span.get("section") or "preamble",
                    "source_api": "indra_pdf_literal_fallback",
                    "verification_status": "quote_matched",
                }
                key = (fact["group"], fact["field"], fact["value"], fact["pdf_page"])
                if key not in known and valid_evidence_item(fact, record):
                    fields.append(fact)
                    known.add(key)
        if not fields and fallback_spans:
            try:
                candidates = extract_abstract_fields(str(fallback_spans[0].get("text") or ""))
            except (OSError, RuntimeError, ValueError, requests.RequestException):
                LOGGER.warning("Abstract SLM fallback failed for %s", paper.paper_id)
                candidates = []
            for candidate in candidates:
                fact = {
                    **candidate,
                    "pdf_page": fallback_spans[0]["page"],
                    "pdf_sha256": artifact["sha256"],
                    "section": fallback_spans[0].get("section") or "preamble",
                    "source_api": "indra_pdf_local_slm",
                    "verification_status": "quote_matched",
                }
                if valid_evidence_item(fact, record):
                    fields.append(fact)
    except (OSError, RuntimeError, ValueError, requests.RequestException):
        LOGGER.exception("Research full-text extraction failed for %s", paper.paper_id)
        return "FULLTEXT_EXTRACTION_FAILED"
    record["metadata"]["pdf_sha256"] = artifact["sha256"]
    record["metadata"]["ocr_engine"] = "indra"
    record["metadata"]["ocr_pages"] = parsed["num_pages"]
    record["metadata"]["fulltext_verified"] = True
    for field in fields:
        field["pdf_sha256"] = artifact["sha256"]
    record["metadata"].setdefault("verified_extractions", []).extend(fields)
    return "FULLTEXT_EXTRACTED" if fields else "FULLTEXT_NO_VERIFIED_FIELDS"
