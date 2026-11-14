# Archipelago S1–S6 Final Acceptance & Fix Plan

**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration`  
**Supabase Project:** `spllaastejfwclllfndp`  
**Main Backend (Production):** `https://archipelago-blond.vercel.app` (alias of `archipelago-7niutd6k9-archipelago-6383.vercel.app`)  
**Librarian App (Production):** `https://archipelago-librarian.vercel.app` (`shinaura` Vercel team)  
**Final Verdict:** **`ARCHIPELAGO CONDITIONALLY RELEASED`**

---

## 1. S1–S6 End-to-End Audit Matrix

| Stream | Scope Verified | Production Status | Key Evidence |
|---|---|---|---|
| **S1/S2** | Academic Chat, Kùzu Graph (`610` concepts, `graph_version: 9818ac0e8fd3`), OPAC grounding, multi-turn chat | **PASS** | Live `200 OK` across 10/10 CS/Math/AI domains + Library OPAC (`https://uemk-opac.l2c2.co.in/`) + multi-turn follow-up (`1,296–4,007 ms`, zero MCQ noise). |
| **S3** | Supabase auth (`RS256` JWKS + `ES256` fallback), role isolation, cache/dedup | **PASS** | Unauth `401`, student forbidden `403` on staff/admin routes; Supabase cache live. |
| **S4** | Academic ingestion review & safety gates | **PASS (GATED)** | Candidate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` verified `publication_status: BLOCKED`; student decision `403`, unreviewed librarian decision `409`. |
| **S5** | Research Intelligence, 50-ID batched Stage-2 author/venue enrichment, evidence-anchored claims, 14-sheet `.xlsx` export, monitors + cron | **PASS** | `94/94` OpenAlex author enrichment on `jarvis ai`, `365` claims across 6 topics, live `/xlsx` `200 OK` (`68,805` bytes, 14 sheets), `vercel_cron` ticks verified (`401` unauth). |
| **S6** | Library Analytics (`Koha` + academic events + PII rejection + dedup), Unified UI routes (`/`, `/library`, `/research`, `/analytics`, `/academic-automation`) | **PASS (Main)** / **GATE (Librarian Prod)** | Live analytics `109` titles / `904` copies / `901` available; PII `400`; idempotent dedup; Main pages `392–494 ms`. `host_research/` build parity verified, pending `shinaura` team promotion. |

---

## 2. Prioritized Issue Register (P0–P3)

| ID | Severity | Component | Root Cause & Status |
|---|---|---|---|
| **P0-1** | **P0 (External Gate)** | `archipelago-librarian.vercel.app` (`shinaura` team) | **Open**: Current operator CLI lacks `shinaura` deployment permission; `host_research/` must be promoted by an authorized `shinaura` team owner. |
| **P0-2** | **P0 (Governance Gate)** | S4 D2L Candidate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` | **Open (Intentional)**: `publication_status: BLOCKED` pending independent human scientific review. Must not be auto-approved. |
| **P1-1** | **P1 (Fixed)** | Stage-2 Author Enrichment Cap (`MAX_AUTHOR_LOOKUPS = 8`) | **Resolved**: Replaced with 50-ID batched OpenAlex `/authors` queries + cache; `jarvis ai` author coverage rose from `8/94` to `94/94`. |
| **P1-2** | **P1 (Fixed)** | Missing Venue URLs & 2yr Citedness | **Resolved**: Added `enrich_venues()` batch `/sources` lookup; `jarvis ai` venue URLs rose from `0/26` to `10/26` and 2yr citedness to `19/26`. |
| **P1-3** | **P1 (Fixed)** | Narrow Claim Extraction & Sparse Workbook | **Resolved**: Implemented `extract_evidence()` + 5 normalized sheets (`Institutions_Affiliations`, `Funding_Grants`, `Research_Claims`, `Metric_Observations`, `Coverage_Audit`). |
| **P2-1** | **P2 (Known Limitation)** | Licensed Journal Metrics (`JIF`, `CiteScore`, `SJR`) | **Documented**: Requires commercial Clarivate/Scopus APIs; explicitly tagged `LICENSE_RESTRICTED` in `Venues` and `Coverage_Audit`. |
| **P2-2** | **P2 (Known Limitation)** | Cross-Provider Author ID Resolution (`IDENTITY_UNRESOLVED`) | **Documented**: Crossref/arXiv-only authors without OpenAlex IDs are not fuzzy-merged to avoid false attribution. |
| **P3-1** | **P3 (Deferred)** | Physical Library Footfall Sensor | **Documented**: Analytics UI/API honestly reports `"Data source not connected"` until campus turnstile/RFID telemetry is integrated. |

---

## 3. Exact Operator Actions to Close External Gates

1. **Promote `host_research/` to `https://archipelago-librarian.vercel.app` (as `shinaura` team owner):**
   ```bash
   cd host_research
   vercel link --scope shinaura --project archipelago-librarian --yes
   vercel --prod --yes
   ```
   Verify `https://archipelago-librarian.vercel.app/api/research/intelligence/readiness` returns `{"ready": true}` and all S6 navigation routes load.
2. **Complete S4 Human Review:**
   An authorized librarian/reviewer must inspect candidate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` (`review_digest: 0fba3b14cc9e50fac0fd32fb960ac2a94fe9430f71b6fdbb10e640dd58fc9c77`) via the Academic Automation review interface and record an explicit human decision.

---

## 4. Final Release Verdict

**`ARCHIPELAGO CONDITIONALLY RELEASED`**  
All S1–S6 software engineering, scholarly enrichment, 14-sheet Excel export, database persistence, cron monitoring, security isolation, and live `https://archipelago-blond.vercel.app` verification checks pass (`45/45` focused pytest tests passing, `ruff check` clean). Full unconditional release requires only the two external operator actions listed in Section 3.
