"""Context serialization and chunk model for Archipelago.

Enforces a strict boundary between internal database representations and
the model-facing prompt text, preventing database metadata leakage.
"""

from __future__ import annotations

from dataclasses import dataclass
import re


@dataclass(frozen=True)
class RetrievedChunk:
    """Internal immutable representation of a retrieved document passage."""

    source_id: str
    document_title: str
    page_number: int
    text: str
    content_hash: str = ""
    section_title: str = ""


class ContextSerializer:
    """Strict serialization firewall between storage and model prompts."""

    # Patterns that must NEVER leak from internal DB metadata into model prompts
    _LEAKAGE_PATTERNS = [
        re.compile(r"/api/[^\s]+", re.IGNORECASE),
        re.compile(r"/internal/[^\s]+", re.IGNORECASE),
        re.compile(r"/admin/[^\s]+", re.IGNORECASE),
        re.compile(r"/metadata/[^\s]+", re.IGNORECASE),
        re.compile(r"\bdoc_id:\s*[^\s]+", re.IGNORECASE),
        re.compile(r"\bchunk_id:\s*[^\s]+", re.IGNORECASE),
        re.compile(r"\bsystem:\s*", re.IGNORECASE),
        re.compile(r"\btool:\s*", re.IGNORECASE),
        re.compile(r"p\.\d+\s*↗", re.UNICODE),  # UI link artifacts
    ]

    @classmethod
    def sanitize_text(cls, text: str) -> str:
        """Strip internal metadata, routing artifacts, and control tokens from text."""
        sanitized = text
        for pattern in cls._LEAKAGE_PATTERNS:
            sanitized = pattern.sub("", sanitized)
        # Normalize excessive whitespace introduced by removals
        sanitized = re.sub(r"[ \t]+", " ", sanitized)
        return sanitized.strip()

    @classmethod
    def serialize_chunk(cls, chunk: RetrievedChunk) -> str:
        """Render a single RetrievedChunk into clean model-facing format."""
        clean_text = cls.sanitize_text(chunk.text)
        clean_title = cls.sanitize_text(chunk.document_title)
        return (
            f"[{chunk.source_id}]\n"
            f"Document: {clean_title}\n"
            f"Page: {chunk.page_number}\n\n"
            f"Text:\n{clean_text}"
        )

    @classmethod
    def serialize_context(cls, chunks: list[RetrievedChunk]) -> str:
        """Serialize a list of retrieved chunks into the prompt context payload."""
        if not chunks:
            return ""
        return "\n\n---\n\n".join(cls.serialize_chunk(c) for c in chunks)
