"""Conservative detection of opposing indexed paper claims."""

from __future__ import annotations

import re
from typing import Any

CLAIM = re.compile(r"\b(increases|decreases)\s+(accuracy|latency|throughput|error rate)\b", re.I)


def opposing_papers(
    sources: list[dict[str, Any]],
) -> tuple[str, dict[str, Any], dict[str, Any]] | None:
    """Find explicit opposite directions for the same named metric in two papers."""
    by_metric: dict[str, dict[str, dict[str, Any]]] = {}
    for source in sources:
        doc_id = str(source.get("doc_id") or "")
        if not doc_id.startswith("papers/"):
            continue
        match = CLAIM.search(str(source.get("text_passage") or ""))
        if not match:
            continue
        direction, metric = match.group(1).casefold(), match.group(2).casefold()
        by_metric.setdefault(metric, {}).setdefault(direction, source)
    for metric, claims in by_metric.items():
        increase, decrease = claims.get("increases"), claims.get("decreases")
        if increase and decrease and increase.get("doc_id") != decrease.get("doc_id"):
            return metric, increase, decrease
    return None
