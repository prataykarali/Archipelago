# S5-C3-P4 — Future A/C Validation & S5-D1 Compatibility Plan (Design Only)

**Stage:** S5-C3-P4 (Validation-Only Readiness Plan — **NO** gate modified, **NO** S5-D1 executed)  
**Date:** 2026-11-19  
**Status:** **`AWAITING_GENUINE_HUMAN_REVIEW`**

---

## 1. Preconditions Before Running A/C Comparison

A/C comparison MUST NOT execute until all four prerequisites below are verified on disk:

1. **Preserved Original `REV_A` Workbook Recovered & Hash-Verified:** `data/annotation_local/s5c2/originals/reviewer_a_s5b2_1_workbook.md` present with exact `SHA-256 == 70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c`.
2. **Signed `REV_A` Provenance Attestation Validated:** `data/annotation_local/s5c3/submissions/reviewer_a_provenance_attestation_signed.md` signed by a human, confirming `provenance_class == INDEPENDENT_HUMAN` and `assistance_declaration == NONE_INDEPENDENT_HUMAN` (or transparently flagging if not independent).
3. **Completed Independent `REV_C` Workbook Validated:** `data/annotation_local/s5c3/submissions/independent_reviewer_c_s5c3_workbook_COMPLETED.md` with `254/254` valid grades `{0, 1, 2}`, `0` duplicates, `0` ID/corpus/text mismatches, `100%` exact verbatim supporting quotations for grades `1` and `2`, blank quotations for grade `0`, and signed `provenance_class == INDEPENDENT_HUMAN`.
4. **Completed Human Negative-Control Verification Validated:** `data/annotation_local/s5c3/submissions/s5c3_negative_control_verification_worksheets_COMPLETED.md` with signed `INDEPENDENT_HUMAN` decisions for `Q-S5B2-03`, `Q-S5B2-08`, and `Q-S5B2-11` addressing the full 713-passage corpus.

---

## 2. Validation-Only A/C Comparison Procedure (Post-Submission)

Once preconditions 1–3 pass, run a **strictly read-only validation script** (to be authored in S5-C3-P5 after human submissions arrive; zero retrieval effectiveness metrics computed):

1. **Structural Alignment Check:** Confirm both `REV_A` and `REV_C` cover all `254` `(pair_id, query_id, passage_id)` tuples from frozen `retrieval_query_pool_blinded.json` (`SHA-256: 2d134546...`) and `s5a_eval_corpus_v1` (`713` eligible passages, `corpus_sha256: 6435bf44...`).
2. **Inter-Human Reliability Metrics (`REV_A` vs. `REV_C`):**
   - Raw exact agreement rate (`%`)
   - Unweighted Cohen's $\kappa$
   - Quadratic weighted Cohen's $\kappa$ (and $3 \times 3$ confusion matrix)
   - Per-query agreement breakdown (`Q-S5B2-01` .. `Q-S5B2-11`)
3. **Fresh A/C Disagreement Packet Generation:**
   - Extract **every** pair where `REV_A.grade != REV_C.grade` into a new private blank adjudication packet (`data/annotation_local/s5c3/s5c3_ac_disagreement_adjudication_packet.md`) containing canonical `okf_graph.db` passage text, `REV_A` and `REV_C` grades/quotes/notes, and blank human adjudicator fields.
   - Keep the historical 51-item `REV_A` vs. `REV_B` (`AI_ASSISTED_OR_GENERATED`) packet strictly separate and archived.
4. **Human A/C Adjudication Gate:** A designated human adjudicator resolves `100%` of `REV_A != REV_C` pairs with signed `ADJUDICATED_HUMAN` provenance, verbatim quotes (for grades `1`/`2`), and written rationales before assembling the final gold-label JSON.

---

## 3. Current S5-D0/D1 Evaluator Constraint & Proposed Versioned A/C Pathway

### Current Gate Behavior (Preserved Unchanged)
In [evaluate_gold_labels_readonly.py](file:///home/pratay-karali/Desktop/archipelago/research/s5-d0-experimental-analysis-prep/scripts/evaluate_gold_labels_readonly.py) (lines 59–65, 119–120):
- Expects `schema_version == "s5d0_adjudicated_gold_v1"`.
- Enforces **`gold_payload.get("reviewer_b_independence_confirmed") is True`**.
- **Scientific Integrity Constraint:** Because historical `REV_B` is permanently classified as `AI_ASSISTED_OR_GENERATED`, setting `reviewer_b_independence_confirmed = True` to force an A/C gold file through `v1` would be **scientifically dishonest and is strictly forbidden**.

### Proposed Separately Tested, Versioned A/C Pathway (Future S5-D1 Prep Only)
Do **not** alter the existing `s5d0_adjudicated_gold_v1` gate or weaken `test_s5d0_analysis_prep.py`. Instead, once validated human A/C gold labels exist, introduce a **new, separately versioned schema (`s5d1_adjudicated_gold_ac_v2`)** with dedicated unit tests:

1. **Explicit Dual-Human Stream Fields (Replacing `reviewer_b_independence_confirmed`):**
   - `primary_human_assessor_pair`: `["REV_A", "REV_C"]`
   - `reviewer_a_provenance_class`: `"INDEPENDENT_HUMAN"` (with attestation SHA-256 + workbook SHA-256)
   - `reviewer_c_provenance_class`: `"INDEPENDENT_HUMAN"` (with workbook SHA-256)
   - `historical_reviewer_b_excluded_from_gold`: `True`
   - `all_ac_disagreements_adjudicated`: `True` (with human adjudicator ID and adjudication packet SHA-256)
   - `negative_control_verifications`: all 3 queries (`Q-S5B2-03`, `Q-S5B2-08`, `Q-S5B2-11`) carrying `provenance_class == "INDEPENDENT_HUMAN"` and explicit stratification handling for any `AMBIGUOUS_OR_UNSUPPORTED_FACTUAL_QUESTION` or `QUESTION_REQUIRING_REVISION` outcome.
2. **Strict Separation of Tests:** Keep `s5d0_adjudicated_gold_v1` validator tests untouched (`reviewer_b_independence_confirmed=False` must still hard-fail `v1`), and add an independent test suite (`tests/unit/test_s5d1_ac_gold_validator.py`) verifying `s5d1_adjudicated_gold_ac_v2` rejects any `AI_ASSISTED_OR_GENERATED` or unattested stream.
3. **No Premature Execution:** Neither `evaluate_gold_labels_readonly.py` nor any `v2` evaluator is modified or executed now. S5-D1 remains strictly locked.
