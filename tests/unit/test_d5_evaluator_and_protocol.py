"""Issue #13 Scientific Evaluation Integrity & Protocol Tests (Agent C).

Exercises the actual evaluator modules (`d5_relationship_eval`,
`archipelago.eval.retrieval_baselines`, `host_inference/engine/answer.py`,
`research/d5_sigir_evaluation/build_blinded_pool.py`) against the frozen
benchmark artifacts, enforcing:
  - Frozen SHA-256 dataset/corpus/qrel/embedding locks
  - Dev vs held-out semantic leakage checks
  - Embedding manifest passage-order fingerprint verification
  - Live runtime verification of baseline Concept Resolution, Passage Retrieval,
    Abstention, and Exact-Triple Relationship Prediction numbers
  - Complete (all-item) null-grade provenance, 100% top-5 pooling coverage,
    system-blinding, and accurate non-double-blind terminology on human worksheets

Markers: unit
Run: PYTHONPATH=.:host_inference pytest tests/unit/test_d5_evaluator_and_protocol.py -v
"""

from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = REPO_ROOT / "host_inference"
D5_DIR = REPO_ROOT / "research" / "d5_sigir_evaluation"
BENCH_DIR = REPO_ROOT / "scripts" / "benchmarks"

for path_entry in (str(REPO_ROOT), str(HOST_DIR), str(BENCH_DIR)):
    if path_entry not in sys.path:
        sys.path.insert(0, path_entry)

FROZEN_SHA256: dict[Path, str] = {
    D5_DIR / "queries_dev_15.json": (
        "43893328d55fc5cb0b6f583ee7a20ab0eb36c95e686122db75703d6e6dadbd5b"
    ),
    D5_DIR / "queries_heldout_50.json": (
        "9e39430942b4f00d34911848cbe61a96532c29ffaee76f0d82ce69496f71103a"
    ),
    D5_DIR / "d5_graph_slice.json": (
        "55140e114dcf192cde59d95271a4cb81f1d099fb4de44b0135c6d95f3e455590"
    ),
    HOST_DIR / "fixtures" / "okf_graph.json": (
        "9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76"
    ),
    D5_DIR / "passage_qrels.json": (
        "b3e55ab147907940c6cd90ea5273284558037363066c4cfdd199efa0743bc8a2"
    ),
    D5_DIR / "corpus_embeddings_snowflake.npy": (
        "f2fe942e6c07d95337ec22b1bcaaa1e0666e33ee47012518db7a302be7ea26c2"
    ),
    D5_DIR / "concept_embeddings_snowflake.npy": (
        "db7a019a684b343c92c1a76aac7ebe2f1208362e560c9fffb8b91eec3818a3f3"
    ),
}

EXPECTED_SUPPORTED_HITS = 26
EXPECTED_SUPPORTED_TOTAL = 38
EXPECTED_UNSUPPORTED_TOTAL = 12
EXPECTED_BM25_MRR = 0.7500
EXPECTED_BM25_NDCG5 = 0.6415
EXPECTED_ARCHI_MRR = 0.4865
EXPECTED_ARCHI_NDCG5 = 0.2253
EXPECTED_EVAL_QREL_QUERIES = 37
EXPECTED_CITATION_TOTAL = 24
EXPECTED_CITATION_FULL_SUPPORT = 7
EXPECTED_CITATION_SPURIOUS = 9
BM25_K1 = 1.5
BM25_B = 0.75
TOP_K_EVAL = 5
MIN_PASSAGE_CHARS = 40

LEAKED_SYSTEM_TOKENS: tuple[str, ...] = (
    "bm25_lexical",
    "snowflake_arctic_neural",
    "archipelago_graph_assisted",
    "feature_hashed_vector",
)


def _load_pool_module() -> Any:
    """Dynamically load research/d5_sigir_evaluation/build_blinded_pool.py."""
    pool_script = D5_DIR / "build_blinded_pool.py"
    spec = importlib.util.spec_from_file_location("build_blinded_pool", pool_script)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _normalize_query(text: str) -> str:
    """Lowercase alphanumeric normalization for exact-duplicate leakage checks."""
    return " ".join("".join(ch.lower() if ch.isalnum() else " " for ch in text).split())


def _load_corpus_passages_and_flat_qrels() -> tuple[
    list[Any],
    dict[str, dict[str, Any]],
    dict[tuple[str, int], list[str]],
    dict[str, dict[str, int]],
]:
    """Load the 775 corpus passages and unwrapped algorithmic qrels using actual Passage class."""
    from archipelago.eval.retrieval_baselines import Passage

    raw_graph = json.loads((HOST_DIR / "fixtures" / "okf_graph.json").read_bytes())
    raw_qrels = json.loads((D5_DIR / "passage_qrels.json").read_bytes())

    passages: list[Passage] = []
    meta_by_id: dict[str, dict[str, Any]] = {}
    by_doc_page: dict[tuple[str, int], list[str]] = {}
    seen: set[str] = set()

    for cid, node in raw_graph.get("concepts", {}).items():
        for src in node.get("sources", []):
            text = (src.get("text_passage") or "").strip()
            doc_id = src.get("doc_id") or ""
            page = int(src.get("page_number") or 0)
            chunk_id = src.get("chunk_id") or f"{doc_id}_p{page}"
            if len(text) >= MIN_PASSAGE_CHARS:
                pid = f"{doc_id}::{chunk_id}"
                if pid not in seen:
                    seen.add(pid)
                    passages.append(
                        Passage(
                            pid, doc_id, chunk_id, page, src.get("section_title") or "", text, ""
                        )
                    )
                    meta_by_id[pid] = {"passage_id": pid, "doc_id": doc_id, "concept_id": cid}
                    by_doc_page.setdefault((doc_id, page), []).append(pid)

    flat_qrels: dict[str, dict[str, int]] = {}
    for qid, qdata in raw_qrels["qrels"].items():
        flat_qrels[qid] = {
            pid: int(label["relevance_grade"]) for pid, label in qdata["passages"].items()
        }
    return passages, meta_by_id, by_doc_page, flat_qrels


@pytest.mark.unit
def test_frozen_artifact_sha256_locks() -> None:
    """All frozen corpus, split, qrel, and cached embedding files match locked SHA-256."""
    for artifact_path, expected_sha in FROZEN_SHA256.items():
        assert artifact_path.exists(), f"Missing frozen artifact: {artifact_path}"
        actual_sha = hashlib.sha256(artifact_path.read_bytes()).hexdigest()
        assert actual_sha == expected_sha, (
            f"SHA-256 mismatch for {artifact_path.name}: got {actual_sha}, expected {expected_sha}"
        )


@pytest.mark.unit
def test_embedding_manifest_passage_order_fingerprint() -> None:
    """Embedding manifest passage_id_order_fingerprint reproduces deterministically."""
    manifest = json.loads((D5_DIR / "embedding_manifest.json").read_bytes())
    passages, _, _, _ = _load_corpus_passages_and_flat_qrels()
    computed = hashlib.sha256("\n".join(p.passage_id for p in passages).encode()).hexdigest()
    assert manifest["corpus_passages"]["passage_id_order_fingerprint"] == computed


@pytest.mark.unit
def test_dev_vs_heldout_no_exact_text_or_id_leakage() -> None:
    """Dev (15) and held-out (50) splits have zero query ID or normalized text overlap."""
    dev = json.loads((D5_DIR / "queries_dev_15.json").read_bytes())
    held = json.loads((D5_DIR / "queries_heldout_50.json").read_bytes())
    assert not ({q["query_id"] for q in dev} & {q["query_id"] for q in held})
    assert not (
        {_normalize_query(q["query"]) for q in dev} & {_normalize_query(q["query"]) for q in held}
    )


@pytest.mark.unit
def test_live_engine_concept_resolution_and_abstention_baseline() -> None:
    """Actual Engine() reproduces 26/38 concept resolution and 12/12 clean abstention."""
    from engine.answer import Engine

    engine = Engine()
    queries: list[dict[str, Any]] = json.loads((D5_DIR / "queries_heldout_50.json").read_bytes())
    supported_hits = 0
    unsupported_clean = 0

    for q in queries:
        payload = engine.answer(q["query"])["payload"]
        anchor = payload.get("anchor_concept")
        pred_cid = anchor.get("id") if isinstance(anchor, dict) else None
        if q["is_supported"]:
            gold = set(q.get("gold_relevant_concepts", []))
            if pred_cid and (pred_cid == q.get("expected_concept") or pred_cid in gold):
                supported_hits += 1
        else:
            assert pred_cid is None, f"Unsupported {q['query_id']} resolved to {pred_cid}"
            assert payload.get("render_graph") is False
            cites = payload.get("citations", [])
            non_pearson = [c for c in cites if not c.get("is_pearson")]
            assert non_pearson == [], (
                f"Unsupported {q['query_id']} returned corpus cites: {non_pearson}"
            )
            if q["query_id"] != "Q45":
                assert cites == [], (
                    f"Unsupported {q['query_id']} returned unexpected cites: {cites}"
                )
            unsupported_clean += 1

    assert supported_hits == EXPECTED_SUPPORTED_HITS
    assert unsupported_clean == EXPECTED_UNSUPPORTED_TOTAL


@pytest.mark.unit
def test_live_passage_retrieval_matches_v2_algorithmic_qrels() -> None:
    """Actual BM25Retriever and Engine() match d5_1_evaluation_results_v2.json metrics."""
    from engine.answer import Engine

    from archipelago.eval.retrieval_baselines import BM25Retriever, ndcg_at_k, reciprocal_rank

    passages, meta_by_id, by_doc_page, qrels = _load_corpus_passages_and_flat_qrels()
    queries: list[dict[str, Any]] = json.loads((D5_DIR / "queries_heldout_50.json").read_bytes())
    bm25 = BM25Retriever(passages, k1=BM25_K1, b=BM25_B)
    engine = Engine()

    bm_mrrs, bm_ndcgs, ar_mrrs, ar_ndcgs = [], [], [], []
    for q in queries:
        rel_map = qrels.get(q["query_id"], {})
        if not rel_map:
            continue
        bm_pids = [pid for pid, _ in bm25.search(q["query"], top_k=TOP_K_EVAL)]
        bm_mrrs.append(reciprocal_rank(bm_pids, rel_map) or 0.0)
        bm_ndcgs.append(ndcg_at_k(bm_pids, rel_map, TOP_K_EVAL) or 0.0)

        cites = engine.answer(q["query"])["payload"].get("citations", [])
        archi_pids: list[str] = []
        for c in cites:
            c_doc = c.get("doc_id") or ""
            c_chunk = c.get("chunk_id")
            c_page = int(c.get("page_number") or 0)
            cpid = f"{c_doc}::{c_chunk}" if (c_doc and c_chunk) else None
            if cpid and cpid in meta_by_id:
                if cpid not in archi_pids:
                    archi_pids.append(cpid)
            else:
                for mpid in by_doc_page.get((c_doc, c_page), []):
                    if mpid not in archi_pids:
                        archi_pids.append(mpid)
        ar_top = archi_pids[:TOP_K_EVAL]
        ar_mrrs.append(reciprocal_rank(ar_top, rel_map) or 0.0)
        ar_ndcgs.append(ndcg_at_k(ar_top, rel_map, TOP_K_EVAL) or 0.0)

    assert len(bm_mrrs) == EXPECTED_EVAL_QREL_QUERIES
    assert round(float(np.mean(bm_mrrs)), 4) == pytest.approx(EXPECTED_BM25_MRR)
    assert round(float(np.mean(bm_ndcgs)), 4) == pytest.approx(EXPECTED_BM25_NDCG5)
    assert round(float(np.mean(ar_mrrs)), 4) == pytest.approx(EXPECTED_ARCHI_MRR)
    assert round(float(np.mean(ar_ndcgs)), 4) == pytest.approx(EXPECTED_ARCHI_NDCG5)


@pytest.mark.unit
def test_live_relationship_evaluator_exact_triple_baseline() -> None:
    """Actual evaluate_relationship_predictions() reproduces TP=0, assessable=2, absent=13."""
    from d5_relationship_eval import evaluate_relationship_predictions
    from engine.answer import Engine

    queries: list[dict[str, Any]] = json.loads((D5_DIR / "queries_heldout_50.json").read_bytes())
    res = evaluate_relationship_predictions(queries, Engine())
    assert res["total_relational_queries"] == 18
    assert res["assessable_queries"] == 2
    assert res["true_positives"] == 0
    assert res["predicate_absent_in_graph"] == 13
    assert res["no_anchor_resolved"] == 3
    assert res["precision_over_all_surfaced_triples"] == 0.0
    assert res["recall_over_assessable_queries"] == 0.0
    assert res["f1_assessable"] == 0.0


@pytest.mark.unit
def test_blinded_pool_complete_coverage_and_strict_null_grades() -> None:
    """All 731 worksheet items & reviewer CSVs cover 100% of top-5 runs with strictly null grades."""
    pool_mod = _load_pool_module()
    ws = json.loads((D5_DIR / "human_annotation_worksheet.json").read_bytes())
    meta = ws["worksheet_metadata"]
    items: list[dict[str, Any]] = ws["items"]

    assert meta["status"] == "PENDING_HUMAN_ANNOTATION"
    assert meta["human_judgments_completed"] == 0
    assert "double-blind" not in meta["standard"].lower(), (
        "Worksheet standard must not mislabel single-blinded IR pooling as double-blind."
    )

    ws_pairs: set[tuple[str, str]] = set()
    for item in items:
        ws_pairs.add((item["query_id"], item["passage_id"]))
        assert item["blinded_candidate_id"].startswith("CAND-")
        assessment = item["reviewer_assessment"]
        for field_name, val in assessment.items():
            assert val is None, f"Non-null human field {field_name}={val} in {item['item_id']}"
        serialized = json.dumps(item).lower()
        for sys_token in LEAKED_SYSTEM_TOKENS:
            assert sys_token not in serialized, (
                f"System name {sys_token} leaked in {item['item_id']}"
            )

    for sys_name in pool_mod.POOLED_SYSTEMS:
        run_data = pool_mod.parse_trec_run(
            D5_DIR / "ranked_runs" / f"{sys_name}.run", depth=TOP_K_EVAL
        )
        run_pairs = {(qid, pid) for qid, entries in run_data.items() for pid, _, _ in entries}
        missing = run_pairs - ws_pairs
        assert not missing, f"System {sys_name} missing {len(missing)} top-5 items from pool."

    ws_dir = D5_DIR / "worksheets"
    assert (ws_dir / "pool_key_SEALED.json").exists()
    for csv_name in ("reviewer_A_worksheet.csv", "reviewer_B_worksheet.csv"):
        csv_path = ws_dir / csv_name
        assert csv_path.exists(), f"Missing {csv_path}"
        with csv_path.open("r", encoding="utf-8", newline="") as fh:
            rows = list(csv.DictReader(fh))
        assert len(rows) == len(items)
        for row in rows:
            for blank_col in (
                "relevance_grade",
                "claim_supported",
                "reviewer_id",
                "review_date",
                "confidence",
                "notes",
            ):
                assert row[blank_col] == "", (
                    f"Pre-filled {blank_col} in {csv_name} {row['item_id']}"
                )


@pytest.mark.unit
def test_citation_audit_and_v2_disclosures() -> None:
    """Verify citation audit counts (7/24 strict, 9/24 spurious, author-only) and v2 qrel disclosure."""
    audit = json.loads((D5_DIR / "citation_grounding_audit.json").read_bytes())
    assert audit["audit_metadata"]["independent_peer_review"] is False
    stats = audit["overall_audit_statistics"]
    assert stats["total_citations_from_live_engine"] == EXPECTED_CITATION_TOTAL
    assert stats["claim_support_breakdown"]["fully_supported"] == EXPECTED_CITATION_FULL_SUPPORT
    assert stats["claim_support_breakdown"]["irrelevant_or_spurious"] == EXPECTED_CITATION_SPURIOUS

    v2 = json.loads((D5_DIR / "d5_1_evaluation_results_v2.json").read_bytes())
    assert "ALGORITHMIC" in v2["metadata"]["qrel_provenance"]
    assert "not human-verified" in v2["metadata"]["qrel_provenance"].lower()
