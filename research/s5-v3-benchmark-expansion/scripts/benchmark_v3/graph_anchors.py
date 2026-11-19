"""Deterministic graph-anchor matcher against okf_graph.json."""

from __future__ import annotations

import json
from pathlib import Path
import re

from .constants import (
    GRAPH_RICH_MIN_ANCHORS,
    MIN_CONCEPT_MATCH_CHARS,
    REGIME_RICH,
    REGIME_SPARSE,
)

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def normalize_phrase(text: str) -> str:
    """Lowercase and collapse non-alphanumeric characters to single spaces."""
    return _NON_ALNUM_RE.sub(" ", text.lower()).strip()


class GraphAnchorIndex:
    """Index of normalized concept labels from okf_graph.json."""

    def __init__(self, concept_terms: dict[str, tuple[str, ...]]) -> None:
        self._concept_terms: dict[str, tuple[str, ...]] = concept_terms

    @property
    def concept_count(self) -> int:
        """Return total number of indexed graph concepts."""
        return len(self._concept_terms)

    @classmethod
    def from_json_path(cls, path: Path) -> GraphAnchorIndex:
        """Load concepts from a canonical okf_graph.json file."""
        raw = json.loads(path.read_text(encoding="utf-8"))
        concepts = raw.get("concepts", {})
        if not isinstance(concepts, dict):
            msg = f"Invalid concepts section in {path}"
            raise ValueError(msg)

        mapping: dict[str, tuple[str, ...]] = {}
        for concept_id, payload in sorted(concepts.items()):
            candidates: set[str] = set()
            norm_id = normalize_phrase(str(concept_id).replace("_", " "))
            if len(norm_id) >= MIN_CONCEPT_MATCH_CHARS:
                candidates.add(norm_id)
            if isinstance(payload, dict):
                name = str(payload.get("name", ""))
                norm_name = normalize_phrase(name)
                if len(norm_name) >= MIN_CONCEPT_MATCH_CHARS:
                    candidates.add(norm_name)
            if candidates:
                mapping[str(concept_id)] = tuple(sorted(candidates))
        return cls(mapping)

    def match_query(self, query_text: str) -> tuple[str, ...]:
        """Return sorted concept IDs whose normalized label appears in query."""
        padded_query = f" {normalize_phrase(query_text)} "
        matched: list[str] = []
        for concept_id, phrases in self._concept_terms.items():
            if any(f" {phrase} " in padded_query for phrase in phrases):
                matched.append(concept_id)
        return tuple(sorted(matched))

    def classify_regime(self, query_text: str) -> tuple[str, tuple[str, ...]]:
        """Classify query as graph-anchor 'rich' or 'sparse' with matches."""
        matched = self.match_query(query_text)
        regime = (
            REGIME_RICH
            if len(matched) >= GRAPH_RICH_MIN_ANCHORS
            else REGIME_SPARSE
        )
        return regime, matched
