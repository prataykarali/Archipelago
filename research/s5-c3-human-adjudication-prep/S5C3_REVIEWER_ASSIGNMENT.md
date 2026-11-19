# S5-C3 — Reviewer Assignment & Alternative Pilot Governance

**Stage:** S5-C3-P0 (Human Adjudication Preparation)  
**Date:** 2026-11-19  
**Status:** `HUMAN_REVIEW_REQUIRED`

---

## 1. Current Reviewer Stream Status (Preserved Unchanged)

| Stream | Preserved Original Path (Git-Ignored) | SHA-256 | Current Provenance Classification | Action Required |
|---|---|---|---|---|
| **Reviewer A (`REV_A`)** | `data/annotation_local/s5c2/originals/reviewer_a_s5b2_1_workbook.md` | `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c` | **Pending signed provenance attestation** (0/254 AI-assistance notes in S5-C2, but formal assistance declaration not yet recorded) | Obtain signed provenance attestation confirming `INDEPENDENT_HUMAN` (zero AI assistance) |
| **Reviewer B (`REV_B`)** | `data/annotation_local/s5c2/originals/reviewer_b_s5b2_1_workbook.md` | `ca3e6af86c72c20bf6dbd66d71f3c5c79ef7795de5d149d23c0b918304ae80f4` | **`AI_ASSISTED_OR_GENERATED`** (explicitly disclosed on 254/254 pairs) | Preserve unchanged as historical audit record; **never** relabel as `INDEPENDENT_HUMAN` |

---

## 2. Primary Path (Recommended): Dual Independent Human Assessors

1. **Confirm Reviewer A (`REV_A`):** Obtain a signed provenance declaration confirming `REV_A` graded all 254 pairs independently without AI assistance (`INDEPENDENT_HUMAN`), and verify `REV_A` did not inspect historical Git commits (`788976d`, `78d3f2f`).
2. **Recruit Independent Second Human Assessor (`REV_C`):**
   - Provide **only** the isolated private files `data/annotation_local/s5c3/independent_reviewer_c_s5c3_workbook.md` (and optional `independent_reviewer_c_s5c3_sheet.csv`) **outside Git repository access**.
   - `REV_C` must have **zero** access to `REV_A`, `REV_B`, S5-C2 audit reports, retrieval rankings, or repository history.
   - `REV_C` grades all **254 pairs** under `provenance_class = INDEPENDENT_HUMAN` and signs the provenance header.
3. **Compute Validated Inter-Human Agreement:** Once both `REV_A` (`INDEPENDENT_HUMAN`) and `REV_C` (`INDEPENDENT_HUMAN`) are locked, compute raw agreement, unweighted $\kappa$, and quadratic weighted $\kappa$ between `REV_A` and `REV_C`.
4. **Adjudicate Disagreements:** Adjudicate all `REV_A != REV_C` pairs using [S5C3_ADJUDICATION_PROTOCOL.md](file:///home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-c3-human-adjudication-prep/S5C3_ADJUDICATION_PROTOCOL.md). *(The existing 51-item `REV_A` vs. `REV_B` packet remains separately preserved for audit traceability.)*

---

## 3. Alternative Path: Transparent Single-Human-Assessor Pilot

If recruiting an independent second human assessor (`REV_C`) is infeasible within project constraints, the investigator may explicitly authorize a **Transparent Single-Human-Assessor Pilot** under the following strict rules:

1. **No Disguised Dual-Human Claim:** `REV_B` (`AI_ASSISTED_OR_GENERATED`) MUST **NOT** be relabeled as independent human review, and no inter-human reliability ($\kappa$) may be claimed in the manuscript.
2. **Provenance-Verified Single Human Stream:**
   - Either `REV_A` (after signing `INDEPENDENT_HUMAN` attestation) OR a fresh single human assessor grading the blinded 254-pair S5-C3 package (`independent_reviewer_c_s5c3_workbook.md`) serves as the primary human assessor.
   - If the human investigator additionally inspects the 51 `REV_A` vs. `REV_B` disagreements in `s5c3_disagreement_adjudication_packet_51.md` to audit potential oversights, every modified or confirmed item must be tagged `HUMAN_POST_AI_EXPOSURE` (for AI-exposed confirmation) or `ADJUDICATED_HUMAN` (with explicit note that `REV_B` was an AI-assisted audit signal, not an independent human rater).
3. **Mandatory Manuscript Disclosure:**
   - Report the benchmark explicitly as a **single-human-assessor pilot** (with optional disclosed AI-assisted secondary audit).
   - Add single-assessor reliability risk to `E03_THREATS_TO_VALIDITY.md` and `S5D0_LIMITATIONS_REGISTER.md` (single-assessor judgments cannot quantify inter-annotator variance).
   - Update `evaluate_gold_labels_readonly.py` only under explicit investigator authorization if a single-assessor schema variant is approved; do **not** falsify `reviewer_b_independence_confirmed = True`.

---

## 4. Operational Blinding & Access Control

- Distribute private workbooks via direct local transfer or access-controlled storage outside GitHub.
- Do **not** grant annotators access to `research/s5-b1-integrity-repair/`, `research/s5-b2-benchmark-correction/`, `research/s5-c2-annotation-audit/`, or `research/s5-d0-experimental-analysis-prep/` prior to locking their grades.
- Preserve SHA-256 hashes of every returned workbook immediately upon submission in Git-ignored `data/annotation_local/s5c3/submissions/`.
