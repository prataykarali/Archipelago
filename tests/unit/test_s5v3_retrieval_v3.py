"""Targeted unit tests for S5-v3 retrieval engineering improvements (Module D)."""

from __future__ import annotations

from dataclasses import replace
import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "research" / "s5-v3-benchmark-expansion" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from retrieval_v3 import (  # noqa: E402
    BM25LexicalControl,
    ConceptAnchorMatcher,
    CorpusPassage,
    GraphConcept,
    GraphEdge,
    RetrievalV3Config,
    RetrievalV3Engine,
    build_corpus_grounded_index,
    build_standard_v3_variants,
    normalize_technical_text,
    singularize_token,
)
from run_retrieval_v3_diagnostics import run_diagnostics  # noqa: E402


def _make_sample_corpus() -> list[CorpusPassage]:
    return [
        CorpusPassage(
            passage_id="doc_mml::p001",
            source_doc_id="local_oa_003",
            text="Singular value decomposition factorizes real matrices into orthogonal matrices.",
            page_start=110,
            page_end=110,
            provenance_class="pdf_extracted",
            source_sha256="aaa111",
        ),
        CorpusPassage(
            passage_id="doc_mml::p002",
            source_doc_id="local_oa_003",
            text="Eigenvalues and eigenvectors characterize linear transformations on vector spaces.",
            page_start=98,
            page_end=98,
            provenance_class="pdf_extracted",
            source_sha256="aaa111",
        ),
        CorpusPassage(
            passage_id="doc_mml::p003",
            source_doc_id="local_oa_003",
            text="Principal component analysis projects high dimensional data onto orthogonal axes.",
            page_start=318,
            page_end=318,
            provenance_class="pdf_extracted",
            source_sha256="aaa111",
        ),
        CorpusPassage(
            passage_id="doc_d2l::p001",
            source_doc_id="local_oa_001",
            text="Stochastic gradient descent updates linear regression weights using minibatch gradients.",
            page_start=1,
            page_end=1,
            provenance_class="markdown_oa_extracted",
            source_sha256="bbb222",
        ),
        CorpusPassage(
            passage_id="doc_misc::p001",
            source_doc_id="local_oa_002",
            text="A library catalog along a quiet street uses finite state machines for constrained decoding.",
            page_start=4,
            page_end=4,
            provenance_class="pdf_extracted",
            source_sha256="ccc333",
        ),
        CorpusPassage(
            passage_id="doc_misc::p002",
            source_doc_id="local_oa_004",
            text="Humanoid whole-body tracking policies stabilize locomotion under external disturbances.",
            page_start=2,
            page_end=2,
            provenance_class="pdf_extracted",
            source_sha256="ddd444",
        ),
    ]


def _make_sample_graph() -> tuple[dict[str, GraphConcept], list[GraphEdge]]:
    concepts = {
        "svd": GraphConcept(concept_id="svd", name="Singular Value Decomposition"),
        "eigenvalue": GraphConcept(concept_id="eigenvalue", name="Eigenvalue"),
        "pca": GraphConcept(concept_id="pca", name="Principal Component Analysis"),
        "sgd": GraphConcept(concept_id="sgd", name="Stochastic Gradient Descent"),
        "log": GraphConcept(concept_id="log", name="log"),
        "tree": GraphConcept(concept_id="tree", name="tree"),
        "ungrounded": GraphConcept(concept_id="ungrounded", name="Quantum Entanglement"),
    }
    edges = [
        GraphEdge(
            from_id="pca",
            from_name="Principal Component Analysis",
            to_id="svd",
            to_name="Singular Value Decomposition",
            edge_type="USES",
            raw_relation="uses",
            source="doc_mml:p318",
            confidence=0.9,
        ),
        GraphEdge(
            from_id="svd",
            from_name="Singular Value Decomposition",
            to_id="eigenvalue",
            to_name="Eigenvalue",
            edge_type="REQUIRES",
            raw_relation="requires",
            source="doc_mml:p110",
            confidence=0.85,
        ),
        # Deliberate cycle edge: eigenvalue -> pca
        GraphEdge(
            from_id="eigenvalue",
            from_name="Eigenvalue",
            to_id="pca",
            to_name="Principal Component Analysis",
            edge_type="ENABLES",
            raw_relation="enables",
            source="doc_mml:p098",
            confidence=0.8,
        ),
    ]
    return concepts, edges


@pytest.mark.unit
def test_imp1_boundary_aware_anchor_matching_prevents_substring_false_positives() -> None:
    """Improvement #1: 'log' must not match 'catalog' and 'tree' must not match 'street'."""
    concept_names = {"log": "log", "tree": "tree"}
    query = "library catalog along a quiet street with logarithm"

    boundary_matcher = ConceptAnchorMatcher(
        concept_names, use_boundary_matching=True, use_alias_normalization=True
    )
    assert boundary_matcher.match_text(query) == []

    # Exact standalone token still matches
    exact_matches = boundary_matcher.match_text("compute the log of a binary tree")
    assert [m.concept_id for m in exact_matches] == ["log", "tree"]

    # Ablation toggle: disabling boundary matching reproduces legacy substring false positives
    legacy_matcher = ConceptAnchorMatcher(
        concept_names, use_boundary_matching=False, use_alias_normalization=False
    )
    legacy_ids = [m.concept_id for m in legacy_matcher.match_text(query)]
    assert legacy_ids == ["log", "tree"]


@pytest.mark.unit
def test_imp2_concept_aliases_and_technical_term_normalization() -> None:
    """Improvement #2: Case/hyphen/plural normalization and curated acronym aliases."""
    assert singularize_token("matrices") == "matrix"
    assert singularize_token("eigenvalues") == "eigenvalue"
    assert singularize_token("loss") == "loss"
    assert (
        normalize_technical_text("Back-Propagation of Eigenvalues")
        == "back propagation of eigenvalue"
    )

    concept_names = {
        "svd": "Singular Value Decomposition",
        "eigenvalue": "Eigenvalue",
        "sgd": "Stochastic Gradient Descent",
    }
    norm_matcher = ConceptAnchorMatcher(
        concept_names, use_boundary_matching=True, use_alias_normalization=True
    )
    matches = norm_matcher.match_text("How does SVD relate to eigenvalues and SGD?")
    matched_ids = [m.concept_id for m in matches]
    assert matched_ids == ["eigenvalue", "sgd", "svd"]

    # Ablation toggle: disabling alias normalization misses acronyms & plurals
    raw_matcher = ConceptAnchorMatcher(
        concept_names, use_boundary_matching=True, use_alias_normalization=False
    )
    assert raw_matcher.match_text("How does SVD relate to eigenvalues and SGD?") == []


@pytest.mark.unit
def test_imp3_corpus_grounded_concept_to_passage_mapping_and_provenance() -> None:
    """Improvement #3: Deterministic concept->passage index with exact provenance."""
    passages = _make_sample_corpus()
    concepts, edges = _make_sample_graph()
    matcher = ConceptAnchorMatcher(
        {cid: c.name for cid, c in concepts.items()},
        use_boundary_matching=True,
        use_alias_normalization=True,
    )

    idx_a = build_corpus_grounded_index(
        passages, concepts, edges, matcher, use_corpus_grounded_mapping=True
    )
    idx_b = build_corpus_grounded_index(
        passages, concepts, edges, matcher, use_corpus_grounded_mapping=True
    )

    assert idx_a.index_sha256 == idx_b.index_sha256
    assert idx_a.concept_to_passages["svd"] == ("doc_mml::p001",)
    assert idx_a.concept_to_passages["eigenvalue"] == ("doc_mml::p002",)
    assert "log" not in idx_a.concept_to_passages
    assert "tree" not in idx_a.concept_to_passages
    assert any(
        link.concept_id == "svd" and link.passage_id == "doc_mml::p001" and link.page_start == 110
        for link in idx_a.links
    )

    # Ablation toggle: disabling corpus-grounded mapping yields empty concept->passage index
    idx_off = build_corpus_grounded_index(
        passages, concepts, edges, matcher, use_corpus_grounded_mapping=False
    )
    assert idx_off.concept_to_passages == {}
    assert idx_off.grounded_edge_count == 0


@pytest.mark.unit
def test_imp4_graph_edge_provenance_confidence_and_coverage_instrumentation() -> None:
    """Improvement #4: Edge provenance, confidence weighting, and per-query coverage metrics."""
    passages = _make_sample_corpus()
    concepts, edges = _make_sample_graph()
    cfg = RetrievalV3Config(
        variant_name="test_imp4",
        top_k=5,
        max_hops=2,
        use_edge_confidence_weighting=True,
    )
    engine = RetrievalV3Engine(cfg, passages, concepts, edges)
    summary = engine.graph_index.coverage_summary() if engine.graph_index else {}
    assert summary["grounded_graph_concepts"] >= 4
    assert summary["corpus_grounded_edges"] == 3
    assert summary["mean_edge_confidence"] > 0.0

    qr = engine.search_query("q1", "Explain PCA and its connection to SVD")
    assert "pca" in qr.provenance.matched_anchors
    assert "svd" in qr.provenance.matched_anchors
    assert qr.provenance.query_anchor_coverage_ratio > 0.0
    assert qr.provenance.mean_edge_confidence > 0.0
    assert sum(qr.provenance.edge_type_counts.values()) > 0


@pytest.mark.unit
def test_imp5_deterministic_zero_anchor_fallback_and_toggle() -> None:
    """Improvement #5: Deterministic BM25 fallback on zero anchors or zero grounded passages."""
    passages = _make_sample_corpus()
    concepts, edges = _make_sample_graph()

    cfg_on = RetrievalV3Config(
        variant_name="test_fb_on",
        top_k=3,
        enable_zero_anchor_fallback=True,
    )
    eng_on = RetrievalV3Engine(cfg_on, passages, concepts, edges)

    # Case A: Zero anchors matched
    qr_zero = eng_on.search_query("q_zero", "humanoid whole-body locomotion stabilization")
    assert qr_zero.provenance.fallback_triggered is True
    assert qr_zero.provenance.fallback_reason == "zero_anchors_matched"
    assert len(qr_zero.results) > 0
    assert all(r.source == "fallback" for r in qr_zero.results)

    # Case B: Anchor matched in graph, but 0 grounded passages in corpus
    qr_ungrounded = eng_on.search_query("q_ungrounded", "Quantum Entanglement locomotion")
    assert qr_ungrounded.provenance.fallback_triggered is True
    assert qr_ungrounded.provenance.fallback_reason == "zero_grounded_passages"
    assert all(r.source == "fallback" for r in qr_ungrounded.results)

    # Ablation toggle: fallback disabled returns empty results
    cfg_off = replace(cfg_on, variant_name="test_fb_off", enable_zero_anchor_fallback=False)
    eng_off = RetrievalV3Engine(cfg_off, passages, concepts, edges)
    qr_off = eng_off.search_query("q_zero", "humanoid whole-body locomotion stabilization")
    assert qr_off.provenance.fallback_triggered is False
    assert len(qr_off.results) == 0


@pytest.mark.unit
def test_imp6_partial_list_backfill_provenance_and_toggle() -> None:
    """Improvement #6: Partial-list backfill fills < Top-K with per-rank graph vs backfill tags."""
    passages = _make_sample_corpus()
    concepts, edges = _make_sample_graph()

    # Query matches SGD (only 1 graph passage, 0 outgoing edges) while top_k=4
    cfg_backfill = RetrievalV3Config(
        variant_name="test_bf_on",
        top_k=4,
        max_hops=1,
        enable_partial_backfill=True,
    )
    eng_bf = RetrievalV3Engine(cfg_backfill, passages, concepts, edges)
    qr_bf = eng_bf.search_query("q_sgd", "stochastic gradient descent linear regression matrices")

    assert qr_bf.provenance.short_list_before_backfill is True
    assert qr_bf.provenance.graph_result_count == 1
    assert qr_bf.provenance.backfill_count >= 1
    assert qr_bf.results[0].source == "graph"
    assert all(r.source == "backfill" for r in qr_bf.results[1:])
    # No duplicate passage IDs
    pids = [r.passage_id for r in qr_bf.results]
    assert len(pids) == len(set(pids))

    # Ablation toggle: backfill disabled leaves short list intact
    cfg_no_bf = replace(cfg_backfill, variant_name="test_bf_off", enable_partial_backfill=False)
    eng_no_bf = RetrievalV3Engine(cfg_no_bf, passages, concepts, edges)
    qr_no_bf = eng_no_bf.search_query(
        "q_sgd", "stochastic gradient descent linear regression matrices"
    )
    assert qr_no_bf.provenance.short_list_before_backfill is True
    assert qr_no_bf.provenance.backfill_count == 0
    assert len(qr_no_bf.results) == 1


@pytest.mark.unit
def test_imp7_controlled_multihop_traversal_decay_fanout_and_cycle_guard() -> None:
    """Improvement #7: Controlled 1-hop vs 2-hop decay, fanout cap, and cycle guard."""
    passages = _make_sample_corpus()
    concepts, edges = _make_sample_graph()

    # 1-hop from PCA reaches SVD only (not eigenvalue at hop 2)
    cfg_1h = RetrievalV3Config(
        variant_name="test_1h",
        top_k=5,
        max_hops=1,
        hop_decay=0.5,
        max_fanout_per_node=1,
        enforce_cycle_guard=True,
        enable_partial_backfill=False,
    )
    eng_1h = RetrievalV3Engine(cfg_1h, passages, concepts, edges)
    qr_1h = eng_1h.search_query("q_pca", "Principal Component Analysis")
    assert qr_1h.provenance.observed_hop_depth == 1
    assert {r.passage_id for r in qr_1h.results} == {"doc_mml::p003", "doc_mml::p001"}

    # 2-hop from PCA reaches SVD (hop 1) and Eigenvalue (hop 2), without looping back to PCA
    cfg_2h = replace(cfg_1h, variant_name="test_2h", max_hops=2)
    eng_2h = RetrievalV3Engine(cfg_2h, passages, concepts, edges)
    qr_2h = eng_2h.search_query("q_pca", "Principal Component Analysis")
    assert qr_2h.provenance.observed_hop_depth == 2
    assert {r.passage_id for r in qr_2h.results} == {
        "doc_mml::p003",
        "doc_mml::p001",
        "doc_mml::p002",
    }
    # Cycle guard ensures no hop-2 edge loops back to 'pca'
    assert all(
        not (step.hop == 2 and step.target_concept == "pca")
        for step in qr_2h.provenance.paths_traversed
    )
    # Decay ensures hop-0 passage scores higher than hop-1, which scores higher than hop-2
    scores_by_pid = {r.passage_id: r.score for r in qr_2h.results}
    assert (
        scores_by_pid["doc_mml::p003"]
        > scores_by_pid["doc_mml::p001"]
        > scores_by_pid["doc_mml::p002"]
    )


@pytest.mark.unit
def test_imp8_coverage_aware_retrieval_routing_and_ablation_toggle() -> None:
    """Improvement #8: Coverage-aware routing switches strictly on measured anchor coverage."""
    passages = _make_sample_corpus()
    concepts, edges = _make_sample_graph()

    cfg_routed = RetrievalV3Config(
        variant_name="test_routed",
        top_k=5,
        max_hops=2,
        enable_coverage_routing=True,
        min_coverage_for_graph=0.25,
        high_coverage_threshold=0.60,
    )
    eng = RetrievalV3Engine(cfg_routed, passages, concepts, edges)

    # High coverage query ("Principal Component Analysis") -> graph_heavy
    qr_high = eng.search_query("q_high", "Principal Component Analysis")
    assert qr_high.provenance.routing_decision == "graph_heavy"
    assert qr_high.provenance.graph_route_weight == cfg_routed.graph_heavy_weight
    assert all(r.source == "routed" for r in qr_high.results)

    # Low coverage query (1 anchor token among many unmatched tokens) -> lexical_only
    qr_low = eng.search_query(
        "q_low",
        "SVD in humanoid locomotion tracking policies under external disturbances with constrained decoding",
    )
    assert qr_low.provenance.routing_decision == "lexical_only"
    assert qr_low.provenance.graph_route_weight == 0.0
    assert qr_low.provenance.lexical_route_weight == 1.0


@pytest.mark.unit
def test_imp9_timing_and_memory_instrumentation() -> None:
    """Improvement #9: perf_counter_ns timing and tracemalloc peak memory telemetry."""
    passages = _make_sample_corpus()
    concepts, edges = _make_sample_graph()
    cfg = RetrievalV3Config(variant_name="test_telemetry", top_k=5, measure_memory=True)
    engine = RetrievalV3Engine(cfg, passages, concepts, edges)

    assert engine.index_build_telemetry.latency_ns > 0
    assert engine.index_build_telemetry.peak_memory_bytes > 0

    qr = engine.search_query("q_tel", "Explain PCA and SVD")
    assert qr.telemetry.latency_ns > 0
    assert qr.telemetry.latency_ms >= 0.0
    assert qr.telemetry.peak_memory_bytes > 0


@pytest.mark.unit
def test_config_hash_determinism_and_sensitivity() -> None:
    """Config SHA-256 is deterministic and sensitive to every ablation toggle."""
    variants = build_standard_v3_variants()
    hashes = [v.config_sha256() for v in variants]
    assert len(hashes) == len(set(hashes))

    cfg_a = variants[-1]
    cfg_b = replace(cfg_a)
    assert cfg_a.config_sha256() == cfg_b.config_sha256()

    cfg_c = replace(cfg_a, enable_coverage_routing=not cfg_a.enable_coverage_routing)
    assert cfg_a.config_sha256() != cfg_c.config_sha256()


@pytest.mark.unit
def test_diagnostics_cli_end_to_end_and_no_effectiveness_claims(tmp_path: Path) -> None:
    """CLI writes relevance-agnostic technical diagnostics with zero fabricated labels."""
    corpus_path = tmp_path / "corpus.jsonl"
    graph_path = tmp_path / "graph.json"
    queries_path = tmp_path / "queries.json"
    output_path = tmp_path / "diagnostics.json"

    passages = _make_sample_corpus()
    with corpus_path.open("w", encoding="utf-8") as handle:
        for p in passages:
            handle.write(
                json.dumps(
                    {
                        "passage_id": p.passage_id,
                        "source_doc_id": p.source_doc_id,
                        "text": p.text,
                        "page_start": p.page_start,
                        "page_end": p.page_end,
                        "provenance_class": p.provenance_class,
                        "source_sha256": p.source_sha256,
                    }
                )
                + "\n"
            )

    concepts, edges = _make_sample_graph()
    graph_payload = {
        "concepts": {
            cid: {"name": c.name, "concept_type": c.concept_type, "sources": list(c.sources)}
            for cid, c in concepts.items()
        },
        "edges": [
            {
                "from_id": e.from_id,
                "from_name": e.from_name,
                "to_id": e.to_id,
                "to_name": e.to_name,
                "edge_type": e.edge_type,
                "relation": e.raw_relation,
                "source": e.source,
                "confidence": e.confidence,
            }
            for e in edges
        ],
    }
    graph_path.write_text(json.dumps(graph_payload), encoding="utf-8")

    queries_payload = {
        "queries": [
            {"query_id": "q1", "query_text": "How does PCA use SVD and eigenvalues?"},
            {"query_id": "q2", "query_text": "Humanoid locomotion tracking policies"},
        ]
    }
    queries_path.write_text(json.dumps(queries_payload), encoding="utf-8")

    report = run_diagnostics(corpus_path, graph_path, queries_path, output_path, top_k=4)
    assert output_path.exists()
    assert report["effectiveness_evaluation"] == "NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS"
    assert report["frozen_v2_1_controls_modified"] is False
    assert len(report["variants"]) == 6
    assert report["inputs"]["query_count"] == 2
    assert report["inputs"]["corpus_passage_count"] == len(passages)

    # Ensure lexical control is deterministic
    lex = BM25LexicalControl(passages)
    assert lex.search("SVD matrices", top_k=3) == lex.search("SVD matrices", top_k=3)
