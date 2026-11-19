# E0.1 — Freeze, Preservation & Repository Hygiene Audit

**Phase:** S5-E0.1 (Pre-Results Evidence Audit & Paper Preparation Gate)  
**Repository:** `/home/pratay-karali/Desktop/archipelago/Archipelago`  
**Base Commit (`HEAD`):** `6450585f60b3c1bea7bef2f411458800552cea0b` (`research/s5-c2-annotation-audit`)  
**Audit Date:** 2026-11-19  
**Auditor Role:** Senior IR Research Engineer / Experimental-Audit Assistant (`auditor-e01`)

---

## 1. Cryptographic Preservation Verification (Read-Only)

Executed `verify_preserved_artifacts()` from [generate_s5d0_diagnostics.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/scripts/generate_s5d0_diagnostics.py) in strictly read-only mode (zero file writes to S5-D0 or any prior stage) and computed SHA-256 hashes across all 21 S5-D0-tracked frozen artifacts plus 7 S5-D0 deliverables and 9 additional S5-A/B1/B2 reports:

- **21 / 21 S5-D0 preservation checks passed (`all_checks_passed: true`, `mismatches: []`):**
  - **12 / 12 `VERIFIED_EXACT_MATCH`** against hashes anchored in [S5B2_1_FINAL_RELEASE_CHECK.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/S5B2_1_FINAL_RELEASE_CHECK.md) and [s5c2_audit_summary.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c2-annotation-audit/reports/s5c2_audit_summary.json):
    - `s5b2_proposed_blinded_query_specs.json`: `011025237209a5432409e7998c350f5c2c4970cf7f9f96c79ff938e2b729af8a`
    - `retrieval_query_candidate_pool_blinded.csv`: `4c9cb0e58f9f6d32c59eb12804f032be32a6a52c1eeb75055fb5148600f9acd7`
    - `retrieval_query_pool_blinded.json`: `2d13454655dda965304ac4aabddbeef5e39b77bc6927393bebfdaa94235fb037`
    - `RETRIEVAL_ANNOTATION_PROTOCOL.md`: `35a7bc0168431b355f49dc100364493b0ef69d5ff680e3308ca5dcb44dcc46e9`
    - `s5b2_negative_control_audit.json`: `02e143bfd7b8114ad9652c102248daef36464f521f5b0b3ec1d8b3c4e91199d6`
    - `s5b2_1_passage_necessity_matrix.json`: `cc72beff79bcd446401a65b7ed57854f9e82dccca685585a16e79c3bda464921`
    - `s5b2_1_corpus_provenance_registry.json`: `e537f4a42b2f89f63a7d640a7f9f796e951b535dec9eb690ca361bcd49fa81fc`
    - `s5b2_1_frozen_ranked_results.json`: `e20a9f64272c1afa42d62ea7474cb3d9db8e9472c5cf97b639f680e4942eba86`
    - `s5b2_1_topk_pool_coverage_refreshed.json`: `04be54f0574c55ca95d86a95135eba96c6db143cf7185c362e4115f1272d1958`
    - `S5B2_1_APPROVAL_GATE_REPORT.md`: `3250006a650c93675eb1dc96e4df1d07048a5370443e4365529a9fad8ad8db4b`
    - `data/annotation_local/s5c2/originals/reviewer_a_s5b2_1_workbook.md` (local Git-ignored): `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c`
    - `data/annotation_local/s5c2/originals/reviewer_b_s5b2_1_workbook.md` (local Git-ignored): `ca3e6af86c72c20bf6dbd66d71f3c5c79ef7795de5d149d23c0b918304ae80f4`
  - **9 / 9 `RECORDED_UNMODIFIED`** S5-B1.1 and S5-C2 reports/manifests verified byte-identical to [s5d0_preservation_manifest.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/reports/s5d0_preservation_manifest.json).
  - **7 / 7 S5-D0 deliverables** present and unmodified (SHA-256 recorded in [E01_EVIDENCE_INVENTORY.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E01_EVIDENCE_INVENTORY.md) §2.5).

---

## 2. Git Status & Diff Summary

### 2.1 Changes Introduced by E0.1 (Strictly Scoped)
Only four documentation files were created inside `research/s5-e0-pre-results-paper-prep/`:
1. [E01_EVIDENCE_INVENTORY.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E01_EVIDENCE_INVENTORY.md)
2. [E01_CLAIM_EVIDENCE_MATRIX.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E01_CLAIM_EVIDENCE_MATRIX.md)
3. [E01_RESEARCH_GAPS.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E01_RESEARCH_GAPS.md)
4. [E01_FREEZE_AUDIT.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E01_FREEZE_AUDIT.md)

**Diff against `HEAD` (`6450585`) caused by E0.1:** `0` tracked files modified, `0` tracked files deleted, `4` new untracked documentation files in `research/s5-e0-pre-results-paper-prep/`.

### 2.2 Pre-Existing Uncommitted Working-Tree State (Observed, Untouched by E0.1)
Prior to E0.1 execution, `git status --short` and `git diff --stat -- research/ tests/unit/test_s5*` reported the following pre-existing working-tree modifications relative to `6450585` (all left completely untouched):
- **Within `research/` and `tests/unit/test_s5*`:**
  - `D research/s5-c2-annotation-audit/scripts/run_s5c2_audit.py` (`-529` lines; its 4 committed output reports in `research/s5-c2-annotation-audit/reports/` remain intact).
  - `M tests/unit/test_s5b2_benchmark_correction.py` (`1 insertion, 1 deletion`).
  - `?? research/s5-d0-experimental-analysis-prep/` (untracked S5-D0 deliverables).
  - `?? tests/unit/test_s5d0_analysis_prep.py` (untracked S5-D0 unit tests).
- **Outside `research/`:** Pre-existing product/UI/runtime/catalog edits in `host_inference/`, `host_research/`, `data/catalogs/`, `.gitignore`, `.vercelignore`, and untracked files in `artifacts/validation/`, `docs/`, `outputs/`, `supabase/migrations/`. None were modified by E0.1.

---

## 3. Strict Preservation Rules Verification Checklist

- [x] **Documentation-only scope:** All E0.1 writes reside exclusively in `research/s5-e0-pre-results-paper-prep/`.
- [x] **Zero modifications to frozen experimental artifacts:** Datasets (`s5a_eval_corpus_v1`), rankings (`s5b2_1_frozen_ranked_results.json`), graph construction (`repaired_extractor.py`, `okf_graph.db`), evaluation queries (`s5b2_proposed_blinded_query_specs.json`), scoring (`evaluate_gold_labels_readonly.py`), annotations/workbooks (`REV_A`, `REV_B`), AI-assistance disclosures, experiment scripts, and website/UI are 100% untouched.
- [x] **No premature relevance evaluation:** `evaluate_gold_labels_readonly.py` was not executed on unadjudicated labels; zero Recall@k, Precision@k, MRR, or nDCG@k figures were computed.
- [x] **No new experimental runs:** No retrieval runs, latency benchmarks, or synthetic results were generated.
- [x] **Scientific guardrails enforced:** Zero claims of graph superiority, cross-document reasoning gains, or statistical significance; zero fabricated citations or invented results.

---

## 4. Final GO / HOLD Decision for Pre-Results Manuscript Drafting

> ### **DECISION: GO (for Pre-Results Introduction, Related Work, Methods, Technical Diagnostics, and Limitations) / HOLD (for Results & Conclusions)**
>
> | Manuscript Section | Gate Decision | Governing Evidence & Constraints |
> |---|---|---|
> | **Introduction (Problem Framing & Research Questions)** | **GO** | Ground in verified S5-A/B1/B2/D0 motivation; frame as an exploratory, integrity-audited pilot (`N=10`, 7 answerable + 3 provisional negatives). Do not preview effectiveness outcomes. |
> | **Related Work** | **GO** | Ground strictly in verifiable, real peer-reviewed IR/GraphRAG/evaluation literature (e.g., BM25, dense bi-encoders, RRF — Cormack et al., 2009, pooling/blinding/IAA standards). No invented citations. |
> | **Methods & Experimental Setup** | **GO** | Directly backed by [S5D0_EXPERIMENTAL_SETUP.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/S5D0_EXPERIMENTAL_SETUP.md) and `CLM-01`–`CLM-06`, `CLM-12`. Disclose 4-tier provenance registry, 2 held queries, 0 cross-document queries, and planned S5-D1 metrics. |
> | **System Technical Diagnostics (Relevance-Agnostic)** | **GO** | Directly backed by [S5D0_TECHNICAL_DIAGNOSTICS.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/S5D0_TECHNICAL_DIAGNOSTICS.md) and `CLM-07`–`CLM-11`. Explicitly separate relevance-agnostic measurements from latency hypotheses (`H1–H4`) and effectiveness claims. |
> | **Limitations & Threats to Validity** | **GO** | Directly backed by [S5D0_LIMITATIONS_REGISTER.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-d0-experimental-analysis-prep/S5D0_LIMITATIONS_REGISTER.md) (`LIM-01`–`LIM-09`) and [E01_RESEARCH_GAPS.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-e0-pre-results-paper-prep/E01_RESEARCH_GAPS.md). |
> | **Results, Effectiveness Discussion & Conclusions** | **HOLD** | Blocked on S5-C3 (`GAP-B1`–`GAP-B4`: Reviewer B independent human confirmation, adjudication of 51 disagreements, human verification of `Q03`/`Q08`/`Q11`) and S5-D1 (`evaluate_gold_labels_readonly.py`). |
