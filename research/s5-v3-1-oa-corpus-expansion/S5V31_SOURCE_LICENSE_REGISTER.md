# S5-v3.1 Source & License Register (Stage A)

**Date:** 2026-11-19  
**Branch:** `research/s5-v3-1-oa-corpus-expansion-canonical`  
**Machine-Readable Manifest:** [s5v31_source_license_manifest.json](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/manifests/s5v31_source_license_manifest.json) (`SHA-256: a2242b13c2f857dcb16cf0ff0670b5664ecd7e8a4336bbfe80e3ab79979a336b`)  
**Private Raw Storage (Git-Ignored):** `data/annotation_local/s5v3_1/raw_sources/` (`.gitignore` line 141)

---

## 1. Newly Retrieved Open-Licensed CS Sources (4 / 4 Verified)

| Doc ID | Domain | Title & Authors | Publisher & Version / Commit | License & Exceptions | Official URL / Download URL | Downloaded (UTC) | Source SHA-256 | Retrieval Status |
|---|---|---|---|---|---|---|---|---|
| `oa_os_001` | Operating Systems | *Operating System Fundamentals* — Dr. Umar Khokhar & Dr. Binh Tran (Georgia Gwinnett College) | University System of Georgia / Affordable Learning Georgia (Manifold text `0c25695d`, updated `2023-06-08T14:30:07.135Z`) | **CC-BY-4.0** (`creativecommons.org/licenses/by/4.0/`). No exceptions stated. | Official: `https://alg.manifoldapp.org/projects/operating-system-fundamentals` (Manifold CDN EPUB v3 export) | `2026-11-19T11:06:56Z` | `2cb4e96b1615fa49278c9b4ce8136a2cd5c8a41be89df3f230ef5e8ab50b7c97` | `RETRIEVED_VERIFIED` |
| `oa_db_001` | Databases | *Database Design — 2nd Edition* — Adrienne Watt & Nelson Eng | BCcampus Open Education (2014, 2nd Ed.), mirrored on Engineering LibreTexts (Chapters `1.01`–`1.16`) | **CC-BY-4.0** (`creativecommons.org/licenses/by/4.0/`), *except where otherwise noted* (third-party figures & appendices excluded; prose chapters only). | Official: `https://opentextbc.ca/dbdesign01/` (returned Cloudflare HTTP 403 — **NOT bypassed**). Downloaded from official Engineering LibreTexts mirror (`eng.libretexts.org/.../Database_Design_2e_(Watt)/01%3A_Chapters`). | `2026-11-19T11:08:59Z` | `3fca273036bbdeaa1d3c45424449ea71eeb229050cbc4fd56e7dd1a0e54d6982` (composite over `ch01.html`–`ch16.html`) | `RETRIEVED_VIA_OFFICIAL_LIBRETEXTS_MIRROR` |
| `oa_net_001` | Computer Networks | *Computer Networking: Principles, Protocols and Practice* — Olivier Bonaventure (exercises: Vanbever, Van den Schriek, Saucez, Hoerdt) | Université catholique de Louvain (`github.com/obonaventure/cnp3`, commit `155b3a61690f282a7c72fe117fcd3b83c7c09035`, Release 9/2011 `book/CNP3.pdf`, 282 pp) | **CC-BY-SA-3.0** (`creativecommons.org/licenses/by-sa/3.0/`). Verified in `book/LICENSE.txt` and `README.rst`. | `https://github.com/obonaventure/cnp3` (`git clone --depth 1`) | `2026-11-19T11:06:10Z` | `851a31206647a50a0431381b5e7f702e61b50caec351bf1ab63afde37aa6fa6f` | `RETRIEVED_VERIFIED` |
| `oa_ds_001` | Distributed Systems | *Distributed Systems Lecture Notes* — Martin Kleppmann | University of Cambridge, Dept. of Computer Science and Technology (`github.com/ept/dist-sys`, commit `b8167ac35e3f529b851460dfc0feacc9e2436c92`, Copyright 2020–2024, `dist-sys.tex`) | **CC-BY-SA-4.0** (`creativecommons.org/licenses/by-sa/4.0/`). Verified in `README.md`. | `https://github.com/ept/dist-sys` (`git clone --depth 1`) | `2026-11-19T11:05:36Z` | `57909595db8e9d8bc54e7eadf867466e97b965758258a4862de6d619e64cc108` | `RETRIEVED_VERIFIED` |

---

## 2. Retained S5-v3 Verified Local Sources (Read-Only Base, `818` Eligible Passages)

Retained unmodified from frozen S5-v3 (`data/annotation_local/s5v3/corpus_v3/s5v3_corpus_passages.jsonl`, verified SHA-256 `dd8e973b727a981aeb4b8d0109513616c4ea709afe3eed40bde5c8b14ebeaee4`, filtered strictly to `is_usable == True and is_exact_duplicate == False`):

| Doc ID | Domain | Title | License | Retained Passages |
|---|---|---|---|---:|
| `local_oa_001` | Machine Learning | Dive into Deep Learning — Ch. 3: Linear Regression | `CC-BY-SA-4.0` | `26` |
| `local_oa_002` | Natural Language Processing / LLMs | Efficient Guided Generation for LLMs (arXiv:2307.09702v2) | `arXiv-perpetual-nonexclusive` | `23` |
| `local_oa_003` | Mathematics for Machine Learning | Mathematics for Machine Learning (Deisenroth, Faisal, Ong) | Free online PDF (`mml-book.github.io`; local research only) | `719` |
| `local_oa_004` | Robotics / Control | METATRON Preprint (Tessler et al.) | Preprint (local research only) | `50` |

---

## 3. Explicitly Excluded & Forbidden Sources

Programmatically blocked by `check_not_forbidden` in [extractors.py](file:///home/pratay-karali/Desktop/archipelago/research/s5-v3-1-oa-corpus-expansion/scripts/corpus_v31/extractors.py):
1. **`mixu/distsysbook`** — strictly excluded (unverified/ambiguous reuse rights).
2. **`okf_graph.db` (v2.1)** — absent on disk; never reconstructed, faked, or depended upon (`okf_graph_db_dependency: false`).
3. **Copyrighted commercial textbooks & synthetic stubs** — Elsevier (`predictive_analytics_and_data_mining`), z-library PDFs, private personal files, and synthetic test upload stubs remain strictly excluded.
4. **Raw passage text in Git** — all raw downloads and built JSONL files reside exclusively under Git-ignored `data/annotation_local/s5v3_1/`.
