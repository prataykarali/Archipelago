# S5-C2 Descriptive Agreement Report (Pre-Adjudication)

**Date:** 2026-11-19
**Evaluated Pool:** `s5b2_1_proposed_pooled_v2.1_pending_approval` (254 pairs)

> [!IMPORTANT]
> **Descriptive Agreement Only:** Because Reviewer B's submission carries AI-assisted proposed annotations (`254/254` items) without documented independent human re-grading, the statistics below represent **descriptive agreement between the submitted annotation sets**, NOT validated inter-human reliability.

## 1. Overall Agreement Metrics

- **Exact Raw Agreement:** **203 / 254 (79.92%)**
- **Disagreements Requiring Adjudication:** **51 / 254**
- **Cohen's Weighted Kappa (Quadratic):** **`0.7677`**
- **Cohen's Unweighted Kappa:** `0.5972`

## 2. Confusion Matrix (Rows = `REV_A`, Columns = `REV_B`)

| `REV_A` \ `REV_B` | Grade 0 | Grade 1 | Grade 2 | Row Total |
|---|---:|---:|---:|---:|
| **Grade 0** | 150 | 34 | 0 | 184 |
| **Grade 1** | 4 | 36 | 4 | 44 |
| **Grade 2** | 0 | 9 | 17 | 26 |
| **Col Total** | 154 | 79 | 21 | 254 |

## 3. Grade & Confidence Distributions

- **Reviewer A Grades:** `0`: 184, `1`: 44, `2`: 26 | Confidence: {'HIGH': 188, 'LOW': 10, 'MEDIUM': 56}
- **Reviewer B Grades:** `0`: 154, `1`: 79, `2`: 21 | Confidence: {'HIGH': 175, 'MEDIUM': 79}

## 4. Per-Query Agreement & Disagreement Breakdown

| Query ID | Total Pairs | Agree | Disagree | Agreement % |
|---|---:|---:|---:|---:|
| `Q-S5B2-01` | 13 | 9 | 4 | 69.2% |
| `Q-S5B2-02` | 22 | 15 | 7 | 68.2% |
| `Q-S5B2-03` | 25 | 25 | 0 | 100.0% |
| `Q-S5B2-04` | 31 | 22 | 9 | 71.0% |
| `Q-S5B2-05` | 29 | 19 | 10 | 65.5% |
| `Q-S5B2-06` | 31 | 26 | 5 | 83.9% |
| `Q-S5B2-07` | 28 | 20 | 8 | 71.4% |
| `Q-S5B2-08` | 27 | 27 | 0 | 100.0% |
| `Q-S5B2-10` | 25 | 17 | 8 | 68.0% |
| `Q-S5B2-11` | 23 | 23 | 0 | 100.0% |

## 5. Readiness Decision

**Decision:** `HOLD_FOR_DISAGREEMENT_ADJUDICATION_AND_REV_B_INDEPENDENCE_CHECK` — Do NOT compute final retrieval metrics or proceed to S5-D until all disagreements are human-adjudicated and Reviewer B's human confirmation is documented.
