Production ship complete on Sun Aug  9 09:01:58 AM IST 2026

## 2026-10-06 — inference reply and hosted chat handoff

Built: disabled completed-answer cache replay in both inference chat routes; kept
request rate limits and simultaneous-request deduplication. The AntDeploy
`host_inference` path now asks for two to three grounded paragraphs and tries
NVIDIA when xkiro returns an empty stream. Plural concept questions can reach
graph synthesis. Hosted chat shows up to six named page links before a source
inventory table, with yellow keyword markup and no shared Pearson credential
display. The Hugging Face PDF gateway permits public dataset files without a
token and accepts a token when configured.

Verified: 92 targeted tests passed, two skipped; JavaScript syntax and changed
Python lint passed. The full quality gate still fails on existing repository
lint and 68 oversized files. No AntDeploy deployment was performed.

Deferred: finish live Pearson and Hugging Face reader verification, restore
role-specific Supabase login, compare and restore the three 3D page effects,
and deploy after reviewing the already extensive uncommitted worktree.

## 2026-10-11 — account and personalized roadmap handoff

Built: hosted chat and library routes now require Supabase identity by default.
Browser chat and quiz state use account-specific keys. Idle sessions expire after
five minutes. Chat queries have a persistent 35-per-day count and a one-hour
pause after each seven accepted queries. The quiz needs at least three answers;
the first completed result is saved per account. The personalized graph draws
an ordered, selectable chain with readable labels and source actions. The gap
button became a short explanation. Mirrored the chat UI changes into the
source UI. The normal graph now spaces nodes farther apart and opens its
scroller at the prerequisite end. Added a clearly labelled sample inventory
CSV and phone-width handling for the roadmap and holdings table.

Verified: focused auth, quota, roadmap, source-link and regression tests passed;
changed Python lint and JavaScript syntax passed. No live deployment was made.

Deferred: verify the flows with two real Supabase accounts and a phone browser.
The institutional catalogue remains a common library collection; this change
does not create private uploaded-book collections. Keep provider keys in the
existing ignored environment file and rotate any keys exposed outside it.

## 2026-10-11 — Pearson browser handoff and integrated release

Built: integrated the hosted release with `session3-stable` on
`codex/hosted-release-integrated`. Pearson book links now show a two-step
handoff: sign in on Pearson, return to Archipelago, and open the selected title
in the same browser. The library book card accepts a requested page number and
no longer invents chapter page references when a title lacks a real TOC.
Removed a live Pearson password literal from a legacy test.

Verified: 99 focused hosted tests passed, the hosted chat UI smoke passed, and
one legacy Pearson gateway test passed. In a browser, Pearson login established
a session, and an authenticated direct book URL loaded the PDF reader. Pearson
ignored a `/page/7` fragment on initial load and restored a different page;
entering 7 in its page box worked. A later Pearson redirect produced a blank
reader tab, so automatic page landing and session checks are not verified.

Deferred: the PR remains draft because the repository-wide quality gate has
five failures in older code and the required independent review is pending.
Production AntDeploy was not changed. Each browser must authenticate with
Pearson independently; Archipelago cannot inspect or distribute Pearson cookies.
The hosted ingestion worker remains disabled because it does not publish to
the hosted corpus.

## 2026-10-11 — librarian access handoff

Built: librarian and administrator sign-in now opens the library management
console, and staff navigation links directly to it. The console scrolls to
its controls after identity verification. Added a holdings CSV import form
using the existing librarian-only Supabase-backed endpoint. Graph exploration
remains available from the console. Document and chapter ingestion stay
disabled because the hosted worker cannot publish into the live corpus.

Verified: 17 focused hosted and regression tests passed after this change.
The repository-wide quality gate still fails on older lint, type, banned
pattern, magic-number and dependency-direction issues. Live librarian login
could not be tested without a librarian account. Production remains unchanged;
the updated draft PR awaits a green gate and independent review.
