# Archipelago — Source Redistribution & Historical Exposure Audit (S4-G3)

**Date:** 2026-11-17  
**Branch:** `research/s4-g3-extraction-repair`  
**Auditor:** Antigravity Evaluation & Integrity Engine  

---

## 1. Executive Summary & Legal Principles

Archipelago indexes academic literature across multiple computing domains. In building open science benchmarks (such as CIKM 2027 evaluation artifacts), **redistribution permissions must be explicitly separated from reading/indexing access**:

> [!WARNING]
> **Open Access ≠ Unrestricted Redistribution:**
> A paper accessible via arXiv or an open educational textbook (e.g., OSTEP) is NOT automatically licensed for arbitrary public re-hosting, verbatim packaging, or commercial derivative redistribution. Proprietary publisher works (Elsevier, Pearson, Springer) strictly forbid unauthorized redistribution of prose passages.

To ensure compliance:
1. **Public Package:** Publishes only *content-free metadata*: document IDs, chunk IDs, page numbers, character offsets, SHA-256 chunk fingerprints, and evidence SHA-256 hashes.
2. **Local Annotation Package:** Verbatim text excerpts are retained only in local, access-controlled research directories for authorized annotators and are never uploaded to unrestricted public endpoints.
3. **Historical Exposure Audit:** Identifies any prior repository commits that may contain copyrighted text snippets and provides a non-destructive remediation roadmap.

---

## 2. Document-by-Document Redistribution Permissions Audit

| Document Identifier | Title / Work | Publisher / Authors | Legal Rights & License | Permitted Internal Use | Permitted Public Redistribution |
|---|---|---|---|---|---|
| `archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf` | OSTEP Ch. 13 (Address Spaces) | Remzi & Andrea Arpaci-Dusseau | **CC BY-NC-ND 4.0** (Attribution-NonCommercial-NoDerivatives) | Full research indexing & local annotation | Metadata, offsets, hashes only. No modified text derivatives. |
| `archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf` | OSTEP Ch. 18 (Paging) | Remzi & Andrea Arpaci-Dusseau | **CC BY-NC-ND 4.0** (Attribution-NonCommercial-NoDerivatives) | Full research indexing & local annotation | Metadata, offsets, hashes only. |
| `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` | Attention Is All You Need | Vaswani et al. (arXiv:1706.03762) | **arXiv.org Non-exclusive License** | Full research indexing & local annotation | Short quotes for fair academic commentary; public package uses offsets & hashes. |
| `papers/Hu2021_LoRA.pdf` | LoRA: Low-Rank Adaptation | Hu et al. (arXiv:2106.09685) | **arXiv.org Non-exclusive License** | Full research indexing & local annotation | Short quotes for fair academic commentary; public package uses offsets & hashes. |
| `papers/Dettmers2023_QLoRA.pdf` | QLORA: Efficient Finetuning | Dettmers et al. (arXiv:2305.14314) | **arXiv.org / CC BY 4.0** | Full research indexing & local annotation | Permitted under CC BY with attribution; public package standardizes on offsets & hashes. |
| `papers/Bahdanau2014_Attention.pdf` | Neural Machine Translation | Bahdanau et al. (arXiv:1409.0473) | **arXiv.org Non-exclusive License** | Full research indexing & local annotation | Short quotes for academic audit; public package standardizes on offsets & hashes. |
| `papers/Willard2023_Outlines.pdf` | Efficient Guided Generation | Willard & Louf (arXiv:2307.09702) | **arXiv.org Non-exclusive License** | Full research indexing & local annotation | Short quotes for exploratory analysis; public package uses offsets & hashes. |
| `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf` | Real-time Network Security (Elsevier 2024) | Elsevier B.V. / Authors | **All Rights Reserved (Proprietary Copyright)** | Authorized research indexing under institutional access | **STRICTLY RESTRICTED.** No verbatim distribution. Public release must use offset pointers only. |
| `doc_computer_networks_6_e` | Computer Networks 6th Ed. | Pearson Education (Tanenbaum & Wetherall) | **All Rights Reserved (Proprietary Copyright)** | Local single-excerpt catalog record | **STRICTLY RESTRICTED.** No verbatim text distribution. |
| `doc_fundamentals_of_database_system_7e` | Fundamentals of Database Systems 7th Ed. | Pearson Education (Elmasri & Navathe) | **All Rights Reserved (Proprietary Copyright)** | Local single-excerpt catalog record | **STRICTLY RESTRICTED.** No verbatim text distribution. |
| `doc_compilers_principles_techniques_and_tools` | Compilers: Principles, Techniques, & Tools | Pearson / Addison-Wesley (Dragon Book) | **All Rights Reserved (Proprietary Copyright)** | Local single-excerpt catalog record | **STRICTLY RESTRICTED.** No verbatim text distribution. |
| `data_science_2019/Index_2019_Data-Science.pdf` | Data Science Index | Springer / Elsevier | **All Rights Reserved (Proprietary Copyright)** | Excluded from prose extraction | **STRICTLY RESTRICTED.** Index cross-product rejected. |

---

## 3. Historical Git Exposure Audit

A scan of the local Git tracking tree reveals:
1. **Large binary PDFs are NOT committed to Git:**
   - Full textbook PDFs and research papers in `papers/` and `archipelago-books-cs/` are stored on disk and loaded into Kùzu, but are not tracked in Git. Only small, 5-page integration test fixtures (`test_dpo_5pages.pdf`, `test_flashattention_5pages.pdf`, `test_moe_5pages.pdf`) exist in Git.
2. **Database is properly gitignored:**
   - `okf_graph.db` is explicitly ignored in `.gitignore:14:okf_graph.db`.
3. **Evaluation and Audit Artifacts:**
   - Previous research branches (`research/s4-g2-1-integrity-gate`, `research/s4-g2-2-corpus-locked-annotation`) committed CSV files (e.g., `source_verification_36_items.csv` and `annotation_candidates_verified.csv`) containing short verbatim evidence spans (100–300 characters) for verification audit purposes.
   - These short spans constitute fair use for internal scientific verification and reproducibility, but must not be published as an open redistribution dataset.

---

## 4. Remediation & Clean Publication Protocol

To prepare the Archipelago repository for public release (or submission to CIKM 2027 artifact evaluation):
1. **Never Rewrite Git History Without Explicit Authorization:**
   - Git history rewriting (`git filter-repo`, `BFG Repo-Cleaner`) destroys commit hashes, invalidates cryptographic audit trails, and breaks tracking branches. Do NOT run history rewrites during research phase.
2. **Dual-Package Standard:**
   - **Public Package (`research/s4-g3-extraction-repair/annotation_package/public/`):**
     Distribute only `candidate_metadata_index.csv`. Researchers recreate the exact evidence text locally by running an automated extractor over their own licensed/downloaded copies of the source PDFs using the published byte offsets and SHA-256 fingerprints.
   - **Local Annotation Package (`research/s4-g3-extraction-repair/annotation_package/blinded/`):**
     Maintained locally in access-controlled environments for human raters.
3. **If Future Public Scrubbing Is Required:**
   - An authorized maintainer can run `git filter-repo --path-glob '*.pdf' --invert-paths` prior to final open-source publication if third-party legal counsel requests complete removal of all test PDFs.
