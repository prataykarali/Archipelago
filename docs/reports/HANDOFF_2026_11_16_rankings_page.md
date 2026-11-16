# Research rankings page handoff — 2026-11-16

## Built

- Added a public, verified state-space-models example at `/research/rankings` with a matching five-sheet XLSX download. The preview shows 94 papers, 323 authors, and 57 publications.
- Added sortable, searchable Papers, Authors, and Publications tables on the signed-in live search page. The authenticated preview endpoint builds the same standard workbook used by XLSX export, so table cells follow the export's cleansing rules.
- Added requested rankable columns for paper, author, and publication metrics. Values absent from verified providers remain blank; source-specific scores are labeled.
- Cleaned method, dataset, and evaluation evidence objects into readable names in the workbook and page.
- Pushed branch `feature/multi-provider-research-enrichment` and deployed backend and frontend production aliases on Vercel. Local route tests and live public-page checks passed.

## Deferred

- Production search and XLSX export for an authenticated user were not exercised in this handoff because no signed-in browser session was available. The endpoint was verified with a local authenticated route test; production access control returns 401 without a session.
- Licensed JIF, CiteScore, SJR, SNIP, CORE, and other metrics remain blank until authoritative data is connected.
- Repository-wide quality gate remains red on existing lint, type, magic-number, and file-size debt. Targeted tests and lint for the changed paths passed.

## Next pair

- Run an authenticated production search for a fresh topic, compare the preview with the downloaded workbook, and check the production function logs.
- Add authoritative licensed venue metrics only with provider attribution and coverage dates.
