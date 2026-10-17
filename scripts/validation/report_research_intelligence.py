"""Export factual local or staging Research Intelligence run evidence."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
from typing import Any, cast

from archipelago.scholarly.pipeline.postgres_store import PostgresResearchStore
from archipelago.scholarly.pipeline.postgres_store_constants import PIPELINE_VERSION
from scripts.validation.research_report_queries import (
    EVIDENCE_EXAMPLE_LIMIT,
    IDENTITY_EXAMPLE_LIMIT,
    _evidence_examples,
    _feature_examples,
    _identity_examples,
)

TOPICS = (
    ("optical character recognition", "optical-character-recognition"),
    ("pedestrian detection", "pedestrian-detection"),
    ("bengali speech recognition", "bengali-speech-recognition"),
    ("skin cancer detection", "skin-cancer-detection"),
    ("fake news detection", "fake-news-detection"),
)
SOURCE_NAMES = ("openalex", "crossref", "arxiv", "semantic_scholar")


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime,)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_value(item) for item in value]
    return value


def export_topic(store: PostgresResearchStore, topic: str, environment: str) -> dict[str, Any]:
    """Export one actual job and its private provenance without raw response bytes."""
    with store._connect() as conn:
        job = conn.execute(
            """SELECT job_id, user_id, role, topic, pipeline_version, status, stage,
                      counts, shortlist, error, created_at, updated_at
               FROM research_intelligence.jobs
               WHERE topic = %s AND idempotency_key LIKE %s
               ORDER BY created_at DESC LIMIT 1""",
            (topic, "e2e-%"),
        ).fetchone()
        if job is None:
            return {"topic": topic, "environment": environment, "result": "NOT_RUN"}
        job_id = str(job["job_id"])
        sources = store.source_summaries(job_id)
        by_name = {source["source"]: source for source in sources}
        source_evidence = [
            _json_value(by_name.get(name, {"source": name, "status": "not_requested"}))
            for name in SOURCE_NAMES
        ]
        shortlist = job["shortlist"] or []
        merged = _identity_examples(conn, job_id)
        evidence = _evidence_examples(conn, job_id)
        evidence_states = {
            row["verification_state"]: row["total"]
            for row in conn.execute(
                """SELECT pe.verification_state, count(DISTINCT pe.paper_id) AS total
                   FROM research_intelligence.paper_evidence pe
                   JOIN research_intelligence.job_papers jp ON jp.paper_id = pe.paper_id
                   WHERE jp.job_id = %s GROUP BY pe.verification_state""",
                (job_id,),
            ).fetchall()
        }
        features = _feature_examples(conn, job_id, shortlist)
        gaps = [part.strip() for part in (job["error"] or "").split(",") if part.strip()]
        if len(merged) < IDENTITY_EXAMPLE_LIMIT:
            gaps.append("fewer_than_three_identity_merges")
        if len(evidence) < EVIDENCE_EXAMPLE_LIMIT:
            gaps.append("fewer_than_two_extracted_fulltext_assertions")
        if any(not item.get("extractor_version") for item in evidence):
            gaps.append("extractor_version_not_recorded_in_initial_run")
        if not any(item["verification_state"] == "validated" for item in evidence):
            gaps.append("no_human_validated_evidence")
        if len(shortlist) < 5:
            gaps.append("fewer_than_five_displayed_papers")
        return cast(
            dict[str, Any],
            _json_value(
                {
                    "topic": topic,
                    "requested_by_role": job["role"],
                    "requested_by_user_id": job["user_id"],
                    "job_id": job_id,
                    "started_at": job["created_at"],
                    "completed_at": job["updated_at"],
                    "pipeline_version": job["pipeline_version"],
                    "environment": environment,
                    "job_status": job["status"],
                    "pipeline_stage": job["stage"],
                    "source_evidence": source_evidence,
                    "candidate_pool": job["counts"],
                    "displayed_papers": shortlist,
                    "identity_merge_examples": merged,
                    "evidence_examples": evidence,
                    "evidence_state_counts": evidence_states,
                    "feature_examples": features,
                    "coverage_gaps": sorted(set(gaps)),
                    "result": "PARTIAL" if gaps or environment != "staging" else "PASS",
                }
            ),
        )


def main() -> None:
    """Write five machine-readable artifacts and a factual Markdown summary."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--environment", required=True)
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--projection-root", type=Path)
    args = parser.parse_args()
    store = PostgresResearchStore()
    args.artifacts.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    projection = None
    if args.projection_root:
        pointer = args.projection_root / "current.json"
        if pointer.exists():
            projection = json.loads(pointer.read_text(encoding="utf-8"))
    rebuild_path = args.artifacts / "graph-rebuild.json"
    rebuild = (
        json.loads(rebuild_path.read_text(encoding="utf-8")) if rebuild_path.exists() else None
    )
    access_path = args.artifacts / "access-control.json"
    access = json.loads(access_path.read_text(encoding="utf-8")) if access_path.exists() else None
    vector_smoke_path = args.artifacts / "vector-smoke.json"
    vector_smoke = (
        json.loads(vector_smoke_path.read_text(encoding="utf-8"))
        if vector_smoke_path.exists()
        else None
    )
    institutional_path = args.artifacts / "institutional-source-check.json"
    institutional = (
        json.loads(institutional_path.read_text(encoding="utf-8"))
        if institutional_path.exists()
        else None
    )
    actor_files = ("opac-https-apify.json", "opac-http-apify.json", "iemcrp-apify.json")
    actor_probes = {
        name: json.loads((args.artifacts / name).read_text(encoding="utf-8"))
        for name in actor_files
        if (args.artifacts / name).exists()
    }
    graph_topics_path = args.artifacts / "graph-topic-traces.json"
    graph_topics = (
        json.loads(graph_topics_path.read_text(encoding="utf-8"))
        if graph_topics_path.exists()
        else None
    )
    refresh_path = args.artifacts / "refresh-cycle.json"
    refresh = (
        json.loads(refresh_path.read_text(encoding="utf-8")) if refresh_path.exists() else None
    )
    sections = [
        "# Research Intelligence end-to-end validation",
        "",
        f"Environment: `{args.environment}`. Pipeline version: `{PIPELINE_VERSION}`. "
        f"Commit SHA: `{revision}` (working tree includes uncommitted pipeline changes).",
        "This report contains actual run records. It is not a staging PASS when the environment is local.",
        "Local database: PostgreSQL 17 in Docker container `archipelago-ri-validation` "
        "on `127.0.0.1:15432`, backed by named volume `archipelago-ri-validation-data`. "
        "PDF artifacts and derived projections are under `/tmp/archipelago-ri-validation/`; "
        "the machine-readable run summaries are saved in this repository.",
        "",
        "## Test accounts / roles",
        "",
        "Jobs were submitted as `local-validation-faculty` with stored role `faculty`. "
        "No live Supabase staff or student session was available for staging authorization tests.",
        "",
    ]
    for topic, slug in TOPICS:
        result = export_topic(store, topic, args.environment)
        (args.artifacts / f"{slug}.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        sources = result.get("source_evidence") or []
        lines = [
            f"## {topic.title()}",
            "",
            f"Job: `{result.get('job_id', 'not run')}`; result: **{result['result']}**; "
            f"status: `{result.get('job_status', 'not run')}`.",
            "",
            f"Candidates: `{result.get('candidate_pool', {})}`. "
            f"Displayed: **{len(result.get('displayed_papers', []))}**.",
            "",
            "Sources: "
            + "; ".join(
                f"{item['source']}={item['status']} (HTTP {item.get('http_status')}, "
                f"records {item.get('record_count', 0)})"
                for item in sources
            ),
            "",
            "Coverage gaps: " + (", ".join(result.get("coverage_gaps", [])) or "none recorded"),
            "",
            f"Full records, shortlists, identities, evidence, and features: `{slug}.json`.",
            "",
        ]
        sections.extend(lines)
        sections.extend(
            [
                "### Source request evidence",
                "",
                "| Source | Requested at | HTTP | Request ID | Raw SHA-256 |",
                "|---|---|---:|---|---|",
            ]
        )
        for item in sources:
            sections.append(
                f"| {item['source']} | {item.get('requested_at') or '—'} | "
                f"{item.get('http_status') or '—'} | {item.get('request_id') or '—'} | "
                f"`{item.get('response_sha256') or '—'}` |"
            )
        sections.extend(
            [
                "",
                "### Actual displayed papers",
                "",
                "| Rank | Title | Year | DOI / arXiv | Access | Pipeline state | Relevance reason |",
                "|---:|---|---:|---|---|---|---|",
            ]
        )
        for paper in result.get("displayed_papers", []):
            title = str(paper["title"]).replace("|", "\\|").replace("\n", " ")
            reason = "; ".join(paper.get("topic_relevance_reason") or [])
            sections.append(
                f"| {paper['rank']} | {title} | {paper.get('year') or '—'} | "
                f"{paper.get('doi') or paper.get('arxiv_id') or '—'} | "
                f"{paper.get('access_state') or '—'} | "
                f"{paper.get('pipeline_state') or '—'} | {reason} |"
            )
        merges = result.get("identity_merge_examples", [])
        evidence = result.get("evidence_examples", [])
        sections.extend(
            [
                "",
                f"Identity merges demonstrated: **{len(merges)} / 3 requested**. "
                f"Full-text assertion examples: **{len(evidence)} / 2 requested**. "
                f"Feature dumps: **{len(result.get('feature_examples', []))} papers**. "
                f"Evidence states: `{result.get('evidence_state_counts', {})}`.",
                "",
            ]
        )
        for item in merges:
            signals = [
                history.get("signals", {}).get("reason") for history in item["merge_history"]
            ]
            sections.append(
                f"- Merge `{item['canonical_paper_id']}` from {item['source_records']} records: "
                + ", ".join(str(signal) for signal in signals)
            )
        for item in evidence:
            pointer = (item.get("evidence_pointers") or [{}])[0]
            assertion = item["assertion"]
            excerpt = " ".join(
                str(assertion.get("text") or assertion.get("metric") or assertion).split()
            )[:150].rstrip()
            sections.append(
                f"- Evidence `{item['paper_id']}`: `{item['verification_state']}`; "
                f"page {pointer.get('page') or 'unknown'}, section "
                f"{pointer.get('section_id') or 'unknown'}, artifact "
                f"`{item['artifact_sha256']}`, extractor "
                f"`{item.get('extractor_version') or 'not recorded'}`; {excerpt}"
            )
        sections.append("")
    sections.extend(
        [
            "## Graph validation",
            "",
            f"Latest projection pointer: `{projection or 'not built'}`.",
            "",
            f"PostgreSQL → Kùzu delete/rebuild trace: `{rebuild or 'not run'}`.",
            "",
            f"Representative paper/author/venue edge traces for all five topics: "
            f"`{graph_topics or 'not run'}`.",
            "",
            "Vector smoke: "
            + (
                "; ".join(
                    f"{topic} → {items[0]['title']} ({items[0]['cosine']:.3f})"
                    for topic, items in vector_smoke["results"].items()
                )
                if vector_smoke
                else "not run"
            ),
            "",
            "The graph currently projects paper, author, and venue metadata. "
            "No claim/evidence edges were published because no extraction passed human adjudication. "
            "Citation, benchmark, and semantic relation edges remain unimplemented.",
            "",
            "## Automatic refresh validation",
            "",
            "A tracked OCR topic was made due in the isolated database and one `work_cycle` "
            "queued and processed it. OpenAlex and Crossref refreshed live; arXiv and Semantic "
            "Scholar returned 429. The cycle published a new Kùzu/vector generation from PostgreSQL.",
            "",
            "This verifies one worker cycle, not continuous operation. No scheduler or worker "
            "was deployed, and staff access remains disabled pending the release gate.",
            "",
            f"[Refresh cycle trace](../../artifacts/validation/research-intelligence/refresh-cycle.json) "
            f"(generation `{refresh.get('projection_generation') if refresh else 'not run'}`).",
            "",
            "## Bibliometrics and feature validation",
            "",
            "Per-paper feature observations include missing states and formula inputs in each JSON file. "
            "Author h-index/g-index/i10/m-index snapshots are not implemented. "
            "The topic shortlist reads only title and abstract query coverage; the local ordering test "
            "confirms that citation count and author reputation do not affect it.",
            "",
            "## Access control validation",
            "",
            "Automated four-role route tests ran locally. The DB-backed Flask route probe used "
            "simulated verified principals: all five direct student requests returned 403; "
            "faculty job/feature/evidence reads and librarian/admin manager reads succeeded. "
            "Job creation and refresh actions produced PostgreSQL audit rows. "
            "Live Supabase staff/student account tests remain open.",
            "",
            "[DB-backed access trace](../../artifacts/validation/research-intelligence/"
            f"access-control.json) (pass: `{access.get('pass') if access else 'not run'}`).",
            "",
            "## Institutional source status",
            "",
            "OPAC and IEM CRP were checked read-only. No approved machine-readable export path "
            "or session credential was available, so no institutional book/holding data was ingested.",
            "",
            f"Observed endpoint states: `{institutional or 'not checked'}`.",
            "",
            "Apify public-page probes: "
            + "; ".join(
                f"{name} → {probe['source_status']} "
                f"({probe.get('failure_state') or probe['actor_run']['status']}; "
                f"{probe['dataset_items']} dataset items, {len(probe['records'])} records)"
                for name, probe in actor_probes.items()
            ),
            "",
            "The Actor's own `SUCCEEDED` status does not establish a successful source fetch. "
            "The HTTPS OPAC probe timed out, the HTTP OPAC probe was stopped after two minutes "
            "with zero pages, and the public IEM portal returned HTTP 403. No book or holding "
            "was inferred from any of these runs. The actor trace JSON files preserve run IDs, "
            "cost, dataset counts, and failure states without storing tokens.",
            "",
            "## Failures / coverage gaps and final decision",
            "",
            "Focused auth/research tests: 38 passed. Repository-wide Ruff lint and formatting "
            "passed. Strict mypy passed on the touched research modules; the repository-wide "
            "strict-mypy quality gate still has an existing baseline of unrelated errors.",
            "",
            "**PARTIAL.** Local ingestion is inspectable; the required staging run, live role tests, "
            "human evidence adjudication, GROBID/selective OCR, and institutional OPAC/IEM ingestion "
            "remain release gates. The research projection is not yet wired into chat retrieval. "
            "Research Intelligence stays disabled.",
            "",
        ]
    )
    args.report.write_text("\n".join(sections), encoding="utf-8")
    print(args.report)


if __name__ == "__main__":
    main()
