# Archipelago — S5-A Source-Text Exposure Status & Inventory Report

**Date:** November 18, 2026  
**Auditor:** Archipelago Retrieval Integrity Gate (S5-A)  
**Branch:** `research/s5-a-retrieval-integrity`  
**Repository Visibility:** **PUBLIC** (GitHub)

---

## 1. Executive Summary & Exposure Statement

In accordance with Phase S5-A instructions, this report audits all source-text exposure across the Archipelago repository, distinguishing between:
1. Historical commits that entered Git history in prior research phases (S4-B through S4-G3).
2. The active working tree on `research/s5-a-retrieval-integrity`.
3. Sanitization actions taken on this branch to eliminate unnecessary tracked source-text copies.
4. Genuinely access-controlled local-only approved materials (`data/annotation_local/`).

As required: **Repository visibility has NOT been changed, and Git history has NOT been rewritten autonomously without repository owner authorization.**

---

## 2. Complete Inventory: Current Working Tree vs. Historical Exposure

| Artifact Path | Current Tree Status (S5-A) | Historical Git Commits | Source Document Licensing | Exposure Classification | Remediation Implemented in S5-A |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `research/s4-g4-validation-readiness/concept_audit/concept_validity_audit_pool_public.csv` | **SANITIZED** (Metadata-Only) | `d20c16d` | Mixed (Pearson, Elsevier, OSTEP, arXiv) | **Resolved in S5-A** | Replaced `context_snippet` with `context_offset_start`, `context_offset_end`, and `context_sha256`. Zero verbatim text remains in the public file. Full snippets preserved in local-only `data/annotation_local/`. |
| `research/s4-g3-extraction-repair/annotation_package/blinded/blinded_human_annotation_pool.csv` | **REMOVED FROM TRACKING** (`git rm`) | `8ff96f2`, `d20c16d` | Restricted (Pearson, Elsevier, OSTEP) | **Resolved in S5-A Working Tree**; Packfile history remains until owner rewrite | Untracked on branch `research/s5-a-retrieval-integrity`. Preserved in approved local storage `data/annotation_local/`. Test suite redirected to local target. |
| `research/s4-g3-extraction-repair/annotation_package/blinded/blinded_human_annotation_workbook.md` | **REMOVED FROM TRACKING** (`git rm`) | `8ff96f2`, `d20c16d` | Restricted (Pearson, Elsevier, OSTEP) | **Resolved in S5-A Working Tree**; Packfile history remains until owner rewrite | Untracked on branch `research/s5-a-retrieval-integrity`. Preserved in local-only `data/annotation_local/`. |
| `research/s4-g4-validation-readiness/annotation_package/public/candidate_metadata_index.csv` | **CLEAN** (Metadata-Only) | `d20c16d` | Pointers only (Pearson, Elsevier, OSTEP, arXiv) | **Compliant** | Contains zero verbatim text; contains exact offsets, byte lengths, and SHA-256 digests. |
| `research/s4-g2-2-corpus-locked-annotation/annotation_candidates/annotation_candidates_verified.csv` | Historical Milestone Artifact | `0f78955` | Restricted (Pearson, Elsevier, OSTEP) | Historical Exposure (Required by frozen regression test `test_s4g2_2_corpus_locked_annotation.py`) | Retained in historical folder until repository owner executes `git filter-repo` historical purge. |
| `research/s4-g2-1-integrity-gate/human_annotation_package/multidomain_human_annotation_pool_corrected.csv` | Historical Milestone Artifact | `2147ece` | Restricted (Pearson, OSTEP) | Historical Exposure (Required by frozen regression test `test_s4g2_1_integrity_gate.py`) | Retained in historical folder until owner executes history rewrite. |
| `research/s4-g2-multidomain-evaluation/human_annotation_package/multidomain_human_annotation_pool.csv` | Historical Milestone Artifact | `abad203` | Restricted / Synthetic | Historical Exposure (Required by frozen regression test `test_s4g2_multidomain_evaluation.py`) | Retained in historical folder until owner executes history rewrite. |
| `research/s4-b-annotation-integrity/human_audit_labels_24.csv` | Historical Milestone Artifact | `e3af789` | Restricted (OSTEP, Vaswani) | Historical Exposure (Required by frozen regression test `test_s4d_human_audit_comparison.py`) | Retained in historical folder until owner executes history rewrite. |

---

## 3. Approved Access-Controlled Local Storage

All human annotation workbooks and candidate pools containing verbatim text excerpts now reside exclusively in:
- **Directory:** `data/annotation_local/`
- **Protected by `.gitignore`:**
  ```gitignore
  data/annotation_local/
  /data/annotation_local/
  research/s4-g4-validation-readiness/annotation_local/
  research/s5-a-retrieval-integrity/annotation_local/
  ```
- **Local Artifacts Present:**
  - `data/annotation_local/blinded_human_annotation_pool.csv` (Hydrated 24-item relation pool)
  - `data/annotation_local/blinded_human_annotation_workbook.md` (Hydrated markdown guide)
  - `data/annotation_local/admin_selection_manifest.json` (Full cryptographic linkage)
  - `data/annotation_local/concept_validity_audit_pool.csv` (Hydrated 54-item concept pool with snippets)
  - `data/annotation_local/concept_validity_audit_workbook.md` (Hydrated concept guide)

---

## 4. Remaining Historical Git Exposure & Recommended Action

Because Git is an immutable directed acyclic graph of snapshots, executing `git rm` removes files from the current commit tree, but historical packfiles still contain the commits `8ff96f2`, `0f78955`, `2147ece`, `abad203`, and `e3af789`.

### Recommendation for Repository Owner
When ready to purge historical commits across all branches, the repository administrator should run:
```bash
git filter-repo --invert-paths \
  --path research/s4-g3-extraction-repair/annotation_package/blinded/blinded_human_annotation_pool.csv \
  --path research/s4-g3-extraction-repair/annotation_package/blinded/blinded_human_annotation_workbook.md \
  --path research/s4-g2-2-corpus-locked-annotation/annotation_candidates/annotation_candidates_verified.csv \
  --path research/s4-g2-2-corpus-locked-annotation/annotation_candidates/rejected_candidates_log.csv \
  --path research/s4-g2-1-integrity-gate/human_annotation_package/multidomain_human_annotation_pool_corrected.csv \
  --path research/s4-g2-1-integrity-gate/human_annotation_package/multidomain_human_annotation_pool_corrected.md \
  --path research/s4-g2-multidomain-evaluation/human_annotation_package/multidomain_human_annotation_pool.csv \
  --path research/s4-g2-multidomain-evaluation/human_annotation_package/multidomain_human_annotation_pool.md \
  --path research/s4-b-annotation-integrity/human_audit_labels_24.csv \
  --path research/s4-b-annotation-integrity/human_audit_original.md
```
Alternatively, transitioning repository visibility to **PRIVATE** provides immediate legal protection without requiring historical Git DAG rewriting.
