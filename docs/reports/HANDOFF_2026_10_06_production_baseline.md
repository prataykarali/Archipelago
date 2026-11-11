# Production baseline handoff — 2026-10-06

## Built

- Added `scripts/source_size_gate.py` to audit Python, JavaScript/TypeScript,
  HTML, CSS, shell, and YAML sources across application, UI, script, and test
  directories. Generated, minified, and vendor files are excluded.
- Connected the audit to the existing quality gate and set its limit to the
  production roadmap's 400 lines. The previous local setting was 1,500 lines
  and the gate checked only Python outside tests and scripts.
- Added focused tests for source coverage and generated/vendor exclusions.
  They pass, as do Ruff lint and format checks on changed Python files.

## Current release baseline

- Current branch: `archipelago3`; locally recorded remote default:
  `origin/session3-stable`. `HEAD` is `5280237` (2026-10-04).
- The worktree already had extensive changes before this handoff. After these
  edits, Git reports 539 modified/deleted tracked files and 63 untracked
  top-level entries. Nothing was staged, committed, or deleted.
- The new full-tree source audit reports **68 files over 400 lines**. The prior
  roadmap listed 56 paths; 55 of those 56 remain over 400 lines. The broader
  audit includes current changes and additional source roots. Its largest file
  is the 1,844-line root `books_showcase_src.tsx`, linked from
  `frontend/book-stack/books_showcase_src.tsx`.
- Antideploy's local config starts `host_inference/hostapp.wsgi:application`.
  The hosted UI is served from `host_inference/ui/`. The current GitHub CI
  Docker job builds the root Dockerfile, so it does not establish parity with
  that Antideploy start path.
- Verified browser callers so far: hosted chat sends to `/api/chat`; graph
  choice fetches `/api/chat/diagnostic-mcqs` and posts telemetry; the hosted
  library fetches `/api/library/data`, `/api/auth/me`, and ingest routes.
  A complete caller-to-route inventory remains open.
- CI currently uses `continue-on-error` for type checking, integration, and
  security jobs. Its Bandit, dependency, and secret scans also swallow scan
  failures. A green CI result therefore does not certify those gates.

## Deferred / next pair

1. Preserve and review the pre-existing worktree changes, including untracked
   release artifacts. Identify ownership before creating a release commit.
2. Split the active request/response modules and hosted UI source first. Run
   affected tests after each cohesive split; do not mechanically split data or
   visual assets. Drive the 68-file audit to zero.
3. Complete the browser-caller/API-route map and parity tests for the three UI
   trees before consolidating them.
4. Make CI security, type, and integration gates blocking once their current
   failures are triaged. Verify Antideploy's actual image/start path in CI.
5. Continue W1 through W6 acceptance work from
   `PRODUCTION_MODULE_ROADMAP_2026-10-04.md`. No roadmap workstream is fully
   complete based on this handoff.
