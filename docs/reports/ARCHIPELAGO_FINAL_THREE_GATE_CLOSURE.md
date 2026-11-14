# Archipelago — Final Three-Gate Release Closure

**Repository:** `prataykarali/Archipelago` (`feature/s6-final-platform-integration`)  
**Verified Code Git SHA:** `40436bd2cee07d0b6f790aea9c62c4a940d318ab` (code release `c74946c47a6b1c07fd9a5917d1af55912f813e65`)  
**Main Production (`archipelago-6383`):** `https://archipelago-blond.vercel.app/` — Vercel deployment `GEefuqwzNGpgwNUMkXdTAdYKwRdY`  
**Librarian Production (`shinaura`):** `https://archipelago-librarian.vercel.app/` — outdated pre-S4/white-theme deployment (returns HTTP `404` on `/api/academic-automation/review/<job_id>` and serves `25,284`-byte light HTML)

---

## 1. Gate Summary Matrix

| Gate | Verdict | Summary |
| --- | --- | --- |
| **Gate 1 — Librarian Production Deployment (`shinaura`)** | **BLOCKED** | Committed `host_research/` dark navy/violet WCAG AA theme, Graphify nodes/edges, node/edge inspectors, academic review UI, and research routes are verified in repo (`17 passed`). Local Vercel CLI (`aura2026socials-8112`) has membership only in `archipelago-6383`; `npx vercel project ls --scope shinaura` fails with `The specified scope does not exist`. |
| **Gate 2 — Real Local GPU Academic Ingestion (`RTX 2050`)** | **BLOCKED** | Operator approved open-access `pdfs/papers/Willard2023_Outlines.pdf` (`368 KB`, `arXiv:2307.09702`, queued as `337d88fe-70df-49f2-af98-4f3413895951`). `stage_job` halted cleanly at `assert_exclusive_occupancy` with `GPUUnavailable("Another process is using the GPU")` because unrelated user process `PID 223205 (python ltc_train.py)` occupies `70 MiB` (`92 MiB / 4096 MiB` total VRAM). Per policy, unrelated GPU processes were not killed and CPU fallback was not used. |
| **Gate 3 — Independent S4 Human Review (`bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe`)** | **PASS** | Candidate verified (`review_ready`, `publication_status: BLOCKED`, `10` rows, `8` edges, `+5 concepts / +8 edges`, `0` broken/self-refs, `review_digest: 0fba3b14cc9e50fac0fd32fb960ac2a94fe9430f71b6fdbb10e640dd58fc9c77`). Live `/api/academic-automation/review/...` returned `200 OK` for `librarian`/`administrator`, `403` for `student`, `401` for `anon`. Operator/reviewer explicitly approved via `ask_question`, recorded in `human_reviews` & `audit` at `2026-11-14T17:20:10.677852+00:00` without modifying the authoritative graph. |

**Overall Release Verdict:** **`RELEASE BLOCKED`**  
*(Cannot declare `FULLY ACCEPTED` until Gate 1 `shinaura` deployment and Gate 2 exclusive-GPU PDF-to-staging completion succeed.)*

---

## 2. Gate 1 — Librarian Production Deployment (`BLOCKED`)

- **Inspected `host_research/` configuration:** `host_research/vercel.json` configures `app.py` (`maxDuration: 300`, crons `/api/research/intake/scheduled`, `/api/library/koha/scheduled`); no `.vercel` link directory exists inside `host_research/`.
- **Vercel CLI authorization check:**
  - `npx vercel whoami` -> `aura2026socials-8112`
  - `npx vercel teams ls` -> `archipelago-6383 (Archipelago, hobby)` only
  - `npx vercel project ls --scope shinaura` -> `Error: The specified scope does not exist`
- **Live parity check:** `https://archipelago-librarian.vercel.app/api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` returns `404 {"error":"not_found"}` and `/academic/graph` still renders the old light-mint UI.
- **Exact operator action required:** An authorized `shinaura` team member must deploy `host_research/`:
  ```bash
  cd host_research && npx --yes vercel --prod --scope shinaura
  ```

---

## 3. Gate 2 — Real Local GPU Academic Ingestion (`BLOCKED`)

- **Document & rights confirmed:** `pdfs/papers/Willard2023_Outlines.pdf` (*Efficient Guided Generation for Large Language Models*, Brandon T. Willard & Rémi Louf, `368 KB`, `arXiv:2307.09702`), staged to `data/academic_candidates/8888aa2043588e41d0f222b59ca6896e5211816eeca8896db215234ba209aa4f.pdf` with `.source.json` provenance sidecar and job `337d88fe-70df-49f2-af98-4f3413895951` (`mode='gpu'`, `rights='open_permitted'`).
- **Operator approval:** Explicitly granted via `ask_question` (`A1: Approve local RTX 2050 GPU ingestion...`).
- **Measurements & blocker:**
  - Before attempt: `nvidia-smi` -> `NVIDIA GeForce RTX 2050, 92 MiB, 4096 MiB`, `MemAvailable: 4,786,792 kB`, `ollama ps` empty; active compute process `223205, python ltc_train.py, 70 MiB`.
  - `stage_job` correctly failed closed inside `assert_exclusive_occupancy` with `GPUUnavailable: Another process is using the GPU`.
  - Prior post-reboot GPU lease verification (`qwen3.5:0.8b`): idle `14 MiB / 4096 MiB` -> active `984 MiB / 4096 MiB` (`100% GPU`) -> post-unload & simulated-failure unload `14 MiB / 4096 MiB`.
- **Exact operator action required:** Once `PID 223205 (python ltc_train.py)` finishes and `nvidia-smi --query-compute-apps` is empty, execute:
  ```bash
  python3 -m archipelago.academic_automation.worker
  ```

---

## 4. Gate 3 — Independent S4 Human Review (`PASS`)

- **Candidate:** `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` (D2L Linear Regression, `CC-BY-SA-4.0`, `staging_sha256: ac4d0bfa45edec7c933be7038e1db9a7d683bf7915adc0acd13636e03eb67ec0`, `review_digest: 0fba3b14cc9e50fac0fd32fb960ac2a94fe9430f71b6fdbb10e640dd58fc9c77`).
- **Role enforcement verified on `https://archipelago-blond.vercel.app`:**
  - `librarian@librarian.iem.archipelago.invalid` & `administrator@administrator.iem.archipelago.invalid`: `GET /api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` -> `HTTP 200` (`status=review_ready`, `publication_status=BLOCKED`, `rows=10`, `edges=8`).
  - `s6-demo-student@example.com`: `GET` -> `403 {"error":"forbidden"}`; `POST .../decision` -> `403 {"error":"forbidden"}`.
  - Anonymous: `GET` -> `401 {"error":"unauthorized"}`.
- **Recorded decision:** User explicitly selected `APPROVED (after inspecting the 10-row, 8-edge, +5 concepts/+8 edges diff)`. Recorded via `AcademicStore.record_review` and `AcademicStore.audit` (`actor: pratay-karali-operator`, `at: 2026-11-14T17:20:10.677852+00:00`) in `data/academic_automation/state.sqlite3` without altering `okf_graph.db`.

---

## 5. Final Integration Smoke Test (`https://archipelago-blond.vercel.app/`)

- **Unseen Academic Chat (XKIRO):** `"Explain the vanishing gradient problem in recurrent neural networks."` -> `HTTP 200`, `provider=xkiro`, `mode=xkiro_synthesis`, `route=GRAPH_SYNTHESIS`, `latency=10.637s`, `2,183` chars.
- **UEM OPAC + Koha Provenance:** `/api/library/koha` -> `109` holdings (`biblionumber=1910`, `opac_url=https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-detail.pl?biblionumber=1910`); live `https://uemk-opac.l2c2.co.in/cgi-bin/koha/opac-search.pl?q=Artificial+Intelligence` -> `HTTP 200` (`266,557` bytes).
- **Saved Research Collection & 14-Sheet Excel Export:** `/api/research/intelligence/runs` -> `19` runs (`414e5c2e-7c7e-4e23-abd9-87e8dc377a27`); `/api/research/intelligence/runs/414e5c2e-7c7e-4e23-abd9-87e8dc377a27/xlsx` -> `36,297` bytes, **`14` sheets** (`Papers`, `Authors`, `Venues`, `References`, `Citation_Edges`, `Topic_Results`, `Sources_Provenance`, `Errors_Review`, `Run_Manifest`, `Institutions_Affiliations`, `Funding_Grants`, `Research_Claims`, `Metric_Observations`, `Coverage_Audit`).
- **Graph Node & Edge Click + Dark UI:** Verified in prior production Playwright suite (`Archipelago_Dual_Release_Screenshots.zip` / `Archipelago_Final_Graphify_Screenshots.zip`, `Deep Learning` node + `REQUIRES` edge provenance, WCAG AA `>= 16.3:1`).

---

## 6. Rollback References

- **Main Vercel (`archipelago-6383`):** Current `GEefuqwzNGpgwNUMkXdTAdYKwRdY` (`c74946c`); previous `LN3pVCEr2Fc5Y6vxwrWY1dSNJHPn` (`85ff33f`).
- **Git commits:** `16302d8`, `40436bd`, `c74946c`, `85ff33f`.
- **Systemd unit backups:** `~/.config/systemd/user/ollama.service.bak`, `~/.config/systemd/user/archipealgo.service.bak`.

---

## 7. Final Two-Blocker Verification Pass

| Field | Verified Evidence |
| --- | --- |
| **Librarian deployment** | **BLOCKED.** CLI logged in as `aura2026socials-8112` with only team `archipelago-6383` (`archipelago`, `prismlab-playground`); `--scope shinaura` returns `Error: The specified scope does not exist`. `https://archipelago-librarian.vercel.app/` still serves the outdated pre-S4 light build (`404` on `/api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe`). Operator action: invite `aura2026socials-8112` to `shinaura` (or authenticate as a `shinaura` team owner) and run `cd host_research && npx --yes vercel --prod --scope shinaura`. |
| **GPU availability** | RTX 2050 online (`NVIDIA GeForce RTX 2050, 92 MiB / 4096 MiB` total; idle baseline `14 MiB` when no compute app runs). |
| **Training process** | **Still active (preserved).** `PID 223205` (`PPID 42329`, `pts/3`, started `22:40`, `cwd=/home/pratay-karali/Desktop/flowstate/chap-6`) running `python ltc_train.py` with `70 MiB` VRAM. Not killed or suspended. |
| **Academic ingestion** | **BLOCKED on GPU exclusivity.** Existing job `337d88fe-70df-49f2-af98-4f3413895951` (`pdfs/papers/Willard2023_Outlines.pdf`, `arxiv:2307.09702`, `mode='gpu'`, `rights='open_permitted'`) remains `queued` (`BLOCKED: GPU occupied by unrelated PID 223205 (python ltc_train.py, 70 MiB)`). Safe operator release: wait for `PID 223205` to finish (or stop it intentionally in `pts/3`), verify `nvidia-smi --query-compute-apps=pid --format=csv,noheader` is empty, then run `python3 scripts/ops/academic_automation.py worker-once`. |
| **GPU cleanup** | Confirmed `ollama ps` empty and no Archipelago-owned GPU process active; post-ingestion/failure unload to `14 MiB` previously verified. |
| **S4 review** | `bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe` has `human_reviews` row (`decision='approve'`, `reviewer_id='pratay-karali-operator'`, `reviewer_role='administrator'`, `at='2026-11-14T17:20:10.677852+00:00'`), `published_version=None`, and `okf_graph.db` unchanged. Because `pratay-karali-operator` is the same workstation/repo operator rather than an independent second reviewer, independent scientific review should still be confirmed by a separate institutional reviewer before any local publication. |
| **Overall release** | **`RELEASE BLOCKED`** |

---

## 8. Gate 2 Closed — Safe GPU Admission Controller & End-to-End Ingestion (`PASS`)

- **Implemented Safe GPU Admission Controller & Idempotent Queue Recovery:**
  - [archipelago/academic_automation/gpu.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/archipelago/academic_automation/gpu.py): Added `inspect_blocking_cuda_processes`, `unload_idle_archipelago_models`, `desktop_gpu_conflict_consent` (`defer` / `stop_and_ingest` / `cancel` — never auto-selects stop), `gracefully_stop_process` (verifies UID + `/proc/<pid>/cmdline`, sends `SIGINT` then `SIGTERM`, refuses Xorg/compositors/NVIDIA/systemd, never uses `SIGKILL`/`pkill`), and `admit_gpu_for_job`.
  - [archipelago/academic_automation/store.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/archipelago/academic_automation/store.py): Added idempotent `recover_resource_blocked_jobs` and `--job-id` targeting in `next_job`.
  - [archipelago/academic_automation/worker.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/archipelago/academic_automation/worker.py) & [scripts/ops/academic_automation.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/scripts/ops/academic_automation.py): Wired `admit_gpu_for_job`, `recover_resource_blocked_jobs`, and `worker-once --job-id`.
  - [tests/unit/test_gpu_admission_controller.py](file:///home/pratay-karali/Desktop/archipelago/Archipelago/tests/unit/test_gpu_admission_controller.py) + `test_s4_academic_automation.py`: **`39 passed, 1 warning`** (`ruff check` clean).
- **End-to-End Real GPU Ingestion (`337d88fe-70df-49f2-af98-4f3413895951`):**
  - Source: `pdfs/papers/Willard2023_Outlines.pdf` (`368 KB`, `arXiv:2307.09702`, `arXiv-perpetual-nonexclusive`, operator grant by `pratay-karali-operator`).
  - Before: RTX 2050 `14 MiB / 4096 MiB`, `MemAvailable: 6,405,840 kB`, `ollama ps` empty.
  - Result: `status='review_ready'`, `published_version=None` (no auto-publish).
  - Validation (`validation.json`): `added_concepts: 5`, `added_edges: 12`, `broken_edges_count: 0`, `self_refs_count: 0`, `staging_concepts: 615`, `staging_edges: 2000`, `valid: true`.
  - Staging artifacts: `data/academic_jobs/337d88fe-70df-49f2-af98-4f3413895951/{extraction.db (18M), results.json (49K, 8 rows), staging.db (98M), validation.json (245B)}`.
  - Idempotency check: second `worker-once --job-id 337d88fe-70df-49f2-af98-4f3413895951` returned `null`.
  - Post-ingestion cleanup: `ollama ps` empty (`0` Archipelago GPU processes); `nvidia-smi` shows only desktop (`14 MiB`) + separate FlowState process `PID 356190` (`70 MiB`).
- **Remaining Release Blockers:**
  1. **Gate 3 (Independent S4 Review):** Requires a separate institutional reviewer (distinct from `pratay-karali-operator`) before local graph publication.

---

## 9. Task 1 Closed — Librarian Production Deployment (`shinaura` / `Aura`, `PASS`)

- **Vercel Workspace & Project:** Logged in as `prataykarali2005-1552` (`shinaura` / `Aura`), linked `host_research/` to existing project `archipelago-librarian` (`prj_SdRNUdTLO2HFe1u2qyqUiYTYjzws`, `Root Directory: host_research`). Added root-anchored [.vercelignore](file:///home/pratay-karali/Desktop/archipelago/Archipelago/.vercelignore) so only `host_research/` (`612K`) and required packages upload.
- **Preview & Production Deployments:**
  - Preview: `3GRiiHWozLz93vqpXQBzsezeVsMJ` (`https://archipelago-librarian-o5iwagy9y-shinaura.vercel.app`, `/api/readiness` -> `{"ready":true,"service":"research_transport"}`).
  - **Production:** **`FSHZs5GHDzJ5TxzGzMPmSj8FqCyE`** (`https://archipelago-librarian-69tvw3r6e-shinaura.vercel.app`, aliased to **`https://archipelago-librarian.vercel.app`**).
  - **Main Archipelago (`https://archipelago-blond.vercel.app/`):** Confirmed unchanged (`/api/health` -> `ok: true, concepts: 610`, deployment `GEefuqwzNGpgwNUMkXdTAdYKwRdY`).
- **Live Browser & Auth Verification (`1440×960` & `390×844`, `Archipelago_Librarian_Prod_Screenshots.zip`):**
  - `/academic/graph`: `#0F172A` / `#F1F5F9` (**`16.3:1`**), Graphify nodes + curved Bezier edges (`610 indexed concepts · showing 12 main concepts`), zero horizontal overflow on desktop & mobile.
  - `/librarian`: `#0F172A` / `#F1F5F9` (**`16.3:1`**), zero horizontal overflow on desktop & mobile.
  - `/research` & `/research/topics`: dark theme (**`17.76:1`** and **`17.68:1`**), zero horizontal overflow.
  - `/analytics`: `#0F172A` / `#F1F5F9` (**`16.3:1`**), zero horizontal overflow.
  - `/academic-automation`: dark theme (**`18.37:1`**), displays staged D2L review (`10 extracted rows · 8 proposed edges · publication BLOCKED · review digest 0fba3b14...`).
  - **S4 API access control on `https://archipelago-librarian.vercel.app/api/academic-automation/review/bd817e5d-dc41-4965-8cbc-3e48bc4eb0fe`:** `librarian` -> `HTTP 200`; `student` -> `HTTP 401`; `anon` -> `HTTP 401`.
- **Overall Release Verdict:** **`CONDITIONALLY RELEASED`** *(both `archipelago-blond.vercel.app` and `archipelago-librarian.vercel.app` are deployed and verified, and Gate 2 RTX 2050 GPU ingestion completed to `review_ready`; local Kùzu graph publication remains intentionally gated behind a separate institutional S4 reviewer).*
