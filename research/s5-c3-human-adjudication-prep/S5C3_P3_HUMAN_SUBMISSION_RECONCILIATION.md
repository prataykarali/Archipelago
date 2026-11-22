# S5-C3-P3 — Human Submission Recovery & Source-Reconciliation Audit

**Stage:** S5-C3-P3 (Read-Only Human Submission Reconciliation)  
**Date:** 2026-11-19  
**Audit Scope:** Entire local project tree (`/home/pratay-karali/Desktop/archipelago/`, including `Archipelago/`, `data/`, `docs/`, `research/`, `artifacts/`, Git stashes, and all `data/annotation_local/` subdirectories)  
**Audit Mode:** Strictly read-only — zero modifications to frozen corpora, rankings, original workbooks, or prior audit exports; S5-D1 remains strictly locked.  
**Overall Verdict:** **`HOLD`**

---

## 1. Executive Summary & Reconciliation Conclusion

An exhaustive filename, content (`S5B21-PAIR-001`, `NO_ANSWER_IN_FROZEN_CORPUS`, `adjudicated_grade`, `human_relevance_grade`), and timestamp scan across the entire local project confirmed:

1. **The prior S5-C3 export builder did NOT select the wrong files.** Every populated S5-C3 file currently present in the local project was inspected and faithfully represented in `data/annotation_local/s5c3/chatgpt_audit_export/`.
2. **Zero independently documented human S5-C3 submissions exist in the local project.**
   - All three populated S5-C3 files (`independent_reviewer_c_s5c3_workbook.md`, `s5c3_negative_control_verification_worksheets.md`, `s5c3_disagreement_adjudication_packet_51.md`) **explicitly declare themselves `AI_ASSISTED_OR_GENERATED`** and warn that they are **not** independent human assessments.
   - The `data/annotation_local/s5c3/submissions/` directory (specified in `S5C3_REVIEWER_ASSIGNMENT.md`) **does not exist**.
   - The external source file referenced inside Reviewer C's workbook (`Pasted text(20261119-030051).txt`) is **not present** anywhere in the local project.
   - The only completed submission without an AI-assistance disclosure is original **`REV_A`** (`reviewer_a_s5b2_1_workbook.md`, `254/254` pairs, SHA-256 `70049fa8...`), whose human provenance remains **`UNVERIFIED`** because no signed attestation, identity/pseudonym, completion date, AI-assistance declaration, or non-exposure declaration exists.
3. **No corrected private export was generated** because no unexported genuine human submissions exist in the local project. If human reviewers completed their assigned forms externally (e.g., via email, shared drive, or local `Downloads/` outside `/home/pratay-karali/Desktop/archipelago/`), those files have not yet been copied into the project workspace.

---

## 2. Complete Inventory of Populated Annotation / Submission Files in Local Project

All timestamps are from Linux `stat` (`Birth` / `Modify`, local offset `+0530`).

| # | Full Absolute Path | Creation (Birth) / Modification Timestamp (`+0530`) | SHA-256 Hash | Reviewer / Verifier Identity Recorded | Completed Judgments | Recorded AI-Assistance Disclosure | Independently Documented Human Provenance | Classification |
|---:|---|---|---|---|---:|---|---|---|
| 1 | `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5b2_1/reviewer_a_s5b2_1_workbook.md` | Birth: `2026-11-18 23:32:39` <br> Mod: `2026-11-19 00:25:35` | `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c` | `REV_A` *(template token only; no human name/pseudonym)* | `254 / 254` | None recorded (`0/254` AI notes; no signed zero-AI declaration) | **`UNVERIFIED`** *(no signed attestation, dates, or non-exposure declaration)* | Unverified Primary Submission (`REV_A`) |
| 2 | `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5c2/originals/reviewer_a_s5b2_1_workbook.md` | Birth: `2026-11-19 00:42:11` <br> Mod: `2026-11-19 00:25:35` | `70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c` | `REV_A` *(byte-identical preserved copy of #1)* | `254 / 254` | None recorded (identical to #1) | **`UNVERIFIED`** | Preserved Original Archive of #1 |
| 3 | `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5c2/originals/reviewer_b_s5b2_1_workbook.md` | Birth: `2026-11-19 00:42:11` <br> Mod: `2026-11-19 00:33:39` | `ca3e6af86c72c20bf6dbd66d71f3c5c79ef7795de5d149d23c0b918304ae80f4` | `REV_B` | `254 / 254` | **Explicit on `254/254` pairs:** *"AI-assisted proposed annotation; requires independent human confirmation."* | **`NO`** (`AI_ASSISTED_OR_GENERATED`) | Preserved AI-Assisted Draft (`REV_B` v1) |
| 4 | `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5b2_1/reviewer_b_s5b2_1_workbook.md` | Birth: `2026-11-19 00:56:43` <br> Mod: `2026-11-19 00:56:43` | `770f5c75ebfeab60208e81c8b4a47d11e8ae789e5aafc308852470a8d47985c9` | `REV_B` (`Reviewer Slot: REV_B`) | `254 / 254` *(differs from #3 on `85` grades & `254` notes)* | **Explicit in title & header:** *"Reviewer B (AI-assisted)"*; *"AI-assisted draft; not an independent human assessment; human verification pending"* | **`NO`** (`AI_ASSISTED_OR_GENERATED`) | Overwritten Working-Copy AI Draft (`REV_B` v2) |
| 5 | `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5c3/independent_reviewer_c_s5c3_workbook.md` | Birth: `2026-11-19 08:44:01` <br> Mod: `2026-11-19 08:44:01` | `8286404a15159663dae1dda25044e1640613561dfd833092040cb72a36778793` | `AI-generated annotation set; no independent human reviewer` *(dates: `NOT_ATTESTED`)* | `254 / 254` | **Explicit:** `provenance_class: AI_ASSISTED_OR_GENERATED`; `assistance_declaration: AI_ASSISTED`; transferred from `Pasted text(20261119-030051).txt` | **`NO`** (`AI_ASSISTED_OR_GENERATED`) | AI-Generated Derivative (Not Human `REV_C`) |
| 6 | `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5c3/s5c3_negative_control_verification_worksheets.md` | Birth: `2026-11-19 11:01:30` <br> Mod: `2026-11-19 11:01:30` | `7cef22e448df454375eac889b4f01ae1ec76017d93a779bc8704ed227e50c7fd` | `AI_JUDGE_B_STRICT_AUDIT` (`2026-11-19T05:22:00Z`) | `3 / 3` queries (`74 / 74` hydrated passages inspected) | **Explicit:** `AI_ASSISTED_OR_GENERATED` — populated from supplied `AI_JUDGE_B_STRICT_AUDIT` judgments; `INDEPENDENT_HUMAN_VERIFICATION_STILL_REQUIRED` | **`NO`** (`AI_ASSISTED_OR_GENERATED`) | AI-Assisted Negative-Control Draft |
| 7 | `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5c3/s5c3_disagreement_adjudication_packet_51.md` | Birth: `2026-11-19 11:06:21` <br> Mod: `2026-11-19 11:06:21` | `a6a52793058e69eac447e1198c4a74c63014d85fa2a655bc3ae9a39801dafecc` | `[PENDING_HUMAN_ASSIGNMENT]` / `[PENDING_HUMAN_SIGNOFF]` (`51/51`) | `51 / 51` AI-proposed resolutions (`0 / 51` signed human adjudications) | **Explicit:** `AI_ASSISTED_OR_GENERATED` / `AI_ASSISTED` — AI-generated proposed-resolution copy of historical A/B packet | **`NO`** (`AI_ASSISTED_OR_GENERATED`) | AI-Assisted Historical A/B Draft |

---

## 3. Blank Templates & Earlier-Stage Files Verified (0 Completed Judgments)

Every alternative CSV, JSON, and earlier-stage Markdown workbook in the local project was verified to contain **0 completed judgments**:

| Full Absolute Path | Modification Timestamp (`+0530`) | SHA-256 Hash | Completed Judgments | Status |
|---|---|---|---:|---|
| `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5c3/independent_reviewer_c_s5c3_sheet.csv` | `2026-11-19 08:05:10` | `ad45eb09606c5f3fce2ec3639ea81940b6bd630cb6ae575f5372ddcff9cb51cb` | `0 / 254` | Unmodified blank S5-C3 CSV template |
| `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5c3/s5c3_disagreement_adjudication_packet_51.json` | `2026-11-19 08:05:10` | `34302aab817eecc5c807434478e88502bc86972dc86c410428b3a8854cc79e4d` | `0 / 51` | Unmodified blank S5-C3 JSON template |
| `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5c2/S5C2_DISAGREEMENT_ADJUDICATION.md` | `2026-11-19 00:44:18` | `a65c9b39d62535282539645657d3e64ec793ee195792007bb262defb24c793c3` | `0 / 51` | Blank S5-C2 adjudication docket |
| `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5c2/S5C2_NEGATIVE_CONTROL_VERIFICATION_LOCAL.md` | `2026-11-19 00:44:18` | `17981b576b3ad93d824d32819e1b421971504b327a7de29751f0eb76398cd953` | `0 / 3` | Blank S5-C2 negative-control sheet |
| `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5b2/reviewer_a_s5b2_workbook.md` | `2026-11-18 23:23:59` | `ca012c469dfc350344a157e8d526336738e3ba610952eaed494ad28b50b18cfe` | `0` | Blank S5-B2 v2.0 template |
| `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/s5b2/reviewer_b_s5b2_workbook.md` | `2026-11-18 23:23:59` | `d782b673f19c5b3b7bb7bacd7b96b4e546ecb5d20daef6fc57b0aa4418a1d7b1` | `0` | Blank S5-B2 v2.0 template |
| `/home/pratay-karali/Desktop/archipelago/Archipelago/research/s5-b1-integrity-repair/annotation_local/reviewer_a_retrieval_workbook.md` | `2026-11-18 20:10:38` | `a807eebc0a758ec0f8a32817d14502dbf8c1886c3be393dedbc2fe49a6d1b2b7` | `0` | Blank S5-B1.1 template |
| `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/retrieval_eval/retrieval_relevance_reviewer_workbook.md` | `2026-11-18 19:04:40` | `1812dcdf2898c39b8b72c1ed964c4a98174ccae2c448ae199bb06eb83577d4c4` | `0` | Blank S5-A template |
| `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/blinded_human_annotation_workbook.md` | `2026-11-18 21:17:52` | `c2bb99ccb96c1ee2...` | `0` | Blank earlier pilot template |
| `/home/pratay-karali/Desktop/archipelago/Archipelago/data/annotation_local/concept_validity_audit_workbook.md` | `2026-11-18 18:55:09` | `a02b956a795b8bf2...` | `0` | Blank concept-validity template |

---

## 4. Comparison Against the Four Exported Audit Files (Did the Export Builder Select Wrong Files?)

| Exported Audit File (`data/annotation_local/s5c3/chatgpt_audit_export/`) | Source Selected by Export Builder | Alternative Populated Human Source Found Locally? | Selection Verdict |
|---|---|---|---|
| `REVIEWER_C_COMPLETED.md` | `data/annotation_local/s5c3/independent_reviewer_c_s5c3_workbook.md` (`8286404a...`) | **None.** Companion `independent_reviewer_c_s5c3_sheet.csv` is blank (`0/254`). No `submissions/` folder exists. | **Correct source selected** — source itself is explicitly `AI_ASSISTED_OR_GENERATED`. |
| `REVIEWER_A_PROVENANCE.md` | `MISSING` (referencing preserved `s5c2/originals/reviewer_a_s5b2_1_workbook.md`, `70049fa8...`) | **None.** Neither `s5c3/`, `s5c2/`, nor `s5b2_1/` contains a signed Reviewer A provenance declaration. | **Correctly reported `MISSING`** — `REV_A` provenance is `UNVERIFIED`. |
| `NEGATIVE_CONTROL_VERIFICATION.md` | `data/annotation_local/s5c3/s5c3_negative_control_verification_worksheets.md` (`7cef22e4...`) | **None.** Earlier `s5c2/S5C2_NEGATIVE_CONTROL_VERIFICATION_LOCAL.md` is blank (`0/3`). | **Correct source selected** — source itself is explicitly `AI_ASSISTED_OR_GENERATED` (`AI_JUDGE_B_STRICT_AUDIT`). |
| `HUMAN_ADJUDICATION_FINAL.md` | `MISSING` for A/C human adjudication (with historical 51-item A/B AI draft `a6a52793...` kept strictly separate) | **None.** No A/C adjudication file exists; `s5c3_disagreement_adjudication_packet_51.json` and `s5c2/S5C2_DISAGREEMENT_ADJUDICATION.md` are both blank (`0/51`). | **Correctly reported `MISSING`** — `0/16` A/C and `0/51` A/B human adjudications exist. |

**Discrepancy Noted Outside S5-C3 Export Scope:** `data/annotation_local/s5b2_1/reviewer_b_s5b2_1_workbook.md` (`770f5c75...`, modified `2026-11-19 00:56:43 +0530`) was overwritten after the S5-C2 archive copy `data/annotation_local/s5c2/originals/reviewer_b_s5b2_1_workbook.md` (`ca3e6af8...`, modified `2026-11-19 00:33:39 +0530`) and differs on `85` grades and `254` notes. Both versions explicitly declare themselves AI-assisted drafts (`AI_ASSISTED_OR_GENERATED`), and the S5-C2 archive copy remains byte-identically preserved at `ca3e6af8...`.

---

## 5. Missing Reviewer Attestations & Unresolved Human Disagreements

### A. Missing / Unverified Reviewer Provenance Attestations
1. **Reviewer A (`REV_A`):** `254/254` judgments exist (`70049fa8...`), but human provenance is **`UNVERIFIED`** — missing signed identity/pseudonym, original-work declaration, zero-AI-assistance declaration, completion/attestation dates, and non-exposure declaration (`788976d`, `78d3f2f`).
2. **Independent Reviewer C (`REV_C`):** **`MISSING`** — no genuine independent human submission exists in the local project; the file on disk is an explicitly declared `AI_ASSISTED_OR_GENERATED` derivative.
3. **Human Negative-Control Verifier (`Q-S5B2-03`, `Q-S5B2-08`, `Q-S5B2-11`):** **`MISSING`** — the file on disk is populated by `AI_JUDGE_B_STRICT_AUDIT` (`AI_ASSISTED_OR_GENERATED`).
4. **Human Disagreement Adjudicator:** **`MISSING`** — no signed human adjudicator identity, rationale, or decision date exists for any disagreement.

### B. Unresolved Disagreements
- **`REV_A` vs. populated `REV_C` (`AI_ASSISTED_OR_GENERATED`):** **`16`** disagreements (`0 / 16` human-adjudicated; `5` are outside the historical 51-item A/B packet: `S5B21-PAIR-095`, `S5B21-PAIR-132`, `S5B21-PAIR-173`, `S5B21-PAIR-216`, `S5B21-PAIR-228`).
- **Historical `REV_A` vs. preserved `REV_B` (`AI_ASSISTED_OR_GENERATED`):** **`51`** disagreements (`0 / 51` signed human adjudications; `51 / 51` AI-proposed drafts with `[PENDING_HUMAN_SIGNOFF]`).

---

## 6. Frozen Artifact Preservation Check & Verdict

- **Frozen Corpus (`s5a_eval_corpus_v1`, 713 passages):** Preserved (`6435bf449702edf826d69dc8e1ed0525ee611e0c7504d43d2023c32cef8bdba7`).
- **Immutable Pool (`retrieval_query_pool_blinded.json`, 254 pairs):** Preserved (`2d13454655dda965304ac4aabddbeef5e39b77bc6927393bebfdaa94235fb037`).
- **Preserved Originals:** `REV_A` (`70049fa849985cfb38aadef2dd499dbf8e665f55f5796a122302d501f17fa09c`) and `REV_B` (`ca3e6af86c72c20bf6dbd66d71f3c5c79ef7795de5d149d23c0b918304ae80f4`) remain untouched and byte-identical.
- **S5-D1 Execution Status:** **NOT EXECUTED (STRICTLY LOCKED).**

### Final Reconciliation Verdict: **`HOLD`**

No unexported genuine human submissions exist anywhere in `/home/pratay-karali/Desktop/archipelago/`. To proceed, the investigator must place the actual human-completed reviewer files (and signed provenance attestations) into Git-ignored `data/annotation_local/s5c3/submissions/` (preserving original filenames and timestamps) before re-running export and reconciliation.
