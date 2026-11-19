# Archipelago S5-v3.1 — Independent Verification & Engineering Release Gate

**Date:** 2026-11-19  
**Audit Role:** Stage F — Independent Verification & Engineering Release Gate (`@verifier`)  
**Canonical Repository:** `/home/pratay-karali/Desktop/archipelago`  
**Branch / Base Commit:** `research/s5-v3-1-oa-corpus-expansion-canonical` (from `7f3a01ab81bfdd47972d514a82cc59d35ac195cd`)

---

## 1. Dual Gate Verdicts

| Gate | Verdict | Meaning |
|---|---|---|
| **Engineering Gate** | **`ENGINEERING_GO`** | All S5-v3.1 engineering deliverables (Stages A–E) pass independent test, lint, line-limit, privacy, determinism, and frozen-artifact integrity checks. Safe to commit all **48** public files and proceed to human query audit. |
| **Scientific Human Gate** | **`HUMAN_VALIDATION_PENDING`** | `0` human query verifications, `0` human negative-control verifications, `0` human relevance judgments, `0` adjudications, and `0` real S5-D1 evaluations have been performed. No effectiveness, system superiority, or statistical significance claims are authorized until human validation and investigator-authorized S5-D1 complete. |

---

## 2. Stage-by-Stage Independent Verification (Stages A–E)

| Stage | Owner | Status | Key Verified Evidence |
|---|---|---|---|
| **Stages A & B** — OA Source Retrieval & Corpus v3.1 | `@corpus-v3` | **PASS** | 4/4 official OA CS sources verified (OS: Khokhar & Tran CC-BY-4.0; DB: Watt & Eng 2e CC-BY-4.0 via official Engineering LibreTexts mirror after primary `opentextbc.ca` Cloudflare 403 was honestly NOT bypassed; Networks: Bonaventure `cnp3` `155b3a61...` CC-BY-SA-3.0; Distributed Systems: Kleppmann `ept/dist-sys` `b8167ac3...` CC-BY-SA-4.0; `mixu/distsysbook` strictly excluded). Deterministic Corpus v3.1 (`1,958` passages = `818` retained S5-v3 + `1,140` new OA CS across `8` domains; SHA-256 `63664771...`, `0` dependence on `okf_graph.db`) stored under Git-ignored `data/annotation_local/s5v3_1/corpus_v31/`. `4/4` tests pass; `ruff` 0 errors; max `377`L. |
| **Stage C** — Model Pin Verification & Retrieval v3.1 | `@retrieval-v3` | **PASS** | Essential model `Snowflake/snowflake-arctic-embed-m-v1.5` (`e58a8f75...`, Apache-2.0) verified **11/11** file SHA-256s + offline CPU smoke test PASS; zero optional rerankers downloaded. Hash-pinned dense cache (`[1958, 768]`, SHA-256 `c02f817f...`) stored under Git-ignored `data/annotation_local/s5v3_1/embeddings/`. `8/8` systems passed repeat-run determinism (`all_systems_deterministic=True`); Corpus v3.1 graph coverage `183/610` (`30.00%`) concepts, `341/1,988` (`17.15%`) edges; actual relevance-agnostic unique pools measured (`1,001` @ `k=5`, `1,855` @ `k=10`); `effectiveness_evaluation: "NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS"`. `5/5` tests pass; `ruff` 0 errors; max `436`L. |
| **Stage D** — Multi-Domain Proposed Queries & Blinded Audit Workbook | `@benchmark-v3` | **PASS** | `72` proposed queries (`24` dev / `48` test; `44` retained S5-v3 + `28` new CS-domain) covering all `8` OA docs, zero dev/test overlap, zero v2.1 reuse, all categories/necessity claims labeled `PROVISIONAL_PENDING_HUMAN_VERIFICATION`. Fresh blinded human audit workbook (`72` items, strictly blank decisions/attestation, `0` relevance grades) stored under Git-ignored `data/annotation_local/s5v3_1/query_audit/`. `5/5` tests pass; `ruff` 0 errors; max `490`L. |
| **Stage E** — Python-Verified Cost & Strategy Forecast | `@eval-design-v3` | **PASS** | `S5V31_ANNOTATION_COST.md` + `reports/s5v31_cost_estimate.json` grounded in actual Stage A–D pools (`1,001` @ `k=5`, `1,855` @ `k=10`), clearly separating estimated vs. `0` completed human annotations; recommends phased `test_only_depth_10` strategy (`80.03 hr` incl. test QV/NC, `$0.00` marginal cloud cost, `1.87 GB` local Git-ignored footprint). |

---

## 3. Independent Engineering, Integrity & Privacy Checks

### 3.1 Automated Test Results
- **S5-v3.1 New Unit Tests (`pytest tests/unit/test_s5v31_*.py -v`):** **`14 passed, 0 failed`** (`1.33s`):
  - `tests/unit/test_s5v31_corpus_builder.py`: **4 passed**
  - `tests/unit/test_s5v31_benchmark.py`: **5 passed**
  - `tests/unit/test_s5v31_retrieval.py`: **5 passed**
- **All 14 Reproducible S5 Research Suites (S5-B1/B2/C2/D0 + S5-C3 + S5-v3 + S5-v3.1):** **`113 passed, 9 skipped, 0 failed`** (`4.58s`).
- **Historical Missing-Data Limitation (Honest Disclosure):** `tests/unit/test_s5a_retrieval_integrity.py::test_precomputed_embeddings_cache_validity` remains blocked (`13 passed, 1 fail`) solely because historical S5-v2.1 local `okf_graph.db` (`s5a_eval_corpus_v1`, 713 passages) is absent on disk; historical Reviewer A workbook (`70049fa8...`) likewise remains `BLOCKED`. S5-v3.1 operates with **zero dependence** on `okf_graph.db`.

### 3.2 Code Quality (`AGENTS.md` Compliance)
- **`ruff check research/s5-v3-1-oa-corpus-expansion/ tests/unit/test_s5v31_*.py`:** **`All checks passed!`** (`0` errors).
- **File Size Limit (`<= 500` lines):** **`33 / 33` Python files compliant** (maximum: `490` lines in `benchmark_v31/validator.py`).
- **`from __future__ import annotations`:** **`33 / 33` present**.
- **Banned Patterns Scan** (`except: pass`, `except Exception: pass`, `shell=True`, `eval(`, `exec(`, `os.system`, `pickle.load`, `yaml.load(`, `verify=False`): **`0` hits**.

### 3.3 Frozen Artifact Integrity & Git/Privacy Hygiene
- **Frozen S5-v2.1 Preservation Manifest (`s5d0_preservation_manifest.json`):** **`19 / 19` tracked frozen artifacts verified exact SHA-256 match** (`0` mismatches; `2` local Git-ignored S5-C2 originals remain absent as documented).
- **Prior S5-v3 Committed Artifacts:** **`git diff HEAD -- research/s5-v3-benchmark-expansion/` empty** (`0` modifications).
- **Privacy & Git Hygiene:** **`5 / 5`** private directories/files (`raw_sources/`, `s5v31_corpus_passages.jsonl`, `s5v31_snowflake_embeddings.npy`, `s5v31_query_audit_workbook.json`, `model.safetensors`) verified Git-ignored via `git check-ignore -q` (`.gitignore:141`). **0** raw source passages, private workbooks, or model weights appear in `git status`.
- **Scientific Integrity:** **0** fabricated page numbers (`page_start=None` preserved honestly for EPUB/HTML/TeX sources), **0** fabricated human judgments or approvals, **0** real S5-D1 runs, **0** effectiveness claims.

---

## 4. Exact Safe-to-Commit S5-v3.1 File Inventory (48 Files)

### 4.1 Markdown Reports (8 Files)
- `research/s5-v3-1-oa-corpus-expansion/S5V31_SOURCE_LICENSE_REGISTER.md`
- `research/s5-v3-1-oa-corpus-expansion/S5V31_CORPUS_BUILD_REPORT.md`
- `research/s5-v3-1-oa-corpus-expansion/S5V31_DOMAIN_COVERAGE.md`
- `research/s5-v3-1-oa-corpus-expansion/S5V31_MODEL_AND_RETRIEVAL_VERIFICATION.md`
- `research/s5-v3-1-oa-corpus-expansion/S5V31_QUERY_CANDIDATES.md`
- `research/s5-v3-1-oa-corpus-expansion/S5V31_HUMAN_QUERY_AUDIT_HANDOFF.md`
- `research/s5-v3-1-oa-corpus-expansion/S5V31_ANNOTATION_COST.md`
- `research/s5-v3-1-oa-corpus-expansion/S5V31_ENGINEERING_RELEASE.md`

### 4.2 Public Metadata-Only Manifests & Relevance-Agnostic Reports (7 Files)
- `research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_source_license_manifest.json`
- `research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_corpus_manifest.json`
- `research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_retrieval_manifest.json`
- `research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_query_benchmark_proposed.json`
- `research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_query_audit_schema.json`
- `research/s5-v3-1-oa-corpus-expansion/reports/s5v31_retrieval_diagnostics.json`
- `research/s5-v3-1-oa-corpus-expansion/reports/s5v31_cost_estimate.json`

### 4.3 Python Modules & CLI Entrypoints (30 Files)
- `research/s5-v3-1-oa-corpus-expansion/scripts/build_corpus_v31.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/corpus_v31/__init__.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/corpus_v31/builder.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/corpus_v31/constants.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/corpus_v31/extractors.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/corpus_v31/models.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/corpus_v31/quality_dedup.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/corpus_v31/registry.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/build_benchmark_v31.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/__init__.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/audit_validator.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/audit_workbook.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/builder.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/catalog_v31_cs_dev.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/catalog_v31_cs_test_core.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/catalog_v31_cs_test_cross_nc.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/catalog_v3_retained.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/constants.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/corpus_index.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/graph_anchors.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/leakage.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/queries_catalog.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/schema.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/benchmark_v31/validator.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/run_retrieval_v31_verification.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/retrieval_v31/__init__.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/retrieval_v31/dense_cache.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/retrieval_v31/model_pin.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/retrieval_v31/pooling.py`
- `research/s5-v3-1-oa-corpus-expansion/scripts/retrieval_v31/runner.py`

### 4.4 Unit Tests (3 Files)
- `tests/unit/test_s5v31_corpus_builder.py`
- `tests/unit/test_s5v31_benchmark.py`
- `tests/unit/test_s5v31_retrieval.py`
