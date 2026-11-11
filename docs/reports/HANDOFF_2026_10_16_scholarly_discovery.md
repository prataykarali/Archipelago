# Scholarly discovery handoff — 2026-10-16

## Built

- The parallel harvester now reports live fetches separately from fallback catalogs and navigation links. arXiv and OpenAlex are live machine sources. OPAC records count as live only when returned by Koha or a configured `api-anything` operation. Pearson bookshelf entries retain their own source and unknown physical availability. IEM CRP manifest entries remain navigation links. Google Scholar supplies human verification links and zero automated records.
- `GET /api/scholarly/discover?q=...` is registered on the local inference and production REST apps. It performs read-only discovery and never writes SLM training pairs.
- The scheduled cycle writes a dated, source-labeled manifest and summary, then syncs manifests only. It does not sync datasets or LoRA weights. The hosted library can read the published snapshot through `GET /api/scholarly/snapshot`; the page labels its age and each source's mode.
- `api-anything` is optional and configured through `ARCHIPELAGO_API_ANYTHING_CLI`. Koha base URL and IEM CRP library URL are configurable through `ARCHIPELAGO_OPAC_BASE_URL` and `ARCHIPELAGO_IEMCRP_LIBRARY_URL`. Session cookies are read through the existing `IEMCRP_SESSION_COOKIE` setting. No token was added to source files.
- Vercel preparation now writes a scholarly fixture rather than overwriting `books_showcase_data.json`. A local file write does not prove deployment.

## Verified

- One live cycle for `transformer architectures` found four arXiv and four OpenAlex records. OPAC timed out on both public paths; IEM CRP returned HTTP 403 and supplied four manifest links; Google Scholar supplied a verification link only. The manifest records `ingestion_status: not_started` and zero new SLM pairs.
- Hugging Face accepted the manifest and summary uploads. The hosted snapshot endpoint fetched the published manifest and returned eight cataloged live papers.
- Five focused automated tests passed. Targeted Ruff lint and format passed. Strict mypy with imported modules skipped passed on the changed discovery files. The broader chat UI contract test has an unrelated existing failure in the modified chat script. The full quality gate passed lint, banned-pattern, and architecture checks but failed strict types against an interim baseline of 675 repository-wide errors. The three newly reported annotations/types in the discovery code were corrected after that run.

## Deferred

- Live Koha holdings and IEM CRP protected content need approved machine endpoints and authentication details. The site hostnames and a student login ID do not identify a supported API. CAPTCHA or Turnstile challenges are not machine data interfaces.
- Google Scholar remains a human outbound verification link. OpenAlex provides live scholarly metadata for machine use.
- SLM ingestion, paper full-text extraction, and chat answer grounding against these discoveries are intentionally left for the next stage. The discovery endpoint and published snapshot are available to consume after review.
- The scheduler supports `--run-once`, `--daemon`, and `--install-cron`. The user crontab now runs discovery at 00:00 and 12:00 in the host timezone (Asia/Kolkata).

## Next pair

1. Obtain a Koha public API or scheduled CSV/MARC export URL and its authentication mode from the library administrator. Obtain an IEM CRP documented API or approved export path and service account/session policy. Keep credentials in the environment or secret manager.
2. Test those paths from the production host before changing the source mode to live.
3. Review discovery records and licenses before enabling full-text ingestion or SLM training.
