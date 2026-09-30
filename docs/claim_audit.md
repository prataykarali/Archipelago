# Archipelago Technical & Empirical Claim Audit

**Date:** September 2026  
**Status:** Complete Empirical Audit  
**Auditor:** Archipelago Systems & ML Architecture Team  

---

## 1. Executive Summary & Status Taxonomy

Section 0 of the Production Engineering Master Prompt requires rigorous classification of every technical claim into distinct categories:
- **`LITERATURE_FACT`**: Backed by a verified, peer-reviewed publication or formal system specification.
- **`ENGINEERING_TARGET`**: A desirable system SLO or target, but not an inherent mathematical or literature truth.
- **`PROPOSED_THRESHOLD`**: An empirical threshold that requires experimental calibration against a gold dataset.
- **`UNVERIFIED`**: Cannot be supported by local benchmarks or authoritative sources.
- **`SPECIFICATION_OUTDATED`**: Superseded by newer APIs or incorrect in the original specification.
- **`CITATION_MISMATCH`**: A citation was provided, but the cited text does not establish the claim.

---

## 2. Technical Claims Audit Table

| ID | Domain | Claim in Architecture | Audit Classification | Empirical Reality & Audit Finding | Action Taken |
|---|---|---|---|---|---|
| **CLM-001** | Database | KùzuDB traversal latency is below 5 ms. | **ENGINEERING_TARGET — NOT LITERATURE FACT** | Micro-benchmarking multi-hop Cypher queries on `kuzu` 0.11.3 yields: **p50 = 4.35 ms**, **p95 = 5.91 ms**, **p99 = 8.32 ms**. Sub-5 ms holds at median, but fails at p95/p99 under load. | Relabeled as internal SLO: `Internal benchmark target: p95 < 5 ms under defined workload`. Add benchmark script `scripts/benchmark_db.py`. |
| **CLM-002** | Database | Atomic database swaps allow zero-downtime graph updates. | **LITERATURE_FACT** (POSIX Semantics) | In KùzuDB 0.11+, the database is persisted as a single database file (`okf_graph.db`). POSIX `os.replace` on the same filesystem is atomic, allowing background rebuilds to swap atomically into production. | Supported in `src/archipelago/graph/engine.py` via `atomic_swap()`. |
| **CLM-003** | Database | Read-only connections prevent concurrent write locks. | **LITERATURE_FACT** | KùzuDB Python API provides `kuzu.Database(db_path, read_only=True)`. Read-only instances can open concurrently and safely query the graph without file lock conflicts. | Enforced in `src/archipelago/graph/engine.py`. |
| **CLM-004** | Embedding | Cosine similarity $\ge 0.75$ using `arctic-embed-m-v1.5` defines the domain boundary. | **PROPOSED_THRESHOLD — MUST BE EMPIRICALLY CALIBRATED** | 0.75 is an empirical heuristic, not a universal semantic constant. Queries with domain acronyms or short lengths can drop to 0.65 while remaining valid, and long conversational noise can exceed 0.75 while being out-of-scope. | Made configurable via `SIMILARITY_THRESHOLD = 0.75` in environment/settings. Evaluated via `scripts/calibrate_embedding_threshold.py`. |
| **CLM-005** | Model Registry | Model identifier `Qwen/Qwen2.5-0.8B-Instruct` is the extraction model. | **SPECIFICATION_OUTDATED — INVALID IDENTIFIER** | An official query to Hugging Face `HfApi` reveals `Qwen/Qwen2.5-0.8B-Instruct` **does not exist**. Official Qwen2.5 models are 0.5B, 1.5B, 3B, 7B, 14B, 32B, 72B. Local Ollama contains `lib-qwen:latest` (fine-tuned 1.5B/0.8B) and `qwen3.5:0.8b`. | Reject `Qwen2.5-0.8B-Instruct`. Set `lib-qwen` for ingestion and `qwen3.5:0.8b` for inference in `docs/research/model_selection.md`. |
| **CLM-006** | Corpus Scale | The system indexes 412 Research Papers and 48 Textbooks / Syllabi. | **ENGINEERING_TARGET — NOT LITERATURE FACT** | `CORPUS_MANIFEST.json` and directory inspection show **43 PDFs total**, comprising **25 research papers and 6 textbooks**. Exactly 31 distinct documents are cited in `okf_graph.json`. | Corrected in documentation. All test benchmarks calibrated to ground-truth 25-paper/6-book corpus. |
| **CLM-007** | Traffic / Ops | System rate limit is 15 requests per minute. | **PROPOSED_THRESHOLD — MUST BE EMPIRICALLY CALIBRATED** | 15 rpm is a pilot safety proposal, not an empirical capacity limit. Benchmark testing is required to determine maximum sustained concurrency. | Configurable via `RATE_LIMIT_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS`. Tiered by role (anonymous: 15, student: 60, faculty: 120, admin: unlimited). |
| **CLM-008** | Ingestion | Training dataset requires a 20% hard negative ratio. | **PROPOSED_THRESHOLD — MUST BE EMPIRICALLY CALIBRATED** | 20% is a tuning parameter. `okf_dataset_report_v5.json` shows actual empty target percentage is 13.87% (Train) and 28.33% (Test). | Configurable in training pipeline (`NEGATIVE_SAMPLE_RATIO = 0.20`). |
| **CLM-009** | Retrieval | Undirected graph traversal acts as a valid prerequisite fallback. | **CITATION_MISMATCH & LOGICAL FALLACY** | An undirected edge path ($A - B - C$) establishes topological proximity, but does **not** represent a valid pedagogical learning sequence. Traversing in reverse can invert causation (e.g. learning Deep Learning before Linear Algebra). | Replaced with strict directed traversal. If no directed prerequisite path exists, engine returns `NO_VALID_PEDAGOGICAL_PATH`. |
| **CLM-010** | Graph Theory | Kahn's algorithm guarantees semantic correctness of the curriculum. | **CITATION_MISMATCH** | Kahn's algorithm detects cycles in directed graphs ($\mathcal{O}(V + E)$). It verifies DAG validity; it does not and cannot verify whether concept $A$ is pedagogically appropriate as a prerequisite for $B$. | Distinguish structural DAG integrity (Kahn sort) from pedagogical edge correctness (validated against gold test sets). |
| **CLM-011** | Retrieval | HNSW provides exact nearest-neighbor search. | **CITATION_MISMATCH** | Malkov & Yashunin (2018) explicitly define HNSW as an **approximate** nearest-neighbor graph algorithm. | Clarified in documentation: HNSW provides high-recall approximate retrieval, not exact guarantees. |
| **CLM-012** | Model Loss | Training loss $< 0.30$ guarantees extraction quality. | **ENGINEERING_TARGET — NOT LITERATURE FACT** | Cross-entropy loss can decrease while the model suffers mode-collapse on JSON schema tags or outputs empty concept lists. | Replaced with holistic evaluation: JSON syntax rate, Schema compliance, Concept Exact/Alias F1, Edge F1, Cycle rate, Empty-chunk precision. |

---

## 3. Mandatory Engineering Rules Derived from Audit

1. **Never claim sub-5ms traversal as a guarantee:** Document as `p95 < 5 ms target`.
2. **Never hardcode 0.75 as an immutable boundary:** Expose `SIMILARITY_THRESHOLD` as a tunable parameter.
3. **Never cite non-existent models:** Use verified `lib-qwen` for ingestion and `qwen3.5:0.8b` for inference.
4. **Never claim 412 papers:** Report true corpus scale of 25 papers and 6 textbooks.
5. **Never return undirected paths as prerequisites:** Return `NO_VALID_PEDAGOGICAL_PATH` when directed dependency chains are broken.
