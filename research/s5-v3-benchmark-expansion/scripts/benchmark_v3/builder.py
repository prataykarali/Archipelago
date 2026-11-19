"""Builder that grounds proposed S5-v3 query drafts against Corpus v3."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .constants import (
    ANSWERABILITY_STATUS_UNVERIFIED,
    DEFERRED_CS_DOMAINS,
    DEFERRED_DOMAIN_STATUS,
    PROVENANCE_STATUS_PROPOSED,
    SCHEMA_VERSION,
)
from .corpus_index import compute_file_sha256, load_corpus_metadata
from .graph_anchors import GraphAnchorIndex
from .leakage import load_v21_queries
from .schema import (
    CorpusPassageMeta,
    EvidenceRef,
    QuerySpec,
    ShortcutCheck,
    ValidationReport,
)
from .validator import validate_benchmark


@dataclass(frozen=True)
class QueryDraft:
    """Authoring draft before programmatic grounding against Corpus v3."""

    query_id: str
    query_text: str
    split: str
    category: str
    domain_topic: str
    exact_information_need: str
    evidence_passage_ids: tuple[str, ...]
    minimum_required_evidence_ids: tuple[str, ...]
    answer_exists_in_eligible_corpus: bool
    multi_document_truly_necessary: bool
    shortcut_found: bool
    shortcut_rationale: str
    premise_audit_flags: tuple[str, ...] = ()


def ground_query_draft(
    draft: QueryDraft,
    corpus_index: dict[str, CorpusPassageMeta],
    graph_index: GraphAnchorIndex,
) -> QuerySpec:
    """Resolve evidence refs from Corpus v3 and compute graph-anchor regime."""
    evidence_refs: list[EvidenceRef] = []
    for pid in draft.evidence_passage_ids:
        meta = corpus_index.get(pid)
        if meta is None:
            msg = (
                f"Query {draft.query_id} references unknown passage_id "
                f"'{pid}' not present in Corpus v3."
            )
            raise KeyError(msg)
        evidence_refs.append(
            EvidenceRef(
                passage_id=meta.passage_id,
                source_doc_id=meta.source_doc_id,
                page_start=meta.page_start,
                page_end=meta.page_end,
                passage_sha256=meta.passage_sha256,
            )
        )

    regime, matched_concepts = graph_index.classify_regime(draft.query_text)
    return QuerySpec(
        query_id=draft.query_id,
        query_text=draft.query_text,
        split=draft.split,
        category=draft.category,
        domain_topic=draft.domain_topic,
        graph_anchor_regime=regime,
        graph_matched_concepts=matched_concepts,
        exact_information_need=draft.exact_information_need,
        supporting_evidence=tuple(evidence_refs),
        answer_exists_in_eligible_corpus=draft.answer_exists_in_eligible_corpus,
        answerability_verification_status=ANSWERABILITY_STATUS_UNVERIFIED,
        minimum_required_evidence_set=draft.minimum_required_evidence_ids,
        multi_document_truly_necessary=draft.multi_document_truly_necessary,
        single_passage_shortcut_check=ShortcutCheck(
            shortcut_found=draft.shortcut_found,
            rationale=draft.shortcut_rationale,
        ),
        premise_audit_flags=draft.premise_audit_flags,
        provenance_status=PROVENANCE_STATUS_PROPOSED,
    )


def build_benchmark_manifest(
    drafts: list[QueryDraft],
    corpus_jsonl_path: Path,
    graph_json_path: Path,
    v21_specs_path: Path | None = None,
    enforce_size_bounds: bool = True,
) -> tuple[dict[str, Any], ValidationReport]:
    """Ground drafts, validate all invariants, and build public manifest."""
    corpus_index = load_corpus_metadata(corpus_jsonl_path)
    graph_index = GraphAnchorIndex.from_json_path(graph_json_path)
    v21_queries = (
        load_v21_queries(v21_specs_path)
        if v21_specs_path is not None
        else []
    )

    grounded = [
        ground_query_draft(draft, corpus_index, graph_index)
        for draft in drafts
    ]
    report = validate_benchmark(
        queries=grounded,
        corpus_index=corpus_index,
        graph_index=graph_index,
        v21_queries=v21_queries,
        enforce_size_bounds=enforce_size_bounds,
    )

    doc_counter: Counter[str] = Counter()
    for q in grounded:
        for doc_id in {ref.source_doc_id for ref in q.supporting_evidence}:
            doc_counter[doc_id] += 1

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "provenance_status": PROVENANCE_STATUS_PROPOSED,
        "answerability_verification_status": ANSWERABILITY_STATUS_UNVERIFIED,
        "human_verification_notice": (
            "Candidate generation is NOT human validation. Every query in this "
            "manifest is an AI-proposed candidate requiring independent human "
            "verification of answerability, passage grounding, and multi-passage "
            "necessity before entering any evaluated S5-v3 benchmark."
        ),
        "corpus_v3_jsonl_sha256": compute_file_sha256(corpus_jsonl_path),
        "corpus_v3_passage_count": len(corpus_index),
        "graph_json_path": str(graph_json_path.name),
        "graph_json_sha256": compute_file_sha256(graph_json_path),
        "graph_concept_count": graph_index.concept_count,
        "deferred_domains": dict.fromkeys(DEFERRED_CS_DOMAINS, DEFERRED_DOMAIN_STATUS),
        "summary": {
            "total_queries": report.total_queries,
            "split_counts": report.split_counts,
            "category_counts": report.category_counts,
            "graph_anchor_regime_counts": report.regime_counts,
            "multi_document_necessary_count": sum(
                1 for q in grounded if q.multi_document_truly_necessary
            ),
            "source_doc_query_coverage": dict(sorted(doc_counter.items())),
            "validation_error_count": report.error_count,
        },
        "queries": [q.to_dict() for q in grounded],
    }
    return manifest, report


def write_manifest(manifest: dict[str, Any], output_path: Path) -> None:
    """Write deterministic formatted JSON manifest to disk."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
