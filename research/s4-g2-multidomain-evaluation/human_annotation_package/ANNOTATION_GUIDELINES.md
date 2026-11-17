# Multi-Domain Academic Knowledge Graph Human Annotation Guidelines

**Package Version:** 1.0  
**Phase:** S4-G2 Multi-Domain Evaluation Preparation  
**Scope:** Independent human evaluation across 6 core academic domains (OS, DBMS, Computer Networks, Automata Theory, Probability & Statistics, Artificial Intelligence & Machine Learning).

---

## 1. Ethical & Scientific Purpose

This annotation package is designed for **independent human judges** to evaluate candidate academic concepts and relationships extracted from published scholarly sources.
- **Independence:** Annotators must evaluate candidates solely based on the provided source passage and accepted academic domain consensus.
- **Blinded Protocol:** System-generated predictions, AI model labels, and baseline heuristics are strictly concealed.
- **Separation of Quality Control:** This multi-domain package is an independent evaluation pool, kept strictly separate from the earlier 24-item human QC audit.

---

## 2. Annotation Task Overview

For each item in the pool (identified by `item_id`), you are provided:
1. `Domain`: Academic discipline
2. `Concept A` and `Concept B`: Candidate concept terms
3. `Source Document`, `Chunk ID`, and `Page Number`: Source citation
4. `Evidence Passage`: Verbatim text excerpt from the document

You must record the following 9 judgment fields:

### Field 1 & 2: Concept Validity (`human_concept_validity_a` and `b`)
Score each concept as `0` or `1`:
- `1` (Valid): A meaningful technical term, theory, architecture, algorithm, theorem, or abstraction within the domain.
- `0` (Invalid): Generic stopword, sentence fragment, conversational phrase, author name, or corrupted entity.

### Field 3: Relation Type (`human_relation_type`)
Select exactly one category:
- `REQUIRES`: **Pedagogical Prerequisite**. Learning or implementing one concept fundamentally requires prior understanding of the other.
- `UNLOCKS`: **Forward Enablement**. One concept directly enables or forms the foundational basis for deriving the second.
- `PART_OF`: **Structural Subcomponent**. One concept is an architectural module, structural layer, or internal element of the other (e.g. Page Table Entries are part of Page Tables).
- `USES`: **Empirical Tool / Hardware Usage**. One concept employs, optimizes with, or executes on the other (e.g. Operating system uses MMU hardware; Model optimized using Adam).
- `CONTRASTS_WITH`: **Methodological Alternative / Comparison**. Two concepts represent competing or alternative techniques (e.g. Paging vs. Segmentation; Packet Switching vs. Circuit Switching).
- `RELATED`: **General Conceptual Association**. Semantically related in domain theory, but neither is a prerequisite, component, tool, or direct contrast.
- `UNRELATED`: Co-occurring merely by coincidence; no meaningful technical relationship.

### Field 4: Prerequisite Direction (`human_prereq_direction`)
Specify the educational learning sequence:
- `A_BEFORE_B`: Concept A must be understood before Concept B.
- `B_BEFORE_A`: Concept B must be understood before Concept A.
- `UNDIRECTED`: Symmetric or non-directional relationship (e.g. contrast or general association).
- `NONE`: No valid relationship exists.

### Field 5: Evidence Support (`human_evidence_support_0_1_2`)
Score whether the provided passage text supports your judgment:
- `2` (Fully Supported): Verbatim phrasing in the passage directly establishes the relationship.
- `1` (Partially Supported): The passage implies the connection, but full justification relies on broader domain textbook context.
- `0` (Unsupported): The passage merely mentions the words without stating or implying any relationship.

### Field 6: Source & Page Verification (`human_source_verified_0_1`)
- `1`: The cited document, section, and page match the passage text.
- `0`: Provenance mismatch or hallucinated citation.

### Field 7: Confidence (`human_confidence_high_med_low`)
- `High`: Unambiguous decision based on established textbook theory.
- `Medium`: Reasonable interpretation, but alternative semantic framing exists.
- `Low`: Uncertain judgment due to passage brevity or ambiguous technical phrasing.

### Field 8: Uncertainty Flag (`human_uncertainty_flag`)
- `1` (Uncertain): Flag if the relationship is borderline, contentious, or requires multi-source verification.
- `0` (Certain): Clear judgment.

### Field 9: Notes (`human_notes`)
Brief free-text explanation of edge cases, nuances, or specific rationale.
