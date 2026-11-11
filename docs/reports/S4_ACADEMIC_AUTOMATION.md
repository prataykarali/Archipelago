# S4 academic catalog automation validation

Date: 2026-11-11. Scope: the existing local checkout and UEM Kolkata OPAC connector. This report records the code and checks; it does not authorize production graph publication.

## Source reconciliation

The persistent ledger is `data/academic_automation/state.sqlite3` (ignored runtime data). A live `sync` and an identical repeat ran against the configured UEM Kolkata OPAC URL, the authorized local Koha export, Pearson bookshelf metadata, and the institutional repository feed.

| Provider | First observed records | Repeated run | Availability claim |
| --- | ---: | ---: | --- |
| Koha export | 109 | 109 unchanged | Catalog snapshot; not current stock |
| Pearson bookshelf | 40 | 40 unchanged | Licensed metadata only |
| UEM Kolkata OPAC arrivals | 20 | 20 unchanged | Arrival metadata only |
| Institutional repository | 0 strong catalog matches | 0 | No full text eligibility inferred |

The dashboard reports 169 provider records and preserves provider provenance even when ISBNs match. The repeat creates no new record versions. Failed or empty responses do not withdraw prior records. Withdrawal requires an explicit verified action. The OPAC check covers the existing arrivals connector, not the entire live OPAC catalog or current item availability.

## Graph before and after

| Artifact | Before S4 sync | After S4 sync |
| --- | ---: | ---: |
| Canonical Kùzu concepts | 610 | 610 |
| Canonical documents | 79 | 79 |
| Canonical chunks | 808 | 808 |
| Canonical typed concept edges | 1,988 | 1,988 |
| Exported graph JSON nodes | 610 | 610 |
| Exported graph JSON edges | 1,988 | 1,988 |
| Canonical DB SHA-256 | `df3943eeebd6a541ba83dde0cb7f0ed606a46deb40aecc9ff3db4d7888923cc8` | same |

No eligible content was queued from these sources, so no extraction, GPU execution, or production graph publication occurred. The publication path was tested with staged fixtures and a simulated failure; it requires a named local reviewer before swapping a validated graph.

## GPU and resource policy

Academic extraction uses the existing configured OKF/Ollama model (`lib-qwen:latest` unless locally configured otherwise). It never selects a second model for the academic job. The academic worker takes a local file lease. The existing research worker in this checkout also takes that lease, but its source is part of the separate uncommitted research pipeline and is not in this S4 commit. The academic worker rejects another loaded Ollama model or an unrelated NVIDIA compute process before starting and checks occupancy during progress callbacks. The local operator may approve one job, grant a revocable 24-hour trusted-open-content class, choose CPU, defer, or cancel. A job without a valid right, model availability, and consent remains queued. The current live GPU probe returned 14/4096 MiB, 0% utilization, no loaded models, and no compute process; it was not used for extraction.

The worker caps candidate file size at 100 MiB, extraction at 40 pages, and processing at one hour. It serializes jobs, applies retry backoff and dead-letter status, and checks cancellation at progress boundaries. The systemd daily sync and local worker polling units are supplied but not enabled by this change.

## Evidence and tests

- `PYTHONPATH=host_inference:. python3 -m pytest -q tests/unit/test_s4_academic_automation.py tests/unit/test_research_worker_bridge.py tests/integration/test_s4_academic_dashboard.py`: 28 passed.
- Targeted Ruff lint and format checks: passed.
- Local browser validation: 9 dashboard cards, 4 source rows, durable state rendered; see `artifacts/validation/s4-academic/dashboard.png`.
- Repository-wide quality gate: fails on pre-existing Ruff files, hundreds of baseline strict typing errors, and 8 other oversized files. The new S4 `store.py` is 400 lines, within the configured size gate.

## Known limits

No openly licensed full-text candidate was verified from the live catalog, so actual GPU extraction and post-publication academic chat freshness could not be live-tested. The institutional repository match requires a strong title match and rights review; its current live match count is zero. The public OPAC check uses the arrivals feed and cannot certify real-time holdings. An external GPU program can start after an occupancy probe; the worker detects that on its next progress callback and aborts, while the shared lease serializes Archipelago workers immediately. The full repository quality gate remains red from the existing checkout baseline and must pass before merge.
