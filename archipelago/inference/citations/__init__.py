"""Citations package — split from the former citations.py monolith."""

from archipelago.inference.citations.part01_evidence import (
    _citation_label,
    _evidence_for_concept,
    _evidence_for_prerequisite,
    _normalize_legacy_citation,
    _page_display,
    _resolve_printed_page,
    build_concept_citation_map,
)
from archipelago.inference.citations.part02_payloads import (
    build_citation_link,
    build_citation_payloads,
    build_library_source_payloads,
    citation_payload,
)
from archipelago.inference.citations.part03_render import (
    _citation_marker,
    _cite_with_link,
    cleanse_model_citations,
    compile_narrative_recipe,
    render_citation_from_payload,
    validate_citations,
)

__all__ = [
    "_citation_label",
    "_citation_marker",
    "_cite_with_link",
    "_evidence_for_concept",
    "_evidence_for_prerequisite",
    "_normalize_legacy_citation",
    "_page_display",
    "_resolve_printed_page",
    "build_citation_link",
    "build_citation_payloads",
    "build_concept_citation_map",
    "build_library_source_payloads",
    "citation_payload",
    "cleanse_model_citations",
    "compile_narrative_recipe",
    "render_citation_from_payload",
    "validate_citations",
]
