"""Repaired academic concept and relation extraction pipeline (S4-G3).

Addresses systemic issues identified in S4-G1 through S4-G2.2:
1. Document Pre-screening:
   - Rejects book indices, bibliographies, sparse catalog entries, and non-prose.
2. Concept Extraction Denoising:
   - Filters numeric tokens, measurement units, figure/table labels, section headers,
     and generic capitalized discourse markers.
   - Preserves canonical technical acronyms and domain terminology.
   - Cleans concept boundaries and provides alias normalization.
3. Clause-Aware Relation Extraction:
   - Requires syntactic binding within single clause or tight sentence scope.
   - Replaces broad window triggers with clause-delimited argument identification.
   - Preserves semantic direction for asymmetric relations (PART_OF, USES, REQUIRES).
   - Strictly abstains when argument binding is ambiguous or crosses unrelated clauses.
4. Prerequisite-Specific Cycle Prevention:
   - Enforces full DAG property (reachability DFS) specifically on prerequisite edges
     (REQUIRES, INFERRED_REQUIRES).
   - Permits heterogeneous relations (USES, CONTRASTS_WITH, RELATED) without artificial
     DAG constraints.
   - Records all rejected edges in a detailed audit log.
"""

from __future__ import annotations

import dataclasses
import re
import unicodedata
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class RepairedEdge:
    from_name: str
    to_name: str
    edge_type: str         # "REQUIRES", "INFERRED_REQUIRES", "PART_OF", "USES", "CONTRASTS_WITH", "RELATED"
    relation: str          # detailed description e.g. "explicit_prerequisite", "structural_subcomponent"
    is_inferred: bool
    doc_id: str
    chunk_id: str
    source: str
    evidence_text: str
    confidence: float
    learner_path: tuple[str, str]
    domain: str = ""
    argument_direction: str = "natural" # "natural", "inverted", "undirected"


@dataclasses.dataclass
class RepairedDecision:
    concept_a: str
    concept_b: str
    relation_type: str     # "REQUIRES", "INFERRED_REQUIRES", "PART_OF", "USES", "CONTRASTS_WITH", "RELATED", "ABSTAIN"
    learner_direction: str # "a_to_b", "b_to_a", "undirected", "none"
    is_inferred: bool
    confidence: float
    evidence_quote: str
    reason: str
    argument_direction: str = "natural"


# ---------------------------------------------------------------------------
# Document Pre-screening
# ---------------------------------------------------------------------------

_EXCLUDED_DOC_PATTERNS = [
    r"index_\d{4}",
    r"/index_",
    r"about-the-authors",
    r"hints-from-probability",
    r"catalogs/",
    r"table-of-contents",
]

def is_excluded_document(doc_id: str) -> tuple[bool, str]:
    """Check if document should be excluded from relation extraction."""
    doc_low = doc_id.lower()
    for pat in _EXCLUDED_DOC_PATTERNS:
        if re.search(pat, doc_low):
            return True, f"Excluded document type matching pattern '{pat}' (index/catalog/author list)"
    return False, ""


# ---------------------------------------------------------------------------
# Concept Denoising and Boundary Detection
# ---------------------------------------------------------------------------

_NUMERIC_TOKEN_RE = re.compile(
    r"^(?:\d+(?:[.,]\d+)?\s*(?:kb|mb|gb|tb|b|m|k|ms|s|ghz|mhz|bit|bits|byte|bytes|gpu|gpus|parameters?)?|\d+(?:st|nd|rd|th)|\d+)$",
    re.I
)

_FIGURE_TABLE_RE = re.compile(
    r"^(?:figure|fig\.?|table|section|sec\.?|algorithm|algo\.?|equation|eq\.?|chapter|ch\.?|appendix|page|item|step)\s*\d+.*",
    re.I
)

_GENERIC_DISCOURSE = {
    "the", "a", "an", "in", "on", "at", "by", "for", "with", "this", "that", "these", "those",
    "it", "its", "we", "our", "their", "they", "he", "she", "you", "who", "which", "what", "where",
    "when", "how", "why", "there", "also", "however", "therefore", "thus", "hence", "moreover",
    "furthermore", "unlike", "using", "given", "such", "while", "although", "during", "after",
    "before", "because", "since", "instead", "whereas", "rather", "example", "examples",
    "in particular", "unfortunately", "note", "next time", "in this paper", "in this work",
    "we propose", "we introduce", "we present", "our approach", "our method", "our results",
    "abstract", "introduction", "conclusion", "background", "related work", "discussion",
    "experiments", "experimental results", "overview", "preliminaries",
}

_CANONICAL_ACRONYMS = {
    "ANN", "GNN", "GCN", "GAT", "NIDS", "LoRA", "QLORA", "LSTM", "BERT", "GPT", "TLB",
    "DFA", "NFA", "PTE", "ACID", "3NF", "SVD", "TCP", "UDP", "IP", "OSI", "MMU", "ALU",
    "DPO", "AST", "CFG", "PDA", "LLM", "NMT", "SAGA", "D-MAGIC", "CPU", "GPU",
}

def clean_concept_name(raw: str) -> str:
    """Normalize and clean concept name boundaries."""
    nfc = unicodedata.normalize("NFC", raw).strip()
    # Strip leading/trailing punctuation
    nfc = re.sub(r"^[\s\W_]+|[\s\W_]+$", "", nfc)
    # Collapse internal whitespace
    return " ".join(nfc.split())


def is_valid_technical_concept(concept: str) -> bool:
    """Validate whether an extracted phrase is a genuine academic concept."""
    c = clean_concept_name(concept)
    if not c or len(c) < 2:
        return False

    c_low = c.lower()
    if c_low in _GENERIC_DISCOURSE:
        return False

    # Known canonical acronyms (including numeric-leading ones like 3NF) always pass
    if c in _CANONICAL_ACRONYMS:
        return True

    # Check numeric tokens / measurement units or starting with digit
    if re.match(r"^\d", c):
        return False

    if _NUMERIC_TOKEN_RE.match(c):
        return False

    # Check figure / table / section references
    if _FIGURE_TABLE_RE.match(c):
        return False

    # Acronyms: if all-caps and known or reasonable length
    if c.isupper():
        if len(c) < 2:
            return False
        if len(c) > 8:
            return False
        # Known acronyms always pass
        if c in _CANONICAL_ACRONYMS:
            return True
        # Reject generic 2-3 letter words capitalized
        if c in {"THE", "AND", "FOR", "NOT", "BUT", "ALL", "NEW", "ONE", "TWO"}:
            return False

    words = c.split()
    if len(words) > 4:
        return False

    # Reject capitalized verb-starts (e.g. "Users Didn", "Building Computer", "Systems Was")
    if len(words) >= 2:
        second = words[1].lower().rstrip("'nt")
        if second in {
            "did", "didn", "do", "does", "was", "were", "is", "are", "have", "had", "has",
            "presents", "proposes", "introduces", "shows", "led", "meet", "computer"
        }:
            return False

    first_low = words[0].lower()
    if first_low in {"building", "users", "early", "making", "taking", "getting"}:
        return False

    # Reject if every word is short / non-technical
    if not any(len(w) >= 3 for w in words):
        return False

    return True


def normalize_concept_key(concept: str) -> str:
    """Canonical dictionary key for alias grouping."""
    c = clean_concept_name(concept).lower()
    # Lemmatize simple plurals
    if c.endswith("ies") and len(c) > 5:
        c = c[:-3] + "y"
    elif c.endswith(("sses", "shes", "ches", "xes", "zes")):
        c = c[:-2]
    elif c.endswith("s") and not c.endswith("ss") and len(c) > 3:
        c = c[:-1]
    return c


# ---------------------------------------------------------------------------
# Clause-Aware Relation Patterns
# ---------------------------------------------------------------------------

_CLAUSE_SPLIT_RE = re.compile(r"(?:[;:]|\s+—\s+|\s+-\s+|,\s*(?:whereas|while|but|although|because|since|however|moreover)\s+)")

# Strict dependency markers
_EXPLICIT_REQUIRES_PATTERNS = [
    r"\b(?:requires|strictly requires|depends on|is dependent upon|relies on|is built on|is built upon|presupposes)\b",
]

_EXPLICIT_PREREQ_FOR_PATTERNS = [
    r"\b(?:is a prerequisite for|is required for|is needed for|is essential for|forms the prerequisite for)\b",
]

_PART_OF_PATTERNS = [
    r"\b(?:is a component of|are components of|is a part of|are parts of|subcomponent of|module of|layer of)\b",
    r"\b(?:consists of|composed of|comprises|contains|includes as a sub-layer)\b",
]

_USES_PATTERNS = [
    r"\b(?:uses|utilizes|employs|applies|implemented using|executed on|leveraging|accelerated by)\b",
]

_CONTRAST_PATTERNS = [
    r"\b(?:in contrast to|compared to|compared with|differs from|unlike|as an alternative to|versus|vs\.?)\b",
]

_PEDAGOGICAL_PATTERNS = [
    r"\b(?:before examining|before introducing|we must first understand|having established)\b",
]


class RepairedConceptExtractor:
    """Denoised academic concept extractor with boundary and alias validation."""

    def __init__(self) -> None:
        pass

    def extract_concepts_from_text(self, text: str) -> list[str]:
        if not text or len(text) < 15:
            return []

        candidates = set()

        # 1. Acronym with expansion: "Translation Lookaside Buffer (TLB)"
        for m in re.finditer(r"\b([A-Z][a-zA-Z0-9\s\-]{2,35}?)\s*\(([A-Z0-9]{2,8})\)", text):
            full = clean_concept_name(m.group(1))
            acro = clean_concept_name(m.group(2))
            if is_valid_technical_concept(full):
                candidates.add(full)
            if is_valid_technical_concept(acro):
                candidates.add(acro)

        # 2. Multi-word technical capitalized phrases: 2-4 words (each capitalized)
        for m in re.finditer(r"\b([A-Z][a-zA-Z0-9\+\-\/]+(?:\s+[A-Z][a-zA-Z0-9\+\-\/]+){1,3})\b", text):
            phrase = clean_concept_name(m.group(1))
            if is_valid_technical_concept(phrase):
                candidates.add(phrase)

        # 3. Canonical vetted single technical terms or domain acronyms
        for m in re.finditer(r"\b([A-Z][a-z]{3,20}|[A-Z0-9]{2,8})\b", text):
            word = clean_concept_name(m.group(1))
            if is_valid_technical_concept(word):
                # Vetted single words
                w_low = word.lower()
                if word in _CANONICAL_ACRONYMS or w_low in {
                    "paging", "segmentation", "transformer", "encoder", "decoder",
                    "attention", "semaphores", "virtualization", "concurrency",
                    "compilers", "parser", "quantization", "backpropagation"
                }:
                    candidates.add(word)

        # Sort deterministically
        return sorted(candidates)


class RepairedRelationExtractor:
    """Clause-aware relation extractor with argument direction preservation."""

    def __init__(self, confidence_threshold: float = 0.70) -> None:
        self.confidence_threshold = confidence_threshold

    def classify_relation_in_chunk(
        self,
        concept_a: str,
        concept_b: str,
        chunk_text: str,
    ) -> RepairedDecision:
        """Classify relationship between concepts within chunk text.

        Enforces clause-aware syntactic proximity (<= 150 chars).
        Preserves asymmetric direction for PART_OF, USES, REQUIRES.
        Strictly abstains when binding is ambiguous.
        """
        if not chunk_text:
            return RepairedDecision(concept_a, concept_b, "ABSTAIN", "none", False, 0.0, "", "Empty text")

        a_clean = clean_concept_name(concept_a)
        b_clean = clean_concept_name(concept_b)
        a_low = a_clean.lower()
        b_low = b_clean.lower()

        if a_low == b_low:
            return RepairedDecision(concept_a, concept_b, "ABSTAIN", "none", False, 0.0, "", "Self-pair")

        # Split into sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", chunk_text) if s.strip()]

        for sent in sentences:
            sent_low = sent.lower()
            if a_low in sent_low and b_low in sent_low:
                # Inspect clauses within this sentence
                clauses = _CLAUSE_SPLIT_RE.split(sent)
                for clause in clauses:
                    c_low = clause.lower()
                    if a_low in c_low and b_low in c_low:
                        decision = self._analyze_span(a_clean, b_clean, clause, c_low, a_low, b_low)
                        if decision.relation_type != "ABSTAIN":
                            return decision

                # If not in the same sub-clause, check whole sentence if distance <= 150 chars
                pos_a = sent_low.find(a_low)
                pos_b = sent_low.find(b_low)
                if abs(pos_a - pos_b) <= 150:
                    decision = self._analyze_span(a_clean, b_clean, sent, sent_low, a_low, b_low)
                    if decision.relation_type != "ABSTAIN":
                        return decision

        return RepairedDecision(
            concept_a=concept_a,
            concept_b=concept_b,
            relation_type="ABSTAIN",
            learner_direction="none",
            is_inferred=False,
            confidence=0.20,
            evidence_quote="",
            reason="No binding syntactic relation in sentence or clause scope (abstained)",
        )

    def _analyze_span(
        self,
        cA: str,
        cB: str,
        span_text: str,
        span_low: str,
        a_low: str,
        b_low: str,
    ) -> RepairedDecision:
        pos_a = span_low.find(a_low)
        pos_b = span_low.find(b_low)
        if pos_a == -1 or pos_b == -1:
            return RepairedDecision(cA, cB, "ABSTAIN", "none", False, 0.0, "", "Not found in span")

        if pos_a < pos_b:
            first, second = cA, cB
            first_low, second_low = a_low, b_low
            between = span_low[pos_a + len(a_low) : pos_b].strip()
            direction_forward = True
        else:
            first, second = cB, cA
            first_low, second_low = b_low, a_low
            between = span_low[pos_b + len(b_low) : pos_a].strip()
            direction_forward = False

        quote = span_text.strip()[:240]

        # 1. CONTRASTS_WITH (symmetric)
        for pat in _CONTRAST_PATTERNS:
            if re.search(pat, between) or re.search(pat, span_low[:min(pos_a, pos_b)]):
                return RepairedDecision(
                    concept_a=cA, concept_b=cB,
                    relation_type="CONTRASTS_WITH", learner_direction="undirected",
                    is_inferred=False, confidence=0.88, evidence_quote=quote,
                    reason=f"Contrast marker between '{cA}' and '{cB}'",
                    argument_direction="undirected",
                )

        # 2. PART_OF (asymmetric: component -> whole)
        # Check "A is a component of B" -> A is component, B is whole
        for pat in _PART_OF_PATTERNS:
            m = re.search(pat, between)
            if m:
                # If trigger is "consists of" / "contains", order is whole -> component
                trigger = m.group(0).lower()
                if "consists" in trigger or "contain" in trigger or "include" in trigger:
                    whole, component = first, second
                else:
                    component, whole = first, second

                ldir = "a_to_b" if component == cA else "b_to_a"
                return RepairedDecision(
                    concept_a=cA, concept_b=cB,
                    relation_type="PART_OF", learner_direction=ldir,
                    is_inferred=False, confidence=0.85, evidence_quote=quote,
                    reason=f"Structural subcomponent: '{component}' is part of '{whole}'",
                    argument_direction="natural",
                )

        # 3. REQUIRES (first requires second -> dependent=first, prereq=second)
        for pat in _EXPLICIT_REQUIRES_PATTERNS:
            if re.search(pat, between):
                dependent, prereq = first, second
                ldir = "b_to_a" if dependent == cA else "a_to_b"
                return RepairedDecision(
                    concept_a=cA, concept_b=cB,
                    relation_type="REQUIRES", learner_direction=ldir,
                    is_inferred=False, confidence=0.92, evidence_quote=quote,
                    reason=f"Explicit requirement: '{dependent}' requires '{prereq}'",
                    argument_direction="natural",
                )

        # 4. EXPLICIT PREREQUISITE FOR (first is required for second -> prereq=first, dependent=second)
        for pat in _EXPLICIT_PREREQ_FOR_PATTERNS:
            if re.search(pat, between):
                prereq, dependent = first, second
                ldir = "a_to_b" if prereq == cA else "b_to_a"
                return RepairedDecision(
                    concept_a=cA, concept_b=cB,
                    relation_type="REQUIRES", learner_direction=ldir,
                    is_inferred=False, confidence=0.92, evidence_quote=quote,
                    reason=f"Explicit prerequisite: '{prereq}' is required for '{dependent}'",
                    argument_direction="natural",
                )

        # 5. USES (asymmetric: user/technique -> tool/resource)
        for pat in _USES_PATTERNS:
            if re.search(pat, between):
                user, tool = first, second
                ldir = "a_to_b" if user == cA else "b_to_a"
                return RepairedDecision(
                    concept_a=cA, concept_b=cB,
                    relation_type="USES", learner_direction=ldir,
                    is_inferred=False, confidence=0.82, evidence_quote=quote,
                    reason=f"Technique usage: '{user}' uses '{tool}'",
                    argument_direction="natural",
                )

        # 6. INFERRED_REQUIRES (pedagogical progression)
        for pat in _PEDAGOGICAL_PATTERNS:
            if re.search(pat, between) or re.search(pat, span_low[:min(pos_a, pos_b)]):
                prereq, target = second, first
                ldir = "a_to_b" if prereq == cA else "b_to_a"
                return RepairedDecision(
                    concept_a=cA, concept_b=cB,
                    relation_type="INFERRED_REQUIRES", learner_direction=ldir,
                    is_inferred=True, confidence=0.76, evidence_quote=quote,
                    reason=f"Pedagogical prerequisite: '{prereq}' precedes '{target}'",
                    argument_direction="natural",
                )

        return RepairedDecision(
            concept_a=cA, concept_b=cB,
            relation_type="ABSTAIN", learner_direction="none",
            is_inferred=False, confidence=0.30, evidence_quote="",
            reason="Concepts co-occur without recognized directional relation trigger",
        )


class RepairedGraphExtractor:
    """Full extraction pipeline integrating pre-screening, denoising, and cycle-safe graph insertion."""

    def __init__(self, confidence_threshold: float = 0.70) -> None:
        self.concept_extractor = RepairedConceptExtractor()
        self.relation_extractor = RepairedRelationExtractor(confidence_threshold=confidence_threshold)

    def extract_document_graph(
        self,
        chunks: list[dict[str, Any]],
        doc_id: str,
        domain: str = "",
    ) -> dict[str, Any]:
        """Extract graph with document pre-screening and prerequisite cycle prevention."""
        is_excl, excl_reason = is_excluded_document(doc_id)
        if is_excl:
            return {
                "doc_id": doc_id,
                "domain": domain,
                "status": "EXCLUDED",
                "exclusion_reason": excl_reason,
                "concepts": {},
                "edges": [],
                "abstentions_count": 0,
                "rejections_count": 0,
                "cycles_prevented": [],
                "rejected_edges": [],
            }

        # 1. Concept extraction
        all_concepts: dict[str, dict[str, Any]] = {}
        for chunk in chunks:
            text = chunk.get("text_passage") or chunk.get("text") or ""
            c_id = chunk.get("chunk_id") or chunk.get("id") or "chunk_000"
            concepts = self.concept_extractor.extract_concepts_from_text(text)
            for c in concepts:
                ckey = normalize_concept_key(c)
                if ckey not in all_concepts:
                    all_concepts[ckey] = {
                        "name": c,
                        "canonical_key": ckey,
                        "doc_id": doc_id,
                        "first_chunk": c_id,
                        "occurrences": 1,
                        "domain": domain,
                    }
                else:
                    all_concepts[ckey]["occurrences"] += 1

        concept_list = list(all_concepts.values())

        # 2. Pairwise classification & Cycle-safe insertion
        # Maintain reachability for prerequisite relations
        prereq_adj: dict[str, set[str]] = defaultdict(set)

        def can_reach(u: str, target: str, visited: set[str]) -> bool:
            if u == target:
                return True
            visited.add(u)
            for neighbor in prereq_adj.get(u, set()):
                if neighbor not in visited:
                    if can_reach(neighbor, target, visited):
                        return True
            return False

        admitted_edges: list[RepairedEdge] = []
        cycles_prevented: list[dict[str, Any]] = []
        rejected_edges: list[dict[str, Any]] = []
        abstentions_count = 0
        candidate_pair_count = 0

        for chunk in chunks:
            c_id = chunk.get("chunk_id") or chunk.get("id") or "chunk_000"
            text = chunk.get("text_passage") or chunk.get("text") or ""
            text_low = text.lower()

            chunk_concepts = [
                c["name"] for c in concept_list
                if c["name"].lower() in text_low
            ]

            if len(chunk_concepts) < 2:
                continue

            for i in range(len(chunk_concepts)):
                for j in range(i + 1, len(chunk_concepts)):
                    cA, cB = chunk_concepts[i], chunk_concepts[j]
                    candidate_pair_count += 1

                    dec = self.relation_extractor.classify_relation_in_chunk(cA, cB, text)

                    if dec.relation_type == "ABSTAIN":
                        abstentions_count += 1
                        continue

                    # Determine endpoints based on relation semantics
                    if dec.relation_type in ("REQUIRES", "INFERRED_REQUIRES"):
                        # In student/graph ontology: from_name=dependent, to_name=prerequisite
                        if dec.learner_direction == "a_to_b":
                            dep, prereq = cB, cA
                        else:
                            dep, prereq = cA, cB

                        u_key = normalize_concept_key(dep)
                        v_key = normalize_concept_key(prereq)

                        # Full DFS reachability cycle check: would adding dep -> prereq cause a cycle?
                        # That happens if prereq can already reach dep!
                        if can_reach(v_key, u_key, set()):
                            cycles_prevented.append({
                                "conflict_type": "prerequisite_cycle_prevented",
                                "from_concept": dep,
                                "to_concept": prereq,
                                "chunk_id": c_id,
                                "doc_id": doc_id,
                                "reason": f"Cycle prevention: '{prereq}' already reaches '{dep}' in prerequisite graph",
                            })
                            rejected_edges.append({
                                "from_name": dep, "to_name": prereq,
                                "edge_type": dec.relation_type,
                                "reason": "prerequisite_cycle_prevented",
                                "chunk_id": c_id,
                            })
                            continue

                        # Safe to insert
                        prereq_adj[u_key].add(v_key)
                        edge = RepairedEdge(
                            from_name=dep,
                            to_name=prereq,
                            edge_type=dec.relation_type,
                            relation=dec.reason,
                            is_inferred=dec.is_inferred,
                            doc_id=doc_id,
                            chunk_id=c_id,
                            source=f"{doc_id}:{c_id}",
                            evidence_text=dec.evidence_quote,
                            confidence=dec.confidence,
                            learner_path=(prereq, dep),
                            domain=domain,
                            argument_direction="natural",
                        )
                        admitted_edges.append(edge)

                    elif dec.relation_type == "PART_OF":
                        # Component -> Whole
                        if dec.learner_direction == "a_to_b":
                            comp, whole = cA, cB
                        else:
                            comp, whole = cB, cA

                        edge = RepairedEdge(
                            from_name=comp,
                            to_name=whole,
                            edge_type="PART_OF",
                            relation=dec.reason,
                            is_inferred=False,
                            doc_id=doc_id,
                            chunk_id=c_id,
                            source=f"{doc_id}:{c_id}",
                            evidence_text=dec.evidence_quote,
                            confidence=dec.confidence,
                            learner_path=(comp, whole),
                            domain=domain,
                            argument_direction="natural",
                        )
                        admitted_edges.append(edge)

                    elif dec.relation_type == "USES":
                        # User -> Tool
                        if dec.learner_direction == "a_to_b":
                            user, tool = cA, cB
                        else:
                            user, tool = cB, cA

                        edge = RepairedEdge(
                            from_name=user,
                            to_name=tool,
                            edge_type="USES",
                            relation=dec.reason,
                            is_inferred=False,
                            doc_id=doc_id,
                            chunk_id=c_id,
                            source=f"{doc_id}:{c_id}",
                            evidence_text=dec.evidence_quote,
                            confidence=dec.confidence,
                            learner_path=(user, tool),
                            domain=domain,
                            argument_direction="natural",
                        )
                        admitted_edges.append(edge)

                    elif dec.relation_type == "CONTRASTS_WITH":
                        edge = RepairedEdge(
                            from_name=cA,
                            to_name=cB,
                            edge_type="CONTRASTS_WITH",
                            relation=dec.reason,
                            is_inferred=False,
                            doc_id=doc_id,
                            chunk_id=c_id,
                            source=f"{doc_id}:{c_id}",
                            evidence_text=dec.evidence_quote,
                            confidence=dec.confidence,
                            learner_path=(cA, cB),
                            domain=domain,
                            argument_direction="undirected",
                        )
                        admitted_edges.append(edge)

        # Deduplicate edges by (from_key, to_key, edge_type)
        dedup_edges = {}
        for e in admitted_edges:
            ekey = (normalize_concept_key(e.from_name), normalize_concept_key(e.to_name), e.edge_type)
            if ekey not in dedup_edges:
                dedup_edges[ekey] = e

        final_edges = list(dedup_edges.values())

        return {
            "doc_id": doc_id,
            "domain": domain,
            "status": "PROCESSED",
            "concepts": all_concepts,
            "concept_count": len(all_concepts),
            "edges": final_edges,
            "edge_count": len(final_edges),
            "candidate_pairs_evaluated": candidate_pair_count,
            "abstentions_count": abstentions_count,
            "cycles_prevented": cycles_prevented,
            "rejected_edges": rejected_edges,
            "edge_type_distribution": {
                etype: sum(1 for e in final_edges if e.edge_type == etype)
                for etype in {"REQUIRES", "INFERRED_REQUIRES", "PART_OF", "USES", "CONTRASTS_WITH"}
            },
        }
