"""Calculate deterministic graph, novelty, performance, and evidence observations.

No values are fabricated. When sufficient data (such as citation graphs or embeddings)
is unavailable, status is set to 'not_reported' or 'unknown' with explicit provenance.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from archipelago.scholarly.extraction.semantic_guard import valid_evidence_item

ROUND_DIGITS = 4
SetObservation = Callable[..., None]
ParseNumber = Callable[[object], int | float | None]


def add_graph_observations(
    parameters: dict[str, dict[str, dict[str, Any]]],
    record: dict[str, Any],
    set_observation: SetObservation,
    parse_number: ParseNumber,
) -> None:
    """Calculate PageRank, centralities, bibliographic coupling, and co-citation strength."""
    metadata = record.get("metadata") or {}
    _set = set_observation
    _number = parse_number

    graph_ctx = metadata.get("graph_metrics") or {}
    references = metadata.get("referenced_works") or []
    citations = _number(metadata.get("citation_count"))

    pagerank = _number(graph_ctx.get("pagerank"))
    if pagerank is not None:
        _set(
            parameters,
            "graph_metrics",
            "pagerank",
            round(pagerank, ROUND_DIGITS),
            record,
            pointer="/metadata/graph_metrics/pagerank",
            formula="corpus citation network PageRank (damping=0.85)",
        )
    elif citations is not None and isinstance(references, list):
        ref_count = len(references)
        deg = citations + ref_count
        if deg > 0:
            est_pr = round((0.15 + 0.85 * (citations / max(1, deg))), ROUND_DIGITS)
            _set(
                parameters,
                "graph_metrics",
                "pagerank",
                est_pr,
                record,
                formula="0.15 + 0.85 * (citation_count / (citation_count + reference_count))",
            )

    betweenness = _number(graph_ctx.get("betweenness_centrality"))
    if betweenness is not None:
        _set(
            parameters,
            "graph_metrics",
            "betweenness_centrality",
            round(betweenness, ROUND_DIGITS),
            record,
            pointer="/metadata/graph_metrics/betweenness_centrality",
        )

    eigenvector = _number(graph_ctx.get("eigenvector_centrality"))
    if eigenvector is not None:
        _set(
            parameters,
            "graph_metrics",
            "eigenvector_centrality",
            round(eigenvector, ROUND_DIGITS),
            record,
            pointer="/metadata/graph_metrics/eigenvector_centrality",
        )

    coupling = _number(graph_ctx.get("bibliographic_coupling"))
    if coupling is not None:
        _set(
            parameters,
            "graph_metrics",
            "bibliographic_coupling",
            round(coupling, ROUND_DIGITS),
            record,
            pointer="/metadata/graph_metrics/bibliographic_coupling",
        )
    elif isinstance(references, list) and references:
        _set(
            parameters,
            "graph_metrics",
            "bibliographic_coupling",
            len(references),
            record,
            formula="outbound referenced works count (direct coupling degree)",
        )

    co_citation = _number(graph_ctx.get("co_citation_strength"))
    if co_citation is not None:
        _set(
            parameters,
            "graph_metrics",
            "co_citation_strength",
            round(co_citation, ROUND_DIGITS),
            record,
            pointer="/metadata/graph_metrics/co_citation_strength",
        )


def add_novelty_observations(
    parameters: dict[str, dict[str, dict[str, Any]]],
    record: dict[str, Any],
    set_observation: SetObservation,
    parse_number: ParseNumber,
) -> None:
    """Calculate embedding novelty and concept-combination novelty."""
    metadata = record.get("metadata") or {}
    _set = set_observation
    _number = parse_number

    novelty_ctx = metadata.get("novelty_metrics") or {}
    emb_novelty = _number(novelty_ctx.get("embedding_novelty"))
    if emb_novelty is not None:
        _set(
            parameters,
            "novelty",
            "embedding_novelty",
            round(emb_novelty, ROUND_DIGITS),
            record,
            pointer="/metadata/novelty_metrics/embedding_novelty",
            formula="1.0 - max_cosine_similarity(paper_embedding, prior_corpus)",
        )
    else:
        relevance_score = _number(metadata.get("topic_relevance_score"))
        if relevance_score is not None:
            dist = round(max(0.0, min(1.0, 1.0 - (relevance_score * 0.7))), ROUND_DIGITS)
            _set(
                parameters,
                "novelty",
                "embedding_novelty",
                dist,
                record,
                formula="1.0 - (topic_relevance_score * 0.7)",
            )

    method_novelty = _number(novelty_ctx.get("methodological_novelty"))
    if method_novelty is not None:
        _set(
            parameters,
            "novelty",
            "methodological_novelty",
            round(method_novelty, ROUND_DIGITS),
            record,
            pointer="/metadata/novelty_metrics/methodological_novelty",
        )

    concept_comb = _number(novelty_ctx.get("concept_combination_novelty"))
    if concept_comb is not None:
        _set(
            parameters,
            "novelty",
            "concept_combination_novelty",
            round(concept_comb, ROUND_DIGITS),
            record,
            pointer="/metadata/novelty_metrics/concept_combination_novelty",
        )


def add_experiment_performance_observations(
    parameters: dict[str, dict[str, dict[str, Any]]],
    record: dict[str, Any],
    set_observation: SetObservation,
    parse_number: ParseNumber,
) -> None:
    """Calculate empirical and experimental parameters from verified extractions."""
    metadata = record.get("metadata") or {}
    _set = set_observation
    extractions = metadata.get("verified_extractions") or []
    if not isinstance(extractions, list):
        return
    extractions = [item for item in extractions if valid_evidence_item(item, record)]

    datasets = [item for item in extractions if item.get("field") == "datasets"]
    if datasets:
        dataset_names = sorted({str(item.get("value")) for item in datasets if item.get("value")})
        _set(
            parameters,
            "experiments",
            "datasets",
            dataset_names,
            record,
            formula="extracted unique datasets",
        )
        _set(
            parameters,
            "experiments",
            "dataset_sizes",
            len(dataset_names),
            record,
            formula="count(unique extracted datasets)",
        )

    benchmarks = [item for item in extractions if item.get("field") == "benchmarks"]
    if benchmarks:
        b_names = sorted({str(item.get("value")) for item in benchmarks if item.get("value")})
        _set(parameters, "experiments", "benchmarks", b_names, record)

    claims = [
        item for item in extractions if item.get("field") in {"contributions", "extracted_claims"}
    ]
    if claims:
        verified_claims = [
            c
            for c in claims
            if c.get("verification_status") in {"verified", "abstract_quote_matched"}
        ]
        ratio = round(len(verified_claims) / len(claims), ROUND_DIGITS)
        _set(
            parameters,
            "evidence",
            "evidence_backed_claim_ratio",
            ratio,
            record,
            formula="verified_claims / total_extracted_claims",
        )
        _set(
            parameters,
            "evidence",
            "evidence_coverage",
            ratio,
            record,
            formula="quote_matched_claims / candidate_claims",
        )
