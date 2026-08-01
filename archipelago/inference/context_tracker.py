from __future__ import annotations

from typing import Any

SESSION_CONTEXTS: dict[str, "ContextTracker"] = {}
"""Module-level session store mapping session_id → ContextTracker."""


class ContextTracker:
    """Track conversational history for session-aware responses."""

    def __init__(self) -> None:
        """Initialise an empty context tracker."""
        self._history: list[dict[str, str]] = []
        self.active_topics: list[str] = []

    def add(self, role: str, content: str) -> None:
        """Append a turn to the history.

        Args:
            role: Speaker role — 'user' or 'assistant'.
            content: Text content of the turn.
        """
        self._history.append({"role": role, "content": content})

    def get_history(self) -> list[dict[str, str]]:
        """Return a snapshot of the conversation history.

        Returns:
            List of role/content dicts.
        """
        return list(self._history)

    def reset(self) -> None:
        """Clear all stored history."""
        self._history.clear()
        self.active_topics.clear()

    def last_user_message(self) -> str:
        """Return the most recent user message, or empty string.

        Returns:
            Last user content string.
        """
        for turn in reversed(self._history):
            if turn.get("role") == "user":
                return turn.get("content", "")
        return ""


def get_or_create_context(session_id: str) -> ContextTracker:
    """Get or create a ContextTracker for the session.

    Args:
        session_id: Session identifier string.

    Returns:
        The ContextTracker instance.
    """
    if session_id not in SESSION_CONTEXTS:
        SESSION_CONTEXTS[session_id] = ContextTracker()
    return SESSION_CONTEXTS[session_id]

