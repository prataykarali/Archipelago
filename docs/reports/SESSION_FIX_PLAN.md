# Archipelago — Session-Wise Fix Plan

**Date:** 2026-07-28  
**Goal:** Make Gemini+Python hybrid reliable, wire ODS/SCH control cases, keep graph closed when Gemini is down, and ship a Docker/Railway-ready deploy.

---

## Product policy (non-negotiable)

| Route class | Gemini **ON** | Gemini **OFF** / exhausted |
|-------------|---------------|----------------------------|
| **SCH-1 hours, SCH-2 credentials, ODS catalog lookups, system FAQ, identity/onboarding small talk** | Python facts → Gemini rephrase (hybrid) | **Python-only** grounded reply (no invention) |
| **Graph theory (INF-4/5, curriculum, citations)** | Python graph notes → Gemini synthesis | **Library closed** — never raw graph template as final answer |
| **Out-of-scope / OOD** | Hybrid refusal or canned policy text | Python refusal OK (no Gemini required) |
| **INF-1 length > 500** | JSON 400 before any model/DB work | Same |

Rationale: graph answers without Gemini risk ungrounded or template-looking prose; hours/credentials/ODS are deterministic lookups and must stay available offline.

---

## Current state (audit snapshot)

| Layer | Status | Notes |
|-------|--------|-------|
| Module imports | OK (in `.venv`) | System `python3` lacks `google.generativeai` |
| Graph data | Partial | Kùzu ~473 concepts, 237 REQUIRES, 387 UNLOCKS; JSON 460 nodes / 1832 edges; `visualization.edges = 0` |
| ODS parser/ingestion code | Written, unit-tested | **Not wired** into worker/API; **no ODS tables** in live DB |
| SCH-1 / SCH-2 detection | Works | Routes exist; final path still **requires** Gemini hybrid today |
| Gemini client | Fragile | Uses deprecated `google.generativeai`; default model list includes unverified ids; hybrid mandatory everywhere |
| Services | Down | Stale PIDs in `logs/*.pid`; no listeners on 505x |
| Docker | Exists at root | `requirements.txt` **missing torch/transformers** → Railway/Railpack crash |
| Junk | Present | `=0.8.0`, `<new_str>*` artifacts from bad edits |
| Control-case gaps | Many | INF-2 weak norm; INF-4 Qiskit → hard OOD not soft topo; ODS schema ≠ Resource/JournalIssue |

---

## Session map (overview)

```
S0  Cleanup + policy lock          (½ day)   ← start here
S1  Gemini+Python reliability      (1 day)
S2  Offline library path           (½–1 day)
S3  ODS wire-up + Phase C ingest   (1–1½ day)
S4  INF control-case alignment     (1 day)
S5  Docker / Railway / GitHub      (1 day)
S6  Extraction / graph health      (1–2 days)
S7  Eval + pilot gate              (½ day)
```

Dependencies: **S0 → S1 → S2** sequential. **S3** after S0 (can parallel S1 lightly). **S4** after S1+S2. **S5** can start after S0 in parallel with S1. **S6** after S3 optional. **S7** last.

---

## Session 0 — Cleanup + policy lock

**Why first:** Stop bad artifacts and document the product contract so later sessions don’t re-break hybrid rules.

### Work
1. Delete junk files: `=0.8.0`, `<new_str>*` edit leftovers.
2. Fix `init_concepts_data()` log spam (print once, not per concept).
3. Codify policy in one place:
   - `archipelago/inference/synthesis.py`: `require_hybrid_reply` / new `reply_or_closed(mode=...)`
   - Modes: `factual` | `refusal` | `graph` | `general`
   - **`graph` mode:** Gemini required → else `GEMINI_UNAVAILABLE_MSG`
   - **`factual` mode:** Gemini preferred → else return `python_context` as final
4. Update `PILOT_LAUNCH.md` / `TODO.md` so “Gemini optional for graph” is **false**.
5. Smoke: unit tests for mode policy (no network).

### Done when
- [ ] Junk gone
- [ ] Concept load logs once
- [ ] Policy helpers + 5–10 unit tests green
- [ ] Docs match policy table above

### Files
- `archipelago/inference/synthesis.py`
- `archipelago/inference/routes_chat.py` (call sites only if needed)
- `archipelago/inference/routes_chat.py` `init_concepts_data`
- `PILOT_LAUNCH.md`, `TODO.md`
- `tests/unit/test_hybrid_policy.py` (new)

---

## Session 1 — Gemini + Python reliability

**Why:** Every graph answer and most chat paths die if Gemini client/SDK/models are wrong.

### Work
1. **Client dual-path**
   - Prefer `google.genai` (new SDK) with fallback to `google.generativeai`.
   - Keep key + model roulette; map errors to rotate.
2. **Model list hygiene**
   - Default primary: `gemini-2.5-flash` (or env `ARCHIPELAGO_GEMINI_MODEL`).
   - Fallbacks: `gemini-2.5-flash-lite`, `gemini-2.0-flash` only after live probe or documented working set.
   - Drop speculative `gemini-3.x` / empty-candidate models from default unless env-listed.
3. **`requirements.txt`**
   - `google-genai` + keep `google-generativeai` transitional **or** single SDK after dual-path proven.
4. **Availability**
   - `is_gemini_available()` true only if key **and** import succeed.
   - Readiness endpoint reports `gemini: true/false` honestly (not “ENABLED” when import fails).
5. **Live smoke script** `scripts/ops/gemini_smoke.py`: one chat call, print model used.
6. Wire graph path to policy: synthesis fails → library closed (already mostly true; ensure no silent template final).

### Done when
- [ ] `gemini_smoke.py` returns non-empty text with pilot keys
- [ ] Graph query with key → hybrid answer
- [ ] Graph query without key → exact library-closed message
- [ ] Unit tests mock client; no live key required in CI

### Files
- `archipelago/inference/gemini_client.py`
- `archipelago/inference/state.py`
- `archipelago/inference/routes_misc.py` (readiness)
- `requirements.txt`
- `scripts/ops/gemini_smoke.py`
- `tests/unit/test_gemini_client.py`

---

## Session 2 — Offline library path (SCH + FAQ + books)

**Why:** Hours/credentials must work when Gemini is down; control cases say bypass RAG **and** prevent credential hallucination.

### Work
1. **SCH-1 / SCH-2 final replies**
   - With Gemini: hybrid `mode=factual`.
   - Without Gemini: return `format_schedule_for_response` / `format_credential_for_response` **directly** (sterile strip only).
2. Same for `system_faq`, `library_books` / chapters if grounded purely in Cypher/Python.
3. **Do not** send credentials through free-form graph synthesis.
4. Detection order already early in `routing.py` — keep **before** kill-switch; add tests that hours win over weak graph cosines.
5. Align SCH-1 copy with `docs/time_library.png` (24×7 policy already coded).
6. NDLI dual passkeys: keep primary + alt; tests accept either in output.

### Done when
- [ ] Hours query works with `GEMINI_API_KEY=` unset
- [ ] Credentials query works offline; never invents passwords
- [ ] Graph query still closed offline
- [ ] Integration tests: schedules/credentials offline + online mock

### Files
- `archipelago/inference/routes_chat.py`
- `archipelago/inference/synthesis.py` (`factual` fallback)
- `archipelago/inference/library_schedules.py` / `library_credentials.py` (only if copy gaps)
- `tests/integration/test_library_schedules_credentials.py`
- `tests/unit/test_offline_library_path.py` (new)

---

## Session 3 — ODS wire-up (ODS-1 / ODS-2 + Phase C)

**Why:** Parser/ingestion modules exist but are **disconnected** from production graph and APIs.

### Work
1. **Schema decision (pragmatic)**
   - Ship working tables: `SubjectReport`, `JournalReport`, `KeywordReport` (already in `ods_ingestion.py`).
   - Optional alias FAQ text: map “Resource / JournalIssue” language → these tables **or** add thin `Resource`/`JournalIssue` views later (Session 6).
2. **CLI** `scripts/ops/sync_ods.py`:
   - `default_docs_ods_paths()` → `sync_ods_reports_to_graph(conn, paths)`
   - Print inserted/dropped/errors.
3. **API** (librarian-only): `POST /api/ingest/ods` multipart or path-based; reuse auth from `routes_misc`.
4. **Worker hook** (optional): accept `.ods` upload extension in `ingestion_worker` quarantine list → ODS path instead of PDF pipeline.
5. **No concept-linking yet** for incomplete rows (already drop+log); do **not** invent Concept edges from bad ISSN.
6. Run sync once against live `okf_graph.db` (write lock careful — stop servers or use rebuild script).
7. Optional: Cypher-backed “how many titles in subject X?” route if product needs it (else Session 4).

### Done when
- [ ] Live DB shows ODS node tables with non-zero counts from `docs/*.ods`
- [ ] Bad-schema fixture → drop + error log, zero ghost nodes
- [ ] Unit tests remain green; add integration ingest test on temp DB

### Files
- `archipelago/inference/ods_parser.py` / `ods_ingestion.py` (minor)
- `scripts/ops/sync_ods.py` (new)
- `archipelago/inference/routes_misc.py` (endpoint)
- `ingestion_worker.py` (optional `.ods`)
- `tests/integration/test_ods_ingest.py` (new)

---

## Session 4 — INF control-case alignment

**Why:** Routing mostly exists; behavior diverges from the written INF-1…5 contract.

### Work

| Case | Target behavior | Fix |
|------|-----------------|-----|
| **INF-1** | `{"error":"Query too long. Limit to 500 characters."}` | Already in `routes_chat`; add contract test |
| **INF-2** | Strip filler → technical intent | Strengthen `normalize_user_query` (strip trailing Thanks/please explain scaffolding); use normalized query for ranking only |
| **INF-3** | cos &lt; 0.75 → OOD soft reject **before Gemini** | Ensure kill-switch message format; sourdough stays OOD without API call when embeddings on; when embeddings off, lexical/intent path must still refuse |
| **INF-4** | Concept-ish miss → soft rejection + topo map stub | Qiskit-style: prefer `low_similarity_reject` / partial graph with “missing from catalog chunks” over hard `not_in_corpus` when no entity-trivia; tune intent gate |
| **INF-5** | Full hybrid topo + [S#] | Ensure `synthesize_with_gemini*` prompts keep Topo Map + citations; strong anchor for “Scaled Dot-Product Attention” if possible (`attention` not only `attention_head`) |

### Done when
- [ ] Scripted control suite (7 prompts) matches expected **route** + **shape** of answer
- [ ] No Gemini call on INF-1 / INF-3 (assert via mock)
- [ ] INF-5 with mock Gemini returns structure markers

### Files
- `archipelago/inference/ranking.py`
- `archipelago/inference/routing.py`
- `archipelago/inference/intent_gate.py`
- `archipelago/inference/synthesis.py`
- `archipelago/inference/routes_chat.py`
- `tests/integration/test_inf_control_cases.py` (new)

---

## Session 5 — Docker / Railway / GitHub hosting

**Why:** Root `Dockerfile` exists but image deps don’t match runtime (torch used by embeddings/ranking). Railway may ignore Dockerfile or fail mid-import.

### Work
1. **Split requirements**
   - `requirements.txt` — **inference runtime** (always installed in Docker):
     - flask, gunicorn, kuzu, thefuzz, pymupdf, python-docx
     - google-genai (+ generativeai bridge if needed)
     - pyexcel-ods, openpyxl
     - **torch (CPU wheel)**, **transformers**, **sentencepiece** (or document `ARCHIPELAGO_SKIP_EMBED=1` lexical-only mode)
   - `requirements-dev.txt` — pytest, training extras
   - `requirements-extract.txt` — llama-cpp / ollama extraction (optional, not in slim image)
2. **Dockerfile fixes**
   - Multi-stage or CPU torch index:  
     `pip install torch --index-url https://download.pytorch.org/whl/cpu`
   - Do **not** COPY giant `pdfs/`, `models/`, `training_data/` into image (`.dockerignore`).
   - Ship `okf_graph.json` + compact DB **or** download at boot; document size limits.
   - `ENV ARCHIPELAGO_FORCE_CPU_EMBED=1`, `ARCHIPELAGO_LOAD_AURA=0`
   - Single public process: prefer inference on `$PORT`; graph optional internal or same app static.
3. **`.dockerignore`**
   - `.venv`, `pdfs/`, `models/*.gguf`, `logs/`, `jobs/`, `__pycache__`, training, scratch
4. **`railway.toml` or `railway.json`**
   - `builder = "DOCKERFILE"`
   - `dockerfilePath = "Dockerfile"`
   - Healthcheck: `/api/readiness`
5. **`start.sh`**
   - Align PORT comments; fail fast if graph JSON missing; optional skip graph_server if not needed for pilot.
6. **GitHub**
   - Ensure Dockerfile at repo root for `prataykarali/libraryAI`
   - Optional GH Action: build image on push (no push secrets unless asked)
7. **Local verify**
   - `docker build -t libraryai .` && `docker run -e GEMINI_API_KEY=... -p 8080:8080 libraryai`
   - Hit readiness + hours query

### Done when
- [ ] Image builds without Railpack inventing deps
- [ ] Container boots; readiness 200
- [ ] Chat hours works; graph with key works or closed without key
- [ ] README “Deploy on Railway” section: set builder Dockerfile, env vars list

### Files
- `Dockerfile`, `.dockerignore`, `start.sh`
- `requirements.txt`, `requirements-dev.txt`
- `railway.toml` (new)
- `README.md` / `PILOT_LAUNCH.md`
- Optional: `.github/workflows/docker.yml`

### Env vars for Railway
```
GEMINI_API_KEY=
GEMINI_API_KEY_2=          # optional
ARCHIPELAGO_GEMINI_MODEL=gemini-2.5-flash
ARCHIPELAGO_FORCE_CPU_EMBED=1
ARCHIPELAGO_LOAD_AURA=0
ARCHIPELAGO_LIBRARIAN_TOKEN=  # production
PORT=                     # platform-injected
```

---

## Session 6 — Extraction + graph health (deeper)

**Why:** Ingestion/extraction “broken” reports often mean model path, locks, or export drift—not missing Python modules.

### Work
1. Document extraction backends: GGUF present under `models/`; `lib-qwen` missing; Ollama fallback.
2. Fix Kùzu lock stories: inference default read-only when lock held; no “empty DB under READ ONLY” crash — clear error in readiness.
3. After ODS sync + any PDF job: `write_all_artifacts` so root JSON, UI, and DB stay aligned (`visualization.edges` currently 0 while `edges` full — graph_server uses top-level `edges`, OK; still fix export consistency).
4. `ingestion_worker` only accepts PDF/MD/TXT today — document; ODS via Session 3 path.
5. Optional: concept-link keyword titles → existing Concept nodes (low confidence, behind flag).

### Done when
- [ ] Readiness reports db open mode + concept count + gemini + embeddings
- [ ] One PDF `--add` or job completes on pilot machine **or** documented blocker (GPU/Ollama)
- [ ] Export: vis edges non-zero **or** UI proven on top-level edges only

### Files
- `okf/pipeline*.py`, `ingestion_worker.py`, `okf/exports.py`
- `archipelago/inference/state.py` / `routes_misc.py`
- `scripts/ops/rebuild_graph_db.py`

---

## Session 7 — Eval + pilot gate

### Work
1. Expand `scripts/ops/demo_check.sh` with SCH-1, SCH-2, INF-1, INF-3, one graph INF-5.
2. Run unit + integration subsets in CI-friendly mode (no live Gemini required except optional job).
3. Update `TODO.md` checkboxes honestly (no “all complete” until Session 7 passes).
4. Stale PID cleanup in `serve.sh start` (kill or ignore dead pids).

### Done when
- [ ] `./scripts/ops/start_pilot.sh` green locally
- [ ] Control-case doc matches observed routes
- [ ] Railway/Docker smoke checklist signed off

---

## Priority if time-boxed (minimum viable)

If only **2 sessions** of work:

1. **S0 + S1 + S2** — hybrid policy, Gemini works, offline hours/creds, graph closed offline  
2. **S5** — Docker/Railway actually boots  

Defer S3/S4/S6 polish to follow-up.

---

## Risk register

| Risk | Mitigation |
|------|------------|
| Full torch in image = multi‑GB | CPU wheel + `.dockerignore`; or lexical-only flag without torch for ultra-slim (weaker INF-3) |
| Gemini SDK deprecation mid-flight | Dual client in S1 |
| Kùzu exclusive lock on Railway multi-instance | `--workers 1`; single replica |
| ODS real headers ≠ ideal control schema | Already have alias schemas; don’t block on ideal ISSN |
| Credential secrets in repo | Already in code/PDF; treat as institutional; don’t log raw passwords in server logs |

---

## Suggested execution order (this repo)

```
Session 0  cleanup + policy helpers
Session 1  gemini client + requirements
Session 2  offline library replies
Session 5  docker/railway  (can overlap late S1)
Session 3  ODS sync
Session 4  INF suite
Session 6  graph/extract
Session 7  eval gate
```

---

## Out of scope for this plan

- Full fine-tune of extraction SLM / re-ingest all `pdfs/real-lib`
- Renaming entire catalog schema to Resource/JournalIssue (unless S6 chooses)
- Multi-region HA, auth SSO, payment
- Pushing secrets or force-pushing git history
