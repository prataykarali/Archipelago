# ADR 0005: KùzuDB Atomic Database Swaps and Read-Only Concurrency

## Status
Accepted

## Context
Archipelago relies on KùzuDB as its embedded columnar graph DBMS. Re-ingesting new documents or rebuilding graph relationships can take significant time. Attempting to write directly to an active production database while serving queries causes lock contention, database corruption, or user-facing latency spikes.

## Decision
1. **Staging Pipeline:** All document ingestion and graph construction operate on a dedicated staging database file (`okf_graph_staging.db`).
2. **POSIX Atomic Swap:** Once staging validation, schema verification, and Kahn DAG integrity checks pass completely, the staging database is swapped into production using atomic `os.replace`:
   ```python
   os.replace(staging_db_path, production_db_path)
   ```
   On POSIX systems, `os.replace` is an atomic filesystem operation.
3. **Read-Only Connections:** The inference engine connects to the production database with `read_only=True`:
   ```python
   db = kuzu.Database(production_db_path, read_only=True)
   ```
   This guarantees that multiple inference workers can execute concurrent graph queries without acquiring write locks or corrupting database pages.

## Consequences
- Zero-downtime updates when publishing new graph releases.
- Inference queries are completely isolated from ingestion writes.
- Write corruption risks during unexpected server crashes are eliminated.
