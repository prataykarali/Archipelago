"""Versioned research feature observations with explicit missing states."""

from __future__ import annotations

import math
import re
from typing import Any

from archipelago.scholarly.contracts.okf_models import FeatureObservation, PaperRecord, StatusEnum

FEATURE_VERSION = "2.0.0"
TOKEN_PATTERN = re.compile(r"\w+")
FEATURE_REGISTRY = (
    "title_query_similarity",
    "abstract_query_similarity",
    "fulltext_query_similarity",
    "BM25",
    "concept_coverage",
    "citation_count_snapshot",
    "log_citations",
    "citation_velocity",
    "age_normalized_citations",
    "field_normalized_citation_impact",
    "pagerank",
    "betweenness_centrality",
    "eigenvector_centrality",
    "bibliographic_coupling",
    "co_citation_strength",
    "embedding_novelty",
    "method_novelty",
    "dataset_count",
    "dataset_diversity",
    "baseline_count",
    "relative_improvement",
    "effect_size",
    "run_variance",
    "generalization_gap",
    "cross_dataset_eval",
    "ablation_coverage",
    "evidence_backed_claim_ratio",
    "evidence_coverage",
    "independent_support_count",
    "replication_count",
    "code_available",
    "data_available",
    "weights_available",
    "hyperparameter_completeness",
    "seed_count",
    "hardware_disclosure",
    "parameter_efficiency",
    "compute_efficiency",
    "memory_efficiency",
    "latency_efficiency",
    "retraction_status",
    "correction_status",
    "version_status",
)


def _tokens(value: str) -> set[str]:
    return set(TOKEN_PATTERN.findall(value.casefold()))


def _coverage(query: str, body: str) -> float | None:
    wanted = _tokens(query)
    if not wanted or not body.strip():
        return None
    return len(wanted & _tokens(body)) / len(wanted)


class FeatureEngine:
    """Compute only supported observations; mark other registry features missing."""

    def compute_features(
        self,
        paper: PaperRecord,
        query: str,
        extraction_data: dict[str, Any],
        citation_count: int | None = None,
    ) -> list[FeatureObservation]:
        """Return the typed registry without manufactured values."""
        values: dict[str, FeatureObservation] = {}

        def record(
            name: str,
            value: Any,
            status: StatusEnum,
            formula: str | None = None,
            inputs: dict[str, Any] | None = None,
        ) -> None:
            values[name] = FeatureObservation(
                feature_name=name,
                value=value,
                status=status,
                extractor_version=FEATURE_VERSION,
                derivation_json={
                    "formula_version": FEATURE_VERSION,
                    "formula": formula,
                    "inputs": inputs,
                }
                if formula
                else None,
            )

        for name, field in (
            ("title_query_similarity", paper.title),
            ("abstract_query_similarity", paper.abstract or ""),
        ):
            score = _coverage(query, field)
            record(
                name,
                round(score, 4) if score is not None else None,
                StatusEnum.DERIVED if score is not None else StatusEnum.NOT_REPORTED,
                "query_token_coverage_v1" if score is not None else None,
                {"query": query, "field": field} if score is not None else None,
            )

        concepts = extraction_data.get("query_concepts")
        if isinstance(concepts, list) and concepts:
            body_tokens = _tokens(f"{paper.title} {paper.abstract or ''}")
            covered = sum(bool(_tokens(str(concept)) & body_tokens) for concept in concepts)
            record(
                "concept_coverage",
                covered / len(concepts),
                StatusEnum.DERIVED,
                "covered_concepts / query_concepts",
                {"covered": covered, "total": len(concepts)},
            )

        if citation_count is not None and citation_count >= 0:
            record("citation_count_snapshot", citation_count, StatusEnum.OBSERVED)
            record(
                "log_citations",
                round(math.log1p(citation_count), 4),
                StatusEnum.DERIVED,
                "ln(1 + citation_count)",
                {"citation_count": citation_count},
            )

        datasets = extraction_data.get("datasets")
        if isinstance(datasets, list):
            record("dataset_count", len(datasets), StatusEnum.OBSERVED)
            distinct = {getattr(dataset, "name", None) for dataset in datasets}
            record(
                "dataset_diversity",
                len(distinct - {None}),
                StatusEnum.DERIVED,
                "distinct_dataset_names",
                {"dataset_names": sorted(str(x) for x in distinct if x)},
            )

        claims = extraction_data.get("claims")
        if (
            extraction_data.get("verification_state") == "validated"
            and isinstance(claims, list)
            and claims
        ):
            backed = sum(bool(getattr(claim, "provenance_ids", [])) for claim in claims)
            record(
                "evidence_backed_claim_ratio",
                backed / len(claims),
                StatusEnum.DERIVED,
                "backed_claims / total_claims",
                {"backed": backed, "total": len(claims)},
            )

        code_url = extraction_data.get("code_url")
        if code_url:
            record("code_available", True, StatusEnum.OBSERVED)
        elif extraction_data.get("code_absence_verified") is True:
            record("code_available", False, StatusEnum.OBSERVED)

        for name in ("retraction_status", "correction_status"):
            value = getattr(paper, name)
            if value and value != "unknown":
                record(name, value, StatusEnum.OBSERVED)
        if paper.publication_status and paper.publication_status != "unknown":
            record("version_status", paper.publication_status, StatusEnum.OBSERVED)

        return [
            values.get(name)
            or FeatureObservation(
                feature_name=name,
                value=None,
                status=StatusEnum.UNKNOWN,
                extractor_version=FEATURE_VERSION,
                comparability_status="insufficient_evidence",
            )
            for name in FEATURE_REGISTRY
        ]
