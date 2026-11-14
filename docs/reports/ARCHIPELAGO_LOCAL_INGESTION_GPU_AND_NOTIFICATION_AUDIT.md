# Archipelago — Local Ingestion, GPU Policy & Notification Audit

**Date:** 2026-11-14  
**Repository:** `prataykarali/Archipelago`  
**Branch:** `feature/s6-final-platform-integration`  
**Commit:** `179abd8` (local worker fixes landed in `d63c83b`)

---

## 1. Root Cause of Repeated Popups & Memory Pressure

- **Popup Source:** `archipelago-research-worker.service` (`systemd --user`, `active (running)`) executes `archipelago/scholarly/bridge/cli.py`, whose `_approve_gpu_request()` previously invoked `zenity --question --title="Archipelago research request" --text="Approve local research ingestion?..."` on every 15-second poll loop without preflight resource checks or a notification cap.
- **VRAM & RAM Exhaustion:** Live diagnostics showed two pinned Ollama models (`qwen3.5:0.8b` at `939 MB` VRAM and `lib-qwen:latest` at `615 MB` VRAM, both with `expires_at: 2319-02-24`) consuming `1691 MiB / 4096 MiB` VRAM on the RTX 2050 and pushing system RAM to `12616 MiB used` (`3075 MiB available`, `4050 MiB swap used`).

---

## 2. Implemented Controls

1. **Preflight Gate Before Popup (`archipelago/scholarly/bridge/cli.py`):**
   - `_preflight_check(job)` checks display availability, verified rights (`rights_verified` / non-restricted `rights`), free system RAM (`>= 3 GiB`), free disk (`>= 5 GiB`), Ollama model readiness, and GPU VRAM/occupancy (`MIN_FREE_VRAM_MIB = 1024`) **before** any `zenity` dialog is shown.
   - Failed preflight checks record `BLOCKED_RESOURCE` or `DEFERRED` cleanly with zero UI interruption.
2. **Notification Ledger & Daily Cap (`archipelago/scholarly/bridge/cli.py`):**
   - `NotificationLedger` (`~/.cache/archipelago/ingestion_notifications.json` or `ARCHIPELAGO_NOTIFICATION_LEDGER`) enforces:
     - Maximum **2** automatic popups per `Asia/Kolkata` calendar day
     - Minimum **8 hours** (`28800s`) cooldown between automatic popups
     - Per-job suppression on decline/defer and no re-prompting across polling loops
     - Consolidated `pending_count` prompt when multiple approved jobs wait
     - `manual_review=True` (`--manual-review`) remains unrestricted for explicit operator review.
3. **GPU Usage Policy Allowlist (`archipelago/ingestion/gpu_lease.py`, `archipelago/academic_automation/gpu.py`):**
   - `shared_gpu_lease(job_type=...)` enforces `ALLOWED_GPU_JOB_TYPES = {"academic_pdf_ingestion", "opac_linked_document_ingestion", "academic_concept_extraction", "academic_ocr_processing"}` and raises `GPUJobTypeRejected` for `chat`, `research_chat`, `scholarly_search`, `research_monitoring`, `excel_generation`, `ui_rendering`, `experimental_research`, or unlisted types.
4. **Safe VRAM Reclamation (`archipelago/scholarly/bridge/cli.py`, `archipelago/academic_automation/gpu.py`):**
   - `unload_ollama_model(model)` sends `{"model": model, "keep_alive": 0, "prompt": "", "stream": false}` to `http://127.0.0.1:11434/api/generate` in `finally` blocks after job completion, cancellation, failure, or timeout — never killing unrelated desktop/IDE processes.

---

## 3. Live Workstation Verification

- **Service Restarted:** `systemctl --user restart archipelago-research-worker.service` (`active (running)`, PID `1250011`).
- **Pinned Ollama Models Unloaded (`keep_alive: 0`):**
  - Unloaded `qwen3.5:0.8b` (`done_reason: unload`) and `lib-qwen:latest` (`done_reason: unload`).
  - `/api/ps` confirmed `{"models":[]}`.
- **Before vs. After Workstation Readings:**
  - **Before:** `Mem: 15691 total, 12616 used, 3075 available, Swap: 4050 used`; GPU `1691 MiB / 4096 MiB` used.
  - **After:** `Mem: 15691 total, 3999 used, 8193 free, 11692 available, Swap: 519 used` (**+8.6 GiB RAM reclaimed**, RTX 2050 powered down cleanly).
- **Automated Tests:**
  - `ruff check archipelago/scholarly/bridge/cli.py archipelago/ingestion/gpu_lease.py archipelago/academic_automation/gpu.py tests/unit/test_research_worker_bridge.py tests/unit/test_s4_academic_automation.py`: `All checks passed!`
  - `pytest tests/unit/test_research_worker_bridge.py tests/unit/test_s4_academic_automation.py -q`: **51 passed, 0 failed**.
