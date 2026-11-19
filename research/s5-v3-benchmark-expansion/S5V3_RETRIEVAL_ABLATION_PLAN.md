# S5-v3 Retrieval Engineering Improvements & Ablation Plan (Module D)

**Date:** 2026-11-19  
**Schema Version:** `s5v3-retrieval-v3.0`  
**Package:** `research/s5-v3-benchmark-expansion/scripts/retrieval_v3/`  
**Diagnostics CLI:** `research/s5-v3-benchmark-expansion/scripts/run_retrieval_v3_diagnostics.py`  
**Unit Test Suite:** `tests/unit/test_s5v3_retrieval_v3.py`  
**Frozen S5-v2.1 Controls:** **100% UNMODIFIED** (all six frozen S5-v2.1 systems remain untouched as controls).

---

## 1. Scientific Boundary: Software Correctness vs. Relevance Improvement

> [!IMPORTANT]
> **Strict Distinction Between Software Correctness and Retrieval Effectiveness**
> - **Software Correctness (VERIFIED):** Verified deterministically by unit tests (`tests/unit/test_s5v3_retrieval_v3.py`) and relevance-agnostic technical diagnostics (`reports/s5v3_retrieval_diagnostics.json`: latency, memory, anchor hit rate, fallback rate, short-list rate, backfill count, graph coverage).
> - **Relevance Improvement (UNMEASURED):** Retrieval effectiveness (nDCG@k, Recall@k, MRR, Precision@k) is **strictly `NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS`**. No human relevance labels exist yet for Corpus v3 + S5-v3 queries. **Zero relevance gain or system superiority claims are made in this document.**

---

## 2. Recorded S5-v3 Variant Configurations & Deterministic SHA-256 Hashes

All six S5-v3 system variants are defined in `retrieval_v3/config.py` (`build_standard_v3_variants()`). Each variant's configuration is canonically serialized (`sort_keys=True, separators=(",", ":")`) and hashed with SHA-256 (`RetrievalV3Config.config_sha256()`).

| Variant Name | Mode | Boundary | Aliases | Grounded | Edge Conf. | Fallback | Backfill | Max Hops | Coverage Routing | Deterministic Config SHA-256 |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `v3_lexical_bm25_control` | `lexical` | `False` | `False` | `False` | `False` | `False` | `False` | `0` | `False` | `ce5c06bc51045371e844a16e1a83223e200aef2836008fd0e5ddf4c3d860c1be` |
| `v3_graph_naive_substring_ablation` | `graph` | `False` | `False` | `True` | `False` | `False` | `False` | `1` | `False` | `baedfc1c02bd7a209502b0234a09dcb690db1ddc178060f5ee5e7af183b45041` |
| `v3_graph_1hop_no_backfill` | `graph` | `True` | `True` | `True` | `True` | `True` | `False` | `1` | `False` | `899340783bc76312ffb01a4e595016388383ecd458de336d3fcbfef6569982f3` |
| `v3_graph_1hop_backfill` | `graph` | `True` | `True` | `True` | `True` | `True` | `True` | `1` | `False` | `12534da6f856505d6c31558d7b6090e3f8383addc48feb19edad6552d4b052a4` |
| `v3_graph_2hop_backfill` | `graph` | `True` | `True` | `True` | `True` | `True` | `True` | `2` | `False` | `590a2bd86c681d9100b6873aa34870571d0c10d2b67603c55ebfdaaf0b020e0a` |
| `v3_graph_2hop_coverage_routed` | `graph` | `True` | `True` | `True` | `True` | `True` | `True` | `2` | `True` | `5af80badfba24b90807cbda944f1d7150a995e6406d1de6ea0539402e85cc1be` |

**Shared Named Constants (`retrieval_v3/config.py`):**
- `DEFAULT_TOP_K = 10`
- `DEFAULT_BM25_K1 = 1.5`, `DEFAULT_BM25_B = 0.75`, `DEFAULT_RRF_K = 60`
- `DEFAULT_HOP_DECAY = 0.5`, `DEFAULT_MAX_FANOUT_PER_NODE = 8`
- `DEFAULT_MIN_COVERAGE_FOR_GRAPH = 0.15`, `DEFAULT_HIGH_COVERAGE_THRESHOLD = 0.50`
- `DEFAULT_GRAPH_HEAVY_WEIGHT = 0.65`, `DEFAULT_BALANCED_GRAPH_WEIGHT = 0.35`
- `EDGE_TYPE_WEIGHTS = {"REQUIRES": 1.0, "PART_OF": 0.9, "ENABLES": 0.85, "USES": 0.8, "CONTRASTS_WITH": 0.7, "RELATED": 0.5}`
- `EDGE_CONFIDENCE_WITH_SOURCE = 0.85`, `EDGE_CONFIDENCE_CO_MENTION = 0.60`, `EDGE_CONFIDENCE_NO_SOURCE = 0.50`

---

## 3. Detailed Specification & Ablation Matrix for All 9 Improvements

### Improvement 1: Token-Boundary-Aware Graph Anchor Matching
- **Module:** `retrieval_v3/normalization.py` (`ConceptAnchorMatcher`)
- **Explicit Hypothesis:** Enforcing alphanumeric token-boundary regex matching (`(?<![a-z0-9_])<surface>(?![a-z0-9_])`) eliminates spurious substring anchor triggers (e.g., `log` matching `catalog`/`logarithm`, `tree` matching `street`) that caused false graph traversal in v2.1.
- **Targeted Unit Test:** `test_imp1_boundary_aware_anchor_matching_prevents_substring_false_positives`
- **Ablation Toggle & Comparison:** `use_boundary_matching: bool` (`True` vs `False`; compared in `v3_graph_naive_substring_ablation` vs `v3_graph_1hop_no_backfill`).
- **Possible Negative Effects / Failure Modes:** May reduce raw anchor hit rate when a valid concept appears embedded in a compound identifier or morphological variant not covered by the normalization table (e.g., `subtrees` vs `tree`).
- **Verification Status:** Software correctness **VERIFIED**; relevance impact **UNMEASURED** (pending human judgments).

### Improvement 2: Concept Aliases and Technical-Term Normalization
- **Module:** `retrieval_v3/normalization.py` (`normalize_technical_text`, `singularize_token`, `CURATED_TECHNICAL_ALIASES`)
- **Explicit Hypothesis:** Case-folding, hyphen/underscore/slash canonicalization, conservative plural/irregular singularization (`matrices -> matrix`, `eigenvalues -> eigenvalue`), and curated technical acronym aliases (`SVD`, `PCA`, `SGD`, `MLE`, `LLM`, `FSM`, `CFG`, etc.) recover legitimate concept anchors missed by exact canonical string matching without introducing substring noise.
- **Targeted Unit Test:** `test_imp2_concept_aliases_and_technical_term_normalization`
- **Ablation Toggle & Comparison:** `use_alias_normalization: bool` (`True` vs `False`).
- **Possible Negative Effects / Failure Modes:** Ambiguous short acronyms (e.g., `map` for *Maximum A Posteriori* vs. geographic/data-structure *map*; `pdf` for *Probability Density Function* vs. *Portable Document Format*) can trigger false-positive anchors in cross-domain text.
- **Verification Status:** Software correctness **VERIFIED**; relevance impact **UNMEASURED**.

### Improvement 3: Corpus-Grounded Concept-to-Passage Mapping
- **Module:** `retrieval_v3/corpus_grounding.py` (`build_corpus_grounded_index`, `GroundedGraphIndex`)
- **Explicit Hypothesis:** Constructing a deterministic inverted index directly from Corpus v3 passages + `okf_graph.json` concepts with exact `ConceptPassageLink` provenance (`passage_id`, `source_doc_id`, `page_start`, `matched_surface`, `match_kind`) and SHA-256 fingerprinting eliminates stale Kùzu chunk-ID drift and guarantees 100% corpus-scoped retrieval.
- **Targeted Unit Test:** `test_imp3_corpus_grounded_concept_to_passage_mapping_and_provenance`
- **Ablation Toggle & Comparison:** `use_corpus_grounded_mapping: bool` (`True` vs `False`).
- **Possible Negative Effects / Failure Modes:** Concepts present in `okf_graph.json` whose canonical/alias surfaces never appear verbatim in Corpus v3 passages remain ungrounded (`0` passages), exposing domain mismatch between the legacy graph and Corpus v3 (which is measured honestly rather than hidden).
- **Verification Status:** Software correctness **VERIFIED**; relevance impact **UNMEASURED**.

### Improvement 4: Graph Edge Provenance, Confidence, and Coverage Instrumentation
- **Module:** `retrieval_v3/corpus_grounding.py` (`normalize_edge_type`, `resolve_edge_confidence`, `coverage_summary`) & `retrieval_v3/traversal.py` (`compute_query_coverage`)
- **Explicit Hypothesis:** Normalizing raw `okf_graph.json` relations, assigning explicit provenance-based confidence weights (distinguishing sourced edges, `co_mention` edges, and unsourced edges), and instrumenting per-query non-stopword anchor coverage enables transparent stratification of graph behavior and prevents noisy `co_mention` edges from dominating typed prerequisite/structural edges.
- **Targeted Unit Test:** `test_imp4_graph_edge_provenance_confidence_and_coverage_instrumentation`
- **Ablation Toggle & Comparison:** `use_edge_confidence_weighting: bool` (`True` vs `False`).
- **Possible Negative Effects / Failure Modes:** Provenance-based confidence priors (`0.85` / `0.60` / `0.50`) are heuristic rather than calibrated on human relevance data; miscalibrated edge weights could overweight noisy sourced edges or underweight useful co-mentions.
- **Verification Status:** Software correctness **VERIFIED**; relevance impact **UNMEASURED**.

### Improvement 5: Deterministic Zero-Anchor Fallback
- **Module:** `retrieval_v3/traversal.py` (`execute_graph_search`)
- **Explicit Hypothesis:** Explicitly falling back to deterministic `BM25LexicalControl` whenever `0` anchors match (`fallback_reason="zero_anchors_matched"`) or matched anchors have `0` grounded Corpus v3 passages (`fallback_reason="zero_grounded_passages"`) eliminates empty result lists while maintaining exact provenance (`fallback_triggered=True`, per-rank `source="fallback"`).
- **Targeted Unit Test:** `test_imp5_deterministic_zero_anchor_fallback_and_toggle`
- **Ablation Toggle & Comparison:** `enable_zero_anchor_fallback: bool` (`True` vs `False`; compared in `v3_graph_naive_substring_ablation` vs `v3_graph_1hop_no_backfill`).
- **Possible Negative Effects / Failure Modes:** High fallback rates can mask poor graph coverage, making a graph retriever behave identically to BM25 on a large fraction of queries if results are not stratified into fallback vs. non-fallback slices during human evaluation.
- **Verification Status:** Software correctness **VERIFIED**; relevance impact **UNMEASURED**.

### Improvement 6: Partial-List Backfill When Fewer Than Top-K Passages Returned
- **Module:** `retrieval_v3/traversal.py` (`execute_graph_search`)
- **Explicit Hypothesis:** When graph retrieval returns `0 < N < Top-K` passages, deterministically backfilling the remaining `Top-K - N` slots from `BM25LexicalControl` (deduplicating already-ranked passages and tagging each rank `"graph"` vs `"backfill"`) eliminates short-list truncation penalties at `@K` while preserving complete auditability.
- **Targeted Unit Test:** `test_imp6_partial_list_backfill_provenance_and_toggle`
- **Ablation Toggle & Comparison:** `enable_partial_backfill: bool` (`True` vs `False`; directly compared in `v3_graph_1hop_no_backfill` vs `v3_graph_1hop_backfill`).
- **Possible Negative Effects / Failure Modes:** Backfilling weak graph results can conflate lexical retrieval quality with graph retrieval quality at ranks `N+1..K`; human evaluation MUST report both full-list metrics and graph-only (pre-backfill) slices.
- **Verification Status:** Software correctness **VERIFIED**; relevance impact **UNMEASURED**.

### Improvement 7: Controlled One-Hop and Two-Hop Graph Traversal
- **Module:** `retrieval_v3/traversal.py` (`traverse_controlled_graph`)
- **Explicit Hypothesis:** Bounding multi-hop expansion with explicit `max_hops` (`0`/`1`/`2`), multiplicative `hop_decay` (`0.5^hop`), deterministic `max_fanout_per_node` (`8`), and a `visited_depth` cycle guard prevents hub-node topic drift and `A -> B -> A` score inflation while recording per-hop attribution (`hop_concept_counts`, `paths_traversed`).
- **Targeted Unit Test:** `test_imp7_controlled_multihop_traversal_decay_fanout_and_cycle_guard`
- **Ablation Toggle & Comparison:** `max_hops` (`1` vs `2` in `v3_graph_1hop_backfill` vs `v3_graph_2hop_backfill`), `hop_decay`, `max_fanout_per_node`, `enforce_cycle_guard`.
- **Possible Negative Effects / Failure Modes:** Aggressive fanout caps (`max_fanout_per_node=8`) may prune relevant neighbors on high-degree hub concepts, whereas 2-hop expansion can still introduce off-topic concepts if `okf_graph.json` contains noisy `co_mention` bridges.
- **Verification Status:** Software correctness **VERIFIED**; relevance impact **UNMEASURED**.

### Improvement 8: Coverage-Aware Retrieval Routing
- **Module:** `retrieval_v3/traversal.py` (`decide_coverage_route`, `weighted_rrf_fuse`)
- **Explicit Hypothesis (Falsifiable):** Routing/weighting graph vs. lexical rankings strictly by measured query anchor coverage (`query_anchor_coverage_ratio`) and grounded support (`grounded_anchor_ratio`) — assigning `lexical_only` when coverage `< 0.15`, `balanced_hybrid` (`0.35 / 0.65`) for moderate coverage, and `graph_heavy` (`0.65 / 0.35`) when coverage `>= 0.50` — will reduce graph-induced degradation on low-coverage queries without losing graph signal on high-coverage queries. *(Falsifiable once human relevance labels exist: compare `v3_graph_2hop_coverage_routed` against `v3_graph_2hop_backfill` and `v3_lexical_bm25_control` stratified by coverage tier.)*
- **Targeted Unit Test:** `test_imp8_coverage_aware_retrieval_routing_and_ablation_toggle`
- **Ablation Toggle & Comparison:** `enable_coverage_routing: bool` (`True` vs `False`; directly compared in `v3_graph_2hop_backfill` vs `v3_graph_2hop_coverage_routed`).
- **Possible Negative Effects / Failure Modes:** Coverage thresholds (`0.15`, `0.50`) and blend weights (`0.35`, `0.65`) are fixed prior to human evaluation; a query with high lexical coverage of generic concepts might still be better served by BM25 than graph-heavy fusion, and RRF discards raw score magnitudes.
- **Verification Status:** Software correctness **VERIFIED**; relevance impact **UNMEASURED**.

### Improvement 9: End-to-End Timing and Memory Measurements
- **Module:** `retrieval_v3/instrumentation.py` (`measure_call`, `summarize_telemetry`)
- **Explicit Hypothesis:** Instrumenting both index construction and per-query execution with `time.perf_counter_ns()` and `tracemalloc` (`peak_memory_bytes`, `current_memory_bytes`) yields reproducible latency (`mean`, `std`, `min`, `p50`, `p95`, `max`, `total`) and peak-memory distributions across all variants.
- **Targeted Unit Test:** `test_imp9_timing_and_memory_instrumentation`
- **Ablation Toggle & Comparison:** `measure_memory: bool` (`True` vs `False`; disabling `tracemalloc` measures pure uninstrumented latency overhead).
- **Possible Negative Effects / Failure Modes:** Enabling `tracemalloc` adds Python allocation tracking overhead to wall-clock latency (`latency_ms`); timing comparisons across variants remain apples-to-apples when all variants run with the same `measure_memory` setting, and pure latency sweeps can set `measure_memory=False`.
- **Verification Status:** Software correctness **VERIFIED**; relevance impact **N/A (systems telemetry)**.

---

## 4. Verification Summary

- **Unit Tests:** `python3 -m pytest tests/unit/test_s5v3_retrieval_v3.py` — **11/11 passed** (covers all 9 improvements, ablation toggles, SHA-256 config hash determinism, and CLI end-to-end).
- **Linting:** `ruff check` on `research/s5-v3-benchmark-expansion/scripts/retrieval_v3/`, `research/s5-v3-benchmark-expansion/scripts/run_retrieval_v3_diagnostics.py`, and `tests/unit/test_s5v3_retrieval_v3.py` — **0 issues**.
- **Diagnostics Output:** `research/s5-v3-benchmark-expansion/reports/s5v3_retrieval_diagnostics.json` (SHA-256: `54b021e0c6ae06d680691d63519341c3991f5cfdb380c37732c2c5609d1ebf78`), executed against Corpus v3 (`858` passages, SHA-256 `dd8e973b727a981aeb4b8d0109513616c4ea709afe3eed40bde5c8b14ebeaee4`), canonical `okf_graph.json` (`610` concepts, `1,988` edges), and `s5v3_query_benchmark_proposed.json` (`48` queries, SHA-256 `17914918ac1355a8e4768cf0fc57629c85d43630d244bbfee3f004a5c611c153`).

---

## 5. Observed Relevance-Agnostic Technical Diagnostics (Corpus v3, 48 Proposed Queries)

> [!NOTE]
> All numbers below are **strictly relevance-agnostic technical telemetry** (`effectiveness_evaluation = "NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS"`). Under boundary + alias normalization, **139 / 610 (22.79%)** `okf_graph.json` concepts and **270 / 1,988 (13.58%)** graph edges are grounded in Corpus v3 (`858` passages).

| Variant | Anchor Hit | Fallback | Short-List (Before → After) | Zero-Result After | Backfill Passages | Mean Query Coverage | Mean Latency (ms) | p95 Latency (ms) | Max Peak Mem (B) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `v3_lexical_bm25_control` | 0/48 | 0/48 | 0 → 0 | 0 | 0 | 0.0000 | 40.6775 | 60.0620 | 124,807 |
| `v3_graph_naive_substring_ablation` | 45/48 (93.8%) | 0/48 | 6 → 6 | 3 | 0 | 0.1752 | 10.4349 | 24.2103 | 515,508 |
| `v3_graph_1hop_no_backfill` | 42/48 (87.5%) | 8/48 (16.7%) | 1 → 1 | 0 | 0 | 0.1910 | 16.8984 | 32.6511 | 444,476 |
| `v3_graph_1hop_backfill` | 42/48 (87.5%) | 8/48 (16.7%) | 1 → 0 | 0 | 1 | 0.1910 | 16.7641 | 33.2548 | 455,268 |
| `v3_graph_2hop_backfill` | 42/48 (87.5%) | 7/48 (14.6%) | 0 → 0 | 0 | 0 | 0.1910 | 25.8832 | 38.0858 | 657,042 |
| `v3_graph_2hop_coverage_routed` | 42/48 (87.5%) | 7/48 (14.6%) | 0 → 0 | 0 | 0 | 0.1910 | 66.6618 | 106.9405 | 684,970 |

**Coverage-Routed Decision Distribution (`v3_graph_2hop_coverage_routed`):** `lexical_only: 17`, `balanced_hybrid: 30`, `graph_heavy: 1`.

