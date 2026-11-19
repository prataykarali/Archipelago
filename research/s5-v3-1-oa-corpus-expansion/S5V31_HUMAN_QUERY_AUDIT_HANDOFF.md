# S5-v3.1 Stage D — Blinded Human Query-Audit Handoff & Quality Concerns

**Date:** 2026-11-19  
**Audit Schema (Public, Metadata-Only):** [s5v31_query_audit_schema.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_query_audit_schema.json) (`997e3679e453cdc3027db8c6d6e52acfe6914b12bae757d9cbf564dfb7c49154`)  
**Private Blinded Workbooks (Git-Ignored, `data/annotation_local/s5v3_1/query_audit/`):**
- `s5v31_query_audit_workbook.md` (SHA-256 `db02a9452566d3d8346c93f534a38bcddb23d3fd25a2bcca102fcd3b4e32ba54`) — human-readable blinded review workbook with passage excerpts
- `s5v31_query_audit_workbook.csv` (SHA-256 `74ec48edecd1ace004c7636230ce80a3149a2eaede7dafaa03542d90c8cd82c5`) — tabular blank decision sheet
- `s5v31_query_audit_workbook.json` (SHA-256 `ab04e025f6448d2954dee95769a9f4c54860ca4e91a31185234314992e9fd72c`) — machine-validatable blank workbook (`72` items, `0` pre-filled decisions, `0` relevance grades)

---

## 1. Blinded Investigator Review Instructions

1. **Independence & Zero AI Assistance:** Complete the audit independently without using LLMs or automated answer generators. Set `assistance_declaration: "NONE_INDEPENDENT_HUMAN"` and sign `reviewer_attestation` before submitting.
2. **Blinding Rules:** The `72` queries are presented in deterministic SHA-256 shuffled order (`AUDIT-01` .. `AUDIT-72`). Split assignment (`dev` vs `test`) and `graph_anchor_regime` (`rich` vs `sparse`) are hidden to prevent evaluation bias.
3. **Zero Relevance Grading:** This workbook audits **query validity, grounding, necessity, and negative-control unanswerability ONLY**. Do **not** assign passage relevance grades here; the submission validator rejects any relevance-grade fields (`FORBIDDEN_RELEVANCE_GRADE_FIELD`).
4. **Required Per-Query Fields (All Currently BLANK):**
   - `human_decision`: `ACCEPT` | `REVISE` | `REJECT`
   - `human_necessity_verified`: `YES` | `NO` | `NA` (verify whether all passages in `minimum_required_evidence_set` are truly needed)
   - `human_shortcut_found`: `YES` | `NO` | `NA` (flag if any single passage answers a proposed multi-passage/cross-doc query)
   - `human_negative_control_classification`: `CONFIRMED_UNANSWERABLE` | `PARTIALLY_ANSWERABLE_IN_CORPUS` | `ANSWERABLE_IN_CORPUS` | `NOT_APPLICABLE_POSITIVE_QUERY`
   - `human_correction_or_rationale`: mandatory (`>= 8` chars) for all `REVISE` or `REJECT` decisions.

### Submission Validation Command

```bash
python3 research/s5-v3-1-oa-corpus-expansion/scripts/build_benchmark_v31.py \
  --validate-submission data/annotation_local/s5v3_1/query_audit/<completed_submission.json>
```

The validator (`benchmark_v31.audit_validator`) strictly rejects:
- Pre-filled decisions in blank workbooks (`PREFILLED_HUMAN_DECISION`, `PREFILLED_SIGNATURE`)
- Unsigned submissions (`UNSIGNED_ATTESTATION`, `MISSING_REVIEWER_METADATA`)
- Blank/invalid decisions or missing rationales for `REVISE`/`REJECT`
- Missing negative-control classifications or injected relevance-grade fields.

---

## 2. Disclosed Benchmark Quality Concerns for Human Reviewers

1. **AI-Proposed / Corpus-Aware Authorship Bias:** All `72` queries were proposed with direct visibility into Corpus v3.1 passages. Reviewers should check for overly narrow phrasing or unnatural alignment with specific passage wording and mark such items `REVISE`.
2. **Explicit Source-Title Cueing in Retained S5-v3 Queries:** `35` of the `44` retained S5-v3 queries (including all `10` retained ML/Math/NLP/Robotics cross-doc queries) name source books/authors explicitly (e.g., *"Dive into Deep Learning"*, *"Mathematics for Machine Learning"*, *"Willard and Louf"*, *"METATRON"*). By contrast, the `28` new CS-domain queries (`Q-S5V31-45..72`) avoid explicit textbook titles. Reviewers should evaluate whether retained v3 queries should be de-cued (`REVISE`) before pooling so BM25 cannot exploit title matching.
3. **Residual Domain Skew Toward MML (`local_oa_003`):** Although Corpus v3.1 now covers all `8` domains, `local_oa_003` still accounts for `719 / 1,958` (`36.7%`) of passages and `23 / 64` (`35.9%`) of positive queries (vs `6–9` queries per other source doc). Domain-stratified macro-averaging should be used alongside overall micro-averages.
4. **Corpus Quality Flags & Non-PDF Section References:** `13` cited passages from retained S5-v3 queries carry Corpus v3 boundary truncation flags (`MID_SENTENCE_TRUNCATION_START/END`), and `oa_os_001`, `oa_db_001`, and `oa_ds_001` use `section_ref` without PDF page numbers (`page_start=null`). All concerns are surfaced per item in `source_provenance_concerns` in the private workbook.
5. **Statistical Power & Test Split Size:** With `48` test queries (`42` positive + `6` negative controls), `N_test_pos = 42` is substantially stronger than S5-v3 (`27`) but still slightly below the `50`-topic rule of thumb (Sakai, 2016); paired randomization tests and bootstrap confidence intervals remain mandatory.
6. **Negative-Control Verification:** Programmatic regex absence checks (`0` hits across `1,958` passages) cannot rule out indirect conceptual coverage. Human reviewers must confirm `CONFIRMED_UNANSWERABLE` on all `8` negative controls before pooling.
