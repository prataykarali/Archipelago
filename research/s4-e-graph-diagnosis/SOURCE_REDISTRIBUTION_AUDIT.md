# Archipelago — S4-E Phase 1: Source Redistribution & Scholarly Passage Audit

**Branch:** `research/s4-e-graph-diagnosis`  
**Date:** 2026-11-17  
**Auditor:** Pratay Karali  
**Objective:** Audit newly tracked research annotation files for copyrighted scholarly text, ensure complete local provenance preservation, and provide repository-safe tracked artifacts without unauthorized Git history rewriting.

---

## 1. Audit Scope & Inspection Findings

We conducted an exhaustive text volume and copyright audit across all files introduced in the S4-D milestone (commit `e3af789` on `research/s4-b-annotation-integrity`):

| File Inspected | Tracked Status | Bulk Passage Text Detected? | Passage Words / Characters | Description |
| :--- | :---: | :---: | :---: | :--- |
| `research/s4-b-annotation-integrity/human_audit_original.md` | **Tracked** | **YES (EXPOSURE)** | **4,705 words / 28,703 chars** | 24 full verbatim blockquoted passages from published papers |
| `research/s4-b-annotation-integrity/human_audit_labels_24.csv` | Tracked | NO | 0 bulk text (metadata only) | Structured CSV: question ID, candidate ID, score, 1-sentence reason |
| `research/s4-b-annotation-integrity/s4d_human_vs_ai_comparison.csv` | Tracked | NO | 0 bulk text (metadata only) | Matched comparison table: candidate ID, passage ID, AI vs human scores |
| `research/s4-b-annotation-integrity/S4D_HUMAN_AUDIT_COMPARISON_REPORT.md` | Tracked | NO | 0 bulk text (report tables) | Markdown report with aggregated metrics, confusion matrix, and 1-sentence reasons |
| `research/s4-b-annotation-integrity/scripts/run_s4d_human_comparison.py` | Tracked | NO | 0 bulk text (code) | Python script for metric computation |
| `tests/unit/test_s4d_human_audit_comparison.py` | Tracked | NO | 0 bulk text (tests) | Pytest suite |

### Nature of Identified Passage Text:
The 24 passages in `human_audit_original.md` constitute verbatim, multi-paragraph excerpts from copyrighted scholarly literature:
- Vaswani et al. (2017) *Attention Is All You Need* (Sections 1, 3.1, 3.2.1, 3.2.3, 3.3, conclusion)
- Hu et al. (2021) *LoRA: Low-Rank Adaptation of Large Language Models* (Sections 4.1, 4.2, 5.1, subspace similarity)
- Kwon et al. (2023) *vLLM / PagedAttention* (Section 4, KV-cache memory manager)
- Bahdanau et al. (2014) *Neural Machine Translation by Jointly Learning to Align and Translate* (Appendix A)
- Brown et al. (2020) *Language Models are Few-Shot Learners (GPT-3)*
- Dettmers et al. (2023) *QLoRA: Efficient Finetuning of Quantized LLMs*
- Ouyang et al. (2022) *Training language models to follow instructions with human feedback (InstructGPT)*

Under Archipelago repository policy (`.gitignore`), bulk passage text exports (`s3_retrieval_candidates_export.*`) and candidate worksheets (`artifacts/validation/local_only/s4a_human_annotation_worksheet.md`) are designated `local_only` to avoid third-party text redistribution. The inclusion of full 200–500 word verbatim passage quotes in `human_audit_original.md` violated this redistribution boundary.

---

## 2. Local Provenance Preservation (Immutability Guarantee)

Before modifying the tracked repository file, the complete original audit Markdown was copied to the gitignored local storage area:
- **Local Path:** `artifacts/validation/local_only/human_audit_original_full.md`
- **SHA-256 Checksum:** `655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051`
- **File Size:** 40,532 bytes (24 verbatim passages intact)
- **Status:** **Preserved immutably on local disk for scientific audit verification.**

---

## 3. Repository-Safe Remediation Completed

A clean, repository-safe version of `research/s4-b-annotation-integrity/human_audit_original.md` was prepared and validated:
1. **Human Judgments & Metadata 100% Preserved:**
   - All 24 query IDs, questions, candidate numbers, candidate IDs (`CAND-XX`), page labels, and section titles remain untouched.
   - All 24 human relevance scores (`0 / 1 / 2`) and 1-sentence reasons are preserved character-for-character.
   - All 5 uncertainty flags (`Uncertain: yes`) and query-level direct answer checks remain intact.
2. **Bulk Text Replaced with Canonical Provenance Pointers:**
   - The multi-paragraph blockquotes (28,703 chars) were replaced with canonical citations:
     ```markdown
     > [Verbatim passage text omitted for repository copyright compliance. Corpus Passage ID: `papers/vaswani2017_attention_is_all_you_need.pdf::chunk_013` (Page 5). Full original text preserved locally in `artifacts/validation/local_only/human_audit_original_full.md` (SHA-256: 655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051).]
     ```
3. **Verification of Test Invariants:**
   - Pytest suite `tests/unit/test_s4d_human_audit_comparison.py` was executed against the sanitized file: **9/9 PASSED**.
   - Extraction script `run_s4d_human_comparison.py` was executed: all metrics reproduced identically.

---

## 4. Historical Exposure & Git Policy Compliance

- **Historical Exposure:** Commit `e3af789` containing the verbatim quotes was pushed to remote branch `origin/research/s4-b-annotation-integrity`.
- **Policy Compliance:** In strict adherence to Archipelago research policy (*"Do not rewrite Git history or force-push without authorization"*), **no history rewriting or force-push (`git push --force`) has been performed.**
- **Remediation Path:** The repository-safe replacement is committed on the dedicated branch `research/s4-e-graph-diagnosis`. If complete historical scrubbing is later authorized by the repository owner, a standard BFG Repo-Cleaner or git-filter-repo procedure can be applied with institutional sign-off.
