# Archipelago Data Sources

This document details the sources of data ingested into the Archipelago system, the methods of ingestion, and the current operational state of these pipelines.

## 1. Academic Content Sources

*   **Pearson eLibrary (Institutional Subscription)**:
    *   Metadata for 40 books is stored in `data/catalogs/pearson_bookshelf.json`.
    *   **Current State**: 18 books are fully populated with UUIDs; 22 books need UUID population.
*   **HuggingFace Datasets**:
    *   `Prataykarali/Library_books`: CURRENT production corpus.
    *   `Prataykarali/graphier`: TARGET new graph dataset, needs population.
*   **Local PDFs**: Stored in the `/pdfs/` directory.
*   **User Uploads**: Ingested papers via librarian upload.

## 2. Library Catalog Sources

*   **Koha OPAC**: `http://uemk-opac.l2c2.co.in`
    *   Currently serves as a static catalog reference; no live API integration exists yet.
*   **ODS Spreadsheets** (at repo root):
    *   `JOURNALS TITLES AND ISSUE COUNTS-reportresults.ods` (15KB)
    *   `SUBJECT-WISE TITLE COUNT-reportresults.ods` (two versions: 112KB and 19KB)
    *   `Titles List with specified keyword-reportresults.ods` (12KB)
*   **CSV Imports**: Local CSV imports are processed via `library_inventory.py`.

## 3. External Services

*   **Apify**: Used for web data extraction via actors.
    *   Cost-capped at $1.00/run via the `APIFY_MAX_TOTAL_CHARGE_USD` environment variable.
*   **Pearson Portal**: `https://elibrary.in.pearson.com/`
*   **HuggingFace API**: Used for dataset download and upload synchronization.

## 4. Ingestion Pipeline Status (Honest Assessment)

*   **PDF Ingestion**: **WORKING**. Uses PyMuPDF for section-aware chunking.
*   **OCR**: **WORKING**. Uses Tesseract, primarily for scanned library material.
*   **ODS/CSV/Spreadsheet Ingestion**: **WORKING**. Uses `defusedxml` with a validated schema.
*   **lib-qwen OKF Extraction**: **EXISTS (Needs Validation)**. `accuracy.json` shows 100% on 2 test chunks, but this is too small a sample to prove production readiness.
*   **Pearson Extraction via Apify**: **CONFIGURED (Untested)**. The `apify_source.py` script exists but has not been tested at scale.
*   **Graph Fusion & Deduplication**: **WORKING**. Employs Kahn DAG validation and idempotent merge logic.
*   **HuggingFace Sync**: **EXISTS**. Scripts available at `scripts/sync_to_graphier.py` and `scripts/sync_to_hf_library.py`.
*   **Automated Graph Population**: **PARTIAL**. Scripts exist, but there is no cron/daemon for continuous population.

## 5. Data Quality Assessment

*   **Island Nodes**: The graph contains "island nodes" (e.g., PCA) with 0 edges.
*   **Empty Summaries**: Some concepts have empty summaries.
*   **Pearson Bookshelf Incomplete**: The bookshelf is only 55% complete (22 out of 40 books are missing UUIDs).
*   **Evaluation Deficits**: `accuracy.json` evaluated on only 2 chunks — not representative of production requirements. No systematic ingestion model benchmark has been run.

## 6. Compliance & Legal

*   **Pearson Compliance**: Only metadata, structure, and index information are extracted. **NEVER** extract or store full-text copyrighted content.
*   **HuggingFace Compliance**: Only legally distributable graph, metadata, and index content should be uploaded.
*   **Fetch Controls**: `ARCHIPELAGO_FETCH_ALLOWLIST` controls permitted outbound fetch domains. The default policy is **DENY-ALL**.
*   **Audit Logging**: All fetch operations are logged to `ARCHIPELAGO_FETCH_AUDIT_LOG`.
