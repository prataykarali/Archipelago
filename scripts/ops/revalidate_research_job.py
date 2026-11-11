"""Repair saved evidence and republish the OKF file for a finished research job."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from dotenv import load_dotenv

from archipelago.scholarly.acquisition.indra_parser import parse_with_indra
from archipelago.scholarly.bridge.hf_export import publish_okf_dataset
from archipelago.scholarly.bridge.supabase_store import ResearchQueueStore
from archipelago.scholarly.extraction.research_abstract_fallback import (
    extract_fallback_abstract_fields,
)
from archipelago.scholarly.extraction.semantic_guard import valid_evidence_item
from archipelago.scholarly.extraction.structured_okf import build_paper_okf

ROOT = Path(__file__).resolve().parents[2]
MAX_JOB_PAPERS = 100
PAPER_COLUMNS = "record_key,kind,title,source_url,source_name,topic,content,published_at,metadata"
MAX_FALLBACK_SPANS = 3


def _cached_pdf_facts(row: dict[str, Any]) -> list[dict[str, Any]]:
    """Recover page-linked literal facts from an already-approved local PDF."""
    metadata = row["metadata"]
    digest = str(metadata.get("pdf_sha256") or "")
    if len(digest) != 64:
        return []
    paths = list((ROOT / "data/artifacts/papers").glob(f"*/pdf/{digest}.pdf"))
    if not paths or sha256(paths[0].read_bytes()).hexdigest() != digest:
        return []
    parsed = parse_with_indra(paths[0], digest)
    sections = parsed.get("sections") or {}
    spans = list(sections.get("abstract") or [])[:MAX_FALLBACK_SPANS]
    if not spans:
        first_page = [
            span for group in sections.values() for span in group if span.get("page") == 1
        ]
        spans = sorted(first_page, key=lambda span: len(str(span.get("text") or "")), reverse=True)[
            :MAX_FALLBACK_SPANS
        ]
    facts: list[dict[str, Any]] = []
    for span in spans:
        for candidate in extract_fallback_abstract_fields(str(span.get("text") or "")):
            fact = {
                **candidate,
                "pdf_page": span["page"],
                "pdf_sha256": digest,
                "section": span.get("section") or "preamble",
                "source_api": "indra_pdf_literal_fallback",
                "source_timestamp": datetime.now(UTC).isoformat(),
                "verification_status": "quote_matched",
            }
            if valid_evidence_item(fact, row):
                facts.append(fact)
    return facts


def revalidate(job_id: str, *, apply: bool, enrich_cached_pdf: bool = False) -> dict[str, Any]:
    """Check every source quote, then sync the corrected record, result, and HF file."""
    load_dotenv(ROOT / ".env", override=False)
    store = ResearchQueueStore()
    jobs = store._request(
        "GET",
        "research_processing_jobs",
        params={"job_id": f"eq.{job_id}", "select": "job_id,status,result_summary", "limit": 1},
    )
    if not jobs or jobs[0]["status"] not in {"completed", "partial"}:
        raise ValueError("Job must be finished before revalidation")
    rows = store._request(
        "GET",
        "research_intake_records",
        params={
            "select": PAPER_COLUMNS,
            "metadata->>ingestion_job_id": f"eq.{job_id}",
            "order": "title.asc",
            "limit": MAX_JOB_PAPERS,
        },
    )
    active = [row for row in rows or [] if (row.get("metadata") or {}).get("active") is not False]
    report: dict[str, Any] = {
        "job_id": job_id,
        "papers": len(active),
        "rejected": 0,
        "added_pdf_facts": 0,
        "added_pdf_details": [],
        "rejected_papers": [],
    }
    results: list[dict[str, Any]] = []
    states: Counter[str] = Counter()
    abstract_facts = 0
    abstracts_with_facts = 0
    for row in active:
        metadata = row["metadata"]
        candidates = metadata.get("verified_extractions") or []
        retained = (
            [
                fact
                for fact in candidates
                if not (
                    isinstance(fact, dict)
                    and fact.get("source_api")
                    in {"indra_pdf_literal_fallback", "abstract_span_extractor"}
                )
            ]
            if enrich_cached_pdf
            else candidates
        )
        accepted = [fact for fact in retained if valid_evidence_item(fact, row)]
        if enrich_cached_pdf:
            for fact in extract_fallback_abstract_fields(str(row.get("content") or "")):
                if valid_evidence_item(fact, row):
                    accepted.append(fact)
            known = {
                (fact["group"], fact["field"], fact["value"], fact.get("pdf_page"))
                for fact in accepted
            }
            for fact in _cached_pdf_facts(row):
                key = (fact["group"], fact["field"], fact["value"], fact.get("pdf_page"))
                if key not in known:
                    accepted.append(fact)
                    known.add(key)
                    report["added_pdf_facts"] += 1
                    report["added_pdf_details"].append(
                        {
                            "title": row["title"],
                            "field": fact["field"],
                            "value": fact["value"][:120],
                            "page": fact["pdf_page"],
                        }
                    )
        rejected = len(retained) - len(
            [fact for fact in retained if valid_evidence_item(fact, row)]
        )
        report["rejected"] += rejected
        if rejected:
            report["rejected_papers"].append({"title": row["title"], "count": rejected})
        metadata["verified_extractions"] = accepted
        metadata["rejected_extraction_count"] = (
            int(metadata.get("rejected_extraction_count") or 0) + rejected
        )
        if metadata.get("fulltext_verified"):
            metadata["access_state"] = (
                "FULLTEXT_EXTRACTED"
                if any(isinstance(fact.get("pdf_page"), int) for fact in accepted)
                else "FULLTEXT_NO_VERIFIED_FIELDS"
            )
        state = str(metadata.get("access_state") or "METADATA_ONLY")
        states[state] += 1
        abstract_count = sum(
            fact.get("verification_status") == "abstract_quote_matched" for fact in accepted
        )
        abstract_facts += abstract_count
        abstracts_with_facts += abstract_count > 0
        okf = build_paper_okf(row, row.get("topic"))
        results.append(okf)
        if apply:
            store._request(
                "PATCH",
                "research_intake_records",
                params={"record_key": f"eq.{row['record_key']}"},
                headers={"Prefer": "return=minimal"},
                json={"metadata": metadata},
            )
            store.save_result(
                {
                    "job_id": job_id,
                    "paper_id": str(uuid5(NAMESPACE_URL, row["record_key"])),
                    "title": row["title"],
                    "source_url": row["source_url"],
                    "source_name": row["source_name"],
                    "access_state": state,
                    "okf": okf,
                }
            )
    report["states"] = dict(states)
    if apply:
        hf = publish_okf_dataset(job_id, results)
        summary = {
            **(jobs[0].get("result_summary") or {}),
            "abstract_facts_extracted": abstract_facts,
            "abstracts_with_facts": abstracts_with_facts,
            "fulltext_extracted": states["FULLTEXT_EXTRACTED"],
            "evidence_revalidated": True,
            "rejected_extractions": report["rejected"],
            "hf_dataset": hf,
        }
        store.update_job(
            job_id,
            result_summary=summary,
            fulltext_count=states["FULLTEXT_EXTRACTED"],
            status="partial" if report["rejected"] else jobs[0]["status"],
            stage="REVALIDATED_PARTIAL" if report["rejected"] else "REVALIDATED",
        )
        report["hf_status"] = hf["status"]
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_id")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--enrich-cached-pdf", action="store_true")
    args = parser.parse_args()
    print(revalidate(args.job_id, apply=args.apply, enrich_cached_pdf=args.enrich_cached_pdf))


if __name__ == "__main__":
    main()
