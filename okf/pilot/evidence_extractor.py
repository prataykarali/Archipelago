"""S4-G1: Evidence-Grounded Graph Extraction Prototype.

Implements principled, evidence-grounded concept extraction and prerequisite
relation direction determination without relying on problematic heuristics
(such as order of mention, difficulty ranking fallback, or alphabetical sorting).

Key architectural principles:
1. Multi-concept extraction per chunk (retrieving intermediate concepts).
2. Explicit differentiation of dependency, usage, part-of, contrast, and co-occurrence.
3. Strict abstention when evidence is insufficient (no guessing, no alphabetical fallback).
4. Full provenance retention: doc_id, chunk_id, source f"{doc_id}:{chunk_id}",
   verbatim evidence quote, relation interpretation, and confidence score.
5. Cycle and reciprocal conflict prevention at insertion time.
"""

from __future__ import annotations

import dataclasses
import re
from typing import Any

from okf.canonicalize import _concept_key, canonicalize_name
from okf.eval.gold.part01_load_gold_graph import _canonical_key


@dataclasses.dataclass
class EvidenceGroundedEdge:
    from_name: str
    to_name: str
    edge_type: str  # "REQUIRES", "UNLOCKS", "RELATED"
    relation: str   # "requires", "enables", "part_of", "uses", "contrasts_with", "co_occurrence"
    doc_id: str
    chunk_id: str
    source: str     # f"{doc_id}:{chunk_id}"
    evidence_text: str
    confidence: float
    learner_path: tuple[str, str]  # (prereq, dependent) for educational order


@dataclasses.dataclass
class RelationDecision:
    concept_a: str
    concept_b: str
    relation_type: str  # "REQUIRES", "UNLOCKS", "PART_OF", "USAGE", "CONTRAST", "CO_OCCURRENCE", "ABSTAIN"
    learner_direction: str  # "a_to_b" (a is prereq of b), "b_to_a" (b is prereq of a), "undirected", "none"
    confidence: float
    evidence_quote: str
    reason: str


class EvidenceGroundedExtractor:
    """Extracts concepts and validates relations strictly with text evidence."""

    def __init__(self, confidence_threshold: float = 0.65) -> None:
        self.confidence_threshold = confidence_threshold

    def extract_salient_concepts(self, chunk_text: str) -> list[str]:
        """Extract salient academic noun phrases and concept candidates from text."""
        if not chunk_text or len(chunk_text) < 20:
            return []

        stopwords = {
            "this", "that", "these", "those", "such", "which", "there", "their", "where",
            "section", "figure", "table", "paper", "author", "authors", "approach",
            "method", "model", "results", "experiment", "experiments", "baseline", "baselines",
            "performance", "training", "parameters", "dataset", "datasets", "task", "tasks",
            "table 1", "table 2", "figure 1", "figure 2", "appendix", "introduction"
        }

        candidates = set()

        # 1. Acronyms with expansions: e.g. "Low-Rank Adaptation (LoRA)"
        acronym_matches = re.finditer(r"\b([A-Z][a-zA-Z0-9\s\-]{2,35})\s*\(([A-Z]{2,6})\)", chunk_text)
        for m in acronym_matches:
            full = m.group(1).strip()
            acro = m.group(2).strip()
            if full.lower() not in stopwords:
                candidates.add(full)
            if acro.lower() not in stopwords:
                candidates.add(acro)

        # 2. Capitalized Phrases, Single Technical Terms, and CamelCase identifiers (e.g. "Transformer", "ConceptA")
        title_matches = re.finditer(r"\b([A-Z][a-zA-Z0-9_\-]+(?:\s+[A-Z][a-zA-Z0-9_\-]+)*)\b", chunk_text)
        for m in title_matches:
            phrase = m.group(1).strip()
            # If multi-word, length <= 4 words
            words = phrase.split()
            if len(words) <= 4:
                if phrase.lower() not in stopwords and len(phrase) >= 3:
                    candidates.add(phrase)

        # 3. All-caps technical acronyms (e.g. "GPT", "BERT", "SVD", "DPO", "PEFT", "VRAM")
        acro_all_matches = re.finditer(r"\b([A-Z]{2,6})\b", chunk_text)
        for m in acro_all_matches:
            acro = m.group(1).strip()
            if acro.lower() not in stopwords:
                candidates.add(acro)

        # 3. Hyphenated technical compound terms
        hyphen_matches = re.finditer(r"\b([A-Z][a-zA-Z]+-[A-Z][a-zA-Z]+(?:\s+[A-Z][a-z]+)?)\b", chunk_text)
        for m in hyphen_matches:
            phrase = m.group(1).strip()
            if phrase.lower() not in stopwords:
                candidates.add(phrase)

        cleaned = []
        for c in sorted(candidates):
            c_norm = c.strip()
            if len(c_norm) >= 3 and c_norm.lower() not in stopwords:
                cleaned.append(c_norm)

        return cleaned

    def classify_relation_with_evidence(
        self,
        concept_a: str,
        concept_b: str,
        chunk: dict[str, Any],
    ) -> RelationDecision:
        """Classify relationship strictly from textual evidence.

        Abstains whenever dependency evidence is absent. NEVER guesses direction from
        mention order or alphabetical sorting.
        """
        text = chunk.get("text_passage") or chunk.get("text") or ""
        if not text:
            return RelationDecision(
                concept_a=concept_a, concept_b=concept_b,
                relation_type="ABSTAIN", learner_direction="none",
                confidence=0.0, evidence_quote="",
                reason="Empty text passage",
            )

        a_lower = concept_a.strip().lower()
        b_lower = concept_b.strip().lower()

        if a_lower == b_lower:
            return RelationDecision(
                concept_a=concept_a, concept_b=concept_b,
                relation_type="ABSTAIN", learner_direction="none",
                confidence=0.0, evidence_quote="",
                reason="Self-referential concept pair",
            )

        sentences = re.split(r"(?<=[.!?])\s+", text)
        co_occurring_sentences = [
            s.strip() for s in sentences
            if a_lower in s.lower() and b_lower in s.lower()
        ]

        if not co_occurring_sentences:
            return RelationDecision(
                concept_a=concept_a, concept_b=concept_b,
                relation_type="ABSTAIN", learner_direction="none",
                confidence=0.0, evidence_quote="",
                reason="Concepts do not co-occur in any single sentence",
            )

        for sent in co_occurring_sentences:
            sent_low = sent.lower()

            m_a = list(re.finditer(r"\b" + re.escape(a_lower) + r"\b", sent_low))
            m_b = list(re.finditer(r"\b" + re.escape(b_lower) + r"\b", sent_low))

            if not m_a or not m_b:
                idx_a = sent_low.find(a_lower)
                idx_b = sent_low.find(b_lower)
                if idx_a == -1 or idx_b == -1:
                    continue
                if idx_a < idx_b:
                    first_c, second_c = (concept_a, concept_b)
                    between = sent_low[idx_a + len(a_lower) : idx_b].strip()
                    before = sent_low[:idx_a].strip()
                else:
                    first_c, second_c = (concept_b, concept_a)
                    between = sent_low[idx_b + len(b_lower) : idx_a].strip()
                    before = sent_low[:idx_b].strip()
            else:
                best_pair = min(
                    ((ma, mb) for ma in m_a for mb in m_b),
                    key=lambda p: abs(p[0].start() - p[1].start()),
                )
                ma, mb = best_pair
                if ma.start() < mb.start():
                    first_c, second_c = (concept_a, concept_b)
                    between = sent_low[ma.end() : mb.start()].strip()
                    before = sent_low[:ma.start()].strip()
                else:
                    first_c, second_c = (concept_b, concept_a)
                    between = sent_low[mb.end() : ma.start()].strip()
                    before = sent_low[:mb.start()].strip()

            # 1. CONTRAST / ALTERNATIVE (e.g. "unlike X, Y", "X differs from Y", "X performs on-par or better than Y")
            contrast_re = re.compile(
                r"\b(in contrast to|compared to|compared with|differs from|unlike|as an alternative to|versus|vs\.?|performs on-par or better than|outperforms)\b"
            )
            if contrast_re.search(between) or contrast_re.search(before):
                return RelationDecision(
                    concept_a=concept_a, concept_b=concept_b,
                    relation_type="CONTRAST", learner_direction="undirected",
                    confidence=0.85, evidence_quote=sent[:180],
                    reason=f"Linguistic contrast marker between '{first_c}' and '{second_c}'",
                )

            # 2. PART_OF (e.g. "X is a component of Y")
            part_of_re = re.compile(
                r"\b(is a component of|is part of|consists of|is an element of|is composed of|module of|layer of|layers of)\b"
            )
            if part_of_re.search(between):
                return RelationDecision(
                    concept_a=concept_a, concept_b=concept_b,
                    relation_type="PART_OF", learner_direction="undirected",
                    confidence=0.80, evidence_quote=sent[:180],
                    reason=f"Structural subcomponent marker between '{first_c}' and '{second_c}'",
                )

            # 3. PREREQUISITE FOR / REQUIRED FOR (first is prerequisite of second)
            prereq_for_re = re.compile(
                r"\b(is a prerequisite for|is required for|is needed for|is essential for|prerequisite of)\b"
            )
            if prereq_for_re.search(between):
                ldir = "a_to_b" if first_c == concept_a else "b_to_a"
                return RelationDecision(
                    concept_a=concept_a, concept_b=concept_b,
                    relation_type="REQUIRES", learner_direction=ldir,
                    confidence=0.90, evidence_quote=sent[:180],
                    reason=f"Explicit prerequisite marker: '{first_c}' is prerequisite for '{second_c}'",
                )

            # 4. DEPENDENCY (first depends on second -> second is prerequisite of first)
            depends_on_re = re.compile(
                r"\b(requires|depends on|is built on|is built upon|relies on|is based on|based on|assumes|conditioned on|derived from|building on|extending)\b"
            )
            if depends_on_re.search(between):
                ldir = "b_to_a" if first_c == concept_a else "a_to_b"
                return RelationDecision(
                    concept_a=concept_a, concept_b=concept_b,
                    relation_type="REQUIRES", learner_direction=ldir,
                    confidence=0.85, evidence_quote=sent[:180],
                    reason=f"Explicit dependency marker: '{first_c}' depends on '{second_c}'",
                )

            # 5. FORWARD ENABLEMENT (first enables second -> first is prerequisite of second)
            enables_re = re.compile(
                r"\b(enables|allows for|allows(?: us)? to|unlocks|lays the groundwork for|forms the basis of|provides the foundation for|leads to)\b"
            )
            if enables_re.search(between):
                ldir = "a_to_b" if first_c == concept_a else "b_to_a"
                return RelationDecision(
                    concept_a=concept_a, concept_b=concept_b,
                    relation_type="UNLOCKS", learner_direction=ldir,
                    confidence=0.85, evidence_quote=sent[:180],
                    reason=f"Explicit enablement marker: '{first_c}' enables '{second_c}'",
                )

            # 6. USAGE (empirical tool / technique application)
            usage_re = re.compile(
                r"\b(uses|utilizes|employs|applies|using|optimized with|evaluated with|by optimizing)\b"
            )
            if usage_re.search(between) or usage_re.search(before):
                return RelationDecision(
                    concept_a=concept_a, concept_b=concept_b,
                    relation_type="USAGE", learner_direction="undirected",
                    confidence=0.75, evidence_quote=sent[:180],
                    reason=f"Technique usage / tool application marker between '{first_c}' and '{second_c}'",
                )

        return RelationDecision(
            concept_a=concept_a, concept_b=concept_b,
            relation_type="ABSTAIN", learner_direction="none",
            confidence=0.30, evidence_quote=co_occurring_sentences[0][:180],
            reason="Co-occurrence without explicit directional dependency evidence (abstained to prevent hallucinated dependency)",
        )

    def extract_document_graph(
        self,
        chunks: list[dict[str, Any]],
        doc_id: str,
    ) -> dict[str, Any]:
        """Process document chunks and build an evidence-grounded graph representation."""
        all_concepts: dict[str, dict[str, Any]] = {}
        candidate_edges: list[EvidenceGroundedEdge] = []
        abstentions: list[dict[str, Any]] = []
        rejections: list[dict[str, Any]] = []
        cycles_prevented: list[dict[str, Any]] = []

        # 1. Concept extraction pass
        for chunk in chunks:
            c_id = chunk.get("chunk_id") or chunk.get("id") or "chunk_000"
            text = chunk.get("text_passage") or chunk.get("text") or ""
            c_names = self.extract_salient_concepts(text)
            for name in c_names:
                ckey = _canonical_key(name)
                if ckey not in all_concepts:
                    all_concepts[ckey] = {
                        "name": name,
                        "canonical_key": ckey,
                        "doc_id": doc_id,
                        "first_chunk": c_id,
                        "occurrences": 1,
                    }
                else:
                    all_concepts[ckey]["occurrences"] += 1

        concept_list = list(all_concepts.values())

        # 2. Pairwise relation evaluation within chunks
        existing_learner_paths: set[tuple[str, str]] = set()

        for chunk in chunks:
            c_id = chunk.get("chunk_id") or chunk.get("id") or "chunk_000"
            text = (chunk.get("text_passage") or chunk.get("text") or "").lower()

            chunk_concepts = [
                c["name"] for c in concept_list
                if c["name"].lower() in text
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
                            "reason": decision.reason,
                            "evidence": decision.evidence_quote,
                        })
                        continue

                    if decision.confidence < self.confidence_threshold:
                        rejections.append({
                            "concept_a": cA, "concept_b": cB,
                            "chunk_id": c_id, "doc_id": doc_id,
                            "relation_type": decision.relation_type,
                            "confidence": decision.confidence,
                            "reason": f"Confidence {decision.confidence:.2f} < threshold {self.confidence_threshold:.2f}",
                        })
                        continue

                    if decision.relation_type in ("REQUIRES", "UNLOCKS"):
                        if decision.learner_direction == "a_to_b":
                            prereq, dep = cA, cB
                        elif decision.learner_direction == "b_to_a":
                            prereq, dep = cB, cA
                        else:
                            abstentions.append({
                                "concept_a": cA, "concept_b": cB,
                                "chunk_id": c_id, "doc_id": doc_id,
                                "reason": "Direction of dependency could not be established unambiguously",
                                "evidence": decision.evidence_quote,
                            })
                            continue

                        prereq_key = _canonical_key(prereq)
                        dep_key = _canonical_key(dep)
                        if (dep_key, prereq_key) in existing_learner_paths:
                            cycles_prevented.append({
                                "conflict_type": "reciprocal_cycle",
                                "existing_edge": (dep, prereq),
                                "blocked_edge": (prereq, dep),
                                "chunk_id": c_id,
                                "evidence": decision.evidence_quote,
                            })
                            continue

                        existing_learner_paths.add((prereq_key, dep_key))

                        # Map to Kùzu export schema:
                        # For REQUIRES: from_name depends on to_name (learner path to_name -> from_name).
                        # So from_name = dep, to_name = prereq.
                        # For UNLOCKS: from_name enables to_name (learner path from_name -> to_name).
                        # So from_name = prereq, to_name = dep.
                        if decision.relation_type == "REQUIRES":
                            edge = EvidenceGroundedEdge(
                                from_name=dep,
                                to_name=prereq,
                                edge_type="REQUIRES",
                                relation="requires",
                                doc_id=doc_id,
                                chunk_id=c_id,
                                source=f"{doc_id}:{c_id}",
                                evidence_text=decision.evidence_quote,
                                confidence=decision.confidence,
                                learner_path=(prereq, dep),
                            )
                        else:  # UNLOCKS
                            edge = EvidenceGroundedEdge(
                                from_name=prereq,
                                to_name=dep,
                                edge_type="UNLOCKS",
                                relation="enables",
                                doc_id=doc_id,
                                chunk_id=c_id,
                                source=f"{doc_id}:{c_id}",
                                evidence_text=decision.evidence_quote,
                                confidence=decision.confidence,
                                learner_path=(prereq, dep),
                            )
                        candidate_edges.append(edge)

                    else:
                        # RELATED (PART_OF, USAGE, CONTRAST)
                        edge = EvidenceGroundedEdge(
                            from_name=cA,
                            to_name=cB,
                            edge_type="RELATED",
                            relation=decision.relation_type.lower(),
                            doc_id=doc_id,
                            chunk_id=c_id,
                            source=f"{doc_id}:{c_id}",
                            evidence_text=decision.evidence_quote,
                            confidence=decision.confidence,
                            learner_path=(cA, cB),
                        )
                        candidate_edges.append(edge)

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
                }
                for c in concept_list
            },
            "edges": [
                {
                    "from_name": e.from_name,
                    "to_name": e.to_name,
                    "edge_type": e.edge_type,
                    "relation": e.relation,
                    "source": e.source,
                    "doc_id": e.doc_id,
                    "chunk_id": e.chunk_id,
                    "evidence_text": e.evidence_text,
                    "confidence": e.confidence,
                }
                for e in final_edges
            ],
            "doc_id": doc_id,
        }

        directed_count = sum(1 for e in final_edges if e.edge_type in ("REQUIRES", "UNLOCKS"))
        related_count = sum(1 for e in final_edges if e.edge_type == "RELATED")

        return {
            "doc_id": doc_id,
            "graph_export": graph_export,
            "concept_count": len(concept_list),
            "edge_count": len(final_edges),
            "directed_edge_count": directed_count,
            "related_edge_count": related_count,
            "abstention_count": len(abstentions),
            "rejection_count": len(rejections),
            "cycles_prevented_count": len(cycles_prevented),
            "abstentions": abstentions,
            "rejections": rejections,
            "cycles_prevented": cycles_prevented,
        }
