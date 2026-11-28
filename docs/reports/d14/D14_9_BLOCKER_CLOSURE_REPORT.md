# D14.9 final coder closure — 2026-11-28

**Verdict: REVISE.** This file reconstructs the requested D14.9 handover in `sigir/d14-recovery`; no prior `D14_9_*` report files were present at candidate commit `6f1fa77864fa006c1519e465e9e7faf6f6836b42`.

## Previously reported, not repeated

B1 citation provenance, B2 alias and out-of-coverage routing, B3 DPO explanation, B4 vLLM/paging relation, B5 12-domain suggestions, C1 five UI mirrors, C3 neural dense capability, C4 source-rights inventory, C5 local guardrails, and C6 institutional/OA boundary were reported complete by the supplied closure summary. Its 2,408-pass test result, 46-query diagnostics, and 105 D14 tests are historical reports, not rerun or independent validation here. The graph and corpus candidates were not modified.

## Current independent observations

* The protected isolated deployment's `/api/readiness`, queried with the authorized Vercel CLI, loads `corpus_v2_d10_3025`: 3,025 passages, 43 documents, SHA-256 `93f6db39cb10d03beeb41c48469d138be27b62ed90aa59d20dd4c5107fbb2e52` from Supabase Storage. The same deployment's suggestions claim `corpus_v3_d14`. This is a real hosted parity failure.
* Local V3 JSONL is 11,768 passages / 68 documents according to its manifest; its bytes hash to `6fe7f4d8cc27a91ebbf2e86c55267a661adf36f81425ed0cb7ab17c5f7ec4ffc`. Local V2 graph bytes hash to `4f6861e6131cbccd7f60fa811492b20cba77fd1012acc7aecb9607f63c5c35ac`; manifest records 631 concepts and 1,943 edges.
* Vercel project binding is `archipelago-sigir` (`prj_BjRCpNfUItbG8BO26CIQbPhP1oi9`), scope `sigir1`. Its production-scoped `SUPABASE_URL` is `https://edokbtmhztkhndmxetpy.supabase.co`. The Vercel CLI masks the `SUPABASE_SECRET_KEY` as `[SENSITIVE]` on export. The connected Supabase account lists only unrelated project `tvzntaafqzixvnavygai`. Local usable Supabase keys belong to `spllaastejfwclllfndp`, which was not accessed. No research database or Storage write was made.
* An in-app browser reached Vercel's `You Need Access` page for the isolated URL. The logged-in browser account requires a team owner to approve access. Therefore no authenticated application browser trace was produced. CLI-protected GETs do not constitute browser verification. CLI-protected `/api/catalog/all` and unauthenticated `POST /api/chat` both returned `unauthorized` / `missing_session`.
* The source license register's 70 eligible rows all use the same generic `verified_open_access` gate reason and generic redistribution note. This does not demonstrate source-specific rights to ingest, store, display, or redistribute passages. V3 activation requires source-specific license evidence or a rights-filtered, newly versioned corpus.
* The 45-item protected inventory has 44 matching local checksums. `outputs/d11-a-author-diagnostic/D11_A_AUTHOR_DIAGNOSTIC_WORKSHEET.xlsx` is missing from this worktree. All 731 historical `reviewer_assessment` objects remain blank. All 1,943 graph edges remain `PENDING_REVIEW`. The stated blank 120-row D14 graph packet was not found and therefore could not be checked.
* `scripts/run_gold_eval.py` reproduces `Binder exception: Table Concept does not exist`; the worktree's `okf_graph.db` has zero tables. This is an isolated local Kuzu setup defect. Hosted readiness uses the versioned JSON graph and reports 631 concepts, so the local pilot gate result cannot be used to infer hosted failure or success.

## B/C status

| ID | Final coder status |
|---|---|
| B1–B5 | Code changes reported completed at candidate SHA; hosted scientific verification pending. |
| B6 | Unresolved: authenticated hosted behavior cannot be verified. The supplied summary did not define B6 more narrowly. |
| C1 | Five UI mirrors reportedly synchronized; not repeated. |
| C2 | Unresolved hosted corpus synchronization: V2 is loaded while V3 is advertised. |
| C3 | Genuine neural path exists, but model identity and baseline selection conflict; see D15 report. |
| C4 | Register exists; source-specific rights evidence remains insufficient for V3 activation. |
| C5 | Local out-of-coverage checks reported passed; hosted authenticated check pending. |
| C6 | Local boundary repair reported; hosted authenticated check pending. |

## Recoverable staging procedure, not executed

Before any write: obtain authorized access to research project `edokbtmhztkhndmxetpy`; verify project and Storage bucket identity; export current V2 object and checksum; record the exact deployment and environment bindings; confirm rights for each included document; upload only a new versioned object; verify its raw JSONL SHA, passage IDs, counts, document IDs, and manifest; create a new isolated deployment with matching Storage object and expected SHA; exercise authenticated retrieval and reader navigation. Roll back by restoring the recorded prior V2 environment bindings and isolated deployment. Never overwrite the V2 object or change either protected alias.

## Remaining gate

Owner access to the research Supabase project and Vercel-protected browser deployment, source-specific rights evidence, the missing 120-row packet and protected worksheet, and authenticated hosted tests are required. The independent leakage audit remains pending under a genuinely separate reviewer. No held-out 50-query evaluation, manuscript edit, D15 run, production change, or alias promotion occurred.
