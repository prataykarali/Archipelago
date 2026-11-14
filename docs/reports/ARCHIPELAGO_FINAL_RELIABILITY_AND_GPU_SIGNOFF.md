# Archipelago — Final Reliability, GPU Resource & Production Stabilization Signoff

**Repository:** `prataykarali/Archipelago` (`feature/s6-final-platform-integration`)  
**Git SHA:** `8b4c1bc5ad3836102d3f77456a67e00afb77640b`  
**Main Production (`archipelago-6383`):** `https://archipelago-blond.vercel.app/` (deployment `21oPzNC73y622ZCymNHrc6FHvP2k`)  
**Librarian Production (`shinaura`):** `https://archipelago-librarian.vercel.app/` (requires `shinaura` team authorization to deploy updated `host_research/` build)

---

## 1. Subsystem Signoff Matrix

| Subsystem | Verdict | Evidence Summary |
| --- | --- | --- |
| **GPU & Ingestion Policy** | **PARTIAL** | Repo `keep_alive=-1` removed (`gpu_recover.sh`, `start_soference.sh`); `cli.py` fails closed on missing/disallowed `job_type`; `62 passed` tests; Ollama load/unload verified cleanly. Host `nvidia-smi` returned exit `6` (GPU0 off bus on workstation) and user systemd units (`ollama.service`, `archipealgo.service`) still set `OLLAMA_KEEP_ALIVE=-1`. |
| **Automated Regression Suite** | **PASS** | All `11` failing tests inspected & resolved (including genuine `\bos\b` bug in `compose_catalog.py`). Combined suite: **`190 passed, 0 failed`**. |
| **Academic Chat Generalization** | **PASS** | 18 prior partial/fail re-check: `13 PASS, 5 PARTIAL, 0 FAIL`; fresh 30-question holdout (`fresh_holdout_benchmark.json`): **`29 PASS, 1 PARTIAL, 0 FAIL` (`96.7%`)**; XKIRO `100%` invoked on substantive routes. |
| **Chat Latency** | **PASS** | `--local-flask` instrumented `stage_timings_ms`: `p50` improved **`9.322s -> 0.901s`**, `p95` improved **`16.513s -> 1.500s`** (via skipping unnecessary `enrich_with_research` Supabase round-trips on non-research queries). |
| **OPAC, Graph & Chat UI** | **PASS (Main) / PARTIAL (Librarian)** | Live Playwright on `archipelago-blond.vercel.app`: WCAG AA `>= 9.85:1`, `0` `/academic_light.css` 404s, Bezier edges + arrows, node/edge inspectors, Explore/Back, OPAC, Research, Chat + inline graph card, mobile `390×844` zero overflow. `archipelago-librarian.vercel.app` awaits `shinaura` deploy. |
| **Security & Quotas** | **PASS** | Untrusted `X-Forwarded-For` rate-limit bypass fixed (`security.py` + `test_rate_limit_proxy_headers.py`); student `10/hr` quota, faculty/librarian roles, S4 human review preserved. |

---

## 2. P0 — GPU Memory, Ingestion Ownership & Popup Verification

- **Repo Fixes:**
  - `scripts/ops/gpu_recover.sh`: Removed `"keep_alive": -1` warm-pin curl; recovery/boot now unloads any loaded/CPU-stuck runner (`"keep_alive": 0` to `/api/generate`) and starts web services without pinning models.
  - `scripts/ops/start_soference.sh`: Removed `OLLAMA_KEEP_ALIVE=-1` and `"keep_alive": -1` warm ping (`bash -n` OK; `rg` confirms zero `keep_alive=-1` in repo).
  - `archipelago/scholarly/bridge/cli.py`: Removed `job.get("job_type") or "academic_pdf_ingestion"` fallback; added `validate_gpu_job_type(...)` failing closed (`status="failed"`, `stage="GPU_POLICY_REJECTED"`) before preflight or `zenity` consent for missing/empty/disallowed jobs (`chat`, `research_chat`, `scholarly_search`, `research_monitoring`, `excel_generation`, `ui_rendering`, `experimental_research`, `unapproved_gpu_job`).
- **Host / Service Measurements:**
  - `nvidia-smi`: exit `6` (`Unable to determine the device handle for GPU0: 0000:01:00.0: Unknown Error` — RTX 2050 currently off bus on host, so on-device VRAM/compute PIDs could not be read).
  - `/proc/meminfo` & `ollama ps`:
    - Idle (`serve.sh status`: `inference :5151`, `graph :5150`, `chat :5152`, `ollama :11434` all `UP`): `MemAvailable: 6,236,896 kB`, `ollama ps` empty.
    - Active `academic_pdf_ingestion` lease (`qwen3.5:0.8b`, `1.1 GB`, `100% CPU`): `MemAvailable: 5,782,312 kB`.
    - After completion (`unload_ollama_model -> True`): `ollama ps` empty, `MemAvailable: 7,162,224 kB`.
    - After simulated failure (`RuntimeError` in lease): `ollama ps` empty, `MemAvailable: 6,906,908 kB`.
  - **Host systemd note:** `~/.config/systemd/user/ollama.service` and `archipealgo.service` still have `Environment=OLLAMA_KEEP_ALIVE=-1` outside repo control.
- **Popup & Ingestion Tests (`tests/unit/test_research_worker_bridge.py`, `tests/unit/test_s4_academic_automation.py`):** `62 passed, 1 warning` — verifies 2/day `Asia/Kolkata` prompt cap, >= 8h (`28800s`) spacing, preflight failure blocking `zenity` (`BLOCKED_RESOURCE`), decline suppression, manual queue review, `unload_ollama_model` on completion/failure, and mandatory S4 human approval.

---

## 3. P1 — 11 Regression Test Dispositions & Combined Suite

- **9 Obsolete S1/S2a Assertions Updated:**
  - `test_host_intent_routing.py::test_graph_reply_exposes_anchor_prerequisites_and_citations` & `test_s1_intent_routing.py::test_research_topic_has_citations_and_date_coverage_disclosure`: updated `render_graph=False` -> `True` (S6 inline chat graph cards).
  - `test_s1_intent_routing.py::test_library_inventory_omits_unsupported_claims`: updated `"central library"` -> `"not verified"` + `"uemk-opac.l2c2.co.in"`.
  - `test_s2a_cross_domain_qa.py`: added `MULTI_CONCEPT` to 3 Class A allowed routes; updated 3 Class B table header strings (`Author`/`Available`); updated Class C `"mid-2024"` -> `"corpus date coverage"` + `"2024"`.
- **2 Genuine Regression Failures Fixed:** `test_class_b_library_inventory_tables[OS]` and `test_s2a_5_turn_sequential_flow` exposed `host_inference/engine/compose_catalog.py` missing word-boundary `\bos\b` matching (`library_inventory_reply` fell back to unrelated books). Fixed in `compose_catalog.py`.
- **Combined Suite Verification:** `PYTHONPATH=.:host_inference pytest -q ...` across all 16 unit test files -> **`190 passed, 0 failed`**.

---

## 4. P1 — Academic Chat Generalization, Fresh Holdout & Latency

- **Root-Cause Fixes:**
  - `host_inference/engine/route_logic.py`: Excluded `PAPER_LOOKUP_RE` from `BOOK_PAGE`, broadened `PAPER_LOOKUP_RE`, added `_CAPABILITY_BROAD_RE`, added `_normalize_query_for_graph` + `_fallback_graph_hits` (resolving `H005`, `H006`, `Q108`, `H015`, `Q088` to `GRAPH_SYNTHESIS`), and added `_EXPLOIT_INTENT_RE`.
  - `host_inference/hostapp/routes/chat.py` & `archipelago/inference/synthesis/streaming.py`: Suppressed unsolicited `Reading order / Time/priority` headers on conceptual queries, skipped `enrich_with_research` Supabase round-trips when not needed, and added `stage_timings_ms`.
- **Accuracy Results:**
  - Original 128-question baseline (`domain_benchmark_results.json`): `113 PASS, 15 PARTIAL, 0 FAIL` (20 holdouts: `15 PASS, 5 PARTIAL`).
  - Re-verification of 18 prior partial/fail/spot-check cases: **`13 PASS, 5 PARTIAL, 0 FAIL`** (remaining 5 partials are valid XKIRO `GENERAL_EXPLANATION` answers on subtopics without standalone graph nodes).
  - **Fresh 30-Question Holdout (`artifacts/validation/fresh_holdout_benchmark.json`):** **`29 PASS, 1 PARTIAL, 0 FAIL` (`96.7%` PASS)**, `0` unsolicited `Reading order` headers.
- **Latency (`artifacts/validation/latency_profile.json`):**
  - Before: `p50 = 9.322s`, `p95 = 16.513s`, `max = 24.153s`.
  - After (`--local-flask`): `p50 = 0.901s`, `p95 = 1.500s`, `max = 6.097s` (`intent_and_graph_ms p50/p95 = 12.1 / 113.2 ms`, `provider_ttft_ms p50/p95 = 865.8 / 1484.4 ms`).

---

## 5. Remaining Limitations

1. **Librarian `shinaura` Vercel Deployment:** Requires `shinaura` team authorization to deploy `host_research/` (`8b4c1bc`) to `https://archipelago-librarian.vercel.app/`.
2. **Workstation GPU0 Hardware State & User Systemd Units:** Host `nvidia-smi` returned exit `6` (GPU0 off bus), and `~/.config/systemd/user/{ollama,archipealgo}.service` retain `OLLAMA_KEEP_ALIVE=-1`.
3. **Standalone Graph Nodes:** `5` subtopics (`Q012`, `Q014`, `Q054`, `Q074`, `Q076`) lack standalone nodes in `okf_graph.json`, so they route cleanly to XKIRO `GENERAL_EXPLANATION` without local catalog citations.
