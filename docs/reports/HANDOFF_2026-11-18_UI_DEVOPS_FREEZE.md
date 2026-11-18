# Maintenance handoff — UI / DevOps freeze (2026-11-18)

## Scope and release boundary

This maintenance branch originates from `codex/blond-research-unified` and must be reviewed against that branch. It is **not** an S5 research-evaluation branch and must **not** be merged into `research/*` by default.

**Frozen:** retrieval, ranking/scoring, model weights, corpora, annotations, metrics, evaluation scripts, experiment configurations, data provenance, research result contents, and page layout/copy. No new features or visual redesign.

**Allowed:** the minimum navigation fix for the broken `/research/papers?run=undefined` link, isolated regression tests, lightweight CI, and subsequent measured frontend performance or deployment fixes that do not change research semantics.

## Current patch

The paper-search UI rejects empty/stringified-missing run identifiers at (1) search responses, (2) async recovery completion, (3) session state restoration, and (4) incoming deep links. Missing IDs no longer produce `run=undefined` navigation. The saved-run API and S5 retrieval pipeline are unchanged. The actual cause of an absent ID in a hosted backend response remains unverified; do not disguise a backend contract failure as a successful search.

The scoped GitHub Actions workflow runs JavaScript syntax and navigation tests without invoking the research backend. The existing broad `.github/workflows/ci.yml` still targets `main` and `develop`; do **not** treat this new smoke workflow as a replacement for full tests or the independent quality gate.

## Verification and operational blockers

- Review the exact file diff; no ingestion, evaluation, API, scoring, data, or page-template changes are authorized.
- Run `node --check host_inference/ui/research_intelligence.js` and `node --test tests/js/research-navigation.test.mjs`; verify green GitHub Actions before considering the patch for release.
- Test a real valid saved run, a missing saved run, and `?run=undefined` in an authenticated browser. Confirm that failed searches surface an explicit error rather than fabricating results.
- Confirm Vercel project, team, production branch, backend URL, and deployment ID with the owner before releasing. The connected Vercel account available during this patch did not expose the provided `archipelago-blond.vercel.app` deployment; production was not inspected or changed.
- Benchmark before any performance optimization (LCP/INP, request waterfalls, backend response time) and preserve original research-page behavior.
- The repository's AGENTS.md requires independent human review. This branch should remain a **draft PR** until reviewed and browser-tested.

**Deferred:** UI redesign, cache-policy changes, CSS consolidation, data loading refactors, changing the S5 API contract, modifying pipelines or metrics, production promotion. None are implied by this branch.
