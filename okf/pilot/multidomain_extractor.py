"""S4-G2: Multi-Domain Evidence-Grounded Graph Extraction Engine.

Implements domain-general concept extraction, relation classification,
and explicit vs inferred prerequisite reasoning across all 12 academic domains:
1. Operating Systems
2. Database Management Systems
3. Data Structures & Algorithms
4. Computer Networks
5. Compilers & Programming Languages
6. Automata Theory & Computation
7. Mathematics for Computing
8. Probability & Statistics
9. Information Security
10. Artificial Intelligence & Machine Learning
11. Software Engineering
12. Computer Organization & Architecture

Key architectural capabilities:
1. Multi-domain technical terminology and phrase extraction (OS, DBMS, NetSec, TOC, Math, ML).
2. Distinction between EXPLICIT prerequisites, INFERRED pedagogical prerequisites,
   PART_OF (composition), USES (technique usage), CONTRASTS_WITH (alternatives),
   and ABSTAIN (insufficient evidence).
3. Inferred pedagogical dependencies are explicitly marked (is_inferred=True)
   and supported by structured pedagogical evidence.
4. Windowed multi-sentence context analysis (within chunk) to capture
   inter-sentence pedagogical progression.
5. Strict abstention on unsupported co-occurrences without alphabetical or position fallbacks.
6. Insertion-time cycle prevention and complete provenance retention.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any

from okf.canonicalize import _concept_key, canonicalize_name
from okf.eval.gold.part01_load_gold_graph import _canonical_key


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclasses.dataclass
class MultiDomainEdge:
    from_name: str
    to_name: str
    edge_type: str         # "REQUIRES", "UNLOCKS", "RELATED"
    relation: str          # "explicit_prerequisite", "inferred_pedagogical_prerequisite", "enables", "part_of", "uses", "contrasts_with", "related"
    is_inferred: bool      # True for pedagogical curriculum inference, False for explicit textual assertion
    doc_id: str
    chunk_id: str
    source: str            # f"{doc_id}:{chunk_id}"
    evidence_text: str
    confidence: float
    learner_path: tuple[str, str]  # (prerequisite, dependent) for pedagogical learning order
    domain: str = ""


@dataclasses.dataclass
class MultiDomainDecision:
    concept_a: str
    concept_b: str
    relation_type: str     # "EXPLICIT_PREREQUISITE", "INFERRED_PREREQUISITE", "UNLOCKS", "PART_OF", "USES", "CONTRASTS_WITH", "RELATED", "ABSTAIN"
    learner_direction: str # "a_to_b" (a is prereq of b), "b_to_a" (b is prereq of a), "undirected", "none"
    is_inferred: bool
    confidence: float
    evidence_quote: str
    reason: str


# ---------------------------------------------------------------------------
# Linguistic patterns across all academic domains
# ---------------------------------------------------------------------------

# Explicit prerequisite markers (A depends on B -> B is prerequisite of A -> learner path B -> A)
_EXPLICIT_DEPENDS_ON_PATTERNS = [
    r"\b(requires|depends on|is built on|is built upon|relies on|is based on|assumes|conditioned on|derived from|building on|extending)\b",
    r"\b(cannot be understood without|strictly requires|prerequisite knowledge of)\b",
]

# Explicit prerequisite markers (A is prerequisite for B -> A is prerequisite of B -> learner path A -> B)
_EXPLICIT_PREREQ_FOR_PATTERNS = [
    r"\b(is a prerequisite for|is required for|is needed for|is essential for|prerequisite of|necessary foundation for)\b",
]

# Inferred pedagogical prerequisite markers (educational transition across sentences or clauses)
_INFERRED_PEDAGOGICAL_PATTERNS = [
    r"\b(before (?:examining|studying|introducing|discussing|implementing))\b",
    r"\b(we must first (?:understand|examine|review|introduce|study))\b",
    r"\b(having (?:established|introduced|reviewed|studied))\b",
    r"\b(is defined in terms of|is formulated using the concept of|builds upon the foundation of)\b",
    r"\b(to understand [a-zA-Z0-9_\-\s]{2,30}, we first)\b",
]

# Forward enablement markers (A enables B -> A is prerequisite of B -> learner path A -> B)
_ENABLES_PATTERNS = [
    r"\b(enables|allows for|allows(?: us)? to|unlocks|lays the groundwork for|forms the basis of|provides the foundation for|leads directly to)\b",
]

# Structural subcomponent markers (architectural composition -> non-prerequisite RELATED)
_PART_OF_PATTERNS = [
    r"\b(?:is|are)?\s*(?:a\s+)?components?\s+of\b",
    r"\b(?:is|are)?\s*(?:a\s+)?parts?\s+of\b",
    r"\b(?:consists? of|composed of|elements? of|modules? of|layers? of|subcomponents? of|entries in|entry in)\b",
]

# Empirical tool / hardware / technique usage markers (technique application -> non-prerequisite RELATED)
_USAGE_PATTERNS = [
    r"\b(uses|utilizes|employs|applies|using|optimized with|evaluated with|by optimizing|implemented using|executed by|hardware acceleration using)\b",
]

# Contrast / Alternative comparison markers (competing methods -> non-prerequisite RELATED)
_CONTRAST_PATTERNS = [
    r"\b(in contrast to|compared to|compared with|differs from|unlike|as an alternative to|versus|vs\.?|performs on-par or better than|outperforms|contrasting)\b",
]


class MultiDomainExtractor:
    """Domain-general, evidence-grounded academic concept and relation extractor."""

    def __init__(self, confidence_threshold: float = 0.65) -> None:
        self.confidence_threshold = confidence_threshold

    def extract_domain_concepts(self, chunk_text: str) -> list[str]:
        """Extract multi-domain academic technical concepts from chunk text.

        Covers Operating Systems, DBMS, Networks, Compilers, Automata, Math,
        Probability, Security, and AI/ML. Avoids generic conversational stopwords.
        """
        if not chunk_text or len(chunk_text) < 15:
            return []

        stopwords = {
            "this", "that", "these", "those", "such", "which", "there", "their", "where",
            "section", "figure", "table", "paper", "author", "authors", "approach",
            "method", "model", "results", "experiment", "experiments", "baseline", "baselines",
            "performance", "training", "parameters", "dataset", "datasets", "task", "tasks",
            "table 1", "table 2", "figure 1", "figure 2", "appendix", "introduction",
            "chapter", "page", "pages", "note", "example", "problem", "solution", "system",
            "systems", "algorithm", "algorithms", "data", "process", "processes", "case"
        }

        candidates = set()

        # 1. Acronyms with full expansions: e.g. "Translation Lookaside Buffer (TLB)", "Virtual Memory (VM)"
        acro_exp_matches = re.finditer(
            r"\b([A-Z][a-zA-Z0-9\s\-]{2,40}?)\s*\(([A-Z0-9]{2,8})\)", chunk_text
        )
        for m in acro_exp_matches:
            full = m.group(1).strip()
            acro = m.group(2).strip()
            if full.lower() not in stopwords and len(full) >= 4:
                candidates.add(full)
            if acro.lower() not in stopwords:
                candidates.add(acro)

        # 2. Multi-word technical capitalized phrases (Title Case or compound nouns)
        # Matches 2 to 4 capitalized words: e.g. "Virtual Memory", "Page Table", "B+ Tree"
        phrase_matches = re.finditer(r"\b([A-Z][a-zA-Z0-9\+\-\/]+(?:\s+[A-Z][a-zA-Z0-9\+\-\/]+){1,3})\b", chunk_text)
        for m in phrase_matches:
            phrase = m.group(1).strip()
            if phrase.lower() not in stopwords and len(phrase) >= 4:
                candidates.add(phrase)

        # 3. Canonical Single Technical Nouns (e.g. "Paging", "Segmentation", "Transformer", "Semaphores")
        single_matches = re.finditer(r"\b([A-Z][a-z]{3,20})\b", chunk_text)
        for m in single_matches:
            word = m.group(1).strip()
            if word.lower() not in stopwords:
                candidates.add(word)

        # 4. All-caps technical acronyms (e.g. "TLB", "DFA", "NFA", "PTE", "ACID", "3NF", "SVD", "TCP", "UDP", "IPsec", "MMU", "ALU", "BERT", "GPT")
        caps_matches = re.finditer(r"\b([A-Z0-9]{2,8})\b", chunk_text)
        for m in caps_matches:
            acro = m.group(1).strip()
            if acro.lower() not in stopwords and len(acro) >= 2:
                candidates.add(acro)

        # 5. Hyphenated technical terms (e.g. "Two-Phase", "Base-and-Bounds", "Multi-Head", "Low-Rank")
        hyphen_matches = re.finditer(r"\b([A-Z][a-zA-Z0-9]+-[A-Z][a-zA-Z0-9]+(?:\s+[A-Z][a-zA-Z0-9]+)?)\b", chunk_text)
        for m in hyphen_matches:
            term = m.group(1).strip()
            if term.lower() not in stopwords:
                candidates.add(term)

        # Clean and sort candidates
        cleaned = []
        for c in sorted(candidates):
            c_norm = c.strip()
            if len(c_norm) >= 2 and c_norm.lower() not in stopwords:
                cleaned.append(c_norm)

        return cleaned

    def classify_relation_with_evidence(
        self,
        concept_a: str,
        concept_b: str,
        chunk: dict[str, Any],
    ) -> MultiDomainDecision:
        """Classify the relationship between concept_a and concept_b.

        Examines both sentence-level contexts and adjacent 2-sentence windows.
        Differentiates explicit prerequisites, inferred pedagogical prerequisites,
        PART_OF, USES, CONTRASTS_WITH, and ABSTAIN.
        """
        text = chunk.get("text_passage") or chunk.get("text") or ""
        if not text:
            return MultiDomainDecision(
                concept_a=concept_a, concept_b=concept_b,
                relation_type="ABSTAIN", learner_direction="none",
                is_inferred=False, confidence=0.0, evidence_quote="",
                reason="Empty text passage",
            )

        a_lower = concept_a.strip().lower()
        b_lower = concept_b.strip().lower()

        if a_lower == b_lower:
            return MultiDomainDecision(
                concept_a=concept_a, concept_b=concept_b,
                relation_type="ABSTAIN", learner_direction="none",
                is_inferred=False, confidence=0.0, evidence_quote="",
                reason="Self-referential concept pair",
            )

        # Split into sentences
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]

        # 1. First search in single sentences containing both concepts
        for sent in sentences:
            sent_low = sent.lower()
            if a_lower in sent_low and b_lower in sent_low:
                decision = self._analyze_text_segment(
                    concept_a, concept_b, sent, sent_low, a_lower, b_lower, is_window=False
                )
                if decision.relation_type != "ABSTAIN":
                    return decision

        # 2. Next search in adjacent 2-sentence windows within chunk for pedagogical transitions
        for idx in range(len(sentences) - 1):
            window = sentences[idx] + " " + sentences[idx + 1]
            window_low = window.lower()
            if a_lower in window_low and b_lower in window_low:
                decision = self._analyze_text_segment(
                    concept_a, concept_b, window, window_low, a_lower, b_lower, is_window=True
                )
                if decision.relation_type != "ABSTAIN":
                    return decision

        # If co-occurring without relational markers, strictly abstain
        sample_evidence = ""
        for s in sentences:
            if a_lower in s.lower() or b_lower in s.lower():
                sample_evidence = s[:180]
                break

        return MultiDomainDecision(
            concept_a=concept_a, concept_b=concept_b,
            relation_type="ABSTAIN", learner_direction="none",
            is_inferred=False, confidence=0.25, evidence_quote=sample_evidence,
            reason="Co-occurrence without explicit or pedagogical dependency evidence (abstained to prevent hallucinated dependency)",
        )

    def _analyze_text_segment(
        self,
        concept_a: str,
        concept_b: str,
        text_segment: str,
        text_low: str,
        a_lower: str,
        b_lower: str,
        is_window: bool,
    ) -> MultiDomainDecision:
        """Analyze a single sentence or 2-sentence window containing both concepts."""
        m_a = list(re.finditer(r"\b" + re.escape(a_lower) + r"\b", text_low))
        m_b = list(re.finditer(r"\b" + re.escape(b_lower) + r"\b", text_low))

        if not m_a or not m_b:
            idx_a = text_low.find(a_lower)
            idx_b = text_low.find(b_lower)
            if idx_a == -1 or idx_b == -1:
                return MultiDomainDecision(
                    concept_a=concept_a, concept_b=concept_b,
                    relation_type="ABSTAIN", learner_direction="none",
                    is_inferred=False, confidence=0.0, evidence_quote="",
                    reason="Exact concept text boundary match not found",
                )
            if idx_a < idx_b:
                first_c, second_c = (concept_a, concept_b)
                between = text_low[idx_a + len(a_lower) : idx_b].strip()
                before = text_low[:idx_a].strip()
            else:
                first_c, second_c = (concept_b, concept_a)
                between = text_low[idx_b + len(b_lower) : idx_a].strip()
                before = text_low[:idx_b].strip()
        else:
            best_pair = min(
                ((ma, mb) for ma in m_a for mb in m_b),
                key=lambda p: abs(p[0].start() - p[1].start()),
            )
            ma, mb = best_pair
            if ma.start() < mb.start():
                first_c, second_c = (concept_a, concept_b)
                between = text_low[ma.end() : mb.start()].strip()
                before = text_low[:ma.start()].strip()
            else:
                first_c, second_c = (concept_b, concept_a)
                between = text_low[mb.end() : ma.start()].strip()
                before = text_low[:mb.start()].strip()

        quote = text_segment[:200]

        # 1. CONTRAST / ALTERNATIVE (e.g. "unlike X, Y" or "X differs from Y")
        contrast_re = re.compile("|".join(_CONTRAST_PATTERNS))
        if contrast_re.search(between) or (not is_window and contrast_re.search(before)):
            return MultiDomainDecision(
                concept_a=concept_a, concept_b=concept_b,
                relation_type="CONTRASTS_WITH", learner_direction="undirected",
                is_inferred=False, confidence=0.85, evidence_quote=quote,
                reason=f"Linguistic contrast marker between '{first_c}' and '{second_c}'",
            )

        # 2. PART_OF (e.g. "X is a component of Y")
        part_of_re = re.compile("|".join(_PART_OF_PATTERNS))
        if part_of_re.search(between):
            return MultiDomainDecision(
                concept_a=concept_a, concept_b=concept_b,
                relation_type="PART_OF", learner_direction="undirected",
                is_inferred=False, confidence=0.80, evidence_quote=quote,
                reason=f"Structural subcomponent marker between '{first_c}' and '{second_c}'",
            )

        # 3. EXPLICIT PREREQUISITE FOR / REQUIRED FOR (first is prerequisite of second)
        prereq_for_re = re.compile("|".join(_EXPLICIT_PREREQ_FOR_PATTERNS))
        if prereq_for_re.search(between):
            ldir = "a_to_b" if first_c == concept_a else "b_to_a"
            return MultiDomainDecision(
                concept_a=concept_a, concept_b=concept_b,
                relation_type="EXPLICIT_PREREQUISITE", learner_direction=ldir,
                is_inferred=False, confidence=0.90, evidence_quote=quote,
                reason=f"Explicit prerequisite marker: '{first_c}' is prerequisite for '{second_c}'",
            )

        # 4. EXPLICIT DEPENDENCY (first depends on second -> second is prerequisite of first)
        depends_on_re = re.compile("|".join(_EXPLICIT_DEPENDS_ON_PATTERNS))
        if depends_on_re.search(between):
            ldir = "b_to_a" if first_c == concept_a else "a_to_b"
            return MultiDomainDecision(
                concept_a=concept_a, concept_b=concept_b,
                relation_type="EXPLICIT_PREREQUISITE", learner_direction=ldir,
                is_inferred=False, confidence=0.85, evidence_quote=quote,
                reason=f"Explicit dependency marker: '{first_c}' depends on '{second_c}'",
            )

        # 5. INFERRED PEDAGOGICAL PREREQUISITE (educational curriculum transition)
        pedagogical_re = re.compile("|".join(_INFERRED_PEDAGOGICAL_PATTERNS))
        if pedagogical_re.search(between) or (not is_window and pedagogical_re.search(before)):
            # If "before examining X, we first study Y" -> Y is prerequisite of X
            ldir = "b_to_a" if first_c == concept_a else "a_to_b"
            return MultiDomainDecision(
                concept_a=concept_a, concept_b=concept_b,
                relation_type="INFERRED_PREREQUISITE", learner_direction=ldir,
                is_inferred=True, confidence=0.75, evidence_quote=quote,
                reason=f"Inferred pedagogical prerequisite: curriculum progression from '{second_c}' to '{first_c}'",
            )

        # 6. FORWARD ENABLEMENT (first enables second -> first is prerequisite of second)
        enables_re = re.compile("|".join(_ENABLES_PATTERNS))
        if enables_re.search(between):
            ldir = "a_to_b" if first_c == concept_a else "b_to_a"
            return MultiDomainDecision(
                concept_a=concept_a, concept_b=concept_b,
                relation_type="UNLOCKS", learner_direction=ldir,
                is_inferred=False, confidence=0.85, evidence_quote=quote,
                reason=f"Explicit enablement marker: '{first_c}' enables '{second_c}'",
            )

        # 7. USAGE (empirical tool / technique / hardware application)
        usage_re = re.compile("|".join(_USAGE_PATTERNS))
        if usage_re.search(between) or (not is_window and usage_re.search(before)):
            return MultiDomainDecision(
                concept_a=concept_a, concept_b=concept_b,
                relation_type="USES", learner_direction="undirected",
                is_inferred=False, confidence=0.75, evidence_quote=quote,
                reason=f"Technique usage / tool application marker between '{first_c}' and '{second_c}'",
            )

        return MultiDomainDecision(
            concept_a=concept_a, concept_b=concept_b,
            relation_type="ABSTAIN", learner_direction="none",
            is_inferred=False, confidence=0.30, evidence_quote=quote,
            reason="Co-occurrence without explicit or pedagogical dependency evidence",
        )

    def extract_document_graph(
        self,
        chunks: list[dict[str, Any]],
        doc_id: str,
        domain: str = "",
    ) -> dict[str, Any]:
        """Extract multi-domain concepts and evidence-grounded edges from chunks."""
        all_concepts: dict[str, dict[str, Any]] = {}
        candidate_edges: list[MultiDomainEdge] = []
        abstentions: list[dict[str, Any]] = []
        rejections: list[dict[str, Any]] = []
        cycles_prevented: list[dict[str, Any]] = []

        # 1. Multi-domain concept extraction
        for chunk in chunks:
            c_id = chunk.get("chunk_id") or chunk.get("id") or "chunk_000"
            text = chunk.get("text_passage") or chunk.get("text") or ""
            names = self.extract_domain_concepts(text)
            for name in names:
                ckey = _canonical_key(name)
                if ckey not in all_concepts:
                    all_concepts[ckey] = {
                        "name": name,
                        "canonical_key": ckey,
                        "doc_id": doc_id,
                        "first_chunk": c_id,
                        "occurrences": 1,
                        "domain": domain,
                    }
                else:
                    all_concepts[ckey]["occurrences"] += 1

        concept_list = list(all_concepts.values())

        # 2. Pairwise relationship classification
        existing_prereq_paths: set[tuple[str, str]] = set()

        for chunk in chunks:
            c_id = chunk.get("chunk_id") or chunk.get("id") or "chunk_000"
            text_low = (chunk.get("text_passage") or chunk.get("text") or "").lower()

            chunk_concepts = [
                c["name"] for c in concept_list
                if c["name"].lower() in text_low
            ]

            if len(chunk_concepts) < 2:
                continue

            for i in range(len(chunk_concepts)):
                for j in range(i + 1, len(chunk_concepts)):
                    cA = chunk_concepts[i]
                    cB = chunk_concepts[j]

                    decision = self.classify_relation_with_evidence(cA, cB, chunk)

                    if decision.relation_type == "ABSTAIN":
                        abstentions.append({
                            "concept_a": cA, "concept_b": cB,
                            "chunk_id": c_id, "doc_id": doc_id,
                            "domain": domain,
                            "reason": decision.reason,
                            "evidence": decision.evidence_quote,
                        })
                        continue

                    if decision.confidence < self.confidence_threshold:
                        rejections.append({
                            "concept_a": cA, "concept_b": cB,
                            "chunk_id": c_id, "doc_id": doc_id,
                            "domain": domain,
                            "relation_type": decision.relation_type,
                            "confidence": decision.confidence,
                            "reason": f"Confidence {decision.confidence:.2f} < threshold {self.confidence_threshold:.2f}",
                        })
                        continue

                    # Handle Prerequisite and Enablement
                    if decision.relation_type in ("EXPLICIT_PREREQUISITE", "INFERRED_PREREQUISITE", "UNLOCKS"):
                        if decision.learner_direction == "a_to_b":
                            prereq, dep = cA, cB
                        elif decision.learner_direction == "b_to_a":
                            prereq, dep = cB, cA
                        else:
                            abstentions.append({
                                "concept_a": cA, "concept_b": cB,
                                "chunk_id": c_id, "doc_id": doc_id,
                                "domain": domain,
                                "reason": "Undirected dependency direction could not be verified",
                                "evidence": decision.evidence_quote,
                            })
                            continue

                        prereq_key = _canonical_key(prereq)
                        dep_key = _canonical_key(dep)

                        # Insertion-time cycle check: (dep, prereq) already exists
                        if (dep_key, prereq_key) in existing_prereq_paths:
                            cycles_prevented.append({
                                "conflict_type": "reciprocal_cycle",
                                "existing_edge": (dep, prereq),
                                "blocked_edge": (prereq, dep),
                                "chunk_id": c_id,
                                "domain": domain,
                                "evidence": decision.evidence_quote,
                            })
                            continue

                        existing_prereq_paths.add((prereq_key, dep_key))

                        # Determine edge representation
                        if decision.relation_type in ("EXPLICIT_PREREQUISITE", "INFERRED_PREREQUISITE"):
                            edge = MultiDomainEdge(
                                from_name=dep,
                                to_name=prereq,
                                edge_type="REQUIRES",
                                relation=decision.relation_type.lower(),
                                is_inferred=decision.is_inferred,
                                doc_id=doc_id,
                                chunk_id=c_id,
                                source=f"{doc_id}:{c_id}",
                                evidence_text=decision.evidence_quote,
                                confidence=decision.confidence,
                                learner_path=(prereq, dep),
                                domain=domain,
                            )
                        else:  # UNLOCKS
                            edge = MultiDomainEdge(
                                from_name=prereq,
                                to_name=dep,
                                edge_type="UNLOCKS",
                                relation="enables",
                                is_inferred=False,
                                doc_id=doc_id,
                                chunk_id=c_id,
                                source=f"{doc_id}:{c_id}",
                                evidence_text=decision.evidence_quote,
                                confidence=decision.confidence,
                                learner_path=(prereq, dep),
                                domain=domain,
                            )
                        candidate_edges.append(edge)

                    else:
                        # Non-prerequisite relationships: PART_OF, USES, CONTRASTS_WITH, RELATED
                        edge = MultiDomainEdge(
                            from_name=cA,
                            to_name=cB,
                            edge_type="RELATED",
                            relation=decision.relation_type.lower(),
                            is_inferred=False,
                            doc_id=doc_id,
                            chunk_id=c_id,
                            source=f"{doc_id}:{c_id}",
                            evidence_text=decision.evidence_quote,
                            confidence=decision.confidence,
                            learner_path=(cA, cB),
                            domain=domain,
                        )
                        candidate_edges.append(edge)

        # Deduplicate edges
        dedup_edges = {}
        for e in candidate_edges:
            ekey = (_canonical_key(e.from_name), _canonical_key(e.to_name), e.edge_type)
            if ekey not in dedup_edges:
                dedup_edges[ekey] = e

        final_edges = list(dedup_edges.values())

        graph_export = {
            "concepts": {
                c["canonical_key"]: {
                    "name": c["name"],
                    "concept_type": "concept",
                    "difficulty": "intermediate",
                    "doc_id": c["doc_id"],
                    "first_chunk": c["first_chunk"],
                    "occurrences": c["occurrences"],
                    "domain": domain,
                }
                for c in concept_list
            },
            "edges": [
                {
                    "from_name": e.from_name,
                    "to_name": e.to_name,
                    "edge_type": e.edge_type,
                    "relation": e.relation,
                    "is_inferred": e.is_inferred,
                    "source": e.source,
                    "doc_id": e.doc_id,
                    "chunk_id": e.chunk_id,
                    "evidence_text": e.evidence_text,
                    "confidence": e.confidence,
                    "domain": domain,
                }
                for e in final_edges
            ],
            "doc_id": doc_id,
            "domain": domain,
        }

        explicit_prereq_count = sum(1 for e in final_edges if e.relation == "explicit_prerequisite")
        inferred_prereq_count = sum(1 for e in final_edges if e.relation == "inferred_prerequisite")
        unlocks_count = sum(1 for e in final_edges if e.edge_type == "UNLOCKS")
        part_of_count = sum(1 for e in final_edges if e.relation == "part_of")
        uses_count = sum(1 for e in final_edges if e.relation == "uses")
        contrasts_count = sum(1 for e in final_edges if e.relation == "contrasts_with")

        return {
            "doc_id": doc_id,
            "domain": domain,
            "graph_export": graph_export,
            "concept_count": len(concept_list),
            "edge_count": len(final_edges),
            "directed_edge_count": explicit_prereq_count + inferred_prereq_count + unlocks_count,
            "explicit_prereq_count": explicit_prereq_count,
            "inferred_prereq_count": inferred_prereq_count,
            "unlocks_count": unlocks_count,
            "part_of_count": part_of_count,
            "uses_count": uses_count,
            "contrasts_count": contrasts_count,
            "abstention_count": len(abstentions),
            "rejection_count": len(rejections),
            "cycles_prevented_count": len(cycles_prevented),
            "abstentions": abstentions,
            "rejections": rejections,
            "cycles_prevented": cycles_prevented,
        }
