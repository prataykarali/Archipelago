"""Extract local PDF field candidates and accept only exact quote matches."""

from __future__ import annotations

from datetime import UTC, datetime
import json
import os
from pathlib import Path
import re
from typing import Any

import requests

from archipelago.scholarly.contracts.okf_v2_fields import PARAMETER_FIELDS
from archipelago.scholarly.contracts.research_contract import FIELDS as CONTRACT_FIELDS
from archipelago.scholarly.extraction.semantic_guard import field_role_supported

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "okf_fields_v2.txt"
OLLAMA_ENDPOINT = "http://127.0.0.1:11434/api/chat"
MODEL_NAME = "qwen3.5:0.8b"
MAX_SPANS = 8
MAX_SPAN_CHARS = 900
MAX_FIELDS = 32
REQUEST_TIMEOUT_SECONDS = 45
MODEL_CONTEXT_TOKENS = 4096
MODEL_MAX_TOKENS = 550
MAX_MODEL_CALLS = 2
MAX_MODEL_FACTS = 2
SECTION_ORDER = ("abstract", "experiments", "methods", "results", "conclusion", "limitations")
CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
EXTRACTABLE_GROUPS = frozenset(
    {
        "methodology",
        "datasets",
        "claims",
        "experiments",
        "performance",
        "evidence",
        "reproducibility",
        "efficiency",
        "research_relationships",
        "relations",
        "research_usefulness",
        "integrity",
    }
)
EXTRACTABLE_FIELDS = {
    group: tuple(
        dict.fromkeys((*PARAMETER_FIELDS.get(group, ()), *CONTRACT_FIELDS.get(group, "").split()))
    )
    for group in EXTRACTABLE_GROUPS
}
SECTION_GROUPS = {
    "abstract": ("methodology", "datasets", "experiments", "performance", "claims", "evidence"),
    "methods": ("methodology", "datasets", "experiments", "efficiency", "reproducibility"),
    "experiments": ("datasets", "experiments", "performance", "efficiency"),
    "results": ("performance", "evidence", "claims", "efficiency"),
    "conclusion": ("claims", "evidence", "research_usefulness", "integrity"),
    "limitations": ("claims", "integrity", "reproducibility"),
}
PRIORITY_FIELDS = {
    "methodology": (
        "research_problem",
        "contributions",
        "techniques",
        "model_architecture",
    ),
    "datasets": (
        "dataset_names",
        "benchmark_names",
    ),
    "experiments": (
        "datasets",
        "evaluation_metrics",
        "reported_results",
    ),
    "performance": (
        "metric_name",
        "metric_value",
    ),
    "claims": ("claim_text", "limitations"),
    "evidence": ("extracted_claims", "supporting_evidence"),
    "efficiency": ("parameter_count", "inference_latency"),
    "reproducibility": ("code_url", "dataset_url"),
    "integrity": ("retraction_status", "correction_status"),
    "research_usefulness": ("limitations", "future_work"),
}


def ingestion_model_name() -> str:
    """Resolve the shared model after service configuration is loaded."""
    return (
        os.getenv("ARCHIPELAGO_RESEARCH_MODEL")
        or os.getenv("ARCHIPELAGO_INGESTION_MODEL")
        or os.getenv("ARCHIPELAGO_OKF_MODEL")
        or MODEL_NAME
    )


def _spans(parsed_doc: dict[str, Any]) -> list[dict[str, Any]]:
    by_page: dict[int, list[dict[str, Any]]] = {}
    for section, spans in (parsed_doc.get("sections") or {}).items():
        if not isinstance(spans, list):
            continue
        for span in spans:
            if not isinstance(span, dict) or not isinstance(span.get("page"), int):
                continue
            text = CONTROL.sub(" ", str(span.get("text") or "")).strip()[:MAX_SPAN_CHARS]
            if text:
                by_page.setdefault(span["page"], []).append(
                    {"pdf_page": span["page"], "section": str(section), "text": text}
                )
    pages = sorted(by_page)
    anchors: list[int] = []
    anchor_sections: dict[int, str] = {}
    for section in SECTION_ORDER:
        first_page = next(
            (page for page in pages if any(span["section"] == section for span in by_page[page])),
            None,
        )
        if first_page is not None and first_page not in anchors:
            anchors.append(first_page)
            anchor_sections[first_page] = section
    if len(pages) > MAX_SPANS:
        remaining = [page for page in pages if page not in anchors]
        spaces = MAX_SPANS - len(anchors)
        sampled = (
            [remaining[index * (len(remaining) - 1) // (spaces - 1)] for index in range(spaces)]
            if spaces > 1
            else remaining[:spaces]
        )
        pages = sorted([*anchors, *sampled])

    def rank(span: dict[str, Any]) -> tuple[int, int]:
        section = span["section"]
        order = SECTION_ORDER.index(section) if section in SECTION_ORDER else len(SECTION_ORDER)
        return (order, -len(span["text"]))

    selected = [
        min(
            [span for span in by_page[page] if span["section"] == anchor_sections[page]]
            if page in anchor_sections
            else by_page[page],
            key=rank,
        )
        for page in pages
    ]
    if len(selected) < MAX_SPANS:
        extra = [
            span
            for page in pages
            for span in sorted(by_page[page], key=lambda item: len(item["text"]), reverse=True)[1:]
        ]
        selected.extend(extra[: MAX_SPANS - len(selected)])
    return selected


def verify_candidates(candidates: object, spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Reject invented values, missing quotes, unknown fields, and page mismatches."""
    if not isinstance(candidates, list):
        return []
    verified: list[dict[str, Any]] = []
    for candidate in candidates[:MAX_FIELDS]:
        if not isinstance(candidate, dict):
            continue
        group, field = candidate.get("group"), candidate.get("field")
        value, evidence = candidate.get("value"), candidate.get("evidence_text")
        if (
            group not in EXTRACTABLE_GROUPS
            or field not in EXTRACTABLE_FIELDS[group]
            or not isinstance(value, str)
            or not value.strip()
            or not isinstance(evidence, str)
            or not evidence.strip()
        ):
            continue
        source = next(
            (
                span
                for span in spans
                if span["pdf_page"] == candidate.get("pdf_page")
                and span["section"] == candidate.get("section")
                and evidence.casefold() in span["text"].casefold()
            ),
            None,
        )
        if source is None or value.casefold() not in evidence.casefold():
            continue
        if not field_role_supported(group, field, value, evidence):
            continue
        verified.append(
            {
                "group": group,
                "field": field,
                "value": value,
                "evidence_text": evidence,
                "pdf_page": source["pdf_page"],
                "section": source["section"],
                "source_api": "local_ollama_quote_match",
                "source_timestamp": datetime.now(UTC).isoformat(),
                "verification_status": "quote_matched",
            }
        )
    return verified


def anchor_model_quotes(candidates: object, span: dict[str, Any]) -> list[dict[str, Any]]:
    """Replace model ellipses with the exact PDF sentence containing its literal value."""
    if not isinstance(candidates, list):
        return []
    source = span["text"]
    anchored: list[dict[str, Any]] = []
    for candidate in candidates[:MAX_MODEL_FACTS]:
        if not isinstance(candidate, dict) or not isinstance(candidate.get("value"), str):
            continue
        value = candidate["value"].strip()
        if not value or value.casefold() not in source.casefold():
            continue
        quote = candidate.get("evidence_text")
        if not isinstance(quote, str) or quote.casefold() not in source.casefold():
            quote = next(
                (
                    sentence.strip()
                    for sentence in re.split(r"(?<=[.!?])\s+", source)
                    if value.casefold() in sentence.casefold()
                ),
                source,
            )
        anchored.append({**candidate, "value": value, "evidence_text": quote})
    return anchored


def extract_slm_paper_fields(parsed_doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract page-linked facts in small calls so JSON finishes before its limit."""
    spans = _spans(parsed_doc)
    if not spans:
        return []
    selected = []
    for section in SECTION_ORDER:
        match = next((span for span in spans if span["section"] == section), None)
        if match is not None and match not in selected:
            selected.append(match)
    selected.extend(span for span in spans if span not in selected)
    verified: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, int]] = set()
    for span in selected[:MAX_MODEL_CALLS]:
        relevant_groups = SECTION_GROUPS.get(
            span["section"], ("methodology", "datasets", "performance")
        )
        registry = {
            group: [
                field
                for field in PRIORITY_FIELDS.get(group, ())
                if field in EXTRACTABLE_FIELDS[group]
            ]
            for group in relevant_groups
        }
        response = requests.post(
            OLLAMA_ENDPOINT,
            json={
                "model": ingestion_model_name(),
                "stream": False,
                "format": "json",
                "think": False,
                "messages": [
                    {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
                    {
                        "role": "user",
                        "content": json.dumps({"registry": registry, "spans": [span]}),
                    },
                ],
                "options": {
                    "num_ctx": MODEL_CONTEXT_TOKENS,
                    "num_predict": MODEL_MAX_TOKENS,
                    "temperature": 0,
                },
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        payload = response.json()
        content = (payload.get("message") or {}).get("content")
        if not isinstance(content, str):
            continue
        content = content.strip()
        if content.startswith("```") and content.endswith("```"):
            content = content.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            continue
        candidates = data.get("fields") if isinstance(data, dict) else None
        anchored = anchor_model_quotes(candidates, span)
        allowed = [
            candidate
            for candidate in anchored
            if candidate.get("field") in registry.get(candidate.get("group"), ())
        ]
        for field in verify_candidates(allowed, [span]):
            key = (field["group"], field["field"], field["value"], field["pdf_page"])
            if key not in seen:
                verified.append(field)
                seen.add(key)
    return verified
