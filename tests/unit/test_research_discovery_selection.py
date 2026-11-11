"""Keep OCR candidates relevant while reserving legally readable full texts."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from archipelago.scholarly.bridge.discovery import select_relevant_papers


def _candidate(name: str, readable: bool) -> dict[str, Any]:
    return {
        "name": name,
        "paper": SimpleNamespace(is_open_access=readable, license=None),
        "pdf_url": f"https://arxiv.org/pdf/{name}" if readable else None,
    }


def test_readable_paper_displaces_lowest_metadata_only_result() -> None:
    ranked = [
        (0.90, _candidate("title-only", False)),
        (0.85, _candidate("review", False)),
        (0.80, _candidate("metadata", False)),
        (0.65, _candidate("relevant-pdf", True)),
        (0.40, _candidate("off-topic-pdf", True)),
    ]
    chosen = select_relevant_papers(ranked, 3)
    assert [item["name"] for _, item in chosen] == ["title-only", "review", "relevant-pdf"]


def test_low_relevance_pdf_does_not_replace_relevant_metadata() -> None:
    ranked = [
        (0.90, _candidate("method-paper", False)),
        (0.80, _candidate("survey", False)),
        (0.30, _candidate("other-field-pdf", True)),
    ]
    assert [item["name"] for _, item in select_relevant_papers(ranked, 2)] == [
        "method-paper",
        "survey",
    ]
