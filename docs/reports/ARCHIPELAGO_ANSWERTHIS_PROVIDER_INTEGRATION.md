# ARCHIPELAGO — ANSWERTHIS PROVIDER INTEGRATION

## 1. Environment Availability
- **Status:** `ANSWERTHIS_NOT_CONFIGURED`
- Checked installed plugins (`list_plugin_accounts`) and MCP servers: no AnswerThis MCP server or plugin credential is available in this coding/runtime environment.
- Per policy, **zero AnswerThis results were fabricated or emulated**.

## 2. Implemented Architecture (`answerthis_adapter.py`)
Created `archipelago/scholarly/discovery/answerthis_adapter.py` with four explicit verification states:
- `ANSWERTHIS_API_VERIFIED`: Used when server-side `ANSWERTHIS_API_URL` and `ANSWERTHIS_API_KEY` are configured; routes requests through `ProviderReliabilityClient` with timeouts, caching, and rate limits (credentials are never exposed to frontend bundles, logs, or exports).
- `ANSWERTHIS_IMPORTED_VALIDATION`: `import_answerthis_export(raw_content, fmt)` parses externally exported AnswerThis JSON or CSV files into normalized `PaperRecord` entries with SHA-256 provenance.
- `ANSWERTHIS_NOT_CONFIGURED`: Returned cleanly when server credentials are absent.
- `ANSWERTHIS_UNAVAILABLE`: Returned on upstream HTTP/transport failure.

## 3. Independent Comparison Interface
- `compare_against_answerthis(archipelago_papers, answerthis_records)` computes DOI and normalized-title overlap without treating AnswerThis as an automatic ground-truth oracle, keeping provider disagreements visible.
- Unit-tested in `tests/unit/test_s5_relevance_and_metrics_repair.py::test_answerthis_adapter_unconfigured_and_import_comparison`.
