Production ship complete on Sun Aug  9 09:01:58 AM IST 2026

## 2026-10-06 — production plan and first hardening pass

Built in the isolated `codex/production-hardening` worktree: a traceable P0–P8 master checklist; a read-only resource-lifecycle audit; hosted student enrollment CSV preview/import and first-login password-change paths; modern Supabase secret-key headers; and Pearson reader links that no longer claim an unverified page jump. Removed fabricated sample shelf chapters, years, and page counts where source metadata is absent. No credentials were committed.

Verification: 50 focused source/library/roster tests and 9 auth/roster tests passed. Ruff lint/format passed for the newly affected source-link, shelf, roster, and test files. The broad suite was not a release pass: 988 passed, 10 failed, 6 errors, 6 skipped in a checkout initially missing ignored private corpus/model fixtures. After copying only the graph/catalog fixtures into this worktree, the focused suite passed.

Deferred: full corpus-backed regression, strict mypy and repo-wide quality debt, security and resource-leak remediation, live Supabase account writes, Pearson page-navigation proof, private HF source access, two-pass graph evaluation, Docker ingestion and SLM benchmark, Vercel feasibility, AntDeploy staging/production deployment, old-site retirement, and independent human review. The live AntDeploy site still advertises release `554c8df`, older than this branch. Do not claim production readiness or exact-page Pearson navigation until live evidence exists.

Follow-up in the same pair handoff: librarian spreadsheet preview/apply now stream into a bounded temporary directory and remove it on normal and failure paths. Four focused cleanup tests pass. The audit report above is a dated read-only snapshot of the pre-fix code; the remaining cache, limiter, PDF, and SQLite findings are not fixed or production-tested.
