# ARCHIPELAGO — COMPLETE SOURCE INVENTORY, CHAT EVIDENCE & INTERACTIVE LEARNING DIAGNOSTIC

**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration`  
**Production:** `https://archipelago-blond.vercel.app/` (Main) · `https://archipelago-librarian.vercel.app/` (Librarian)  
**Mode:** Read-Only Diagnostic Audit (no application behavior modified, no ingestion/publication/deployment executed)  
**Date:** `2026-11-15`

---

## Executive Summary

Archipelago already holds substantial real academic data across its knowledge graph (`610` concepts, `1,988` edges), Hugging Face (`Prataykarali/Library_books` with `118` files, `Prataykarali/graphier` with `29` files), institutional catalogs (`40` Pearson eBooks, `91` reader-backed titles, `109` Koha holdings, `1,212` journal issues), and Supabase (`1,908` `research_intake_records`, `350` `research_processing_papers`, `29` `research_topic_inventory`).

However, the Student Chat interface fails to expose much of this evidence reliably due to five concrete integration gaps:
1. **Regex-gated domain allowlist (`ACADEMIC_DOMAIN_RE`):** Rejects valid queries (`"What is AGI?"`, `"What are the e-resources?"`, `"Where can I access the e-book?"`, `"Give me the OPAC link."`) as out-of-scope before checking institutional library/catalog metadata.
2. **Broken hardcoded textbook citations (`ACADEMIC_SOURCES_BY_ID`):** All `22` `textbooks/*.pdf` entries in `host_inference/engine/academic_sources.py` do not exist in `Prataykarali/Library_books` or on disk and return `HTTP 404` on `/api/reader/info/...`.
3. **Disconnected catalog/holding search in Chat:** `koha_bridge.lookup_chat_library_holding` times out or returns `"cannot verify"` instead of querying `library_manifest.json` (`109` holdings, `91` `ebook_shelf`) and `pearson_bookshelf.json` (`40` Pearson books).
4. **Missing graph anchors & quiz gating:** Concepts missing from `okf_graph.json` (e.g., `hessian`, `agi`) receive `anchor_concept: None`, causing `populateTopology()` in `11-populate-topology.js` to suppress both the graph card and the "Take Quiz" button; meanwhile `/api/chat/diagnostic-mcqs?concept=hessian_matrix` silently fuzzy-falls back to `2d_discrete_convolution`.
5. **Missing math renderer:** Chat loads `marked.min.js` (`host_inference/ui/index.html:13`) with **no KaTeX or MathJax**, leaving valid LaTeX (`\( H \)`, `\[ H_{ij} = \frac{\partial^2 f}{\partial x_i \partial x_j} \]`) unrendered as raw delimiters.

---

## Phase 1 — Complete Source Inventory

| # | Source | Location / Store | Records / Docs | Subjects / Scope | Evidence Type | Access / License | Last Sync / Health | Chat Retrieves? | Exact Links Work? | Availability |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **Academic Knowledge Graph** | `host_inference/fixtures/okf_graph.json` (note: root `okf_graph.db` is non-SQLite `data`) | **610** concepts (`507` with sources, `103` with `0` sources), **1,988** edges (`267` requires, `387` unlocks, `1,334` related) | CS, AI/ML, OS, DBMS, Networks, Compilers, Automata, Math | Node summaries + typed graph edges + source IDs | Internal open/mixed metadata | Healthy (`graph_version: 9818ac0e8fd3`) | Partial (only exact/alias matches; `hessian`, `agi` missing) | Partial (`papers/*` yes, `textbooks/*` 404) | Main Vercel, Librarian Vercel, Local |
| 2 | **Hardcoded Textbook Registry** | `host_inference/engine/academic_sources.py` (`ACADEMIC_SOURCES_BY_ID`) | **22** entries (`textbooks/*.pdf`) | OS, DBMS, CLRS, Networks, Compilers, Automata, Linear Algebra, Prob. | 1-sentence synthetic passage + hardcoded `page_number` | Reference metadata only | Broken PDF links (`404`) | Yes (when `anchor_concept` matches) | **No** (`HTTP 404` on `/api/reader/info/textbooks/...`) | Main Vercel, Local |
| 3 | **Pearson eLibrary Catalogue** | `host_inference/fixtures/pearson_bookshelf.json` & `data/catalogs/pearson_bookshelf.json` | **40** books (`ingestion_tier: deep`) | Engineering, DSP, CS, Math, Electronics | Metadata, ISBN, page count, sections, `reader_base_url` | IEM Trust Institutional Subscription (`ebooks.elibrary.in.pearson.com`) | Healthy (`40` reported on `/api/health`) | **No** (not wired into general Chat book lookup) | Requires institutional Pearson login | Main Vercel, Local |
| 4 | **UEM Kolkata Koha OPAC & Manifest** | `host_inference/fixtures/library_manifest.json` + `data/koha/*.ods` + live `uemk-opac.l2c2.co.in` | **109** holdings, **91** `ebook_shelf` (`40` Pearson + `51` HF PDFs), **1,212** journal issues, **952** subject counts, **2,882** subject titles | Multi-disciplinary engineering & CS holdings | Catalogue metadata & copy counts (`available_copies`, barcodes) | Public OPAC / Institutional | Live OPAC slow/intermittent (`timed out` on main; librarian `/api/library/opac/live` falls back to `dated_koha_export`) | **No** (P3_1/P3_2/P3_3 fail to match manifest) | OPAC portal URL works; `/api/library/opac/live` timed out on Main | Main Vercel (manifest), Librarian Vercel (live+fallback), Local |
| 5 | **HF `Prataykarali/Library_books`** | Hugging Face private dataset (`hf_dataset_manifest.json`, `hf_files.json`) | **118** repo files (`51` in `hf_dataset_manifest.json`, `86` in `hf_files.json`) | AI/ML papers (`Vaswani2017`, `Krizhevsky2012`, `Hu2021_LoRA`, `Kwon2023_vLLM`, `Deisenroth_Math_For_ML.pdf`, `ostep_three_easy_pieces/*`) | Full-text PDFs | Private HF (`401` unauth; requires `HF_TOKEN`) | Last modified `2026-11-14T12:36:33Z`, Healthy | Partial (`papers/*` via `okf_graph`) | Yes for `papers/*` (`200` on `/api/reader/info/papers/...`) | Main Vercel (via HF proxy), Local |
| 6 | **HF `Prataykarali/graphier`** | Hugging Face private dataset | **29** files (`catalogs/*.json`, `datasets/dataset1_pedagogical_revamped.jsonl`, `dataset2_scholarly_evidence.jsonl`, `research_okf/*.jsonl`) | Pedagogical & scholarly evidence JSONLs | Structured JSONL evidence & catalogs | Private HF (`401` unauth; requires `HF_TOKEN`) | Last modified `2026-11-14T18:30:25Z`, Healthy | Indirect (exported into `okf_graph`) | N/A (dataset repo) | HF Cloud, Local (`data/datasets/`) |
| 7 | **Supabase Research & Runtime** | Supabase PostgREST (`spllaastefjwclllfndp`) | `research_intake_records`: **1,908**; `research_processing_papers`: **350**; `research_processing_jobs`: **19**; `research_topic_inventory`: **29**; `profiles`: **13**; `research_graph_annotations`: **0** | Academic research topics & papers | Metadata, topics, extracted claims/runs | Authenticated Supabase session / service key | Healthy | Partial (`P4_7_RESEARCH_TOPICS` retrieves `29` topics / `1843` records; `P4_6_KVCACHE_PAPERS` misses) | Via Research UI on Librarian | Main Vercel, Librarian Vercel, Supabase |
| 8 | **Live Scholarly Manifest & APIs** | `host_inference/fixtures/live_scholarly_manifest.json` + arXiv / OpenAlex | **40** cataloged papers (`20` arXiv live, `20` OpenAlex live, `17` IEMCRP fallback nav links, `4` resources) | Deep learning, networks, DSA, distributed systems, NLP | Abstracts, authors, venue, year, `oa_url`, `scholar_link` | Open Access / Public APIs | Updated `2026-11-14T18:30:22Z` | Partial (`research_chat.py`) | Yes (`oa_url`, `scholar_link`) | Main Vercel, Librarian Vercel, Local |
| 9 | **Local Staged Candidates & Jobs** | `data/academic_candidates/` (`2` candidates), `data/academic_jobs/` (`337d88fe...`, `bd817e5d...`), `data/artifacts/papers/` | **2** staged candidates (`d2l.ai` ch3, `arXiv:2307.09702v2`), **2** staging DBs (`615` concepts each, `valid: True`) | Linear regression, LLM guided generation | Extracted PDF/HTML + staging SQLite | Staged S4 only (unpublished) | Validated locally, intentionally unpublished | **No** (intentionally gated by S4) | N/A | Local workstation only |
| 10 | **Local Training Datasets & Research SQLite** | `data/datasets/*.jsonl`, `data/research_intelligence.sqlite3` (`61 KB`), `host_inference/data/research_intelligence.sqlite3` (`168 KB`), `data/private/IEM-UEM e-Resources Login Credentials (1).pdf` | `blended_multitask_dataset.jsonl` (`4.86 MB`), `pearson_v44_pairs.jsonl` (`139 KB`), etc. | Multi-domain CS/AI/Math | Training pairs, SQLite run snapshots, private credential PDF | Internal / `data/private/` restricted | Healthy | **No** (training/private artifacts) | N/A | Local workstation (SQLite also in `host_inference/data/`) |

---

## Phase 2 — Book & Page Citation Verification

Audit of [academic_sources.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/host_inference/engine/academic_sources.py) and live `/api/reader/info/` on `https://archipelago-blond.vercel.app`:

- **Finding 1 (All 22 hardcoded textbook citations fail resolution):** Every entry in `ACADEMIC_SOURCES_BY_ID` references `textbooks/<book>.pdf` with a hardcoded `page_number` and a 1-sentence synthetic summary (`in_hf=False`, `in_local=False`). Calling `/api/reader/info/textbooks/ostep_three_easy_pieces.pdf` returns **`HTTP 404 {"detail":"This document is not a reader-backed dataset file.","error":"not_found"}`**.
- **Finding 2 (`papers/*.pdf` in HF `Prataykarali/Library_books` DO resolve):** Calling `/api/reader/info/papers/Krizhevsky2012_AlexNet.pdf` returns **`HTTP 200`** with `pdf_url: '/papers/books/papers/Krizhevsky2012_AlexNet.pdf'`. Note that `/read?doc=...&page=6` returns an HTML viewer (`HTTP 200`, `6664` bytes) whose client JS fetches `/api/reader/info/<doc>`.
- **Finding 3 (PDF page index vs printed page):** `ACADEMIC_SOURCES_BY_ID` stores `page_number` without `printed_page` (`printed_page: None` in live citations), while `P3_2_NN_BOOKS` returned `page_number: 6`, `printed_page: None` on `papers/Krizhevsky2012_AlexNet.pdf`.

| Topic | Graph Node (`okf_graph.json`) | Cited Document / Availability | Page / Link Status |
|---|---|---|---|
| **Hessian matrix** | Missing (`[]`) | None (`cites: []`) | General LLM explanation only; no verified page reference |
| **Linear algebra** | `matrix_multiplication` (in `ACADEMIC_SOURCES_BY_ID`) | `textbooks/introduction_to_linear_algebra_strang.pdf` p.12 (unavailable) | **Broken** (`in_hf=False`, `404` on `/api/reader/info`) |
| **Virtual memory** | `virtual_memory` | `textbooks/ostep_three_easy_pieces.pdf` p.175 (unavailable; HF has chapter PDFs under `archipelago-books-cs/ostep_three_easy_pieces/`) | **Broken** (`404` on `/api/reader/info/textbooks/ostep_three_easy_pieces.pdf`) |
| **TLB / page tables** | `address_translation` | Cited in live `W1` (`cites: 1`) | Check against actual `ostep` chapter PDFs needed |
| **TCP congestion control** | `tcp_congestion_control` | `textbooks/computer_networks_tanenbaum.pdf` p.545 (unavailable) | **Broken** (`in_hf=False`, `404` on `/api/reader/info`) |
| **Transformer** | `transformer` | `Vaswani2017_Attention_Is_All_You_Need.pdf` (present in HF `Library_books`) | **Available** in HF `Library_books` |
| **Tokenization** | `lexical_analysis` (compiler) | `textbooks/compilers_principles_techniques_tools_aho.pdf` p.109 (unavailable) | **Broken** (`in_hf=False`) |
| **Neural networks** | `neural_network` | Live `P3_2` cited `papers/Krizhevsky2012_AlexNet.pdf` `#page=6` (and `library_manifest` has Pearson `Neural Networks and Learning Machines`) | **Available** (`HTTP 200` on `/api/reader/info/papers/Krizhevsky2012_AlexNet.pdf`) |
| **LLM fine-tuning** | `fine_tuning` | `Hu2021_LoRA.pdf`, `Dettmers2023_QLoRA.pdf` (present in HF `Library_books`) | **Available** in HF `Library_books` |

---

## Phase 3 — Live OPAC & E-Resources Diagnostic

- **Why `"What are the e-resources?"`, `"Where can I access the e-book?"`, and `"Give me the OPAC link."` return OUT OF SCOPE:**
  - In [route_logic.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/host_inference/engine/route_logic.py#L45-L70), `ACADEMIC_DOMAIN_RE` only matches CS/AI/Math technical keywords (`ai`, `ml`, `os`, `dbms`, `hessian`, etc.). It contains **no** institutional library keywords (`e-resources`, `e-book`, `ebook`, `opac`, `journals`, `subscriptions`, `pearson`, `library access`, `remote access`). Consequently, `route()` rejects them with `verified_deterministic`: `"That topic falls outside the current scope of this library assistant..."`.
- **Actual verified institutional resources in repo:**
  1. **UEM Kolkata Koha OPAC:** `https://uemk-opac.l2c2.co.in/` (`109` catalog holdings, `1,212` journal issues, `952` subject counts, `2,882` subject titles in `library_manifest.json`). Note: live OPAC timed out on Main (`/api/library/opac/live?q=Operating+System+Concepts`), whereas Librarian returns `HTTP 200` with `dated_koha_export` fallback.
  2. **Pearson eLibrary (IEM Trust):** `40` deep-tier eBooks in `pearson_bookshelf.json` (`ebooks.elibrary.in.pearson.com/wr/pdfviewer.html?subscriptionId=35f75a06-07b5-4be6-93c9-d6449a30d88a#book/<id>`). Requires institutional Pearson credentials; **no** unverified subscriptions (IEEE, ACM, Springer, Scopus) should be claimed.
  3. **Hugging Face Reader PDFs:** `51`–`86` indexed PDFs (`library_manifest.json` `hf_paths` / `hf_files.json`), accessible via `/read?doc=...`.
- **Live Chat checks (`P3_1`–`P3_5`):**
  - `P3_1_OS_BOOK` (`"Is Operating System Concepts available in the library?"`): Returned `"This service cannot verify a physical copy or current circulation status..."` (`library_manifest.json` has `0` Koha holdings for `"Operating System Concepts"`).
  - `P3_2_NN_BOOKS` (`"Show me books about neural networks."`): Returned `"Unknown. The provided evidence does not contain specific book recommendations..."` (cited AlexNet dropout passage instead of `Neural Networks and Learning Machines` from `ebook_shelf` or `Journal of neural computing systems` `biblionumber=1913`, `4 / 4` copies from `holdings`).
  - `P3_3_COPIES`: Returned `"cannot verify a physical copy..."` (no conversation-context book binding).
  - `P3_4_EBOOK` & `P3_5_OPAC_LINK`: Both rejected as **OUT OF SCOPE**.

---

## Phase 4 — Academic Routing Error Traces (Live `https://archipelago-blond.vercel.app/api/chat`)

| # | Prompt | Route / Intent | Synthesis Mode | Anchor Concept | Citations | Root Cause of Defect |
|---|---|---|---|---|---|---|
| 1 | `"What is AGI?"` | `route=None`, `intent=None` | `verified_deterministic` | `None` | `0` | **Incorrect guardrail (`ACADEMIC_DOMAIN_RE`):** `"agi"` is absent from `ACADEMIC_DOMAIN_RE` and `okf_graph.json`, triggering `"That topic falls outside the current scope..."` even though AGI is core AI/CS. |
| 2 | `"What is Hessian matrix?"` | `route=None`, `intent=None` | `xkiro_synthesis` | `None` | `0` | **Missing graph node + unrendered math:** `"hessian"` matches `ACADEMIC_DOMAIN_RE`, so LLM answers accurately, but `hessian` has no node in `okf_graph.json` (`anchor=None`, no graph card/quiz) and raw LaTeX is unrendered. |
| 3 | `"What do I need to learn to become an LLM expert?"` | `route=None`, `intent=None` | `xkiro_synthesis` | `None` | `0` | **Missing learning-path/graph anchor:** `"llm"` passes `ACADEMIC_DOMAIN_RE`, but multi-node curriculum/roadmap edges (`transformer`, `attention`, `fine_tuning`, `rlhf`) are not attached (`anchor=None`, `cites=0`). |
| 4 | `"What are the e-resources?"` | `route=None`, `intent=None` | `verified_deterministic` | `None` | `0` | **Missing institutional-library route:** `"e-resources"` is absent from `ACADEMIC_DOMAIN_RE`, causing false out-of-scope rejection instead of listing Pearson eBooks (`40`), Koha OPAC, and HF PDFs (`51`). |
| 5 | `"Which books explain backpropagation?"` | `route=None`, `intent=None` | `xkiro_synthesis` | `None` | `0` | **Catalog not queried:** `error_backpropagation_algorithm` exists in `okf_graph.json` and `library_manifest.json` has `91` `ebook_shelf` + `109` `holdings`, yet Chat falls back to generic LLM text with `anchor=None, cites=0`. |
| 6 | `"Show me papers about KV caching."` | `route=None`, `intent=None` | `verified_deterministic` | `None` | `0` | **Retrieval mismatch:** `kv_cache` is in `okf_graph.json` and `Kwon2023_vLLM.pdf` is in `Library_books`, yet `"papers about KV caching"` fails `RESEARCH_EVIDENCE` retrieval and outputs `"I cannot verify findings or research gaps..."`. |
| 7 | `"What research topics are covered?"` | `route=RESEARCH_EVIDENCE` | `verified_deterministic` | `None` | `0` | **Working:** Correctly queries Supabase `research_topic_inventory` (`29` topics, `1,843` topic-to-paper records). |
| 8 | `"Can you quiz me on the Hessian matrix?"` | `route=None`, `intent=None` | `verified_deterministic` | `None` | `0` | **Missing graph node:** Returns `"the library has not indexed a concept node for this topic"`, suppressing quiz UI. |

---

## Phase 5 — Interactive Concept Graph & Quiz Integration

Audit of [11-populate-topology.js](file:///home/pratay-karali/Desktop/archipelago/Archipelago/host_inference/ui/js/11-populate-topology.js#L7-L18), [13-render-horizontal-graph-card.js](file:///home/pratay-karali/Desktop/archipelago/Archipelago/host_inference/ui/js/13-render-horizontal-graph-card.js#L44-L87), and [12-choose-graph-experience.js](file:///home/pratay-karali/Desktop/archipelago/Archipelago/host_inference/ui/js/12-choose-graph-experience.js#L63-L128):

- **How rendering works:** `08-send-message.js` calls `populateTopology(metadata.anchor_concept, metadata.prerequisites, metadata.unlocks, metadata.related_concepts)`. In `11-populate-topology.js:12`, `if (!anchor) return;` exits immediately when `anchor_concept` is `null` — hiding the SVG topology, horizontal graph card, and the `Take Quiz` button (`quiz-start-${msgId}`).
- **Why valid explanations lose graph & quiz controls:**
  1. Concepts absent from `okf_graph.json` (e.g., `hessian`) return `anchor_concept: None`.
  2. Multi-word/book queries (e.g., `"Which books explain backpropagation?"`, `"What do I need to learn to become an LLM expert?"`) drop `anchor_concept` even when matching nodes (`error_backpropagation_algorithm`, `transformer`) exist in `okf_graph.json`.
- **Quiz API discrepancy:** Calling `GET /api/chat/diagnostic-mcqs?concept=neural_network` returns `available: True, target_concept: 'neural_network', mcqs: 4, chain: 4`. Calling `GET /api/chat/diagnostic-mcqs?concept=hessian_matrix` returns `available: True, target_concept: '2d_discrete_convolution', mcqs: 1` (silent fuzzy fallback to an unrelated concept!).
- **Recommended integration policy:** Attach `anchor_concept` whenever a verified node in `okf_graph.json` matches; never fabricate nodes/edges or silent-fuzzy-fallback MCQs when no node exists; suppress prerequisite/quiz cards on pure research-paper or library-inventory responses (`!isResearchGraph`).

---

## Phase 6 — Research Intelligence & 14-Sheet XLSX Provenance

Verified via live `GET /api/research/intelligence/runs/c9185797-69e1-4fd2-92b1-dd1083b5c620/xlsx` (`HTTP 200`, `79,237` bytes):
- **14 sheets present and populated:** `Papers` (`21` rows), `Authors` (`102`), `Venues` (`8`), `References` (`444`), `Citation_Edges` (`2`), `Topic_Results` (`21`), `Sources_Provenance` (`21`), `Errors_Review` (`12`), `Run_Manifest` (`18`), `Institutions_Affiliations` (`14`), `Funding_Grants` (`1` header-only — provider missing funding grants, not a software bug), `Research_Claims` (`49`), `Metric_Observations` (`129`), `Coverage_Audit` (`9`).
- **Chat integration:** Chat can answer `"What research topics are covered?"` (`P4_7_RESEARCH_TOPICS` -> `29` topics, `1,843` records via Supabase), but failed `"Show me papers about KV caching."` (`P4_6_KVCACHE_PAPERS`) because `research_chat.py` / `route_logic.py` did not match `KV caching` across `research_intake_records` / `research_processing_papers`.
- **Irrelevant citation guard:** `_MEDICAL_PAPER_RE` in `research_chat.py` and `query`-only `_RESEARCH_ENRICH_CUE_RE` in `chat.py` already block false keyword attachment from conversation history.

---

## Phase 7 — Math Rendering Audit

Inspected `P4_2_HESSIAN` live output and [01--hide-welcome-with-transitio.js](file:///home/pratay-karali/Desktop/archipelago/Archipelago/host_inference/ui/js/01--hide-welcome-with-transitio.js#L353-L372):
- **Root cause:** The backend LLM emits valid LaTeX (`\( H \)`, `\( f: \mathbb{R}^n \to \mathbb{R} \)`, `\[ H_{ij} = \frac{\partial^2 f}{\partial x_i \partial x_j} \]`), but `host_inference/ui/index.html` only loads `marked.min.js` and calls `sanitizeMarkdown(marked.parse(processedText))` with **zero** KaTeX or MathJax integration. Consequently, all inline math, block equations, matrices, partial derivatives, fractions, and subscripts render as raw `\( ... \)` / `\[ ... \]` text.
- **Minimal renderer fix:** Load KaTeX CSS/JS + `auto-render` (or protect math spans before `marked.parse` so `_` subscripts are not mangled into `<em>` tags by Markdown, then call `renderMathInElement(target, { delimiters: [{left: '$$', right: '$$', display: true}, {left: '\\[', right: '\\]', display: true}, {left: '$', right: '$', display: false}, {left: '\\(', right: '\\)', display: false}] })` after `sanitizeMarkdown`).

---

## Phase 8 — Source-to-Chat Integration Matrix & Minimal Repairs

| Source | Data available | Chat retrieves it | Exact links work | Graph supported | Quiz supported | Primary Defect |
|---|---|---|---|---|---|---|
| `okf_graph.json` (`610` nodes, `1,988` edges) | Yes | Partial | Partial (`papers/*` yes, `textbooks/*` 404) | Yes (when anchored) | Yes (when anchored) | Missing concepts (`hessian`, `agi`); anchor dropped on book/path queries |
| `academic_sources.py` (`22` textbooks) | Synthetic only | Yes (on match) | **No (`HTTP 404`)** | N/A | N/A | Hardcoded `textbooks/*.pdf` files do not exist in HF or locally |
| `pearson_bookshelf.json` (`40` eBooks) | Yes | **No** | Institutional login req. | No | No | Not wired into Chat book/e-resource lookup |
| `library_manifest.json` (`109` holdings, `91` shelf) | Yes | **No** | OPAC URL works | No | No | Chat ignores `holdings`/`ebook_shelf`; live OPAC times out on Main |
| HF `Prataykarali/Library_books` (`118` files) | Yes (private) | Partial | Yes for `papers/*` (`200`) | Via `okf_graph` | Via `okf_graph` | `okf_graph` / `academic_sources.py` paths mismatch chapter PDFs |
| Supabase Research (`1,908` intake, `350` papers, `29` topics) | Yes | Partial (`P4_7` yes, `P4_6` no) | Via Librarian UI | No | Intentionally suppressed | Topic summary works; paper-level retrieval misses `KV caching` |
| Research Intelligence 14-sheet XLSX | Yes | Indirect | Yes (`200` on Librarian) | No | No | `Funding_Grants` empty due to upstream provider metadata |
| Math Rendering (`marked.min.js`) | LLM emits LaTeX | N/A | N/A | N/A | N/A | No KaTeX/MathJax in `host_inference/ui/index.html` |

### Categorized Minimal Repairs (For Next Implementation Phase)
1. **Incorrect router/intent (High):** Add institutional library / e-resources intent (`e-resources`, `e-book`, `opac`, `journals`, `pearson`, `library access`) returning verified Pearson (`40`), Koha OPAC (`https://uemk-opac.l2c2.co.in/`), and HF PDF (`51`) counts without fabricating IEEE/ACM/Springer subscriptions; add `agi` / `artificial general intelligence` to `ACADEMIC_DOMAIN_RE`.
2. **Invalid/inaccessible citations (High):** Stop returning `textbooks/*.pdf` `page_number` links that `404` on `/api/reader/info/`; resolve only verified HF `Library_books` paths or omit exact-page claims when only chapter/general metadata exists.
3. **Retrieval mismatch (Medium):** Wire `library_manifest.json` (`holdings`, `ebook_shelf`) and `pearson_bookshelf.json` into book-recommendation and copy-availability queries (`P3_1`, `P3_2`, `P4_5`), and improve `research_chat` paper search for `P4_6` (`KV caching`).
4. **Missing graph anchor & quiz fallback (Medium):** Preserve `anchor_concept` on book/curriculum queries when a matching node exists (`error_backpropagation_algorithm`, `transformer`), and remove silent fuzzy fallback in `/api/chat/diagnostic-mcqs` so unindexed concepts (`hessian_matrix`) return `available: false` cleanly.
5. **Math rendering (Medium):** Add KaTeX (`auto-render`) with pre-`marked` math-delimiter protection in `host_inference/ui/index.html` + `01--hide-welcome-with-transitio.js`.
