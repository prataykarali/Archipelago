"""Match reconciled books to existing external metadata without downloading text."""

from __future__ import annotations

import re
from typing import Any

from .store import AcademicStore

_NON_WORD = re.compile(r"[^a-z0-9]+")
MIN_TITLE_TOKENS = 3


def _tokens(value: str) -> set[str]:
    return {token for token in _NON_WORD.sub(" ", value.casefold()).split() if token}


def match_repository(store: AcademicStore, items: list[dict[str, Any]]) -> int:
    """Persist only strong title matches as metadata requiring rights review."""
    records = store.match_rows()
    count = 0
    for item in items:
        title = str(item.get("title") or "")
        url = str(item.get("source_url") or "")
        if not title or not url.startswith("https://"):
            continue
        wanted = _tokens(title)
        if len(wanted) < MIN_TITLE_TOKENS:
            continue
        for record in records:
            known = _tokens(str(record["title"]))
            if wanted != known:
                continue
            store.save_match(
                str(record["record_key"]),
                "institutional_repository",
                url,
                url,
                "metadata_only_requires_rights_review",
            )
            count += 1
    return count
