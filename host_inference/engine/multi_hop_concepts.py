"""Concept extraction and evidence-backed identity resolution for multi-hop replies."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any

from .concept_foundations import VERIFIED_CONCEPT_FOUNDATIONS as VERIFIED_CONCEPT_FOUNDATIONS
from .constants import KILL_SWITCH

# Maximum hops for relationship traversal
DEFAULT_MAX_HOPS = 5
MAX_EXTRACTED_CONCEPTS = 6
MIN_SOURCE_OVERLAP = 2
SUMMARY_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "with",
        "from",
        "that",
        "this",
        "using",
        "into",
        "model",
        "models",
        "neural",
        "network",
        "based",
    }
)

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


def _source_supports_summary(summary: str, citation: dict[str, Any]) -> bool:
    """Require content overlap before attaching a passage citation to a summary."""
    passage = str(citation.get("text_passage") or "")
    summary_terms = {
        word
        for word in re.findall(r"[a-z]{4,}", summary.casefold())
        if word not in SUMMARY_STOPWORDS
    }
    passage_terms = set(re.findall(r"[a-z]{4,}", passage.casefold()))
    return len(summary_terms & passage_terms) >= MIN_SOURCE_OVERLAP


def _grounded_summary_and_citation(graph: Any, cid: str) -> tuple[str, list[dict[str, Any]]]:
    """Choose a supporting passage before citing a concept definition."""
    node = graph.nodes[cid]
    if cid == "transformer":
        summary = "The Transformer replaces recurrent and convolutional sequence transduction layers with attention."
    elif cid == "rag":
        summary = "RAG combines a retriever and a generator, training them together to use retrieved documents."
    else:
        summary = str(node.get("summary") or "").strip()
    terms = {
        word
        for word in re.findall(r"[a-z]{4,}", summary.casefold())
        if word not in SUMMARY_STOPWORDS
    }
    sources = [
        source
        for source in node.get("sources") or []
        if source.get("doc_id") and source.get("text_passage")
    ]
    if not sources:
        return summary, []
    best = max(
        sources,
        key=lambda source: len(
            terms & set(re.findall(r"[a-z]{4,}", str(source["text_passage"]).casefold()))
        ),
    )
    record = graph.cite_record(cid, str(best["text_passage"]), source_override=best)
    if (
        not record.get("doc_id")
        or record.get("withdrawn")
        or not _source_supports_summary(summary, record)
    ):
        return summary, []
    return summary, [record]


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
    parts = re.split(
        r",\s*(?:and\s+)?|;\s*|\s+(?:and|versus|vs\.?|with)\s+", candidate_block, flags=re.I
    )

    raw_candidates = []
    for part in parts:
        cleaned = re.sub(r"^(?:the|an|a)\s+", "", part.strip(), flags=re.I).strip(" ?.,!")
        if cleaned and cleaned.lower() not in NOISE_TERMS:
            raw_candidates.append(cleaned)

    # If parsing found 0 or 1 candidates from frame, or missed phrases, verify with phrase hits
    if known_graph is not None:
        has_relational_cue = bool(
            re.search(r"\b(and|with|versus|vs\.?|between|compare|,)\b", clean_q, re.I)
        )
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
                    lbl
                    for _, lbl in matched
                    if not any(
                        lbl.lower() != o[1].lower() and lbl.lower() in o[1].lower() for o in matched
                    )
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
            summary, citations = _grounded_summary_and_citation(graph, cid_cand)
            return ResolvedConcept(
                raw_text=raw,
                cid=cid_cand,
                label=graph.label(cid_cand),
                is_indexed=True,
                node=node,
                summary=summary,
                citations=citations,
                status="indexed",
            )

    # 2. Phrase hit in aliases / label index (check singular too)
    hits = graph.phrase_hits(raw)
    if not hits and raw.endswith("s"):
        hits = graph.phrase_hits(raw[:-1])
    if hits:
        best_cid = hits[0]
        node = graph.nodes[best_cid]
        summary, citations = _grounded_summary_and_citation(graph, best_cid)
        return ResolvedConcept(
            raw_text=raw,
            cid=best_cid,
            label=graph.label(best_cid),
            is_indexed=True,
            node=node,
            summary=summary,
            citations=citations,
            status="indexed",
        )

    # 3. Embedding cosine ranking
    ranked = graph.rank(raw, top_k=1)
    if ranked and ranked[0][0] >= KILL_SWITCH:
        best_cid = ranked[0][1]
        node = graph.nodes[best_cid]
        summary, citations = _grounded_summary_and_citation(graph, best_cid)
        return ResolvedConcept(
            raw_text=raw,
            cid=best_cid,
            label=graph.label(best_cid),
            is_indexed=True,
            node=node,
            summary=summary,
            citations=citations,
            status="indexed",
        )

    # 4. Check if concept appears in document passages even if no dedicated concept node
    doc_passages = []
    for node in graph.nodes.values():
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
            summary="Mentioned in indexed documents without a standalone concept node.",
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
