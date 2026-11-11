"""Versioned prompt shared by academic ingestion and its training data."""

from __future__ import annotations

import json
from pathlib import Path

PROMPT_PATH = Path(__file__).resolve().parent / "prompts" / "academic_okf_v1.txt"
MAX_PASSAGE_CHARS = 2500


def academic_messages(
    passage: str, source_title: str, domain: str = "Computer Science", page: int = 1
) -> list[dict[str, str]]:
    """Keep source content in a JSON data block after the task instructions."""
    source = {
        "title": source_title,
        "domain": domain,
        "page": page,
        "text": passage[:MAX_PASSAGE_CHARS],
    }
    return [
        {"role": "system", "content": PROMPT_PATH.read_text(encoding="utf-8")},
        {"role": "user", "content": json.dumps(source, ensure_ascii=False)},
    ]
