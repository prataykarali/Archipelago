from __future__ import annotations

import re


def strip_think_tags(text: str) -> str:
    """Remove <think>...</think> reasoning blocks from model output.

    Args:
        text: Raw model output that may contain think tags.

    Returns:
        Text with think blocks removed.
    """
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def cleanse_llm_output(text: str) -> str:
    """Sanitise raw LLM output for user-facing display.

    Args:
        text: Raw LLM output string.

    Returns:
        Cleaned output string suitable for display.
    """
    return strip_think_tags(text)


class ArchipelagoResponseSanitizer:
    """Stateless sanitizer for Archipelago LLM responses."""

    def sanitize(self, text: str) -> str:
        """Run all cleansing passes on a model response.

        Args:
            text: Raw model output.

        Returns:
            Sanitised text.
        """
        return cleanse_llm_output(text)
