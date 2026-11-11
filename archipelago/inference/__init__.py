"""Archipelago inference (feature-split modules).

Import from here or from inference_server (compat shim).
"""

import sys as _sys
import types as _types

from archipelago.inference.aliases import (
    _core_concept_bonus,
    _node_name,
    extract_acronym,
    generate_aliases,
    markdown_pdf_link,
    pdf_page_url,
)
from archipelago.inference.citations import (
    build_citation_link,
    build_citation_payloads,
    build_concept_citation_map,
    citation_payload,
    compile_narrative_recipe,
    validate_citations,
)
from archipelago.inference.curriculum import find_curriculum_chains, format_curriculum_paths_section
from archipelago.inference.embeddings import get_snowflake_embedding, load_embedding_model
from archipelago.inference.neighborhood import get_concept_citations, get_graph_neighborhood
from archipelago.inference.ranking import find_anchor_concept, rank_concepts
from archipelago.inference.routes_chat import api_chat, init_concepts_data
from archipelago.inference.routing import resolve_query_routing
import archipelago.inference.state as _st
from archipelago.inference.state import BASE_DIR, CONCEPTS_DATA, DATA_FILE, app, db, use_embeddings
from archipelago.inference.synthesis import (
    format_natural_fallback,
    render_indexed_learning_path,
    synthesize_with_ollama,
)

__all__ = [
    "BASE_DIR",
    "CONCEPTS_DATA",
    "DATA_FILE",
    "_core_concept_bonus",
    "_node_name",
    "api_chat",
    "app",
    "build_citation_link",
    "build_citation_payloads",
    "build_concept_citation_map",
    "citation_payload",
    "compile_narrative_recipe",
    "db",
    "extract_acronym",
    "find_anchor_concept",
    "find_curriculum_chains",
    "format_curriculum_paths_section",
    "format_natural_fallback",
    "generate_aliases",
    "get_concept_citations",
    "get_graph_neighborhood",
    "get_snowflake_embedding",
    "init_concepts_data",
    "load_embedding_model",
    "markdown_pdf_link",
    "pdf_page_url",
    "rank_concepts",
    "render_indexed_learning_path",
    "resolve_query_routing",
    "synthesize_with_ollama",
    "use_embeddings",
    "validate_citations",
]


class _InferencePackage(_types.ModuleType):
    def __setattr__(self, key, value):
        object.__setattr__(self, key, value)
        if hasattr(_st, key):
            setattr(_st, key, value)

    def __getattr__(self, key):
        if hasattr(_st, key):
            return getattr(_st, key)
        raise AttributeError(f"module {self.__name__!r} has no attribute {key!r}")


_sys.modules[__name__].__class__ = _InferencePackage
