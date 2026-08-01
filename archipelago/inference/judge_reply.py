from __future__ import annotations

JUDGE_SYSTEM_PROMPT: str = (
    "You are an AI/ML education assistant judge. "
    "Evaluate answers for accuracy, citation quality, and educational value. "
    "For each answer, check: (1) factual correctness, (2) inline citation presence, "
    "(3) clarity and accessibility for undergraduate students."
)

JUDGE_MAX_OUTPUT_TOKENS: int = int("512")
JUDGE_TEMPERATURE: float = 0.0


def build_judge_user_content(query: str, answer: str) -> str:
    """Build user content for the judge LLM prompt.

    Args:
        query: User query string.
        answer: Response answer string to judge.

    Returns:
        Formatted user content string.
    """
    return f"Query: {query}\nAnswer: {answer}"


def has_judge_section_headings(text: str) -> bool:
    """Check if the text has judge section headings.

    Args:
        text: Response text to check.

    Returns:
        True if headings are present.
    """
    t = text.lower()
    return "correctness" in t or "clarity" in t or "citation" in t



