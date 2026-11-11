"""Multi-hop curriculum chains with book/page links."""

from __future__ import annotations

import hashlib  # noqa: F401

import kuzu  # noqa: F401

from archipelago.inference import state as st  # noqa: F401
from archipelago.inference.aliases import _node_name, markdown_pdf_link, pdf_page_url  # noqa: F401
from archipelago.inference.citations import _normalize_legacy_citation  # noqa: F401
from archipelago.inference.graph_lock import graph_lock  # noqa: F401
from archipelago.inference.neighborhood import (  # noqa: F401
    get_concept_citations,
    is_plausible_prereq,
)

from .part01_hop_provenance import (
    _hop_provenance,
    find_curriculum_chains,
    format_curriculum_paths_section,
)
from .part02_find_roadmap_between import (
    find_roadmap_between,
    generate_diagnostic_quiz,
)
from .part03_evaluate_quiz_and_route_roadmap import (
    evaluate_quiz_and_route_roadmap,
)

__all__ = [
    "_hop_provenance",
    "evaluate_quiz_and_route_roadmap",
    "find_curriculum_chains",
    "find_roadmap_between",
    "format_curriculum_paths_section",
    "generate_diagnostic_quiz",
]
