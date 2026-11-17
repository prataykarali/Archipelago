# Archipelago — S4-E Phase 2: Graph Evaluation Diagnostic Report

**Branch:** `research/s4-e-graph-diagnosis`  
**Date:** 2026-11-17  
**Investigator:** Pratay Karali  
**Scope:** Gold Graph Evaluation Infrastructure, Kùzu Graph Database (`okf_graph.db`), Structural Audit, and Curriculum Alignment  
**Evaluation Standard:** ACM CIKM 2027 Scientific Rigor Protocols  

---

## 1. Executive Summary & S1 Reproduction

We reproduced the document-scoped and whole-graph S1 evaluations using `scripts/run_gold_eval.py` on the live Kùzu graph database (`okf_graph.db`, 610 concepts, 1,988 edges) against the three gold curriculum fixtures:

| Gold Fixture | Evaluation Scope | Concept F1 (Precision / Recall) | Directed Edge F1 | Undirected Edge F1 | Direction Accuracy | Unscopable Edges | Skipped Related Edges |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `gold_lora.json` | Document-Scoped (`papers/Hu2021_LoRA.pdf`) | **19.05%** (18.18% / 20.00%) | **0.00%** (0.0% / 0.0%) | **0.00%** (0.0% / 0.0%) | 100.00%* | **101** | **1,334** |
| `gold_attention.json` | Document-Scoped (`papers/Vaswani2017...`) | **40.00%** (36.67% / 44.00%) | **0.00%** (0.0% / 0.0%) | **0.00%** (0.0% / 0.0%) | 100.00%* | **101** | **1,334** |
| `gold_lora.json` | Whole Graph | **2.23%** (1.15% / 35.00%) | **0.00%** (0.0% / 0.0%) | **0.00%** (0.0% / 0.0%) | 100.00%* | 0 | 1,334 |
| `gold_attention.json` | Whole Graph | **5.69%** (2.96% / 72.00%) | **0.00%** (0.0% / 0.0%) | **0.00%** (0.0% / 0.0%) | 100.00%* | 0 | 1,334 |
| `gold_curriculum.json` | Whole Graph (Cross-Document) | **4.18%** (2.14% / 92.86%) | **0.00%** (0.0% / 0.0%) | **0.00%** (0.0% / 0.0%) | 100.00%* | 0 | 1,334 |

*\*Note: 100.00% Direction Accuracy is a vacuous metric defect caused by returning 1.0 when true positive edge count is zero.*

### Confirmation of Known Diagnostic Findings:
- **Directed Edge F1:** **0.00%** across all documents and whole-graph scopes.
- **Undirected Edge F1:** **0.00%** across all documents and whole-graph scopes.
- **Graph Cycles:** **9 cycles detected** (8 length-2 cycles, 1 length-6 cycle).
- **Edge Provenance Issues:** **157 edges** lacking canonical PDF chunk provenance.
- **Unscopable Edges:** Exactly **101 unscopable edges** reported in every document-scoped evaluation.
- **Skipped RELATED Edges:** Exactly **1,334 edges** (67.1% of the entire edge store) skipped by the evaluator.

---

## 2. Root Cause Classification: Evaluator Defects vs. Graph-Extraction Errors

A primary goal of this diagnosis is to rigorously separate **evaluator defects** (measurement code bugs and schema mismatches) from **genuine graph-extraction errors** (quality failures of the pipeline extraction models).

```
                             GRAPH FAILURE ROOT CAUSES
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
         EVALUATOR DEFECTS                           GENUINE EXTRACTION ERRORS
     (Measurement / Metric Flaws)                    (Model / Ingestion Flaws)
  ┌─────────────────────────────────────┐         ┌─────────────────────────────────────┐
  │ 1. Endpoint Resolution Disparity    │         │ 1. Missing Core Technical Concepts  │
  │    Concept eval allows fuzzy match; │         │    80% of LoRA concepts absent;     │
  │    Edge eval strictly tests string. │         │    56% of Attention concepts absent.│
  │ 2. Vacuous Direction Accuracy       │         │ 2. Missing Intermediate Hops (PEFT) │
  │    Returns 100% when TP=0.          │         │    PEFT exists as orphan (0 edges). │
  │ 3. Unconditional Skip of RELATED    │         │ 3. Symmetric Dual Edge Insertion    │
  │    1,334 semantic edges discarded.  │         │    Simultaneous REQUIRES + UNLOCKS. │
  │ 4. Lack of Equivalence Mapping      │         │ 4. Provenance Erasure (157 edges)   │
  │    Edges evaluated on raw strings.  │         │    None, pearson_batch1, librarian. │
  └─────────────────────────────────────┘         └─────────────────────────────────────┘
```

### A. Evaluator Defects (Measurement Flaws)

1. **Endpoint Resolution Disparity (Concept vs. Edge Alignment):**
   - In `compare_concepts()`, predicted concepts match gold concepts through a fuzzy matching token ratio fallback (`_rf_fuzz.token_set_ratio >= 90`) and alias expansion (`ALIAS_MAP`). For instance, predicted `adapter` successfully matches gold `adapter layers` (100% token ratio match).
   - In `compare_edges()`, `_canonicalize_edge_set()` deterministically strips characters with `_canonical_key()` but **does NOT link endpoints to matched concept equivalence classes**.
   - As a consequence, predicted `('fine tuning', 'adapter')` is evaluated against gold `('parameter efficient fine tuning', 'adapter layer')`. Even though `adapter` was judged a True Positive in concept evaluation, the edge evaluator compares the raw string `"adapter"` against `"adapter layer"`, immediately failing as a False Positive and False Negative.

2. **Vacuous Direction Accuracy (100% on Zero Matches):**
   - In `okf/eval/gold/part01_load_gold_graph.py`, line 258:
     ```python
     dir_accuracy = correct_directions / len(matched_undir) if matched_undir else 1.0
     ```
   - When zero undirected edges match (`len(matched_undir) == 0`), the expression evaluates the fallback `1.0` (100.00%). Reporting 100% direction accuracy on an evaluation where edge recall is 0.00% is misleading. It should return `0.0` or `None`.

3. **Unconditional Skipping of 1,334 RELATED Edges:**
   - 67.10% of all edges in the database (1,334 / 1,988) carry `edge_type = "RELATED"` (comprising `co_mention`, `part_of`, `uses`, `contrasts_with`, `variant_of`).
   - The evaluator flag `include_related` defaults to `False`. When `False`, `_add_edge_record()` unconditionally discards every `RELATED` edge.
   - However, pedagogical relationships like *"Attention Mechanism is used by Transformer"* or *"Multi-Head Attention is part of Transformer Encoder"* are stored under `RELATED` in the DB but formalized as prerequisite dependencies in the gold curricula.

### B. Genuine Graph-Extraction / Ingestion Errors (System Quality Flaws)

1. **Severe Concept Under-Extraction (High False Negative Rate):**
   - In `papers/Hu2021_LoRA.pdf`: **16 out of 20 gold concepts (80.0%) were never extracted** into Kùzu DB. Concepts like `Intrinsic Rank`, `Rank Decomposition Matrices`, `Weight Matrix Reparameterization`, `Scaling Factor Alpha`, `Inference Latency`, and `Singular Value Decomposition` do not exist in the concept table.
   - In `papers/Vaswani2017_Attention_Is_All_You_Need.pdf`: **14 out of 25 gold concepts (56.0%) were never extracted**. Critical components such as `Scaled Dot-Product Attention`, `Query, Key, and Value Vectors`, `Softmax Function`, `Positional Encoding`, and `Masked Self-Attention` do not exist.
   - When the concepts do not exist, no edge between them can possibly be extracted.

2. **Missing Intermediate Abstractions & Orphaned Nodes:**
   - The extraction model extracted `fine tuning` and `low rank adaptation` and linked them directly (`fine tuning -> low rank adaptation`).
   - The intermediate concept `parameter efficient fine tuning` (PEFT) was extracted as a concept node in Kùzu (`id = "parameter_efficient_fine_tuning"`), but has **zero prerequisite, unlocks, or related edges connected to it**. It is an isolated node.

3. **Symmetric Dual Insertion (Cycle Generator):**
   - Ingestion jobs (specifically `librarian_upload`) simultaneously asserted reciprocal relationships: asserting that concept $A$ REQUIRES concept $B$, and that concept $A$ UNLOCKS concept $B$. This created 8 instant 2-cycles in the graph.

4. **Provenance Erasure:**
   - 157 edges in Kùzu have invalid provenance (`source = None`, `pearson_batch1`, or `librarian_upload`).

---

## 3. Diagnostic Deep-Dive: The 9 Graph Cycles

The structural audit revealed 9 cycles in the directed concept graph. Our diagnostic analysis identified the exact hops, edge types, relations, and provenance for each cycle:

| Cycle # | Nodes in Cycle | Length | Participating Hops & Edge Types | Provenance Source | Root Cause Classification |
| :---: | :--- | :---: | :--- | :--- | :--- |
| **1** | `self_attention` $\leftrightarrow$ `long_context_transformer` | 2 | `long_context_transformer` $\xrightarrow{\text{REQUIRES}}$ `self_attention`<br>`long_context_transformer` $\xrightarrow{\text{UNLOCKS}}$ `self_attention` | `librarian_upload` | **Symmetric Dual Insertion** |
| **2** | `transformer` $\leftrightarrow$ `token_dropping` | 2 | `token_dropping` $\xrightarrow{\text{REQUIRES}}$ `transformer`<br>`token_dropping` $\xrightarrow{\text{UNLOCKS}}$ `transformer` | `librarian_upload` | **Symmetric Dual Insertion** |
| **3** | `reward_model` $\to$ `inception_score` $\to$ `GCN` $\to$ `neural_network` $\to$ `probability_distribution` $\to$ `MLE` $\to$ `reward_model` | 6 | `reward_model` $\xrightarrow{\text{UNLOCKS}}$ `inception_score`<br>`inception_score` $\xrightarrow{\text{UNLOCKS}}$ `GCN`<br>`GCN` $\xrightarrow{\text{UNLOCKS}}$ `neural_network`<br>`neural_network` $\xrightarrow{\text{UNLOCKS}}$ `probability_distribution`<br>`MLE` $\xrightarrow{\text{RELATED}}$ `reward_model` | Multi-paper:<br>Ouyang2022, Kipf2016, Willard2023, Goodfellow2014 | **Cross-Document Semantic Cycle** (No cross-document acyclicity check) |
| **4** | `language_model` $\leftrightarrow$ `summarization` | 2 | `language_model` $\xrightarrow{\text{REQUIRES}}$ `summarization`<br>`language_model` $\xrightarrow{\text{UNLOCKS}}$ `summarization` | `librarian_upload` | **Symmetric Dual Insertion** |
| **5** | `reinforcement_learning` $\leftrightarrow$ `binary_cross_entropy` | 2 | `binary_cross_entropy` $\xrightarrow{\text{REQUIRES}}$ `reinforcement_learning`<br>`binary_cross_entropy` $\xrightarrow{\text{UNLOCKS}}$ `reinforcement_learning` | `librarian_upload` | **Symmetric Dual Insertion** |
| **6** | `DPO` $\leftrightarrow$ `kl_divergence` | 2 | `kl_divergence` $\xrightarrow{\text{REQUIRES}}$ `DPO`<br>`kl_divergence` $\xrightarrow{\text{UNLOCKS}}$ `DPO` | `librarian_upload` | **Symmetric Dual Insertion** |
| **7** | `direct_preference_optimization` $\leftrightarrow$ `gae` | 2 | `gae` $\xrightarrow{\text{REQUIRES}}$ `DPO`<br>`gae` $\xrightarrow{\text{UNLOCKS}}$ `DPO` | `librarian_upload` | **Symmetric Dual Insertion** |
| **8** | `DPO` $\leftrightarrow$ `bradley_terry_preference_model` | 2 | `DPO` $\xrightarrow{\text{REQUIRES}}$ `bradley_terry`<br>`DPO` $\xrightarrow{\text{UNLOCKS}}$ `bradley_terry` | `librarian_upload` | **Symmetric Dual Insertion** |
| **9** | `sparse_routing` $\leftrightarrow$ `sparse_mixture_of_experts` | 2 | `sparse_routing` $\xrightarrow{\text{REQUIRES}}$ `sparse_MoE`<br>`sparse_routing` $\xrightarrow{\text{UNLOCKS}}$ `sparse_MoE` | `librarian_upload` | **Symmetric Dual Insertion** |

### Key Diagnostic Discovery on Cycles:
- **8 out of 9 cycles (88.9%) are length-2 reciprocal cycles** created exclusively by `source = "librarian_upload"`. In each case, the upload script inserted both a `REQUIRES` relationship and an `UNLOCKS` relationship in the same direction between node pairs, which inverts direction under learner semantics and produces an immediate reciprocal cycle.
- **Only 1 cycle (Cycle 3)** is a true multi-hop semantic cycle, spanning 6 nodes across 4 distinct papers.

---

## 4. Diagnostic Deep-Dive: 157 Provenance Issues & 101 Unscopable Edges

### Provenance Audit Breakdown:
The structural audit identifies 157 edges where `edge.source` fails canonical document attribution:
- **`source = None` (or empty):** **98 edges** (legacy manual graph insertions).
- **`source = "pearson_batch1"`:** **30 edges** (bulk institutional textbook ingest lacking chunk-level citation).
- **`source = "librarian_upload"`:** **29 edges** (manual librarian upload lacking document / chunk ID).
- **Total:** $98 + 30 + 29 = \mathbf{157\text{ edges}}$.

### Mathematical Derivation of "101 Unscopable Edges":
In every single document-scoped evaluation, the report lists:
`Unscopable Edges (missing provenance): 101`

Why is this number exactly 101 for both LoRA and Attention?
1. The evaluator iterates over all edges in the graph.
2. It excludes `RELATED` edges when `include_related=False`.
3. Of the 157 provenance-flawed edges:
   - **`REQUIRES` edges with bad provenance:** **71**
   - **`UNLOCKS` edges with bad provenance:** **30**
   - **`RELATED` edges with bad provenance:** **56**
4. Sum of directed edges with bad provenance: $71 (\text{REQUIRES}) + 30 (\text{UNLOCKS}) = \mathbf{101\text{ directed edges}}$.
5. When checking any document (e.g., `papers/Hu2021_LoRA.pdf`), `_edge_matches_doc()` checks if the edge provenance matches the target document. For all 101 directed edges with `None`, `pearson_batch1`, or `librarian_upload`, `is_unscopable` evaluates to `True`.
6. Therefore, exactly 101 directed edges are tallied as unscopable for **every** document scope.

---

## 5. Concrete Examples of Failed Edge Matches

### Case 1: Granularity Skip (LoRA)
- **Predicted Edge:** `('fine tuning', 'low rank adaptation')` (derived from `Fine-Tuning ---[REQUIRES]---> Low-Rank Adaptation`)
- **Gold Path:**
  1. `('fine tuning', 'parameter efficient fine tuning')`
  2. `('parameter efficient fine tuning', 'low rank adaptation')`
- **Why it Failed:** The extraction pipeline jumped directly from coarse concept to leaf method, skipping the intermediate prerequisite abstraction (`Parameter-Efficient Fine-Tuning`). The gold standard penalizes this missing hop as 2 False Negatives and 1 False Positive.

### Case 2: Endpoint String Mismatch (Attention)
- **Predicted Edge:** `('attention mechanism', 'transformer encoder')` (derived from `Transformer Encoder ---[REQUIRES]---> Attention Mechanism`)
- **Gold Path:**
  1. `('attention mechanism', 'self attention')`
  2. `('self attention', 'multi head attention')`
  3. `('multi head attention', 'transformer encoder')`
- **Why it Failed:** The extraction model attributed dependency to the broad family (`Attention Mechanism`), whereas Vaswani et al. Section 3.2 explicitly specifies that the encoder stack uses `Multi-Head Attention`.

### Case 3: Concept Resolution Disparity (LoRA)
- **Extracted Edge:** `('fine tuning', 'adapter')` (canonical keys: `fine tuning`, `adapter`)
- **Gold Edge:** `('parameter efficient fine tuning', 'adapter layer')` (canonical keys: `parameter efficient fine tuning`, `adapter layer`)
- **Why it Failed:** In concept evaluation, `adapter` matches `adapter layers` via fuzzy ratio (100%). In edge evaluation, `_canonicalize_edge_set()` checks exact equality of canonical keys (`"adapter" == "adapter layer" -> False`). The evaluator fails to credit the edge endpoint even though the concept was credited in the concept table.

### Case 4: Concept Non-Existence in Database (Attention)
- **Gold Edge:** `('self attention', 'scaled dot product attention')`
- **Kùzu Graph Status:** Concept `Scaled Dot-Product Attention` was never extracted (0 concept nodes in database).
- **Why it Failed:** Genuine extraction failure. The pipeline cannot produce a valid edge when one of the endpoints was never extracted.

---

## 6. Scientific Scope: Valid Corrections vs. Experimental System Tampering

| Proposed Action | Classification | Permitted in Benchmark Integrity? | Scientific Rationale |
| :--- | :---: | :---: | :--- |
| **Concept-Aligned Edge Evaluation** | Valid Correction | **YES** | Evaluates edges over matched concept clusters rather than raw unaligned string keys. Restores measurement consistency between concept and edge evaluation. |
| **Fix Vacuous Direction Accuracy Metric** | Valid Correction | **YES** | Return `0.0` or `None` when $TP=0$ instead of misleading `100.0%`. |
| **Separate Provenance Tracking** | Valid Correction | **YES** | Explicitly report unscopable edges in the denominator rather than silently discarding them. |
| **Manual Insertion of Missing Concepts into DB** | System Tampering | **NO** | Fabricates model extraction results; invalidates baseline evaluation. |
| **Rewriting Gold Curricula to Match Kùzu** | Experimental Tampering | **NO** | Distorts ground-truth definition to artificially inflate scores. |
| **Silent Deletion of Cycles or Bad Provenance Edges** | Data Laundering | **NO** | Deleting the 9 cycles or 157 provenance issues without recording pipeline changes hides extraction flaws. |

---

## 7. Minimal Repair Plan & Regression Test Specifications

### Phase A: Evaluator & Metric Repair (Harness Only)
1. **Concept-Aligned Edge Matcher (`okf/eval/gold/edge_extraction.py`):**
   - Use the `matched_pairs` mapping generated during concept comparison to evaluate edges. An extracted edge $(u, v)$ matches gold edge $(u^*, v^*)$ if $(u \sim u^*)$ and $(v \sim v^*)$ under concept equivalence.
2. **Direction Accuracy Guard:**
   - Update `dir_accuracy` calculation to return `None` (or `0.0` with explicit flag) when `len(matched_undir) == 0`.
3. **Structured Scoping Metadata:**
   - Add explicit counts for `in_scope_edges`, `out_of_scope_edges`, and `unscopable_provenance_edges` in the evaluation JSON export.

### Phase B: Non-Destructive Provenance & Ingestion Hardening
1. **Reciprocal Edge Cleaner (`okf/cleanup_parts/directionality.py`):**
   - For reciprocal pairs created by `librarian_upload` (e.g. $A \xrightarrow{\text{REQUIRES}} B$ and $A \xrightarrow{\text{UNLOCKS}} B$), enforce relation priority or flag for manual review, eliminating the 8 length-2 cycles.
2. **Provenance Backfilling Script (`scripts/ops/backfill_edge_provenance.py`):**
   - Trace `pearson_batch1` and `librarian_upload` concepts back to their source chunks using text-passage matching, replacing opaque tags with canonical chunk IDs (`<doc_id>::chunk_XXX`).

### Regression Test Gate Specifications:
- `test_evaluator_direction_accuracy_not_100_when_tp_zero`: Asserts that empty true positive sets do not return 100% accuracy.
- `test_edge_matching_respects_concept_alignment`: Asserts that concept synonyms correctly propagate to edge matching.
- `test_structural_audit_detects_all_9_cycles`: Prevents regression in cycle detection.
- `test_unscopable_edge_count_invariant`: Validates that exactly 101 directed provenance issues are tracked until explicitly remediated.
