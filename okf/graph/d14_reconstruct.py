"""Reproducible OKF graph reconstruction & semantic DAG validation for Archipelago D14."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any

from .d14_curation_edges import CURATED_EDGES, INVALID_EDGE_REMOVALS, NOISE_HUB_IDS
from .d14_curation_nodes import (
    DUPLICATE_MERGES,
    NEW_CURRICULUM_CONCEPTS,
    NODE_ENRICHMENTS,
    REMOVED_ARTIFACT_IDS,
)
from .d14_curation_summaries import SUMMARY_REPLACEMENTS
from .d14_domain_classifier import infer_node_domain
from .d14_schema import (
    GRAPH_V1_ID,
    GRAPH_V1_SHA256,
    GRAPH_V2_ID,
    GRAPH_V2_SCHEMA_VERSION,
    PREREQUISITE_RELATIONS,
    REL_ENABLES,
    REL_RELATED_TO,
    REL_REQUIRES,
    REVIEW_PENDING,
    normalize_edge_relation,
)

PLACEHOLDER_PATTERN = re.compile(
    r"is a fundamental concept|is a key concept|is an important concept|"
    r"fundamental concept in|key concept in|no summary|placeholder",
    re.IGNORECASE,
)

_RAG_QUARANTINE_NODES: frozenset[str] = frozenset({"retrieval_augmented_generation"})
_SUPPORTED_RAG_PREREQS: frozenset[tuple[str, str, str]] = frozenset(
    {
        ("vector_rag", "retrieval_augmented_generation", REL_REQUIRES),
        ("advanced_rag", "retrieval_augmented_generation", REL_REQUIRES),
        ("retrieval_augmented_generation", "vector_rag", REL_ENABLES),
        ("retrieval_augmented_generation", "advanced_rag", REL_ENABLES),
    }
)


@dataclass
class ReconstructionResult:
    """In-memory result of rebuilding ``graph_v2_d14`` from ``graph_v1_okf610``."""

    graph_v2: dict[str, Any]
    parent_sha256: str
    removed_nodes: list[dict[str, str]]
    merged_nodes: list[dict[str, str]]
    added_nodes: list[dict[str, str]]
    updated_summaries: list[str]
    removed_edges: list[dict[str, str]]
    added_edges: list[dict[str, str]]
    cycle_breaks: list[dict[str, str]]
    edge_provenance: list[dict[str, str]]


def find_strongly_connected_components(adjacency: dict[str, set[str]]) -> list[list[str]]:
    """Return all strongly connected components of size > 1 via Tarjan's SCC."""
    index = 0
    stack: list[str] = []
    on_stack: set[str] = set()
    indices: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    sccs: list[list[str]] = []

    def strongconnect(vertex: str) -> None:
        nonlocal index
        indices[vertex] = lowlink[vertex] = index
        index += 1
        stack.append(vertex)
        on_stack.add(vertex)
        for neighbor in sorted(adjacency.get(vertex, ())):
            if neighbor not in indices:
                strongconnect(neighbor)
                lowlink[vertex] = min(lowlink[vertex], lowlink[neighbor])
            elif neighbor in on_stack:
                lowlink[vertex] = min(lowlink[vertex], indices[neighbor])
        if lowlink[vertex] == indices[vertex]:
            component: list[str] = []
            while True:
                member = stack.pop()
                on_stack.remove(member)
                component.append(member)
                if member == vertex:
                    break
            if len(component) > 1:
                sccs.append(sorted(component))

    for node in sorted(adjacency):
        if node not in indices:
            strongconnect(node)
    return sccs


def _prereq_adjacency(edges: list[dict[str, Any]], *, include_enables: bool) -> dict[str, set[str]]:
    """Build directed prerequisite adjacency (u -> v means u requires v)."""
    adj: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        rel = str(edge.get("relation") or "").upper()
        src, dst = str(edge["from_id"]), str(edge["to_id"])
        if src == dst:
            continue
        if rel == REL_REQUIRES:
            adj[src].add(dst)
        elif include_enables and rel == REL_ENABLES:
            adj[dst].add(src)
    return adj


def _is_explicitly_invalid_edge(src: str, dst: str, rel: str) -> tuple[str, str] | None:
    """Return (defect_id, reason) when an edge matches a curated removal rule."""
    if (src, dst, rel) in INVALID_EDGE_REMOVALS:
        return INVALID_EDGE_REMOVALS[(src, dst, rel)]
    if (src, dst, "*") in INVALID_EDGE_REMOVALS:
        return INVALID_EDGE_REMOVALS[(src, dst, "*")]
    if rel in PREREQUISITE_RELATIONS and (src in NOISE_HUB_IDS or dst in NOISE_HUB_IDS):
        return (
            "D14-DEF-013",
            f"Quarantined spurious prerequisite/unlock on noise hub '{src}/{dst}'.",
        )
    if (
        (src in _RAG_QUARANTINE_NODES or dst in _RAG_QUARANTINE_NODES)
        and rel in PREREQUISITE_RELATIONS
        and (src, dst, rel) not in _SUPPORTED_RAG_PREREQS
    ):
        return ("D10-S4-RAG", "Unverified RAG prerequisite/unlock edge quarantined per D10_S4.")
    return None


def reconstruct_graph_v2(v1_path: Path) -> ReconstructionResult:
    """Deterministically reconstruct ``graph_v2_d14`` from immutable ``graph_v1_okf610``."""
    raw_bytes = v1_path.read_bytes()
    parent_sha256 = sha256(raw_bytes).hexdigest()
    if parent_sha256 != GRAPH_V1_SHA256:
        raise ValueError(
            f"Baseline v1 SHA-256 mismatch: expected {GRAPH_V1_SHA256}, got {parent_sha256}"
        )
    raw: dict[str, Any] = json.loads(raw_bytes.decode("utf-8"))

    removed_nodes: list[dict[str, str]] = []
    merged_nodes: list[dict[str, str]] = []
    added_nodes: list[dict[str, str]] = []
    updated_summaries: list[str] = []
    removed_edges: list[dict[str, str]] = []
    added_edges: list[dict[str, str]] = []
    cycle_breaks: list[dict[str, str]] = []

    nodes: dict[str, dict[str, Any]] = {}
    raw_nodes: list[dict[str, Any]] = list(raw.get("nodes") or [])
    for raw_node in raw_nodes:
        cid = str(raw_node["id"])
        if cid in REMOVED_ARTIFACT_IDS:
            removed_nodes.append({"id": cid, "reason": REMOVED_ARTIFACT_IDS[cid]})
            continue
        if cid in DUPLICATE_MERGES:
            continue
        node = dict(raw_node)
        node["aliases"] = list(node.get("aliases") or [])
        nodes[cid] = node

    # Merge duplicate nodes into canonical targets (preserving sources + aliases)
    for dup_id, canon_id in sorted(DUPLICATE_MERGES.items()):
        dup_node = next((n for n in raw_nodes if n.get("id") == dup_id), None)
        if dup_node is None or canon_id not in nodes:
            continue
        target = nodes[canon_id]
        aliases = {str(a).lower() for a in target.get("aliases") or []}
        aliases.add(dup_id.replace("_", " "))
        dup_label = str(dup_node.get("label") or "").strip().lower()
        if dup_label:
            aliases.add(dup_label)
        target["aliases"] = sorted(aliases)
        existing_sources = list(target.get("sources") or [])
        seen_src = {
            (s.get("doc_id"), s.get("chunk_id")) for s in existing_sources if isinstance(s, dict)
        }
        for src_rec in dup_node.get("sources") or []:
            if isinstance(src_rec, dict):
                src_key = (src_rec.get("doc_id"), src_rec.get("chunk_id"))
                if src_key not in seen_src:
                    existing_sources.append(src_rec)
                    seen_src.add(src_key)
        target["sources"] = existing_sources
        merged_nodes.append({"from_id": dup_id, "to_id": canon_id})

    # Apply summary replacements, metadata enrichments, and domain classification
    for cid, node in nodes.items():
        if cid in SUMMARY_REPLACEMENTS:
            node["summary"] = SUMMARY_REPLACEMENTS[cid]
            updated_summaries.append(cid)
        enrichment = NODE_ENRICHMENTS.get(cid)
        explicit_domain = ""
        if enrichment is not None:
            node["label"] = enrichment.label
            explicit_domain = enrichment.domain
            merged_aliases = {str(a).lower() for a in node.get("aliases") or []}
            merged_aliases.update(a.lower() for a in enrichment.aliases)
            node["aliases"] = sorted(merged_aliases)
        node["domain"] = infer_node_domain(
            cid,
            str(node.get("label") or cid),
            str(node.get("summary") or ""),
            explicit_domain=explicit_domain,
        )
        node["review_status"] = REVIEW_PENDING

    # Add curated new curriculum concepts
    for concept_spec in NEW_CURRICULUM_CONCEPTS:
        if concept_spec.cid in nodes:
            continue
        nodes[concept_spec.cid] = {
            "id": concept_spec.cid,
            "label": concept_spec.label,
            "concept_type": concept_spec.concept_type,
            "difficulty": concept_spec.difficulty,
            "summary": concept_spec.summary,
            "domain": concept_spec.domain,
            "aliases": sorted({a.lower() for a in concept_spec.aliases}),
            "tags": [concept_spec.domain.lower().replace(" ", "_")],
            "sources": [],
            "source_categories": ["d14_curriculum_curation"],
            "sections": [],
            "prerequisites": [],
            "unlocks": [],
            "related": [],
            "degree": 0,
            "source_count": 0,
            "source_justification": concept_spec.source_justification,
            "review_status": concept_spec.review_status,
        }
        added_nodes.append(
            {
                "id": concept_spec.cid,
                "label": concept_spec.label,
                "domain": concept_spec.domain,
                "review_status": concept_spec.review_status,
            }
        )

    # Process & normalize v1 edges
    edges_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw_edge in raw.get("edges") or []:
        src = DUPLICATE_MERGES.get(str(raw_edge["from_id"]), str(raw_edge["from_id"]))
        dst = DUPLICATE_MERGES.get(str(raw_edge["to_id"]), str(raw_edge["to_id"]))
        rel = normalize_edge_relation(raw_edge.get("edge_type"), raw_edge.get("relation"))
        if src not in nodes or dst not in nodes or src == dst:
            removed_edges.append(
                {
                    "from_id": str(raw_edge["from_id"]),
                    "to_id": str(raw_edge["to_id"]),
                    "relation": rel,
                    "defect_ref": "D14-HYGIENE",
                    "reason": "Endpoint removed as artifact or collapsed to self-loop after merge.",
                }
            )
            continue
        invalid = _is_explicitly_invalid_edge(src, dst, rel)
        if invalid is not None:
            defect_ref, reason = invalid
            removed_edges.append(
                {
                    "from_id": src,
                    "to_id": dst,
                    "relation": rel,
                    "defect_ref": defect_ref,
                    "reason": reason,
                }
            )
            continue
        edge_key = (src, dst, rel)
        if edge_key not in edges_by_key:
            edges_by_key[edge_key] = {
                "from_id": src,
                "from_name": str(nodes[src].get("label") or src),
                "to_id": dst,
                "to_name": str(nodes[dst].get("label") or dst),
                "relation": rel,
                "edge_type": rel,
                "source": str(raw_edge.get("source") or "v1_okf610_inherited"),
                "provenance_origin": GRAPH_V1_ID,
                "review_status": REVIEW_PENDING,
            }

    # Add curated D14 edges
    for edge_spec in CURATED_EDGES:
        if edge_spec.from_id not in nodes or edge_spec.to_id not in nodes:
            continue
        curated_key = (edge_spec.from_id, edge_spec.to_id, edge_spec.relation)
        edges_by_key[curated_key] = {
            "from_id": edge_spec.from_id,
            "from_name": str(nodes[edge_spec.from_id].get("label") or edge_spec.from_id),
            "to_id": edge_spec.to_id,
            "to_name": str(nodes[edge_spec.to_id].get("label") or edge_spec.to_id),
            "relation": edge_spec.relation,
            "edge_type": edge_spec.relation,
            "source": edge_spec.source_justification,
            "provenance_origin": "d14_curated",
            "defect_ref": edge_spec.defect_ref,
            "review_status": edge_spec.review_status,
        }
        added_edges.append(
            {
                "from_id": edge_spec.from_id,
                "to_id": edge_spec.to_id,
                "relation": edge_spec.relation,
                "defect_ref": edge_spec.defect_ref,
                "source": edge_spec.source_justification,
                "review_status": edge_spec.review_status,
            }
        )

    edges = [edges_by_key[k] for k in sorted(edges_by_key)]
    edges = _resolve_contradictions_and_cycles(edges, cycle_breaks)

    for node in nodes.values():
        node["prerequisites"] = []
        node["unlocks"] = []
        node["related"] = []
        node["degree"] = 0
        node["source_count"] = len(node.get("sources") or [])

    for edge in edges:
        src, dst, rel = edge["from_id"], edge["to_id"], edge["relation"]
        nodes[src]["degree"] = int(nodes[src]["degree"]) + 1
        nodes[dst]["degree"] = int(nodes[dst]["degree"]) + 1
        if rel == REL_REQUIRES:
            nodes[src]["prerequisites"].append(dst)
        elif rel == REL_ENABLES:
            nodes[src]["unlocks"].append(dst)
        else:
            nodes[src]["related"].append(dst)

    rel_counts = Counter(e["relation"] for e in edges)
    sorted_nodes = [nodes[cid] for cid in sorted(nodes)]
    graph_v2: dict[str, Any] = {
        "graph_version_id": GRAPH_V2_ID,
        "schema_version": GRAPH_V2_SCHEMA_VERSION,
        "parent_graph_id": GRAPH_V1_ID,
        "parent_graph_sha256": parent_sha256,
        "stats": {
            "total_concepts": len(sorted_nodes),
            "total_edges": len(edges),
            "requires_edges": rel_counts[REL_REQUIRES],
            "enables_edges": rel_counts[REL_ENABLES],
            "uses_edges": rel_counts["USES"],
            "part_of_edges": rel_counts["PART_OF"],
            "related_to_edges": rel_counts[REL_RELATED_TO],
            "contrasts_with_edges": rel_counts["CONTRASTS_WITH"],
        },
        "nodes": sorted_nodes,
        "concepts": {n["id"]: n for n in sorted_nodes},
        "edges": edges,
    }

    edge_provenance = [
        {
            "from_id": e["from_id"],
            "to_id": e["to_id"],
            "relation": e["relation"],
            "provenance_origin": str(e.get("provenance_origin") or GRAPH_V1_ID),
            "source_justification": str(e.get("source") or ""),
            "review_status": str(e.get("review_status") or REVIEW_PENDING),
        }
        for e in edges
    ]
    return ReconstructionResult(
        graph_v2=graph_v2,
        parent_sha256=parent_sha256,
        removed_nodes=removed_nodes,
        merged_nodes=merged_nodes,
        added_nodes=added_nodes,
        updated_summaries=sorted(updated_summaries),
        removed_edges=removed_edges,
        added_edges=added_edges,
        cycle_breaks=cycle_breaks,
        edge_provenance=edge_provenance,
    )


def _resolve_contradictions_and_cycles(
    edges: list[dict[str, Any]],
    cycle_breaks: list[dict[str, str]],
) -> list[dict[str, Any]]:
    """Eliminate same-pair REQUIRES/ENABLES contradictions and guarantee a strict prerequisite DAG."""
    pair_rels: dict[tuple[str, str], set[str]] = defaultdict(set)
    for e in edges:
        pair_rels[(e["from_id"], e["to_id"])].add(e["relation"])

    cleaned: list[dict[str, Any]] = []
    for e in edges:
        src, dst, rel = e["from_id"], e["to_id"], e["relation"]
        if rel == REL_ENABLES and REL_REQUIRES in pair_rels[(src, dst)]:
            cycle_breaks.append(
                {
                    "from_id": src,
                    "to_id": dst,
                    "relation": rel,
                    "reason": "Dropped contradictory ENABLES co-occurring with same-direction REQUIRES.",
                }
            )
            continue
        cleaned.append(e)

    while True:
        sccs = find_strongly_connected_components(_prereq_adjacency(cleaned, include_enables=True))
        if not sccs:
            break
        scc_set = set(sccs[0])
        victim_idx = -1
        for idx, e in enumerate(cleaned):
            if e["relation"] not in PREREQUISITE_RELATIONS:
                continue
            if e["from_id"] in scc_set and e["to_id"] in scc_set:
                if e.get("provenance_origin") != "d14_curated":
                    victim_idx = idx
                    break
                if victim_idx == -1:
                    victim_idx = idx
        if victim_idx == -1:
            break
        victim = cleaned.pop(victim_idx)
        cycle_breaks.append(
            {
                "from_id": victim["from_id"],
                "to_id": victim["to_id"],
                "relation": victim["relation"],
                "reason": "Demoted/removed to guarantee strict DAG acyclicity on prerequisite edges.",
            }
        )
    return cleaned
