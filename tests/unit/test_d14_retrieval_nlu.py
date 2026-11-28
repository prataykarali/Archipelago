"""Unit tests for Phase D14.3 Retrieval, NLU, Dense/Hybrid Scoring, and Versioned Loaders."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "host_inference") not in sys.path:
    sys.path.append(str(REPO_ROOT / "host_inference"))

from engine.evidence_selection import (  # noqa: E402
    DOMAIN_DB,
    DOMAIN_MATH,
    DOMAIN_ML_AI,
    DOMAIN_NETWORKS,
    DOMAIN_OS,
    DOMAIN_PROB_STATS,
    DOMAIN_SECURITY,
    domains_compatible,
    infer_doc_domains,
    select_catalog_passages,
)
from engine.graph import LibraryGraph, resolve_runtime_graph_path  # noqa: E402
from engine.graph_semantics import (  # noqa: E402
    ENV_GRAPH_PATH,
    ENV_GRAPH_VERSION,
    GRAPH_V1_FILENAME,
    GRAPH_V1_ID,
    GRAPH_V2_FILENAME,
    GRAPH_V2_ID,
)
from engine.route_logic import route  # noqa: E402
from library_index import (  # noqa: E402
    CORPUS_V2_ID,
    CORPUS_V3_ID,
    ENV_CORPUS_VERSION,
    Catalog,
    resolve_candidate_passages_path,
)

from archipelago.inference.dense_retriever import (  # noqa: E402
    METHOD_BM25_LEXICAL,
    METHOD_DENSE_NEURAL,
    METHOD_HYBRID_BM25_DENSE,
    DensePassageEncoder,
    HybridPassageRetriever,
)

FIXTURES_DIR = REPO_ROOT / "host_inference" / "fixtures"
V1_GRAPH_PATH = FIXTURES_DIR / GRAPH_V1_FILENAME
V2_GRAPH_PATH = FIXTURES_DIR / GRAPH_V2_FILENAME


@pytest.fixture(scope="module")
def graph_v2() -> LibraryGraph:
    """Load graph_v2_d14 once for specificity and alias tests."""
    return LibraryGraph(V2_GRAPH_PATH, allow_env_override=False)


# ── Goal 1: Versioned Runtime Loaders + Rollback ──────────────────────────────


@pytest.mark.unit
def test_runtime_graph_loader_defaults_to_v2_and_rolls_back_to_v1(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """load_default() prefers graph_v2_d14 and cleanly rolls back to v1 via env."""
    monkeypatch.delenv(ENV_GRAPH_PATH, raising=False)
    monkeypatch.delenv(ENV_GRAPH_VERSION, raising=False)

    chosen_default = resolve_runtime_graph_path(FIXTURES_DIR)
    assert chosen_default.name == GRAPH_V2_FILENAME
    g_v2 = LibraryGraph.load_default(V1_GRAPH_PATH)
    assert g_v2.graph_artifact_version == GRAPH_V2_ID
    assert "singular_value_decomposition" in g_v2.nodes

    monkeypatch.setenv(ENV_GRAPH_VERSION, GRAPH_V1_ID)
    chosen_rollback = resolve_runtime_graph_path(FIXTURES_DIR)
    assert chosen_rollback.name == GRAPH_V1_FILENAME
    g_v1 = LibraryGraph.load_default(V1_GRAPH_PATH)
    assert g_v1.graph_artifact_version == GRAPH_V1_ID
    assert len(g_v1.nodes) == 610


@pytest.mark.unit
def test_corpus_version_selection_and_v3_metadata_preservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Catalog loader selects v3 by default, supports v2 rollback, and preserves v3 fields."""
    fake_here = tmp_path / "host_inference"
    v3_dir = tmp_path / "data" / "artifacts" / "corpus_v3_d14"
    v2_dir = fake_here / "cache"
    v3_dir.mkdir(parents=True)
    v2_dir.mkdir(parents=True)

    v3_file = v3_dir / "d14_candidate_passages_v3.jsonl"
    v2_file = v2_dir / "d10_candidate_passages.jsonl"
    v3_rec = {
        "corpus_version": CORPUS_V3_ID,
        "passage_id": "d14:abc:p4:c0",
        "doc_id": "d14_oa/ostep/08_paging.pdf",
        "source_title": "OSTEP Chapter 18: Paging Introduction",
        "authors": "Remzi & Andrea Arpaci-Dusseau",
        "domain": "Operating Systems",
        "secondary_domains": [],
        "page_number": 4,
        "printed_page": "4",
        "section_title": "Page Tables and Address Translation",
        "structural_class": "BODY",
        "concept_ids": ["paging"],
        "text": "Paging splits virtual address space into fixed-size pages mapped via a page table.",
    }
    v3_bytes = (json.dumps(v3_rec) + "\n").encode("utf-8")
    v3_file.write_bytes(v3_bytes)
    v2_file.write_text(
        json.dumps({"doc_id": "books/old.pdf", "page_number": 1, "text": "Legacy v2 chunk."}) + "\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("ARCHIPELAGO_CANDIDATE_PASSAGES", raising=False)
    monkeypatch.delenv(ENV_CORPUS_VERSION, raising=False)
    path_default, _src, ver_default = resolve_candidate_passages_path(fake_here)
    assert path_default == v3_file
    assert ver_default == CORPUS_V3_ID

    monkeypatch.setenv(ENV_CORPUS_VERSION, CORPUS_V2_ID)
    path_v2, _src2, ver_v2 = resolve_candidate_passages_path(fake_here)
    assert path_v2 == v2_file
    assert ver_v2 == CORPUS_V2_ID

    # Load v3 via env path + SHA-256 verification.
    monkeypatch.setenv("ARCHIPELAGO_CANDIDATE_PASSAGES", str(v3_file))
    monkeypatch.setenv("ARCHIPELAGO_CANDIDATE_PASSAGES_SHA256", hashlib.sha256(v3_bytes).hexdigest())
    catalog = Catalog(nodes={}, books=[])
    assert catalog.candidate_passages_info["loaded"] is True
    assert catalog.candidate_passages_info["checksum_verified"] is True
    assert catalog.candidate_passages_info["corpus_version"] == CORPUS_V3_ID
    assert catalog.passages[0]["domain"] == "Operating Systems"
    assert catalog.passages[0]["source_title"] == "OSTEP Chapter 18: Paging Introduction"
    assert catalog.passages[0]["structural_class"] == "BODY"


# ── Goal 2 & 3: Honest Hybrid BM25 + Genuine Dense & Graph-Independent Retrieval ─


@pytest.mark.unit
def test_hybrid_retriever_honest_method_labels_with_and_without_dense() -> None:
    """Hybrid retriever labels bm25_lexical honestly when dense is off and hybrid when active."""
    passages = [
        {
            "passage_id": "p1",
            "doc_id": "d14_oa/stats/bayes.pdf",
            "page": 12,
            "domain": "Probability & Statistics",
            "structural_class": "BODY",
            "text": "Bayes theorem computes posterior probability P(A|B) = P(B|A) P(A) / P(B) from prior and likelihood.",
        },
        {
            "passage_id": "p2",
            "doc_id": "d14_oa/stats/toc.pdf",
            "page": 1,
            "domain": "Probability & Statistics",
            "structural_class": "TOC",
            "section_title": "Table of Contents",
            "text": "Chapter 1 Bayes theorem and conditional probability ... 12",
        },
        {
            "passage_id": "p3",
            "doc_id": "d14_oa/net/tcp.pdf",
            "page": 5,
            "domain": "Computer Networks",
            "structural_class": "BODY",
            "text": "TCP congestion control uses slow start and additive increase multiplicative decrease.",
        },
    ]

    # Lexical-only mode must never claim dense retrieval.
    lex_ret = HybridPassageRetriever(passages, corpus_version=CORPUS_V3_ID, enable_dense=False)
    lex_res = lex_ret.retrieve("posterior probability from prior and likelihood", top_k=3)
    assert lex_res.method == METHOD_BM25_LEXICAL
    assert lex_res.dense_available is False
    assert lex_res.hits[0].passage["passage_id"] == "p1"
    assert lex_res.hits[0].dense_score is None

    # Dense-only mode with unavailable encoder returns empty honestly.
    dense_off = lex_ret.retrieve("posterior probability", top_k=3, mode="dense")
    assert dense_off.hits == []
    assert dense_off.dense_available is False

    # With a genuine injected neural encoder function, hybrid RRF is active and labeled.
    def _toy_neural_encode(texts: list[str]) -> np.ndarray:
        vecs = []
        for t in texts:
            tl = t.lower()
            vecs.append(
                [
                    1.0 if ("bayes" in tl or "posterior" in tl or "likelihood" in tl) else 0.0,
                    1.0 if ("tcp" in tl or "congestion" in tl) else 0.0,
                    0.2,
                ]
            )
        return np.asarray(vecs, dtype=np.float32)

    encoder = DensePassageEncoder(model_name="test-neural-encoder", encode_fn=_toy_neural_encode)
    hyb_ret = HybridPassageRetriever(
        passages, corpus_version=CORPUS_V3_ID, dense_encoder=encoder
    )
    hyb_res = hyb_ret.retrieve("How does posterior probability update the prior?", top_k=3)
    assert hyb_res.method == METHOD_HYBRID_BM25_DENSE
    assert hyb_res.dense_available is True
    assert hyb_res.dense_model == "test-neural-encoder"
    assert hyb_res.hits[0].passage["passage_id"] == "p1"
    assert hyb_res.hits[0].dense_score is not None

    dense_only = hyb_ret.retrieve("posterior prior update", top_k=2, mode="dense")
    assert dense_only.method == METHOD_DENSE_NEURAL
    assert dense_only.hits[0].passage["passage_id"] == "p1"


@pytest.mark.unit
def test_graph_independent_retrieval_succeeds_without_graph_node(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Routing retrieves corpus passages even when the queried concept is absent from the graph."""
    monkeypatch.setenv("ARCHIPELAGO_DENSE_RETRIEVAL", "0")
    monkeypatch.setenv("ARCHIPELAGO_CANDIDATE_PASSAGES", "0")
    empty_graph = LibraryGraph(V2_GRAPH_PATH, allow_env_override=False)
    catalog = Catalog(nodes={}, books=[])
    catalog.passages = [
        {
            "passage_id": "d14:raft:p7:c0",
            "doc_id": "d14_oa/distributed/raft_consensus.pdf",
            "page": 7,
            "domain": "Operating Systems",
            "source_title": "In Search of an Understandable Consensus Algorithm",
            "authors": "Diego Ongaro & John Ousterhout",
            "section_title": "Leader Election and Log Replication",
            "structural_class": "BODY",
            "corpus_version": CORPUS_V3_ID,
            "text": (
                "Raft consensus achieves fault-tolerant state machine replication via leader election, "
                "randomized election timeouts, and AppendEntries RPC log replication across quorum nodes."
            ),
        }
    ]
    engine = SimpleNamespace(graph=empty_graph, catalog=catalog)
    route_name, text, anchor, extra = route(
        engine, "How does Raft consensus handle leader election and log replication?"
    )
    assert anchor is None
    assert route_name == "GENERAL_EXPLANATION"
    assert extra.get("graph_independent_retrieval") is True
    assert extra.get("retrieval_method") == METHOD_BM25_LEXICAL
    cites = extra.get("citations") or []
    assert len(cites) == 1
    assert cites[0]["chunk_id"] == "d14:raft:p7:c0"
    assert "Raft consensus" in text


# ── Goal 4: Specificity, Alias Register, Multi-Concept, Explanatory Ranking ──


@pytest.mark.unit
@pytest.mark.parametrize(
    ("query", "expected_primary"),
    [
        ("Explain Singular Value Decomposition (SVD) in linear algebra", "singular_value_decomposition"),
        ("How do Graph Attention Networks (GAT) compute attention?", "graph_attention_network"),
        ("Explain LALR bottom-up parsing in syntax analysis", "lalr"),
        ("How does paging work in virtual memory?", "paging"),
        ("How does a B+ Tree index support range queries?", "b_plus_tree"),
    ],
)
def test_concept_specificity_prevents_broad_umbrella_hijacking(
    graph_v2: LibraryGraph, query: str, expected_primary: str
) -> None:
    """Specific concepts outrank broad umbrella parents via alias register and specificity rules."""
    hits = graph_v2.phrase_hits(query)
    assert hits, f"Expected concept match for {query!r}"
    assert hits[0] == expected_primary


@pytest.mark.unit
def test_multi_concept_resolution_orders_specific_concepts_first(graph_v2: LibraryGraph) -> None:
    """Multi-concept queries resolve both specific anchors without broad-parent hijacking."""
    anchors = graph_v2.resolve_multi_concepts(
        "Compare Singular Value Decomposition (SVD) and Principal Component Analysis (PCA) in linear algebra"
    )
    assert "singular_value_decomposition" in anchors[:2]
    assert "principal_component_analysis" in anchors[:2]


@pytest.mark.unit
def test_ostep_paging_and_math_explanatory_chunks_outrank_intro_and_toc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explanatory body chunks outrank dialogue/intro/TOC/reference chunks for OS and Math."""
    monkeypatch.setenv("ARCHIPELAGO_DENSE_RETRIEVAL", "0")
    monkeypatch.setenv("ARCHIPELAGO_CANDIDATE_PASSAGES", "0")
    catalog = Catalog(nodes={}, books=[])
    catalog.passages = [
        {
            "passage_id": "ostep:dialogue:p1",
            "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/00_Dialogue.pdf",
            "page": 1,
            "domain": "Operating Systems",
            "section_title": "A Dialogue on the Book",
            "structural_class": "BODY",
            "text": "Professor: Welcome to Operating Systems! Later we will discuss paging and virtual memory.",
        },
        {
            "passage_id": "ostep:addr:p1",
            "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/06_address_spaces.pdf",
            "page": 1,
            "domain": "Operating Systems",
            "section_title": "Address Spaces Overview",
            "structural_class": "BODY",
            "text": "Early operating systems ran one process at a time before paging and virtual memory.",
        },
        {
            "passage_id": "ostep:paging:p5",
            "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/08_paging.pdf",
            "page": 5,
            "domain": "Operating Systems",
            "section_title": "Page Table Translation",
            "structural_class": "BODY",
            "text": (
                "Paging divides virtual address spaces into fixed-size pages. The virtual page number (VPN) "
                "indexes the per-process page table to find the physical frame number (PFN), while the page offset "
                "is preserved unchanged during address translation."
            ),
        },
        {
            "passage_id": "math:mle_toc:p1",
            "doc_id": "d14_oa/math/deisenroth_mml.pdf",
            "page": 1,
            "domain": "Mathematics for ML",
            "section_title": "Table of Contents",
            "structural_class": "TOC",
            "text": "9.2 Maximum Likelihood Estimation and Gaussian MLE ... 295",
        },
        {
            "passage_id": "math:mle_body:p295",
            "doc_id": "d14_oa/math/deisenroth_mml.pdf",
            "page": 295,
            "domain": "Mathematics for ML",
            "section_title": "Gaussian Maximum Likelihood Estimation",
            "structural_class": "BODY",
            "text": (
                "To derive the Gaussian MLE, we maximize the log-likelihood of i.i.d. observations under a "
                "normal distribution. Setting the derivative with respect to mean mu and variance sigma^2 to zero "
                "yields the sample mean and empirical variance."
            ),
        },
        {
            "passage_id": "math:pca_body:p320",
            "doc_id": "d14_oa/math/deisenroth_mml.pdf",
            "page": 320,
            "domain": "Mathematics for ML",
            "section_title": "Principal Component Analysis",
            "structural_class": "BODY",
            "text": (
                "Principal Component Analysis (PCA) projects centered data onto orthogonal eigenvectors of the "
                "sample covariance matrix ordered by largest eigenvalue to maximize retained variance."
            ),
        },
    ]

    paging_cites = select_catalog_passages(
        catalog, "How does paging translate a virtual address using a page table?", open_access_only=True
    )
    assert paging_cites
    assert paging_cites[0]["chunk_id"] == "ostep:paging:p5"

    mle_cites = select_catalog_passages(
        catalog, "Derive the Gaussian MLE for mean and variance", open_access_only=True
    )
    assert mle_cites
    assert mle_cites[0]["chunk_id"] == "math:mle_body:p295"

    pca_cites = select_catalog_passages(
        catalog, "How does PCA use covariance matrix eigenvectors?", open_access_only=True
    )
    assert pca_cites
    assert pca_cites[0]["chunk_id"] == "math:pca_body:p320"


# ── Goal 5: Cross-Domain Isolation + Legitimate Interdisciplinary Bridges ────


@pytest.mark.unit
def test_domain_isolation_blocks_contamination_while_preserving_interdisciplinary_bridges() -> None:
    """Pure cross-domain leakage is blocked while legitimate bridges remain compatible."""
    assert domains_compatible({DOMAIN_DB}, {DOMAIN_ML_AI}) is False
    assert domains_compatible({DOMAIN_OS}, {DOMAIN_DB}) is False
    assert domains_compatible({DOMAIN_NETWORKS}, {DOMAIN_SECURITY}) is True
    assert domains_compatible({DOMAIN_MATH}, {DOMAIN_PROB_STATS}) is True
    assert domains_compatible({DOMAIN_PROB_STATS}, {DOMAIN_ML_AI}) is True
    assert domains_compatible({DOMAIN_OS, DOMAIN_ML_AI}, {DOMAIN_OS}) is True
    assert domains_compatible({DOMAIN_OS, DOMAIN_ML_AI}, {DOMAIN_ML_AI}) is True

    explicit_domains = infer_doc_domains(
        "d14_oa/custom/source.pdf", explicit_domain="Information Security"
    )
    assert explicit_domains == {DOMAIN_SECURITY}
