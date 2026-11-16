# ARCHIPELAGO — RESEARCH RANKING, METRICS & DEPLOYMENT STATUS

## 1. Grounded Ranking & Exploration Modes
- Default ordering remains `newest` (`publication_date_desc`) applied **after** semantic relevance filtering.
- Supported sort modes: `newest`, `relevance`, `foundational` (citation count + FWCI tie-break), `citations`, `citations_per_year`, `fwci`, `open_access`, `evidence_completeness`, `provider` — missing values always sorted last, never zero-filled.
- UI (`papers.html` + `research_intelligence.js`) exposes three exploration tabs: **Papers**, **Authors**, and **Publications & Sources**.

## 2. Fixed Coverage Audit & Citation Graph Math
- `Coverage_Audit` (`workbook_extra.py`): `"Papers: References Populated"` now uses `refs_pop` (count of papers with >=1 reference) over `n_papers`, guaranteeing `0.0% <= Coverage % <= 100.0%` (verified `max = 95.0%` on repaired `Liquid Neural Networks` workbook).
- `graph.py` `coverage_report` separates `raw_reference_count` (166), `identifier_matched_count` (166), `existence_verified_count` (2), `in_collection_edges` (2), `externally_resolved_edges` (164), `unresolved_count` (0), and `verification_coverage` (`0.012`).

## 3. Deliverables & Verification
- **Repaired 14-Sheet Workbook:** `artifacts/validation/Archipelago_Liquid_Neural_Networks_Repaired.xlsx` (and artifact directory copy)
- **Unit Tests:** `38 passed, 1 warning` (`test_s5_research_intelligence.py`, `test_s5_enrichment.py`, `test_s5_multisource_providers.py`, `test_s5_multi_provider_enrichment.py`, `test_s5_relevance_and_metrics_repair.py`)
- **Runtime Sync:** `python3 scripts/ops/sync_s5_host_runtime.py --check` exited `0`
- **Branch:** `fix/research-pipeline-relevance-and-metrics`
