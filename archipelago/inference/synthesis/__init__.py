"""Answer rendering, Ollama wording, and free chat."""
from __future__ import annotations

from .constants import (  # noqa: F401
    OLLAMA_UNAVAILABLE_MSG,
    _STREAM_SYSTEM_PROMPT,
    stream_system_prompt,
)
from .reply_checks import (  # noqa: F401
    _strip_residual_markers,
    _count_words,
    _looks_like_citation_spam,
    _trim_verbose_study_answer,
    _model_answer_is_usable,
    _finalize_stream_answer,
)
from .library_render import (  # noqa: F401
    render_catalog_stats,
    render_library_info,
)
from .prose import (  # noqa: F401
    _strip_latex,
    _EMOJI_RE,
    _SLANG_LEAK_RE,
    enforce_sterile_prose,
    is_readable_synthesis,
    _scrub_slm_artifacts,
)
from .streaming import (  # noqa: F401
    is_ollama_available,
    stream_synthesis_with_ollama,
    synthesize_with_ollama_streaming,
)
from .render_path import (  # noqa: F401
    render_indexed_learning_path,
)
from .replies import (  # noqa: F401
    closed_library_reply,
    _extract_missing_topic,
    _related_concepts_for_topic,
    not_indexed_reply,
    general_chat_reply,
    identity_reply,
    onboarding_reply,
)
from .graph_notes import (  # noqa: F401
    _summarize_evidence,
    build_graph_notes,
    format_natural_fallback,
    generate_aura_synthesis,
    run_ollama_agent,
)
from .library_books import (  # noqa: F401
    DOC_TITLE_MAP,
    prettify_doc_title,
    render_library_books,
    render_library_chapters,
    render_library_chapter_lookup,
    _FRONTMATTER_RE,
    _TOP_LEVEL_CHAPTER_RE,
)
from .core import (  # noqa: F401
    synthesize_with_ollama,
)
from archipelago.inference.synthesis_library import (  # noqa: F401
    view_page_url,
    render_physical_resources,
    render_catalog_resources,
    render_resource_availability,
    render_journal_status,
)

__all__ = ["DOC_TITLE_MAP", "OLLAMA_UNAVAILABLE_MSG", "_EMOJI_RE", "_FRONTMATTER_RE", "_SLANG_LEAK_RE", "_STREAM_SYSTEM_PROMPT", "_TOP_LEVEL_CHAPTER_RE", "_count_words", "_extract_missing_topic", "_finalize_stream_answer", "_looks_like_citation_spam", "_model_answer_is_usable", "_related_concepts_for_topic", "_scrub_slm_artifacts", "_strip_latex", "_strip_residual_markers", "_summarize_evidence", "_trim_verbose_study_answer", "build_graph_notes", "closed_library_reply", "enforce_sterile_prose", "format_natural_fallback", "general_chat_reply", "generate_aura_synthesis", "identity_reply", "is_ollama_available", "is_readable_synthesis", "not_indexed_reply", "onboarding_reply", "prettify_doc_title", "render_catalog_stats", "render_indexed_learning_path", "render_library_books", "render_library_chapter_lookup", "render_library_chapters", "render_library_info", "run_ollama_agent", "stream_synthesis_with_ollama", "stream_system_prompt", "synthesize_with_ollama", "synthesize_with_ollama_streaming"]
