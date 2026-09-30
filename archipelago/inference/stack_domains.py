"""Domain and subject key detection for curriculum and library stack."""
from __future__ import annotations

import re

_SUBJECT_PATTERNS = [
    ("dbms", re.compile(r"\b(dbms|sql|database|databases|relational\s+algebra|acid|b\+?\s*tree|transaction)\b", re.I)),
    ("operating_systems", re.compile(r"\b(operating\s+systems?|\bos\b|ostep|cpu\s+scheduling|virtual\s+memory|paging|concurrency|process\s+scheduling|scheduler)\b", re.I)),
    ("data_structures", re.compile(r"\b(data\s+structures?|dsa|binary\s+tree|heap|sort|sorting|graph\s+algorithm|clrs|algorithms?)\b", re.I)),
    ("aiml", re.compile(r"\b(machine\s+learning|deep\s+learning|\bai\b|aiml|transformer|transformers|attention|neural\s+network|lora|peft|rag|bert|llm|llms)\b", re.I)),
]


def detect_stack_subject_key(query: str) -> str | None:
    """Detect the canonical subject key from user query, or None."""
    if not query:
        return None
    ql = query.lower()
    for key, pattern in _SUBJECT_PATTERNS:
        if pattern.search(ql):
            return key
    return None
