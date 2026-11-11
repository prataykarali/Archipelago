"""Expand legacy paper observations into the complete research OKF contract."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .research_evidence_guard import valid_evidence_item

CONTRACT_VERSION = "3.0.0"
FIELDS = {
    "identity": "paper_id title subtitle doi arxiv_id openalex_id semantic_scholar_id pmid pmcid abstract keywords topics field_of_study subfields publication_date preprint_date revision_date publication_type journal conference venue_id publisher issn eissn volume issue pages language open_access_status license pdf_url landing_page_url",
    "authors": "author_id author_name orcid author_position corresponding_author affiliations institution_id institution_name country author_count institution_count collaboration_count international_collaboration",
    "author_bibliometrics": "h_index g_index i10_index i20_index i100_index m_index e_index total_citations total_publications career_start_year academic_age average_citations_per_paper citation_velocity highly_cited_paper_count named_i_indices",
    "venue_metrics": "venue_name venue_type publisher issn journal_h_index journal_h5_index journal_h5_median impact_factor five_year_impact_factor CiteScore SJR SNIP quartile indexing_status",
    "citation_metrics": "citation_count reference_count influential_citation_count influential_citation_ratio citation_count_by_year recent_citations_12m recent_citations_24m log_citation_count citation_velocity citation_acceleration citations_per_year age_normalized_citations field_normalized_citation_impact citation_percentile citation_half_life self_citation_count self_citation_ratio citation_intents citation_contexts",
    "semantic_relevance": "title_similarity abstract_similarity method_similarity experiment_similarity conclusion_similarity fulltext_similarity max_section_similarity mean_top_k_section_similarity BM25 TF_IDF_similarity keyword_overlap concept_coverage entity_overlap jaccard_similarity topic_confidence query_intent_match",
    "graph_metrics": "pagerank eigenvector_centrality betweenness_centrality closeness_centrality degree_centrality in_degree out_degree HITS_authority HITS_hub bibliographic_coupling co_citation_strength community_id community_centrality cross_community_bridge_score reference_diversity citation_diversity graph_neighborhood_density",
    "novelty_metrics": "embedding_novelty method_novelty concept_novelty concept_combination_novelty reference_novelty dataset_novelty cross_domain_novelty method_adoption_count dataset_adoption_count implementation_adoption SOTA_persistence research_lineage_depth",
    "methodology": "research_problem research_questions hypotheses contributions method_family algorithms model_architecture model_parameters training_regime loss_functions optimization_methods hyperparameters input_modalities preprocessing assumptions mathematical_formulations implementation_details",
    "datasets": "dataset_names dataset_ids dataset_versions dataset_count dataset_size training_samples validation_samples test_samples sample_size dataset_diversity dataset_languages dataset_domains benchmark_names benchmark_coverage baseline_names baseline_count evaluation_protocol statistical_tests random_seed_count experimental_repetitions external_validation cross_dataset_evaluation ablation_present error_analysis_present",
    "experiments": "dataset split evaluation_protocol baseline measurement_unit metric_direction statistical_tests random_seed_count experimental_repetitions external_validation cross_dataset_evaluation ablation_present error_analysis_present",
    "performance": "metric_name metric_value metric_unit metric_direction baseline_value proposed_value absolute_improvement relative_improvement effect_size p_value confidence_interval confidence_interval_width statistical_power standard_deviation variance_across_runs coefficient_of_variation generalization_gap train_test_gap OOD_performance robustness_measurements ablation_effect_size result_consistency benchmark_saturation",
    "efficiency": "parameter_count model_size_MB FLOPs training_compute training_time inference_latency throughput peak_RAM peak_VRAM energy_consumption hardware_type GPU_count parameter_efficiency compute_efficiency memory_efficiency latency_efficiency energy_efficiency",
    "claims": "claim_id claim_text claim_type claim_count supporting_evidence evidence_span evidence_coverage evidence_backed_claim_ratio independent_support_count replication_count replication_success_rate contradiction_count verification_status claim_confidence limitations failure_modes error_analysis open_problems future_work",
    "evidence": "claim_id claim_text supporting_evidence evidence_span page_number section table_id figure_id verification_status",
    "reproducibility": "code_available code_url dataset_available dataset_url weights_available weights_url license software_dependencies hyperparameter_completeness seed_reported hardware_reported artifact_completeness reproducibility_status external_replication_evidence",
    "relations": "CITES CITED_BY EXTENDS USES USES_DATASET EVALUATED_ON COMPARES_AGAINST INTRODUCES SUPPORTS CONTRADICTS REPLICATES VARIANT_OF PART_OF RELATED_TO",
    "integrity": "retraction_status correction_status expression_of_concern version_status revision_count textual_revision_magnitude duplicate_of publication_history data_leakage_risk source_integrity_status",
    "provenance": "source_api source_record_id source_snapshot_time paper_id pdf_sha256 page_number section table_id figure_id evidence_text extraction_method extractor_version formula_name formula_version formula_inputs confidence verification_status computed_at",
}
ALIASES = {
    ("identity", "publication_type"): ("paper_identity", "paper_type"),
    ("identity", "journal"): ("paper_identity", "journal_or_conference"),
    ("authors", "orcid"): ("paper_identity", "orcid"),
    ("author_bibliometrics", "total_publications"): ("author_metrics", "publication_count"),
    ("author_bibliometrics", "academic_age"): ("author_metrics", "academic_career_age"),
    ("author_bibliometrics", "average_citations_per_paper"): (
        "author_metrics",
        "average_citations_per_publication",
    ),
    ("citation_metrics", "influential_citation_count"): (
        "citation_metrics",
        "influential_citations",
    ),
    ("semantic_relevance", "method_similarity"): ("relevance", "methodology_similarity"),
    ("semantic_relevance", "fulltext_similarity"): ("relevance", "full_text_similarity"),
    ("semantic_relevance", "BM25"): ("relevance", "bm25"),
    ("semantic_relevance", "topic_confidence"): ("relevance", "topic_relevance_confidence"),
    ("novelty_metrics", "method_novelty"): ("novelty", "methodological_novelty"),
    ("datasets", "dataset_names"): ("experiments", "datasets"),
    ("datasets", "benchmark_names"): ("experiments", "benchmarks"),
    ("datasets", "baseline_names"): ("experiments", "baseline_models"),
    ("datasets", "sample_size"): ("experiments", "sample_sizes"),
    ("datasets", "ablation_present"): ("experiments", "ablation_studies"),
    ("claims", "claim_text"): ("evidence", "extracted_claims"),
    ("claims", "independent_support_count"): ("evidence", "independent_support"),
    ("efficiency", "FLOPs"): ("efficiency", "flops"),
    ("efficiency", "parameter_count"): ("efficiency", "model_parameters"),
    ("reproducibility", "code_available"): ("reproducibility", "code_availability"),
    ("reproducibility", "dataset_available"): ("reproducibility", "dataset_availability"),
    ("relations", "CITES"): ("research_relationships", "cites"),
}
SOURCE_FIELDS = {
    ("identity", "paper_id"): "record_key",
    ("identity", "landing_page_url"): "source_url",
    ("identity", "topics"): "metadata.topics",
    ("identity", "license"): "metadata.license",
    ("authors", "author_name"): "metadata.authors",
    ("authors", "affiliations"): "metadata.institutions",
    ("citation_metrics", "citation_count_by_year"): "metadata.counts_by_year",
    ("provenance", "pdf_sha256"): "metadata.pdf_sha256",
    ("provenance", "source_api"): "source_name",
    ("author_bibliometrics", "named_i_indices"): "metadata.named_i_indices",
}
FORMULA_SOURCES = {
    "citation_velocity": ("metadata.counts_by_year",),
    "citation_acceleration": ("metadata.counts_by_year",),
    "citations_per_year": ("metadata.citation_count", "published_at"),
    "age_normalized_citations": ("metadata.citation_count", "published_at"),
    "dataset_count": ("metadata.verified_extractions",),
    "author_count": ("metadata.authors",),
    "institution_count": ("metadata.institutions",),
}


def _source_value(record: dict[str, Any], path: str) -> Any:
    value: Any = record
    for key in path.split("."):
        value = value.get(key) if isinstance(value, dict) else None
    return value


def _reported_value(value: Any) -> Any:
    """Discard source placeholders without discarding legitimate zero values."""
    if isinstance(value, str) and value.strip().casefold() in {
        "unknown",
        "not reported",
        "not available",
        "n/a",
        "null",
        "none",
        "",
    }:
        return None
    if isinstance(value, (list, dict)) and not value:
        return None
    return value


def _verified_extraction(record: dict[str, Any], group: str, name: str) -> dict[str, Any] | None:
    """Accept a new-contract field only when its quote matches the stored source."""
    metadata = record.get("metadata") or {}
    for item in metadata.get("verified_extractions") or []:
        if not isinstance(item, dict) or item.get("group") != group or item.get("field") != name:
            continue
        value, quote = item.get("value"), item.get("evidence_text")
        if not isinstance(value, str) or not value.strip() or not isinstance(quote, str):
            continue
        if valid_evidence_item(item, record):
            return item
    return None


def expand_contract(okf: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    """Emit every field with explicit status and provenance; preserve legacy parameters."""
    parameters = okf["parameters"]
    now = datetime.now(UTC).isoformat()
    feature_observations: list[dict[str, Any]] = []
    for group, names in FIELDS.items():
        observations: dict[str, dict[str, Any]] = {}
        for name in names.split():
            legacy_group, legacy_name = ALIASES.get((group, name), (group, name))
            legacy = parameters.get(legacy_group, {}).get(legacy_name, {})
            value = _reported_value(legacy.get("value"))
            extracted = _verified_extraction(record, group, name)
            if extracted is not None:
                value = extracted["value"]
            from_source = False
            if value is None and (group, name) in SOURCE_FIELDS:
                value = _reported_value(_source_value(record, SOURCE_FIELDS[(group, name)]))
                from_source = value is not None
            if value is None and group in {
                "identity",
                "authors",
                "citation_metrics",
                "methodology",
                "datasets",
                "experiments",
                "reproducibility",
                "integrity",
                "provenance",
            }:
                metadata = record.get("metadata") or {}
                value = _reported_value(metadata.get(name))
                if value is None:
                    value = _reported_value((metadata.get("source_metadata") or {}).get(name))
                from_source = value is not None
            if group == "authors" and name == "author_count":
                authors = (record.get("metadata") or {}).get("authors")
                value = len(authors) if isinstance(authors, list) and authors else None
            if group == "authors" and name == "institution_count":
                institutions = (record.get("metadata") or {}).get("institutions")
                value = (
                    len(set(institutions))
                    if isinstance(institutions, list) and institutions
                    else None
                )
            status = (
                "inferred"
                if extracted is not None
                else "derived"
                if group == "authors"
                and name in {"author_count", "institution_count"}
                and value is not None
                else "observed"
                if from_source
                else legacy.get("status", "unknown" if value is None else "observed")
            )
            if value is None and status != "not_applicable":
                status = "unknown"
            pointer = (legacy.get("provenance") or [{}])[0]
            formula_inputs = (
                {path: _source_value(record, path) for path in FORMULA_SOURCES.get(name, ())}
                if status == "derived"
                else None
            )
            if status == "derived" and not formula_inputs:
                formula_inputs = {"source_pointer": pointer.get("json_pointer")}
            feature = {
                "feature_name": name,
                "value": value,
                "unit": (extracted or {}).get("unit"),
                "entity_scope": "first_author"
                if group == "author_bibliometrics"
                else "venue"
                if group == "venue_metrics"
                else "paper",
                "ranking_use": "analytics_only"
                if group in {"authors", "author_bibliometrics"}
                else "candidate_feature",
                "status": status,
                "source_api": (extracted or {}).get("source_api")
                or pointer.get("source_api")
                or record.get("source_name"),
                "source_record_id": record.get("record_key"),
                "source_snapshot_time": (extracted or {}).get("source_timestamp")
                or pointer.get("source_timestamp")
                or (record.get("metadata") or {}).get("source_timestamp"),
                "paper_id": record.get("record_key"),
                "pdf_sha256": (record.get("metadata") or {}).get("pdf_sha256"),
                "page_number": (extracted or {}).get("pdf_page") or pointer.get("pdf_page"),
                "section": (extracted or {}).get("section") or pointer.get("section"),
                "table_id": (extracted or {}).get("table_id") or pointer.get("table"),
                "figure_id": (extracted or {}).get("figure_id") or pointer.get("figure"),
                "evidence_text": (extracted or {}).get("evidence_text")
                or pointer.get("evidence_text"),
                "extraction_method": "slm_quote_match"
                if extracted is not None
                else "deterministic"
                if status == "derived"
                else pointer.get("verification_status"),
                "extractor_version": (extracted or {}).get("extractor_version")
                or legacy.get("extractor_version"),
                "formula_name": pointer.get("formula")
                or (
                    "count(authors)"
                    if group == "authors" and name == "author_count"
                    else "count(unique institutions)"
                    if group == "authors" and name == "institution_count"
                    else None
                ),
                "formula_version": "1.0.0" if status == "derived" else None,
                "formula_inputs": formula_inputs,
                "confidence": (extracted or {}).get("extraction_confidence")
                or legacy.get("confidence"),
                "verification_status": (extracted or {}).get("verification_status")
                or (
                    "computed"
                    if status == "derived"
                    else pointer.get("verification_status") or "not_available"
                ),
                "computed_at": now,
            }
            observations[name] = feature
            feature_observations.append(feature)
        okf[group] = observations
    okf["contract_version"] = CONTRACT_VERSION
    okf["raw_metadata"] = record.get("metadata") or {}
    okf["extracted_evidence"] = (record.get("metadata") or {}).get("verified_extractions") or []
    okf["feature_observations"] = feature_observations
    return okf
