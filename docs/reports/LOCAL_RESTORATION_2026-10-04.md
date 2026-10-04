# Local restoration handoff — 2026-10-04

## Release scope

**Local development and a review branch only. Not a production-readiness certification.**
No Antideploy deployment, configuration change, default-branch merge, model retraining, credential publication or Hugging Face publication was performed.

Base: `67cd809` on `session3-stable`.
Review branch: `restore/production-readiness-20261004`.

Start here: [Local setup and validation](../guides/LOCAL_LEARNING.md).

## Audit findings and corrections

| Finding | Change |
|---|---|
| Adaptive HTTP grading trusted browser-supplied keys/history | Shared server-issued question protocol with opaque session/question IDs and server-side grading |
| Answer keys returned before submission | Only one public question is returned; answer/explanation released after grading |
| Personalized edges could be generated as a target-centered star | Project actual REQUIRES/UNLOCKS edges from the bounded existing neighborhood |
| Insufficient distinction between correct guesses and confident knowledge | High/medium/low self-reported confidence, bounded micro-verification, explicit missing/fading/review states |
| Quiz flow obscured normal learning | Restore Normal/Personalized choice, preserve the existing presentation and assets |
| Local and standalone UI/backend implementations could drift | Canonical and standalone JS synchronized; both local API entrypoints use the shared diagnostic implementation |
| Local UI proxy would lose the new browser owner cookie | Forward only the validated learning cookie and preserve HttpOnly/no-store response headers |
| Greetings/physical holdings could fall through to unrelated graph or scope rejection | Conservative greeting handling and earlier deterministic shelf routing |
| Similar wording could collide across normal/personalized cache modes | Diagnostics, ingestion-analysis and identity/learning-state-bearing requests bypass the shared response cache |
| Shared graph citation query state could cross concurrent requests | Context-local query state |
| Streaming generator accessed Flask context after request teardown | Preserve request context for streaming |
| Provider drafting received overly broad prepared text | Bounded retrieved academic-summary allowlist and defensive redaction; no learner history or inventory |
| Automatic provider chain included another provider | Automatic XKIRO → NVIDIA only, one bounded failover; explicit legacy pin compatibility retained |
| No safe reviewed graphier publication path | Offline rights-manifest-filtered metadata export, explicit publish only, no change to Library_books |
| Default branch lacked a focused local regression gate | Dedicated non-deploying GitHub Actions workflow for the current default and restoration branches |

New responsibilities are separated into learning-state, adaptive-session, privacy, inspector, SQLite session-store, local bridge and proxy-cookie modules. This is incremental restoration, **not** a complete rewrite or modularization of the entire repository.

## Verification actually performed

- Clean baseline in a separate worktree, same Python environment and graph fixtures:
  **1,416 passed; 28 failed; 7 skipped; 7 errors.**
- Updated full unit + integration run:
  **1,448 passed; 24 failed; 7 skipped; 5 errors.**
- Comparing failing test identities against the clean baseline: no new failures in that run.
- Focused new CI suite: **80 passed**, including a fresh minimal environment containing only the standalone dependencies and explicit test dependencies.
- Local diagnostic/proxy compatibility suite after cookie-forwarding correction: **14 passed**.
- Real browser: normal graph, personalized choice, confidence/preference selection, **four server-graded questions**, completed personalized graph and optional inspector; **no JavaScript page errors** in the smoke run.
- Python compilation, JavaScript syntax, `git diff --check`, and Ruff checks on new Python modules passed. The repository-wide Ruff/type-check backlog is not certified clean.
- Local readiness: HTTP 200, **84 fixture concepts**, zero provisioned Pearson catalogue books, inference-only mode.
- Browser scripts and new regression tests are committed for repeatability.

The full suite is **not green**. Remaining failures/errors existed in the baseline and include missing Pearson catalogue/reader assets, absent source PDFs and trained-model directories, local MLE routing expectations, and Kuzu citation/evidence interface/fixture failures. Passing mock or fixture tests does not substitute for production source/model/provider validation.

Some baseline errors disappeared in the updated run; fixture/order-sensitive differences are reported as measured results, not attributed automatically to a particular code change.

## Assets

No visual asset pointer, video, font, 3D asset, stylesheet, landing-page layout or unrelated source content was intentionally replaced/deleted.

23 public LFS objects covering 100 paths were fetched and verified against their pointer SHA-256 hashes for local inspection. Fifteen other unique objects returned 404 from the public media endpoint. Full animation/font/graph-art validation remains blocked on recovery or authorized retrieval of those original objects. See the local guide; don't replace them with placeholders.

## Scope map against the two requested specifications

### Implemented and tested in this batch
- Existing six-contract behavior retained and targeted routing checks run.
- Greeting and shelf-routing corrections; truthful unknown physical holdings.
- Optional query inspector with actual exported-graph retrieval labels and bounded context.
- Optional Normal versus Personalized flow; current UI preserved.
- Server-authoritative, replay-resistant, browser-bound diagnostics.
- Three-hop coverage-first selection, early stopping and ten-question hard ceiling.
- Session preference influences selection among eligible nodes, not duplicate graphs.
- Confidence-calibrated mastery and unit-tested decay/micro-verification logic.
- Evidence-gated possible misconception prompts; no arbitrary misconception diagnosis.
- Genuine prerequisite edges, missing/fading states, node/edge explanation affordances.
- Session-only learning data and bounded SQLite retention.
- Minimal external inference context and private-request cache isolation.
- Explicit safe graphier export tooling and preserved old dataset.
- Reproducible localhost runner, browser smoke and focused CI.

### Partial / still requires work
- Preference weighting is a type-based selection heuristic, not fully validated mathematical/code/conceptual trajectories.
- Diagnostics use grounded definition-choice questions; rich Socratic follow-up generation and alternative skill assessment need expansion.
- Mastery decay is implemented/tested, but there is **no opt-in cross-day persisted profile**; default one-hour sessions deliberately don't retain long-term learner histories.
- Existing book stack, citations, OPAC links and ingestion modules are preserved, not comprehensively revalidated against complete live data.
- Gap-to-book/physical-copy matching and staff aggregate demand dashboards are not newly completed.
- Faculty/librarian restricted diagnostic inspector and a complete role-specific analytics UI are not added.
- The standalone inspector describes its actual exported graph; it does not falsely claim a live Kuzu query. A richer Kuzu execution-plan/debug surface remains future work.
- Legacy verify-mcq practice compatibility remains; it is not trusted for new adaptive mastery or authorization.
- Existing OCR/ODS/append/dedup ingestion implementations and tests were exercised where dependencies allowed, but a fresh real-document-to-production-graph pipeline was not completed.

### Blocked / not attempted
- Ingestion-model benchmark: expected local `lib-qwen` checkpoint absent; no fabricated precision/recall/F1 or latency claims, no training.
- Authorized Pearson extraction: no authorized source session/content provisioned.
- Complete corpus, holdings and missing original LFS object restoration.
- Real NVIDIA/XKIRO calls: no configured provider credentials; policy/failure behavior tested with fakes.
- `Prataykarali/graphier` population: export tooling ready, but source-rights review and HF credentials required; no publication performed.
- Antideploy: explicitly deferred by the latest request.

## Next release gate

Recover original data/assets, complete the remaining specification items, run real ingestion/model/provider evaluations, and make the entire regression suite green before merging or deploying. This branch is useful and locally runnable now, but it is not the complete two-specification production deliverable.