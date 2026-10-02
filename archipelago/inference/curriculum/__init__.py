"""Multi-hop curriculum chains with book/page links."""
from __future__ import annotations

import hashlib  # noqa: F401
import kuzu  # noqa: F401
from archipelago.inference.graph_lock import graph_lock  # noqa: F401
from archipelago.inference import state as st  # noqa: F401
from archipelago.inference.aliases import _node_name, pdf_page_url, markdown_pdf_link  # noqa: F401
from archipelago.inference.neighborhood import get_concept_citations, is_plausible_prereq  # noqa: F401
from archipelago.inference.citations import _normalize_legacy_citation  # noqa: F401

from .part01_hop_provenance import (  # noqa: F401
    _hop_provenance,
    find_curriculum_chains,
    format_curriculum_paths_section,
)
from .part02_find_roadmap_between import (  # noqa: F401
    find_roadmap_between,
    generate_diagnostic_quiz,
)
from .part03_evaluate_quiz_and_route_roadmap import (  # noqa: F401
    evaluate_quiz_and_route_roadmap,
)

__all__ = ["_hop_provenance", "find_curriculum_chains", "format_curriculum_paths_section", "find_roadmap_between", "generate_diagnostic_quiz", "evaluate_quiz_and_route_roadmap"]
