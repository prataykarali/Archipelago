# Archipelago S1–S6 Final Acceptance & Fix Plan

**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration`  
**Supabase Project:** `spllaastejfwclllfndp`  
**Main Backend (Production):** `https://archipelago-blond.vercel.app` (alias of `archipelago-7niutd6k9-archipelago-6383.vercel.app`)  
**Protected Preview (Latest Multi-Source Build):** `https://archipelago-l7ihqkcd9-archipelago-6383.vercel.app` (deployment `4epazA4Yw8conwkteWJcF7C2nDW7`)  
**Librarian App (Production):** `https://archipelago-librarian.vercel.app` (`shinaura` Vercel team)  
**Final Verdict:** **`ARCHIPELAGO CONDITIONALLY RELEASED`**

---

## 1. S1–S6 End-to-End Audit Matrix

| Stream | Scope Verified | Status & Environment | Key Evidence |
|---|---|---|---|
| **S1/S2** | Academic Chat, Kùzu Graph (`610` concepts, `graph_version: 9818ac0e8fd3`), OPAC grounding, multi-turn chat | **Verified in Production** | Live `200 OK` across 10/10 CS/Math/AI domains + Library OPAC (`https://uemk-opac.l2c2.co.in/`) + multi-turn follow-up (`1,296–4,007 ms`, zero MCQ noise). |
| **S3** | Supabase auth (`RS256` JWKS + `ES256` fallback), role isolation, cache/dedup | **Verified in Production** | Unauth `401`, student forbidden `403` on staff/admin routes; Supabase cache live. |
| **S4** | Academic ingestion review & safety gates | **Verified in Production (Gated)** | Candidate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` verified `publication_status: BLOCKED`; student decision `403`, unreviewed librarian decision `409`. |
| **S5 (Core + Multi-Source)** | OpenAlex, Crossref, S2, arXiv, DBLP (gate-detected), OpenAIRE, DataCite, OpenCitations, Europe PMC, PubMed, ORCID, Google Scholar BibTeX/RIS import, 50-ID author/venue enrichment, 14-sheet `.xlsx`, Research Chat, Cron | **Verified Locally & Protected Preview** | `51/51` pytest passing; 7-topic live multi-provider run (`9.8–14.4 s/topic`, 14 sheets, OpenCitations `8/8` DOIs); live prod `/xlsx` `200 OK` (`68,805` bytes). |
| **S6** | Library Analytics (`Koha` + academic events + PII rejection + dedup), Unified UI routes | **Verified in Production (Main)** / **Blocked by External Auth (Librarian Prod)** | Live analytics `109` titles / `904` copies / `901` available; PII `400`; idempotent dedup; Main pages `392–494 ms`. `host_research/` pending `shinaura` team promotion. |

---

## 2. Prioritized Issue Register (P0–P3)

| ID | Severity | Component | Root Cause, Fix & Status |
|---|---|---|---|
| **P0-1** | **P0 (External Release Gate)** | `archipelago-librarian.vercel.app` (`shinaura` team) | **Open**: Operator CLI lacks `shinaura` deployment scope; `host_research/` must be promoted by an authorized `shinaura` team owner. |
| **P0-2** | **P0 (Governance Gate)** | S4 D2L Candidate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` | **Open (Intentional)**: `publication_status: BLOCKED` pending independent human librarian scientific review (`review_digest: 0fba3b14cc9e50fac0fd32fb960ac2a94fe9430f71b6fdbb10e640dd58fc9c77`). |
| **P1-1** | **P1 (Fixed)** | Stage-2 Author Enrichment Cap (`MAX_AUTHOR_LOOKUPS = 8`) | **Resolved**: Replaced with 50-ID batched OpenAlex `/authors` queries + cache; `jarvis ai` author coverage rose from `8/94` to `94/94`. |
| **P1-2** | **P1 (Fixed)** | Multi-Source Identity & Deduplication | **Resolved**: Extended `PaperIdentifiers` and `Canonicalizer` for `pmid`, `pmcid`, `dblp_key`, `openaire_id`, `datacite_doi`; never merges by title alone. |
| **P1-3** | **P1 (Fixed)** | Missing Venue URLs, Claims & Sparse Workbook | **Resolved**: Added `enrich_venues()`, `extract_evidence()`, and 5 normalized sheets (`Institutions_Affiliations`, `Funding_Grants`, `Research_Claims`, `Metric_Observations`, `Coverage_Audit`). |
| **P2-1** | **P2 (External Bot Gate)** | DBLP (`dblp.org/search/publ/api`) | **Documented**: DBLP currently returns `HTTP 202` Anubis JS proof-of-work challenge to automated HTTP clients; `extended_sources.py` detects and reports `blocked_bot_challenge` cleanly without bypassing. |
| **P2-2** | **P2 (Rate Limit / Licensed)** | Semantic Scholar `HTTP 429` & Clarivate JIF/CiteScore/SJR | **Documented**: Unauthenticated S2 burst limits surface `rate_limited` without aggressive retry (add `SEMANTIC_SCHOLAR_API_KEY` if higher quota needed); JIF/CiteScore/SJR remain `LICENSE_RESTRICTED`. |
| **P3-1** | **P3 (Deferred)** | Physical Library Footfall Sensor | **Documented**: Analytics honestly reports `"Data source not connected"` until campus turnstile/RFID telemetry is integrated. |

---

## 3. Exact Operator Actions & Rollback Instructions

### Promotion Steps (Authorized Operators Only)
1. **Promote `host_research/` to `https://archipelago-librarian.vercel.app` (`shinaura` team owner):**
   ```bash
   cd host_research
   vercel link --scope shinaura --project archipelago-librarian --yes
   vercel --prod --yes
   ```
2. **Promote `host_inference/` multi-source preview (`4epazA4Yw8conwkteWJcF7C2nDW7`) after preview sign-off:**
   ```bash
   vercel promote https://archipelago-l7ihqkcd9-archipelago-6383.vercel.app --scope archipelago-6383 --yes
   ```
3. **Complete S4 Human Review:** Inspect candidate `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` in Academic Automation and record an explicit human decision.

### Rollback Instructions
- **Vercel Backend Rollback:** `vercel rollback https://archipelago-7niutd6k9-archipelago-6383.vercel.app --scope archipelago-6383 --yes`
- **Git Branch Rollback:** `git revert --no-edit <commit_sha>` on `feature/s6-final-platform-integration` and re-run `scripts/ops/sync_s5_host_runtime.py`.

---

## 4. Final Acceptance Verdict

**`ARCHIPELAGO CONDITIONALLY RELEASED`**  
All multi-source discovery integrations (OpenAlex, Crossref, Semantic Scholar, arXiv, DBLP gate-aware, OpenAIRE, DataCite, OpenCitations, Europe PMC, PubMed, ORCID, and compliant Google Scholar BibTeX/RIS import), 14-sheet workbook export, Research Chat, monitoring, security isolation, and `51/51` automated tests pass. Full unconditional acceptance awaits only the `shinaura` production promotion and S4 independent human review.
