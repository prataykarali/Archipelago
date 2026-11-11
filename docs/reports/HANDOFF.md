Production ship complete on Sun Aug  9 09:01:58 AM IST 2026

## 2026-10-26 — research and academic pages, Indra ingestion

Built: refreshed the hosted Research and Academic graph pages with a topic-first
research journey, a collapsed paper archive, local readiness indicators, and
compact ingestion progress. The local queued research worker now checks rights,
fetches up to eight permitted PDFs per job, parses them with Indra, accepts only
page-linked SLM quotes, emits the complete research OKF field contract with
explicit unknown statuses, and attempts a per-job Hugging Face JSONL upload
when `HF_TOKEN` is configured. PDFs are not uploaded. A workstation dialog
still requires an affirmative approval before processing.

Verified: the installed `indra-ocr` 1.1.2 parsed a local PDF into page and
section text; `qwen3.5:0.8b` produced a quote-checked dataset from a sample
abstract. A local permitted-PDF probe returned a page-linked field and PDF
hash. All 23 focused tests passed, and the local worker heartbeat reported
`ready:qwen3.5:0.8b:ocr_ready`. Vercel deployment
`dpl_8UdTyecwxYextqkNiURK4ydiaLwQ` is READY and aliased at
`https://archipelago-archipelago-6383.vercel.app`. The production readiness
API succeeded and the served Research CSS matched the local file hash. Both
staff routes correctly redirected unauthenticated requests to app login.
Live Supabase queue processing and Hugging Face upload were not exercised
without a staff-approved ingestion session.

Next pair: verify one authorized queued job end to end on the workstation and
confirm the published JSONL path in the configured Hugging Face dataset. Check
the Indra model-weights license against deployment terms before broader use.

Follow-up on the same day: fixed the Research button's invalid queue request.
The browser sent 100 papers while the deployed Supabase function accepts 20–30;
the page now uses the server's 25-paper default and the route validates the
same range. Sparse Crossref samples had only 10–14 reported fields out of the
316-field contract, so the visual OKF now shows reported values and a coverage
count while the JSON audit retains explicit unknowns. Added source-document
links to Academic neighborhoods and styled Research topic-to-paper links like
the Academic graph. Generated an original research hero illustration and
checked the page visually at narrow and desktop widths. Focused tests passed.
Production deployment `dpl_DusSYV7eWU47DQutrxgo8Q1Ft59S` is READY on both
existing aliases; served Research JS, CSS, and hero image matched local hashes.

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

## 2026-10-20 — staff research graph page handoff

Built: replaced the old hosted librarian console at the end of the library page
with a staff Research button. The new `/research` page shows a searchable concept
graph, relationship filters, a concept list, and node details. Faculty can read
saved annotations; librarians and administrators can add or update summaries
and source links. The server checks roles on both the page and API. Annotations
persist in the existing Supabase project's RLS-enabled table, accessible through
the server credential only. Existing accounts were not changed.

Verified: all 18 hosted deployment tests passed; changed-file Ruff, JavaScript
syntax, and focused strict mypy passed. The repository quality gate passed six
of seven checks; repository-wide mypy timed out after two minutes. Supabase
Data API read returned 200 and table grants/RLS were checked. Vercel production
deployment `dpl_DPf7RfSFdVjAhyzkVnwqf3kGRnLC` is ready; the original
`archipelago-archipelago-6383.vercel.app` hostname serves the new asset and
reports 520 concepts and 40 Pearson books. Unauthenticated Research API access
returns 401, and direct `/research.html` returns 404.

Deferred: verify the page and save flow with actual staff sessions. The Research
Intelligence worker and paper pipeline remain behind their separate release
gate; this page currently explores the institutional concept graph.

## 2026-10-21 — campus sync and paper OKF handoff

Built: the hosted research intake now emits one versioned OKF JSON object per
paper, with all 16 requested parameter groups and per-field provenance. Metrics
are calculated only from source values; missing fields retain explicit statuses.
The research page can inspect and download those objects. The scheduled campus
sync visits relevant public IEM and UEM sitemap pages and retires a managed page
only after a complete crawl and a direct 404 or 410 confirmation. Retired pages
are excluded from research search and graph. Local PDF jobs now save matching
OKF objects; the optional local Ollama extractor verifies exact quotes and page
numbers before accepting model suggestions.

Verified: 49 focused research and hosted tests pass; changed-file Ruff passes.
The full quality gate still fails on the repository's strict mypy baseline.
The live daily route saved 50 papers each for two topics and 60 of 62 sitemap
pages. The remaining two IEM publication pages exceeded the former 1 MB limit;
the new 3 MB bound parses both locally and was deployed afterward. Live metrics
then reported 757 distinct papers and 62 campus pages. Production deployment
`dpl_8KJBnpKLrtnWNkoyqba4hhEwYaQ4` is ready. Public IEM/UEM pages are
reachable. IEMCRP returns 403 and IEM/UEM OPAC hosts timed out during direct
and tool-based probes, so private student and faculty personalization cannot
be verified or enabled from those sources.

Deferred: confirm the next scheduled production run handles all 62 pages;
connect a supported institutional API/session to the private portal and OPAC;
verify real staff session actions. The local PDF worker needs an always-on
runtime and database connection for production. The optional 0.8B SLM returned
malformed JSON in one real extraction probe; quote validation rejected it, so
SLM-derived fields remain unverified. Hosted metadata OKF does not claim
PDF-derived fields.

## 2026-10-23 — queued local GPU research handoff

Built: staff research questions on the Papers and Evidence pages now create
durable Supabase jobs. The database function enforces 20 to 30 papers, three
requests per hour and ten per day per user, one active job per user, and a
100-job global queue. A local systemd user service polls, claims, recovers stale
jobs, and reports a heartbeat. The workstation searches OpenAlex, Crossref,
arXiv, and Semantic Scholar, ranks on the CUDA embedding model, parses
rights-approved PDFs, and publishes 16-section OKF JSON plus research intake
records used by the hosted graph and normal chat. The page shows progress,
source cards, JSON, and an offline notice when heartbeats expire. Existing
staff accounts and private portal credentials were not changed.

Verified: one production faculty test job completed 25 of 25 papers, including
five verified full texts. The hosted store retrieved all 25 paper cards and a
16-section OKF object. Normal chat enrichment found three research sources.
Focused queue tests (3) and changed-file Ruff passed. Production Vercel
deployment `dpl_3e2xPQ4FSR6CxdZNv8YZrkfwxkrQ` is ready; public readiness
returns 200 and unauthenticated research API access returns 401. The full
quality gate still fails on its pre-existing strict mypy baseline (749 errors).

Deferred: an interactive authenticated staff-browser check; IEMCRP daily
personalization while Cloudflare human verification blocks automated login.
The queue worker runs after this user's systemd login and is offline when this
workstation is shut down. Semantic Scholar rate-limited the sample, while the
other three sources returned live papers.

## 2026-10-23 — research live inventory and metadata-only ingestion

Built: the local worker now ingests scholarly metadata and abstracts without
fetching paper PDFs. The library details activity panel, research topic
directory, overview count, filtered paper cards, and inventory chat answer read
the same live Supabase paper store. Chat lists every ingested topic and links
original papers from distinct recent topics. The research page shows an
ingestion-request dialog, and the local worker issues a desktop notification
when it claims a job. GPU device and peak allocation are recorded with each
job. Topic and paper panels refresh once a minute.

Verified: two existing faculty-profile jobs completed, each with 25 fetched
and 25 processed papers, zero full-text records, and no new local PDF files.
Topics: quantum error correction surface codes and climate change crop yield
adaptation. The RTX 2050 peaked at 100% utilization in 840 monitoring samples;
job summaries reported 692 MiB and 1062 MiB peak PyTorch allocations.
The live library displayed both topics and 870 saved paper records; the live
Librarian chat listed all 21 topics and linked one original paper from each
new topic. Paper cards and the topic directory were also checked before the
Librarian browser session expired. Captures are in `docs/reports/screenshots/`.
Focused tests: 24 passed; changed-file Ruff and JavaScript syntax checks passed.
Production deployment `dpl_2QA4pRvg3zsv7111GdMC9CHxs5Ra` is READY, and the
requested `archipelago-archipelago-6383.vercel.app` alias points to it.
The repository-wide quality gate still fails on 748 pre-existing strict mypy
errors; the new test's Ruff formatting finding was fixed locally.

Deferred: a fresh authenticated Faculty browser check, since the user chose
Librarian screenshots; IEMCRP remains outside this research-only finish. The
worker requires this laptop and user systemd session to remain online.

## 2026-10-23 — OKF 2.1 source metrics and abstract evidence

Built: the research worker now preserves OpenAlex, Crossref, and Semantic
Scholar IDs, keywords, domain, reference counts, annual citations, retraction
flags, publisher/license, and first-author OpenAlex metrics. OKF 2.1 records
value, status, extraction confidence, extractor version, timestamp, and
provenance for all 166 registered fields. Citation and relevance calculations
remain separate from author impact and paper quality. A local 0.8B model
proposes abstract facts; a literal-source check rejects unsupported values.
Paper cards expose DOI, citation and reference counts, first-author h-index,
and extracted method. The full-session view shows populated/unknown coverage.
No PDFs were fetched. A repeatable completed-job backfill script is at
`scripts/ops/backfill_research_okf.py`.

Verified: production research job `559fb296-b6ad-485d-8eb6-1e875d4d7af5`
finished 25/25 papers. After backfill, its 4,150 field observations include
759 source-reported, 227 calculated, 26 quote-checked, and 3,138 unknown.
Seven papers have abstract-supported dataset names; 18 have first-author
h-index; all 25 have reference counts. The local worker heartbeat is current.
24 focused tests, changed-file Ruff, and JavaScript syntax checks passed.
Vercel deployment `dpl_FuXLXw3nvFANvNvFo37NpD8ctQFr` is READY and both
production aliases point to it. The quality gate passes 6/7 checks; the
repository-wide strict mypy baseline still fails. The signed-in browser
session timed out, so final authenticated UI click-through remains unverified.

Deferred: full-text-derived fields (PDF pages, tables, figure evidence,
experimental details, efficiency, and reproducibility) require permitted paper
bytes; source APIs alone cannot verify them. G-index, m-index, and normalized
impact remain unknown without their required underlying measurements.

## 2026-10-23 — Two-page research UI and local GPU approval

Built: Research now uses one graph/discovery page and one job-progress page.
The paper graph reads only ingested paper records, begins at topic nodes, and
expands to linked papers whose full OKFs appear in a side panel. Library Details
links separately to the academic concept graph and the research graph. The
latest OKF and a source-linked paper list are loaded from the live research
store, with periodic refresh as ingestion saves new records. A staff topic
search previews up to 30 source-linked papers before an explicit local
ingestion action queues 25 papers. The worker uses a Zenity tick/cross
approval dialog before any GPU processing; decline marks the job failed.

Verified: 20 focused tests passed; live discovery returned 30 previews across
OpenAlex, Crossref, arXiv and Europe PMC. The existing store held 921 paper
records and 22 research topics, and the latest completed job held 25/25
papers. The newest paper OKF had 35 observed, 11 derived and 2 quote-checked
fields. The worker service restarted and remained active. Vercel production
readiness returned 537 full-corpus concepts. Repo quality gate passes 6/7;
strict mypy remains at its pre-existing baseline of 756 errors. A signed-in
production click-through remains unverified because the browser session is at
login. Paper preview and GPU-selected papers can differ because the worker
repeats discovery for the topic.
Production deployment: `dpl_DXRv5KT6XpEp6w5xfyz9gfJGgutu`; custom alias
`https://archipelago-archipelago-6383.vercel.app` points to that READY build.

## 2026-10-23 — Public production access

Changed Vercel project `archipelago-6383/archipelago` deployment protection
from all vercel.app URLs to preview-only. The production alias now serves HTTP
200 without Vercel authentication; `/api/readiness` also returns HTTP 200.
Research staff pages continue to redirect unauthenticated visitors to the
application's own `/login` page.

## 2026-10-23 — Safe local artifact cleanup

Removed `.mypy_cache/` (569,837,152 file bytes) and `.release-artifacts/`
(98,725,929 file bytes). Both were generated locally; no runtime or deploy
script references the release package directory. Added ignore rules for these
artifacts and the separate `.codex-release/` Git worktree, which was preserved.
The active local GPU worker, models, graph databases, PDFs, source videos, and
Vercel UI assets were preserved because they support ingestion or future builds.
Verified the UI asset sync build, 32 focused research tests, and unauthenticated
production home/readiness responses after cleanup. The local research worker
remained active.

## 2026-10-23 — Landing video clarity and graph UI

Restored the original centered landing composition after reviewing a foreground
video treatment. The girl animation remains a full-page background, shifted
right and rendered with a lighter overlay so the subject is visible behind
the copy. The library butterfly video now appears as a visible media panel,
and the previously hidden chat banner video is shown in a shallow uncropped
frame. The academic graph uses readable rounded cards in two columns around
the selected concept; a single click expands to a connected neighborhood.
The separate research graph uses topic/paper cards, an orderly grid, and zoom
controls while retaining its OKF side panel and source data.

Verified local screenshots of the landing, library, and academic graph; UI
asset sync, JavaScript syntax, 19 focused research tests, and production
home/readiness HTTP 200. Production research assets served HTTP 200 and
sampled video bytes served HTTP 206. Staff graph routes correctly redirect
unauthenticated requests to login. Vercel deployment
`dpl_9s5Qf6P9dDEnSXEBT1c72itSYQoy` is READY at
`https://archipelago-archipelago-6383.vercel.app/`.

## 2026-10-25 — Dual-ingestion dataset and local QLoRA benchmark

Built a 678-example, 113-paper local dataset from arXiv, OpenAlex, Crossref,
and Europe PMC, with paper-isolated train/validation/test splits and separate
academic OKF, research abstract, and research quote-span targets. Trained one
local QLoRA adapter for Qwen2.5-0.5B for two epochs without activating it in
services. The detailed source audit, run commands, scores, and limitations are
in `docs/reports/DUAL_INGEST_EVAL_2026_10_25.md`.

Held-out exact F1 was 0.609 academic, 0.330 research abstract, and 0.123
research quote spans. The academic operational probes scored 0.636 F1 but
failed all three negative passages. A real 26-page LoRA PDF parsed with valid
claim provenance but zero structured experiments or results; its full-text SLM
response was truncated and unparseable. The candidate therefore remains local
and should not be used for unattended ingestion. Next pair should review weak
labels, add academic negative and real PDF-page examples, address the
full-text output contract, and rerun held-out gates before activation.

## 2026-10-26 — Research atlas, Indra evidence, and Vercel release

Rebuilt Academic and Research graph views as full-viewport circular networks.
Clicking a node preserves a focused neighborhood while unrelated nodes and
edges fade. The Research path is now topic directory → up to 30 paper circles
and titles → a separate source-backed paper OKF dashboard. The page hides
legacy metadata-only research records by displaying records marked
`ingestion_pipeline=local_indra_v3`; those historical rows remain in storage.
Source-backed citation edges appear only when both cited and citing papers are
saved. Expanded local SLM extraction to additional OKF contract groups, retained
exact quote and PDF-page validation, raised the per-job permitted PDF cap to 30,
and made Hugging Face upload failure a partial job rather than a success.
The desktop approval dialog displays actual RAM, disk, and Indra readiness.

Live discovery returned 25 candidates for each mandatory topic: Optical
Character Recognition, Pedestrian Detection, Bengali Speech Recognition, Skin
Cancer Detection, and Fake News Detection. An arXiv OCR paper completed a real
PDF fetch → Indra parse (4 pages) → local SLM quote-checked field extraction.
The worker heartbeat reports local model and OCR ready; the private HF dataset
is reachable. Thirty focused tests pass; changed Python files pass Ruff.
The repository-wide quality gate retains its pre-existing strict typing errors.
Visual previews verified both graphs and the paper dashboard. Production Vercel
deployment `dpl_BbCcWn9LQaRoThmsWnR4J3ry61a2` is Ready with both production
aliases attached; served asset hashes match the workspace files.

Outstanding: the browser's staff session is expired. No five-topic Vercel job
has been submitted, no tick/cross approval was observed from a Vercel request,
and no new OKF/HF job result is claimed. The workstation owner must sign in as
staff and approve each local popup; then inspect per-job OCR, OKF, HF, and graph
results. Do not describe the five end-to-end runs as complete until this is done.

## 2026-10-27 — Five live research jobs and evidence audit

Built: the Vercel queue admits at most 100 globally active jobs, and the local
worker keeps processing after a staff browser session expires. It requires a
fresh desktop ✓/✕ decision for each job. Research and Academic graphs now use
full-screen circular nodes; selecting one focuses its adjacent links and dims
unrelated nodes. Research navigation is topic graph → paper graph → aggregate
topic dossier → individual paper OKF dashboard. A collapsed paper browser
replaces the long open sidebar list, and each paper dashboard exposes every
validated extraction in a source-linked evidence log. Unsupported fields stay
explicit in the full JSON contract while the dashboard shows reported values.

Verified: all five mandatory topics were submitted through the live Vercel
page and reached the local approval popup, Indra OCR, quote-checked extraction,
Supabase records, and Hugging Face JSONL publication. After evidence cleanup:
Optical Character Recognition has 24 active/HF rows and 1 PDF fact;
Pedestrian Detection 25 rows and 6 PDF facts; Bengali Speech Recognition 25
rows and 9 PDF facts; Skin Cancer Detection 25 rows and 3 PDF facts; Fake News
Detection 25 rows and 12 PDF facts. The four latter topics also have accepted
local SLM facts. Every HF paper key matches the active database paper key, and
all stored facts pass the current quote, field-role, and PDF hash/page guard.
Source gaps are reported as metadata-only or full-text-without-supported-field,
not filled with invented metrics. Semantic Scholar returned HTTP 429 on some
runs, so those jobs truthfully remain partial even though their rows published.

The previous OCR run selected too many generic title matches and only one
source-supported PDF fact. Discovery now reserves up to six sufficiently
relevant, legally readable PDFs; a fresh read-only discovery selected six for
Optical Character Recognition. A live rerun still requires staff sign-in and
its own desktop approval before this improvement can be called end-to-end
verified. The worker service is enabled and reports
`ready:qwen3.5:0.8b:ocr_ready` after restart. Production deployment
`dpl_69GN5bJmCrsxkDbDLWKsJfukhuLy` is Ready; Vercel readiness returned
HTTP 200. Forty-nine focused tests, changed-file Ruff checks, formatting, and
JavaScript syntax checks pass. The repository-wide quality gate still has its
pre-existing strict typing and file-size baseline failures; see
`/tmp/archipelago-quality-gate-20261027.log`.

## 2026-11-11 — S1 intelligent replies and multi-anchor reasoning

Built: main chat now routes exact-evidence paper, library, multi-concept, and
research-topic questions even when the semantic scope provider is unavailable.
Multi-concept replies resolve every named anchor, rank one supporting passage
per concept, search bounded typed paths, and report missing nodes. Hosted chat
now cites distinct supporting passages, distinguishes stored paths from
document inference, reports conservative opposing-paper claims, and omits
learning graphs and quizzes from bibliographic and research replies. Concept
learning retains its existing graph payload. Bibliometric requests hand off to
the authorized research workspace without inventing metrics. Dated research
replies state the dates of indexed examples and avoid claiming they are the
latest studies.

Verified: 169 focused unit and integration tests across main and hosted chat pass;
changed Python files pass Ruff. Manual local API probes returned paper, library,
multi-concept, research, and multi-turn replies with the expected payloads.

Deferred: the repository-wide quality gate still fails on existing lint,
strict-type, and 400-line baseline violations in unrelated files. The current
worktree is on `feature/s2a-academic-coverage-repair` with substantial prior
uncommitted changes; this S1 work has not been rebased onto `session3-stable`.

## S2 — Evidence, Citations & Library Inventory (2026-11-11)

Built a canonical reply evidence record and clickable citation rendering with
verified local PDF pages, DOI targets for verified scholarly records, and a
deduplicated Sources section. Removed demo citation overlays and demo passage
fallbacks. Replaced hardcoded local and hosted holdings claims with timestamped
Koha export snapshots or explicit unverified-stock messages. The hosted
composition code was split to keep modules below 500 lines. Full findings and
rendered examples: `docs/reports/S2_SOURCE_INTEGRITY.md`.

Verified: 131 focused unit/integration tests pass, plus 4 library integration
tests in isolation. Changed S2 files pass focused Ruff and diff checks.

Deferred: the supplied Koha export does not verify sample textbook holdings;
live Koha circulation and OPAC sync remain separate work. This task remains
on the pre-existing dirty `feature/s2a-academic-coverage-repair` checkout
rather than `session3-stable`.

## S3 — Complete Knowledge Graph Recovery & Exploration (2026-11-11)

Built: Audited the persisted Kùzu graph, three byte-identical concept exports,
main and hosted APIs, and browser render paths. Added read-only paginated
access to all 6,186 persisted nodes and 20,160 typed edges through the main
staff graph service, plus a mobile-friendly global browser. The hosted graph
can page all 610 exported concepts while retaining its focused and learning
views. Restored source-bearing concept nodes in the main API. Removed a
synthetic hosted source edge while retaining source links in node details.

Verified: 30 focused graph and personalized learning tests pass. Desktop and
mobile browser screenshots and the full reconciliation are in
`docs/reports/S3_GRAPH_RECONCILIATION.md`.

Deferred: The hosted JSON export still contains only concepts, so deploying
the Kùzu-backed global service is necessary to expose non-concept entities.
The remote deployed artifact was not inspected. Two pre-existing research page
tests fail outside the graph scope. No graph persistence or OPAC sync changed.

## 2026-11-11 — S4 academic daily cycle and D2L staging

Built: the 09:00 Asia/Kolkata daily cycle, durable source evidence across external providers, a verified D2L chapter candidate, strict contents-only separation, CPU Ollama option, and the dashboard evidence view. DOAB XOAI parsing populated licenses and ISBNs. The approved D2L job is staged with 7 added concepts and 21 edges; all 610 prior concepts and 1,988 edges remain intact. A controlled rollback copy restored the exact current graph SHA.

Verified: 35 focused S4 tests passed; changed-module Ruff lint passed; systemd units verified; two isolated daily cycles ended with zero jobs and unchanged records on the repeat. The graph's actual pre-staging SHA differs from the plan while counts match. See `docs/reports/S4_ACADEMIC_AUTOMATION.md` for evidence and limits.

Next pair: obtain independent librarian approval for review-ready job `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe`; then publish, capture post-swap graph counts and hashes, verify chat citations and idempotency, and retain a browser screenshot. Keep timers disabled until explicitly enabled by the operator. Do not touch S5 research files or load another Ollama model.
