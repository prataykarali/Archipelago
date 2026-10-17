"""Resumable research discovery and evidence job orchestration."""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from archipelago.scholarly.acquisition.artifact_fetcher import ArtifactFetcher
from archipelago.scholarly.acquisition.pdf_parser import PDFParser
from archipelago.scholarly.acquisition.rights_resolver import RightsResolver
from archipelago.scholarly.discovery.canonicalizer import Canonicalizer
from archipelago.scholarly.discovery.live_sources import LiveResearchSources, SourceResponse
from archipelago.scholarly.extraction.extractor import ScientificExtractor
from archipelago.scholarly.features.feature_engine import FeatureEngine
from archipelago.scholarly.pipeline.postgres_store import IdentityConflict, PostgresResearchStore
from archipelago.scholarly.pipeline.relevance import (
    DEFAULT_RETAIN_LIMIT,
    relevance_score,
    shortlist,
)

logger = logging.getLogger("archipelago.research.pipeline")
RESEARCH_SOURCES = ("openalex", "crossref", "arxiv", "semantic_scholar")
PER_SOURCE_LIMIT = 50
DEFAULT_DISPLAY_LIMIT = 10
MIN_METADATA_TITLE_LENGTH = 5
MAX_FULLTEXT_PER_JOB = 8


class ResearchJobRunner:
    """Run staged scholarly work; PostgreSQL checkpoints make retries safe."""

    def __init__(
        self,
        store: PostgresResearchStore,
        sources: LiveResearchSources | None = None,
        *,
        fetch_fulltext: bool = False,
    ) -> None:
        self.store = store
        self.sources = sources or LiveResearchSources()
        self.fetch_fulltext = fetch_fulltext
        self.canonicalizer = Canonicalizer()
        self.rights = RightsResolver()
        self.features = FeatureEngine()

    def run_next(self) -> dict[str, Any] | None:
        """Claim and process one queued job, recording an explicit failure."""
        job = self.store.claim_next()
        if job is None:
            return None
        try:
            return self.run(job)
        except Exception as exc:
            logger.exception("Research job %s failed", job["job_id"])
            self.store.update_job(
                str(job["job_id"]),
                status="failed",
                stage="FAILED",
                error=type(exc).__name__,
            )
            raise

    def run(self, job: dict[str, Any]) -> dict[str, Any]:
        """Execute source, identity, rights, evidence, feature, and shortlist stages."""
        job_id = str(job["job_id"])
        topic = str(job["topic"])
        responses = [self._source(job_id, source, topic) for source in RESEARCH_SOURCES]
        raw = [candidate for response in responses for candidate in response.records]
        self.store.update_job(job_id, status="running", stage="CANONICALIZATION")
        canonical = self.canonicalizer.canonicalize_candidates(raw)
        canonical.sort(key=lambda item: -relevance_score(item, topic)[0])
        retained = canonical[:DEFAULT_RETAIN_LIMIT]
        counts = {
            "raw_candidates": len(raw),
            "duplicates_removed": len(raw) - len(canonical),
            "canonical_candidates": len(retained),
            "metadata_validated": 0,
            "metadata_only": 0,
            "fulltext_eligible": 0,
            "fulltext_parsed": 0,
            "fulltext_attempted": 0,
            "fulltext_deferred": 0,
            "fulltext_fetch_failed": 0,
            "fulltext_parse_failed": 0,
            "evidence_validated": 0,
            "identity_conflicts": 0,
        }
        self.store.update_job(job_id, status="running", stage="IDENTITY_VALIDATION", counts=counts)
        validated: list[dict[str, Any]] = []
        fetcher = ArtifactFetcher() if self.fetch_fulltext else None
        parser = PDFParser() if self.fetch_fulltext else None
        extractor = ScientificExtractor() if self.fetch_fulltext else None
        for item in retained:
            paper = item["paper"]
            if (
                len(paper.title.strip()) < MIN_METADATA_TITLE_LENGTH
                or paper.title.casefold().strip() in {"untitled", "untitled paper"}
                or not self._has_identity(item)
            ):
                continue
            try:
                paper.paper_id = self.store.resolve_identity(paper)
            except IdentityConflict:
                counts["identity_conflicts"] += 1
                continue
            item["pipeline_state"] = "METADATA_VALIDATED"
            access = self.rights.resolve_access(
                paper.is_open_access, paper.license, item.get("pdf_url")
            )
            item["access_state"] = (
                "FULLTEXT_ELIGIBLE" if access["can_fetch_fulltext"] else "METADATA_ONLY"
            )
            try:
                self.store.save_paper(job_id, item)
            except IdentityConflict:
                counts["identity_conflicts"] += 1
                continue
            counts["metadata_validated"] += 1
            if access["can_fetch_fulltext"]:
                counts["fulltext_eligible"] += 1
            extraction: dict[str, Any] = {}
            can_attempt = bool(
                fetcher
                and parser
                and extractor
                and access["can_fetch_fulltext"]
                and counts["fulltext_attempted"] < MAX_FULLTEXT_PER_JOB
            )
            if access["can_fetch_fulltext"] and not can_attempt:
                counts["fulltext_deferred"] += 1
            if can_attempt and fetcher and parser and extractor:
                counts["fulltext_attempted"] += 1
                artifact = fetcher.fetch_pdf(item["pdf_url"], paper.paper_id)
                if artifact:
                    try:
                        parsed = parser.parse_pdf(artifact["file_path"], artifact["sha256"])
                        extraction = extractor.extract_from_parsed_document(paper, parsed)
                        item["pipeline_state"] = "FULLTEXT_PARSED"
                        item["access_state"] = "FULLTEXT_PARSED"
                        counts["fulltext_parsed"] += 1
                        provenance_checked = self._verify_evidence(extraction, artifact["sha256"])
                        self.store.save_evidence(
                            paper.paper_id,
                            artifact["sha256"],
                            self._serialize_extraction(extraction),
                            "provenance_checked" if provenance_checked else "pending_review",
                        )
                    except (OSError, ValueError, RuntimeError):
                        logger.exception("Full-text parse failed for %s", paper.paper_id)
                        item["access_state"] = "METADATA_ONLY"
                        counts["fulltext_parse_failed"] += 1
                else:
                    item["access_state"] = "METADATA_ONLY"
                    counts["fulltext_fetch_failed"] += 1
            self.store.save_paper(job_id, item)
            if item["pipeline_state"] == "METADATA_VALIDATED":
                counts["metadata_only"] += 1
            self.store.save_features(
                job_id,
                paper.paper_id,
                self.features.compute_features(
                    paper, topic, extraction, item.get("citation_count")
                ),
            )
            validated.append(item)
            self.store.update_job(
                job_id, status="running", stage="CANONICAL_RECORDS", counts=counts
            )
        shown = shortlist(validated, topic, limit=DEFAULT_DISPLAY_LIMIT)
        failures = [r.source for r in responses if r.status not in {"live", "live_empty"}]
        if counts["fulltext_deferred"]:
            failures.append("fulltext_processing_deferred")
        if counts["fulltext_fetch_failed"]:
            failures.append("fulltext_fetch_failed")
        if counts["fulltext_parse_failed"]:
            failures.append("fulltext_parse_failed")
        if len(shown) < 5:
            failures.append("fewer_than_five_relevant_papers")
        status = "partial" if failures else "complete"
        self.store.update_job(
            job_id,
            status=status,
            stage="SHORTLIST_READY",
            counts=counts,
            shortlist=shown,
            error=", ".join(failures) or None,
        )
        if validated:
            self.store.enqueue_projection(job_id)
        return {
            "job_id": job_id,
            "topic": topic,
            "status": status,
            "counts": counts,
            "shortlist": shown,
            "source_status": [response.summary() for response in responses],
            "coverage_gaps": failures,
        }

    def _source(self, job_id: str, source: str, topic: str) -> SourceResponse:
        previous = self.store.source_payload(job_id, source)
        if previous and previous["status"] in {"live", "live_empty"} and previous["response_body"]:
            body = bytes(previous["response_body"])
            digest = hashlib.sha256(body).hexdigest()
            if digest == previous["response_sha256"]:
                records = self.sources._parse(source, body, digest)
                return SourceResponse(
                    source=source,
                    requested_at=str(previous["requested_at"]),
                    status=previous["status"],
                    records=records,
                    raw_body=body,
                    raw_sha256=digest,
                    request_id=previous["request_id"],
                    http_status=previous["http_status"],
                )
        response = self.sources.search(source, topic, PER_SOURCE_LIMIT)
        self.store.save_source(job_id, response)
        return response

    @staticmethod
    def _has_identity(item: dict[str, Any]) -> bool:
        ids = item["paper"].identifiers
        return bool(ids.doi or ids.arxiv_id or ids.openalex_id or ids.semantic_scholar_id)

    @staticmethod
    def _verify_evidence(extraction: dict[str, Any], artifact_sha256: str) -> bool:
        provenance = {p.provenance_id: p for p in extraction.get("provenance", [])}
        assertions = [
            *extraction.get("claims", []),
            *extraction.get("experiments", []),
            *extraction.get("results", []),
        ]
        if not assertions:
            return False
        return all(
            assertion.provenance_ids
            and all(
                pointer_id in provenance
                and provenance[pointer_id].artifact_sha256 == artifact_sha256
                and provenance[pointer_id].page is not None
                and (
                    provenance[pointer_id].tei_xpath is not None
                    or (
                        provenance[pointer_id].char_start is not None
                        and provenance[pointer_id].char_end is not None
                    )
                    or provenance[pointer_id].bbox is not None
                    or provenance[pointer_id].table_id is not None
                )
                for pointer_id in assertion.provenance_ids
            )
            for assertion in assertions
        )

    @staticmethod
    def _serialize_extraction(extraction: dict[str, Any]) -> dict[str, Any]:
        return {
            key: [item.model_dump(mode="json") for item in value]
            if isinstance(value, list)
            else value
            for key, value in extraction.items()
        }
