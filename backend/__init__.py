"""Archipelago Core Backend Package.

Organized into clean, production-oriented modules:
- routing: Deterministic 6-contract routing & graph-render protocol
- intent: Fast intent classification, greetings, & security intercept
- retrieval: Dense Snowflake Arctic vectors & lexical hybrid search
- graph: KùzuDB graph engine & topological traversal
- synthesis: Grounded synthesis & multi-model LLM gateway
- citations: Page-level deep linking (#page=N) & provenance
- personalization: Prerequisite paths & learning roadmaps
- catalog: Physical library inventory, Koha ODS, & Pearson eLibrary
- authentication: Supabase JWT auth & institutional credential gateway
- ingestion: Section-aware chunking & background worker queue
- OCR: Local OCR extraction for scanned indices
- quiz: 4-option diagnostic MCQs & adaptive evaluation
- caching: Multi-tier LRU query cache & probabilistic filters
- telemetry: P50/P90/P99 latency & performance monitoring
"""
from __future__ import annotations

from . import (
    OCR,
    authentication,
    caching,
    catalog,
    citations,
    graph,
    ingestion,
    intent,
    personalization,
    quiz,
    retrieval,
    routing,
    synthesis,
    telemetry,
)

__all__ = [
    "OCR",
    "authentication",
    "caching",
    "catalog",
    "citations",
    "graph",
    "ingestion",
    "intent",
    "personalization",
    "quiz",
    "retrieval",
    "routing",
    "synthesis",
    "telemetry",
]
