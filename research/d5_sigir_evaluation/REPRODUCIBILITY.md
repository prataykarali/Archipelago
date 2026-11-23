# Archipelago D5 — Evaluation Reproducibility Guide

**Target Venue:** ACM SIGIR 2027 Demonstrations Track  
**Evaluation Directory:** `research/d5_sigir_evaluation/`  
**Evaluation Scripts:** `scripts/benchmarks/d5_1_evaluation_suite.py`, `scripts/benchmarks/d5_relationship_eval.py`, `research/d5_sigir_evaluation/build_blinded_pool.py`

---

## 1. Frozen Dataset & Artifact Checksums (SHA-256)

Every evaluation artifact is frozen. Verify checksums before running or reporting any metric:

| Artifact | Path | SHA-256 |
|---|---|---|
| Dev Split (15 queries) | `research/d5_sigir_evaluation/queries_dev_15.json` | `43893328d55fc5cb0b6f583ee7a20ab0eb36c95e686122db75703d6e6dadbd5b` |
| Held-Out Split (50 queries) | `research/d5_sigir_evaluation/queries_heldout_50.json` | `9e39430942b4f00d34911848cbe61a96532c29ffaee76f0d82ce69496f71103a` |
| Curated Graph Slice (40 edges) | `research/d5_sigir_evaluation/d5_graph_slice.json` | `55140e114dcf192cde59d95271a4cb81f1d099fb4de44b0135c6d95f3e455590` |
| Runtime Corpus & Graph (775 passages, 610 concepts) | `host_inference/fixtures/okf_graph.json` | `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76` |
| Algorithmic Candidate QRels (445 labels, non-human) | `research/d5_sigir_evaluation/passage_qrels.json` | `b3e55ab147907940c6cd90ea5273284558037363066c4cfdd199efa0743bc8a2` |
| Cached Corpus Embeddings `(775, 768)` float32 | `research/d5_sigir_evaluation/corpus_embeddings_snowflake.npy` | `f2fe942e6c07d95337ec22b1bcaaa1e0666e33ee47012518db7a302be7ea26c2` |
| Cached Concept Embeddings `(610, 768)` float32 | `research/d5_sigir_evaluation/concept_embeddings_snowflake.npy` | `db7a019a684b343c92c1a76aac7ebe2f1208362e560c9fffb8b91eec3818a3f3` |

Quick verification command:

```bash
sha256sum \
  research/d5_sigir_evaluation/queries_dev_15.json \
  research/d5_sigir_evaluation/queries_heldout_50.json \
  research/d5_sigir_evaluation/d5_graph_slice.json \
  host_inference/fixtures/okf_graph.json \
  research/d5_sigir_evaluation/passage_qrels.json \
  research/d5_sigir_evaluation/corpus_embeddings_snowflake.npy \
  research/d5_sigir_evaluation/concept_embeddings_snowflake.npy
```

---

## 2. Environment & Pinned Model Provenance

- **Python:** 3.12 (`pytest`, `numpy`, `sentence-transformers`, `torch`)
- **Neural Dense Baseline:** `Snowflake/snowflake-arctic-embed-m`
  - **Pinned HuggingFace Revision:** `fc74610d18462d218e312aa986ec5c8a75a98152`
  - **Embedding Dimensions:** 768, L2-normalized (`normalize_embeddings=True`)
  - **Query Prefix:** `"Represent this sentence for searching relevant passages: "`
  - **Document Prefix:** `""` (empty)
  - **Manifest:** `research/d5_sigir_evaluation/embedding_manifest.json`
- **Lexical Baseline:** BM25Okapi (`k1=1.5`, `b=0.75`) in `archipelago/eval/retrieval_baselines.py`
- **Feature-Hashed Baseline:** BLAKE2b 384-dim token projection (`host_inference/engine/text.py`)
- **Reference Hardware:** Intel x86_64 CPU + NVIDIA GeForce RTX 2050 (4 GB VRAM), Linux 6.8, PyTorch 2.5.1 + CUDA 12.1.

---

## 3. Step-by-Step Reproduction Commands

### 3.1 Run Automated Evaluation Integrity Suite (CPU-Only, Fast)

Exercises the actual evaluator modules (`d5_1_evaluation_suite.py`, `d5_relationship_eval.py`,
`archipelago/eval/retrieval_baselines.py`, `host_inference/engine/answer.py`), verifies all
frozen SHA-256 checksums, checks dev/held-out split leakage, verifies embedding manifest
provenance, and asserts all 731 human worksheet items remain unfilled (`null`/empty):

```bash
PYTHONPATH=.:host_inference pytest tests/unit/test_d5_eval_integrity.py tests/unit/test_d5_evaluator_and_protocol.py -v
```

### 3.2 Re-Run Full D5.1/D5.3 Evaluation Suite (Requires Cached Snowflake Model / GPU)

```bash
PYTHONPATH=.:host_inference python3 scripts/benchmarks/d5_1_evaluation_suite.py
```

Outputs:
- `research/d5_sigir_evaluation/d5_1_evaluation_results_v2.json`
- `research/d5_sigir_evaluation/ranked_runs/{bm25,feature_hashed_vector,snowflake_arctic_neural,archipelago_graph_assisted}.run`

> [!NOTE]
> **External `trec_eval` Whitespace Caveat:** One indexed filename in `okf_graph.json`
> (`papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf`)
> contains internal spaces, producing 2–10 non-6-field lines per `.run` file. The Python
> evaluator (`d5_1_evaluation_suite.py`) and pool builder (`build_blinded_pool.py`) handle
> canonical `doc_id::chunk_id` strings safely in memory; if passing runs to external
> whitespace-delimited `trec_eval`, URL-encode spaces in `docno` in both runs and qrels
> consistently without modifying the frozen corpus fixture.

### 3.3 Rebuild System-Blinded Pooled Top-5 Human Worksheets

```bash
python3 research/d5_sigir_evaluation/build_blinded_pool.py
```

Regenerates deterministically:
- `research/d5_sigir_evaluation/human_annotation_worksheet.json` (731 items, all grades `null`)
- `research/d5_sigir_evaluation/worksheets/reviewer_A_worksheet.csv`
- `research/d5_sigir_evaluation/worksheets/reviewer_B_worksheet.csv`
- `research/d5_sigir_evaluation/worksheets/adjudication_worksheet.csv`
- `research/d5_sigir_evaluation/worksheets/pool_key_SEALED.json`

### 3.4 Quality Gates

```bash
ruff check research/d5_sigir_evaluation/build_blinded_pool.py tests/unit/test_d5_eval_integrity.py tests/unit/test_d5_evaluator_and_protocol.py
python3 scripts/quality_gate.py
```
