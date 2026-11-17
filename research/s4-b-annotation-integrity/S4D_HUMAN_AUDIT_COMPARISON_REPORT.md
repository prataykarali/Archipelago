# Archipelago — S4-D Human Audit vs. AI Annotations Comparison Report

**Date:** 2026-11-17  
**Reviewer:** Pratay Karali  
**Branch:** `research/s4-b-annotation-integrity`  
**Classification:** **Quality Control Audit** (Stratified Challenge Sample), *NOT* Independent Double-Human Gold Data  

---

## 1. Executive Summary & Core Metrics

A stratified sample of 24 candidate passages across 6 pilot queries was independently audited by a human domain reviewer without access to AI Reviewer scores. The human relevance scores (`0/1/2`) were matched against repository AI Reviewer A annotations and evaluated for agreement.

| Metric | Value | Percentage | Target / Reference | Interpretation |
| :--- | :---: | :---: | :---: | :--- |
| **Total Sample Size (N)** | **24** | 100.0% | 24 passages (4 per query) | Stratified challenge sample |
| **Exact Agreement Rate** | **15/24** | **62.50%** | Baseline | Exact 3-point score agreement |
| **Disagreement Rate** | **9/24** | **37.50%** | 0.0% ideal | 100% of disagreements are exactly 1 point off |
| **Binary Agreement Rate** | **21/24** | **87.50%** | >= 80.0% | Relevant (>= 1) vs Irrelevant (0) |
| **Unweighted Cohen's Kappa** | **0.4433** | — | >= 0.75 (CIKM target) | Moderate agreement (penalizes 1-off errors fully) |
| **Linear Weighted Kappa** | **0.6029** | — | — | Moderate-to-substantial agreement |
| **Quadratic Weighted Kappa** | **0.7477** | — | >= 0.75 | Substantial agreement (0.7477 ~ 0.75 threshold) |
| **Binary Cohen's Kappa** | **0.7500** | — | >= 0.75 | Substantial agreement on topical relevance |
| **AI Reviewer A Labels Present** | **24/24** | **100.0%** | 100.0% | Complete match across all candidate IDs |
| **AI Reviewer B Labels Present** | **0/24** | **0.0%** | Expected 100% | **MISSING**: Pending double-blind annotation |
| **Uncertain Human Judgments** | **5/24** | **20.83%** | Transparent flag | 5 items flagged uncertain: yes |

---

## 2. Status of Reviewer A and Reviewer B Annotations

1. **AI Reviewer A:**
   - **Source:** `artifacts/validation/local_only/s4b_reviewer_a_scored.json` (deterministic extraction from `s4a_human_annotation_worksheet.md`).
   - **Coverage:** **113/113 candidates populated in full pool; 24/24 matched in human audit (100% coverage).**
   - **Integrity Notice:** Reviewer A's worksheet had question category labels exposed in headers (`reviewer_a_preservation_manifest.json`), meaning Reviewer A was not category-blinded.

2. **AI Reviewer B:**
   - **Source Inspected:** `artifacts/validation/s4a_reviewer_b_template.json`, `artifacts/validation/local_only/s4b_reviewer_b_template.json`, `artifacts/validation/local_only/s4b_reviewer_b_worksheet.md`, `stage1_independent_template.json`.
   - **Audit Finding:** **0/113 annotations populated (0/24 matched in audit sample). All Reviewer B relevance fields are null or blank (`___`).**
   - **Integrity Compliance:** In strict compliance with scientific honesty requirements, **no Reviewer B data has been fabricated.** Reviewer B is recorded as `MISSING_PENDING_ANNOTATION`.

---

## 3. Confusion Matrix Analysis (Human vs. AI Reviewer A)

### Graded 3×3 Relevance Confusion Matrix

| Human \ AI Rev A | AI = 0 (Irrelevant) | AI = 1 (Partial Context) | AI = 2 (Direct Answer) | Total Human |
| :--- | :---: | :---: | :---: | :---: |
| **Human = 0** | **9** | **3** | **0** | **12** |
| **Human = 1** | **0** | **2** | **6** | **8** |
| **Human = 2** | **0** | **0** | **4** | **4** |
| **Total AI** | **9** | **5** | **10** | **24** |

### Key Structural Findings from Confusion Matrix:
1. **Monotonic Lenience Bias:** In **every single disagreement** (9/9, 100%), the AI assigned a higher score than the human by exactly $+1$ grade ($AI = Human + 1$). There are **zero** instances where Human > AI.
2. **Zero Extreme Mismatches:** There are **zero** 2-grade disagreements (no Human 0 vs AI 2, and no Human 2 vs AI 0).
3. **Perfect Direct Answer Precision (Human=2):** All 4 passages graded `2` by the human were also graded `2` by AI Reviewer A (100% recall for core direct answers). However, the AI over-allocated grade `2` to 6 passages that the human considered only partial context (`Human=1`).

### Binary Relevance (Irrelevant $0$ vs. Relevant $\ge 1$)

| Human \ AI Rev A | AI = 0 (Irrelevant) | AI $\ge$ 1 (Relevant) | Total |
| :--- | :---: | :---: | :---: |
| **Human = 0** | **9** | **3** | **12** |
| **Human $\ge$ 1** | **0** | **12** | **12** |
| **Total** | **9** | **15** | **24** |

- **Binary Precision:** $12 / (12 + 3) = 80.00\%$
- **Binary Recall:** $12 / 12 = 100.00\%$
- **Binary Specificity:** $9 / 12 = 75.00\%$
- **Binary Cohen's $\kappa$:** **0.7500**

---

## 4. Full Table of Disagreements (9 Items)

| Query ID | Candidate ID | Passage ID | Page / Section | Human | AI A | Diff | Human Reason | Uncertain? |
| :--- | :--- | :--- | :--- | :---: | :---: | :---: | :--- | :---: |
| `CIKM-PILOT-001` | `CAND-16` | `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_013` | p.5 (3.2.3 Applications of Attention in our Model) | **0** | **1** | `-1` | Explains how multi-head attention and decoder masking work inside the Transformer, not what sequence-modeling flaws motivated replacing recurrence | `no` |
| `CIKM-PILOT-001` | `CAND-03` | `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_031` | p.10 (N/A) | **1** | **2** | `-1` | Mentions in the conclusion that the Transformer trains faster than recurrent models and notes a future goal of making generation less sequential, giving only indirect context on recurrence's limits | `yes` |
| `CIKM-PILOT-001` | `CAND-17` | `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_002` | p.1 (Abstract) | **1** | **2** | `-1` | Notes in the abstract that dropping recurrence and convolutions makes the Transformer more parallelizable and faster to train, offering partial evidence without explaining the underlying sequence-modeling bottlenecks. | `no` |
| `CIKM-PILOT-005` | `CAND-06` | `papers/hu2021_lora.pdf::chunk_019` | p.7 (N/A) | **0** | **1** | `-1` | Covers where LoRA inserts rank decomposition matrices, how trainable parameters are counted, and GPT-2 benchmark results rather than the mathematical assumption behind the method. | `no` |
| `CIKM-PILOT-005` | `CAND-03` | `papers/hu2021_lora.pdf::chunk_012` | p.4 (N/A) | **1** | **2** | `-1` | States that LoRA does not require accumulated gradient updates to weight matrices to have full rank during adaptation, providing partial evidence without explicitly framing the intrinsic-rank hypothesis. | `yes` |
| `CIKM-PILOT-002` | `CAND-04` | `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_012` | p.5 (N/A) | **1** | **2** | `-1` | Focuses on multi-head projections but includes a footnote proving that dot products of unit-variance vectors have variance $d_k$, which supplies partial mathematical evidence without mentioning softmax gradients. | `no` |
| `CIKM-PILOT-002` | `CAND-08` | `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_010` | p.4 (N/A) | **0** | **1** | `-1` | Gives only the general definition of attention as a weighted sum of values and does not discuss scaling by $\sqrt{d_k}$ or softmax behavior. | `no` |
| `CIKM-PILOT-004` | `CAND-08` | `papers/bahdanau2014_attention.pdf::chunk_031` | p.12 (IEEE Transactions on, 45(11), 2673–2681.) | **1** | **2** | `-1` | Provides half of the comparison by detailing Bahdanau et al.'s single-layer MLP additive alignment formula between decoder and encoder states, without mentioning Vaswani et al.'s multi-head self-attention. | `no` |
| `CIKM-PILOT-004` | `CAND-16` | `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_013` | p.5 (3.2.3 Applications of Attention in our Model) | **1** | **2** | `-1` | Contrasts Transformer encoder and decoder self-attention with encoder-decoder cross-attention (citing Bahdanau et al. as [2]), offering partial comparative evidence while omitting multi-head projection and dot-product versus additive scoring differences. | `yes` |

### Analysis of Disagreement Drivers:
1. **Partial Context vs Core Answer (6 cases: H=1, AI=2):**
   - `CIKM-PILOT-001 CAND-03`: Transformer conclusion mentions training faster and making generation less sequential; human noted this provides indirect context on recurrence limits rather than explaining the foundational sequence-modeling bottlenecks.
   - `CIKM-PILOT-001 CAND-17`: Abstract notes dropping recurrence/convolutions improves parallelization; human marked partial evidence.
   - `CIKM-PILOT-005 CAND-03`: States LoRA does not require gradient update to have full rank; human noted it lacks explicit framing of the intrinsic-rank hypothesis.
   - `CIKM-PILOT-002 CAND-04`: Proves dot products have variance $d_k$ in a footnote; human graded partial evidence because softmax gradient saturation is not mentioned.
   - `CIKM-PILOT-004 CAND-08`: Gives Bahdanau's single-layer MLP alignment formula; human graded partial because Vaswani's multi-head attention is absent from the passage.
   - `CIKM-PILOT-004 CAND-16`: Contrasts self-attention with cross-attention; human graded partial because dot-product vs additive scoring mechanics are omitted.
2. **Irrelevant Noise vs Weak Background (3 cases: H=0, AI=1):**
   - `CIKM-PILOT-001 CAND-16`: Explains multi-head mechanics and masking, not why recurrence was replaced.
   - `CIKM-PILOT-005 CAND-06`: Describes parameter counting and GPT-2 benchmark results, not mathematical assumptions.
   - `CIKM-PILOT-002 CAND-08`: General definition of attention without scaling or softmax discussion.

---

## 5. Uncertain Judgments Analysis (5 Items)

The reviewer flagged 5 judgments as `uncertain: yes` (20.83% of sample).

| Query ID | Candidate ID | Passage ID | Human | AI A | Outcome | Reason |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| `CIKM-PILOT-001` | `CAND-03` | `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_031` | **1** | **2** | **Disagreement (AI +1)** | Mentions in the conclusion that the Transformer trains faster than recurrent models and notes a future goal of making generation less sequential, giving only indirect context on recurrence's limits |
| `CIKM-PILOT-005` | `CAND-03` | `papers/hu2021_lora.pdf::chunk_012` | **1** | **2** | **Disagreement (AI +1)** | States that LoRA does not require accumulated gradient updates to weight matrices to have full rank during adaptation, providing partial evidence without explicitly framing the intrinsic-rank hypothesis. |
| `CIKM-PILOT-004` | `CAND-07` | `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_031` | **1** | **1** | **Agreement** | Gives high-level context that the Transformer replaces recurrent encoder-decoder layers with multi-headed self-attention, but lacks the structural details needed to contrast it with additive alignment. |
| `CIKM-PILOT-004` | `CAND-16` | `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_013` | **1** | **2** | **Disagreement (AI +1)** | Contrasts Transformer encoder and decoder self-attention with encoder-decoder cross-attention (citing Bahdanau et al. as [2]), offering partial comparative evidence while omitting multi-head projection and dot-product versus additive scoring differences. |
| `CIKM-PILOT-023` | `CAND-15` | `papers/brown2020_gpt3.pdf::chunk_027` | **0** | **0** | **Agreement** | Describes few-shot evaluation and beam search parameters from the GPT-3 paper rather than DeepSeek-R1 or GRPO. |

### Stratification by Confidence:
- **Certain Judgments ($N = 19$):**
  - Exact Agreement: **13/19 (68.42%)**
  - Binary Agreement: **16/19 (84.21%)**
- **Uncertain Judgments ($N = 5$):**
  - Exact Agreement: **2/5 (40.00%)**
  - Disagreements: **3/5 (60.00%)**

---

## 6. Breakdown by Query

| Query ID | Focus Topic | Total | Exact Agree | Disagree | Uncertain | Exact Rate |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| `CIKM-PILOT-001` | Transformer vs RNN sequence modeling | 4 | 1 | 3 | 1 | **25.0%** |
| `CIKM-PILOT-005` | LoRA low-rank mathematical assumption | 4 | 2 | 2 | 1 | **50.0%** |
| `CIKM-PILOT-013` | PagedAttention virtual memory KV-cache | 4 | 4 | 0 | 0 | **100.0%** |
| `CIKM-PILOT-002` | Scaled dot-product sqrt(dk) division | 4 | 2 | 2 | 0 | **50.0%** |
| `CIKM-PILOT-004` | Multi-head vs additive alignment | 4 | 2 | 2 | 2 | **50.0%** |
| `CIKM-PILOT-023` | DeepSeek-R1 GRPO (Out-of-corpus negative) | 4 | 4 | 0 | 1 | **100.0%** |

### Key Observations by Topic:
- **Out-of-Corpus Negative Query (`CIKM-PILOT-023`):** **100% agreement (4/4).** Both human and AI accurately rejected all candidate passages as completely irrelevant (`0`), demonstrating robust true-negative rejection.
- **Systems & Systems Architecture (`CIKM-PILOT-013`):** **100% agreement (4/4).** Highly specific architectural descriptions in PagedAttention yielded zero ambiguity between human and AI.
- **Comparative & Theoretical Proof Queries (`CIKM-PILOT-001`, `002`, `004`, `005`):** Showed higher divergence (25% to 50% exact agreement) because passages contained partial components (e.g., mathematical lemmas without full context, or one side of a two-model comparison), which the AI aggressively promoted to `2` while the human graded `1`.

---

## 7. Methodological Classification & Caveats

1. **Quality Control Audit vs. Gold Standard:**
   - This 24-item audit is explicitly classified as an **internal quality-control and validation audit** of AI preannotations.
   - It is **NOT** independent double-human gold data, nor does it certify the remaining 89 un-audited passages in the 113-item pool.
   - Selection was stratified to intentionally sample borderline and diverse candidate tiers.
2. **Double-Blind Gold Requirements for CIKM 2027:**
   - Final publication benchmarks require an independent human Reviewer B completing the blinded worksheet (`stage1_independent_worksheet.md`) without exposure to Reviewer A or repository history.
   - Formal adjudication must then resolve disagreements between Reviewer A and Reviewer B into `ADJUDICATED_GOLD`.

---

## 8. Artifact Provenance Register

| Artifact | Path | SHA-256 | Description |
| :--- | :--- | :--- | :--- |
| Original Human Markdown | `research/s4-b-annotation-integrity/human_audit_original.md` | Preserved | Human reviewer's completed audit markdown |
| Original Human CSV | `research/s4-b-annotation-integrity/human_audit_labels_24.csv` | Preserved | Extracted 24 human judgments |
| Matched Comparison CSV | `research/s4-b-annotation-integrity/s4d_human_vs_ai_comparison.csv` | Generated | Matched 24-item comparison table |
| Reproducible Script | `research/s4-b-annotation-integrity/scripts/run_s4d_human_comparison.py` | Generated | Automated evaluation script |
| Full Report | `research/s4-b-annotation-integrity/S4D_HUMAN_AUDIT_COMPARISON_REPORT.md` | Generated | This comprehensive analysis report |
