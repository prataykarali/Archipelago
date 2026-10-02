from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from typing import Any

SESSION_CONTEXTS: dict[str, "ContextTracker"] = {}
"""Module-level session store mapping session_id → ContextTracker."""

#: A session is idle after this long without a user turn. Reported so the chat UI
#: can stop polling a context it is not going to receive an update for.
IDLE_AFTER_SECONDS = 900

#: Distinctive tokens below this length carry no topic signal ("the", "is", "of").
MIN_TOPIC_TOKEN_LEN = 4

#: Cosine-ish overlap above which two turns are considered the same topic.
SAME_TOPIC_OVERLAP = 0.34

#: Cap on the reported reading trail, so a long session cannot grow it unbounded.
MAX_TRAIL = 12

#: How many leading tokens of a user turn are kept as its topic label.
TOPIC_LABEL_TOKENS = 6

_STOPWORDS = frozenset({
    "this", "that", "what", "which", "when", "where", "how", "does", "did",
    "explain", "tell", "show", "give", "learn", "teach", "about", "with",
    "from", "into", "have", "help", "please", "want", "need", "more",
    "library", "book", "textbook", "chapter",
})


def _topic_tokens(text: str) -> set[str]:
    """Distinctive lowercase tokens of a turn, used for topic comparison."""
    return {
        token
        for token in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(token) >= MIN_TOPIC_TOKEN_LEN and token not in _STOPWORDS
    }


def _overlap(left: set[str], right: set[str]) -> float:
    """Jaccard overlap of two token sets; 0.0 when either is empty."""
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


class ContextTracker:
    """Track conversational history for session-aware responses."""

    def __init__(self) -> None:
        """Initialise an empty context tracker."""
        self._history: list[dict[str, str]] = []
        self._trail: list[dict[str, Any]] = []
        self._last_user_at: datetime | None = None
        self._shift_detected = False
        self.active_topics: list[str] = []

    def add(self, role: str, content: str) -> None:
        """Append a turn to the history.

        A user turn updates the reading trail and, when it stops overlapping the
        previous one, flags a topic shift. A shift is what tells the chat UI to
        drop a stale sidebar graph: without it the UI keeps showing the last
        concept while the student has moved on.

        Args:
            role: Speaker role — 'user' or 'assistant'.
            content: Text content of the turn.
        """
        self._history.append({"role": role, "content": content})
        if role != "user":
            return

        now = datetime.now(UTC)
        tokens = _topic_tokens(content)
        previous = self._trail[-1]["tokens"] if self._trail else set()
        self._shift_detected = bool(previous) and _overlap(previous, tokens) < SAME_TOPIC_OVERLAP
        label = " ".join(sorted(tokens)[:TOPIC_LABEL_TOKENS]) or content.strip()[:60]
        self._trail.append(
            {"topic": label, "at": now.isoformat(), "tokens": tokens, "shifted": self._shift_detected}
        )
        del self._trail[:-MAX_TRAIL]

        if tokens:
            self.active_topics = [label]
        self._last_user_at = now

    def get_history(self) -> list[dict[str, str]]:
        """Return a snapshot of the conversation history.

        Returns:
            List of role/content dicts.
        """
        return list(self._history)

    def reset(self) -> None:
        """Clear all stored history."""
        self._history.clear()
        self._trail.clear()
        self.active_topics.clear()
        self._last_user_at = None
        self._shift_detected = False

    def last_user_message(self) -> str:
        """Return the most recent user message, or empty string.

        Returns:
            Last user content string.
        """
        for turn in reversed(self._history):
            if turn.get("role") == "user":
                return turn.get("content", "")
        return ""

    def status(self) -> dict[str, Any]:
        """The documented ``/api/context-status`` payload for this session.

        Reports what the chat UI needs to decide whether its cached topic state
        is still valid: whether the last turn shifted topic, whether the session
        has gone idle, and what the student has been reading.
        """
        return {
            "shift_detected": self.shift_detected(),
            "is_idle": self.is_idle(),
            "reading_trail": [
                {k: v for k, v in entry.items() if k != "tokens"} for entry in self._trail
            ],
        }

    def shift_detected(self) -> bool:
        """Whether the most recent user turn changed topic."""
        return self._shift_detected

    def is_idle(self, after_seconds: int = IDLE_AFTER_SECONDS) -> bool:
        """Whether the session has had no user turn for ``after_seconds``.

        A session that has never been used counts as idle: there is nothing for a
        subscriber to wait on.
        """
        if self._last_user_at is None:
            return True
        return datetime.now(UTC) - self._last_user_at > timedelta(seconds=after_seconds)


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

