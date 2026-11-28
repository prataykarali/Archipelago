"""Canonical concept, alias, abbreviation, specificity, and multi-anchor resolver for graph_v2_d14."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import re
from typing import Any

from .d14_schema import REL_PART_OF, REL_REQUIRES

#: Specificity bonus when concept A is a refinement (REQUIRES or PART_OF) of matched concept B.
REFINEMENT_SPECIFICITY_BONUS = 2.0
#: Bonus per extra word in a multi-word matched phrase to prefer specific terms over broad unigrams.
MULTI_WORD_BONUS_PER_TOKEN = 0.6
#: Exact alias/abbreviation match bonus (e.g., SVD, GAT, DDPM, LALR, RSA, TLS).
EXACT_ALIAS_BONUS = 1.2
#: Penalty for broad umbrella concepts when a narrower sibling/child is also matched.
BROAD_PARENT_PENALTY = 1.5
#: Minimum character length for non-alias label phrase matching.
MIN_LABEL_PHRASE_LEN = 3
#: Default max hops when connecting multi-concept anchors.
DEFAULT_SUBGRAPH_MAX_HOPS = 3
#: Default cap on multi-concept anchors extracted from one query.
DEFAULT_MAX_ANCHORS = 6

#: Broad umbrella concepts that should yield to specific child/sub-concepts when both appear.
BROAD_UMBRELLA_CONCEPTS: frozenset[str] = frozenset(
    {
        "linear_algebra",
        "probability",
        "probability_distribution",
        "attention_mechanism",
        "syntax_analysis",
        "diffusion_model",
        "diffusion_process",
        "neural_network",
        "machine_learning",
        "deep_learning",
        "software_engineering",
        "cpu_architecture",
        "virtual_memory",
        "finite_automata",
        "formal_languages",
    }
)


@dataclass(frozen=True)
class ConceptMatch:
    """One resolved concept anchor with its match provenance and specificity score."""

    cid: str
    label: str
    domain: str
    matched_phrase: str
    match_kind: str
    score: float


@dataclass(frozen=True)
class MultiConceptResolution:
    """Multi-anchor resolution result with ordered anchors and connecting typed subgraph."""

    query: str
    primary: ConceptMatch | None
    anchors: list[ConceptMatch] = field(default_factory=list)
    connecting_edges: list[dict[str, str]] = field(default_factory=list)


def _normalize_text(text: str) -> str:
    """Normalize text for case-insensitive whole-phrase matching while preserving '+'."""
    lowered = text.lower().replace("b+", "b plus")
    return re.sub(r"[^a-z0-9]+", " ", lowered).strip()


class ConceptResolver:
    """Deterministic concept resolver over ``graph_v2_d14`` (or any compatible graph dict)."""

    def __init__(self, graph_data: dict[str, Any]) -> None:
        self.nodes: dict[str, dict[str, Any]] = {
            str(n["id"]): n for n in (graph_data.get("nodes") or []) if n.get("id")
        }
        self.edges: list[dict[str, Any]] = list(graph_data.get("edges") or [])
        self._alias_to_cids: dict[str, list[str]] = {}
        self._label_to_cids: dict[str, list[str]] = {}
        self._parents: dict[str, set[str]] = {}
        self._adj: dict[str, list[dict[str, str]]] = {}

        for cid, node in self.nodes.items():
            for alias in node.get("aliases") or []:
                norm = _normalize_text(str(alias))
                if norm:
                    self._alias_to_cids.setdefault(norm, []).append(cid)
            label = str(node.get("label") or cid)
            norm_lbl = _normalize_text(label)
            if norm_lbl:
                self._label_to_cids.setdefault(norm_lbl, []).append(cid)
            no_paren = _normalize_text(re.sub(r"\([^)]*\)", " ", label))
            if no_paren and no_paren != norm_lbl:
                self._label_to_cids.setdefault(no_paren, []).append(cid)
            norm_id = _normalize_text(cid.replace("_", " "))
            if norm_id:
                self._label_to_cids.setdefault(norm_id, []).append(cid)

        for edge in self.edges:
            src = str(edge.get("from_id") or "")
            dst = str(edge.get("to_id") or "")
            rel = str(edge.get("relation") or edge.get("edge_type") or "").upper()
            if src not in self.nodes or dst not in self.nodes:
                continue
            if rel in {REL_REQUIRES, REL_PART_OF}:
                self._parents.setdefault(src, set()).add(dst)
            record = {"from_id": src, "to_id": dst, "relation": rel}
            self._adj.setdefault(src, []).append(record)
            self._adj.setdefault(dst, []).append(record)

    def _is_descendant_of(self, child: str, ancestor: str, max_depth: int = 3) -> bool:
        """Return True if ``child`` reaches ``ancestor`` via REQUIRES/PART_OF within ``max_depth``."""
        frontier = deque([(child, 0)])
        visited = {child}
        while frontier:
            cur, depth = frontier.popleft()
            if depth >= max_depth:
                continue
            for parent in self._parents.get(cur, ()):
                if parent == ancestor:
                    return True
                if parent not in visited:
                    visited.add(parent)
                    frontier.append((parent, depth + 1))
        return False

    def resolve_query(
        self,
        query: str,
        *,
        max_anchors: int = DEFAULT_MAX_ANCHORS,
        max_hops: int = DEFAULT_SUBGRAPH_MAX_HOPS,
    ) -> MultiConceptResolution:
        """Resolve all concepts in ``query``, ordered by specificity, plus connecting edges."""
        norm_q = _normalize_text(query)
        if not norm_q:
            return MultiConceptResolution(query=query, primary=None)
        padded_q = f" {norm_q} "

        # 1. Collect candidate matches from aliases (exact abbreviations/phrases) and labels.
        raw_hits: dict[str, tuple[str, str]] = {}
        for phrase in sorted(self._alias_to_cids, key=len, reverse=True):
            if f" {phrase} " in padded_q:
                for cid in self._alias_to_cids[phrase]:
                    if cid not in raw_hits:
                        raw_hits[cid] = (phrase, "alias")

        for phrase in sorted(self._label_to_cids, key=len, reverse=True):
            if len(phrase) < MIN_LABEL_PHRASE_LEN:
                continue
            if f" {phrase} " in padded_q:
                for cid in self._label_to_cids[phrase]:
                    if cid not in raw_hits:
                        raw_hits[cid] = (phrase, "label")

        if not raw_hits:
            return MultiConceptResolution(query=query, primary=None)

        # 2. Suppress single-token matches strictly subsumed by a longer matched phrase
        #    (e.g., "attention" inside "graph attention network", "diffusion" inside "ddpm").
        matched_phrases = [phrase for phrase, _ in raw_hits.values()]
        filtered: dict[str, tuple[str, str]] = {}
        for cid, (phrase, kind) in raw_hits.items():
            if " " not in phrase and any(
                other != phrase and f" {phrase} " in f" {other} " for other in matched_phrases
            ):
                continue
            filtered[cid] = (phrase, kind)

        # 3. Score each candidate with specificity preference over broad parents.
        matched_cids = set(filtered)
        scored: list[ConceptMatch] = []
        for cid, (phrase, kind) in filtered.items():
            tokens = phrase.split()
            score = MULTI_WORD_BONUS_PER_TOKEN * len(tokens)
            if kind == "alias":
                score += EXACT_ALIAS_BONUS
            for other in matched_cids:
                if other == cid:
                    continue
                if self._is_descendant_of(cid, other):
                    score += REFINEMENT_SPECIFICITY_BONUS
                if self._is_descendant_of(other, cid) and cid in BROAD_UMBRELLA_CONCEPTS:
                    score -= BROAD_PARENT_PENALTY
            node = self.nodes[cid]
            scored.append(
                ConceptMatch(
                    cid=cid,
                    label=str(node.get("label") or cid),
                    domain=str(node.get("domain") or ""),
                    matched_phrase=phrase,
                    match_kind=kind,
                    score=round(score, 4),
                )
            )

        scored.sort(key=lambda m: (-m.score, -len(m.matched_phrase), m.cid))

        # Keep distinct non-redundant primary anchors; drop broad parent only if a direct
        # descendant was matched AND the query wasn't explicitly comparing them.
        has_multi_cue = bool(
            re.search(r"\b(and|vs\.?|versus|between|compare|relate|connect|,)\b", query, re.I)
        )
        anchors: list[ConceptMatch] = []
        for match in scored:
            if (
                not has_multi_cue
                and match.cid in BROAD_UMBRELLA_CONCEPTS
                and any(self._is_descendant_of(kept.cid, match.cid) for kept in anchors)
            ):
                continue
            anchors.append(match)
            if len(anchors) >= max_anchors:
                break

        connecting = self._connecting_subgraph([a.cid for a in anchors], max_hops=max_hops)
        return MultiConceptResolution(
            query=query,
            primary=anchors[0] if anchors else None,
            anchors=anchors,
            connecting_edges=connecting,
        )

    def _connecting_subgraph(self, anchor_ids: list[str], *, max_hops: int) -> list[dict[str, str]]:
        """Collect shortest connecting typed edges between every pair of resolved anchors."""
        if len(anchor_ids) < 2:
            return []
        collected: dict[tuple[str, str, str], dict[str, str]] = {}
        for idx, src in enumerate(anchor_ids):
            for dst in anchor_ids[idx + 1 :]:
                path_edges = self._shortest_edges(src, dst, max_hops=max_hops)
                for edge in path_edges:
                    key = (edge["from_id"], edge["to_id"], edge["relation"])
                    collected[key] = edge
        return [collected[k] for k in sorted(collected)]

    def _shortest_edges(self, start: str, goal: str, *, max_hops: int) -> list[dict[str, str]]:
        """Bounded BFS returning typed edges along one shortest undirected path."""
        queue: deque[tuple[str, list[dict[str, str]]]] = deque([(start, [])])
        visited = {start}
        while queue:
            cur, path = queue.popleft()
            if len(path) >= max_hops:
                continue
            for edge in self._adj.get(cur, ()):
                nxt = edge["to_id"] if edge["from_id"] == cur else edge["from_id"]
                if nxt in visited:
                    continue
                next_path = [*path, edge]
                if nxt == goal:
                    return next_path
                visited.add(nxt)
                queue.append((nxt, next_path))
        return []
