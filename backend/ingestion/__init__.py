"""Document ingestion, section-aware chunking, and background worker queue."""
from __future__ import annotations

from archipelago.ingestion.pdf_chunk import (
    chunk_document_section_aware,
    extract_pdf_pages_with_metadata,
)
from ingestion_jobs import JobRecord, JobStatus, JobStore, job_store
from ingestion_worker import GraphLock, IngestionWorker, get_worker

__all__ = [
    "GraphLock",
    "IngestionWorker",
    "JobRecord",
    "JobStatus",
    "JobStore",
    "chunk_document_section_aware",
    "extract_pdf_pages_with_metadata",
    "get_worker",
    "job_store",
]
