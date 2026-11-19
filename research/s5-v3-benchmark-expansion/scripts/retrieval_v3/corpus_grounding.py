"""Improvements #3 & #4: Corpus-grounded concept-to-passage mapping & edge provenance."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from retrieval_v3.config import (
    EDGE_CONFIDENCE_CO_MENTION,
    EDGE_CONFIDENCE_NO_SOURCE,
    EDGE_CONFIDENCE_WITH_SOURCE,
    EDGE_TYPE_WEIGHTS,
)
from retrieval_v3.normalization import ConceptAnchorMatcher
from retrieval_v3.types import (
    ConceptPassageLink,
    CorpusPassage,
    GraphConcept,
    GraphEdge,
)

RELATION_CANONICAL_MAP: dict[str, str] = {
    "requires": "REQUIRES",
    "prerequisite": "REQUIRES",
    "enables": "ENABLES",
    "unlocks": "ENABLES",
    "uses": "USES",
    "part_of": "PART_OF",
    "contrasts_with": "CONTRASTS_WITH",
    "co_mention": "RELATED",
    "related": "RELATED",
    "variant_of": "RELATED",
    "evaluated_by": "USES",
}

UNDIRECTED_EDGE_TYPES: frozenset[str] = frozenset({"CONTRASTS_WITH", "RELATED"})


def load_corpus_v3_passages(jsonl_path: Path) -> list[CorpusPassage]:
    """Load Corpus v3 passages deterministically from JSONL."""
    passages: list[CorpusPassage] = []
    with jsonl_path.open("r", encoding="utf-8") as handle:
        for line_no, raw_line in enumerate(handle, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            row = json.loads(stripped)
            passage_id = str(
                row.get("passage_id") or row.get("chunk_id") or row.get("id") or f"p_{line_no}"
            )
            source_doc_id = str(row.get("source_doc_id") or row.get("doc_id") or "unknown_doc")
            text = str(row.get("text") or row.get("passage_text") or "")
            page_start = int(row.get("page_start") or row.get("page_number") or 0)
            page_end = int(row.get("page_end") or page_start)
            provenance_class = str(row.get("provenance_class") or "unknown")
            source_sha256 = str(row.get("source_sha256") or row.get("content_sha256") or "")
            passages.append(
                CorpusPassage(
                    passage_id=passage_id,
                    source_doc_id=source_doc_id,
                    text=text,
                    page_start=page_start,
                    page_end=page_end,
                    provenance_class=provenance_class,
                    source_sha256=source_sha256,
                )
            )
    passages.sort(key=lambda p: p.passage_id)
    return passages


def normalize_edge_type(raw_edge_type: Any, raw_relation: Any) -> str:
    """Map raw okf_graph.json edge_type/relation to canonical uppercase edge type."""
    for candidate in (raw_edge_type, raw_relation):
        if candidate is None:
            continue
        cleaned = str(candidate).strip().lower()
        if cleaned in RELATION_CANONICAL_MAP:
            return RELATION_CANONICAL_MAP[cleaned]
        upper = cleaned.upper()
        if upper in EDGE_TYPE_WEIGHTS:
            return upper
    return "RELATED"


def resolve_edge_confidence(edge_dict: dict[str, Any], canonical_type: str) -> float:
    """Resolve explicit edge confidence or deterministic provenance-based prior."""
    raw_conf = edge_dict.get("confidence")
    if isinstance(raw_conf, (int, float)) and 0.0 < float(raw_conf) <= 1.0:
        return float(raw_conf)
    raw_rel = str(edge_dict.get("relation") or "").strip().lower()
    if raw_rel == "co_mention":
        return EDGE_CONFIDENCE_CO_MENTION
    source = str(edge_dict.get("source") or "").strip()
    if source:
        return EDGE_CONFIDENCE_WITH_SOURCE
    if canonical_type == "RELATED":
        return EDGE_CONFIDENCE_NO_SOURCE
    return EDGE_CONFIDENCE_NO_SOURCE


def load_okf_graph(graph_path: Path) -> tuple[dict[str, GraphConcept], list[GraphEdge]]:
    """Load concepts and typed edges with provenance from okf_graph.json."""
    with graph_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    concepts: dict[str, GraphConcept] = {}
    raw_concepts = payload.get("concepts", {})
    if isinstance(raw_concepts, dict):
        for cid, cdata in sorted(raw_concepts.items()):
            if not isinstance(cdata, dict):
                continue
            name = str(cdata.get("name") or cid).strip()
            sources_raw = cdata.get("sources") or []
            sources = tuple(str(s) for s in sources_raw) if isinstance(sources_raw, list) else ()
            concepts[str(cid)] = GraphConcept(
                concept_id=str(cid),
                name=name,
                concept_type=str(cdata.get("concept_type") or "unknown"),
                difficulty=str(cdata.get("difficulty") or "unknown"),
                summary=str(cdata.get("summary") or ""),
                sources=sources,
            )

    edges: list[GraphEdge] = []
    for raw_edge in payload.get("edges", []):
        if not isinstance(raw_edge, dict):
            continue
        from_id = str(raw_edge.get("from_id") or "").strip()
        to_id = str(raw_edge.get("to_id") or "").strip()
        if not from_id or not to_id:
            continue
        from_name = str(
            raw_edge.get("from_name")
            or (concepts[from_id].name if from_id in concepts else from_id)
        ).strip()
        to_name = str(
            raw_edge.get("to_name") or (concepts[to_id].name if to_id in concepts else to_id)
        ).strip()
        raw_rel = str(raw_edge.get("relation") or raw_edge.get("edge_type") or "related").strip()
        canonical_type = normalize_edge_type(raw_edge.get("edge_type"), raw_edge.get("relation"))
        source = str(raw_edge.get("source") or "").strip()
        confidence = resolve_edge_confidence(raw_edge, canonical_type)
        edges.append(
            GraphEdge(
                from_id=from_id,
                from_name=from_name,
                to_id=to_id,
                to_name=to_name,
                edge_type=canonical_type,
                raw_relation=raw_rel,
                source=source,
                confidence=confidence,
            )
        )

    return concepts, edges


@dataclass
class GroundedGraphIndex:
    """Deterministic corpus-grounded concept->passage index and edge adjacency."""

    concepts: dict[str, GraphConcept]
    edges: list[GraphEdge]
    concept_to_passages: dict[str, tuple[str, ...]]
    passage_to_concepts: dict[str, tuple[str, ...]]
    links: tuple[ConceptPassageLink, ...]
    adjacency: dict[str, tuple[GraphEdge, ...]]
    grounded_edge_count: int
    total_edge_count: int
    index_sha256: str

    def coverage_summary(self) -> dict[str, Any]:
        """Return deterministic corpus-level graph coverage statistics."""
        total_concepts = len(self.concepts)
        grounded_concepts = sum(1 for pids in self.concept_to_passages.values() if pids)
        edge_type_dist = Counter(e.edge_type for e in self.edges)
        mean_conf = sum(e.confidence for e in self.edges) / len(self.edges) if self.edges else 0.0
        return {
            "total_graph_concepts": total_concepts,
            "grounded_graph_concepts": grounded_concepts,
            "concept_grounding_ratio": round(
                grounded_concepts / total_concepts if total_concepts else 0.0, 6
            ),
            "total_graph_edges": self.total_edge_count,
            "corpus_grounded_edges": self.grounded_edge_count,
            "edge_grounding_ratio": round(
                self.grounded_edge_count / self.total_edge_count if self.total_edge_count else 0.0,
                6,
            ),
            "total_concept_passage_links": len(self.links),
            "edge_type_distribution": dict(sorted(edge_type_dist.items())),
            "mean_edge_confidence": round(mean_conf, 6),
            "index_sha256": self.index_sha256,
        }


def build_corpus_grounded_index(
    passages: Sequence[CorpusPassage],
    concepts: dict[str, GraphConcept],
    edges: Sequence[GraphEdge],
    matcher: ConceptAnchorMatcher,
    *,
    use_corpus_grounded_mapping: bool = True,
) -> GroundedGraphIndex:
    """Build deterministic concept->passage inverted index directly from Corpus v3 passages."""
    concept_to_pids_set: dict[str, set[str]] = defaultdict(set)
    passage_to_cids_set: dict[str, set[str]] = defaultdict(set)
    links: list[ConceptPassageLink] = []

    if use_corpus_grounded_mapping:
        for passage in sorted(passages, key=lambda p: p.passage_id):
            matches = matcher.match_text(passage.text)
            for m in matches:
                concept_to_pids_set[m.concept_id].add(passage.passage_id)
                passage_to_cids_set[passage.passage_id].add(m.concept_id)
                links.append(
                    ConceptPassageLink(
                        concept_id=m.concept_id,
                        passage_id=passage.passage_id,
                        source_doc_id=passage.source_doc_id,
                        page_start=passage.page_start,
                        matched_surface=m.matched_surface,
                        match_kind=m.match_kind,
                    )
                )

    concept_to_passages = {
        cid: tuple(sorted(pids)) for cid, pids in sorted(concept_to_pids_set.items())
    }
    passage_to_concepts = {
        pid: tuple(sorted(cids)) for pid, cids in sorted(passage_to_cids_set.items())
    }

    adj_lists: dict[str, list[GraphEdge]] = defaultdict(list)
    grounded_edges = 0
    for edge in edges:
        adj_lists[edge.from_id].append(edge)
        if edge.edge_type in UNDIRECTED_EDGE_TYPES:
            adj_lists[edge.to_id].append(
                GraphEdge(
                    from_id=edge.to_id,
                    from_name=edge.to_name,
                    to_id=edge.from_id,
                    to_name=edge.from_name,
                    edge_type=edge.edge_type,
                    raw_relation=edge.raw_relation,
                    source=edge.source,
                    confidence=edge.confidence,
                )
            )
        if concept_to_passages.get(edge.from_id) and concept_to_passages.get(edge.to_id):
            grounded_edges += 1

    adjacency: dict[str, tuple[GraphEdge, ...]] = {}
    for cid, edge_list in adj_lists.items():
        edge_list.sort(
            key=lambda e: (
                -(EDGE_TYPE_WEIGHTS.get(e.edge_type, 0.5) * e.confidence),
                e.to_id,
                e.edge_type,
            )
        )
        adjacency[cid] = tuple(edge_list)

    hash_payload = json.dumps(
        {
            "concept_to_passages": {k: list(v) for k, v in concept_to_passages.items()},
            "grounded_edges": grounded_edges,
            "total_edges": len(edges),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    index_sha256 = hashlib.sha256(hash_payload).hexdigest()

    return GroundedGraphIndex(
        concepts=dict(concepts),
        edges=list(edges),
        concept_to_passages=concept_to_passages,
        passage_to_concepts=passage_to_concepts,
        links=tuple(links),
        adjacency=adjacency,
        grounded_edge_count=grounded_edges,
        total_edge_count=len(edges),
        index_sha256=index_sha256,
    )
