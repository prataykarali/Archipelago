# S4 academic automation acceptance, 2026-11-11

Branch: `codex/s4-academic-automation`. Starting remote commit: `ac56b212877ea3b82aef005ac93b8d269a30802a`. The final pushed commit is reported in the task handoff because a commit cannot contain its own SHA.

## Live source evidence

The ledger contains 178 catalog records after the five live OPAC detail checks. Every source match is retained in `source_evidence` with the OPAC URL, provider URL, match method, license, content status, eligibility, reason, and retrieval time. The dashboard API and UI expose these rows. No restricted or contents-only text is queued for concept extraction.

| Catalog item | Observed evidence | Extraction |
| --- | --- | --- |
| `opac_live:4150`, Dive into Deep Learning | Open Library `OL48193224M` metadata; official D2L chapter, CC-BY-SA-4.0 | Eligible; job `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` |
| `opac_live:4021`, Probabilistic Machine Learning | Open Library `OL34192800M`; author preprint CC-BY-NC-ND-4.0 | Blocked |
| `opac_live:4151`, How to Think about Algorithms | Open Library `OL48686803M` metadata | Blocked |
| `opac_live:588`, Operating System Concepts | No verified external full text | Blocked |
| `opac_live:576`, OPERATING SYSTEMS | No ISBN or verified external match | Blocked |
| OAPEN index proof, Scalable Data Management for Future Hardware, ISBN `9783031740961` | OAI ID `oai:library.oapen.org:20.500.12657/98554`, CC-BY-4.0, 11,189,926-byte PDF with MD5 | Eligible in index only; not claimed as a UEMK match |
| OAPEN restricted index proof, Liberalism against Liberalism, ISBN `9780203016886` | CC-BY-NC-ND rights | Blocked; not claimed as a UEMK match |

A fresh five-page DOAB harvest indexed 403 books; 135 have a parsed permissive license and 646 ISBN links were populated. The `name="*"` XOAI parser fix is retained. OAPEN and DOAB index evidence is resolved by exact ISBN plus verified title overlap. Open Library contributes metadata and contents, Crossref contributes DOI metadata, and Europe PMC may contribute licensed JATS body text when its OA and license checks pass. Only the D2L chapter and verified Europe PMC body text can be queued from these text providers. OAPEN PDF download additionally checks per-file license, size, and MD5.

| License | Decision |
| --- | --- |
| CC-BY-4.0, CC-BY-SA-4.0, CC-BY-3.0, CC0-1.0 | Eligible only with verified body text and provider checks |
| CC-BY-NC-ND-4.0, commercial copyright, unknown per-file rights | No extraction |

## Daily cycle and consent

The daily command reconciles Koha, Pearson, OPAC arrivals, and institutional repository metadata; advances the nine-query live OPAC cursor; and harvests five pages each from DOAB and OAPEN. It then runs at most one pending consent-gated job. An empty queue records `daily_cycle_noop` and returns without probing GPU, starting Ollama, or opening a dialog. The timer is configured for `09:00:00 Asia/Kolkata`, and both systemd units passed `systemd-analyze verify`. The timers remain disabled.

Two controlled `daily-cycle --skip-live-opac` runs used an isolated temporary ledger. The first found 109 Koha and 40 Pearson records, with zero eligible jobs. The second reported 109 and 40 unchanged, zero queued jobs, and `status=noop`. Both exited 0 without a popup or GPU job.

A repeat live `discover --query "Dive into Deep Learning" --max-records 1` returned `unchanged: 1` and `unchanged_evidence_retained`; it did not hunt or queue the record again.

The live GPU snapshot before extraction reported available=true, 4096 MiB total, 14 MiB used, zero loaded Ollama models, and zero compute PIDs. The local operator selected `approve_class` in the five-choice desktop dialog, creating a revocable 24-hour `trusted_academic_open_content` grant. Controlled tests cover defer, cancel, model conflict, shared lease, and CPU `num_gpu=0`; these branches were not exercised against the production job. The worker did not load a second model.

## D2L staging trace

OPAC 4150 matched the official D2L repository by ISBN and title. The source license file declared CC-BY-SA-4.0. The fetched `chapter_linear-regression/linear-regression.md` was bounded, stripped of code tabs, hashed into `data/academic_candidates/`, and recorded with its official chapter URL in a `.source.json` sidecar. After desktop consent, `lib-qwen:latest` extracted 12 source-linked concept rows into the isolated job directory. The cleaned rows include Linear Regression, Loss Function, Minibatch Stochastic Gradient Descent, and Normal Distribution, each with a summary and section title. Markdown has no printed page numbers, so rows correctly carry page number 0 and must be cited by chapter URL and section, not a fabricated page.

Staging contains 617 concepts, 80 documents, 826 chunks, and 2,009 typed edges. Validation reports 7 added concepts, 21 added edges, zero missing prior concepts, zero missing prior edges, and `valid=true`. A cleanup removed two unrelated scratch rows from `results.json` and rebuilt the staged graph from the 12 source-linked rows; `Document.title` is now Dive into Deep Learning. The canonical graph is still untouched.

| Canonical graph | Before staging | Current |
| --- | ---: | ---: |
| SHA-256 | `3ee305138a4a3661b505c30a1f782baeddd7e0779eef634720392821c0eb46ed` | same |
| Concepts / documents / chunks / typed edges | 610 / 79 / 808 / 1,988 | same |

The plan quoted `df3943eeebd6a541ba83dde0cb7f0ed606a46deb40aecc9ff3db4d7888923cc8`, but the actual canonical file was already `3ee305...` when checked before the GPU job. Its node and edge counts still matched the plan. A controlled rollback test on a byte-for-byte copy restored the exact `3ee305...` SHA after simulated corruption. The existing publication failure tests also passed.

## Verification and outstanding gates

- **PASS:** Five live OPAC examples, source evidence, DOAB/OAPEN index proofs, strict metadata/body separation, consent-gated GPU staging, preservation validation, rollback copy, and 09:00 timer syntax.
- **PASS:** Focused S4 suite: 35 tests passed. Changed-module Ruff lint passed. The dashboard API returned HTTP 200 with seven evidence rows, one review-ready job, and one grant; Chromium screenshot: `artifacts/validation/s4-academic/dashboard-full-review-ready.png`.
- **PARTIAL:** Repository-wide quality gate remains red from unrelated existing Ruff and strict typing failures. New S4 modules are below the gate's 400-line file limit. Full strict mypy is red on hundreds of existing errors.
- **BLOCKED pending independent human review:** The job is `review_ready`; production publication, after-graph snapshot, idempotent post-publication ingestion, and D2L chat freshness have not happened. `AGENTS.md` requires a different-role human approval as pass 5. The librarian must review the staged results and approve publication. No reviewer identity has been fabricated.
- **PARTIAL:** Chat end-to-end answers and chat screenshots have not yet been captured against the unpublished D2L graph. The running staff graph API requires a Supabase token; a separate localhost test server was used only for the dashboard screenshot.
