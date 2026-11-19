# S5-v3.1 Multi-Domain Coverage Report

**Date:** 2026-11-19  
**Corpus Manifest:** [s5v31_corpus_manifest.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_corpus_manifest.json)

---

## 1. Domain Coverage Transformation (S5-v3 -> S5-v3.1)

S5-v3 (`818` eligible passages) covered only 4 ML/Math/NLP/Robotics domains and was `87.9%` concentrated in a single textbook (`mml-book.pdf`). S5-v3.1 (`1,958` passages) adds **all 4 previously missing core Computer Science systems domains** (`+1,140` passages) from verified Creative Commons sources:

| Domain | Source Doc ID | S5-v3 Eligible | S5-v3.1 Passages | Share of v3.1 | Page Refs | License |
|---|---|---:|---:|---:|---|---|
| Mathematics for Machine Learning | `local_oa_003` | 719 | **719** | 36.72% | Exact 1-based PDF pages | Free online PDF (local research only) |
| Computer Networks | `oa_net_001` | 0 | **600** | 30.64% | Exact 1-based PDF pages | `CC-BY-SA-3.0` |
| Distributed Systems | `oa_ds_001` | 0 | **220** | 11.24% | Section refs (`page=null`) | `CC-BY-SA-4.0` |
| Databases | `oa_db_001` | 0 | **208** | 10.62% | Section refs (`page=null`) | `CC-BY-4.0` (prose chapters only) |
| Operating Systems | `oa_os_001` | 0 | **112** | 5.72% | Section refs (`page=null`) | `CC-BY-4.0` |
| Robotics / Control | `local_oa_004` | 50 | **50** | 2.55% | Exact 1-based PDF pages | Preprint (local research only) |
| Machine Learning | `local_oa_001` | 26 | **26** | 1.33% | Logical page 1 + section heading | `CC-BY-SA-4.0` |
| Natural Language Processing / LLMs | `local_oa_002` | 23 | **23** | 1.17% | Exact 1-based PDF pages | `arXiv-perpetual-nonexclusive` |
| **Total** | **8 Sources** | **818** | **1,958** | **100.00%** | `1,418` paged / `540` section-only | All 8 verified |

---

## 2. Balance Assessment & Remaining Scope Limitations

1. **Systems vs ML/Math Balance Achieved:** Core CS Systems (Networks `600` + Distributed Systems `220` + Databases `208` + Operating Systems `112` = `1,140` passages, `58.22%`) and ML/Math/NLP/Robotics (`818` passages, `41.78%`) now form a genuinely multi-domain technical retrieval collection.
2. **Remaining Single-Document Skew Within Domains:** Each domain is currently represented by **1** primary source document (with `local_oa_003` at `36.7%` and `oa_net_001` at `30.6%` of total passages, while ML `26` and NLP `23` remain compact single-chapter/single-paper sources).
3. **Allowed Claims vs Disallowed Claims:**
   - **Supported (after human query verification & dual human relevance annotation):** Multi-domain technical CS + ML passage retrieval evaluation across 8 verified domains (`OS`, `Databases`, `Computer Networks`, `Distributed Systems`, `ML`, `Math for ML`, `NLP/LLMs`, `Robotics/Control`).
   - **Not Supported:** Broad multi-document intra-domain diversity claims within a single CS systems domain (each new CS domain has 1 canonical textbook/notes source), or unverified effectiveness claims prior to human annotation.
