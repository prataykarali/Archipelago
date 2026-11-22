# 06_SCRAPING_SPEC.md: Web Scraping & Data Extraction Pipeline

This document specifies the web scraping, crawling, and data extraction pipelines for the Archipelago project.

## 1. Compliance-First Architecture
All outbound network fetches are strictly controlled by a compliance-first architecture.
- **DENY-ALL Default**: `archipelago/ingestion/fetch_policy.py` acts as a gatekeeper, denying outbound requests by default.
- **Allowlist**: `ARCHIPELAGO_FETCH_ALLOWLIST` environment variable (comma-separated hosts/suffixes) defines allowed domains.
- **Audit Log**: `ARCHIPELAGO_FETCH_AUDIT_LOG` maintains an append-only JSONL record of every fetch for auditing.
- **User Agent**: Must use `'ArchipelagoLibraryBot/1.0 (+institutional graph)'`.
- **Robots.txt**: Adherence to `robots.txt` is strictly required.

## 2. Pearson eLibrary Extraction Pipeline
- **Source**: [`archipelago/ingestion/pearson_connector.py`](file:///home/pratay-karali/Desktop/archipelago/archipelago/ingestion/pearson_connector.py)
- **Target**: Institutional subscription content only.
- **Data Extracted**: Book metadata, cover/front matter, index pages, chapter structure, page metadata, concept relationships.
- **Pipeline**: Pearson subscription → Extractor → Book metadata → Chapter/page structure → Concept extraction → OKF graph → Graph DB → HF
- **Credentials**: `PEARSON_PORTAL_URL`, `PEARSON_ACCOUNT_USERNAME`, `PEARSON_ACCOUNT_PASSWORD` (Environment variables; NEVER committed).
- **STRICT Rule**: Never upload full-text copyrighted content to public repositories.
- **Current State**: `pearson_connector.py` exists (6.5KB), connects to Pearson portal, but cold redirect fails without session cookie.

## 3. Apify Integration
- **Source**: [`archipelago/ingestion/apify_source.py`](file:///home/pratay-karali/Desktop/archipelago/archipelago/ingestion/apify_source.py) (9.5KB)
- **Cost Control**: `APIFY_TOKEN` + `APIFY_MAX_TOTAL_CHARGE_USD` (default $1.00 hard cap).
- **Used For**: Source discovery Actors.
- **Pipeline**: Actor results → fetch_policy gate → content extraction → OKF pipeline.
- **Current State**: EXISTS, configured, but untested at scale.

## 4. HuggingFace Data Sync
- **Download**: [`scripts/download_pilot_corpus.py`](file:///home/pratay-karali/Desktop/archipelago/scripts/download_pilot_corpus.py) (35KB) — downloads corpus from `HF_DATASET_REPO`.
- **Upload Graph**: [`scripts/sync_to_graphier.py`](file:///home/pratay-karali/Desktop/archipelago/scripts/sync_to_graphier.py) (5.8KB) → `Prataykarali/graphier`
- **Upload Library**: [`scripts/sync_to_hf_library.py`](file:///home/pratay-karali/Desktop/archipelago/scripts/sync_to_hf_library.py) (7.6KB) → `Prataykarali/Library_books`
- **Auth**: `HF_TOKEN` environment variable.
- **Bootstrap**: [`host_inference/hostapp/corpus_bootstrap.py`](file:///home/pratay-karali/Desktop/archipelago/host_inference/hostapp/corpus_bootstrap.py) — downloads corpus at boot if missing.

## 5. Koha OPAC Integration
- **Target**: `http://uemk-opac.l2c2.co.in`
- **Current State**: NOT BUILT — currently using static catalog data from ODS exports.
- **Needed**: Live OPAC API integration for real-time availability.
- **Data Format**: ODS spreadsheets currently hand-exported and ingested.

## 6. Automated Population Pipeline
- **Scripts**: [`scripts/run_master_library_ingest.py`](file:///home/pratay-karali/Desktop/archipelago/scripts/run_master_library_ingest.py) (48KB — the master orchestrator).
- **Batch Scripts**: `run_batch1_pearson_gpu_ingest.py`, `run_compliant_pilot_ingest.py`, `run_hf_compliant_gpu_ingest.py`, `run_local_gpu_ingest.py`.
- **Idempotency**: Graph append must never create duplicate nodes/edges.
- **Validation**: [`scripts/validate_graph.py`](file:///home/pratay-karali/Desktop/archipelago/scripts/validate_graph.py) (7.4KB).
- **Current State**: Scripts exist but no automated cron/scheduler is in place.
