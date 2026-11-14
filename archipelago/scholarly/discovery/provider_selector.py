"""Domain-aware scholarly provider selection with transparent reporting."""

from __future__ import annotations

import re
from typing import Any

ALL_MACHINE_SOURCES = (
    "openalex",
    "crossref",
    "semantic_scholar",
    "arxiv",
    "dblp",
    "openaire",
    "datacite",
    "europe_pmc",
    "pubmed",
)

DOMAIN_PROFILES: dict[str, tuple[str, ...]] = {
    "biomedical": ("openalex", "semantic_scholar", "europe_pmc", "pubmed", "crossref"),
    "datasets_software": ("openalex", "datacite", "crossref", "openaire"),
    "ai_cs": ("openalex", "semantic_scholar", "arxiv", "dblp", "crossref"),
    "general": ("openalex", "crossref", "semantic_scholar", "arxiv", "openaire"),
}

BIOMED_RE = re.compile(
    r"\b(biomedical|clinical|medical|health|genomic|protein|drug|radiology|pathology|"
    r"cancer|patient|pubmed|ehr|hospital|disease|bioinformatics|therapeutics)\b",
    re.I,
)
DATASET_RE = re.compile(
    r"\b(datasets?|benchmarks?|corpus|corpora|software|repository|codebase|open[- ]source|"
    r"artifact|toolbox|framework|library)\b",
    re.I,
)
AICS_RE = re.compile(
    r"\b(ai|artificial intelligence|machine learning|deep learning|neural|llm|rag|"
    r"retrieval|continual learning|ocr|speech recognition|nlp|transformer|graph|vision|"
    r"robot|agent|jarvis|algorithm|compiler|distributed)\b",
    re.I,
)


def classify_domain(query: str) -> str:
    """Classify query into a transparent provider-selection domain."""
    if BIOMED_RE.search(query):
        return "biomedical"
    if DATASET_RE.search(query):
        return "datasets_software"
    if AICS_RE.search(query):
        return "ai_cs"
    return "general"


def select_providers(
    query: str, explicit_sources: list[str] | None = None
) -> dict[str, Any]:
    """Select active providers and record explicit skip reasons for unused sources."""
    domain = classify_domain(query)
    if explicit_sources:
        selected = [s for s in explicit_sources if s in ALL_MACHINE_SOURCES]
        reason_prefix = "excluded_by_caller_filter"
    else:
        selected = list(DOMAIN_PROFILES[domain])
        reason_prefix = f"not_selected_for_domain:{domain}"

    skipped = [
        {"source": src, "reason": reason_prefix}
        for src in ALL_MACHINE_SOURCES
        if src not in selected
    ]
    return {
        "domain": domain,
        "selected": selected,
        "skipped": skipped,
    }
