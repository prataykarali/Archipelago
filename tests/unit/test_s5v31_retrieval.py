"""Unit tests for S5-v3.1 Stage C retrieval verification, model pinning, cache, and pooling."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
V3_SCRIPTS_DIR = REPO_ROOT / "research" / "s5-v3-benchmark-expansion" / "scripts"
V31_SCRIPTS_DIR = REPO_ROOT / "research" / "s5-v3-1-oa-corpus-expansion" / "scripts"
for entry in (str(V31_SCRIPTS_DIR), str(V3_SCRIPTS_DIR)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from retrieval_v3 import BM25LexicalControl, CorpusPassage  # noqa: E402
from retrieval_v31 import (  # noqa: E402
    CONTROL_SYSTEM_NAMES,
    GRAPH_V3_SYSTEM_NAMES,
    DenseSnowflakeRetriever,
    HybridRRFControl,
    ModelVerificationReport,
    compute_corpus_identity_hashes,
    compute_file_sha256,
    load_eligible_v31_passages,
    load_or_build_embedding_cache,
    run_v31_verification_suite,
    verify_embedding_cache_integrity,
    verify_pinned_model_files,
)

FAKE_DIM = 16


def _deterministic_fake_encoder(texts: list[str]) -> np.ndarray:
    """Fast deterministic unit-normalized encoder for unit tests (zero network/weights)."""
    rows: list[np.ndarray] = []
    for text in texts:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        vec = np.array([b / 255.0 - 0.5 for b in digest[:FAKE_DIM]], dtype=np.float32)
        norm = float(np.linalg.norm(vec))
        rows.append(vec / norm if norm > 0.0 else vec)
    return np.vstack(rows).astype(np.float32)


def _sample_passages() -> list[CorpusPassage]:
    return [
        CorpusPassage(
            passage_id="os::p001",
            source_doc_id="os_doc",
            text="Virtual memory page tables map virtual addresses to physical frames.",
            page_start=12,
            page_end=12,
            provenance_class="oa_html_extracted",
            source_sha256="os111",
        ),
        CorpusPassage(
            passage_id="db::p001",
            source_doc_id="db_doc",
            text="Database normalization removes update anomalies using functional dependencies.",
            page_start=45,
            page_end=45,
            provenance_class="oa_html_extracted",
            source_sha256="db222",
        ),
        CorpusPassage(
            passage_id="net::p001",
            source_doc_id="net_doc",
            text="TCP congestion control adjusts the congestion window after packet loss.",
            page_start=88,
            page_end=88,
            provenance_class="oa_rst_extracted",
            source_sha256="net333",
        ),
        CorpusPassage(
            passage_id="dist::p001",
            source_doc_id="dist_doc",
            text="Raft consensus elects a leader and replicates a deterministic state machine log.",
            page_start=15,
            page_end=15,
            provenance_class="oa_tex_extracted",
            source_sha256="dist444",
        ),
        CorpusPassage(
            passage_id="ml::p001",
            source_doc_id="mml_doc",
            text="Singular value decomposition factorizes matrices into orthogonal components.",
            page_start=110,
            page_end=110,
            provenance_class="pdf_extracted",
            source_sha256="ml555",
        ),
        CorpusPassage(
            passage_id="ml::p002",
            source_doc_id="mml_doc",
            text="Principal component analysis uses eigenvalues and eigenvectors of covariance.",
            page_start=318,
            page_end=318,
            provenance_class="pdf_extracted",
            source_sha256="ml555",
        ),
    ]


def _write_sample_graph(path: Path) -> None:
    payload = {
        "concepts": {
            "svd": {
                "name": "Singular Value Decomposition",
                "concept_type": "method",
                "sources": [],
            },
            "pca": {
                "name": "Principal Component Analysis",
                "concept_type": "method",
                "sources": [],
            },
            "virtual_memory": {"name": "Virtual Memory", "concept_type": "concept", "sources": []},
        },
        "edges": [
            {
                "from_id": "pca",
                "from_name": "Principal Component Analysis",
                "to_id": "svd",
                "to_name": "Singular Value Decomposition",
                "edge_type": "USES",
                "relation": "uses",
                "source": "mml:p318",
                "confidence": 0.9,
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.mark.unit
def test_pinned_model_file_verification_passes_and_detects_tampering(tmp_path: Path) -> None:
    """Model pin verification validates exact byte sizes and SHA-256 and rejects tampering."""
    model_dir = tmp_path / "models" / "demo_model"
    model_dir.mkdir(parents=True)
    weights = model_dir / "model.safetensors"
    weights.write_bytes(b"deterministic-weight-payload")
    pin_path = tmp_path / "pin.json"
    pin_path.write_text(
        json.dumps(
            {
                "repo_id": "Snowflake/snowflake-arctic-embed-m-v1.5",
                "revision": "e58a8f756156a1293d763f17e3aae643474e9b8a",
                "license": "Apache-2.0",
                "local_path": "models/demo_model",
                "files": {
                    "model.safetensors": {
                        "bytes": weights.stat().st_size,
                        "sha256": compute_file_sha256(weights),
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    pin_data, resolved_dir, pin_sha = verify_pinned_model_files(pin_path, tmp_path)
    assert resolved_dir == model_dir
    assert pin_data["license"] == "Apache-2.0"
    assert len(pin_sha) == 64

    # Tamper with weight bytes -> must raise ValueError
    weights.write_bytes(b"corrupted-weight-payload-xxx")
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_pinned_model_files(pin_path, tmp_path)


@pytest.mark.unit
def test_dense_embedding_cache_build_reload_and_tamper_rejection(tmp_path: Path) -> None:
    """Dense embedding cache verifies corpus/model/matrix hashes and fails closed on tampering."""
    passages = _sample_passages()
    cache_npy = tmp_path / "embeddings" / "test_cache.npy"
    pin_sha = "a" * 64
    rev = "e58a8f756156a1293d763f17e3aae643474e9b8a"

    emb1, meta1 = load_or_build_embedding_cache(
        passages,
        cache_npy,
        pin_sha,
        rev,
        encode_fn=_deterministic_fake_encoder,
    )
    assert emb1.shape == (len(passages), FAKE_DIM)
    assert cache_npy.exists()

    # Reload without re-encoding (raising encoder proves cache was used)
    def _must_not_encode(_texts: list[str]) -> np.ndarray:
        raise AssertionError("Cache should have been loaded without re-encoding")

    emb2, meta2 = load_or_build_embedding_cache(
        passages,
        cache_npy,
        pin_sha,
        rev,
        encode_fn=_must_not_encode,
    )
    assert np.allclose(emb1, emb2)
    assert meta2["embedding_matrix_sha256"] == meta1["embedding_matrix_sha256"]

    # Tamper with .npy -> fail closed
    np.save(str(cache_npy), np.zeros_like(emb1))
    fp = compute_corpus_identity_hashes(passages)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_embedding_cache_integrity(
            cache_npy,
            meta1,
            expected_passage_count=len(passages),
            expected_passage_ids_sha256=fp["passage_ids_sha256"],
            expected_passage_texts_sha256=fp["passage_texts_sha256"],
            expected_model_pin_sha256=pin_sha,
        )


@pytest.mark.unit
def test_hybrid_rrf_deterministic_fusion_and_tie_breaking() -> None:
    """Hybrid RRF fuses BM25 + Dense deterministically across repeated calls."""
    passages = _sample_passages()
    bm25 = BM25LexicalControl(passages)
    embs = _deterministic_fake_encoder([p.text for p in passages])
    dense = DenseSnowflakeRetriever(passages, embs, _deterministic_fake_encoder)
    hybrid = HybridRRFControl(bm25, dense, rrf_k=60, candidate_k=6)

    res_a, prov_a = hybrid.search_ranked("virtual memory page tables", top_k=5)
    res_b, _ = hybrid.search_ranked("virtual memory page tables", top_k=5)
    assert [r.passage_id for r in res_a] == [r.passage_id for r in res_b]
    assert len(res_a) == 5
    assert prov_a.routing_decision == "hybrid_rrf_bm25_dense"


@pytest.mark.unit
def test_load_eligible_v31_passages_filters_ineligible(tmp_path: Path) -> None:
    """Eligible passage loader excludes rows marked ineligible or unusable."""
    jsonl = tmp_path / "corpus.jsonl"
    rows = [
        {"passage_id": "p1", "source_doc_id": "d1", "text": "valid passage", "is_usable": True},
        {"passage_id": "p2", "source_doc_id": "d1", "text": "bad", "is_usable": False},
        {
            "passage_id": "p3",
            "source_doc_id": "d1",
            "text": "excluded",
            "eligible_for_benchmark": False,
        },
    ]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    passages, stats = load_eligible_v31_passages(jsonl)
    assert [p.passage_id for p in passages] == ["p1"]
    assert stats["total_rows_read"] == 3
    assert stats["eligible_passages_used"] == 1
    assert stats["excluded_ineligible_rows"] == 2


@pytest.mark.unit
def test_v31_verification_suite_end_to_end_zero_kuzu_dependency(tmp_path: Path) -> None:
    """Full 8-system S5-v3.1 suite runs without okf_graph.db and computes depth-5/10 pools."""
    passages = _sample_passages()
    graph_path = tmp_path / "okf_graph.json"
    _write_sample_graph(graph_path)
    cache_npy = tmp_path / "embeddings" / "v31.npy"

    queries = [
        {
            "query_id": "q1",
            "query_text": "Explain PCA and SVD",
            "split": "dev",
            "category": "single",
        },
        {
            "query_id": "q2",
            "query_text": "How do virtual memory page tables work?",
            "split": "test",
            "category": "single",
        },
        {
            "query_id": "q3",
            "query_text": "How does Raft consensus replicate logs?",
            "split": "test",
            "category": "single",
        },
    ]
    model_report = ModelVerificationReport(
        repo_id="Snowflake/snowflake-arctic-embed-m-v1.5",
        revision="e58a8f756156a1293d763f17e3aae643474e9b8a",
        license_id="Apache-2.0",
        pin_manifest_sha256="b" * 64,
        local_path_relative="data/annotation_local/s5v3/models/snowflake-arctic-embed-m-v1.5",
        verified_file_count=11,
        total_weight_bytes=435588776,
        model_safetensors_sha256="c" * 64,
        all_files_verified=True,
        smoke_test={"device": "cpu", "all_finite": True, "benchmark_query_or_label_used": False},
    )

    manifest, diagnostics = run_v31_verification_suite(
        passages,
        graph_path,
        queries,
        model_report,
        cache_npy,
        encode_fn=_deterministic_fake_encoder,
        top_k=5,
    )

    assert manifest["depends_on_v21_okf_graph_db"] is False
    assert manifest["effectiveness_evaluation"] == "NOT_EVALUATED_PENDING_HUMAN_JUDGMENTS"
    assert manifest["system_count"] == len(CONTROL_SYSTEM_NAMES) + len(GRAPH_V3_SYSTEM_NAMES)
    assert manifest["determinism_verification"]["all_systems_deterministic"] is True

    d5 = diagnostics["pooling_diagnostics"]["depth_5"]["all_systems"]
    d10 = diagnostics["pooling_diagnostics"]["depth_10"]["all_systems"]
    assert d5["query_count"] == 3
    assert d5["total_unique_query_passage_pairs"] > 0
    assert d10["total_unique_query_passage_pairs"] >= d5["total_unique_query_passage_pairs"]
    assert "dev" in diagnostics["pooling_by_split"]
    assert "test" in diagnostics["pooling_by_split"]
