"""host_inference/engine/multi_hop.py — Multi-Anchor, Multi-Hop Reasoning Engine.

Implements n-ary concept extraction, graph identity resolution, bounded multi-hop
directed/undirected relationship search with cycle protection, distinction between
explicitly stored graph relations vs. document-inferred connections, evidence aggregation,
and coherent synthesized explanations covering all requested concepts.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import logging
import re
from typing import Any

from .constants import KILL_SWITCH

logger = logging.getLogger(__name__)

# Maximum hops for relationship traversal
DEFAULT_MAX_HOPS = 5
MAX_EXTRACTED_CONCEPTS = 6

# Stop words and noise phrases in extraction
NOISE_TERMS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "how",
        "are",
        "is",
        "do",
        "does",
        "related",
        "connected",
        "connect",
        "relation",
        "relationship",
        "between",
        "among",
        "compare",
        "comparison",
        "versus",
        "vs",
        "with",
        "differ",
        "difference",
        "explain",
        "tell",
        "me",
        "about",
        "what",
        "can",
        "you",
        "please",
        "which",
    }
)


@dataclass
class ResolvedConcept:
    """A concept extracted from query and resolved against graph or external evidence."""

    raw_text: str
    cid: str | None = None
    label: str = ""
    is_indexed: bool = False
    node: dict[str, Any] | None = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    status: str = "missing"  # "indexed", "doc_only", "missing"


@dataclass
class RelationshipEdge:
    """A single hop in a path preserving edge semantics and direction."""

    from_id: str
    from_label: str
    to_id: str
    to_label: str
    relation: str  # "REQUIRES", "UNLOCKS", "RELATED"
    is_reverse: bool = False
    evidence_type: str = "stored_graph"  # "stored_graph" or "inferred_document"

    def render(self) -> str:
        """Render arrow notation preserving direction and semantic relation."""
        if self.is_reverse:
            return f"({self.from_label}) <-[{self.relation}]- ({self.to_label})"
        return f"({self.from_label}) -[{self.relation}]-> ({self.to_label})"


@dataclass
class PairwisePath:
    """Path between two concepts."""

    source_cid: str
    target_cid: str
    hops: list[RelationshipEdge] = field(default_factory=list)
    is_connected: bool = False
    is_inferred: bool = False
    shared_documents: list[str] = field(default_factory=list)


VERIFIED_CONCEPT_FOUNDATIONS: dict[str, str] = {
    "transformer": (
        "The foundational sequence-to-sequence neural architecture introduced by Vaswani et al. (2017) "
        "relying entirely on stacked self-attention and encoder-decoder cross-attention mechanisms, "
        "dispensing with recurrence and convolutions."
    ),
    "self_attention": (
        "An attention mechanism mapping query, key, and value vectors computed from the same sequence, "
        "enabling each token position to dynamically compute contextual attention weights across all sequence positions."
    ),
    "attention_mechanism": (
        "A neural computational module calculating dynamic alignment weights over input states, "
        "allowing the model to selectively focus on salient contextual features."
    ),
    "bert": (
        "Bidirectional Encoder Representations from Transformers (Devlin et al., 2018): an encoder-only architecture "
        "pretrained bidirectionally using Masked Language Modeling (MLM) and Next Sentence Prediction (NSP)."
    ),
    "low_rank_adaptation": (
        "Parameter-efficient fine-tuning (PEFT) method (Hu et al., 2021) that freezes pre-trained backbone weights "
        "and injects trainable rank-decomposition matrices (W0 + B x A) into dense attention layers, "
        "dramatically reducing trainable parameters without adding inference latency."
    ),
    "qlora": (
        "Efficient LLM fine-tuning technique (Dettmers et al., 2023) combining 4-bit NormalFloat (NF4) quantization, "
        "Double Quantization, and Paged Optimizers with Low-Rank Adaptation."
    ),
    "rag": (
        "Retrieval-Augmented Generation (Lewis et al., 2020): an architecture augmenting autoregressive language models "
        "with an external non-parametric retrieval index (dense vector index or knowledge graph) to supply retrieved context."
    ),
    "knowledge_graph": (
        "A structured knowledge base representing entities as nodes and verified semantic relations as directed or typed edges."
    ),
}


def extract_concept_mentions(query: str, known_graph=None) -> list[str]:
    """Extract 1, 2, 3, 4+ requested concepts from a natural language query.

    Handles formats like:
    - "How are transformers, retrieval-augmented generation and knowledge graphs related?"
    - "How does BERT relate to Self-Attention and RAG?"
    - "Compare LoRA, QLoRA, and full fine-tuning"
    - "Relationship between X, Y, Z, and W"
    - "How does Latent Variables connect to BERT?"
    """
    q = (query or "").strip()
    if not q:
        return []

    # Strip conversational lead-ins and parenthetical meta-notes
    clean_q = re.sub(r"\s*\([Ee]arlier user topics?:.*?\)", "", q).strip()
    clean_q = re.sub(
        r"^(?:please\s+)?(?:can\s+you\s+)?(?:tell\s+me\s+)?(?:about\s+)?", "", clean_q, flags=re.I
    ).strip()

    # Check for relational/comparison query frames
    frames = [
        r"how (?:are|is|do)\s+(.+?)\s+(?:related|connected|interact|differ)",
        r"how (?:does|do|are|is)\s+(.+?)\s+(?:connect|relate|connected|related)\s+(?:to|with)\s+(.+)",
        r"(?:relation(?:ship)?|connection) between\s+(.+)",
        r"compare\s+(.+)",
        r"difference between\s+(.+)",
    ]

    candidate_block = clean_q
    for frame in frames:
        m = re.search(frame, clean_q, re.I)
        if m:
            if len(m.groups()) == 1:
                candidate_block = m.group(1)
            elif len(m.groups()) == 2:
                candidate_block = f"{m.group(1)}, {m.group(2)}"
            break

    # Strip trailing question marks and noise
    candidate_block = re.sub(r"[\?\.!\s]+$", "", candidate_block).strip()

    # Split candidates by commas, semicolons, and coordinating conjunctions
    parts = re.split(r",\s*(?:and\s+)?|;\s*|\s+(?:and|versus|vs\.?|with)\s+", candidate_block, flags=re.I)

    raw_candidates = []
    for part in parts:
        cleaned = re.sub(r"^(?:the|an|a)\s+", "", part.strip(), flags=re.I).strip(" ?.,!")
        if cleaned and cleaned.lower() not in NOISE_TERMS and len(cleaned) >= 2:
            raw_candidates.append(cleaned)

    # If parsing found 0 or 1 candidates from frame, or missed phrases, verify with phrase hits
    if known_graph is not None:
        has_relational_cue = bool(re.search(r"\b(and|with|versus|vs\.?|between|compare|,)\b", clean_q, re.I))
        if has_relational_cue or len(raw_candidates) >= 2:
            phrase_hits = known_graph.phrase_hits(clean_q)
            matched = []
            for cid in phrase_hits:
                lbl = known_graph.label(cid)
                if lbl and lbl.lower() not in [m[1].lower() for m in matched]:
                    matched.append((cid, lbl))

            if len(raw_candidates) < 2 and len(matched) >= 2 and has_relational_cue:
                # Filter out labels that are substrings of another matched label
                filtered = [
                    lbl for _, lbl in matched
                    if not any(lbl.lower() != o[1].lower() and lbl.lower() in o[1].lower() for o in matched)
                ]
                if len(filtered) >= 2:
                    return filtered[:MAX_EXTRACTED_CONCEPTS]

    # Deduplicate while preserving order
    seen = set()
    result = []
    for c in raw_candidates:
        norm = c.lower()
        if norm not in seen and norm not in NOISE_TERMS:
            seen.add(norm)
            result.append(c)

    return result[:MAX_EXTRACTED_CONCEPTS]


def resolve_concept(engine_or_graph, concept_text: str) -> ResolvedConcept:
    """Resolve a raw concept text against the graph, external evidence, or missing state."""
    graph = getattr(engine_or_graph, "graph", engine_or_graph)
    raw = concept_text.strip()
    norm = raw.lower()

    # 1. Direct node ID match (with singular / plural normalization)
    id_candidates = [norm.replace(" ", "_")]
    if norm.endswith("s"):
        id_candidates.append(norm[:-1].replace(" ", "_"))
    if norm.endswith("es"):
        id_candidates.append(norm[:-2].replace(" ", "_"))

    for cid_cand in id_candidates:
        if cid_cand in graph.nodes:
            node = graph.nodes[cid_cand]
            summary = VERIFIED_CONCEPT_FOUNDATIONS.get(cid_cand) or str(node.get("summary") or "").strip()
            return ResolvedConcept(
                raw_text=raw,
                cid=cid_cand,
                label=graph.label(cid_cand),
                is_indexed=True,
                node=node,
                summary=summary,
                citations=[graph.cite_record(cid_cand, raw)],
                status="indexed",
            )

    # 2. Phrase hit in aliases / label index (check singular too)
    hits = graph.phrase_hits(raw)
    if not hits and raw.endswith("s"):
        hits = graph.phrase_hits(raw[:-1])
    if hits:
        best_cid = hits[0]
        node = graph.nodes[best_cid]
        summary = VERIFIED_CONCEPT_FOUNDATIONS.get(best_cid) or str(node.get("summary") or "").strip()
        return ResolvedConcept(
            raw_text=raw,
            cid=best_cid,
            label=graph.label(best_cid),
            is_indexed=True,
            node=node,
            summary=summary,
            citations=[graph.cite_record(best_cid, raw)],
            status="indexed",
        )

    # 3. Embedding cosine ranking
    ranked = graph.rank(raw, top_k=1)
    if ranked and ranked[0][0] >= KILL_SWITCH:
        best_cid = ranked[0][1]
        node = graph.nodes[best_cid]
        summary = VERIFIED_CONCEPT_FOUNDATIONS.get(best_cid) or str(node.get("summary") or "").strip()
        return ResolvedConcept(
            raw_text=raw,
            cid=best_cid,
            label=graph.label(best_cid),
            is_indexed=True,
            node=node,
            summary=summary,
            citations=[graph.cite_record(best_cid, raw)],
            status="indexed",
        )

    # 4. Check if concept appears in document passages even if no dedicated concept node
    doc_passages = []
    for cid, node in graph.nodes.items():
        for src in node.get("sources") or []:
            passage = str(src.get("text_passage") or "")
            if re.search(rf"\b{re.escape(norm)}\b", passage, re.I):
                doc_passages.append(src)
                if len(doc_passages) >= 2:
                    break
        if len(doc_passages) >= 2:
            break

    if doc_passages:
        return ResolvedConcept(
            raw_text=raw,
            cid=None,
            label=raw,
            is_indexed=False,
            citations=doc_passages,
            summary=f"Mentioned in indexed documents without a standalone concept node.",
            status="doc_only",
        )

    # 5. Missing node
    return ResolvedConcept(
        raw_text=raw,
        cid=None,
        label=raw,
        is_indexed=False,
        summary="",
        citations=[],
        status="missing",
    )


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
    shared = list(start_docs & target_docs)

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
    for c in indexed_concepts:
        for cite in c.citations:
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

    explanation_lines.append(
        f"This synthesis analyzes the structural and scientific relationships among {joined_names}."
    )

    # 2. Explain individual concept foundations
    for c in indexed_concepts:
        cite_str = graph.citation(c.cid) if c.cid else ""
        explanation_lines.append(f"• **{c.label}**: {c.summary} {cite_str}".strip())

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

    if connected_pairs:
        explanation_lines.append("\n**Verified Graph Relationships:**")
        for l1, l2, hops, chain in connected_pairs:
            relation_desc = "a direct dependency" if hops == 1 else f"a {hops}-hop verified dependency path"
            explanation_lines.append(f"• **{l1}** and **{l2}** share {relation_desc}: {chain}")

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

    # 5. Add source links
    source_links_lines = []
    for c in indexed_concepts:
        link = engine.pearson_line(c.cid)
        if link and link not in source_links_lines:
            source_links_lines.append(link)

    if source_links_lines:
        explanation_lines.append("")
        explanation_lines.extend(source_links_lines[:3])

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
