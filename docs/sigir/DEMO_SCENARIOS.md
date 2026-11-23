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
- **Scientific Relationship Displayed:**
  - `self_attention` $\xleftrightarrow{\text{RELATED / REQUIRES}}$ `transformer`
  - The runtime stores verifiable `REQUIRES`, `RELATED`, and `UNLOCKS` relationships. The specific architectural decomposition (that self-attention is a core sub-layer of Transformer rather than requiring a transformer to exist) is synthesized in the grounded answer text supported by the Vaswani 2017 citation, rather than asserting unverified `USES` or `PART_OF` edge types in the graph schema.
- **Supporting Citation:**
  - **Document:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (Page 3)
  - **Passage Text:**
    > *"An attention function can be described as mapping a query and a set of key-value pairs to an output, where the query, keys, values, and output are all vectors."*

#### Turn 3: Mathematical Prerequisite Traversal
- **User Query:** `What math is required for self-attention?`
- **Resolved Prerequisite Path:**
  - `self_attention` $\xrightarrow{\text{REQUIRES}}$ `matrix_multiplication`
  - `scaled_dot_product_attention` $\xrightarrow{\text{REQUIRES}}$ `softmax`
  - `softmax` $\xrightarrow{\text{REQUIRES}}$ `probability_distribution`
- **Supporting Citations:**
  - **Linear Algebra:** Gilbert Strang, *Introduction to Linear Algebra* (5th Edition), Page 12 (matrix multiplication for projection matrices $W_Q, W_K, W_V$).
  - **Probability:** Sheldon Ross, *A First Course in Probability* (9th Edition), Page 110 (softmax exponential normalization into a valid categorical probability distribution).

---

## Scenario 2: Dense Passage Retrieval (DPR) and RAG

### 2.1 Objective
Demonstrate how Archipelago supports Information Retrieval researchers and students in understanding neural dense retrieval within Retrieval-Augmented Generation (RAG), highlighting the contrast between dense bi-encoders and sparse BM25 baselines.

### 2.2 Step-by-Step Interaction

#### Turn 1: RAG System Architecture
- **User Query:** `What is Retrieval-Augmented Generation?`
- **Resolved Anchor Concept:** `rag` (`retrieval_augmented_generation`)
- **Retrieval Mode:** `Graph-Assisted Traversal (OKF + Verified Passages)`
- **Grounding Badge:** `Passage located · Grounded` (Status: `verified`)
- **Primary Source Citation:**
  - **Document:** `papers/Lewis2020_RAG.pdf` (Page 1)
  - **Authors:** Patrick Lewis, Ethan Perez, Aleksandra Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim Rocktäschel, Sebastian Riedel, Douwe Kiela
  - **Passage Text:**
    > *"We explore a general-purpose fine-tuning recipe for retrieval-augmented generation (RAG) — models which combine pre-trained parametric and non-parametric memory for language generation."*
- **Inspector State:**
  - Displays RAG connections to `dense_passage_retrieval` (`REQUIRES`), `retrieval` (`RELATED`), and `transformer` (`RELATED`).

#### Turn 2: DPR Component and Contrast with BM25
- **User Query:** `Explain Dense Passage Retrieval`
- **Resolved Anchor Concept:** `retrieval` / `dense_passage_retrieval`
- **Grounding Badge:** `Passage located · Grounded` (Status: `verified`)
- **Primary Source Citation:**
  - **Document:** `papers/Lewis2020_RAG.pdf` (Page 3) & `papers/Karpukhin2020_DPR.pdf` (Page 2)
  - **Authors:** Vladimir Karpukhin, Barlas Oğuz, Sewon Min, Patrick Lewis, Ledell Wu, Sergey Edunov, Danqi Chen, Wen-tau Yih
  - **Passage Text:**
    > *"DPR follows a bi-encoder architecture: one encoder embeds documents into a dense index, and the other embeds queries. Passage retrieval corresponds to Maximum Inner Product Search (MIPS) using FAISS index."*
- **Architectural & IR Contrast Displayed:**
  - **Dual-Encoder:** Decoupled encoders allow offline pre-indexing of millions of passages in continuous vector spaces.
  - **Contrast with BM25 (Grounded Text Synthesis):**
    - The knowledge graph schema does not assert an unverified `CONTRASTS_WITH` edge; instead, contrast is synthesized in the grounded prose and supported by dual paper citations.
    - BM25 uses term frequency, inverse document frequency, and document length normalization over an inverted index.
    - DPR uses deep transformer representations to capture semantic synonymy without lexical overlap.
  - **Contrast with Cross-Encoder:** Cross-encoders evaluate full query-document cross-attention (higher accuracy, higher latency) and are reserved for second-stage re-ranking.

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
