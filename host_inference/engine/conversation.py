"""Conservative deterministic conversation handling, before graph ranking."""
from __future__ import annotations

import re

SMALL_TALK = re.compile(
    r"^(?:hi|hello|hey|good (?:morning|afternoon|evening)|thanks|thank you|"
    r"who are you|what can you (?:help me with|do))[\s!?.]*$", re.I,
)
GREETING_PREFIX = re.compile(r"^(?:hi|hello|hey|good morning)[\s,!:.]+", re.I)
ACADEMIC_QUERY = re.compile(
    r"\b(?:explain|definition|prerequisite|curriculum|concept|theorem|research|"
    r"paper|textbook|syllabus|study|learning|algorithm)\b", re.I,
)


def conversational_reply(query: str) -> str | None:
    """Answer standalone greetings, never swallow a greeting-prefixed real question."""
    if SMALL_TALK.fullmatch(query.strip()):
        return (
            "Hi! I'm Archipelago, your IEM/UEM library and learning assistant. "
            "Ask about a concept, its prerequisites, a book's location, or library access."
        )
    if re.search(r"(?:replace|instead of).*(?:physical|campus).*library", query, re.I):
        return (
            "Archipelago does not replace the physical library. It helps you discover "
            "relevant concepts, source pages and available campus resources."
        )
    return None
