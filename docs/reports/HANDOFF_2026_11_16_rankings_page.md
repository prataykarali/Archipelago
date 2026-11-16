# Research rankings page handoff — 2026-11-16

## Built

- Added a public, verified state-space-models example at `/research/rankings` with a matching five-sheet XLSX download. The preview shows 94 papers, 322 authors, and 57 publications after excluding a provider venue string mistaken for an author.
- Added sortable, searchable Papers, Authors, and Publications tables on the signed-in live search page. The authenticated preview endpoint builds the same standard workbook used by XLSX export, so table cells follow the export's cleansing rules.
- Added requested rankable columns for paper, author, and publication metrics. Values absent from verified providers remain blank; source-specific scores are labeled.
- Cleaned method, dataset, and evaluation evidence objects into readable names in the workbook and page.
- Restored individual paper and topic extraction pages for saved intelligence runs and the public example. Paper titles in ranking tables now open source-backed abstracts, extracted methods, datasets, metrics, claims, provenance, and the exact ranking values. The topic page aggregates verified names, years, providers, and the same cleansed paper set as the workbook.
- Public example pages bypass the idle-login timer. Saved-run pages remain authenticated and owner scoped. The topic page downloads authenticated XLSX through the bearer-aware fetch bridge.
- Pushed branch `feature/multi-provider-research-enrichment` and deployed backend and frontend production aliases on Vercel. Local route tests and live public-page checks passed.

## Deferred

- Production search and XLSX export for an authenticated user were not exercised in this handoff because no signed-in browser session was available. The endpoint was verified with a local authenticated route test; production access control returns 401 without a session.
- Licensed JIF, CiteScore, SJR, SNIP, CORE, and other metrics remain blank until authoritative data is connected.
- Repository-wide quality gate remains red on existing lint, type, magic-number, and file-size debt. Targeted tests and lint for the changed paths passed.

## Next pair

- Run an authenticated production search for a fresh topic, compare the preview with the downloaded workbook, and check the production function logs.
- Add authoritative licensed venue metrics only with provider attribution and coverage dates.
