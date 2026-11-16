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
    "biomedical": ("openalex", "semantic_scholar", "europe_pmc", "pubmed", "crossref", "openaire"),
    "datasets_software": ("openalex", "datacite", "crossref", "openaire", "arxiv"),
    "ai_cs": ("openalex", "semantic_scholar", "arxiv", "dblp", "crossref", "openaire"),
    "general": ("openalex", "crossref", "semantic_scholar", "arxiv", "openaire", "datacite"),
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
    r"\b(ai|artificial intelligence|machine learning|deep learning|neural|llm|slms?|"
    r"small language models?|language models?|transformers?|quantization|model compression|"
    r"on[- ]device|edge inference|edge ai|rag|retrieval|continual learning|ocr|"
    r"speech recognition|nlp|graph|vision|robot|agent|jarvis|algorithm|compiler|distributed|"
    r"diffusion|generative|reinforcement learning|attention|embedding|database|systems?)\b",
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


def classify_domain_candidates(query: str) -> list[str]:
    """Return all plausible domains matched by a query in priority order."""
    matches: list[str] = []
    if BIOMED_RE.search(query):
        matches.append("biomedical")
    if DATASET_RE.search(query):
        matches.append("datasets_software")
    if AICS_RE.search(query):
        matches.append("ai_cs")
    if "general" not in matches:
        matches.append("general")
    return matches


def select_providers(
    query: str,
    explicit_sources: list[str] | None = None,
    resolved_domain: str | None = None,
) -> dict[str, Any]:
    """Select active providers and record explicit skip reasons for unused sources."""
    detected_domain = classify_domain(query)
    domain = resolved_domain if resolved_domain in DOMAIN_PROFILES else detected_domain
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
        "detected_domain": detected_domain,
        "selected": selected,
        "skipped": skipped,
    }
