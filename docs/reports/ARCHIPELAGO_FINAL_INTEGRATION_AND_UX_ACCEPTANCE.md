# Archipelago — Final Integration, Security Hardening & UX Acceptance Report

**Branch:** `fix/s6-security-chat-ux`  
**Base Commit:** `05a82eb` (`feature/s6-final-platform-integration`)  
**Head Commit:** `b396a04`  
**Main Application:** `https://archipelago-blond.vercel.app` (`host_inference/`)  
**Librarian Application:** `https://archipelago-librarian.vercel.app` (`host_research/`)

---

## 1. Executive Summary

This phase hardened application security headers and Markdown sanitization, repaired source-to-chat routing and diagnostic truthfulness, added KaTeX mathematical rendering, and simplified the Librarian Dashboard (`/librarian`) and Knowledge Graph (`/academic/graph`) exploration UX without introducing S7 features, new research algorithms, unauthorized ingestion, or automatic S4 publication.

---

## 2. Security Hardening Summary

- **Secret Hygiene:** Verified `data/private/` is untracked (`git ls-files data/private/` empty) and excluded via `.gitignore`; no hardcoded tokens or service-role keys exist in tracked frontend bundles or source files.
- **Content Security Policy (CSP):**
  - `host_research/app.py`: Added `Content-Security-Policy` in `browser_origin()` (`default-src 'self'`, `frame-ancestors 'self'`, `object-src 'none'`, `base-uri 'self'`, and explicit allowlists for required CDN scripts/styles and Supabase/Hugging Face endpoints).
  - `host_inference/hostapp/middleware.py`: Extended `style-src` and `font-src` to include `https://cdn.jsdelivr.net` for KaTeX stylesheets and fonts.
- **RBAC & Transport Checks:** Verified unauthenticated `/api/librarian/overview` returns `401` and path traversal `/api/reader/info/../../.env` returns `404`.
- **Markdown + KaTeX Sanitization:** Updated `host_inference/ui/js/01--hide-welcome-with-transitio.js` to extract `$...$` / `$$...$$` / `\(...\)` / `\[...\]` spans before `marked.parse()`, sanitize HTML via `sanitizeMarkdown()`, restore HTML-escaped math tokens, and invoke `renderMathInElement()`.

---

## 3. Source-to-Chat & Diagnostic Repairs

- **General Academic Explanations (`route_logic.py`):** Extended `ACADEMIC_DOMAIN_RE` to cover `agi`, `artificial general intelligence`, `superintelligence`, `pagerank`, `e-resources`, `opac`, `pearson`, `textbooks`, and `curriculum` so unindexed academic topics route to `GENERAL_EXPLANATION` instead of `GUARDRAIL_INTERCEPT`.
- **Institutional E-Resources & OPAC Routing (`route_logic.py`):** Added `_institutional_eresources_reply()` and `_catalog_books_reply()` backed by `remote_cache.load_library_manifest()` and `catalogue.load_catalogue()`, reporting verified counts and links for Pearson Digital eLibrary (`40` eBooks), Archipelago Cloud Reader, and UEM Kolkata Koha OPAC (`https://uemk-opac.l2c2.co.in/`) without inventing external publisher subscriptions.
- **Indexed Paper Lookup (`route_logic.py`):** Added `_indexed_papers_reply()` so paper queries (e.g., `"Show me papers about KV caching."`) match indexed preprints (`Kwon2023_vLLM.pdf`) and graph evidence with `hide_graph: True`.
- **Broken `textbooks/*.pdf` Quarantine (`graph.py`):** Updated `cite_record()` to quarantine `doc_id.startswith("textbooks/")` by clearing `hf_url`/`page` and marking `source_type = "metadata_only"` and `access_status = "Unavailable"`.
- **Diagnostic Truthfulness (`diagnostics.py`):** Updated `diagnostic_payload()` so unindexed concepts (e.g., `hessian_matrix`) return `available: False`, `success: False`, `mcqs: []` instead of falling back to `2d_discrete_convolution`.

---

## 4. Librarian & Knowledge Graph UX Simplification

- **`/librarian` (`host_research/ui/librarian.html`, `librarian.js`):**
  - Replaced the flat 8-card overview with 4 source-backed KPI cards (`Pearson eBooks`, `HF Reader PDFs`, `Koha Snapshot`, `Pending S4 Reviews`), 4 primary workflow cards, and a collapsed `<details>` drawer for secondary staff workflows (`Circulation`, `Orders`, `Fine notes`, `Research Discovery`, `Official Koha OPAC`).
  - Updated `#people-traffic-panel` so `#traffic-body` stays hidden when `physical_footfall.status !== 'connected'` and displays `"Not connected — no live gate or QR check-in events recorded yet."`.
- **`/academic/graph` (`host_research/ui/academic_graph.html`):**
  - Changed `.graph-toolbar` from `position: absolute` to `position: relative` above `.graph-stage` so the search bar never overlaps rendered graph nodes.
  - Added dynamic `#domain-filter`, live `#filter-match-count` (`Showing N nodes · M edges`), and a collapsed-by-default `<details id="advanced-filters">` section with `#evidence-filter` and `#clear-filters`.

---

## 5. Verification Results

- **Targeted Unit & Regression Suite (`tests/unit/test_security_chat_ux_fixes.py`):** `8 passed` in `7.88s` (covers AGI/PageRank routing, e-resources/OPAC, OS books, KV caching papers, Hessian diagnostic `available: False`, `textbooks/*.pdf` quarantine, CSP headers on both services, RBAC `401`, and UI structure).
- **Local Phase 8 E2E & Playwright Check (`verify_phase8.py`):**
  - All 12 Chat scenarios (`AGI_1`, `AGI_2`, `ERES_1`, `ERES_2`, `ERES_3`, `OS_AVAIL`, `OS_BOOKS`, `KV_PAPERS`, `HESSIAN_DEF`, `BFS_DFS`, `TRANSFORMER_PREREQ`, `PAGERANK`) routed to expected intents.
  - Playwright desktop (`1440x960`) and mobile (`390x844`) verified zero horizontal overflow on `/librarian` and `/academic/graph`, non-overlapping `.graph-toolbar`, collapsed `#advanced-filters`, dynamic `#domain-filter`, and `#clear-filters`.
