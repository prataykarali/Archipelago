from __future__ import annotations

import re


def strip_production_leaks(text: str) -> str:
    """Remove internal doc_id lineage markers and raw page references from text.

    Args:
        text: Text that may contain internal system markers.

    Returns:
        Cleaned text suitable for user display.
    """
    text = re.sub(r"\[doc_id:\s*.*?\]", "", text)
    text = re.sub(r"\bp\.\d+\s*\u2197", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def sanitize_stream_final(text: str) -> str:
    """Final sanitisation pass for streamed output before display.

    Args:
        text: Final aggregated streamed text.

    Returns:
        Sanitised text.
    """
    return strip_production_leaks(text)


def sanitize_archipelago_output(text: str) -> str:
    """Sanitize overall output text for display.

    Args:
        text: Input text.

    Returns:
        Sanitized text.
    """
    return sanitize_stream_final(text)

