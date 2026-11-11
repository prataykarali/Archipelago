# Handoff — Library and research queue — 2026-11-01

## Built

- Original Library production deployment `dpl_FKWB4xDWrKrr8HRYq9XPyRgX6NNv` now exposes its public data endpoint and renders the verified 91-title reader shelf, 109 dated Koha holdings, source record links, journals, and subject tables. The two fake demo titles and generic chapter indexes were removed.
- The Library page reads the shared daily Koha snapshot. It links to the Academic Koha section at `https://archipelago-librarian.vercel.app/academic/graph#library-details` and redirects Research to the separate deployment.
- The Academic graph on the librarian deployment has a protected concept annotation editor. The OPAC metadata sync timer remains active at 09:00 Asia/Kolkata.
- The local research worker now waits for a graphical session before claiming a job, so a headless boot cannot falsely decline approval. Supabase queue requests retry transient transport errors and an optional progress heartbeat cannot abort an ingestion.

## Verified

- Production Library API: 91 reader-backed titles, 109 holdings, 1212 journal issues, 952 subject counts, 2882 subject title records, four public OPAC sections, and 20 new arrivals.
- Production `/library` returns 200; `/research` redirects to the librarian deployment; Academic graph and Koha API return 200. Browser rendering showed 91 titles, Koha citations, dated holdings, and current public sections.
- 14 targeted unit tests pass; JavaScript syntax and targeted Ruff lint pass. The research approval dialog appeared. Job `a729551f-bcc1-45cd-ad8d-4c3210460af6` completed with 25 papers, one verified full-text extraction, six abstracts with extracted facts, and zero extraction errors. Its OKF output was published to `Prataykarali/graphier` at `datasets/research_okf/a729551f-bcc1-45cd-ad8d-4c3210460af6.jsonl`.

## Deferred / limits

- The four Koha ODS exports are dated 2026-10-03. Copy counts are labeled as historical and the page links to each current OPAC record. Full live catalogue holdings, rack numbers, and live loans require a fresh authorized Koha feed or authenticated catalogue access.
- The annotation editor changes Archipelago concept annotations; it does not edit Koha's catalogue or modify graph topology.
