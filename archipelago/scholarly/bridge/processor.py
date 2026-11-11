"""Process queued research with metadata and permitted local PDF evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
import logging
from typing import Any
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, uuid5

import requests

from archipelago.scholarly.acquisition.indra_parser import indra_available
from archipelago.scholarly.acquisition.rights_resolver import RightsResolver
from archipelago.scholarly.bridge.author_metrics import first_author_metrics
from archipelago.scholarly.bridge.discovery import discover_ranked_papers
from archipelago.scholarly.bridge.fulltext import MAX_FULLTEXT_PAPERS, enrich_fulltext
from archipelago.scholarly.bridge.hf_export import publish_library_papers, publish_okf_dataset
from archipelago.scholarly.bridge.supabase_store import ResearchQueueStore
from archipelago.scholarly.discovery.canonicalizer import canonical_paper_identity
from archipelago.scholarly.extraction.abstract_fields import (
    EXTRACTOR_VERSION,
    extract_abstract_fields,
    ingestion_model_name,
)
from archipelago.scholarly.extraction.research_abstract_fallback import (
    extract_fallback_abstract_fields,
)
from archipelago.scholarly.extraction.semantic_guard import valid_evidence_item
from archipelago.scholarly.extraction.structured_okf import build_paper_okf

MAX_ABSTRACT_CHARS = 12000
ANSWER_SOURCE_LIMIT = 5
ANSWER_EXCERPT_CHARS = 260
LOGGER = logging.getLogger(__name__)


def _intake_row(item: dict[str, Any], topic: str, user_id: str) -> dict[str, Any]:
    """Convert a canonical local paper into the hosted research graph shape."""
    paper = item["paper"]
    ids = paper.identifiers
    identity = canonical_paper_identity(ids)
    identity = identity or paper.paper_id
    key = sha256(f"paper:{identity.lower().strip()}".encode()).hexdigest()
    provenance = item.get("provenance")
    source_metadata = item.get("source_metadata") or {}
    source_url = getattr(provenance, "source_url", None) or paper.oa_url
    if not source_url or urlparse(source_url).scheme != "https":
        if ids.doi:
            source_url = f"https://doi.org/{ids.doi}"
        elif ids.arxiv_id:
            source_url = f"https://arxiv.org/abs/{ids.arxiv_id}"
        elif ids.openalex_id:
            source_url = f"https://openalex.org/{ids.openalex_id}"
        else:
            raise ValueError("Paper has no verifiable HTTPS source")
    return {
        "record_key": key,
        "kind": "paper",
        "title": paper.title[:300],
        "source_url": source_url,
        "source_name": str(item.get("source") or "unknown"),
        "topic": topic,
        "content": (paper.abstract or "")[:MAX_ABSTRACT_CHARS],
        "published_at": paper.publication_date,
        "metadata": {
            "doi": ids.doi,
            "arxiv_id": ids.arxiv_id,
            "openalex_id": ids.openalex_id,
            "semantic_scholar_id": ids.semantic_scholar_id,
            "authors": [author.model_dump(mode="json") for author in paper.authors],
            "institutions": sorted(
                {name for author in paper.authors for name in author.institutions}
            ),
            "venue": paper.venue,
            "paper_type": paper.publication_type,
            "publisher": source_metadata.get("publisher"),
            "keywords": source_metadata.get("keywords"),
            "topics": source_metadata.get("topics"),
            "research_domain": source_metadata.get("research_domain"),
            "license": paper.license,
            "is_open_access": paper.is_open_access,
            "open_access_pdf": item.get("pdf_url"),
            "citation_count": item.get("citation_count"),
            "reference_count": source_metadata.get("reference_count"),
            "referenced_works": source_metadata.get("referenced_works"),
            "counts_by_year": source_metadata.get("counts_by_year"),
            "influential_citations": source_metadata.get("influential_citations"),
            "retraction_status": source_metadata.get("retraction_status"),
            "publication_versions": source_metadata.get("publication_versions"),
            "publication_types": source_metadata.get("publication_types"),
            "author_openalex_ids": source_metadata.get("author_openalex_ids"),
            "first_author_metrics": item.get("first_author_metrics"),
            "field_sources": item.get("source_metadata_sources"),
            "source_metadata": source_metadata,
            "source_timestamp": getattr(provenance, "fetched_at", None)
            or datetime.now(UTC).isoformat(),
            "topic_relevance_score": item.get("topic_relevance_score"),
            "active": True,
            "ingestion_pipeline": "local_indra_v3",
        },
        "updated_by": user_id,
    }


def _reply(topic: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Return linked source excerpts without inventing a scientific conclusion."""
    sources = []
    lines = [f"Papers relevant to “{topic}”:"]
    for index, record in enumerate(records[:ANSWER_SOURCE_LIMIT], start=1):
        excerpt = " ".join(record["content"].split())[:ANSWER_EXCERPT_CHARS]
        lines.append(f"[{index}] {record['title']}. {excerpt}")
        sources.append(
            {
                "title": record["title"],
                "url": record["source_url"],
                "provider": record["source_name"],
                "excerpt": excerpt,
            }
        )
    return {"answer": "\n".join(lines), "sources": sources, "answer_kind": "source_excerpts"}


def process_job(store: ResearchQueueStore, job: dict[str, Any], worker_id: str) -> dict[str, Any]:
    """Discover 20 to 30 papers, process local evidence, and publish progress."""
    job_id = str(job["job_id"])
    topic = str(job["topic"])
    selected, providers, model_status, gpu = discover_ranked_papers(topic, int(job["paper_limit"]))
    store.update_job(
        job_id,
        stage="PAPER_INGESTION",
        fetched_count=len(selected),
        result_summary={"providers": providers, "model_status": model_status, "gpu": gpu},
    )
    if not selected:
        store.update_job(
            job_id,
            status="failed",
            stage="SOURCE_UNAVAILABLE",
            error="no_papers_found",
            completed_at=datetime.now(UTC).isoformat(),
        )
        return {"job_id": job_id, "status": "failed", "fetched": 0}
    saved: list[dict[str, Any]] = []
    errors = 0
    extracted_facts = 0
    abstracts_attempted = 0
    abstracts_with_facts = 0
    extraction_errors = 0
    fulltext_attempted = 0
    fulltext_extracted = 0
    fulltext_states: dict[str, int] = {}
    okf_records: list[dict[str, Any]] = []
    author_metrics = first_author_metrics(selected)
    for item in selected:
        try:
            author_ids = (item.get("source_metadata") or {}).get("author_openalex_ids") or []
            if author_ids:
                item["first_author_metrics"] = author_metrics.get(author_ids[0])
            record = _intake_row(item, topic, str(job["user_id"]))
            record["metadata"]["ingestion_job_id"] = job_id
            if record["content"]:
                abstracts_attempted += 1
                try:
                    facts = extract_abstract_fields(record["content"])
                except (requests.RequestException, ValueError, OSError):
                    extraction_errors += 1
                    facts = []
                if not facts:
                    facts = extract_fallback_abstract_fields(record["content"])
                record["metadata"]["verified_extractions"] = facts
            access_state = "METADATA_ONLY"
            attempted_fulltext = False
            eligible = RightsResolver().resolve_access(
                item["paper"].is_open_access,
                item["paper"].license,
                item.get("pdf_url"),
            )["can_fetch_fulltext"]
            if fulltext_attempted < MAX_FULLTEXT_PAPERS and eligible:
                fulltext_attempted += 1
                attempted_fulltext = True
                store.update_job(job_id, stage="INDRA_OCR", processed_count=len(saved))
                access_state = enrich_fulltext(item, record)
            candidates = record["metadata"].get("verified_extractions") or []
            accepted = [fact for fact in candidates if valid_evidence_item(fact, record)]
            record["metadata"]["verified_extractions"] = accepted
            record["metadata"]["rejected_extraction_count"] = len(candidates) - len(accepted)
            abstract_facts = [
                fact
                for fact in accepted
                if fact.get("verification_status") == "abstract_quote_matched"
            ]
            extracted_facts += len(abstract_facts)
            abstracts_with_facts += bool(abstract_facts)
            if access_state == "FULLTEXT_EXTRACTED" and not any(
                isinstance(fact.get("pdf_page"), int) for fact in accepted
            ):
                access_state = "FULLTEXT_NO_VERIFIED_FIELDS"
            if attempted_fulltext:
                fulltext_states[access_state] = fulltext_states.get(access_state, 0) + 1
                fulltext_extracted += access_state == "FULLTEXT_EXTRACTED"
            record["metadata"]["access_state"] = access_state
            store.update_job(job_id, stage="OKF_EXTRACTION", processed_count=len(saved))
            okf = build_paper_okf(record, topic)
        except (OSError, ValueError, RuntimeError, KeyError):
            errors += 1
            continue
        store.save_intake_record(record)
        store.save_result(
            {
                "job_id": job_id,
                "paper_id": str(uuid5(NAMESPACE_URL, record["record_key"])),
                "title": record["title"],
                "source_url": record["source_url"],
                "source_name": record["source_name"],
                "access_state": access_state,
                "okf": okf,
            }
        )
        okf_records.append(okf)
        saved.append(record)
        store.update_job(
            job_id,
            processed_count=len(saved),
            stage="PAPER_INGESTION",
        )
        ocr_state = "ocr_ready" if indra_available() else "ocr_unavailable"
        try:
            store.heartbeat(worker_id, f"{model_status}:{ingestion_model_name()}:{ocr_state}", 0)
        except requests.RequestException:
            LOGGER.warning("Research heartbeat dropped; continuing saved job %s", job_id)
    store.update_job(job_id, stage="HF_DATASET_SYNC", processed_count=len(saved))
    hf_dataset = publish_okf_dataset(job_id, okf_records)
    library_dataset = publish_library_papers(job_id, saved)
    status = (
        "completed"
        if len(saved) >= 20
        and errors == 0
        and extraction_errors == 0
        and (abstracts_with_facts > 0 or fulltext_extracted > 0)
        and hf_dataset.get("status") == "published"
        and library_dataset.get("status") == "published"
        else "partial"
    )
    summary = {
        **_reply(topic, saved),
        "providers": providers,
        "model_status": model_status,
        "gpu": gpu,
        "ingestion_mode": "metadata_abstract_and_permitted_fulltext",
        "fulltext_attempted": fulltext_attempted,
        "fulltext_extracted": fulltext_extracted,
        "fulltext_states": fulltext_states,
        "hf_dataset": hf_dataset,
        "library_dataset": library_dataset,
        "errors": errors,
        "ingestion_model": ingestion_model_name(),
        "extractor_version": EXTRACTOR_VERSION,
        "abstracts_attempted": abstracts_attempted,
        "abstracts_with_facts": abstracts_with_facts,
        "abstract_extraction_errors": extraction_errors,
        "abstract_facts_extracted": extracted_facts,
    }
    store.update_job(
        job_id,
        status=status,
        stage="READY" if status == "completed" else "PARTIAL",
        processed_count=len(saved),
        fulltext_count=fulltext_extracted,
        result_summary=summary,
        completed_at=datetime.now(UTC).isoformat(),
    )
    return {
        "job_id": job_id,
        "status": status,
        "fetched": len(selected),
        "processed": len(saved),
        "fulltext": fulltext_extracted,
        "model_status": model_status,
    }
