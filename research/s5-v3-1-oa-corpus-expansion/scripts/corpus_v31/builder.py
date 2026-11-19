"""Immutable S5-v3.1 Corpus v3.1 builder combining 818 v3 passages + 4 new OA sources."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .constants import (
    CORPUS_V31_MANIFEST_SCHEMA_VERSION,
    CORPUS_V31_SCHEMA_VERSION,
    NEAR_DUP_JACCARD_THRESHOLD,
    PRIOR_V3_CORPUS_EXPECTED_SHA256,
    PRIOR_V3_CORPUS_JSONL,
    PRIOR_V3_EXPECTED_ELIGIBLE_COUNT,
    SOURCE_LICENSE_MANIFEST_SCHEMA_VERSION,
    SPLIT_CORPUS_SHARED,
)
from .extractors import (
    compute_file_sha256,
    extract_epub_units,
    extract_latex_units,
    extract_libretexts_html_units,
    extract_pdf_units,
)
from .models import (
    CorpusV31Passage,
    DuplicatePair,
    ExtractedUnit,
    ExtractionAuditStats,
    SourceLicenseRecord,
)
from .quality_dedup import (
    chunk_extracted_units,
    classify_chunk_rejection,
    compute_normalized_sha256,
    compute_passage_sha256,
    count_tokens,
    find_near_duplicates,
)
from .registry import build_default_new_oa_source_records

JSON_INDENT = 2
PRIOR_V3_MANIFEST_REL = Path(
    "research/s5-v3-benchmark-expansion/manifests/s5v3_corpus_manifest.json"
)


class CorpusV31BuildError(RuntimeError):
    """Raised when Corpus v3.1 integrity, provenance, or collision checks fail."""


def load_prior_v3_eligible_passages(
    repo_root: Path,
    prior_jsonl: Path | None = None,
    verify_sha256: bool = True,
) -> tuple[list[CorpusV31Passage], str]:
    """Load the immutable 818 eligible S5-v3 passages without modifying v3."""
    path = prior_jsonl if prior_jsonl is not None else (repo_root / PRIOR_V3_CORPUS_JSONL)
    if not path.is_file():
        raise CorpusV31BuildError(f"Prior S5-v3 corpus JSONL missing: {path}")

    actual_sha = compute_file_sha256(path)
    if verify_sha256 and actual_sha != PRIOR_V3_CORPUS_EXPECTED_SHA256:
        raise CorpusV31BuildError(
            f"Prior S5-v3 corpus SHA-256 mismatch: expected "
            f"{PRIOR_V3_CORPUS_EXPECTED_SHA256}, got {actual_sha}"
        )

    retained: list[CorpusV31Passage] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            raw = json.loads(line)
            if not raw.get("is_usable", False) or raw.get("is_exact_duplicate", False):
                continue
            retained.append(
                CorpusV31Passage(
                    passage_id=str(raw["passage_id"]),
                    source_doc_id=str(raw["source_doc_id"]),
                    source_title=str(raw["source_title"]),
                    domain=str(raw["domain"]),
                    origin_tier="retained_s5v3_eligible",
                    provenance_class=str(raw["provenance_class"]),
                    license_id=str(raw["license_id"]),
                    redistribution_permission=str(raw["redistribution_permission"]),
                    source_sha256=str(raw["source_sha256"]),
                    page_start=int(raw["page_start"]),
                    page_end=int(raw["page_end"]),
                    section_ref=f"page_{int(raw['page_start']):04d}",
                    section_heading=str(raw.get("section_heading", "")),
                    chunk_index=int(raw["chunk_index"]),
                    text=str(raw["text"]),
                    char_count=int(raw["char_count"]),
                    token_count=int(raw["token_count"]),
                    normalized_text_sha256=str(raw["normalized_text_sha256"]),
                    passage_sha256=str(raw["passage_sha256"]),
                    quality_flags=tuple(str(f) for f in raw.get("quality_flags", ())),
                    is_usable=True,
                    is_exact_duplicate=False,
                    is_near_duplicate=False,
                    canonical_passage_id=str(raw["passage_id"]),
                    split_assignment=SPLIT_CORPUS_SHARED,
                )
            )

    if verify_sha256 and len(retained) != PRIOR_V3_EXPECTED_ELIGIBLE_COUNT:
        raise CorpusV31BuildError(
            f"Expected {PRIOR_V3_EXPECTED_ELIGIBLE_COUNT} prior eligible v3 passages, "
            f"got {len(retained)}"
        )
    return retained, actual_sha


def _extract_units_for_source(
    rec: SourceLicenseRecord,
    repo_root: Path,
) -> list[ExtractedUnit]:
    """Dispatch deterministic extraction by verified source_format."""
    path = Path(rec.local_raw_path)
    resolved = path if path.is_absolute() else (repo_root / path)
    if rec.source_format == "epub":
        return extract_epub_units(resolved)
    if rec.source_format == "html_chapters":
        return extract_libretexts_html_units(resolved)
    if rec.source_format == "pdf":
        return extract_pdf_units(resolved)
    if rec.source_format == "latex":
        return extract_latex_units(resolved)
    raise CorpusV31BuildError(f"Unsupported source_format '{rec.source_format}' for {rec.doc_id}")


def _format_v31_passage_id(
    doc_id: str,
    page_start: int | None,
    chunk_index: int,
) -> str:
    """Construct collision-free S5-v3.1 passage identifier."""
    loc = f"p{page_start:04d}" if page_start is not None else "s0000"
    return f"s5v31_{doc_id}_{loc}_c{chunk_index:04d}"


def build_corpus_v31(
    repo_root: Path,
    output_jsonl: Path,
    output_corpus_manifest: Path,
    output_license_manifest: Path,
    prior_v3_jsonl: Path | None = None,
    new_sources: list[SourceLicenseRecord] | None = None,
    verify_prior_sha256: bool = True,
    near_dup_threshold: float = NEAR_DUP_JACCARD_THRESHOLD,
) -> tuple[list[CorpusV31Passage], dict[str, object], dict[str, object]]:
    """Build immutable Corpus v3.1 JSONL and public metadata-only manifests."""
    prior_passages, prior_sha = load_prior_v3_eligible_passages(
        repo_root=repo_root,
        prior_jsonl=prior_v3_jsonl,
        verify_sha256=verify_prior_sha256,
    )
    active_new = (
        new_sources if new_sources is not None else build_default_new_oa_source_records(repo_root)
    )

    seen_ids: set[str] = {p.passage_id for p in prior_passages}
    canonical_by_norm: dict[str, str] = {
        p.normalized_text_sha256: p.passage_id for p in prior_passages
    }
    staged_new: list[CorpusV31Passage] = []
    audit_by_doc: dict[str, dict[str, int]] = {}
    exact_dup_pairs: list[DuplicatePair] = []

    for rec in sorted(active_new, key=lambda item: item.doc_id):
        if not rec.source_sha256:
            raise CorpusV31BuildError(
                f"Source {rec.doc_id} missing local artifact or SHA-256: {rec.local_raw_path}"
            )
        units = _extract_units_for_source(rec, repo_root)
        cand_chunks = chunk_extracted_units(units)

        dropped_bib = 0
        dropped_malformed = 0
        dropped_exact = 0
        kept_for_doc: list[CorpusV31Passage] = []

        for ch in cand_chunks:
            rej = classify_chunk_rejection(ch.section_heading, ch.text)
            if rej == "boilerplate_or_bib":
                dropped_bib += 1
                continue
            if rej == "malformed_or_short":
                dropped_malformed += 1
                continue

            pid = _format_v31_passage_id(rec.doc_id, ch.page_start, ch.chunk_index)
            if pid in seen_ids:
                raise CorpusV31BuildError(f"Passage ID collision detected: {pid}")
            norm_sha = compute_normalized_sha256(ch.text)
            if norm_sha in canonical_by_norm:
                dropped_exact += 1
                exact_dup_pairs.append(
                    DuplicatePair(
                        passage_id=pid,
                        matched_passage_id=canonical_by_norm[norm_sha],
                        kind="exact",
                        similarity=1.0,
                    )
                )
                continue

            seen_ids.add(pid)
            canonical_by_norm[norm_sha] = pid
            kept_for_doc.append(
                CorpusV31Passage(
                    passage_id=pid,
                    source_doc_id=rec.doc_id,
                    source_title=rec.title,
                    domain=rec.domain,
                    origin_tier=rec.origin_tier,
                    provenance_class=rec.provenance_class,
                    license_id=rec.license_id,
                    redistribution_permission=rec.redistribution_permission,
                    source_sha256=rec.source_sha256,
                    page_start=ch.page_start,
                    page_end=ch.page_end,
                    section_ref=ch.section_ref,
                    section_heading=ch.section_heading,
                    chunk_index=ch.chunk_index,
                    text=ch.text,
                    char_count=len(ch.text),
                    token_count=count_tokens(ch.text),
                    normalized_text_sha256=norm_sha,
                    passage_sha256=compute_passage_sha256(ch.text),
                    quality_flags=(),
                    is_usable=True,
                    is_exact_duplicate=False,
                    is_near_duplicate=False,
                    canonical_passage_id=pid,
                    split_assignment=SPLIT_CORPUS_SHARED,
                )
            )

        staged_new.extend(kept_for_doc)
        audit_by_doc[rec.doc_id] = {
            "raw_units": len(units),
            "candidate_chunks": len(cand_chunks),
            "dropped_boilerplate_or_bib": dropped_bib,
            "dropped_malformed_or_short": dropped_malformed,
            "dropped_exact_duplicates": dropped_exact,
            "dropped_near_duplicates": 0,
        }

    combined_pre_near = prior_passages + staged_new
    near_pairs = find_near_duplicates(
        [(p.passage_id, p.text) for p in combined_pre_near],
        threshold=near_dup_threshold,
    )
    prior_id_set = {p.passage_id for p in prior_passages}
    near_drop_ids: set[str] = set()
    for pair in near_pairs:
        if pair.passage_id not in prior_id_set:
            near_drop_ids.add(pair.passage_id)
        elif pair.matched_passage_id not in prior_id_set:
            near_drop_ids.add(pair.matched_passage_id)

    final_passages: list[CorpusV31Passage] = []
    for p in combined_pre_near:
        if p.passage_id in near_drop_ids:
            audit_by_doc[p.source_doc_id]["dropped_near_duplicates"] += 1
            continue
        final_passages.append(p)

    retained_by_doc = Counter(p.source_doc_id for p in final_passages)
    extraction_stats = [
        ExtractionAuditStats(
            doc_id=doc_id,
            raw_units=vals["raw_units"],
            candidate_chunks=vals["candidate_chunks"],
            dropped_boilerplate_or_bib=vals["dropped_boilerplate_or_bib"],
            dropped_malformed_or_short=vals["dropped_malformed_or_short"],
            dropped_exact_duplicates=vals["dropped_exact_duplicates"],
            dropped_near_duplicates=vals["dropped_near_duplicates"],
            retained_passages=retained_by_doc[doc_id],
        ).to_dict()
        for doc_id, vals in sorted(audit_by_doc.items())
    ]

    jsonl_payload = "\n".join(
        json.dumps(p.to_jsonl_dict(), ensure_ascii=False, sort_keys=True) for p in final_passages
    ) + ("\n" if final_passages else "")
    jsonl_sha256 = hashlib.sha256(jsonl_payload.encode("utf-8")).hexdigest()
    passage_ids_sha256 = hashlib.sha256(
        "\n".join(p.passage_id for p in final_passages).encode("utf-8")
    ).hexdigest()

    output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    output_jsonl.write_text(jsonl_payload, encoding="utf-8")

    license_manifest: dict[str, object] = {
        "schema_version": SOURCE_LICENSE_MANIFEST_SCHEMA_VERSION,
        "contains_raw_passage_text": False,
        "okf_graph_db_dependency": False,
        "excluded_sources_policy": [
            "mixu/distsysbook (strictly excluded — unverified/ambiguous reuse rights)",
            "okf_graph.db (missing v2.1 DB — never reconstructed or depended upon)",
            "Copyrighted Elsevier / z-lib PDFs and synthetic upload stubs",
        ],
        "prior_v3_corpus_reference": {
            "path": str(PRIOR_V3_CORPUS_JSONL),
            "sha256": prior_sha,
            "retained_eligible_passages": len(prior_passages),
            "prior_manifest_path": str(PRIOR_V3_MANIFEST_REL),
        },
        "new_oa_sources": [rec.to_dict() for rec in active_new],
    }

    try:
        jsonl_rel = str(output_jsonl.relative_to(repo_root))
    except ValueError:
        jsonl_rel = str(output_jsonl)

    domain_counts = dict(sorted(Counter(p.domain for p in final_passages).items()))
    doc_counts = dict(sorted(Counter(p.source_doc_id for p in final_passages).items()))
    prov_counts = dict(sorted(Counter(p.provenance_class for p in final_passages).items()))
    tier_counts = dict(sorted(Counter(p.origin_tier for p in final_passages).items()))

    corpus_manifest: dict[str, object] = {
        "schema_version": CORPUS_V31_MANIFEST_SCHEMA_VERSION,
        "corpus_schema_version": CORPUS_V31_SCHEMA_VERSION,
        "deterministic": True,
        "contains_raw_passage_text": False,
        "okf_graph_db_dependency": False,
        "private_corpus_jsonl": {
            "path": jsonl_rel,
            "gitignored_required": True,
            "sha256": jsonl_sha256,
            "passage_ids_sha256": passage_ids_sha256,
        },
        "summary": {
            "total_passages": len(final_passages),
            "retained_v3_passages": len(prior_passages),
            "new_oa_passages": len(final_passages) - len(prior_passages),
            "source_document_count": len(doc_counts),
            "domain_count": len(domain_counts),
            "total_chars": sum(p.char_count for p in final_passages),
            "total_tokens": sum(p.token_count for p in final_passages),
            "passages_with_page_numbers": sum(
                1 for p in final_passages if p.page_start is not None
            ),
            "passages_without_fixed_pages": sum(1 for p in final_passages if p.page_start is None),
            "domain_passage_counts": domain_counts,
            "source_doc_passage_counts": doc_counts,
            "provenance_class_counts": prov_counts,
            "origin_tier_counts": tier_counts,
        },
        "deduplication": {
            "exact_duplicates_dropped": len(exact_dup_pairs),
            "near_duplicates_detected": len(near_pairs),
            "near_duplicates_dropped_from_new_oa": len(near_drop_ids),
            "exact_duplicate_pairs": [asdict(pair) for pair in exact_dup_pairs],
            "near_duplicate_pairs": [asdict(pair) for pair in near_pairs],
        },
        "new_source_extraction_audit": extraction_stats,
    }

    output_license_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_license_manifest.write_text(
        json.dumps(license_manifest, indent=JSON_INDENT, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    output_corpus_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_corpus_manifest.write_text(
        json.dumps(corpus_manifest, indent=JSON_INDENT, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return final_passages, corpus_manifest, license_manifest
