# Domain Eligibility and Evaluation Split Audit

**Branch:** `research/s4-g2-2-corpus-locked-annotation`  
**Date:** 2026-11-17  
**Purpose:** Classify each domain by its corpus coverage and evaluation split integrity before annotation candidate selection.

---

## Domain Eligibility Matrix

| Domain | Eligibility | Split Type | Docs in DB | Chunks | Notes |
|--------|------------|-----------|-----------|--------|-------|
| Operating Systems | **ELIGIBLE** | DOCUMENT_DISJOINT | 3 (OSTEP) | 10 | Dev: `06_Address_Spaces.pdf`; Eval: `07_...`, `08_Paging.pdf` |
| AI & Machine Learning | **ELIGIBLE** | DOCUMENT_DISJOINT | 7+ research papers | 150+ | Dev: Vaswani2017, Hu2021; Eval: Dettmers2023, Bahdanau2014; Held-out: Devlin2018 |
| Computer Networks | **ELIGIBLE** | DOCUMENT_DISJOINT | 2 | 59 | Dev: Tanenbaum 6e (2 chunks); Eval: network security paper (57 chunks) |
| Automata Theory & Computation | EXPLORATORY | WITHIN_DOCUMENT_CHUNK_SPLIT | 1 | 20 | Willard2023 is LLM decoding paper, NOT classical automata. Chunk split only. |
| Database Management Systems | EXPLORATORY | DOCUMENT_DISJOINT | 2 | 2 | Only 2 prose chunks total — too sparse for multi-item evaluation |
| Compilers & Programming Languages | EXPLORATORY | SINGLE_CHUNK_ONLY | 1 | 1 | Dragon Book p192 — 1 chunk only |
| Probability & Statistics | **EXCLUDED** | N/A | 3 | 3 | Pattern recognition appendix (1–2 chunks); Data Science 2019 is a book index |
| Data Structures & Algorithms | **EXCLUDED** | N/A | 0 | 0 | No dedicated DSA documents with indexed prose |
| Information Security | **EXCLUDED** | N/A | — | — | Covered under Networks (D-MAGIC paper) |
| Software Engineering | **EXCLUDED** | N/A | 0 | 0 | No indexed documents |
| Computer Organization & Architecture | **EXCLUDED** | N/A | 1 | 1 | Catalog-only entry — no body prose |
| Mathematics for Computing | **EXCLUDED** | N/A | 1 | 1 | Isolated appendix chunk only |

---

## Excluded Document Types

| Document | Reason |
|----------|--------|
| `data_science_2019/Index_2019_Data-Science.pdf` | BOOK_INDEX — keyword cross-product, no prose |
| `predictive_analytics_and_data_mining_2015/Index_2015_Predictive-Analytics-and-Data-Mining.pdf` | BOOK_INDEX |
| `knowledge_representation_and_reasoning_2004/Index_2004_Knowledge-Representation-and-Reasoning.pdf` | BOOK_INDEX |
| `pattern_recognition_2009/Appendix-A.pdf` | Textbook appendix — too sparse (1 chunk) |
| `data/catalogs/*` | Catalog holdings only — not full text |
| `upload_*` documents | Unknown provenance — excluded |

---

## Development / Evaluation Partitions for Annotation Pool

| Domain | Development Docs | Evaluation Docs |
|--------|-----------------|----------------|
| OS | `06_Address_Spaces.pdf` | `08_Paging.pdf` |
| AIML | `Vaswani2017_Attention_Is_All_You_Need.pdf`, `Hu2021_LoRA.pdf` | `Dettmers2023_QLoRA.pdf`, `Bahdanau2014_Attention.pdf` |
| NETS | `doc_computer_networks_6_e` (Tanenbaum) | `Real-time network security...pdf` |
| TOC | `Willard2023_Outlines.pdf` chunks 0–9 | `Willard2023_Outlines.pdf` chunks 10–19 (exploratory only, within-document) |

> [!WARNING]
> TOC domain is WITHIN_DOCUMENT_CHUNK_SPLIT. Concepts from development chunks can directly
> inform extraction on evaluation chunks of the same document. Treat TOC results as
> exploratory only and exclude from held-out evaluation denominators.

---

## Annotation Candidate Pool: Final Distribution

| Domain | Items | Eligibility | Partition | Match Type |
|--------|-------|------------|-----------|-----------|
| OS | 5 | ELIGIBLE | 2 dev + 3 eval | All EXACT |
| AIML | 11 | ELIGIBLE | 7 dev + 4 eval | All EXACT |
| NETS | 3 | ELIGIBLE | eval | All EXACT |
| NETS_DEV | 1 | ELIGIBLE | dev | EXACT |
| TOC | 2 | EXPLORATORY | exploratory | All EXACT |
| DBMS | 1 | EXPLORATORY | exploratory | EXACT |
| COMPILERS | 1 | EXPLORATORY | exploratory | EXACT |
| **TOTAL** | **24** | | | **24/24 EXACT** |

---

## Scientific Notes

1. **No artificial 6-domain quota imposed.** The pool reflects actual corpus coverage. STAT, DSA, SE, COARCH, MATH are excluded because no eligible prose documents exist, not because of a design decision.

2. **Candidate categories are annotation task categories, not verified labels.** `POSSIBLE_RELATION`, `AMBIGUOUS`, and `LIKELY_UNRELATED` tell annotators what to look for — they do not assert semantic correctness.

3. **All 24 items passed the hardened provenance validator (Phase A).** Every item has: an existing document ID, an existing chunk ID linked to that document, a verbatim evidence span (EXACT match), a correct page number.

4. **Human labels are not generated.** `label_category = CANDIDATE_UNLABELED` and `human_relation_label = ""` for all items.
