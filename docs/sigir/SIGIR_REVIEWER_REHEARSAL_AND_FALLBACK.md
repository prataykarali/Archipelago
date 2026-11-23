# Archipelago — 5-Minute Live SIGIR Reviewer Rehearsal Script & Fallback Recording Plan

**Issue:** #12 (Hosted Integration, QA & Live Rehearsal)  
**Primary Hosted URL:** `https://archipelago-blond.vercel.app`  
**Secondary Research / Librarian Origin:** `https://archipelago-librarian.vercel.app`  
**Duration:** 5 minutes 00 seconds (strictly timed)  
**Prerequisites:** Authorized Supabase student session (signed in before timer starts); local backup video staged on presenter laptop.

---

## 1. Pre-Flight Checklist (T-15 Minutes Before Demo)

Run these checks 15 minutes before the SIGIR demonstration session:

1. **Verify live deployment health & separate revision from graph fingerprint:**
   ```bash
   python3 scripts/e2e/hosted_e2e_harness.py
   ```
   Confirm:
   - `inference_readiness.ok == true`, `concepts == 610`, `corpus_source == "full"`, `pearson_books == 40`.
   - Record `X-Archipelago-Release` (deployed code revision) separately from `graph_version` (graph export SHA-256 fingerprint, currently `9818ac0e8fd3`).
   - `research_readiness.ready == true`.
2. **Pre-authenticate the demo browser profile:**
   - Open Chrome/Firefox in a clean profile (no personal bookmarks/extensions).
   - Sign in at `https://archipelago-blond.vercel.app/login` with the authorized student demo account.
   - Verify `/chat` loads without redirecting back to `/login`.
   - Keep a second tab pre-loaded on `https://archipelago-blond.vercel.app/library`.
3. **Warm up cold serverless functions:**
   - Submit one warm-up query (`What is a Transformer?`) so Vercel cold-start latency is absorbed before the reviewer arrives.
4. **Stage offline fallback recording:**
   - Keep `archipelago_sigir_fallback_1080p.mp4` open in VLC/QuickTime (paused at 00:00, muted system notifications, full-screen ready on secondary desktop/workspace).

---

## 2. Timed 5-Minute Live Reviewer Script

### Beat 1 — Opening & Verified System Scope (0:00 – 0:30)

- **Screen:** `https://archipelago-blond.vercel.app/chat` (already signed in as student).
- **Say:**
  > "Archipelago is a deployed academic knowledge-graph workspace integrating curated CS/AI concepts, source-page PDF provenance, live scholarly metadata discovery, and institutional Koha OPAC holdings. Every badge distinguishes source provenance from unassessed claim support."
- **Point out:** Chat input, right-hand Graph Inspector, Evidence / Citations drawer, and top navigation to Library & Research.

### Beat 2 — Canonical Concept Resolution & PDF Page Provenance (0:30 – 1:45)

- **Type:** `What is a Transformer?`
- **Verify on screen:**
  - Anchor resolves to `transformer` with Vaswani et al. (2017) *"Attention Is All You Need"*.
  - Badge reads **`Provenance verified · Claim support unassessed`** (or legacy `"Passage located · Grounded"` if pre-redeploy) — explicitly note that provenance verifies the canonical source chunk location, while claim-level entailment is not automatically certified.
  - Click the citation link -> `/api/page-view` -> opens `/read?doc=papers/Vaswani2017_Attention_Is_All_You_Need.pdf&page=2` and renders the original PDF page bytes.
- **Follow-up (optional if ahead of time):** `What mathematical concepts are prerequisites for self-attention?` -> point out `REQUIRES` edges (`matrix_multiplication`, `softmax`). Do **not** claim `USES` or `CONTRASTS_WITH` edges (absent from the deployed runtime graph schema).

### Beat 3 — Live Research Discovery, Dossier & XLSX Export (1:45 – 3:00)

- **Screen:** Navigate to Research workspace (`/research`).
- **Action:** Search topic `Dense Passage Retrieval` (or reopen a pre-saved run if arXiv returns HTTP 429 rate limiting).
- **Verify on screen:**
  - Live scholarly metadata cards from OpenAlex / Crossref (and arXiv when not rate-limited).
  - Open the run dossier and click a primary DOI link (e.g., `https://doi.org/10.18653/v1/2020.emnlp-main.550` -> resolves to ACL Anthology).
  - Click **Export Excel (.xlsx)** -> confirm the downloaded file opens cleanly in LibreOffice/Excel with structured paper rows (verifying valid OOXML `.xlsx` bytes).

### Beat 4 — Public Library & Koha OPAC Freshness Disclosure (3:00 – 3:45)

- **Screen:** Switch to pre-loaded `https://archipelago-blond.vercel.app/library` tab.
- **Verify on screen:**
  - Institutional e-book shelf (91 items: 40 Pearson titles + dataset papers) and Koha catalog holdings (109 records).
  - Point out explicit snapshot freshness disclosure (`koha_stale: true` with `source_updated_at` timestamp) rather than hiding staleness.
  - Open a live institutional Koha OPAC record (`biblionumber=1868` on `uemk-opac.l2c2.co.in`) to show real-time library availability handoff.
  - Note licensing boundary: Pearson titles hand off to the institutional Pearson eLibrary viewer (`ebooks.elibrary.in.pearson.com`) without bypassing institutional subscription walls.

### Beat 5 — Honest Unsupported-Topic Abstention (Q39) & Wrap-Up (3:45 – 5:00)

- **Screen:** Return to `/chat`.
- **Type (exact held-out query Q39):** `Explain Spanner TrueTime and its prerequisites.`
- **Verify on screen:**
  - Badge reads **`No Verified Graph Match · Clean abstention`**.
  - **Zero citations** and **zero fabricated graph nodes/edges** (`render_graph: false`).
- **Wrap-Up (4:30 – 5:00) — Honest Scientific Summary (D5.1-v2):**
  - Concept resolution: **68.4%** supported top-1 accuracy (26/38) vs. BM25 (42.1%) and Snowflake Arctic neural (36.8%).
  - Passage retrieval (algorithmic candidate qrels, not yet human-verified): BM25 MRR **0.75**, Snowflake neural MRR **0.75**, heuristic Graph-Assisted MRR **0.4865**.
  - Unsupported abstention: **12/12** out-of-corpus queries return zero citations and zero fabricated graph edges.
  - Known limitations disclosed upfront: `USES`/`CONTRASTS_WITH`/`APPLIES_TO` are absent from the runtime schema; author-only citation audit found 7/24 (29.2%) strict support and 9/24 irrelevant/spurious citations; independent human annotation is pending.

---

## 3. Fallback Recording Plan (Zero-Panic Contingency)

### 3.1 When to Trigger Fallback (Hard Thresholds)

Switch immediately to the pre-recorded local video (do **not** spend >15 seconds debugging live):

| Trigger Condition | Detection Signal | Immediate Action |
|-------------------|------------------|------------------|
| **Conference Wi-Fi outage / DNS drop** | Page load stalls > 10s | Switch to full-screen offline fallback MP4 at matching beat timestamp |
| **Supabase Auth / Login loop** | `/chat` bounces to `/login` or 401 | Append `?logout=1` once; if still failing after 10s, switch to Beat 2 recording |
| **Vercel cold-start / 5xx** | `/api/chat` > 12s or HTTP 500/503 | Switch to matching segment of fallback MP4 |
| **arXiv HTTP 429 rate-limit** | arXiv returns 429 during Beat 3 | Continue live using OpenAlex + Crossref + pre-saved run reopen/XLSX export (already observed in live probes) |
| **Koha OPAC slow/unreachable** | `uemk-opac.l2c2.co.in` stalls > 8s | Stay on `/library` snapshot view and explain explicit `stale: true` disclosure; show OPAC clip if asked |
| **Pearson subscription prompt** | Institutional login wall appears | Expected by design — explain licensing boundary; never bypass |

### 3.2 Pre-Recording Capture Specification (Record 48 Hours Before Conference)

Record at **1920x1080, 30 fps, H.264 MP4** (plus WebM copy) with a clean browser window (110% zoom for projector legibility) and **no visible credentials, emails, or tokens**:

| Segment | Timestamp | Exact Content Captured | Redaction Check |
|---------|-----------|------------------------|-----------------|
| `S1_login_and_chat` | 0:00 – 1:45 | Authenticated `/chat` -> `What is a Transformer?` -> provenance badge -> click citation -> `/read` PDF page 2 rendered | Hide account email in navbar/toast |
| `S2_research_xlsx` | 1:45 – 3:00 | `/research` -> `Dense Passage Retrieval` -> OpenAlex/Crossref results -> dossier -> DOI redirect to ACL Anthology -> Download & open `.xlsx` | No API keys in DevTools |
| `S3_library_opac` | 3:00 – 3:45 | `/library` -> e-book shelf + Koha snapshot (`stale: true` badge) -> live Koha OPAC `biblionumber=1868` | No patron/staff cookies |
| `S4_q39_abstention` | 3:45 – 4:45 | `/chat` -> `Explain Spanner TrueTime and its prerequisites.` -> `No Verified Graph Match · Clean abstention`, 0 citations, empty graph | Clean viewport |
| `S5_rbac_negative` | 4:45 – 5:00 | Brief clip or slide showing student role receiving HTTP `403 Forbidden` on librarian `/api/library/import` & `/api/librarian/books` | Redact Bearer token |

### 3.3 Post-Recording Verification Before Packing Laptop

1. Play the entire 5-minute MP4 offline with Wi-Fi **turned off**.
2. Confirm every segment chapter marker jumps cleanly in VLC/QuickTime.
3. Verify zero emails, tokens, or `.env` values appear in any frame.
4. Keep a local copy of the redacted `docs/sigir/d8_evidence/d8_authenticated_e2e_results.json` and `docs/sigir/D8_AUTHENTICATED_E2E_REPORT.md` for reviewer Q&A.

---

## 4. D8-Verified 5-Minute SIGIR Demo Recording Instructions (3 Authoritative Scenarios)

Validated live on `https://archipelago-blond.vercel.app` (deployment `dpl_8QiQvF79qZLQS9oj5xaobxurDarY`, `X-Archipelago-Release: 1785846a49db27d5931beb596cf64bbbae778f3c`, `graph_version: 9818ac0e8fd3`) — **HOSTED DEMO GO (6/6 PASS)**.

### Pre-Recording Setup (Do Before Pressing Record)

1. Sign in via `/login` with the authorized demo student account; verify `/chat` loads cleanly.
2. Pre-save one `Dense Passage Retrieval` run in `/research` (30-paper discovery takes ~55–65s on cold start; having a saved run ready lets you demonstrate reload persistence + dossier + `.xlsx` export within the 5-minute budget).
3. Avoid running automated chat scripts against the presenter account within 10 minutes of recording (to stay clear of per-account `/api/chat` rate limiting).
4. Record at `1920x1080`, 30 fps, H.264 MP4; mask or crop out any personal account identifier in the navbar.

### Scenario 1 — Grounded Concept Graph & Original PDF Provenance (0:00 – 1:50)

- **Route:** `/chat` -> `/read`
- **Action:** Submit `What is a Transformer?`.
- **Show on screen:**
  1. Right-hand Graph Inspector rendering `Transformer` with validated `REQUIRES` prerequisites (`Matrix Multiplication`, `Attention Mechanism`, `Recurrent Neural Network`, `Neural Network`).
  2. Provenance status (`provenance_verified`, `claim_support_status: not_assessed`) — state clearly that provenance verifies the source passage location, not automated claim entailment.
  3. Click `Vaswani2017_Attention_Is_All_You_Need.pdf — page 2` -> opens `/read?doc=papers%2FVaswani2017_Attention_Is_All_You_Need.pdf&page=2` and renders page 2/15 of the original 2.2 MB PDF.

### Scenario 2 — Scholarly Research Discovery, Durable Persistence & Excel Export (1:50 – 3:30)

- **Route:** `/research` -> `/research/topic?run=<id>` -> `.xlsx` download
- **Action:** Open `/research`, show `Dense Passage Retrieval` in *Previous research topics* (or run a fresh search if time permits), reload the page to prove durable persistence, reopen the saved topic dossier (allow 4–8s for dossier hydration), click a primary DOI link (e.g., `https://doi.org/10.1186/s40537-025-01257-9` -> SpringerOpen), and click **Export Excel (.xlsx)**.
- **Show on screen:** Open the exported `.xlsx` workbook in LibreOffice/Excel showing all 4 sheets (`Start Here`, `Papers`, `Authors`, `Sources`) with real paper metadata and live clickable hyperlinks (103 hyperlinks verified via `openpyxl`).

### Scenario 3 — Institutional Library Freshness & Honest Out-of-Corpus Abstention (3:30 – 5:00)

- **Part A — Library & OPAC (3:30 – 4:15):** Open `/library`, filter by `Algorithms`, point out the explicit freshness disclosure (`koha_stale: true`, dated `koha_source_updated_at`), and open a live institutional Koha OPAC record (`biblionumber=1910` on `uemk-opac.l2c2.co.in`).
- **Part B — Honest Abstention (4:15 – 5:00):** Return to `/chat` and ask `What is Spanner TrueTime?`. Point out the Trace panel: `GUARDRAIL_INTERCEPT`, `0 hops`, `0 cited passages`, `no_graph_match`, `0.02 s` — proving zero fabricated graph edges or citations on out-of-corpus queries. Conclude with a 15-second note on verified RBAC and P0-2 cross-user run isolation (`404` across student/faculty sessions, `403` student on librarian endpoints).
