"""Unit tests for D14.9 B2 retrieval relevance, honest abstention, and C3 dense profiles."""

from __future__ import annotations

from pathlib import Path
import sys

_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))
if str(_REPO / "host_inference") not in sys.path:
    sys.path.append(str(_REPO / "host_inference"))

from engine.evidence_selection import select_catalog_passages  # noqa: E402
from engine.graph import LibraryGraph  # noqa: E402

from archipelago.inference.dense_retriever import (  # noqa: E402
    DEFAULT_DENSE_MODEL,
    DENSE_MODEL_PROFILES,
    METHOD_BM25_LEXICAL,
    DensePassageEncoder,
)


class _FakeCatalog:
    def __init__(self, passages: list[dict[str, object]]) -> None:
        self.passages = passages


def test_out_of_coverage_query_returns_zero_passages() -> None:
    passages = [
        {
            "doc_id": "d14_oa/operating_systems/downey_think_os.pdf",
            "passage_id": "d14:aaa111bbb222:p10:c0",
            "page_number": 10,
            "domain": "Operating Systems",
            "structural_class": "BODY",
            "text": "The operating system manages process state and mechanism for context switching.",
        },
        {
            "doc_id": "d14_oa/database_systems/sqlite_architecture_docs.html",
            "passage_id": "d14:ccc333ddd444:p2:c0",
            "page_number": 2,
            "domain": "Database Systems",
            "structural_class": "BODY",
            "text": "Database cells store B-tree payload entries with a defined header state.",
        },
    ]
    cat = _FakeCatalog(passages)
    assert (
        select_catalog_passages(
            cat,
            "What is the biochemical mechanism of CRISPR-Cas9 gene editing in eukaryotic cells?",
            anchor_cid="",
            open_access_only=True,
        )
        == []
    )
    assert (
        select_catalog_passages(
            cat,
            "How did the Treaty of Westphalia reshape European state sovereignty in 1648?",
            anchor_cid="",
            open_access_only=True,
        )
        == []
    )


def test_in_domain_query_recalls_relevant_passage() -> None:
    passages = [
        {
            "doc_id": "d14_oa/computer_networks/rfc5681_tcp_congestion.txt",
            "passage_id": "d14:eee555fff666:p8:c0",
            "page_number": 8,
            "domain": "Computer Networks",
            "structural_class": "BODY",
            "text": "TCP fast recovery adjusts congestion window cwnd after three duplicate ACKs without slow start.",
        }
    ]
    cat = _FakeCatalog(passages)
    hits = select_catalog_passages(
        cat,
        "How does TCP fast recovery adjust cwnd after duplicate ACKs?",
        anchor_cid="",
        open_access_only=True,
    )
    assert len(hits) == 1
    assert hits[0]["doc_id"] == "d14_oa/computer_networks/rfc5681_tcp_congestion.txt"


def test_paraphrase_anchoring_for_virtual_pages_and_dp() -> None:
    graph = LibraryGraph.load_default()
    hits_paging = graph.phrase_hits(
        "How does the operating system map virtual page numbers to physical page frames?"
    )
    assert "paging" in hits_paging
    hits_dp = graph.phrase_hits(
        "What makes optimal substructure and overlapping subproblems essential for dynamic programming?"
    )
    assert "dynamic_programming" in hits_dp


def test_c3_dense_profiles_distinguish_runtime_and_experimental() -> None:
    assert DENSE_MODEL_PROFILES["runtime_default"]["model_id"] == DEFAULT_DENSE_MODEL
    assert DENSE_MODEL_PROFILES["experimental_baseline"]["model_id"] == "Snowflake/snowflake-arctic-embed-m"
    assert DENSE_MODEL_PROFILES["experimental_baseline"]["revision"] == "fc74610d"
    assert DENSE_MODEL_PROFILES["manifest_recommended"]["model_id"] == "Snowflake/snowflake-arctic-embed-m-v1.5"
    enc = DensePassageEncoder(model_name="nonexistent/fake-model-for-test", local_files_only=True)
    assert enc.is_available is False
    assert METHOD_BM25_LEXICAL == "bm25_lexical"
