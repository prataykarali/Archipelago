"""Structured negative-control verification worksheet, save/resume, backups, and export.

NEVER auto-populates or auto-signs human classification or provenance fields.
All human decision and attestation fields initialize blank/null/False.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
from typing import Any

from .constants import (
    DEFAULT_BACKUP_DIR,
    NEGATIVE_CONTROL_QUERY_IDS,
    SCHEMA_VERSION,
)
from .corpus import CorpusIndex, SearchResult

DEFAULT_QUERY_SPECS: tuple[dict[str, str], ...] = (
    {
        "query_id": "Q-S5B2-03",
        "legacy_query_id": "Q-S5A-03",
        "domain": "Operating Systems",
        "query_text": (
            "What is the exact multi-level page table walk latency in nanoseconds "
            "for the ARM Cortex-A78 microarchitecture?"
        ),
    },
    {
        "query_id": "Q-S5B2-08",
        "legacy_query_id": "Q-S5A-08",
        "domain": "AI & Machine Learning",
        "query_text": (
            "What was the total dollar cost in electric utility bills for training "
            "the LLaMA-3 405B base model on 16,000 H100 GPUs?"
        ),
    },
    {
        "query_id": "Q-S5B2-11",
        "legacy_query_id": "Q-S5A-11",
        "domain": "Computer Networks",
        "query_text": (
            "What is the exact firmware vulnerability CVE identifier for the Cisco "
            "Catalyst 9300 switch buffer overflow discovered in 2025?"
        ),
    },
)


def utc_now_iso() -> str:
    """Return current UTC timestamp in ISO-8601 format with Z suffix."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc_backup_stamp() -> str:
    """Return filesystem-safe UTC timestamp for backup filenames."""
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S_%fZ")


def sha256_file(path: Path) -> str:
    """Return SHA-256 hex digest of a file on disk."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _collect_hydrated_candidate_ids(audit_entry: dict[str, Any]) -> list[str]:
    """Collect unique candidate passage IDs from an audit entry in deterministic order."""
    seen: set[str] = set()
    ordered: list[str] = []

    def _add(pid: str) -> None:
        if pid and pid not in seen:
            seen.add(pid)
            ordered.append(pid)

    for pid in audit_entry.get("search_selected_candidate_passage_ids", []):
        _add(str(pid))
    for info in audit_entry.get("exact_keyword_hits", {}).values():
        for pid in info.get("passage_ids", []):
            _add(str(pid))
    for info in audit_entry.get("alternate_terminology_hits", {}).values():
        for pid in info.get("passage_ids", []):
            _add(str(pid))
    return ordered


def create_blank_worksheet(
    corpus: CorpusIndex,
    *,
    audit_data: dict[str, Any] | None = None,
    query_specs: Sequence[dict[str, str]] | None = None,
    is_synthetic: bool = False,
) -> dict[str, Any]:
    """Initialize a blank negative-control human verification worksheet.

    All human classification, rationale, candidate-inspection, and provenance
    attestation fields start strictly blank/null/False.
    """
    now = utc_now_iso()
    audit_by_qid: dict[str, dict[str, Any]] = {}
    if audit_data and isinstance(audit_data.get("queries"), list):
        for entry in audit_data["queries"]:
            audit_by_qid[str(entry["query_id"])] = entry

    specs = list(query_specs) if query_specs is not None else list(DEFAULT_QUERY_SPECS)
    queries_out: list[dict[str, Any]] = []

    for spec in specs:
        qid = str(spec["query_id"])
        audit_entry = audit_by_qid.get(qid, {})
        query_text = str(audit_entry.get("query_text") or spec.get("query_text") or "")
        legacy_id = str(audit_entry.get("legacy_query_id") or spec.get("legacy_query_id") or "")
        domain = str(spec.get("domain") or audit_entry.get("domain") or "")

        hydrated_candidates: list[dict[str, Any]] = []
        for pid in _collect_hydrated_candidate_ids(audit_entry):
            if corpus.get_eligibility_status(pid) != "ELIGIBLE_FROZEN_CORPUS":
                continue
            passage = corpus.inspect_passage(pid)
            hydrated_candidates.append(
                {
                    "passage_id": passage.passage_id,
                    "doc_id": passage.doc_id,
                    "source_title": passage.source_title,
                    "chunk_id": passage.chunk_id,
                    "page_number": passage.page_number,
                    "content_sha256": passage.content_sha256,
                    "corpus_eligibility_status": passage.corpus_eligibility_status,
                    "provenance_tier": passage.provenance_tier,
                    "contains_answer": None,
                    "inspection_note": "",
                }
            )

        queries_out.append(
            {
                "query_id": qid,
                "legacy_query_id": legacy_id,
                "domain": domain,
                "query_text": query_text,
                "automated_audit_status": str(
                    audit_entry.get("adjudication_status")
                    or "PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK"
                ),
                "hydrated_candidates": hydrated_candidates,
                "search_audit_log": [],
                "checked_passage_ids": [],
                "supporting_evidence": [],
                "human_answerability_classification": None,
                "d1_evaluation_impact": None,
                "external_factual_premise_assessment": None,
                "corpus_scope_checked": None,
                "verification_rationale": "",
                "revision_or_exclusion_notes": "",
                "human_provenance": {
                    "verifier_id": "",
                    "provenance_class": None,
                    "human_attestation_confirmed": False,
                    "human_attestation_text": "",
                    "ai_assistance_disclosure": "",
                    "verification_date_utc": "",
                },
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "is_synthetic": is_synthetic,
        "corpus_version": corpus.corpus_version,
        "corpus_sha256": corpus.corpus_sha256,
        "corpus_passage_count": corpus.passage_count,
        "corpus_doc_count": corpus.document_count,
        "expected_query_ids": [q["query_id"] for q in queries_out],
        "created_at_utc": now,
        "updated_at_utc": now,
        "queries": queries_out,
    }


def get_query_record(worksheet: dict[str, Any], query_id: str) -> dict[str, Any]:
    """Return mutable query record by query_id or raise KeyError."""
    for record in worksheet.get("queries", []):
        if record.get("query_id") == query_id:
            return record
    raise KeyError(
        f"Query '{query_id}' not found in worksheet. Expected one of: {NEGATIVE_CONTROL_QUERY_IDS}"
    )


def record_search_log(
    worksheet: dict[str, Any],
    query_id: str,
    search_result: SearchResult,
) -> dict[str, Any]:
    """Append a corpus-restricted search execution record to a query's audit log."""
    record = get_query_record(worksheet, query_id)
    entry = {
        "search_query_used": search_result.query_used,
        "mode": search_result.mode,
        "doc_filter": search_result.doc_filter,
        "total_hits": search_result.total_hits,
        "returned_passage_ids": [h.passage_id for h in search_result.hits],
        "corpus_version": search_result.corpus_version,
        "corpus_sha256": search_result.corpus_sha256,
        "searched_at_utc": utc_now_iso(),
    }
    record.setdefault("search_audit_log", []).append(entry)
    worksheet["updated_at_utc"] = utc_now_iso()
    return entry


def add_evidence_citation(
    worksheet: dict[str, Any],
    corpus: CorpusIndex,
    *,
    query_id: str,
    passage_id: str,
    verbatim_excerpt: str,
    search_query_used: str,
    note: str = "",
) -> dict[str, Any]:
    """Verify and append a corpus-eligible verbatim evidence citation to a query."""
    cleaned_search = search_query_used.strip()
    if not cleaned_search:
        raise ValueError("search_query_used must be non-empty when recording evidence.")
    passage = corpus.verify_evidence_citation(passage_id, verbatim_excerpt)
    record = get_query_record(worksheet, query_id)
    citation = {
        "doc_id": passage.doc_id,
        "source_title": passage.source_title,
        "content_sha256": passage.content_sha256,
        "passage_id": passage.passage_id,
        "chunk_id": passage.chunk_id,
        "page_number": passage.page_number,
        "verbatim_excerpt": verbatim_excerpt,
        "search_query_used": cleaned_search,
        "corpus_eligibility_status": passage.corpus_eligibility_status,
        "provenance_tier": passage.provenance_tier,
        "note": note.strip(),
        "recorded_at_utc": utc_now_iso(),
    }
    record.setdefault("supporting_evidence", []).append(citation)
    checked = record.setdefault("checked_passage_ids", [])
    if passage.passage_id not in checked:
        checked.append(passage.passage_id)
    worksheet["updated_at_utc"] = utc_now_iso()
    return citation


def load_worksheet(path: Path) -> dict[str, Any]:
    """Load an existing negative-control verification worksheet JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def save_worksheet(
    worksheet: dict[str, Any],
    output_path: Path,
    *,
    backup_dir: Path | None = None,
) -> dict[str, Any]:
    """Atomically save worksheet JSON, write a timestamped backup, and record SHA-256."""
    worksheet["updated_at_utc"] = utc_now_iso()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_backup_dir = backup_dir if backup_dir is not None else (output_path.parent / "backups")
    if backup_dir is None and output_path.parent == DEFAULT_BACKUP_DIR.parent:
        resolved_backup_dir = DEFAULT_BACKUP_DIR
    resolved_backup_dir.mkdir(parents=True, exist_ok=True)

    serialized = json.dumps(worksheet, indent=2, ensure_ascii=False) + "\n"
    tmp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    tmp_path.write_text(serialized, encoding="utf-8")
    tmp_path.replace(output_path)

    stamp = utc_backup_stamp()
    backup_path = resolved_backup_dir / f"{output_path.stem}_{stamp}{output_path.suffix}"
    backup_path.write_text(serialized, encoding="utf-8")

    file_sha = sha256_file(output_path)
    backup_sha = sha256_file(backup_path)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "saved_at_utc": worksheet["updated_at_utc"],
        "worksheet_path": str(output_path),
        "worksheet_sha256": file_sha,
        "backup_path": str(backup_path),
        "backup_sha256": backup_sha,
        "corpus_version": worksheet.get("corpus_version"),
        "corpus_sha256": worksheet.get("corpus_sha256"),
        "is_synthetic": bool(worksheet.get("is_synthetic", False)),
    }
    hash_manifest_path = Path(f"{output_path}.sha256.json")
    hash_manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def export_markdown_report(
    worksheet: dict[str, Any],
    output_path: Path,
) -> dict[str, str]:
    """Export a human-readable Markdown verification report and return its path + SHA-256."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    is_synthetic = bool(worksheet.get("is_synthetic", False))
    header_prefix = "[SYNTHETIC] " if is_synthetic else ""
    lines: list[str] = [
        f"# {header_prefix}S5-C3 Negative-Control Human Verification Export",
        "",
        f"- **Schema Version:** `{worksheet.get('schema_version')}`",
        f"- **Corpus Version:** `{worksheet.get('corpus_version')}`",
        f"- **Corpus SHA-256:** `{worksheet.get('corpus_sha256')}`",
        f"- **Eligible Corpus Size:** `{worksheet.get('corpus_passage_count')}` passages / "
        f"`{worksheet.get('corpus_doc_count')}` documents",
        f"- **Updated (UTC):** `{worksheet.get('updated_at_utc')}`",
        "",
        "---",
        "",
    ]

    for q in worksheet.get("queries", []):
        prov = q.get("human_provenance", {})
        lines.extend(
            [
                f"## `{q.get('query_id')}` (Legacy `{q.get('legacy_query_id')}`)",
                "",
                f"**Query:** *\"{q.get('query_text')}\"*",
                f"- **Classification:** `{q.get('human_answerability_classification')}`",
                f"- **D1 Evaluation Impact:** `{q.get('d1_evaluation_impact')}`",
                f"- **External Premise Assessment:** `{q.get('external_factual_premise_assessment')}`",
                f"- **Corpus Scope Checked:** `{q.get('corpus_scope_checked')}`",
                f"- **Verification Rationale:** {q.get('verification_rationale') or '(blank)'}",
                f"- **Revision / Exclusion Notes:** {q.get('revision_or_exclusion_notes') or '(none)'}",
                f"- **Verifier ID:** `{prov.get('verifier_id') or '(blank)'}`",
                f"- **Provenance Class:** `{prov.get('provenance_class')}`",
                f"- **Human Attestation Confirmed:** `{prov.get('human_attestation_confirmed')}`",
                f"- **Human Attestation Text:** {prov.get('human_attestation_text') or '(blank)'}",
                f"- **AI Assistance Disclosure:** {prov.get('ai_assistance_disclosure') or '(blank)'}",
                f"- **Verification Date (UTC):** `{prov.get('verification_date_utc') or '(blank)'}`",
                f"- **Checked Passages Count:** `{len(q.get('checked_passage_ids', []))}`",
                f"- **Corpus Searches Logged:** `{len(q.get('search_audit_log', []))}`",
                "",
            ]
        )
        ev_list = q.get("supporting_evidence", [])
        if ev_list:
            lines.append("### Supporting Corpus-Eligible Evidence")
            lines.append("")
            for idx, ev in enumerate(ev_list, start=1):
                lines.extend(
                    [
                        f"{idx}. **`{ev.get('passage_id')}`** (`{ev.get('doc_id')}`, "
                        f"Page `{ev.get('page_number')}`, SHA-256 `{ev.get('content_sha256')}`, "
                        f"Eligibility `{ev.get('corpus_eligibility_status')}`)",
                        f"   - **Search Query Used:** `{ev.get('search_query_used')}`",
                        f"   - **Verbatim Excerpt:** `\"{ev.get('verbatim_excerpt')}\"`",
                    ]
                )
            lines.append("")
        lines.append("---")
        lines.append("")

    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {
        "export_path": str(output_path),
        "export_sha256": sha256_file(output_path),
    }
