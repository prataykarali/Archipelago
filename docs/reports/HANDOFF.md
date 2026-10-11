Production ship complete on Sun Aug  9 09:01:58 AM IST 2026

## 2026-10-12 — landing scene focus and text motion

Built: removed the Connected Knowledge block from the landing page, moved
the short introduction away from the character's face, enlarged and raised
the supplied cinematic scene, and kept the existing navigation, calls to
action, institutional links, and authentication modal. Added accessible
word and letter reveals with the requested stagger and easing, plus a
reduced-motion path.

Verified: 20 hosted regression tests and JavaScript syntax checks passed.
The live Vercel page and phone-width layout were inspected after deployment.

Deferred: no changes to chat, library, or ingestion.

## 2026-10-12 — landing cinematic scene handoff

Built: restored the requested ACME girl clip as the landing background, with
a requestAnimationFrame fade at the start and end of each loop. Kept the
Archipelago wordmark, corner logos, institutional links, auth modal, and chat
visuals. Added the specified four-pixel liquid-glass treatment.

Verified: 20 landing and hosted deployment regression tests passed. The landing
video URL returned HTTP 200 with a video/mp4 content type. The production page
showed active video playback, readable text and links, and no horizontal
overflow at a 390-pixel phone viewport. Chat and library still redirect
unauthenticated visitors to login; readiness returned 537 concepts.

Deferred: no changes to the rest of the product.

## 2026-10-11 — Vercel staff workspace and landing handoff

Built: moved librarian/admin ingestion controls from the bottom of the public
library to the role-guarded `/staff` page. Added local and published graph
links, workstation status and bounded local API waits. The landing page is
static black with animated text, a large Archipelago wordmark, and IEM/UEM
logos in opposite top corners. Chat librarian clips and scene remain intact.
The workstation services now answer private-network preflights for the public
Vercel origin. The hosted corpus and book inventory still hydrate from the
Graphier and Library_books datasets; ingestion remains local.

Verified: 53 focused hosted tests, changed Python lint, JavaScript syntax,
live Vercel readiness, the landing layout, librarian `/staff` access, and
unauthenticated redirect. Local workstation preflight responses were checked
on both ports. The in-app browser blocks direct loopback navigation, so a
browser-to-workstation ingestion action remains unverified there.

Deferred: test a real upload and the local graph link from a regular browser
on the library workstation. Pearson may restore the previous reader page
despite a page fragment in the link.

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

## 2026-10-11 — live account repair handoff

Built: production Supabase Auth passwords were rotated for the named librarian,
faculty, student enrollment, and administrator accounts using the administrator
API; no passwords were added to Git. Applied the missing production faculty
enum migration and corrected the existing faculty profile from student to
faculty. Created a plain `faculty` username for the requested faculty password;
the older `faculty.cs` account remains available. The provisioning script now
accepts faculty accounts. The login page
explains which username to use for each role.

Verified: all four accounts received a Supabase access token and a successful
session and role response from the live Archipelago API. Browser login for the
librarian account reached chat, and the librarian console appeared in the
library page. The browser was signed out afterward. Live code still sends a
librarian to chat first because this draft branch has not deployed.

Deferred: the production deploy remains gated by the repository-wide quality
failures and independent review. Actual OAuth provider sign-in needs a provider
client ID, secret and redirect configuration; this repair concerns the current
Supabase password login.

## 2026-10-11 — complete shelf and Pearson source links

Built: the hosted chat catalog now uses the same 91-entry Supabase shelf as the
library page (40 Pearson and 51 dataset entries), including each title's real
reader target. Book-stack and citation links preserve the requested page and
send Pearson titles through `/open/<book>?page=N`. Library deep links set the
requested Pearson page in the handoff control. The handoff opens Pearson in the
same tab after the separate sign-in step, avoiding a second Pearson reader tab.

Verified: 70 focused regression tests passed. A production-cache test client
returned 91 catalog entries, 40 Pearson entries, a page-7 reader hint, a
working handoff response, and a page-7 redirect. All 51 non-Pearson shelf
entries resolved to dataset files. In the real Pearson UI, changing a reader
URL from page 7 to page 9 left the displayed page at 7; Pearson's page box
must be used when it restores a saved position.

Deferred: AntDeploy production remains unchanged pending the repository's
five failing quality gates and independent review.

## 2026-10-11 — overall regression and release audit

Verified: the project virtual environment collected 1,506 unit tests. The
serial run reached 405 passes, one skip and five failures before the configured
stop: the old anonymous-API expectation, three graph contract cases answered
out of scope, and a test expecting a PDF absent from this checkout. Integration
tests reached 11 passes, then stopped because this checkout has no root
`okf_graph.json` export. The repository quality gate still fails five passes.
The draft release PR has no independent review and no CI run on its base
branch. The live AntDeploy catalog still reports 83 titles; the 91-title fix
has not deployed. Do not describe production as verified for this revision.
## 2026-10-11 — Vercel release handoff

Built: Vercel reads the graph and Pearson catalog from Hugging Face datasets and
keeps ingestion local. Supabase persists per-account quota, quiz completion, and
idle-session state. The landing and library pages use the requested CloudFront
videos; chat keeps its separate 3D scene and librarian clips. Librarian and
administrator accounts can open the hosted management panel and guarded links
to the workstation ingestion console and graph. Pearson links use one automatic
CAS redirect to the selected title and requested page hint.

Verified: 69 focused hosted tests passed; live Vercel returned 537 graph
concepts, 40 Pearson titles, and ingestion disabled. The library loaded 91
reader-backed titles, the librarian panel and graph, and a grounded chat reply.
The browser played both new videos. Pearson signed in and opened the chosen
book, but its reader restored page 9 when page 7 was requested.

Deferred: Pearson's reader must honor the initial page itself or expose an
approved integration for exact-page landing. The full repository unit suite
has 67 failures and 5 setup errors, mostly from old contracts and missing
local fixtures; the five existing quality-gate failures remain.
