"""Answer rendering, Ollama wording, and free chat."""

from __future__ import annotations

from archipelago.inference.synthesis_library import (  # noqa: F401
    render_catalog_resources,
    render_journal_status,
    render_physical_resources,
    render_resource_availability,
    view_page_url,
)

from .constants import (
    _STREAM_SYSTEM_PROMPT,
    OLLAMA_UNAVAILABLE_MSG,
    stream_system_prompt,
)
from .core import (
    synthesize_with_ollama,
)
from .graph_notes import (
    _summarize_evidence,
    build_graph_notes,
    format_natural_fallback,
    generate_aura_synthesis,
    run_ollama_agent,
)
from .library_books import (
    _FRONTMATTER_RE,
    _TOP_LEVEL_CHAPTER_RE,
    DOC_TITLE_MAP,
    prettify_doc_title,
    render_library_books,
    render_library_chapter_lookup,
    render_library_chapters,
)
from .library_render import (
    render_catalog_stats,
    render_library_info,
)
from .prose import (
    _EMOJI_RE,
    _SLANG_LEAK_RE,
    _scrub_slm_artifacts,
    _strip_latex,
    enforce_sterile_prose,
    is_readable_synthesis,
)
from .render_path import (
    render_indexed_learning_path,
)
from .replies import (
    _extract_missing_topic,
    _related_concepts_for_topic,
    closed_library_reply,
    general_chat_reply,
    identity_reply,
    not_indexed_reply,
    onboarding_reply,
)
from .reply_checks import (
    _count_words,
    _finalize_stream_answer,
    _looks_like_citation_spam,
    _model_answer_is_usable,
    _strip_residual_markers,
    _trim_verbose_study_answer,
)
from .streaming import (
    is_ollama_available,
    stream_synthesis_with_ollama,
    synthesize_with_ollama_streaming,
)

__all__ = [
    "DOC_TITLE_MAP",
    "OLLAMA_UNAVAILABLE_MSG",
    "_EMOJI_RE",
    "_FRONTMATTER_RE",
    "_SLANG_LEAK_RE",
    "_STREAM_SYSTEM_PROMPT",
    "_TOP_LEVEL_CHAPTER_RE",
    "_count_words",
    "_extract_missing_topic",
    "_finalize_stream_answer",
    "_looks_like_citation_spam",
    "_model_answer_is_usable",
    "_related_concepts_for_topic",
    "_scrub_slm_artifacts",
    "_strip_latex",
    "_strip_residual_markers",
    "_summarize_evidence",
    "_trim_verbose_study_answer",
    "build_graph_notes",
    "closed_library_reply",
    "enforce_sterile_prose",
    "format_natural_fallback",
    "general_chat_reply",
    "generate_aura_synthesis",
    "identity_reply",
    "is_ollama_available",
    "is_readable_synthesis",
    "not_indexed_reply",
    "onboarding_reply",
    "prettify_doc_title",
    "render_catalog_stats",
    "render_indexed_learning_path",
    "render_library_books",
    "render_library_chapter_lookup",
    "render_library_chapters",
    "render_library_info",
    "run_ollama_agent",
    "stream_synthesis_with_ollama",
    "stream_system_prompt",
    "synthesize_with_ollama",
    "synthesize_with_ollama_streaming",
]
