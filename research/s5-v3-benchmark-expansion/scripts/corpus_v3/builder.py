"""End-to-end deterministic S5-v3 Corpus v3 builder and manifest generator."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .chunking import chunk_pages
from .constants import (
    CORPUS_SCHEMA_VERSION,
    MANIFEST_SCHEMA_VERSION,
    MISSING_OA_DOMAINS,
    NEAR_DUP_JACCARD_THRESHOLD,
    SPLIT_CORPUS_SHARED,
    VERIFIED_LOCAL_OA_SOURCES,
)
from .dedup import (
    compute_normalized_sha256,
    compute_passage_sha256,
    detect_duplicates,
)
from .extractors import extract_document, validate_source_eligibility
from .leakage import verify_leakage_guard
from .models import (
    DeduplicationReport,
    DocumentCompleteness,
    LeakageCheckResult,
    PassageRecord,
    SourceDocumentSpec,
)
from .quality import assess_passage_quality, count_tokens

JSON_INDENT = 2


class LeakageGuardError(RuntimeError):
    """Raised when Corpus v3 fails train/dev/test or forbidden-hash leakage checks."""


def load_default_source_specs() -> list[SourceDocumentSpec]:
    """Build typed SourceDocumentSpec objects from the verified Module A registry."""
    specs: list[SourceDocumentSpec] = []
    for raw in VERIFIED_LOCAL_OA_SOURCES:
        specs.append(
            SourceDocumentSpec(
                doc_id=str(raw["doc_id"]),
                path=str(raw["path"]),
                title=str(raw["title"]),
                source_format=str(raw["source_format"]),
                domain=str(raw["domain"]),
                provenance_class=str(raw["provenance_class"]),
                license_id=str(raw["license_id"]),
                redistribution_permission=str(raw["redistribution_permission"]),
                expected_sha256=str(raw["expected_sha256"]),
                source_url=str(raw["source_url"]),
                eligible=bool(raw["eligible"]),
            )
        )
    return specs


def _format_passage_id(doc_id: str, page_start: int, chunk_index: int) -> str:
    """Create a deterministic passage identifier encoding doc, start page, and chunk."""
    return f"s5v3_{doc_id}_p{page_start:04d}_c{chunk_index:04d}"


def _serialize_passages_jsonl(passages: list[PassageRecord]) -> str:
    """Serialize passages to canonical UTF-8 JSONL (sorted keys, LF endings)."""
    lines = [
        json.dumps(rec.to_jsonl_dict(), ensure_ascii=False, sort_keys=True) for rec in passages
    ]
    return "\n".join(lines) + ("\n" if lines else "")


def build_corpus_v3(
    repo_root: Path,
    output_jsonl: Path,
    output_manifest: Path,
    sources: list[SourceDocumentSpec] | None = None,
    verify_source_sha256: bool = True,
    split_by_doc: dict[str, str] | None = None,
    forbidden_hashes: frozenset[str] = frozenset(),
    near_dup_threshold: float = NEAR_DUP_JACCARD_THRESHOLD,
) -> tuple[list[PassageRecord], dict[str, object]]:
    """Build Corpus v3 JSONL (gitignored) and public metadata-only manifest.

    Args:
        repo_root: Repository root for resolving relative source paths.
        output_jsonl: Path to write private passage JSONL.
        output_manifest: Path to write public metadata-only manifest JSON.
        sources: Optional custom list of SourceDocumentSpec (defaults to 4 verified OA docs).
        verify_source_sha256: Whether to enforce expected_sha256 on each source.
        split_by_doc: Optional mapping doc_id -> split label (default: corpus_shared).
        forbidden_hashes: Optional set of normalized SHA-256 hashes forbidden from corpus.
        near_dup_threshold: Shingle Jaccard threshold for near-duplicate reporting.

    Returns:
        Tuple of (passages, manifest_dict).
    """
    active_sources = sources if sources is not None else load_default_source_specs()
    active_splits = split_by_doc or {}

    staged_records: list[tuple[SourceDocumentSpec, str, int, int, int, str, str]] = []
    completeness_by_doc: list[DocumentCompleteness] = []
    verified_source_rows: list[dict[str, object]] = []

    for spec in sorted(active_sources, key=lambda item: item.doc_id):
        resolved_path, actual_sha256 = validate_source_eligibility(
            spec=spec,
            repo_root=repo_root,
            verify_sha256=verify_source_sha256,
        )
        pages, completeness = extract_document(spec=spec, resolved_path=resolved_path)
        completeness_by_doc.append(completeness)

        chunks = chunk_pages(
            pages=pages,
            is_markdown=(spec.source_format == "markdown"),
        )
        for chunk in chunks:
            staged_records.append(
                (
                    spec,
                    actual_sha256,
                    chunk.page_start,
                    chunk.page_end,
                    chunk.chunk_index,
                    chunk.section_heading,
                    chunk.text,
                )
            )

        verified_source_rows.append(
            {
                "doc_id": spec.doc_id,
                "title": spec.title,
                "source_format": spec.source_format,
                "domain": spec.domain,
                "provenance_class": spec.provenance_class,
                "license_id": spec.license_id,
                "redistribution_permission": spec.redistribution_permission,
                "source_url": spec.source_url,
                "source_sha256": actual_sha256,
                "bytes": resolved_path.stat().st_size,
                "completeness": asdict(completeness),
                "extracted_passage_count": len(chunks),
            }
        )

    dedup_inputs: list[tuple[str, str, str]] = []
    pre_metadata: list[tuple[str, str, str]] = []
    for spec, _sha, page_start, _page_end, chunk_idx, _heading, text in staged_records:
        pid = _format_passage_id(spec.doc_id, page_start, chunk_idx)
        norm_sha = compute_normalized_sha256(text)
        pass_sha = compute_passage_sha256(text)
        dedup_inputs.append((pid, text, norm_sha))
        pre_metadata.append((pid, norm_sha, pass_sha))

    dedup_report, canonical_map = detect_duplicates(
        passage_items=dedup_inputs,
        near_dup_threshold=near_dup_threshold,
    )

    passages: list[PassageRecord] = []
    for staged, (pid, norm_sha, pass_sha) in zip(staged_records, pre_metadata, strict=True):
        spec, actual_sha256, page_start, page_end, chunk_idx, heading, text = staged
        quality = assess_passage_quality(text)
        canonical_id = canonical_map[pid]
        split_label = active_splits.get(spec.doc_id, SPLIT_CORPUS_SHARED)
        passages.append(
            PassageRecord(
                passage_id=pid,
                source_doc_id=spec.doc_id,
                source_title=spec.title,
                domain=spec.domain,
                provenance_class=spec.provenance_class,
                license_id=spec.license_id,
                redistribution_permission=spec.redistribution_permission,
                source_sha256=actual_sha256,
                page_start=page_start,
                page_end=page_end,
                chunk_index=chunk_idx,
                section_heading=heading,
                text=text,
                char_count=len(text),
                token_count=count_tokens(text),
                normalized_text_sha256=norm_sha,
                passage_sha256=pass_sha,
                quality_flags=quality.flags,
                quality_score=quality.quality_score,
                is_usable=quality.is_usable,
                is_exact_duplicate=(canonical_id != pid),
                canonical_passage_id=canonical_id,
                split_assignment=split_label,
            )
        )

    leakage_result = verify_leakage_guard(
        passages=passages,
        near_duplicate_pairs=dedup_report.near_duplicate_pairs,
        forbidden_hashes=forbidden_hashes,
        enforce_doc_level_isolation=True,
    )
    if not leakage_result.passed:
        raise LeakageGuardError(
            "Corpus v3 leakage guard failed: " + "; ".join(leakage_result.violations)
        )

    jsonl_payload = _serialize_passages_jsonl(passages)
    jsonl_sha256 = hashlib.sha256(jsonl_payload.encode("utf-8")).hexdigest()
    passage_ids_sha256 = hashlib.sha256(
        "\n".join(rec.passage_id for rec in passages).encode("utf-8")
    ).hexdigest()

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    output_jsonl.write_text(jsonl_payload, encoding="utf-8")

    manifest = _build_manifest_dict(
        passages=passages,
        verified_source_rows=verified_source_rows,
        dedup_report=dedup_report,
        leakage_result=leakage_result,
        jsonl_sha256=jsonl_sha256,
        passage_ids_sha256=passage_ids_sha256,
        output_jsonl=output_jsonl,
        repo_root=repo_root,
    )

    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(
        json.dumps(manifest, indent=JSON_INDENT, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return passages, manifest


def _build_manifest_dict(
    passages: list[PassageRecord],
    verified_source_rows: list[dict[str, object]],
    dedup_report: DeduplicationReport,
    leakage_result: LeakageCheckResult,
    jsonl_sha256: str,
    passage_ids_sha256: str,
    output_jsonl: Path,
    repo_root: Path,
) -> dict[str, object]:
    """Assemble public metadata-only Corpus v3 manifest (zero raw passage text)."""
    provenance_counts = dict(sorted(Counter(rec.provenance_class for rec in passages).items()))
    domain_counts = dict(sorted(Counter(rec.domain for rec in passages).items()))
    quality_flag_counts: Counter[str] = Counter()
    usable_by_doc: Counter[str] = Counter()
    flagged_by_doc: Counter[str] = Counter()
    for rec in passages:
        if rec.is_usable:
            usable_by_doc[rec.source_doc_id] += 1
        if rec.quality_flags:
            flagged_by_doc[rec.source_doc_id] += 1
            for flag in rec.quality_flags:
                quality_flag_counts[flag] += 1

    for row in verified_source_rows:
        doc_id = str(row["doc_id"])
        row["usable_passage_count"] = usable_by_doc[doc_id]
        row["flagged_passage_count"] = flagged_by_doc[doc_id]

    try:
        jsonl_display_path = str(output_jsonl.relative_to(repo_root))
    except ValueError:
        jsonl_display_path = str(output_jsonl)

    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "corpus_schema_version": CORPUS_SCHEMA_VERSION,
        "deterministic": True,
        "contains_raw_passage_text": False,
        "frozen_v2_1_corpus_status": "MISSING_NOT_REPAIRED_OR_FAKED",
        "private_corpus_jsonl": {
            "path": jsonl_display_path,
            "gitignored_required": True,
            "sha256": jsonl_sha256,
            "passage_ids_sha256": passage_ids_sha256,
        },
        "summary": {
            "source_document_count": len(verified_source_rows),
            "total_passages": len(passages),
            "usable_passages": sum(1 for rec in passages if rec.is_usable),
            "unusable_passages": sum(1 for rec in passages if not rec.is_usable),
            "flagged_passages": sum(1 for rec in passages if rec.quality_flags),
            "total_chars": sum(rec.char_count for rec in passages),
            "total_tokens": sum(rec.token_count for rec in passages),
            "provenance_class_counts": provenance_counts,
            "domain_passage_counts": domain_counts,
            "quality_flag_counts": dict(sorted(quality_flag_counts.items())),
        },
        "sources": verified_source_rows,
        "deduplication": dedup_report.to_dict(),
        "leakage_guard": leakage_result.to_dict(),
        "multi_domain_coverage_gap": {
            "covered_domains": sorted(domain_counts.keys()),
            "missing_domains": list(MISSING_OA_DOMAINS),
            "sufficient_for_full_cs_multidomain_claims": False,
        },
    }
