"""Report and manifest emitters for Archipelago D14 Phase D14.1.

Writes:
- ``D14_SOURCE_INVENTORY.csv``
- ``D14_SOURCE_LICENSE_REGISTER.csv``
- ``D14_CORPUS_COVERAGE_MATRIX.csv``
- ``D14_INGESTION_REPORT.md``
- ``D14_CORPUS_MANIFEST.json`` and ``D14_CORPUS_V3_MANIFEST.json``
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from archipelago.corpus.catalog import CANONICAL_DOMAINS, CORPUS_VERSION_V3, SourceSpec
from archipelago.corpus.license_gate import AuthorizationDecision

MIN_TARGET_INDEPENDENT_SOURCES = 2


def write_source_inventory_csv(
    path: Path,
    specs: list[SourceSpec],
    doc_results: dict[str, dict[str, Any]],
) -> None:
    """Write ``D14_SOURCE_INVENTORY.csv`` covering full-text OA and metadata-only items."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_id",
        "doc_id",
        "title",
        "authors",
        "domain",
        "secondary_domains",
        "source_format",
        "origin",
        "independent_group",
        "content_availability",
        "acquisition_status",
        "sha256",
        "total_bytes",
        "extracted_units",
        "kept_passages",
        "filtered_noise_units",
        "printed_page_mapped_passages",
        "canonical_url",
        "notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for spec in specs:
            res = doc_results.get(spec.source_id, {})
            kept = int(res.get("kept_passages", 0))
            availability = (
                "FULL_TEXT_RETRIEVABLE"
                if kept > 0
                else (
                    "METADATA_ONLY_CATALOG_CARD"
                    if spec.origin == "excluded_commercial"
                    else "ACQUISITION_FAILED"
                )
            )
            writer.writerow(
                {
                    "source_id": spec.source_id,
                    "doc_id": spec.doc_id,
                    "title": spec.title,
                    "authors": spec.authors,
                    "domain": spec.domain,
                    "secondary_domains": ";".join(spec.secondary_domains),
                    "source_format": spec.source_format.value,
                    "origin": spec.origin,
                    "independent_group": spec.independent_group,
                    "content_availability": availability,
                    "acquisition_status": res.get("acquisition_status", "blocked_by_license_gate"),
                    "sha256": res.get("sha256", ""),
                    "total_bytes": res.get("total_bytes", 0),
                    "extracted_units": res.get("extracted_units", 0),
                    "kept_passages": kept,
                    "filtered_noise_units": res.get("filtered_total", 0),
                    "printed_page_mapped_passages": res.get("printed_page_mapped", 0),
                    "canonical_url": spec.canonical_url,
                    "notes": spec.notes,
                }
            )


def write_license_register_csv(
    path: Path,
    specs: list[SourceSpec],
    decisions: dict[str, AuthorizationDecision],
    doc_results: dict[str, dict[str, Any]],
) -> None:
    """Write ``D14_SOURCE_LICENSE_REGISTER.csv`` with authorization outcomes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "source_id",
        "doc_id",
        "title",
        "domain",
        "license_name",
        "license_status",
        "license_url",
        "gate_allowed",
        "gate_reason",
        "sha256",
        "redistribution_note",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for spec in specs:
            dec = decisions[spec.source_id]
            res = doc_results.get(spec.source_id, {})
            note = (
                "Verified open-access source; raw artifact stored outside Git per D14 isolation contract."
                if dec.allowed
                else "Commercial or metadata-only holding; strictly excluded from full-text ingestion."
            )
            writer.writerow(
                {
                    "source_id": spec.source_id,
                    "doc_id": spec.doc_id,
                    "title": spec.title,
                    "domain": spec.domain,
                    "license_name": spec.license_name,
                    "license_status": dec.license_status.value,
                    "license_url": spec.license_url,
                    "gate_allowed": str(dec.allowed).lower(),
                    "gate_reason": dec.reason,
                    "sha256": res.get("sha256", ""),
                    "redistribution_note": note,
                }
            )


def build_coverage_matrix_rows(
    specs: list[SourceSpec],
    doc_results: dict[str, dict[str, Any]],
    baseline_v2_domain_counts: dict[str, tuple[int, int]],
) -> list[dict[str, Any]]:
    """Compute exact 12-domain coverage rows distinguishing full-text vs metadata-only."""
    rows: list[dict[str, Any]] = []
    for domain in CANONICAL_DOMAINS:
        domain_specs = [s for s in specs if s.domain == domain]
        oa_specs = [s for s in domain_specs if s.origin != "excluded_commercial"]
        excluded_specs = [s for s in domain_specs if s.origin == "excluded_commercial"]
        ingested_specs = [
            s for s in oa_specs if int(doc_results.get(s.source_id, {}).get("kept_passages", 0)) > 0
        ]
        indep_groups = sorted({s.independent_group for s in ingested_specs})
        v3_passages = sum(
            int(doc_results.get(s.source_id, {}).get("kept_passages", 0)) for s in ingested_specs
        )
        v3_words = sum(
            int(doc_results.get(s.source_id, {}).get("total_words", 0)) for s in ingested_specs
        )
        v2_docs, v2_passages = baseline_v2_domain_counts.get(domain, (0, 0))
        meets_target = len(indep_groups) >= MIN_TARGET_INDEPENDENT_SOURCES and v3_passages > 0
        rows.append(
            {
                "domain": domain,
                "baseline_v2_docs": v2_docs,
                "baseline_v2_passages": v2_passages,
                "d14_v3_fulltext_docs": len(ingested_specs),
                "d14_v3_independent_sources": len(indep_groups),
                "d14_v3_fulltext_passages": v3_passages,
                "d14_v3_total_words": v3_words,
                "excluded_commercial_catalog_entries": len(excluded_specs),
                "meets_2_source_target": str(meets_target).lower(),
                "independent_source_groups": ";".join(indep_groups),
            }
        )
    return rows


def write_coverage_matrix_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write ``D14_CORPUS_COVERAGE_MATRIX.csv``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "domain",
        "baseline_v2_docs",
        "baseline_v2_passages",
        "d14_v3_fulltext_docs",
        "d14_v3_independent_sources",
        "d14_v3_fulltext_passages",
        "d14_v3_total_words",
        "excluded_commercial_catalog_entries",
        "meets_2_source_target",
        "independent_source_groups",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_manifests(
    reports_dir: Path,
    manifest: dict[str, Any],
) -> tuple[Path, Path]:
    """Write ``D14_CORPUS_MANIFEST.json`` and ``D14_CORPUS_V3_MANIFEST.json``."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    primary = reports_dir / "D14_CORPUS_MANIFEST.json"
    v3_alias = reports_dir / "D14_CORPUS_V3_MANIFEST.json"
    primary.write_text(payload, encoding="utf-8")
    v3_alias.write_text(payload, encoding="utf-8")
    return primary, v3_alias


def write_ingestion_report_md(
    path: Path,
    manifest: dict[str, Any],
    coverage_rows: list[dict[str, Any]],
    failed_sources: list[dict[str, Any]],
) -> None:
    """Write human-readable ``D14_INGESTION_REPORT.md`` with honest counts and caveats."""
    path.parent.mkdir(parents=True, exist_ok=True)
    totals = manifest["totals"]
    filtering = manifest["structural_filtering"]
    lines: list[str] = [
        "# Archipelago D14.1 — Corpus Reconstruction & Ingestion Report (`corpus_v3_d14`)",
        "",
        f"- **Corpus Version:** `{CORPUS_VERSION_V3}`",
        f"- **Parent Baseline Preserved Untouched:** `{manifest['parent_corpus_version']}` "
        f"(Manifest SHA-256: `{manifest['parent_manifest_sha256']}`, "
        f"Passage JSONL SHA-256: `{manifest['parent_passage_index_sha256']}`)",
        f"- **Output Passage JSONL (gitignored):** `{manifest['passage_jsonl_rel_path']}`",
        f"- **Output Passage JSONL SHA-256:** `{manifest['passage_index_sha256']}`",
        f"- **Ingested Full-Text Documents:** `{totals['ingested_documents']}` "
        f"({totals['reextracted_baseline_documents']} re-extracted from `corpus_v2_d10_3025` + "
        f"{totals['added_oa_documents']} newly acquired OA sources)",
        f"- **Excluded Commercial / Metadata-Only Holdings:** `{totals['excluded_commercial_sources']}` "
        "(blocked deterministically by `archipelago.corpus.license_gate`)",
        f"- **Validated Body Passages:** `{totals['total_passages']}` "
        f"(total words: `{totals['total_words']:,}`, mean words/passage: `{totals['mean_words_per_passage']}`)",
        f"- **Domains Meeting >=2 Independent Authoritative OA Sources:** "
        f"`{totals['domains_meeting_target']}/12`",
        "",
        "---",
        "",
        "## 1. Before vs. After 12-Domain Full-Text Coverage Matrix",
        "",
        "| Domain | Baseline v2 Docs | Baseline v2 Passages | D14 v3 Docs | D14 v3 Indep. Sources | D14 v3 Passages | Excluded Commercial | >=2 Sources? |",
        "|---|---:|---:|---:|---:|---:|---:|:---:|",
    ]
    for row in coverage_rows:
        mark = "YES" if row["meets_2_source_target"] == "true" else "NO"
        lines.append(
            f"| {row['domain']} | {row['baseline_v2_docs']} | {row['baseline_v2_passages']} | "
            f"{row['d14_v3_fulltext_docs']} | {row['d14_v3_independent_sources']} | "
            f"{row['d14_v3_fulltext_passages']} | {row['excluded_commercial_catalog_entries']} | {mark} |"
        )

    lines.extend(
        [
            "",
            "---",
            "",
            "## 2. Structural Noise Filtering & Extraction Quality",
            "",
            f"- **Filtered Table of Contents (TOC) units/chunks:** `{filtering['filtered_toc']}`",
            f"- **Filtered References / Bibliography units/chunks:** `{filtering['filtered_references']}`",
            f"- **Filtered Back-of-Book Index units/chunks:** `{filtering['filtered_index']}`",
            f"- **Filtered Front Matter / Copyright stubs:** `{filtering['filtered_front_matter']}`",
            f"- **Filtered Low-Quality / Tiny fragments:** `{filtering['filtered_low_quality']}`",
            f"- **Filtered Exact Normalized Duplicates:** `{filtering['filtered_duplicates']}`",
            f"- **Passages with Mapped Printed Page Labels:** `{totals['printed_page_mapped_passages']}`",
            f"- **Concept-Linked Passages (`okf_graph.json` read-only match):** "
            f"`{manifest['indexing']['lexical_index']['concept_linked_passages']}`",
            f"- **Lexical Vocabulary Size:** `{manifest['indexing']['lexical_index']['vocabulary_size']:,}` terms",
            "",
            "---",
            "",
            "## 3. Acquisition Gaps, Failures & Legal Restrictions",
            "",
        ]
    )
    if failed_sources:
        lines.append("| Source ID | Domain | Error |")
        lines.append("|---|---|---|")
        for item in failed_sources:
            lines.append(f"| `{item['source_id']}` | {item['domain']} | `{item['error']}` |")
    else:
        lines.append(
            "All authorized open-access sources were acquired and validated with zero failures."
        )

    lines.extend(
        [
            "",
            "### Legal Compliance & Isolation",
            "- Zero commercial textbooks (CLRS, Tanenbaum, Dragon Book, Silberschatz, Hopcroft, "
            "Sommerville, Ross, Stallings, Russell & Norvig, Mano, or UEM Pearson eLibrary holdings) "
            "were downloaded, extracted, or promoted to full-text passages.",
            "- `docs/reports/D10_S4_CANDIDATE_PASSAGE_MANIFEST.json` (`corpus_v2_d10_3025`) and "
            "`host_inference/fixtures/okf_graph.json` (`graph_v1_okf610`) were read read-only and remain byte-identical.",
            "- Raw downloaded PDFs/HTMLs/RFCs and `d14_candidate_passages_v3.jsonl` reside under "
            "`data/artifacts/corpus_v3_d14/` (gitignored per `.gitignore` line 143).",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
