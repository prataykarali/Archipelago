# Archipelago — S4-G4 Public Repository Exposure & Safe Remediation Audit

**Date:** November 17, 2026  
**Auditor:** Archipelago Scientific Integrity Gate (S4-G4)  
**Branch:** `research/s4-g4-validation-readiness`  
**Repository Visibility:** **PUBLIC** (GitHub)

---

## 1. Executive Summary & Exposure Statement

The Archipelago GitHub repository is public. During previous development phases (specifically S4-B, S4-D, S4-E, S4-G2, S4-G2.1, S4-G2.2, and S4-G3), annotation CSV files and Markdown workbooks containing verbatim textual passages from commercial textbooks and academic publications were committed and pushed into the git history.

Normal file deletion (`git rm`) removes files from the current working tree and subsequent commits, but **does not purge existing blobs or commit histories** from the public Git packfiles. Anyone cloning the repository or browsing historical commits can access previous blob revisions.

In S4-G4, we establish:
1. Complete identification of all historical commits, branches, and tracked files containing source text.
2. Exhaustive licensing audit of every source document (Pearson textbooks, Elsevier journal, OSTEP, arXiv preprints).
3. Complete replacement of tracked verbatim files with public metadata-only indices (`candidate_metadata_index.csv`) containing zero source text.
4. Strict isolation of annotator-facing passages in `.gitignore`-protected, access-controlled local storage (`data/annotation_local/`) hydrated on-demand via cryptographic hash verification from local database instances.
5. Automated validation rules in the test suite preventing future accidental commits of verbatim text.
6. A definitive historical remediation protocol (using `git-filter-repo` or BFG) ready for execution **only upon explicit authorization by the repository owner**.

---

## 2. Inventory of Tracked Annotation Artifacts Containing Source Text

| Commit SHA | Branch | Tracked File Path | Content Type | Exposure Risk |
| :--- | :--- | :--- | :--- | :--- |
| `8ff96f2` | `research/s4-g3-extraction-repair` | `research/s4-g3-extraction-repair/annotation_package/blinded/blinded_human_annotation_pool.csv` | Full verbatim passage text (`evidence_passage`) | High (Pearson & Elsevier text) |
| `8ff96f2` | `research/s4-g3-extraction-repair` | `research/s4-g3-extraction-repair/annotation_package/blinded/blinded_human_annotation_workbook.md` | Blockquoted verbatim passages | High (Pearson & Elsevier text) |
| `0f78955` | `research/s4-g2-2-corpus-locked-annotation` | `research/s4-g2-2-corpus-locked-annotation/annotation_candidates/annotation_candidates_verified.csv` | Verbatim text column (`evidence_span`) | High (Pearson, Elsevier, OSTEP) |
| `0f78955` | `research/s4-g2-2-corpus-locked-annotation` | `research/s4-g2-2-corpus-locked-annotation/annotation_candidates/rejected_candidates_log.csv` | Verbatim text column (`evidence_span`) | High (Pearson, Elsevier, OSTEP) |
| `2147ece` | `research/s4-g2-1-integrity-gate` | `research/s4-g2-1-integrity-gate/human_annotation_package/multidomain_human_annotation_pool_corrected.csv` | Verbatim text column (`evidence_passage`) | High (Pearson, OSTEP) |
| `2147ece` | `research/s4-g2-1-integrity-gate` | `research/s4-g2-1-integrity-gate/human_annotation_package/multidomain_human_annotation_pool_corrected.md` | Blockquoted verbatim passages | High (Pearson, OSTEP) |
| `abad203` | `research/s4-g2-multidomain-evaluation` | `research/s4-g2-multidomain-evaluation/human_annotation_package/multidomain_human_annotation_pool.csv` | Verbatim text column (`evidence_passage`) | High (Synthesized & real text) |
| `abad203` | `research/s4-g2-multidomain-evaluation` | `research/s4-g2-multidomain-evaluation/human_annotation_package/multidomain_human_annotation_pool.md` | Blockquoted passages | High |
| `e3af789` | `research/s4-d-human-audit` | `research/s4-b-annotation-integrity/human_audit_labels_24.csv` | Verbatim text excerpts | Medium (OSTEP, Vaswani) |
| `57744db` | `research/s4-e-graph-diagnosis` | `research/s4-b-annotation-integrity/human_audit_original.md` | Blockquoted text excerpts | Medium (OSTEP, Vaswani) |

---

## 3. Legal and Licensing Classification of Source Documents

Every document in the candidate pool was audited for its actual redistribution rights:

| Source Document Identifier | Domain | Publisher / Source | Copyright Holder | Legal Status | Redistribution Permission |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `doc_computer_networks_6_e` | Computer Networks | Pearson Education | Pearson Education, Inc. (Tanenbaum et al.) | Proprietary Commercial Textbook | **STRICTLY RESTRICTED**. No public redistribution permitted. |
| `doc_fundamentals_of_database_system_7e` | DBMS | Pearson Education | Pearson Education, Inc. (Elmasri & Navathe) | Proprietary Commercial Textbook | **STRICTLY RESTRICTED**. No public redistribution permitted. |
| `doc_compilers_principles_techniques_and_tools` | Compilers | Pearson / Addison-Wesley | Pearson Education, Inc. (Aho et al.) | Proprietary Commercial Textbook | **STRICTLY RESTRICTED**. No public redistribution permitted. |
| `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf` | Computer Networks | Elsevier Ltd. | Elsevier Ltd. (Computers & Security 2024) | Proprietary Journal Publication | **STRICTLY RESTRICTED**. Subscription/hybrid copyright; verbatim redistribution prohibited. |
| `archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf` | Operating Systems | Arpaci-Dusseau Books | R. Arpaci-Dusseau & A. Arpaci-Dusseau | All Rights Reserved | **RESTRICTED**. Freely readable online for individual use; redistribution prohibited. |
| `archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf` | Operating Systems | Arpaci-Dusseau Books | R. Arpaci-Dusseau & A. Arpaci-Dusseau | All Rights Reserved | **RESTRICTED**. Freely readable online for individual use; redistribution prohibited. |
| `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` | AI & ML | arXiv:1706.03762 | Authors / arXiv | Open Access Preprint | **UNKNOWN / NON-DISTRIBUTABLE**. arXiv non-exclusive license does not grant public mirror rights. |
| `papers/Hu2021_LoRA.pdf` | AI & ML | arXiv:2106.09685 | Authors / arXiv | Open Access Preprint | **UNKNOWN / NON-DISTRIBUTABLE**. Non-exclusive distribution license. |
| `papers/Dettmers2023_QLoRA.pdf` | AI & ML | arXiv:2305.14314 | Authors / arXiv | Open Access Preprint | **UNKNOWN / NON-DISTRIBUTABLE**. Check CC-BY vs arXiv license. |
| `papers/Bahdanau2014_Attention.pdf` | AI & ML | arXiv:1409.0473 | Authors / arXiv | Open Access Preprint | **UNKNOWN / NON-DISTRIBUTABLE**. Non-exclusive distribution license. |
| `papers/Willard2023_Outlines.pdf` | Automata Theory | arXiv:2307.09702 | Authors / arXiv | Open Access Preprint | **UNKNOWN / NON-DISTRIBUTABLE**. Non-exclusive distribution license. |

### Conclusion
**None of the 11 audited documents permit unrestricted public redistribution of verbatim text on GitHub.**  
The classification of `papers/Real-time network security...` as `OPEN_RESEARCH_ACCESS` in S4-G3 was an error caused by reading the candidate note field instead of the publisher copyright attribution. This has been corrected to `RESTRICTED_METADATA_ONLY`.

---

## 4. Remediation Architecture Implemented in S4-G4

### 4.1 Public Metadata-Only Index
Public tracking in the git repository is restricted strictly to cryptographic and structural pointers:
- File: `research/s4-g4-validation-readiness/annotation_package/public/candidate_metadata_index.csv`
- Columns: `blind_id, original_item_id, domain, partition, doc_id, chunk_id, page_number, concept_a, concept_b, evidence_offset_start_in_chunk, evidence_offset_end_in_chunk, evidence_len_chars, chunk_fingerprint_sha256_16, evidence_sha256, evidence_match_type, redistribution_status, license_basis`
- Zero verbatim text fields (`evidence_passage`, `evidence_span`) are present.

### 4.2 Genuinely Access-Controlled Local Storage
Annotator-facing workbooks and candidate pools containing verbatim passages reside strictly in local-only storage:
- Directory: `data/annotation_local/`
- Guarded by `.gitignore`:
  ```gitignore
  data/annotation_local/
  /data/annotation_local/
  research/s4-g4-validation-readiness/annotation_local/
  ```

### 4.3 On-Demand Local Hydration Tool
Researchers and annotators with access to the local database reconstruct their annotation pool locally without checking anything into git:
- Script: `research/s4-g4-validation-readiness/scripts/hydrate_local_annotation_pool.py`
- Protocol:
  1. Reads `candidate_metadata_index.csv`.
  2. Queries local `okf_graph.db` by `(doc_id, chunk_id)`.
  3. Slices the exact passage using `[offset_start:offset_end]`.
  4. Verifies `sha256(extracted_passage) == evidence_sha256`.
  5. Emits `data/annotation_local/blinded_human_annotation_pool.csv` and `blinded_human_annotation_workbook.md`.

---

## 5. Technical Explanation: Why `git rm` Does Not Eliminate Historical Exposure

Git is a content-addressable database of immutable commit objects and tree snapshots:
- When a file is removed via `git rm` and committed, Git creates a new commit whose tree object simply omits the entry.
- The previous commits (`8ff96f2`, `0f78955`, etc.) remain in the repository packfiles (`.git/objects/pack/`).
- Any user executing `git clone` downloads the entire DAG, including all historical commits and blobs.
- Any user can inspect exposed files via `git checkout 8ff96f2` or `git show 8ff96f2:path/to/file.csv`.
- Therefore, removing files from HEAD does not cure historical copyright exposure on a public remote.

---

## 6. Historical Remediation Protocol (Requires Repository Owner Approval)

To permanently purge copyrighted text from Git history, the repository history must be rewritten. **In accordance with strict safety directives, Archipelago agents DO NOT force-push, rewrite history, or change repository visibility autonomously.**

The repository owner may execute the following vetted procedure:

### Option A: Complete Historical Purge via `git-filter-repo` (Recommended)
```bash
# 1. Install git-filter-repo
pip install git-filter-repo

# 2. Make a fresh mirror clone of the repository
git clone --mirror git@github.com:your-org/Archipelago.git archipelago-cleanup
cd archipelago-cleanup

# 3. Purge all exposed annotation files across all branches and tags
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

# 4. Verify that blobs no longer exist
git log --all --full-history -- "**/blinded_human_annotation_pool.csv"

# 5. Force push to remote (Requires repository administrator privileges)
git remote add origin git@github.com:your-org/Archipelago.git
git push origin --force --all
git push origin --force --tags
```

### Option B: Transition Repository to Private
If rewriting git history would disrupt active collaborator worktrees, the repository owner can immediately transition the GitHub repository visibility to **PRIVATE** in repository settings, eliminating public exposure while preserving commit history.
