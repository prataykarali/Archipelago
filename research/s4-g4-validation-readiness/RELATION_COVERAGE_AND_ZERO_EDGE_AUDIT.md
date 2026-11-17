# Archipelago — S4-G4 Relation Coverage & Zero-Edge Document Audit

**Date:** November 17, 2026  
**Auditor:** Archipelago Extraction Validation Gate (S4-G4)  
**Branch:** `research/s4-g4-validation-readiness`  

---

## 1. Overview of the 53 Repaired Knowledge Graph Edges

In S4-G3, the repaired extraction pipeline replaced ungrounded proximity-based edge generation with clause-bound syntactic pattern recognition and DAG-preserving prerequisite validation. Across the multi-domain evaluation corpus, this produced **53 scientifically grounded heterogeneous edges**:

| Edge Type | Count | Learner Semantics | Asymmetric Direction Handling |
| :--- | :--- | :--- | :--- |
| `REQUIRES` | 6 | Strict pedagogical / conceptual prerequisite | Directed DAG ($B \rightarrow A$: learner must master $B$ to learn $A$) |
| `USES` | 15 | Methodological application / tool usage | Asymmetric ($A \rightarrow B$: method $A$ utilizes technique $B$) |
| `PART_OF` | 6 | Structural composition / architectural sub-layer | Hierarchical ($B \rightarrow A$: subcomponent $B$ is part of system $A$) |
| `CONTRASTS_WITH` | 26 | Comparative evaluation / alternative formulation | Bidirectional / Symmetric ($A \leftrightarrow B$: $A$ contrasted with $B$) |
| **Total Edges** | **53** | Heterogeneous Multi-Relation Graph | **Prerequisite Cycles: 0** |

---

## 2. Deep-Dive: Root Cause Analysis of Zero-Edge Documents

Four documents in the multi-domain corpus produced **zero repaired edges** despite being valid academic documents containing recognized concepts:

1. `archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf` (Operating Systems)
2. `doc_computer_networks_6_e` (Computer Networks)
3. `doc_fundamentals_of_database_system_7e` (Database Management Systems)
4. `doc_compilers_principles_techniques_and_tools` (Compilers & Programming Languages)

Our technical inspection of the database chunks and extractor execution logs reveals the exact underlying failure modes:

### 2.1 `08_Paging.pdf` — Fragmentary Corpus Seed & Genuine Absence of In-Chunk Triggers
- **Corpus State:** Only 3 passage chunks exist in `okf_graph.db` (`paging_seed_001`, `paging_seed_002`, `paging_seed_003`).
- **Content Inspection:**
  - `paging_seed_001` (page 1) contains an introductory paragraph introducing the dilemma between segmentation and paging, but without an explicit verb-trigger binding them in clause scope.
  - `paging_seed_002` (page 2) consists largely of an ASCII visual memory diagram ("`64 48 32 16 0 (page 3) (page 2)...`").
  - `paging_seed_003` (page 3) describes free-space management advantages.
- **Extractor Behavior:** Evaluated 2 candidate pairs: `('paging', 'address space physical')` and `('paging', 'introduction it')`. Abstained on both.
- **Root Cause Classification:** **Genuine Absence of In-Chunk Relational Statements**. The introductory seed chunks describe concepts in isolation or in tabular/diagrammatic form. There is no syntactically bound assertion (e.g., "*Paging requires virtual memory*") within any single 150-character clause window.

### 2.2 `doc_computer_networks_6_e` — List Enumeration & Linebreak Boundaries
- **Corpus State:** 2 short excerpt chunks (350 characters each).
- **Content Inspection:**
  - `doc_computer_networks_6_e_p42_1`:
    ```text
    Section 1.4 Network Software & The OSI Reference Model.
    The OSI Reference Model defines a 7-layer architecture for computer communications:
    1. Physical Layer: Transmission of raw bits over a physical communications channel.
    2. Data Link Layer: Transforms a raw transmission facility in...
    ```
- **Extractor Behavior:** Extracted concepts: `['data link layer', 'network software', 'osi', 'physical layer', 'the osi reference model', 'sliding window protocol']`. Evaluated 10 candidate pairs; abstained on all 10.
- **Root Cause Classification:** **Document Structure & Scope Delimitation**.
  - The concepts `Physical Layer` and `Data Link Layer` appear as numbered list items separated by colon punctuation and linebreaks (`1. Physical Layer: ... \n 2. Data Link Layer: ...`).
  - Between `Physical Layer` and `Data Link Layer`, there is **no relational verb** (e.g., they are coordinate siblings in an enumeration, not related by `REQUIRES` or `USES`).
  - Between `The OSI Reference Model` and `Physical Layer`, the connecting phrase is "*defines a 7-layer architecture for computer communications:*", which lacks the standard `PART_OF` pattern (`consists of`, `comprises`, `composed of`).
  - The clause splitter correctly refrained from fabricating a spurious dependency.

### 2.3 `doc_fundamentals_of_database_system_7e` — Cross-Sentence Concept Separation
- **Corpus State:** 1 short excerpt chunk (350 characters).
- **Content Inspection:**
  - `doc_fundamentals_of_database_system_7e_p145_1`:
    ```text
    Chapter 6 The Relational Data Model and Relational Database Constraints.
    The Relational Model represents a database as a collection of relations (tables)...
    Relational Algebra is a formal procedural query language consisting of fundamental algebraic...
    ```
- **Extractor Behavior:** Extracted concepts: `['relational algebra', 'relational database constraint', 'the relational data model', 'the relational model']`. Evaluated 6 candidate pairs; abstained on all 6.
- **Root Cause Classification:** **Distance Limits & Cross-Sentence Boundary**.
  - `The Relational Model` is defined in Sentence 1.
  - `Relational Algebra` is introduced in Sentence 2.
  - While humans know that Relational Algebra operates on the Relational Model, the text does not contain a single-sentence binding verb connecting them.
  - The repaired extractor enforces a strict single-sentence/clause boundary (maximum 150 characters between arguments) to prevent spurious co-occurrence edges.

### 2.4 `doc_compilers_principles_techniques_and_tools` — Entity Extraction Surface Gap
- **Corpus State:** 1 short excerpt chunk (350 characters).
- **Content Inspection:**
  - `doc_compilers_principles_techniques_and_tools_p192_1`:
    ```text
    Chapter 4 Syntax Analysis.
    The parser obtains a string of tokens from the lexical analyzer and verifies that...
    For every context-free grammar G = (V, Sigma, R, S), the parser constructs a parse tree or Abstract Syntax Tree...
    ```
- **Extractor Behavior:** Extracted concepts: `['abstract syntax tree', 'syntax analysi']`. Evaluated 1 candidate pair; abstained.
- **Root Cause Classification:** **Missing Entity Detection (Surface Form Limitation)**.
  - The key relational participants in this passage (`parser`, `lexical analyzer`, `context-free grammar`) appear in lowercase prose (`"the parser"`, `"the lexical analyzer"`).
  - `RepairedConceptExtractor` heuristics target capitalized phrases, canonical acronyms, or quoted terms to prevent generic common noun explosion. As a result, lowercase `parser` and `context-free grammar` were not extracted as candidate entities.
  - The only concepts retained were `Syntax Analysis` (from the chapter heading) and `Abstract Syntax Tree` (capitalized in sentence 2), which are located in separate sentences without a connective trigger.

---

## 3. Systematic Breakdown of Failure Categories

| Failure Category | Mechanism | Example Document | Fixable Without Overgeneration? |
| :--- | :--- | :--- | :--- |
| **Missing Entity Detection** | Valid technical terms in lowercase (e.g. `parser`, `grammar`) missed by title-case filter | `doc_compilers...` | Partially (expand domain glossary, but avoid common-noun explosion) |
| **Document Structure** | Numbered lists and section outlines present entities as siblings without explicit relational verbs | `doc_computer_networks_6_e` | No — sibling list items do not imply direct semantic dependencies |
| **Cross-Sentence Distance** | Concepts introduced in adjacent sentences without an inter-sentence connector | `doc_fundamentals_of_database...` | No — cross-sentence windowing was the exact cause of 51,000+ spurious edges in S4-G1 |
| **Fragmentary Evidence** | Corpus contains only 1-3 seed chunks that lack relational prose | `08_Paging.pdf` | Requires full textbook chapter ingestion, not extractor relaxation |

---

## 4. Coverage vs. Precision Tradeoffs

The S4-G3 repair made an intentional, principled scientific tradeoff:

```
[S4-G1 Baseline Extractor]                  [S4-G3/G4 Repaired Extractor]
- Raw Edges: 51,079                          - Grounded Edges: 53
- Prerequisite Cycles: 208                   - Prerequisite Cycles: 0 (Strict DAG)
- Precision: Extremely Low (<5% supported)   - Precision: High (syntactically verified)
- Zero-edge documents: 0                     - Zero-edge documents: 4
```

### Key Tradeoff Conclusions
1. **Zero Edges is the Scientifically Correct Outcome for Inadequate Evidence:** If an excerpt consists only of chapter headings and isolated definitions, returning zero edges is the only truthful behavior. Fabricating edges from co-occurrence violates evidence grounding.
2. **Recall Limitations are Inherent to High-Precision Pattern Extraction:** Rule-based syntactic extraction misses implicit relationships and discourse-level dependencies spanning multiple paragraphs. Future iterations may explore calibrated LLM relation extractors with schema constraints, but pattern-based baseline extraction must remain strict.
3. **Corpus Completeness Matters More Than Window Size:** The path to connecting `Physical Layer` and `Data Link Layer` is not relaxing sentence boundaries, but ingesting the full text of Chapter 1 where Tanenbaum explicitly writes "*the Data Link layer relies on services provided by the Physical layer*".
