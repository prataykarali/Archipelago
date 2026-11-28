# D14.9 regression triage — 2026-11-28

The supplied closure summary reports baseline `d9f489a8` at 2,392 passed / 190 failed / 43 errors / 18 skipped and candidate `6f1fa778` at 2,408 passed / 189 failed / 41 errors / 18 skipped. It reports seven resolved pre-existing failures, zero newly introduced unresolved regressions, 105 D14 tests passing, and 52 integration passes with seven pre-existing failures. These full suites were not rerun in this final task.

| Issue | Observed status | Consequence |
|---|---|---|
| Hosted V2 retrieval with V3 suggestions | Reproduced on isolated deployment | Blocks author retest. |
| Protected browser login | Vercel `You Need Access` page | Blocks authenticated application verification. |
| Research Supabase administration | Vercel key masked; connected Supabase account lists another project | Blocks safe Storage backup, V3 upload and activation. |
| Source rights | Generic OA gate in register, no source-specific redistribution proof | Blocks upload of unfiltered V3. |
| Pilot readiness | Local Kuzu DB has zero tables; `Concept` binder error reproduced | Local pilot gate remains failed; deployed JSON graph is separate. |
| Dense model identity | Runtime profile BGE small, experimental profile Snowflake, manifest Snowflake v1.5, closure claims MiniLM | Baseline unresolved pending author selection. |
| Protected inventory | 44/45 matching; D11-A worksheet absent | Integrity gate incomplete. |
| D14 graph packet | 120-row packet absent | Human review handoff incomplete. |
| Eight-query challenge | No run artifact located; exposure status unknown | Do not call unseen or completed. |

The authorized 46-query development regression is documented only by the supplied prior report (46/46 HTTP 200, 33/36 diagnostic citation responses, 3/6 paraphrase citation responses, 2/2 out-of-coverage). No new 46-query run was made. The reserved eight-query challenge has no verifiable completion record in this checkout and was not run because its query set was not located. No held-out benchmark contents were opened.
