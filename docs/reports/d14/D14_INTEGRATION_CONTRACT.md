# D14 Integration, Branch Topology & File-Ownership Contract

**Owner:** `d14-integrator`  
**Phase:** D14.0 (Audit & Contract Setup Only — No Code Edits, No Pushes, No Deploys)  
**Date:** 2026-11-28  
**Status:** Active Contract (Pending `@coordinator` Branch-Base Sign-Off)

---

## 1. Deployment & Branch Topology Audit

### 1.1 Live Production vs. SIGIR Demo State (Verified Read-Only via `/api/readiness`)

Both hosted Vercel deployments were verified via read-only `GET /api/readiness` HTTP headers and JSON bodies on `2026-11-28T02:11Z`:

| Dimension | SIGIR 2027 Research Demo (D14 Target) | UEM Institutional Production (**STRICTLY OFF-LIMITS**) |
|---|---|---|
| **Public Domain** | `https://archipelago-sigir.vercel.app` | `https://archipelago-blond.vercel.app` (+ `archipelago-librarian.vercel.app`) |
| **Live Release SHA (`x-archipelago-release`)** | `fe8887c878e27f1770690236513f0f6c79c37d7c` (`sigir/d12-recovery`) | `f76c1c4ddb91bbf1947dbb820c971c51e04753cf` (`redesign_research_workspace`) |
| **Vercel Project** | `archipelago-sigir` (`prj_BjRCpNfUItbG8BO26CIQbPhP1oi9`) | `archipelago` (`prj_yVvxBExHYiLa67oqnABK2vW9FfCS`) |
| **Vercel Team / Org** | `sigir1` (`team_Ng6MKy7PiWsjDa0YAEZTVLku`) | `team_MYgmprJMXuVV1rVJEaZxbOPr` |
| **Vercel Service Topology** | Multi-service root `vercel.json`: `inference` (`host_inference/app.py`) + `research` (`host_research/app.py`) via private `INFERENCE_SERVICE_URL` binding | Single root `host_inference` (`repo.json` directory `host_inference`) + separate `archipelago-librarian.vercel.app` |
| **Vercel Git Policy** | Production branch `sigir/demo-2027`; preview deploys disabled; Git-triggered builds ignored (`exit 0`); explicit protected CLI deploy + alias promotion | Managed independently for UEM institutional production |
| **Supabase Project** | Research Staging `edokbtmhztkhndmxetpy` (`https://edokbtmhztkhndmxetpy.supabase.co`) | UEM Production `spllaastejfwclllfndp` (`https://spllaastejfwclllfndp.supabase.co`) |
| **Storage Buckets** | Private staging buckets: `archipelago-sigir-private` (immutable candidate passages), `archipelago-cache` (dated Koha snapshot) | UEM production Supabase storage/cache (`cache: "supabase"`) |
| **Access Profile & Licensed Books** | `ARCHIPELAGO_ACCESS_PROFILE=open_access` (`open_access_only: true`, `pearson_books: 0`) | `institutional` default (`pearson_books: 40`) |
| **Pinned Corpus & Graph** | `Prataykarali/graphier@86e29828c38dbf0f8cea5d50ed6a341ccde3a8f3` (610 concepts, 1,988 edges, `graph_version: 9818ac0e8fd3`); `Prataykarali/Library_books@b0561c76a4c5a7a8cb1fe3bd91b389280d504cbd` (43 docs); 3,025 passages (`sha256: 93f6db39...e52`, `checksum_verified: true`) | UEM institutional corpus + 40 Pearson books |
| **Protected Manuscript Dirs** | N/A | `/home/pratay-karali/Desktop/sigit_manu/`, `/home/pratay-karali/Desktop/sigit_manu_d11_sync_v1/` (**NEVER MODIFY**) |

### 1.2 Git Lineage & Divergence Audit

Common merge base between `main` and the SIGIR lineage (`sigir/demo-2027`, `sigir/d12-recovery`):  
`ef4e777988d463986b1f1aba54581c2e81e84d73`

| Branch / Ref | Commit SHA | Commits Ahead of Merge Base (`ef4e7779`) | Role & Contents |
|---|---|---|---|
| `main` | `c0d90b8484bbf48e605d4dcffb6975bdb6a09e2e` | 2 (`b9a462a`, `c0d90b8`) | Pre-SIGIR mainline + Nov 22 UI 3D restoration commits (already superseded on SIGIR lineage by `0746650`, `94558b9`, `12a0db6`, `0001769`). **Missing 83 commits of SIGIR isolation, D10-S3..S8, D11, and D12.** |
| `d14_scientific_recovery_stabilization` | `c0d90b8484bbf48e605d4dcffb6975bdb6a09e2e` | 2 (identical to `main`) | Current D14.0 workspace branch. **CRITICAL: Must NOT be used directly as the D14.1–D14.7 code base without rebasing/re-branching from `sigir/d12-recovery`.** |
| `redesign_research_workspace` | `f76c1c4ddb91bbf1947dbb820c971c51e04753cf` | — | Live UEM institutional production (`archipelago-blond.vercel.app`). |
| `sigir/demo-2027` | `71271ecad00ec30a4339ab6d072d9b5dbaf07861` | 61 | D10-S8 hosted SIGIR release baseline (`vercel.json` multi-service isolation, pinned HF revisions, durable sessions, 3,025/43 passage loader). |
| `tag: d11-a4-frozen` | `3c724431edd11e8b987e9150b7a526675cc6501f` | 73 | Frozen D11-A.4 baseline (session reliability, F01 SSE truncation/EOF hotfix, D11-B UX & `open_access` profile, stream deadline, RBAC fix). |
| `sigir/d11-a2-stage3-consolidated` | `b6ec23eee15cf45b3edce801a617fb614cad99e1` | 74 | D11-A.4 + topic listing & Colab-style fallback pills. |
| `sigir/d12-recovery` (merge `809a70a`) | `809a70a6434ee18fce65250b98207fa52b2ae8f1` | 80 | Initial D12 consolidated merge (`d12/retrieval-nlu` `ca99e52` + `d12/synthesis-citations` `b0fd195` + `d12/ui-3d` `12a0db6`). |
| `sigir/d12-recovery` (HEAD) | `fe8887c878e27f1770690236513f0f6c79c37d7c` | 83 | **LIVE ON `archipelago-sigir.vercel.app`**. Adds `0001769` (UI polish), `8555462` (urllib3 8s socket / 14s idle watchdog), `fe8887c` (Sources & Resources empty-href fix). |

### 1.3 Worktree Inventory & Drift Check

| Worktree / Clone Path | Checked-Out Ref | `.vercel` Link | Notes |
|---|---|---|---|
| `/home/pratay-karali/Desktop/archipelago` | `main` (`c0d90b8`) | `prj_yVvxBExHYiLa67oqnABK2vW9FfCS` (`archipelago` / UEM org) | **DO NOT DEPLOY OR MODIFY.** Linked to UEM production! |
| `/home/pratay-karali/Desktop/archipelago-sigir-demo` | `sigir/demo-2027` (`71271ec`) | `.vercel/cache` & `.vercel/dev` only (no `project.json`) | Has 2 untracked files: `docs/reports/D11_A_AUTHOR_EVALUATION_INSTRUCTIONS.md`, `docs/reports/D11_A_ENGINEERING_ISSUES.md`. |
| `/home/pratay-karali/.gemini/antigravity/worktrees/66c355ef-147d-4e8e-a8e2-037d4b340ff7/subagent-D11-A-2-Verification--36Q-Diagnostic---Stage-3-Consolidator-self-edf9d920` | `sigir/d12-recovery` (`fe8887c`) | `prj_BjRCpNfUItbG8BO26CIQbPhP1oi9` (`archipelago-sigir` / `sigir1`) | **Has 1 uncommitted modified file:** `ui/chat/landing.html` (66+/67- lines, not in `fe8887c`). Do not commit or mutate this worktree in D14.0. |
| `/home/pratay-karali/.gemini/antigravity/worktrees/archipelago/d14_scientific_recovery_stabilization` | `d14_scientific_recovery_stabilization` (`c0d90b8`) | None (safe) | Active D14.0 audit/contract workspace. |

---

## 2. D14 Integration Branch Strategy & Rollback Procedures

### 2.1 Mandatory Branch-Base Recommendation

> **RECOMMENDATION (CRITICAL):** D14.1–D14.8 implementation **MUST** base off **`sigir/d12-recovery` (`fe8887c878e27f1770690236513f0f6c79c37d7c`)**, NOT `main` (`c0d90b8`).

- **Why:** Building on `c0d90b8` would discard 83 commits (411 files, +86,868/-7,743 lines) including the root multi-service `vercel.json`, `ARCHIPELAGO_ACCESS_PROFILE=open_access`, HF revision pinning, Supabase staging passage loading, `research/d5_sigir_evaluation/` (absent on `main`, present on `sigir/d12-recovery`), D11 session/SSE/UX hardening, and D12 retrieval/synthesis/UI-3D fixes.
- **Why NOT merge `main` into `sigir/d12-recovery`:** The only 2 commits on `main` not in `sigir/d12-recovery` (`b9a462a`, `c0d90b8`) modify 65 legacy UI files and would create severe merge conflicts and regressions against D11/D12 UI improvements (`12a0db6`, `0001769`, `fe8887c`).

### 2.2 Controlled Integration Strategy

1. **Preserve immutable baselines:** Never rewrite, rebase, force-push, or delete `main`, `sigir/demo-2027`, `sigir/d12-recovery`, or tag `d11-a4-frozen`.
2. **D14.0 -> D14.1 Transition (Executed only after `@coordinator` approves D14.0 gate):**
   - Create a dedicated integration branch **`sigir/d14-recovery`** from `sigir/d12-recovery` (`fe8887c878e27f1770690236513f0f6c79c37d7c`):
     ```bash
     git branch sigir/d14-recovery fe8887c878e27f1770690236513f0f6c79c37d7c
     ```
   - Copy/commit the D14.0 audit & contract artifacts (`docs/reports/d14/*`) from `d14_scientific_recovery_stabilization` onto `sigir/d14-recovery` as the first D14 commit (`docs(d14.0): freeze audit, benchmark isolation, and integration contract`).
3. **Specialist Worker Branches:**
   - Each D14.1–D14.7 specialist works in an isolated `workspace:"share"` worktree on branch `d14/<specialist-slug>` branched from the latest gated `sigir/d14-recovery`.
   - Workers may ONLY modify files in their assigned ownership slice (Section 3).
   - `d14-integrator` merges each specialist branch into `sigir/d14-recovery` via `--no-ff` only after its unit/regression tests and `scripts/quality_gate.py` (scoped to modified files) pass.
4. **UI Mirror Sync Invariant:**
   - On `sigir/d12-recovery`, `host_inference/ui/` and `ui/chat/` are mirrored assets checked by UI contract tests. Any worker editing `host_inference/ui/<path>` MUST mirror the identical edit to `ui/chat/<path>` (verified by `d14-integrator` before merge).
5. **Pre-Deploy Guardrail (Every Deploy Command):**
   - Before any future D14 staging/SIGIR deploy, verify `.vercel/project.json` equals `projectId: "prj_BjRCpNfUItbG8BO26CIQbPhP1oi9"` and `orgId: "team_Ng6MKy7PiWsjDa0YAEZTVLku"` (`archipelago-sigir`). Abort immediately if `prj_yVvxBExHYiLa67oqnABK2vW9FfCS` (`archipelago` / UEM) is detected.

### 2.3 Verified Rollback Commands (D11 & D12)

All rollbacks target **ONLY** `archipelago-sigir` (`prj_BjRCpNfUItbG8BO26CIQbPhP1oi9`). Never run rollback commands in `/home/pratay-karali/Desktop/archipelago`.

#### Rollback to D12 Live Baseline (`fe8887c`)
```bash
# 1. Git: create clean rollback worktree from immutable D12 HEAD
git worktree add /tmp/archipelago-d12-rollback fe8887c878e27f1770690236513f0f6c79c37d7c
# 2. Verify Vercel project link is archipelago-sigir (prj_BjRCpNfUItbG8BO26CIQbPhP1oi9)
cat .vercel/project.json
# 3. Vercel instant rollback (preferred — zero rebuild) or protected redeploy + alias:
vercel rollback --scope sigir1
# Or explicit alias to known-good D12 deployment ID:
# vercel alias set <d12-deployment-url> archipelago-sigir.vercel.app --scope sigir1
```

#### Rollback to Initial D12 Consolidated Merge (`809a70a`)
```bash
git worktree add /tmp/archipelago-d12-initial-rollback 809a70a6434ee18fce65250b98207fa52b2ae8f1
# Verify projectId == prj_BjRCpNfUItbG8BO26CIQbPhP1oi9, then deploy & alias to archipelago-sigir.vercel.app
```

#### Rollback to Frozen D11-A.4 Baseline (`tag: d11-a4-frozen` / `3c72443`)
```bash
git worktree add /tmp/archipelago-d11-rollback d11-a4-frozen
# (Exact commit: 3c724431edd11e8b987e9150b7a526675cc6501f; or D11 Stage-3 consolidated: b6ec23eee15cf45b3edce801a617fb614cad99e1)
# Verify projectId == prj_BjRCpNfUItbG8BO26CIQbPhP1oi9, then deploy & alias to archipelago-sigir.vercel.app
# If D11-A1 DB rollback is ever required on Staging Supabase (edokbtmhztkhndmxetpy ONLY):
# Apply docs/reports/D11_A1_MIGRATION_ROLLBACK.sql against staging only.
```

---

## 3. Non-Overlapping File Ownership Map (D14.1–D14.8)

All paths below are relative to the `sigir/d14-recovery` repository root (based on `sigir/d12-recovery` `fe8887c`). **No two active workers may edit the same file concurrently.**

| Worker | Phase | Exclusive Owned Paths (Write Access) | Must NOT Touch |
|---|---|---|---|
| **`d14-corpus-ingestion`** | D14.1 | `archipelago/academic_automation/**`, `archipelago/inference/corpus_inventory.py`, `archipelago/inference/inventory_ssot.py`, `host_inference/hostapp/corpus_bootstrap.py`, `host_inference/hostapp/inventory_store.py`, `host_inference/engine/corpus_titles.py`, `host_inference/engine/inventory.py`, `host_inference/engine/ingestion_view.py`, `host_inference/hostapp/routes/ingest.py`, `scripts/corpus/**` (new D14 corpus scripts), `tests/unit/test_d14_corpus_*.py` | `okf/**`, `host_inference/engine/answer.py`, `host_inference/ui/**`, quarantined benchmark files (`D14_BENCHMARK_ISOLATION_CONTRACT.md`) |
| **`d14-okf-graph`** | D14.2 | `okf/**` (excluding `okf/gold/**` — read-only quarantine!), `archipelago/graph/**`, `host_inference/engine/graph.py`, `host_inference/engine/graph_semantics.py`, `host_inference/engine/nodes.py`, `host_inference/engine/pathfinder.py`, `host_inference/engine/multi_hop.py`, `host_inference/engine/multi_hop_concepts.py`, `host_inference/hostapp/routes/graph.py`, `tests/unit/test_d14_okf_graph_*.py` | `okf/gold/**`, `host_inference/engine/answer.py`, `host_inference/engine/llm.py`, `host_inference/ui/**`, original 610-concept baseline graph artifact (must write versioned D14 graph artifact alongside it) |
| **`d14-retrieval-nlu`** | D14.3 | `host_inference/engine/intent.py`, `host_inference/engine/route_logic.py`, `host_inference/engine/routing_constants.py`, `host_inference/engine/patterns.py`, `host_inference/engine/evidence_selection.py`, `host_inference/engine/catalogue.py`, `host_inference/engine/concept_foundations.py`, `host_inference/engine/docmap.py`, `host_inference/engine/route_special_books.py`, `tests/unit/test_d14_retrieval_nlu_*.py` | `host_inference/engine/answer.py`, `host_inference/engine/llm.py`, `host_inference/engine/math_guard.py`, `host_inference/ui/**`, `okf/**` |
| **`d14-synthesis-math`** | D14.4 | `host_inference/engine/answer.py`, `host_inference/engine/compose.py`, `host_inference/engine/compose_catalog.py`, `host_inference/engine/math_guard.py`, `host_inference/engine/reply_plan.py`, `host_inference/engine/reply_evidence.py`, `host_inference/engine/reply_templates.py`, `host_inference/engine/reply_templates.json`, `host_inference/engine/prompts/chat_reply.txt`, `host_inference/engine/source_answer_fixes.py`, `host_inference/engine/render.py`, `tests/unit/test_d14_synthesis_math_*.py` | `host_inference/engine/intent.py`, `host_inference/engine/evidence_selection.py`, `host_inference/engine/llm.py`, `host_inference/engine/citations.py`, `host_inference/engine/citation_format.py`, `host_inference/ui/**` |
| **`d14-reader-provenance`** | D14.5 | `host_inference/engine/citations.py`, `host_inference/engine/citation_format.py`, `host_inference/engine/links.py`, `host_inference/engine/provenance.py`, `host_inference/engine/evidence_export.py`, `host_inference/engine/access_profile.py`, `host_inference/hostapp/routes/reader.py`, `host_inference/hostapp/routes/library.py`, `host_inference/hostapp/page_fragments.py`, `host_inference/ui/reader.html`, `ui/chat/reader.html`, `host_inference/ui/js/06-open-book-or-unavailable.js`, `ui/chat/js/06-open-book-or-unavailable.js`, `host_inference/ui/js/07-open-page-viewer-modal.js`, `ui/chat/js/07-open-page-viewer-modal.js`, `host_inference/ui/js/15-inspector.js`, `ui/chat/js/15-inspector.js`, `tests/unit/test_d14_reader_provenance_*.py` | `host_inference/engine/answer.py`, `host_inference/engine/llm.py`, `host_inference/ui/js/08-*.js`, `host_inference/ui/auth_bridge.js` |
| **`d14-ux-followups`** | D14.6 | `host_inference/engine/followups.py`, `host_inference/engine/conversational.py`, `host_inference/engine/inventory_card.py`, `host_inference/ui/landing.html`, `ui/chat/landing.html`, `host_inference/ui/js/01--hide-welcome-with-transitio.js`, `host_inference/ui/js/02--kw-highlights.js`, `host_inference/ui/js/03-wrap-library-inventory-secti.js`, `host_inference/ui/js/04-start-new-chat.js`, `host_inference/ui/js/05-display-books.js`, `host_inference/ui/js/11-populate-topology.js`, `host_inference/ui/js/11a-topology-layout.js`, `host_inference/ui/js/19-draw-horizontal-svg.js`, `host_inference/ui/js/22-welcome-suggestions.js`, `host_inference/ui/js/23-followups-export.js` (+ exact mirrors under `ui/chat/js/`), `host_inference/ui/styles/13-d11-b-ux-readability.css`, `host_inference/ui/styles/14-d12-ui-3d.css` (+ mirrors under `ui/chat/styles/`), `tests/unit/test_d14_ux_followups_*.py` | `host_inference/ui/js/08-*.js`, `host_inference/ui/js/stream-*.js`, `host_inference/ui/auth_bridge.js`, `host_inference/ui/login.html`, `host_inference/hostapp/routes/auth.py`, `host_inference/hostapp/routes/chat.py`, `host_inference/engine/llm.py` |
| **`d14-streaming-perf`** | D14.7 | `host_inference/engine/llm.py`, `host_inference/engine/diagnostics.py`, `host_inference/cache_service.py`, `host_inference/remote_cache.py`, `host_inference/library_index.py` *(cold-start lazy-init/caching; coordinate schema changes with `d14-corpus-ingestion`)*, `host_inference/hostapp/factory.py`, `host_inference/hostapp/routes/auth.py`, `host_inference/hostapp/routes/chat.py`, `host_inference/hostapp/routes/pages.py`, `host_inference/hostapp/session_store.py`, `host_inference/hostapp/middleware.py`, `host_inference/hostapp/runtime_state.py`, `host_inference/hostapp/security.py`, `host_inference/ui/auth_bridge.js`, `ui/chat/auth_bridge.js`, `host_inference/ui/login.html`, `ui/chat/login.html`, `host_inference/ui/session-bridge.html`, `ui/chat/session-bridge.html`, `host_inference/ui/js/00-current-origin.js`, `host_inference/ui/js/00-state.js`, `host_inference/ui/js/08-send-message.js`, `host_inference/ui/js/08-send-request.js`, `host_inference/ui/js/08-stream-cleanup.js`, `host_inference/ui/js/08-stream-error.js`, `host_inference/ui/js/index.js`, `host_inference/ui/js/stream-markers.js`, `host_inference/ui/js/stream-support.js`, `host_inference/ui/js/storage-key.js` (+ exact mirrors under `ui/chat/js/`), `tests/unit/test_d14_streaming_perf_*.py` | `host_inference/engine/answer.py`, `host_inference/engine/intent.py`, `host_inference/engine/citations.py`, `host_inference/ui/js/15-inspector.js`, `host_inference/ui/js/22-*.js`, `host_inference/ui/js/23-*.js` |
| **`d14-independent-verifier`** | D14.8 | `tests/e2e/test_d14_*.py`, `docs/reports/d14/D14_VERIFICATION_REPORT.md`, `docs/reports/d14/D14_EVAL_RESULTS_*.json` (new D14-versioned eval outputs only) | **READ-ONLY** on all production code (`host_inference/**`, `host_research/**`, `okf/**`, `archipelago/**`, `ui/**`). Never edits code directly; files defects for owning worker to fix. Never overwrites historical D5–D12 eval artifacts or blank human evaluation fields. |
| **`d14-integrator`** | All | `vercel.json`, `host_inference/vercel.json`, `host_research/vercel.json`, `host_inference/hf_revision.py`, `host_inference/hostapp/config.py`, `host_inference/ui/index.html`, `ui/chat/index.html`, `requirements*.txt`, `pyproject.toml`, `docs/reports/d14/D14_INTEGRATION_CONTRACT.md`, merge conflict resolution across slices | Protected manuscript dirs, UEM production (`archipelago-blond.vercel.app`), `main` / `sigir/demo-2027` / `sigir/d12-recovery` history |

### 3.1 Cross-Slice Interface Contracts (Zero-Conflict Rule)

- **`host_inference/ui/index.html` (+ `ui/chat/index.html`):** Owned exclusively by `d14-integrator`. If `d14-ux-followups`, `d14-reader-provenance`, or `d14-streaming-perf` need a script/CSS tag or DOM hook in `index.html`, they submit a minimal patch spec on the board to `@d14-integrator`.
- **Chat SSE Payload Schema (`host_inference/hostapp/routes/chat.py` -> `host_inference/ui/js/08-*.js` & `15-inspector.js`):** Any new SSE event or metadata key (`latency_ms`, `provider`, `finish_reason`, `citation_kind`, `evidence_backed`) must be additive and backward-compatible. `d14-streaming-perf` owns the SSE transport/framing; `d14-reader-provenance` consumes citation fields in `15-inspector.js`.
- **Corpus & Graph Versioning (per `D14_BENCHMARK_ISOLATION_CONTRACT.md`):** Preserve `graph_v1_okf610` (`host_inference/fixtures/okf_graph.json`, `sha256=9818ac0e...2f76`) and `corpus_v2_d10_3025` (`sha256=93f6db39...e52`) untouched. `d14-corpus-ingestion` and `d14-okf-graph` must emit versioned `corpus_v3_d14` (`D14_CORPUS_V3_MANIFEST.json`) and `graph_v2_d14` alongside them.
- **Tier 1 Benchmark Quarantine (ALL D14.1–D14.7 workers):** Never read, tune on, or modify `research/d5_sigir_evaluation/{queries_heldout_50.json,qrels.tsv,passage_qrels.json,unjudged_qrels.json,human_annotation_worksheet.json,worksheets/*}` or `D10-S4` preliminary 6Q (`S4-*`). Approved exposed dev/regression suite: `D10-*` 36Q (`docs/sigir/D10_S3_ANSWERING_BEFORE_AFTER_36Q.csv`).

---

## 4. Phase-Gate Checklist (`D14.0 -> D14.8`)

No phase begins implementation until the preceding gate is explicitly marked **PASS** by `d14-integrator` and approved by `@coordinator`.

| Gate | Transition | Required Artifacts & Exit Criteria | Gate Owners |
|---|---|---|---|
| **Gate 0** | **D14.0 -> D14.1 & D14.2** | 1. `D14_RELEASE_IDENTITY_AUDIT.md`, `D14_BASELINE_MANIFEST.json`, `D14_CONSOLIDATED_DEFECT_REGISTER.csv`, `D14_REQUIREMENTS_TEST_TRACEABILITY.md`, `D14_SWARM_EXECUTION_CONTRACT.md` complete (`d14-forensic-audit`).<br>2. `D14_BENCHMARK_EXPOSURE_AUDIT.json` & `D14_BENCHMARK_ISOLATION_CONTRACT.md` complete with zero held-out leakage (`d14-benchmark-integrity`).<br>3. `D14_STREAMING_AUTH_DIAGNOSIS.md` complete (`d14-streaming-perf`).<br>4. `D14_INTEGRATION_CONTRACT.md` complete (`d14-integrator`).<br>5. `@coordinator` approves creating `sigir/d14-recovery` from `fe8887c` and importing `docs/reports/d14/*`. | `d14-integrator`, `@coordinator` |
| **Gate 1** | **D14.1 & D14.2 -> D14.3** | 1. `d14-corpus-ingestion` and `d14-okf-graph` branches merged into `sigir/d14-recovery` with zero file-ownership violations.<br>2. Original 610-concept / 3,025-passage / 43-doc baseline checksums remain untouched; D14 corpus/graph artifacts are separately versioned with SHA-256 manifests.<br>3. `pytest tests/unit/test_d14_corpus_*.py tests/unit/test_d14_okf_graph_*.py` + existing D10–D12 unit tests pass; `ruff check` & `scripts/quality_gate.py` clean on all modified files. | `d14-integrator`, `d14-benchmark-integrity` |
| **Gate 2** | **D14.3 -> D14.4, D14.5, D14.6, D14.7** | 1. `d14-retrieval-nlu` branch merged into `sigir/d14-recovery`.<br>2. Query NLU, domain routing, concept resolution, and passage selection regression tests (`test_d14_retrieval_nlu_*.py` + `test_d12_retrieval_nlu.py`) pass with zero benchmark quarantine violations.<br>3. Retrieval output contract frozen for downstream parallel wave (`D14.4` synthesis/math, `D14.5` reader/provenance, `D14.6` UX/follow-ups, `D14.7` streaming/auth/perf).<br>*(Note: If `@coordinator` authorizes an urgent D14.7 auth/chat-hang hotfix on `sigir/d14-recovery` in parallel with D14.1–D14.3, its file slice is already 100% disjoint from D14.1–D14.3 and may merge early under `d14-integrator` supervision.)* | `d14-integrator` |
| **Gate 3** | **D14.4–D14.7 -> D14.8** | 1. `d14-synthesis-math`, `d14-reader-provenance`, `d14-ux-followups`, and `d14-streaming-perf` all merged into `sigir/d14-recovery`.<br>2. `host_inference/ui/` <-> `ui/chat/` mirror sync verified 100% clean.<br>3. All D10, D11, D12, and D14 unit + integration test suites pass.<br>4. `ruff check`, `ruff format --check`, `scripts/quality_gate.py` (no banned patterns, files <= 500 lines), `bandit`, and `detect-secrets` pass on all D14-modified files.<br>5. Auth boundary tests (401/200) and sign-out -> sign-in + `/chat` load regression tests pass. | `d14-integrator` |
| **Gate 4** | **D14.8 -> Release Sign-Off** | 1. `d14-independent-verifier` completes independent verification on both frozen baseline (610 concepts / 3,025 passages / 43 docs) and D14 versioned artifacts without modifying production code.<br>2. `d14-benchmark-integrity` certifies zero contamination of the 50 held-out queries and 731-item human judgment pool.<br>3. All 36 D13 author-tested dev/regression queries and 93 defect register items have recorded pass/status evidence.<br>4. UEM isolation verified: `archipelago-blond.vercel.app` untouched (`f76c1c4`, `pearson_books: 40`), protected manuscript dirs untouched.<br>5. Only after explicit `@coordinator` / user approval: deploy `sigir/d14-recovery` to `prj_BjRCpNfUItbG8BO26CIQbPhP1oi9` (`archipelago-sigir.vercel.app`). | `d14-independent-verifier`, `d14-benchmark-integrity`, `d14-integrator`, `@coordinator` |
