# S5-C3 — Negative-Control Human Verification Protocol

**Stage:** S5-C3-P0 (Human Adjudication Preparation)  
**Date:** 2026-11-19  
**Status:** `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_HUMAN_VERIFICATION` (0 of 3 verified)

---

## 1. Queries Requiring Independent Human Verification

Three active queries are currently provisional negative controls in [s5b2_negative_control_audit.json](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b2-benchmark-correction/reports/s5b2_negative_control_audit.json) and [S5C2_NEGATIVE_CONTROL_VERIFICATION.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c2-annotation-audit/reports/S5C2_NEGATIVE_CONTROL_VERIFICATION.md):

| Query ID | Legacy ID | Domain | Automated Status | External Premise Status |
|---|---|---|---|---|
| `Q-S5B2-03` | `Q-S5A-03` | Operating Systems | `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK` | `UNVERIFIED_EXTERNAL_PREMISE_PENDING_INDEPENDENT_CHECK` |
| `Q-S5B2-08` | `Q-S5A-08` | AI & Machine Learning | `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK` | `UNVERIFIED_EXTERNAL_PREMISE_PENDING_INDEPENDENT_CHECK` |
| `Q-S5B2-11` | `Q-S5A-11` | Computer Networks | `PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK` | `UNVERIFIED_EXTERNAL_PREMISE_PENDING_INDEPENDENT_CHECK` |

**Restriction:** These queries are **NOT** automatically classified as valid negative controls.

---

## 2. Corpus-Wide Verification Requirement (Not Top-10 Only)

Inspecting only the Top-10 pooled retrieval results is **insufficient** to establish corpus-wide unanswerability. Human verifiers MUST verify against the **entire frozen 713-passage / 53-document corpus (`s5a_eval_corpus_v1`)** using the private Git-ignored worksheet:
- `data/annotation_local/s5c3/s5c3_negative_control_verification_worksheets.md` (`SHA-256: 678cc2fcdd6bd5fa1ce0deec90c6ebdd1ece6e2bd3764c226c1318467e32662c`)

For each query, the private worksheet provides:
1. The complete **53-document inventory** of `s5a_eval_corpus_v1` (with passage counts) so the verifier can inspect whether any in-domain document could plausibly contain the answer.
2. All exact-keyword hit counts and alternate-terminology hit counts from `s5b2_negative_control_audit.json`.
3. Verbatim canonical text from `okf_graph.db` for **every unique passage** surfaced by top-5 dense semantic search, exact keyword hits, AND alternate-terminology hits across the full 713-passage corpus.
4. Blank per-passage inspection fields (`contains_answer`, `inspection_note`) and a field to record any additional manual corpus searches run by the verifier.

---

## 3. Supported Human Outcome Classifications

For each query, the independent human verifier MUST select exactly one classification:

| Classification | Operational Meaning | Downstream Treatment in S5-D1 |
|---|---|---|
| **`NO_ANSWER_IN_FROZEN_CORPUS`** | Human verifier confirms no passage in the 713-passage frozen corpus answers the query (after inspecting hydrated candidates, 53-document scope, and any additional corpus searches). | Treated as a verified corpus-unanswerable negative control; excluded from Recall/MRR/nDCG denominators and reported separately. |
| **`NO_ANSWER_IN_SELECTED_PASSAGES`** | Inspected search-selected passages contain no answer, but full corpus-wide exclusion is not established. | Remains **unverified** for corpus-wide unanswerability; cannot be reported as a verified corpus-unanswerable negative control. |
| **`AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION`** | Question rests on an ambiguous, unverified, or factually unsupported/synthetic external premise (e.g., unreported utility bills or synthetic 2025 CVE). | Must be explicitly disclosed and excluded from standard answerable effectiveness averages (confirm `evaluate_gold_labels_readonly.py` stratification rule before S5-D1). |
| **`QUESTION_REQUIRING_REVISION`** | Question is unexpectedly answerable in the corpus or malformed and must be revised or excluded. | Placed on `HOLD` for v2.1; cannot be scored as a negative control. |

---

## 4. Mandatory Human Verification Fields

Each completed worksheet must record (all currently blank):
- `human_answerability_classification`
- `external_factual_premise_assessment` (`VERIFIED_REAL_FACT | UNVERIFIED_OR_UNREPORTED | SYNTHETIC_OR_FALSE_PREMISE`)
- `corpus_scope_checked`
- `additional_corpus_queries_run_by_verifier`
- `checked_passage_ids`
- `verifier_id`, `provenance_class`, `verification_date_utc`, and `verification_rationale`
