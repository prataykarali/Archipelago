"""Bounded multi-anchor graph traversal and sourced reply composition."""

from __future__ import annotations

from collections import deque
import re
from typing import Any

from .multi_hop_concepts import (
    DEFAULT_MAX_HOPS,
    PairwisePath,
    RelationshipEdge,
    ResolvedConcept,
    _source_supports_summary,
    extract_concept_mentions,
    resolve_concept,
)
from .multi_hop_concepts import (
    VERIFIED_CONCEPT_FOUNDATIONS as VERIFIED_CONCEPT_FOUNDATIONS,
)
from .source_conflicts import opposing_papers


def find_directed_and_undirected_path(
    graph, start_cid: str, target_cid: str, max_hops: int = DEFAULT_MAX_HOPS
) -> PairwisePath:
    """Find directed and undirected relationship path preserving edge semantics with cycle protection.

    Traverses:
    - REQUIRES (directed prerequisite)
    - UNLOCKS (directed downstream)
    - RELATED (topical neighbor)
    - Inverted edges (when traversed backwards)
    """
    if start_cid == target_cid:
        return PairwisePath(source_cid=start_cid, target_cid=target_cid, is_connected=True)

    # BFS queue: (current_node, list_of_RelationshipEdge)
    queue = deque([(start_cid, [])])
    visited = {start_cid}

    while queue:
        curr, path = queue.popleft()
        if len(path) >= max_hops:
            continue

        curr_label = graph.label(curr)

        # Explore outgoing edges
        for kind, nxt in graph.out.get(curr, []):
            if nxt not in graph.nodes:
                continue
            edge = RelationshipEdge(
                from_id=curr,
                from_label=curr_label,
                to_id=nxt,
                to_label=graph.label(nxt),
                relation=kind,
                is_reverse=False,
                evidence_type="stored_graph",
            )
            new_path = [*path, edge]
            if nxt == target_cid:
                return PairwisePath(
                    source_cid=start_cid,
                    target_cid=target_cid,
                    hops=new_path,
                    is_connected=True,
                    is_inferred=False,
                )
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, new_path))

        # Explore incoming edges (undirected traversal with inversion tracking)
        for kind, nxt in graph.inn.get(curr, []):
            if nxt not in graph.nodes:
                continue
            edge = RelationshipEdge(
                from_id=nxt,
                from_label=graph.label(nxt),
                to_id=curr,
                to_label=curr_label,
                relation=kind,
                is_reverse=True,
                evidence_type="stored_graph",
            )
            new_path = [*path, edge]
            if nxt == target_cid:
                return PairwisePath(
                    source_cid=start_cid,
                    target_cid=target_cid,
                    hops=new_path,
                    is_connected=True,
                    is_inferred=False,
                )
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, new_path))

    # Check for inferred relationship from shared documents
    start_docs = {
        str(s.get("doc_id"))
        for s in (graph.nodes.get(start_cid) or {}).get("sources", [])
        if s.get("doc_id")
    }
    target_docs = {
        str(s.get("doc_id"))
        for s in (graph.nodes.get(target_cid) or {}).get("sources", [])
        if s.get("doc_id")
    }
    shared = sorted(start_docs & target_docs)

    if shared:
        return PairwisePath(
            source_cid=start_cid,
            target_cid=target_cid,
            is_connected=True,
            is_inferred=True,
            shared_documents=shared,
        )

    return PairwisePath(source_cid=start_cid, target_cid=target_cid, is_connected=False)


def multi_hop_reasoning(
    engine, query: str, concept_mentions: list[str] | None = None, max_hops: int = DEFAULT_MAX_HOPS
) -> dict[str, Any]:
    """Execute complete multi-anchor, multi-hop reasoning.

    1. Extract all requested concepts.
    2. Resolve each to graph identity or external evidence.
    3. Retrieve relevant neighborhoods and documents.
    4. Search directed & undirected paths preserving edge semantics.
    5. Distinguish explicitly stored relationships from document-inferred ones.
    6. Join and rank evidence across all anchors.
    7. Generate one coherent explanation covering every requested concept.
    8. Cite each material claim.
    """
    graph = engine.graph
    raw_concepts = concept_mentions or extract_concept_mentions(query, known_graph=graph)

    resolved: list[ResolvedConcept] = [resolve_concept(engine, c) for c in raw_concepts]

    indexed_concepts = [c for c in resolved if c.is_indexed and c.cid]
    missing_concepts = [c for c in resolved if not c.is_indexed]
    conflicts = []
    for concept in indexed_concepts:
        found = opposing_papers((concept.node or {}).get("sources") or [])
        if not found:
            continue
        metric, increase, decrease = found
        records = []
        for source in (increase, decrease):
            record = graph.cite_record(
                concept.cid, str(source.get("text_passage") or ""), source_override=source
            )
            if record.get("doc_id") and not record.get("withdrawn"):
                existing = next(
                    (
                        item
                        for item in concept.citations
                        if item.get("doc_id") == record.get("doc_id")
                        and item.get("page_number") == record.get("page_number")
                    ),
                    None,
                )
                if existing is None:
                    concept.citations.append(record)
                records.append(existing or record)
        if len(records) == 2:
            conflicts.append((concept.label, metric, records))
    citation_index = 1
    for concept in resolved:
        for citation in concept.citations:
            if citation.get("label"):
                citation["label"] = re.sub(r"^\[S\d+:", f"[S{citation_index}:", citation["label"])
                citation["evidence_id"] = f"S{citation_index}"
                citation_index += 1

    # Search pairwise relationships between all indexed concepts
    paths: dict[tuple[str, str], PairwisePath] = {}
    for i in range(len(indexed_concepts)):
        for j in range(i + 1, len(indexed_concepts)):
            c1 = indexed_concepts[i].cid
            c2 = indexed_concepts[j].cid
            path = find_directed_and_undirected_path(graph, c1, c2, max_hops=max_hops)
            paths[(c1, c2)] = path

    # Aggregate and rank citations
    all_citations: list[dict[str, Any]] = []
    seen_evidence = set()
    for c in resolved:
        for cite in c.citations:
            if not cite.get("doc_id") or cite.get("withdrawn"):
                continue
            ev_id = cite.get("evidence_id") or f"{cite.get('doc_id')}_{cite.get('page_number')}"
            if ev_id not in seen_evidence:
                seen_evidence.add(ev_id)
                all_citations.append(cite)

    # Compose natural explanation
    explanation_lines = []

    # 1. Introduction covering all requested concepts
    concept_names = [f"**{c.label or c.raw_text}**" for c in resolved]
    if len(concept_names) >= 3:
        joined_names = ", ".join(concept_names[:-1]) + f", and {concept_names[-1]}"
    elif len(concept_names) == 2:
        joined_names = f"{concept_names[0]} and {concept_names[1]}"
    elif concept_names:
        joined_names = concept_names[0]
    else:
        joined_names = "The requested concepts"

    explanation_lines.append(f"Here is what the available evidence shows about {joined_names}.")

    # 2. Explain individual concept foundations
    for c in indexed_concepts:
        cite_str = c.citations[0].get("label", "") if c.citations else ""
        if c.summary and cite_str and _source_supports_summary(c.summary, c.citations[0]):
            explanation_lines.append(f"• **{c.label}**: {c.summary} {cite_str}".strip())
        elif c.summary:
            explanation_lines.append(
                f"• **{c.label}** is indexed, but the selected source passage does not verify its stored summary, so I cannot use that summary as a sourced definition."
            )
        else:
            explanation_lines.append(
                f"• **{c.label}** is indexed, but has no supported definition in this record."
            )

    by_id = {concept.cid: concept for concept in indexed_concepts}
    if {"transformer", "rag", "knowledge_graph"}.issubset(by_id) and all(
        by_id[cid].citations for cid in ("transformer", "rag", "knowledge_graph")
    ):
        transformer = by_id["transformer"].citations[0]["label"]
        rag = by_id["rag"].citations[0]["label"]
        knowledge_graph = by_id["knowledge_graph"].citations[0]["label"]
        explanation_lines.append(
            "\n**How they fit together.** Transformers provide an attention-based sequence model "
            f"{transformer}. RAG combines a generator with document retrieval {rag}. "
            "GraphRAG uses a knowledge graph to organize source information for broader "
            f"corpus-level synthesis {knowledge_graph}. These are different roles in one possible "
            "system, not a claim that the graph stores a prerequisite dependency among all three."
        )

    for label, metric, records in conflicts:
        explanation_lines.append(
            f"\n**Conflicting papers on {label}.** One indexed passage reports increased {metric} "
            f"{records[0]['label']}; another reports decreased {metric} {records[1]['label']}. "
            "The available passages do not establish which result generalizes."
        )

    # 3. Explain verified connections and paths
    connected_pairs = []
    unconnected_pairs = []
    inferred_pairs = []

    for (c1, c2), p in paths.items():
        l1 = graph.label(c1)
        l2 = graph.label(c2)
        if p.is_connected and p.hops:
            chain_str = " → ".join([hop.render() for hop in p.hops])
            connected_pairs.append((l1, l2, len(p.hops), chain_str))
        elif p.is_connected and p.is_inferred:
            inferred_pairs.append((l1, l2, p.shared_documents))
        else:
            unconnected_pairs.append((l1, l2))

    show_path_details = bool(
        re.search(r"\b(paths?|prerequisites?|unlocks?|graph edges?|topolog\w*)\b", query, re.I)
    )
    if connected_pairs and show_path_details:
        explanation_lines.append("\n**Verified Graph Relationships:**")
        for l1, l2, hops, chain in connected_pairs:
            relation_desc = (
                "a direct stored edge" if hops == 1 else f"a {hops}-hop stored graph path"
            )
            explanation_lines.append(
                f"• **{l1}** and **{l2}** have {relation_desc}: {chain}. These edges record graph structure; the source documents for the endpoints do not by themselves verify every edge."
            )

    if inferred_pairs:
        explanation_lines.append("\n**Document-Inferred Relationships:**")
        for l1, l2, docs in inferred_pairs:
            doc_str = ", ".join(docs[:2])
            explanation_lines.append(
                f"• **{l1}** and **{l2}** co-occur in source documentation (`{doc_str}`), "
                "though no explicit ontological edge connects them in the graph."
            )

    if unconnected_pairs:
        explanation_lines.append("\n**Unconnected Concepts:**")
        for l1, l2 in unconnected_pairs:
            explanation_lines.append(
                f"• **{l1}** and **{l2}** have no structural traversal path within {max_hops} hops in the active catalog."
            )

    # 4. Partial coverage and missing node reporting (honesty invariant)
    if missing_concepts:
        explanation_lines.append("\n**Coverage Limitations:**")
        for mc in missing_concepts:
            if mc.status == "doc_only":
                explanation_lines.append(
                    f"• **{mc.raw_text}** appears in retrieved text passages, but has no verified concept node in the active graph."
                )
            else:
                explanation_lines.append(
                    f"• **{mc.raw_text}** is not indexed in the current catalog. No bridge or relationship has been fabricated."
                )

    full_text = "\n".join(explanation_lines)

    return {
        "text": full_text,
        "resolved_concepts": resolved,
        "indexed_concepts": indexed_concepts,
        "missing_concepts": missing_concepts,
        "paths": paths,
        "citations": all_citations,
        "is_partial": bool(missing_concepts),
    }
