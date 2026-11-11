# Handoff — OPAC and research discovery, 29 October 2026

## Built

- Confirmed the UEMK Koha OPAC has a searchable catalog index and individual records.
- Switched scholarly OPAC discovery to the existing local Koha ODS export. It makes no automated request to the OPAC.
- Set book and paper asset resolver defaults to `Prataykarali/Library_books`; graph metadata remains in `Prataykarali/graphier`.
- Added a Google Scholar review link and `ingestion_status=not_started` to the daily research discovery report.
- Created a daily Codex research-discovery follow-up that asks for an ingestion decision and does not ingest.

## Deferred

- Daily OPAC updates require an authorized machine-readable export or API. The public OPAC's `robots.txt` disallows all crawlers, OAI-PMH is disabled, and a sample MARCXML request returned 406. Scrapling, Apify, and Anything API do not change this source policy.
- Google Scholar supplies verification links and user-created email alerts, not a machine-search API for this project. Existing scheduled paper discovery uses scholarly metadata providers.
- Created `archipelago-librarian` (`prj_SdRNUdTLO2HFe1u2qyqUiYTYjzws`) under the shinaura Vercel team. It has no deployment or domain yet. `archipelago-blond.vercel.app` belongs to the separate Archipelago team/account. A true split still needs a smaller librarian-only bundle and shared durable Supabase/Hugging Face configuration.
- Ingestion, dataset uploads, and production deployment were not started.

## Next pair

1. Obtain an authorized daily Koha export/API and its delivery location. Validate schema, checksum, and freshness before each sync.
2. Build the librarian-only deployment bundle, then point both deployments at the same Supabase project and the two existing Hugging Face datasets.
3. Keep research discovery and GPU ingestion as separate stages; require a librarian decision before queueing new topic or paper ingestion.
4. Verify research chat reads new Supabase evidence at request time and label OPAC holdings with snapshot age until a live authorized feed exists.
