"""Parallel scholarly discovery with explicit live and fallback provenance.

Concurrently harvests academic publications, library catalogs, and institutional holdings
across 4 targets:
1. arXiv (https://export.arxiv.org)
2. UEMK Koha OPAC (http://uemk-opac.l2c2.co.in)
3. IEM CRP Digital Library (https://www.iemcrp.com)
4. Google Scholar (https://scholar.google.com)

Features:
- Parallel fetch via ThreadPoolExecutor(max_workers=4)
- Direct integration with api-anything + resilient native adapter fallbacks
- Deduplication and canonicalization into OKF v1.0.0 paper records
- Discovery manifest generation for pages and downstream inference
- No automatic SLM ingestion; discovery must be reviewed before that stage
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import logging
from pathlib import Path
import time
from typing import Any

from archipelago.scholarly.contracts.okf_models import PaperRecord
from archipelago.scholarly.discovery.anything_api_bridge import AnythingApiBridge
from archipelago.scholarly.discovery.arxiv_adapter import ArXivAdapter
from archipelago.scholarly.discovery.canonicalizer import Canonicalizer
from archipelago.scholarly.discovery.iemcrp_adapter import IEMCRPAdapter
from archipelago.scholarly.discovery.opac_adapter import OPACAdapter
from archipelago.scholarly.discovery.openalex_adapter import OpenAlexAdapter
from archipelago.scholarly.discovery.scholar_adapter import GoogleScholarAdapter
from archipelago.scholarly.discovery.scholar_deeplink import generate_scholar_url

from .source_fetch import SourceFetchMixin

logger = logging.getLogger("archipelago.scholarly.harvester")

ROOT = Path(__file__).resolve().parents[3]
CATALOGS_DIR = ROOT / "data/catalogs"
LIVE_MANIFEST_PATH = CATALOGS_DIR / "live_scholarly_manifest.json"
HARVEST_SUMMARY_PATH = CATALOGS_DIR / "latest_harvest_summary.json"


class ParallelHarvester(SourceFetchMixin):
    """Institutional-grade concurrent harvester for 4 scholarly sources."""

    def __init__(self, use_api_anything: bool = True):
        self.use_api_anything = use_api_anything
        self.bridge = AnythingApiBridge()
        self.canonicalizer = Canonicalizer()

        # Dedicated native adapters
        self.arxiv_adapter = ArXivAdapter()
        self.opac_adapter = OPACAdapter()
        self.iemcrp_adapter = IEMCRPAdapter()
        self.scholar_adapter = GoogleScholarAdapter()
        self.openalex_adapter = OpenAlexAdapter()

    # -------------------------------------------------------------------------
    # Target 1: arXiv
    # -------------------------------------------------------------------------
    def harvest_parallel(
        self, query: str, limit_per_source: int = 5, *, persist: bool = True
    ) -> dict[str, Any]:
        """Discover records and links concurrently, without creating training data."""
        t_start = time.time()
        logger.info("Starting 4-way parallel harvest for query: '%s'", query)

        source_results: dict[str, list[dict[str, Any]]] = {
            "arxiv": [],
            "opac": [],
            "iemcrp": [],
            "google_scholar": [],
            "openalex": [],
        }

        # Concurrently dispatch 4 worker threads
        tasks = {
            "arxiv": lambda: self.fetch_arxiv(query, limit=limit_per_source),
            "opac": lambda: self.fetch_opac(query, limit=limit_per_source),
            "iemcrp": lambda: self.fetch_iemcrp(query, limit=limit_per_source),
            "google_scholar": lambda: self.fetch_scholar(query, limit=limit_per_source),
            "openalex": lambda: self.fetch_openalex(query, limit=limit_per_source),
        }

        with ThreadPoolExecutor(
            max_workers=len(tasks), thread_name_prefix="ArchipelagoHarvester"
        ) as executor:
            future_to_src = {executor.submit(fn): src for src, fn in tasks.items()}
            for future in as_completed(future_to_src):
                src = future_to_src[future]
                try:
                    res = future.result()
                    source_results[src] = res
                    logger.info("Source '%s' completed with %d records.", src, len(res))
                except Exception as e:
                    logger.error("Source '%s' failed in parallel thread: %s", src, e)
                    source_results[src] = []

        live_candidates = [
            item
            for items in source_results.values()
            for item in items
            if item.get("retrieval_mode") == "live" and item.get("source") != "iemcrp"
        ]
        fallback_resources = [
            item
            for items in source_results.values()
            for item in items
            if item.get("retrieval_mode") != "live" or item.get("source") == "iemcrp"
        ]
        canonical_records = self.canonicalizer.canonicalize_candidates(live_candidates)

        # Enrich with verified Google Scholar deep-links if missing
        for item in canonical_records:
            paper: PaperRecord = item["paper"]
            if not item.get("scholar_verification_url"):
                first_author = paper.authors[0].name if paper.authors else None
                item["scholar_verification_url"] = generate_scholar_url(paper.title, first_author)

        elapsed = time.time() - t_start
        source_status = {}
        for source, items in source_results.items():
            live_count = sum(item.get("retrieval_mode") == "live" for item in items)
            fallback_count = len(items) - live_count
            source_status[source] = {
                "mode": "live"
                if live_count
                else "fallback"
                if fallback_count
                else "link_only"
                if source == "google_scholar"
                else "unavailable",
                "live_records": live_count,
                "fallback_records": fallback_count,
                "content_type": "navigation_links"
                if source in {"iemcrp", "google_scholar"}
                else "catalog_books"
                if source == "opac"
                else "papers",
            }
        source_status["google_scholar"]["verification_url"] = self.scholar_adapter.verification_url(
            query
        )
        manifest = self._build_manifest(query, canonical_records, fallback_resources, source_status)
        if persist:
            self._update_live_manifests(manifest, elapsed)

        return {
            "query": query,
            "status": "success",
            "elapsed_seconds": round(elapsed, 2),
            "counts": {src: status["live_records"] for src, status in source_status.items()},
            "source_status": source_status,
            "total_raw": sum(map(len, source_results.values())),
            "total_canonical": len(canonical_records),
            "new_stacked_training_pairs": 0,
            "manifest": manifest,
        }

    def _build_manifest(
        self,
        query: str,
        records: list[dict[str, Any]],
        resources: list[dict[str, Any]],
        source_status: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Serialize fetched records and fallback navigation separately."""

        def serialize(item: dict[str, Any]) -> dict[str, Any]:
            paper: PaperRecord = item["paper"]
            provenance = item.get("provenance")
            return {
                "id": provenance.source_record_id if provenance else paper.paper_id,
                "title": paper.title,
                "authors": [author.name for author in paper.authors],
                "venue": paper.venue,
                "year": paper.publication_date[:4] if paper.publication_date else None,
                "abstract": paper.abstract[:300] if paper.abstract else "",
                "oa_url": paper.oa_url,
                "source": item.get("source"),
                "retrieval_mode": item.get("retrieval_mode"),
                "source_url": provenance.source_url if provenance else None,
                "fetched_at": provenance.fetched_at if provenance else None,
                "scholar_link": generate_scholar_url(
                    paper.title, paper.authors[0].name if paper.authors else None
                ),
            }

        return {
            "version": "1.1.0",
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "query": query,
            "total_cataloged": len(records),
            "source_status": source_status,
            "items": [serialize(item) for item in records],
            "resources": [serialize(item) for item in resources],
            "scholar_verification_url": self.scholar_adapter.verification_url(query),
        }

    def _update_live_manifests(self, manifest: dict[str, Any], elapsed: float) -> None:
        """Persist discovery metadata for local pages and explicit later sync."""
        CATALOGS_DIR.mkdir(parents=True, exist_ok=True)
        summary = {
            "timestamp": manifest["last_updated"],
            "latest_query": manifest["query"],
            "elapsed_seconds": round(elapsed, 2),
            "sources": manifest["source_status"],
            "canonical_total": manifest["total_cataloged"],
            "ingestion_status": "not_started",
        }
        with open(HARVEST_SUMMARY_PATH, "w", encoding="utf-8") as stream:
            json.dump(summary, stream, indent=2)
        with open(LIVE_MANIFEST_PATH, "w", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    test_query = sys.argv[1] if len(sys.argv) > 1 else "deep learning architectures"
    harvester = ParallelHarvester()
    res = harvester.harvest_parallel(test_query, limit_per_source=3)
    print("\n--- Parallel Harvest Complete ---")
    print(json.dumps(res, indent=2))
