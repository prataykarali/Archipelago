# D10-S3 — Answering, Source-Page Redirect & Stack-of-Books Report

**Author:** Agent E (`answering-engineer`)  
**Date (UTC):** `2026-11-24`  
**Workspace:** Isolated `workspace:"share"` branch (`swarm-answering-engineer-9da419a8`)  
**Frozen Data Guard:** Zero modifications to `host_inference/fixtures/okf_graph.json`, `queries_heldout_50.json`, benchmark labels, qrels, or TREC runs. No Vercel deployment, no git push, zero exposed `HF_TOKEN` or `subscriptionId` values, zero invented Pearson page numbers, and all human evaluation columns kept strictly blank.

---

## 1. End-to-End 5-Source-Type Answering & Redirect Architecture

All citations produced by `host_inference/engine/graph.py` (`LibraryGraph.cite_record`) now flow through the dedicated classifier [`host_inference/engine/source_resolution.py`](../../host_inference/engine/source_resolution.py) (`resolve_source_target`), which resolves every source against the actual Hugging Face dataset index (`resolve_hf_source`) and the official Pearson catalogue (`load_books`) before emitting any clickable URL or provenance status:

| Source Type | `source_category` | Runtime Behavior & Provenance | Clickable URL Emitted | Exact Page Policy |
|---|---|---|---|---|
| **A. OA Research Paper** | `oa_research_paper` | Verified against private HF `Prataykarali/Library_books` / `Prataykarali/graphier` via server-side `HF_TOKEN` | `/read?doc=<doc_id>&page=N` (streams via `/papers/<name>`) | Exact chunk `page_number` preserved (`page_verified: true`) |
| **B. Full-Text OA Textbook** | `oa_full_text_textbook` | Verified against HF `Library_books` (17 OSTEP chapters + `Deisenroth_Math_For_ML.pdf`; fixed bug that treated all `textbooks/*` as broken) | `/read?doc=<doc_id>&page=N` | Exact chunk `page_number` preserved (`page_verified: true`) |
| **C. TOC / Index-Only Textbook** | `toc_index_only_textbook` | Detected (`Index_*`, `About-the-Authors*`, `Table-of-Contents`, `Front-Matter`, `Glossary`, `Preface`, `No-title-available`); penalized in `evidence_selection.py` (`-50`); never promoted to `provenance_verified` | **None (`""`)** — labeled `(TOC/index metadata only)` | `page_number: null`, `page_verified: false` |
| **D. Pearson Catalogue-Only Textbook** | `pearson_catalogue_only` | Exact-title/slug match to `pearson_bookshelf.json` (never false-mapping McGraw-Hill Silberschatz/Ramakrishnan to Pearson Elmasri); `provenance_status: metadata_only` | `/open/<book_id>` (server-side handoff -> `pdfviewer.html` for 28 PDFs, `index.html` for 12 reflowable books) | `page_number: null`, `page_verified: false` — **never invents Pearson page numbers** |
| **E. Missing / Unsupported Source** | `missing_or_unsupported_source` | Unmapped legacy `doc_id`s (e.g., NIDS paper with `:` in filename, `pilot/silberschatz_3nf_card.txt`, non-catalogue textbooks); `provenance_status: metadata_only` | **None (`""`)** — labeled `(source unavailable — metadata only)` | `page_number: null`, `page_verified: false` (upload test stubs retain recorded page metadata non-clickably) |

### Additional Runtime & Security Hardening
- **`host_inference/engine/docmap.py`:** Mapped 5 legacy `doc_*` slugs (`doc_attention_is_all_you_need`, `doc_bert_pre_training_of_deep_bidirectional`, `doc_direct_preference_optimization_your_language`, `doc_vllm_efficient_memory_management_for`, `doc_mathematics_for_machine_learning`) to their verified HF dataset paths.
- **`host_inference/engine/evidence_selection.py`:** Added front-matter/TOC detection (`_FRONTMATTER_RE`), `+30` HF-resolvable bonus, `-50` TOC/index penalty, and `-30` unresolvable penalty so genuine HF-backed passages always outrank unresolvable or index stubs.
- **`host_inference/engine/inventory_card.py` & `catalogue.py`:** Replaced raw `reader_base_url` (which leaked `subscriptionId=` in chat reply markdown) with server-side `/open/<book_id>` links; preserved `book_type`.
- **`host_inference/remote_cache.py` & `host_inference/hostapp/routes/reader.py`:**
  - `pearson_page_url(book, page=None)` omits `/page/N` on all `reflowable` books (`index.html`) AND on `pdf` books when `page` is `None` (unverified).
  - `/open/<book_id>` and `/api/reader/info` no longer default omitted Pearson page params to `page=1`.
  - `/api/page-view` now checks `resolve_hf_path()` and returns `404` JSON for missing dataset files instead of redirecting to a broken `/read?doc=...` page.
- **Private HF Auth Alignment (with `@hf-sync` #12):** Both `Prataykarali/Library_books` and `Prataykarali/graphier` are private HF datasets; browser links only use internal `/read?doc=...` and `/papers/...` routes while `HF_TOKEN` remains strictly server-side.

---

## 2. 36-Question Before/After Diagnostic Benchmark (`D10_S3_ANSWERING_BEFORE_AFTER_36Q.csv`)

Evaluated all 36 questions from `docs/sigir/D10_ANSWER_GROUNDING_DIAGNOSTICS.csv` separately against the original runtime (`before`) and the candidate runtime (`after`), checking every emitted citation and inline markdown URL against `resolve_hf_source()` and `pearson_bookshelf.json`:

| Metric (36 Diagnostic Questions) | Before (Original) | After (Candidate) | Delta |
|---|---:|---:|---:|
| **Broken 404 clickable URLs** | **11** (across 9 queries) | **0** | **-11 (100% eliminated)** |
| **Exposed `subscriptionId=` URLs in replies** | **30** | **0** | **-30 (100% eliminated)** |
| **False `provenance_verified` on 404/TOC/missing sources** | **5** | **0** | **-5 (100% eliminated)** |
| **Honest `verified` (HF-backed canonical chunk)** | 19 (incl. 5 false) | **14** (0 false) | 100% verified links |
| **Honest `source_linked` (`metadata_only`)** | 4 | **12** | Properly labeled |
| **`partial` (`no_passage`)** | 5 (incl. 3 404 stubs) | **2** | 0 broken links |
| **`unmatched` (clean abstention)** | 8 | **8** | Preserved |
| **Human evaluation columns** | Blank | Blank | Preserved for author |

Full per-question before/after table: [`docs/sigir/D10_S3_ANSWERING_BEFORE_AFTER_36Q.csv`](D10_S3_ANSWERING_BEFORE_AFTER_36Q.csv).

---

## 3. Stack of Books UI & Interactive All-12-Domains Drawer

Updated [`host_inference/hostapp/routes/library.py`](../../host_inference/hostapp/routes/library.py), [`host_inference/ui/fragments/chat-operations.html`](../../host_inference/ui/fragments/chat-operations.html), [`host_inference/ui/js/04-start-new-chat.js`](../../host_inference/ui/js/04-start-new-chat.js), [`host_inference/ui/js/05-display-books.js`](../../host_inference/ui/js/05-display-books.js), and [`host_inference/ui/js/02--kw-highlights.js`](../../host_inference/ui/js/02--kw-highlights.js) — and mirrored all 4 UI files identically to `ui/chat/`:

1. **All 83 Unique Library Sources Exposed Cleanly (`/api/catalog/all`):**
   - **40 Pearson institutional textbooks** (`28` `pdf`, `12` `reflowable`) -> `/open/<book_id>` (zero `?page=` invented, zero `subscriptionId` exposed; `/open/<id>?direct=1` verified `302` to `pdfviewer.html` for PDF and `index.html` for reflowable, `40/40` PASS).
   - **43 unique Open Access HF sources** (`25` research papers + `17` OSTEP chapters + `1` Deisenroth textbook; deduplicated root mirrors and excluded `librarian_uploads/` test fixtures) -> `/read?doc=...` (`/api/reader/info` verified `200` + `/papers/...` stream route, `43/43` PASS).
2. **Interactive "All Domains (12)" Drawer (`#all-domains-toggle-btn` / `#all-domains-drawer`):**
   - Users can browse all **12 canonical domains** with live counts: Operating Systems (`18`), Database Systems (`4`), Data Structures & Algorithms (`4`), Computer Networks (`5`), Compilers & Languages (`2`), Automata & Computation (`0` — honestly shown as empty), Mathematics for Computing (`5`), Probability & Statistics (`3`), Information Security (`2`), AI & Machine Learning (`26`), Software Engineering (`4`), Computer Architecture (`10`).
3. **Zero Fabricated Client-Side Links or Hardcoded Credentials:**
   - Removed the hardcoded client-side Pearson `subscription_id` UUID from `02--kw-highlights.js`.
   - `05-display-books.js` no longer fabricates `/read/<doc_id>` or raw HF blob links for unresolved citations; metadata-only and TOC/index-only citations render non-clickable status badges, while Pearson citations render `Open in Pearson` without invented page numbers.

---

## 4. Automated Verification Summary

- `pytest tests/unit/test_d10_s3_source_redirect.py tests/unit/test_citations.py tests/unit/test_citation_integrity_policy.py tests/unit/test_hosted_release_regressions.py tests/unit/test_chat_ui_contract.py` -> **28 passed, 0 failed**.
- `node --check` on `02--kw-highlights.js`, `04-start-new-chat.js`, `05-display-books.js`, `pearson-handoff.js` -> **PASS**.
- `ruff check` on all modified Python files -> **PASS** (verified before commit).
- Live authenticated browser check of Pearson institutional login (1 PDF + 1 reflowable) and exact-page rendering on HF reader remains a primary-author manual verification item (no `EXACT_PAGE_VERIFIED` claim fabricated without live browser check).
