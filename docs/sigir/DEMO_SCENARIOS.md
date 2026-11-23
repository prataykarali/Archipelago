# ACM SIGIR 2027 Demonstrations Track
## Three Reproducible Demonstration Scenarios

This document specifies the three authoritative demonstration scenarios for the **Archipelago Graph-Assisted Academic Research Assistant**, prepared for the ACM SIGIR 2027 Demonstrations Track.

All scenarios run on the frozen, audited AI/ML and Information Retrieval knowledge slice (`research/d5_sigir_evaluation/d5_graph_slice.json`) and verified open-access research papers.

---

## Demonstration Overview

| Scenario | Title | Core Pedagogical / IR Capability | Grounding Status | Canonical Sources |
|---|---|---|---|---|
| **Scenario 1** | **Transformer Concept Reasoning** | Structural component decomposition vs pedagogical prerequisite discovery | `Passage located · Grounded` | Vaswani et al. (2017), Strang (2016) |
| **Scenario 2** | **DPR and RAG in Information Retrieval** | Neural retrieval integration, bi-encoder architecture, and contrast with BM25 | `Passage located · Grounded` | Lewis et al. (2020), Karpukhin et al. (2020) |
| **Scenario 3** | **Honest Unsupported-Topic Abstention** | Honest boundary disclosure and abstention without hallucinated graphs or citations | `Query outside knowledge boundary` | Systematic abstention fallback |

---

## Scenario 1: Transformer Concept Reasoning & Prerequisite Navigation

### 1.1 Objective
Demonstrate how Archipelago disambiguates **structural architectural components** (e.g., self-attention, multi-head attention, layer normalization) from **pedagogical prerequisites** (e.g., matrix multiplication, softmax, probability distributions).

### 1.2 Step-by-Step Interaction

#### Turn 1: Foundational Architecture Query
- **User Query:** `What is Transformer?`
- **Resolved Anchor Concept:** `transformer`
- **Retrieval Mode:** `Graph-Assisted Traversal (OKF + Verified Passages)`
- **Grounding Badge:** `Passage located · Grounded` (Status: `verified`)
- **Primary Source Citation:**
  - **Document:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (Page 2)
  - **Authors:** Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin
  - **Passage Text:**
    > *"Figure 1: The Transformer - model architecture. The Transformer follows this overall architecture using stacked self-attention and point-wise, fully connected layers for both the encoder and decoder, shown in the left and right halves of Figure 1, respectively."* (High-level sequence transduction description introduced on page 1).
- **Inspector State:**
  - **Graph Subgraph:** Centers on `transformer`, displaying outward directed connections to `self_attention` (`RELATED`), `multi_head_attention` (`RELATED`), and prerequisite connections to `vector_embeddings` (`REQUIRES`).
  - **Trace Metrics:** Latency $\approx 60\text{ ms}$, Graph hops: 2, Grounded passages: 10.

#### Turn 2: Component Deep-Dive Query
- **User Query:** `How does self-attention relate to the Transformer?`
- **Resolved Anchor Concept:** `self_attention`
- **Verified Live Runtime Output (`okf_graph.json`):**
  - Connects `self_attention` via `RELATED` and `REQUIRES` edges in the live graph (`transformer`, `matrix_multiplication`, `sequence`).
  - Note: The runtime schema stores only `REQUIRES`, `RELATED`, and `UNLOCKS` (not `USES` or `PART_OF`), and `self_attention -> transformer` remains a known legacy `REQUIRES` direction artifact in `okf_graph.json` (disclosed in `reviewer_provenance.json`).
- **Supporting Citations (Live Runtime):**
  - `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (Pages 5 and 10; 2 citations returned).

#### Turn 3: Mathematical Prerequisite Query (Live Runtime Coverage Note)
- **User Query:** `What math is required for self-attention?`
- **Verified Live Runtime Behavior:**
  - Resolves to `attention_mechanism` (not `self_attention`) with `prerequisites=[]` and 10 neighborhood citations (top-3: Vaswani 2017 p. 13, Devlin 2018 p. 3, Bahdanau 2014 p. 4).
  - *Demonstrator Note:* To inspect mathematical prerequisites (`matrix_multiplication`, `linear_algebra`) in the current runtime graph, inspect the prerequisite list directly on the `transformer` or `self_attention` anchor node from Turns 1–2 rather than expecting a multi-hop Strang/Ross textbook citation chain from Turn 3.

---

## Scenario 2: Dense Passage Retrieval (DPR) and RAG

### 2.1 Objective
Demonstrate how Archipelago supports Information Retrieval researchers and students in understanding neural dense retrieval within Retrieval-Augmented Generation (RAG), highlighting the contrast between dense bi-encoders and sparse BM25 baselines.

### 2.2 Step-by-Step Interaction

#### Turn 1: RAG System Architecture
- **User Query:** `What is Retrieval-Augmented Generation?`
- **Resolved Anchor Concept:** `rag`
- **Retrieval Mode:** `Graph-Assisted Traversal (OKF + Indexed Passages)`
- **Primary Source Citation (Live Runtime):**
  - **Document:** `papers/Lewis2020_RAG.pdf` (Page 4; rank 1 of 10 returned citations; note neighborhood expansion also surfaces peripheral papers such as Brown 2020 p. 10 and Goodfellow 2014 p. 2 — a known citation-dilution limitation disclosed in `citation_grounding_audit.json`).
- **Inspector State (Live Runtime):**
  - Displays `rag` `related_concepts` including `retrieval_augmented_generation`, `language_model`, `gpt_2`, `beam_search`, and `unlocks` including `advanced_rag`, `large_language_model_serving`.

#### Turn 2: DPR Component and Contrast with BM25
- **User Query:** `Explain Dense Passage Retrieval`
- **Resolved Anchor Concept:** `retrieval` (ontology alias; `dense_passage_retriever` and `dpr` appear in its prerequisite/related neighborhood alongside `bm25`).
- **Primary Source Citations (Live Runtime Top-3):**
  - `papers/Lewis2020_RAG.pdf` (Pages 3 and 1) and `papers/Devlin2018_BERT.pdf` (Page 5).
- **Architectural & IR Contrast Displayed:**
  - The knowledge graph schema does not assert an unverified `CONTRASTS_WITH` edge; instead, `dpr`, `dense_passage_retriever`, and `bm25` appear in the `retrieval` concept neighborhood, while comparative synthesis is presented in prose.

---

## Scenario 3: Honest Unsupported-Topic Handling (Abstention)

### 3.1 Objective
Demonstrate Archipelago's scientific integrity by proving that out-of-domain or unindexed topics trigger clean abstention rather than hallucinating concepts, fabricated prerequisites, or synthetic PDF links.

### 3.2 Step-by-Step Interaction

#### Turn 1: Distributed Systems Out-of-Domain Query
- **User Query:** `Explain Spanner TrueTime and its prerequisites.`
- **Target Topic:** Google Spanner TrueTime (distributed systems, atomic clocks, GPS receivers, external consistency).
- **Domain Status:** Outside the indexed AI/ML and CS textbook graph slice.
- **Resolved Anchor Concept:** `None`
- **Retrieval Mode:** `Knowledge Boundary Abstention`
- **Grounding Badge:** `Query outside knowledge boundary · Not in graph` (Status: `abstention`)
- **Generated Answer Excerpt:**
  > *"Here is what the available evidence shows about **Spanner TrueTime** and **its prerequisites**.*
  > 
  > ***Coverage Limitations:***
  > *• **Spanner TrueTime** is not indexed in the current catalog and research knowledge base.*
  > *• To maintain scientific integrity, Archipelago abstains from generating speculative prerequisite paths or synthetic relationships when primary source evidence is absent."*
- **Inspector State:**
  - **Graph Tab:** Displays the clean empty state with message: *"No concept node matched for 'Spanner TrueTime'. Graph traversal aborted to prevent hallucinated edges."*
  - **Evidence Tab:** No fake PDF citations or broken reader links are presented.
  - **Trace Tab:** Trace records `intent: "ABSTENTION"`, `grounding_status: "unsupported_domain"`, `graph_hops: 0`, `latency_ms: 22`.

---

## Verification Checklist for Demonstrators

When presenting at the SIGIR Demonstration booth:

1. [x] **Verify Scenario 1:** Run `What is Transformer?` $\rightarrow$ Confirm Vaswani 2017 citation on Page 2 and green `Passage located · Grounded` badge.
2. [x] **Verify Scenario 1 Direction:** Inspect graph → Confirm `self_attention` is connected via `RELATED` or `REQUIRES` (not `USES` — that predicate is absent from the runtime schema).
3. [x] **Verify Scenario 2:** Run `What is Retrieval-Augmented Generation?` $\rightarrow$ Confirm Lewis 2020 citation on Page 1/4 and DPR dual-encoder discussion.
4. [x] **Verify Scenario 3:** Run `Explain Spanner TrueTime and its prerequisites.` $\rightarrow$ Confirm honest abstention banner and zero invented graph nodes.
5. [x] **Verify Latency:** Confirm trace latency remains under 200 ms across all queries on local host and under 1.5 s on production.
