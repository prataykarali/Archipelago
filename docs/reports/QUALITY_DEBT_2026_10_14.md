# Quality debt ledger — 2026-10-14

The repository's strict quality gate was already failing before the hosted
Archipelago implementation. With the project virtual environment on `PATH`,
the first complete audit found **1,467 mypy errors in 221 files** and **70
source files over 400 lines**. Ruff also found existing violations. Ruff has
been corrected. Five oversized page copies were reduced by extracting their
embedded styles and scripts. Splitting the quality gate's magic-number constants
reduced the interim size baseline to 64 paths; a later alias helper extraction
reduced it to 63.

The interim baseline is stored in `scripts/baselines/quality_debt.json`.
`scripts/quality_gate.py` runs the strict tools and fails on a new diagnostic,
on a newly oversized file, or if an existing oversized file grows beyond its
recorded line count. Passing this interim gate **does not mean** `mypy --strict`
or the 400-line source audit is clean. The gate prints both outstanding totals.

To inspect the complete debt directly:

```bash
PATH="$PWD/.venv/bin:$PATH" .venv/bin/mypy --strict archipelago/ okf/
.venv/bin/python scripts/source_size_gate.py
```

When a violation is fixed, reduce the matching entry in the baseline. The
baseline must never be raised to accommodate a new violation. Remove baseline
handling from the gate once both strict tools pass with no violations.

The first type cleanup added return and constructor annotations to
`archipelago/config.py` and four small API/inference/scholarly modules. API
auth and middleware response annotations, typed API route responses, and a
small alias-word module brought the strict mypy count to 1,398 errors in 210
files. Kùzu query-result normalization for graph export and librarian review
reduced it further to **1,297 errors in 207 files**. The alias module reduced
the oversized-file count to 63. Fourteen unused, untracked monolith copies
shadowed by packages of the same name were archived outside the repository at
`/home/pratay-karali/.codex/backups/archipelago-shadowed-20261015`, reducing
the direct source-size backlog to 49. A retrieval-term helper brought it to
**48**. All fourteen package imports and focused regressions still pass.
Remaining work is organized by module so existing
public contracts and tests can be checked after each split or type change.

On 2026-10-15, further graph export, structural audit, gold-evaluation, and
evidence typing reduced direct strict mypy to **1,204 errors in 205 files**.
The direct size audit now reports **46 paths**. Gold edge normalization and
evidence row mapping were extracted into small modules. The reviewed interim
baseline contains 1,195 type diagnostics and 45 oversized paths; it was only
reduced, never raised. Another task is actively adding scholarly pipeline
files in the shared checkout. Its unreviewed pipeline currently adds nine
strict mypy diagnostics and one 533-line file. Ruff also fails on those new
files. Recheck the combined checkout when that task finishes. No deployment
or independent-role review has occurred.

## 2026-10-15 update

The other task stopped, and its scholarly pipeline files were included in this
cleanup. Direct strict mypy now reports **837 errors in 171 files**, and the
400-line audit reports **34 paths**. The interim baseline records these exact
totals and has only shrunk. The full unit suite passed (922 passed, 6 skipped).
The integration suite excluding the live parallel-harvester file passed
(38 passed). Vercel CLI authentication reached the existing
`archipelago-6383/archipelago` project. Deployment and independent-role review
have not occurred; the direct gates remain open.
