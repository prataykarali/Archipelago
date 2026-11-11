# Handoff — Archipelago five-phase implementation, 2026-10-14

## Built

- Hosted student quota now uses the existing Supabase runtime quota with a
  server-side UTC day boundary, 40 requests/day, a full one-hour cooldown after
  each ten counted AI requests, and request-ID idempotency. Trusted staff roles
  bypass that quota. Local SQLite remains the development fallback.
- Quiz diagnostics use 3–6 questions with the requested early-stop rule.
  Completed quiz state and roadmap status are saved per authenticated user.
- Grounded answers use the existing provider path and carry more source links
  when verified metadata exists. Fake page defaults were removed from the
  modified response paths.
- Inventory displays actual sample rows when the development CSV is in use.
  Mobile roadmap behavior and duplicate submit protection were updated.
- Removed embedded Pearson account credentials from the hosted handoff page.
- Ruff lint/format now pass. An explicit debt baseline prevents new strict type
  and 400-line source violations. `archipelago/config.py` is strict-type clean;
  `scripts/quality_gate.py` was split below 400 lines. API auth and middleware
  response annotations and the extracted alias-word helper reduced the strict
  mypy backlog; Kùzu result normalization reduced it further to 1,297 errors.
- The mirrored hosted and canonical JavaScript modules are synchronized.
- Narrow-screen chat and library layouts were checked at 320, 360, 390, 430,
  768, and 1280 px in the local browser. No page-level horizontal overflow
  remained at those widths; the 768 px chat panel now has usable width.

## Verification

- The remote Supabase migrations applied and were transaction-tested with
  rollback for cooldown persistence and idempotency.
- Focused quota, quiz, roadmap, reader, asset, auth-boundary, and UI source
  parity checks passed. The full unit rerun passed with 921 passed, 6 skipped,
  and 506 deselected. Integration passed with 38 passed and 7 deselected.
- The interim quality gate passes 7/7 with warnings. Direct strict mypy still
  has 1,297 errors and the direct size audit has 48 oversized paths. Fourteen
  shadowed, untracked monolith copies were archived outside the repository;
  the archive has a manifest for restoration.

## Deferred / next pair

- Continue genuine type and module-size remediation. Track reductions in
  `docs/reports/QUALITY_DEBT_2026_10_14.md`; do not raise the baseline.
- Continue protected-role browser checks for quiz, roadmap, graph, and
  citations; the local guest smoke app cannot exercise those auth flows.
- Have a different role perform pass 5 human review. The linked Vercel project
  has been identified but no deployment has been made.
- Smoke-test role-specific auth, quota, quiz, roadmap, citations, inventory,
  and desktop/mobile layouts on the deployed application.

## 2026-10-15 continuation

- Typed the graph export, structural audit, gold evaluation, and citation
  evidence modules; extracted gold edge normalization and evidence row mapping.
  The focused graph evaluation and citation integration tests pass.
- Direct strict mypy is now at 1,204 errors in 205 files; the direct 400-line
  source audit reports 46 paths. The interim baseline was reduced to 1,195
  type diagnostics and 45 oversized paths.
- A second task is editing scholarly pipeline files in this shared checkout.
  Their new Ruff, mypy, and file-size violations remain unresolved. Do not
  deploy until the combined checkout passes the full direct gates and a
  different role approves the release.
