# ARCHIPELAGO — FINAL PRODUCTION FEATURE ACCEPTANCE AUDIT

**Date:** 2026-11-15  
**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration` (audited against HEAD `b31a4893921b21a29b0ecb15219967511c50f830`)  
**Main Production:** `https://archipelago-blond.vercel.app/` (Deployment `GEefuqwzNGpgwNUMkXdTAdYKwRdY`, mode `inference-only`, `concepts: 610`, `pearson_books: 40`, `graph_version: 9818ac0e8fd3`)  
**Librarian Production:** `https://archipelago-librarian.vercel.app/` (Deployment `FSHZs5GHDzJ5TxzGzMPmSj8FqCyE`, workspace `shinaura` / `Aura`)  
**Audit Scope:** Independent functional, academic correctness, security/RBAC, GPU ingestion, and S4 governance acceptance audit. No production behavior, graph data, or S4 publication state was modified during this audit.

---

## 1. Executive Summary & Final Verdict

- **Functional Availability (Infrastructure & Routes):** All core S1–S6 UI pages, authentication flows, graph APIs, research intelligence runs/exports, S4 review inspection, and librarian dashboards are live and reachable across both Vercel deployments with zero browser `pageerror`s and zero horizontal overflow at `1440×960` and `390×844`.
- **Academic Answer Correctness (Separated from Functional Availability):**
  - **Prior Curated CS/AI Benchmarks:** `128`-question domain benchmark (`112 PASS / 9 PARTIAL / 7 FAIL`, `p50 = 9.748s`, `p95 = 16.513s`); `20`-question hosted holdout + `5` prior partials (`21 PASS / 4 PARTIAL / 0 FAIL`, `p50 = 7.182s`, `p95 = 10.324s`); `30`-question local holdout (`29 PASS / 1 PARTIAL`).
  - **Fresh 6-Question Weak-Domain / Edge-Case Live Sample (this audit):** `1 PASS`, `2 PARTIAL`, `3 FAIL` (`1.0s–4.5s`). Off-syllabus guardrail (`W5_UNSUPPORTED_SCOPE`) passed (`0.609s`), but unindexed/weak CS domains showed real retrieval/synthesis gaps (e.g., `"address translation"` matched NLP `Translation` in `Brown2020_GPT3.pdf`; `W3_NET_CONGESTION` returned the prompt instruction template without LLM completion; `W6_FOLLOWUP_PAGETABLE` attached irrelevant medical segmentation papers).
- **Security & RBAC:** Authenticated role resolution (`/api/auth/me`), `HttpOnly; Secure; SameSite=Lax` cookie issuance (`/api/auth/session`), 5-role RBAC enforcement (`401` anonymous, `403` student/faculty on staff/S4/annotation routes), cross-user research run/monitor isolation (`librarian2` saw `0` runs/monitors owned by `librarian`), and student 10-query/hour quota status (`10/10` remaining) all passed.
- **S4 Governance & GPU Ingestion:** Both `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` (`opac_live:4150`) and `337d88fe-70df-49f2-af98-4f3413895951` (`arxiv:2307.09702`, GPU-ingested) remain safely in `status='review_ready'` with `published_version=None` (`okf_graph.db` untouched at `102,637,568` bytes). Local RTX 2050 was idle (`14 MiB / 4096 MiB` used; `ollama ps` empty).

### Final Release Verdict: **CONDITIONALLY RELEASED**
Core S1–S6 platform, RBAC, UI, and offline GPU-staging infrastructure are production-operational, but unqualified `FULLY ACCEPTED` is withheld due to four verified conditions:
1. **Weak-domain `/api/chat` accuracy gaps** observed in the fresh 6-question live sample (`1 PASS / 2 PARTIAL / 3 FAIL`).
2. **S4 Publication Governance Pending:** Neither `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` nor `337d88fe-70df-49f2-af98-4f3413895951` has independent second-reviewer publication sign-off.
3. **External Live OPAC Upstream Flakiness:** `/api/library/opac/live?q=algorithms` returned `503 opac_unavailable` (`14.229s`), though `/api/library/koha` snapshot fallback returned `200`.
4. **Disabled/Unimplemented Hosted Ingestion & Snapshot Endpoints:** `/api/ingest` (`upload_api_enabled: false`), `/api/ingest/index` (`501 not_implemented`), and `/api/scholarly/snapshot` (`503` for librarian) are not active in hosted inference-only production.

---

## 2. Complete 28-Feature Production Acceptance Matrix

| Feature | Implemented | Production-tested | Actual result | Verdict | Evidence |
| --- | --- | --- | --- | --- | --- |
| 1. Student Academic Chat & XKIRO Synthesis | Yes | Yes (`POST /api/chat`, `/chat`) | `HTTP 200` NDJSON stream; `/chat` UI renders (`has_input=1`, `0` console/page errors); curated holdout `21/25 PASS`, fresh weak-domain sample `1/6 PASS` | **PASS (Functional) / PARTIAL (Weak-Domain Accuracy)** | `audit_live_part3.json`, `chat_full_sample.json`, `hosted_prod_holdout_results.json` |
| 2. Academic Domain & Capability Discovery | Yes | Yes (`CAPABILITY_INQUIRY` route in holdout `H020`) | Deterministic capability summary (`0.004s` local, `PASS` in hosted holdout) | **PASS** | `fresh_holdout_benchmark.json` (`H020`), `hosted_prod_holdout_results.json` |
| 3. Concept Explanations & Mathematical Reasoning | Yes | Yes (`W1`–`W4`, curated `128`-Q benchmark) | Strong on indexed ML/Transformer topics (`112/128 PASS`); fails/abstains on unindexed OS/Networks/Algo (`W1`–`W3`) | **PARTIAL** | `domain_benchmark_results.json`, `chat_full_sample.json` |
| 4. Multi-Concept, Multi-Hop & Cross-Domain Q&A | Yes | Yes (`W4_MULTIHOP_KV_FLASH`, `W6_FOLLOWUP_PAGETABLE`) | `W4` returned `Transformer` only (missed KV Cache/FlashAttention); `W6` mismatched `Address Translation` × NLP `Translation` | **PARTIAL** | `chat_full_sample.json` |
| 5. Conversation Context & Follow-Up Questions | Yes | Yes (`W6_FOLLOWUP_PAGETABLE` with `history`) | `HTTP 200` (`2.953s`), consumed `history`, but produced off-topic cross-domain matrix + medical citations | **PARTIAL** | `chat_full_sample.json` |
| 6. Graph-Grounded Academic Answers | Yes | Yes (`GRAPH_SYNTHESIS` route + `anchor_concept` payload) | Returns `anchor_concept`, `prerequisites`, `unlocks`, `render_graph` metadata | **PASS (Indexed) / PARTIAL (Unindexed)** | `chat_full_sample.json`, `hosted_prod_holdout_results.json` |
| 7. Citations, PDFs & Textbook Page Reader (`/read`, `/open/<book_id>`) | Yes | Yes (`/api/catalog/all`, `papers/...` links in chat) | `/api/catalog/all` `HTTP 200` (`total: 91`, `0.858s`); chat citations emit `/read?doc=...&page=...` links | **PASS** | `audit_live_part2.json`, `chat_full_sample.json` |
| 8. Off-Syllabus / Guardrail Interception | Yes | Yes (`W5_UNSUPPORTED_SCOPE`: C4 photosynthesis) | `GUARDRAIL_INTERCEPT` (`0.609s`), cleanly refused out-of-scope biology query | **PASS** | `chat_full_sample.json` (`W5_UNSUPPORTED_SCOPE`) |
| 9. Interactive Knowledge Graph Atlas (`/graph`, `/academic/graph`) | Yes | Yes (`/api/graph/hubs`, `/api/graph/subgraph`, `/api/graph/page`, Playwright) | `hubs` `200` (`12` nodes, `1.58s`), `subgraph?q=Transformer` `200` (`2.075s`), `page` `200` (`10` nodes), Librarian `/academic/graph` dark Graphify UI `0` overflow | **PASS** | `audit_live_part2.json`, `audit_live_part3.json`, `audit_browser.py` |
| 10. Full Research Graph Export (`/api/research/graph/full`) | Yes | Yes (student `403`, librarian `200`) | Staff-gated (`student` -> `403`, `librarian` -> `200`, `1.112s`) | **PASS** | `audit_live_part2.json`, `audit_live_part3.json` |
| 11. Graph Node Annotations (`/api/research/graph/annotation`) | Yes | Yes (5-role RBAC check) | `anon` `401`, `student` `403`, `faculty` `403`, `librarian`/`admin` pass RBAC (`404` on invalid concept) | **PASS** | `audit_live_results.json` |
| 12. Learning Roadmap Generator (`/api/roadmap`) | Yes | Yes (`GET /api/roadmap?topic=Transformer`) | `HTTP 200` (`0.453s`), returned `stages` (`1`), `hops`, `target_id` | **PASS** | `audit_live_part2.json` |
| 13. Practice Quiz Generator (`/api/quiz`) | Yes | Yes (`GET /api/quiz?topic=Transformer`) | `HTTP 200` (`0.408s`), returned `quiz` payload | **PASS** | `audit_live_part2.json` |
| 14. Diagnostic MCQs (`/api/chat/diagnostic-mcqs`) | Yes | Yes (`GET /api/chat/diagnostic-mcqs?concept=Transformer`) | `HTTP 200` (`1.141s`), returned `mcqs`, `prereq_chain`, `initial_question` | **PASS** | `audit_live_part2.json` |
| 15. Adaptive Personalized Learning DAG (`/api/chat/adaptive-step`) | Yes | Yes (`POST /api/chat/adaptive-step`) | `HTTP 200` (`0.679s`), returned `personalized_graph`, `next_concept`, `stride_action` | **PASS** | `audit_live_part2.json` |
| 16. Student Chat Quota & Rate Limiting (`/api/chat/quota`) | Yes | Yes (`student` vs `librarian`) | `student` -> `200` (`remaining: 10, limit: 10`); `librarian` -> `200` (`unrestricted: true`) | **PASS** | `audit_live_results.json` |
| 17. Institutional Library Portal & Koha Snapshot (`/library`, `/api/library/koha`, `/api/library/data`) | Yes | Yes (HTTP + Playwright) | `/library` `200` (`0` overflow), `/api/library/koha` `200` (`2.114s`), `/api/library/data` `200` (`1.802s`) | **PASS** | `audit_live_results.json`, `audit_browser.py` |
| 18. Live OPAC Proxy (`/api/library/opac/live`) | Yes | Yes (`GET /api/library/opac/live?q=algorithms` on Librarian host) | Returned `503 opac_unavailable` after `14.229s` (upstream `uemk-opac.l2c2.co.in` unreachable/timed out from Vercel at audit time) | **PARTIAL (Upstream Unavailable)** | `audit_live_part2.json` |
| 19. Librarian Space CRUD (`/librarian`, `/api/librarian/<record_type>`) | Yes | Yes (5-role RBAC + Playwright `/librarian`) | `/librarian` `200` (`0` overflow); `GET /api/librarian/catalog` `401` anon / `403` student / `200` faculty,librarian,admin; `POST` `403` student,faculty | **PASS** | `audit_live_part2.json`, `audit_browser.py` |
| 20. Library Analytics Dashboard (`/analytics`, `/api/analytics/summary`, `/sources`) | Yes | Yes (HTTP + Playwright) | `/analytics` `200` (`0` overflow), `summary` `200` (`4.126s`), `sources` `200` (`3.714s`) | **PASS** | `audit_live_results.json`, `audit_browser.py` |
| 21. Research Atlas & Intelligence Runs (`/research`, `/research/topics`, `/api/research/intelligence/runs`) | Yes | Yes (HTTP + Playwright + cross-user check) | `/research` `200` (`0` overflow); `runs` `200` (`19` runs for `librarian`, `0` for `librarian2`) | **PASS** | `audit_live_results.json`, `audit_browser.py` |
| 22. Research Intelligence 14-Sheet XLSX Export (`/api/research/intelligence/runs/<id>/xlsx`) | Yes | Previously verified + run list verified | `19` runs live; prior verified XLSX export `36,297` bytes (`14` sheets) | **PASS** | `ARCHIPELAGO_FINAL_THREE_GATE_CLOSURE.md`, `audit_live_results.json` |
| 23. Research Monitors & Scheduled Tick (`/api/research/intelligence/monitors`, `/api/internal/s5-monitor-tick`) | Yes | Yes (HTTP + unauthenticated tick check) | `monitors` `200` (`3` monitors for `librarian`, `0` for `librarian2`); `/api/internal/s5-monitor-tick` unauth `401` | **PASS** | `audit_live_results.json` |
| 24. Research Intake Metrics & Topics (`/api/research/intake/metrics`, `/topics`) | Yes | Yes (librarian token) | `metrics` `200` (`2.108s`), `topics` `200` (`1.255s`) | **PASS** | `audit_live_part3.json` |
| 25. Scholarly Snapshot Endpoint (`/api/scholarly/snapshot`) | Yes | Yes (student `403`, librarian `503`) | Returned `503` for `librarian` (`0.406s`) in hosted `inference-only` mode | **PARTIAL / DEGRADED** | `audit_live_part2.json`, `audit_live_part3.json` |
| 26. Hosted Document Upload Ingestion (`/api/ingest`) | Disabled in prod | Yes (`GET /api/ingest/capabilities`) | `HTTP 200`: `upload_api_enabled: false`, `delete_api_enabled: false`, `student_upload_enabled: false` (`inference-only`) | **PASS (By Design: Workstation-Only)** | `audit_live_results.json` |
| 27. Hosted TOC Indexing (`/api/ingest/index`) | No (`501`) | Yes (`POST /api/ingest/index`) | `HTTP 501` (`{"error": "not_implemented"}`) | **NOT IMPLEMENTED** | `audit_live_results.json`, `ingest.py` |
| 28. S4 Academic Automation Review & GPU Ingestion Pipeline (`/academic-automation`, `/api/academic-automation/...`) | Yes | Yes (5-role RBAC + local `state.sqlite3` + `nvidia-smi`) | `review/<id>` `401` anon, `403` student/faculty, `200` librarian/admin; local RTX 2050 idle (`14 MiB / 4096 MiB`), `337d88fe...` & `bd817e5d...` in `review_ready` (`published_version=None`) | **PUBLICATION GOVERNANCE PENDING** | `audit_live_results.json`, `audit_live_part2.json`, `state.sqlite3` |

---

## 3. Live Production & Latency Evidence

- **Main Production (`https://archipelago-blond.vercel.app/`):**
  - `/api/health` & `/api/readiness`: `200` (`0.411s` / `0.394s`), `ok: true, concepts: 610, pearson_books: 40, mode: "inference-only", graph_version: "9818ac0e8fd3"`.
  - Hosted 25-question curated holdout (`artifacts/validation/hosted_prod_holdout_results.json`): `21 PASS / 4 PARTIAL / 0 FAIL`, `mean = 6.96s, p50 = 7.182s, p95 = 10.324s, max = 12.832s`.
  - Fresh 6-question weak-domain live sample (`chat_full_sample.json`):
    - `W1_OS_TLB` (`4.503s`, `MULTI_CONCEPT`): **FAIL** — lexical match on `"translation"` anchored to NLP `Translation` (`Brown2020_GPT3.pdf`), did not explain TLB.
    - `W2_ALGO_DIJKSTRA` (`1.751s`, `MULTI_CONCEPT`): **PARTIAL** — honest abstention (`not indexed`), no hallucination, but did not answer negative-edge failure / Bellman-Ford.
    - `W3_NET_CONGESTION` (`1.897s`, `GENERAL_EXPLANATION`): **FAIL** — returned raw prompt template (`"Compare **TCP Slow Start** and **Congestion Avoidance (AIMD)..."`) instead of an explanation.
    - `W4_MULTIHOP_KV_FLASH` (`1.802s`, `MULTI_CONCEPT`): **PARTIAL** — grounded `Transformer` (`Vaswani2017_Attention_Is_All_You_Need.pdf`) but missed `KV Cache` & `FlashAttention`.
    - `W5_UNSUPPORTED_SCOPE` (`0.609s`, `GUARDRAIL_INTERCEPT`): **PASS** — cleanly refused C4 photosynthesis.
    - `W6_FOLLOWUP_PAGETABLE` (`2.953s`, `CROSS_DOMAIN`): **FAIL** — cross-domain matrix `Address Translation × Translation` with off-topic medical segmentation citations (`ABR-DeepLabV3+...`, `Voronoi bone scaffolds...`).
- **Librarian Production (`https://archipelago-librarian.vercel.app/`):**
  - `/api/readiness`: `200` (`0.621s`, `{"ready": true}`).
  - Playwright (`1440×960` & `390×844`): `/librarian`, `/analytics`, `/academic/graph`, `/research`, `/research/topics`, `/academic-automation` all rendered cleanly with `overflow: false` and `page_errors: []`.

---

## 4. Security, 5-Role RBAC & Isolation Matrix

All 5 Supabase test identities were verified via `/api/auth/me` before testing: `student` (`s6-demo-student`), `faculty` (`faculty.cs`), `librarian` (`librarian`), `librarian2` (`new_librarian`), and `administrator` (`administrator`).

| Endpoint | Anonymous | Student | Faculty | Librarian | Administrator |
| --- | --- | --- | --- | --- | --- |
| `GET /api/academic-automation/review/<id>` | `401` | `403` | `403` | `200` | `200` |
| `POST /api/academic-automation/review/<id>/decision` | `401` | `403` | `403` | Skipped (no S4 mutation) | Skipped (no S4 mutation) |
| `POST /api/research/graph/annotation` (invalid body) | `401` | `403` | `403` | `404` (RBAC passed) | `404` (RBAC passed) |
| `GET /api/librarian/catalog` | `401` | `403` | `200` | `200` | `200` |
| `POST /api/librarian/catalog` | `401` | `403` | `403` | Skipped (no prod mutation) | Skipped (no prod mutation) |
| `GET /api/research/intelligence/runs` | `401` | `200` (`0`) | `200` (`0`) | `200` (`19` runs) | `200` (`0`) |
| `GET /api/research/graph/full` | `401` | `403` | — | `200` | — |
| `GET /api/internal/s5-monitor-tick` | `401` | — | — | — | — |

- **Cross-User Research Isolation:** `librarian2` (`new_librarian`) received `0` runs and `0` monitors (isolated from `librarian`'s `19` runs and `3` monitors).
- **Session Cookie Hardening:** `POST /api/auth/session` set `archipelago_token` with `Secure; HttpOnly; Path=/; SameSite=Lax`.
- **XSS Hardening Note:** JSON endpoints (`/api/roadmap`) return `application/json`; `host_inference/ui/graphify.js` line 321 interpolates `data.name`/`data.summary` into `tooltip.innerHTML` (currently sourced only from the curated Kuzu graph DB, recommended for HTML-escaping in future hardening).

---

## 5. GPU Ingestion & S4 Governance State (Read-Only Check)

- **GPU & Ollama State:** `nvidia-smi` reported `NVIDIA GeForce RTX 2050, 14 MiB, 4096 MiB` (idle; FlowState training process untouched); `ollama ps` was empty (no pinned models).
- **Job `337d88fe-70df-49f2-af98-4f3413895951` (`arxiv:2307.09702`):** `status='review_ready'`, `published_version=None`, `human_reviews=[]`, `validation.json` reports `added_concepts: 5, added_edges: 12, broken_edges_count: 0, self_refs_count: 0, staging_concepts: 615, staging_edges: 2000, valid: true`.
- **Job `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` (`opac_live:4150`):** `status='review_ready'`, `published_version=None`, `human_reviews` has 1 row (`pratay-karali-operator`, `approve`, `2026-11-14T17:20:10+00:00`). Requires independent second-reviewer governance sign-off before publication.
- **Production Graph Integrity:** `okf_graph.db` (`102,637,568` bytes, Kuzu DB) remains untouched at `610` concepts / `40` Pearson books.

---

## 6. Direct Answers to Audit Questions (A–J)

- **A. Do all core S1–S6 features actually work in production?**  
  **Yes for infrastructure/routing, with 4 caveats:** All 28 inventoried routes/features behave as designed across `archipelago-blond.vercel.app` and `archipelago-librarian.vercel.app`, except `/api/ingest/index` (`501 not_implemented`), `/api/library/opac/live` (`503 opac_unavailable` upstream timeout at audit time), `/api/scholarly/snapshot` (`503` for librarian), and weak-domain `/api/chat` accuracy gaps.
- **B. What is the real live academic answer correctness rate (separated from functional availability)?**  
  Curated CS/AI holdout: **`21/25` (`84.0%` PASS, `4` PARTIAL, `0` FAIL)**; curated `128`-Q domain benchmark: **`112/128` (`87.5%` PASS, `9` PARTIAL, `7` FAIL)**; fresh 6-question weak-domain/edge-case live sample: **`1/6` PASS, `2/6` PARTIAL, `3/6` FAIL**.
- **C. Are hosted chat latencies acceptable?**  
  **Yes:** Hosted 25-Q holdout `p50 = 7.182s`, `p95 = 10.324s`, `max = 12.832s`; fresh 6-Q live sample `0.609s–4.503s`.
- **D. Does the Knowledge Graph & Graphify UI work end-to-end on both hosts?**  
  **Yes:** `/api/graph/hubs` (`12` nodes), `/api/graph/subgraph?q=Transformer`, `/api/graph/page`, and `/api/research/graph/full` (staff-gated) all return `200`, and `/academic/graph` renders the dark Graphify canvas with zero overflow or JS errors.
- **E. Do OPAC / Koha and Librarian Space features work?**  
  **Snapshot & Librarian CRUD: Yes (`200`); Live OPAC proxy: Degraded (`503`).** `/library`, `/api/library/koha`, `/api/library/data`, `/librarian`, `/analytics`, and `/api/librarian/catalog` all work; `/api/library/opac/live` timed out (`14.229s`) against external `uemk-opac.l2c2.co.in`.
- **F. Do Research Intelligence, XLSX export, and monitoring work?**  
  **Yes:** `/research`, `/research/topics`, `/api/research/intelligence/runs` (`19` runs), `monitors` (`3` monitors), `intake/metrics`, `intake/topics`, and prior verified `14`-sheet XLSX export (`36,297` bytes) work; `/api/internal/s5-monitor-tick` is configured in `vercel.json` (`0 4 * * *`) and gated (`401` unauthenticated).
- **G. Is GPU ingestion cleanly staged without polluting production or pinning VRAM?**  
  **Yes:** `337d88fe-70df-49f2-af98-4f3413895951` is `review_ready` (`+5` concepts, `+12` edges, `0` broken/self-refs), `okf_graph.db` is untouched, RTX 2050 is idle (`14 MiB / 4096 MiB`), and `ollama ps` is empty.
- **H. Are 5-role RBAC, student quotas, session cookies, and cross-user isolation enforced?**  
  **Yes:** Verified `401` anonymous, `403` student/faculty on staff/S4/annotation routes, `200` staff access, `librarian2` isolation (`0` runs/monitors), `10/10` student quota status, and `Secure; HttpOnly; SameSite=Lax` session cookies.
- **I. Are any S4 candidates auto-published?**  
  **No:** Both `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` and `337d88fe-70df-49f2-af98-4f3413895951` have `published_version = None` (`PUBLICATION GOVERNANCE PENDING`).
- **J. Final Release Recommendation?**  
  **CONDITIONALLY RELEASED** — shippable for curated CS/AI/ML academic & institutional library operations under S4 human-review governance, with follow-up remediation tracked for weak-domain chat retrieval/prompt-echo (`W1`, `W3`, `W6`), independent S4 second-reviewer sign-off, and external OPAC upstream stability.
