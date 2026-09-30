"""Citation models and provenance contracts for Archipelago.

Enforces immutable source mapping and strictly prevents invention of
bibliographic metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SOURCE_METADATA_UNAVAILABLE = "SOURCE_METADATA_UNAVAILABLE"


@dataclass(frozen=True)
class SourceCitation:
    """Immutable citation lineage mapping an answer badge ([S1]) to source truth."""

    source_id: str
    document_title: str
    page_number: int
    chunk_text: str
    content_hash: str = ""
    authors: str = ""
    edition: str = ""
    chapter_or_section: str = ""

    def __post_init__(self) -> None:
        """Validate that essential bibliographic data is not empty or invented."""
        if not self.source_id.strip():
            raise ValueError("source_id must not be empty")
        if not self.chunk_text.strip():
            raise ValueError("chunk_text must not be empty")

    def to_dict(self) -> dict[str, Any]:
        """Convert citation to API response format."""
        return {
            "source_id": self.source_id,
            "document_title": self.document_title or SOURCE_METADATA_UNAVAILABLE,
            "page_number": self.page_number if self.page_number > 0 else SOURCE_METADATA_UNAVAILABLE,
            "content_hash": self.content_hash or SOURCE_METADATA_UNAVAILABLE,
            "authors": self.authors or SOURCE_METADATA_UNAVAILABLE,
            "edition": self.edition or SOURCE_METADATA_UNAVAILABLE,
            "chunk_text": self.chunk_text,
        }
