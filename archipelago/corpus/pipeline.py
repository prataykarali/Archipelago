"""Checkpointed end-to-end corpus reconstruction pipeline for Archipelago D14.1.

Orchestrates license gating, checkpointed OA acquisition, baseline v2 cache
reuse, native PDF/HTML/RFC extraction, structural filtering, section-aware
segmentation, concept/domain enrichment, lexical indexing, and versioned
``corpus_v3_d14`` manifest + report generation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import logging
from pathlib import Path
from typing import Any

from archipelago.corpus.acquire import DEFAULT_HF_CACHE_SNAPSHOT, acquire_source
from archipelago.corpus.catalog import (
    CORPUS_VERSION_V3,
    PARENT_CORPUS_VERSION,
    PARENT_MANIFEST_REL_PATH,
    SourceFormat,
    SourceSpec,
    build_default_source_catalog,
)
from archipelago.corpus.enricher import (
    ConceptMatcher,
    LexicalIndexAccumulator,
    build_jsonl_record,
)
from archipelago.corpus.extractors import (
    ExtractedUnit,
    extract_html_units,
    extract_pdf_units,
    extract_text_rfc_units,
    sha256_file,
)
from archipelago.corpus.license_gate import verify_license_register
from archipelago.corpus.reports import (
    build_coverage_matrix_rows,
    write_coverage_matrix_csv,
    write_ingestion_report_md,
    write_license_register_csv,
    write_manifests,
    write_source_inventory_csv,
)
from archipelago.corpus.segmenter import SegmentationStats, segment_units

logger = logging.getLogger(__name__)

MANIFEST_SCHEMA_V3 = "archipelago.d14_corpus_v3.manifest.v1"
DEFAULT_OUTPUT_REL_DIR = Path("data") / "artifacts" / "corpus_v3_d14"
DEFAULT_REPORTS_REL_DIR = Path("docs") / "reports" / "d14"
DEFAULT_GRAPH_REL_PATH = Path("host_inference") / "fixtures" / "okf_graph.json"
PASSAGE_JSONL_FILENAME = "d14_candidate_passages_v3.jsonl"
CHECKPOINT_FILENAME = "pipeline_checkpoint.json"


@dataclass(frozen=True)
class PipelineConfig:
    """Configuration for a reproducible D14.1 corpus build run."""

    repo_root: Path
    output_dir: Path
    reports_dir: Path
    graph_path: Path
    hf_cache_dir: Path = DEFAULT_HF_CACHE_SNAPSHOT
    allow_network: bool = True
    resume: bool = True


def _load_parent_baseline(
    repo_root: Path,
    specs: list[SourceSpec],
) -> tuple[str, str, dict[str, tuple[int, int]]]:
    """Read frozen corpus_v2_d10_3025 manifest (read-only) for lineage and before counts."""
    manifest_path = repo_root / PARENT_MANIFEST_REL_PATH
    if not manifest_path.is_file():
        return "", "", {}
    parent_manifest_sha = sha256_file(manifest_path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    parent_passage_sha = str(payload.get("passage_index_sha256") or "")
    doc_to_domain = {s.doc_id: s.domain for s in specs}
    domain_docs: dict[str, int] = {}
    domain_passages: dict[str, int] = {}
    for entry in payload.get("documents") or []:
        doc_id = str(entry.get("doc_id") or "")
        domain = doc_to_domain.get(doc_id, "AI & Machine Learning")
        domain_docs[domain] = domain_docs.get(domain, 0) + 1
        domain_passages[domain] = domain_passages.get(domain, 0) + int(entry.get("passages", 0))
    baseline_counts = {dom: (domain_docs[dom], domain_passages[dom]) for dom in domain_docs}
    return parent_manifest_sha, parent_passage_sha, baseline_counts


def _extract_source_units(spec: SourceSpec, local_paths: tuple[Path, ...]) -> list[ExtractedUnit]:
    """Dispatch extraction based on ``spec.source_format``."""
    if spec.source_format == SourceFormat.PDF:
        return extract_pdf_units(local_paths[0])
    if spec.source_format == SourceFormat.HTML:
        return extract_html_units(list(local_paths))
    if spec.source_format == SourceFormat.TXT:
        return extract_text_rfc_units(local_paths[0])
    return []


def _save_checkpoint(checkpoint_path: Path, state: dict[str, Any]) -> None:
    """Persist checkpoint atomically so interrupted runs can resume cleanly."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = checkpoint_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(checkpoint_path)


def run_pipeline(
    config: PipelineConfig,
    *,
    specs: list[SourceSpec] | None = None,
) -> dict[str, Any]:
    """Execute the full D14.1 corpus pipeline and emit all reports and manifests."""
    catalog = specs if specs is not None else build_default_source_catalog()
    approved_specs, decisions_list = verify_license_register(catalog)
    decisions_map = {d.source_id: d for d in decisions_list}

    parent_manifest_sha, parent_passage_sha, baseline_counts = _load_parent_baseline(
        config.repo_root, catalog
    )
    concept_matcher = ConceptMatcher.from_graph_path(config.graph_path)
    lexical_acc = LexicalIndexAccumulator()

    raw_dir = config.output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = config.output_dir / CHECKPOINT_FILENAME
    jsonl_path = config.output_dir / PASSAGE_JSONL_FILENAME
    tmp_jsonl = jsonl_path.with_suffix(".jsonl.tmp")

    doc_results: dict[str, dict[str, Any]] = {}
    failed_sources: list[dict[str, Any]] = []
    seen_fingerprints: set[str] = set()
    agg_filter = SegmentationStats()
    total_words = 0
    total_printed_mapped = 0
    added_doc_ids: list[str] = []
    reextracted_doc_ids: list[str] = []
    manifest_docs: list[dict[str, Any]] = []

    with tmp_jsonl.open("w", encoding="utf-8") as out_handle:
        for spec in approved_specs:
            logger.info("Processing %s (%s)", spec.source_id, spec.domain)
            acquired = acquire_source(
                spec,
                raw_dir=raw_dir,
                hf_cache_dir=config.hf_cache_dir,
                allow_network=config.allow_network,
            )
            if not acquired.acquired_ok:
                logger.warning("Skipping %s: %s", spec.source_id, acquired.error)
                failed_sources.append(
                    {"source_id": spec.source_id, "domain": spec.domain, "error": acquired.error}
                )
                doc_results[spec.source_id] = {
                    "acquisition_status": f"failed:{acquired.error}",
                    "sha256": "",
                    "total_bytes": 0,
                    "extracted_units": 0,
                    "kept_passages": 0,
                    "filtered_total": 0,
                    "printed_page_mapped": 0,
                    "total_words": 0,
                }
                continue

            units = _extract_source_units(spec, acquired.local_paths)
            passages, seg_stats = segment_units(
                units,
                doc_id=spec.doc_id,
                source_id=spec.source_id,
                file_sha256=acquired.primary_sha256,
                seen_fingerprints=seen_fingerprints,
            )

            doc_words = 0
            doc_printed = 0
            for passage in passages:
                concept_ids = concept_matcher.match_concepts(passage.text)
                record = build_jsonl_record(passage, spec, concept_ids, CORPUS_VERSION_V3)
                out_handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                lexical_acc.add(passage.text, concept_ids)
                doc_words += passage.word_count
                if passage.printed_page is not None:
                    doc_printed += 1

            total_words += doc_words
            total_printed_mapped += doc_printed
            agg_filter.kept_passages += seg_stats.kept_passages
            agg_filter.filtered_toc += seg_stats.filtered_toc
            agg_filter.filtered_references += seg_stats.filtered_references
            agg_filter.filtered_index += seg_stats.filtered_index
            agg_filter.filtered_front_matter += seg_stats.filtered_front_matter
            agg_filter.filtered_low_quality += seg_stats.filtered_low_quality
            agg_filter.filtered_duplicates += seg_stats.filtered_duplicates

            filtered_total = (
                seg_stats.filtered_toc
                + seg_stats.filtered_references
                + seg_stats.filtered_index
                + seg_stats.filtered_front_matter
                + seg_stats.filtered_low_quality
                + seg_stats.filtered_duplicates
            )
            doc_results[spec.source_id] = {
                "acquisition_status": acquired.status,
                "sha256": acquired.primary_sha256,
                "total_bytes": acquired.total_bytes,
                "extracted_units": len(units),
                "kept_passages": seg_stats.kept_passages,
                "filtered_total": filtered_total,
                "printed_page_mapped": doc_printed,
                "total_words": doc_words,
            }
            if seg_stats.kept_passages > 0:
                if spec.origin == "baseline_v2_hf_cache":
                    reextracted_doc_ids.append(spec.doc_id)
                else:
                    added_doc_ids.append(spec.doc_id)
                manifest_docs.append(
                    {
                        "source_id": spec.source_id,
                        "doc_id": spec.doc_id,
                        "title": spec.title,
                        "domain": spec.domain,
                        "secondary_domains": list(spec.secondary_domains),
                        "license": spec.license_name,
                        "origin": spec.origin,
                        "sha256": acquired.primary_sha256,
                        "passages": seg_stats.kept_passages,
                        "words": doc_words,
                        "printed_page_mapped": doc_printed,
                    }
                )
            _save_checkpoint(
                checkpoint_path,
                {
                    "corpus_version": CORPUS_VERSION_V3,
                    "completed_sources": len(doc_results),
                    "last_source_id": spec.source_id,
                    "kept_passages_so_far": agg_filter.kept_passages,
                },
            )

    tmp_jsonl.replace(jsonl_path)
    passage_index_sha256 = sha256_file(jsonl_path)

    coverage_rows = build_coverage_matrix_rows(catalog, doc_results, baseline_counts)
    domains_meeting_target = sum(
        1 for row in coverage_rows if row["meets_2_source_target"] == "true"
    )
    excluded_count = sum(1 for s in catalog if s.origin == "excluded_commercial")
    mean_words = (
        round(total_words / agg_filter.kept_passages, 2) if agg_filter.kept_passages else 0.0
    )

    try:
        rel_jsonl = str(jsonl_path.relative_to(config.repo_root))
    except ValueError:
        rel_jsonl = str(jsonl_path)

    manifest: dict[str, Any] = {
        "schema": MANIFEST_SCHEMA_V3,
        "corpus_version": CORPUS_VERSION_V3,
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "parent_corpus_version": PARENT_CORPUS_VERSION,
        "parent_manifest_path": PARENT_MANIFEST_REL_PATH,
        "parent_manifest_sha256": parent_manifest_sha,
        "parent_passage_index_sha256": parent_passage_sha,
        "graph_sha256": sha256_file(config.graph_path) if config.graph_path.is_file() else "",
        "passage_jsonl_rel_path": rel_jsonl,
        "passage_index_sha256": passage_index_sha256,
        "totals": {
            "ingested_documents": len(manifest_docs),
            "reextracted_baseline_documents": len(reextracted_doc_ids),
            "added_oa_documents": len(added_doc_ids),
            "failed_oa_sources": len(failed_sources),
            "excluded_commercial_sources": excluded_count,
            "total_passages": agg_filter.kept_passages,
            "total_words": total_words,
            "mean_words_per_passage": mean_words,
            "printed_page_mapped_passages": total_printed_mapped,
            "domains_covered": sum(
                1 for row in coverage_rows if int(row["d14_v3_fulltext_passages"]) > 0
            ),
            "domains_meeting_target": domains_meeting_target,
        },
        "structural_filtering": {
            "filtered_toc": agg_filter.filtered_toc,
            "filtered_references": agg_filter.filtered_references,
            "filtered_index": agg_filter.filtered_index,
            "filtered_front_matter": agg_filter.filtered_front_matter,
            "filtered_low_quality": agg_filter.filtered_low_quality,
            "filtered_duplicates": agg_filter.filtered_duplicates,
        },
        "indexing": lexical_acc.summary(),
        "reextracted_doc_ids": reextracted_doc_ids,
        "added_doc_ids": added_doc_ids,
        "domain_coverage": coverage_rows,
        "documents": manifest_docs,
    }

    write_source_inventory_csv(
        config.reports_dir / "D14_SOURCE_INVENTORY.csv", catalog, doc_results
    )
    write_license_register_csv(
        config.reports_dir / "D14_SOURCE_LICENSE_REGISTER.csv",
        catalog,
        decisions_map,
        doc_results,
    )
    write_coverage_matrix_csv(config.reports_dir / "D14_CORPUS_COVERAGE_MATRIX.csv", coverage_rows)
    write_manifests(config.reports_dir, manifest)
    write_ingestion_report_md(
        config.reports_dir / "D14_INGESTION_REPORT.md",
        manifest,
        coverage_rows,
        failed_sources,
    )
    return manifest
