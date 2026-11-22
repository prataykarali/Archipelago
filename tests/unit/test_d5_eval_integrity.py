"""D5.2 Evaluation Integrity Tests (P0-5).

Tests that the D5.1 evaluation artifacts are internally consistent,
reproducible, and do not contain fabricated or misrepresented data.

Markers: unit
Run: PYTHONPATH=.:host_inference pytest tests/unit/test_d5_eval_integrity.py -v

ACM SIGIR 2027 Demonstrations Track — D5.2 P0 audit fixes
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = REPO_ROOT / "host_inference"
D5_DIR = REPO_ROOT / "research" / "d5_sigir_evaluation"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(HOST_DIR) not in sys.path:
    sys.path.append(str(HOST_DIR))

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SNOWFLAKE_MODEL_REVISION = "fc74610d18462d218e312aa986ec5c8a75a98152"
CORPUS_EXPECTED_SIZE = 775
CORPUS_EMBEDDING_SHAPE = (775, 768)
CONCEPT_EMBEDDING_SHAPE = (610, 768)
VALID_PREDICATES: frozenset[str] = frozenset(
    {"USES", "REQUIRES", "CONTRASTS_WITH", "APPLIES_TO", "UNLOCKS", "PART_OF", "RELATED"}
)
GRAPH_PREDICATES: frozenset[str] = frozenset({"REQUIRES", "RELATED", "UNLOCKS"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_corpus() -> list[dict[str, Any]]:
    """Load 775 deduplicated corpus passages from okf_graph.json."""
    graph_file = HOST_DIR / "fixtures" / "okf_graph.json"
    raw = json.loads(graph_file.read_bytes())
    passages: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _cid, node in raw.get("concepts", {}).items():
        for src in node.get("sources", []):
            text = (src.get("text_passage") or "").strip()
            doc_id = src.get("doc_id") or ""
            page = int(src.get("page_number") or 0)
            chunk_id = src.get("chunk_id") or f"{doc_id}_p{page}"
            if len(text) >= 40:
                pid = f"{doc_id}::{chunk_id}"
                if pid not in seen:
                    seen.add(pid)
                    passages.append(
                        {
                            "passage_id": pid,
                            "doc_id": doc_id,
                            "page_number": page,
                            "chunk_id": chunk_id,
                            "content_sha256": hashlib.sha256(text.encode()).hexdigest(),
                        }
                    )
    return passages


# ---------------------------------------------------------------------------
# P0-5 Tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
def test_snowflake_model_revision_cached() -> None:
    """Snowflake model snapshot directory matches the pinned revision."""
    hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
    model_dir = hf_cache / "models--Snowflake--snowflake-arctic-embed-m" / "snapshots"
    if not model_dir.exists():
        pytest.skip("Snowflake model not cached locally; skip on CI without GPU.")
    snapshot_dirs = [d.name for d in model_dir.iterdir() if d.is_dir()]
    assert SNOWFLAKE_MODEL_REVISION in snapshot_dirs, (
        f"Pinned revision {SNOWFLAKE_MODEL_REVISION} not found in snapshots: {snapshot_dirs}"
    )


@pytest.mark.unit
def test_corpus_embedding_array_shape() -> None:
    """Corpus embedding .npy file matches expected shape (775, 768)."""
    npy_path = D5_DIR / "corpus_embeddings_snowflake.npy"
    assert npy_path.exists(), f"Missing corpus embeddings: {npy_path}"
    arr = np.load(str(npy_path))
    assert arr.shape == CORPUS_EMBEDDING_SHAPE, (
        f"Expected shape {CORPUS_EMBEDDING_SHAPE}, got {arr.shape}"
    )
    assert arr.dtype in (np.float32, np.float64), f"Unexpected dtype: {arr.dtype}"


@pytest.mark.unit
def test_concept_embedding_array_shape() -> None:
    """Concept embedding .npy file matches expected shape (610, 768)."""
    npy_path = D5_DIR / "concept_embeddings_snowflake.npy"
    assert npy_path.exists(), f"Missing concept embeddings: {npy_path}"
    arr = np.load(str(npy_path))
    assert arr.shape == CONCEPT_EMBEDDING_SHAPE, (
        f"Expected shape {CONCEPT_EMBEDDING_SHAPE}, got {arr.shape}"
    )


@pytest.mark.unit
def test_corpus_size() -> None:
    """Corpus has exactly 775 unique passage IDs (40+ char text)."""
    passages = _load_corpus()
    assert len(passages) == CORPUS_EXPECTED_SIZE, (
        f"Expected {CORPUS_EXPECTED_SIZE} corpus passages, found {len(passages)}"
    )


@pytest.mark.unit
def test_qrels_all_passage_ids_exist_in_corpus() -> None:
    """Every passage_id referenced in qrels exists in the 775-record corpus manifest."""
    qrels_path = D5_DIR / "passage_qrels.json"
    raw_qrels = json.loads(qrels_path.read_bytes())
    # Support both old flat format and new nested format
    if "qrels" in raw_qrels:
        qrel_pids: set[str] = set()
        for qdata in raw_qrels["qrels"].values():
            passages_dict = qdata.get("passages", qdata) if isinstance(qdata, dict) else {}
            qrel_pids.update(passages_dict.keys())
    else:
        qrel_pids = set()
        for labels in raw_qrels.values():
            if isinstance(labels, dict):
                qrel_pids.update(labels.keys())

    corpus_pids = {p["passage_id"] for p in _load_corpus()}
    missing = qrel_pids - corpus_pids
    assert not missing, (
        f"{len(missing)} qrel passage IDs not found in corpus: {sorted(missing)[:5]}..."
    )


@pytest.mark.unit
def test_relational_queries_use_valid_predicates() -> None:
    """All expected_relation predicates in queries must be in VALID_PREDICATES set."""
    queries_path = D5_DIR / "queries_heldout_50.json"
    queries = json.loads(queries_path.read_bytes())
    invalid = []
    for q in queries:
        exp_rel = q.get("expected_relation")
        if exp_rel:
            pred = exp_rel.get("rel", "")
            if pred not in VALID_PREDICATES:
                invalid.append((q["query_id"], pred))
    assert not invalid, f"Invalid predicates found: {invalid}"


@pytest.mark.unit
def test_relational_predicates_vs_graph_gap_disclosed() -> None:
    """Predicates in queries but absent from engine graph are documented."""
    queries_path = D5_DIR / "queries_heldout_50.json"
    queries = json.loads(queries_path.read_bytes())
    query_preds: set[str] = set()
    for q in queries:
        exp_rel = q.get("expected_relation")
        if exp_rel:
            query_preds.add(exp_rel.get("rel", ""))
    absent = query_preds - GRAPH_PREDICATES
    # The absent predicates must match the known gap documented in d5_relationship_eval.py
    expected_absent = {"USES", "CONTRASTS_WITH", "APPLIES_TO"}
    assert absent == expected_absent, (
        f"Predicate gap mismatch. Got absent={absent}, expected={expected_absent}"
    )


@pytest.mark.unit
def test_no_dataset_leakage_dev_in_heldout() -> None:
    """Dev split query IDs must not overlap with held-out query IDs."""
    dev_path = D5_DIR / "queries_dev_15.json"
    heldout_path = D5_DIR / "queries_heldout_50.json"
    if not dev_path.exists():
        pytest.skip("Dev split file not found.")
    dev_ids = {q["query_id"] for q in json.loads(dev_path.read_bytes())}
    heldout_ids = {q["query_id"] for q in json.loads(heldout_path.read_bytes())}
    overlap = dev_ids & heldout_ids
    assert not overlap, f"Leakage: {overlap} query IDs appear in both dev and heldout sets."


@pytest.mark.unit
def test_mrr_known_values() -> None:
    """MRR metric implementation sanity check against known values."""
    sys.path.insert(0, str(REPO_ROOT / "scripts" / "benchmarks"))
    from archipelago.eval.retrieval_baselines import reciprocal_rank

    # rank 1 hit
    assert reciprocal_rank(["a", "b", "c"], {"a": 1}) == pytest.approx(1.0)
    # rank 2 hit
    assert reciprocal_rank(["b", "a", "c"], {"a": 1}) == pytest.approx(0.5)
    # no hit
    assert reciprocal_rank(["b", "c"], {"a": 1}) == pytest.approx(0.0)


@pytest.mark.unit
def test_citation_audit_records_completeness() -> None:
    """Citation audit must have one record per actual engine-returned citation."""
    audit_path = D5_DIR / "citation_grounding_audit.json"
    audit = json.loads(audit_path.read_bytes())
    stats = audit.get("overall_audit_statistics", {})
    total_claimed = stats.get("total_citations_from_live_engine", 0)
    # Count actual records
    total_records = sum(
        len(qcase.get("citation_records", [])) for qcase in audit.get("audited_query_cases", [])
    )
    assert total_records == total_claimed, (
        f"Audit statistics claim {total_claimed} citations but only {total_records} records exist."
    )
    assert total_records > 0, "Citation audit has no records."


@pytest.mark.unit
def test_citation_audit_has_no_fabricated_query() -> None:
    """Citation audit must only contain queries Q01, Q08, Q21, Q23, Q39."""
    audit_path = D5_DIR / "citation_grounding_audit.json"
    audit = json.loads(audit_path.read_bytes())
    expected_qids = {"Q01", "Q08", "Q21", "Q23", "Q39"}
    actual_qids = {qc["query_id"] for qc in audit.get("audited_query_cases", [])}
    assert actual_qids == expected_qids, (
        f"Unexpected query IDs in citation audit: {actual_qids ^ expected_qids}"
    )


@pytest.mark.unit
def test_provenance_no_independent_review_claimed() -> None:
    """Reviewer provenance must not claim independent peer review was performed."""
    prov_path = D5_DIR / "reviewer_provenance.json"
    prov = json.loads(prov_path.read_bytes())
    breakdown = prov.get("provenance_breakdown", {})
    assert breakdown.get("independently_peer_reviewed", 0) == 0, (
        "Provenance claims independent peer review — this has not been performed."
    )
    # Check that individual records no longer use the legacy SIGIR_Reviewer_Lead label.
    # The disclosure text is allowed to mention it historically; records must not use it.
    records = prov.get("records", [])
    legacy_records = [r for r in records if r.get("reviewer") == "SIGIR_Reviewer_Lead"]
    assert not legacy_records, (
        f"{len(legacy_records)} records still have reviewer='SIGIR_Reviewer_Lead'. "
        "Must be changed to 'pratay_karali_lead_author' or similar."
    )


@pytest.mark.unit
def test_qrels_labelled_algorithmic_not_human() -> None:
    """QRels metadata must declare labels as algorithmic, not human-verified."""
    qrels_path = D5_DIR / "passage_qrels.json"
    raw = json.loads(qrels_path.read_bytes())
    if "metadata" not in raw:
        pytest.skip("Old flat qrels format without metadata key.")
    meta = raw["metadata"]
    assert meta.get("human_reviewed") is False, "QRels metadata claims human_reviewed=True."
    assert "ALGORITHMIC" in meta.get("label_generation_method", ""), (
        f"Expected ALGORITHMIC in label_generation_method, got: {meta.get('label_generation_method')}"
    )


@pytest.mark.unit
def test_embedding_manifest_validity() -> None:
    """Validate embedding manifest matches cached files and model specs."""
    manifest_path = D5_DIR / "embedding_manifest.json"
    assert manifest_path.exists(), f"Missing embedding manifest: {manifest_path}"
    manifest = json.loads(manifest_path.read_bytes())
    assert manifest["embedding_model"]["revision"] == SNOWFLAKE_MODEL_REVISION
    assert manifest["embedding_model"]["dimensions"] == 768
    assert manifest["corpus_passages"]["total_passages"] == CORPUS_EXPECTED_SIZE
    # Verify cached array checksums match
    for arr_name, arr_spec in manifest.get("cached_arrays", {}).items():
        arr_path = D5_DIR / arr_spec["filename"]
        assert arr_path.exists(), f"Missing cached array: {arr_path}"
        actual_sha = hashlib.sha256(arr_path.read_bytes()).hexdigest()
        assert actual_sha == arr_spec["sha256"], f"Checksum mismatch for {arr_name}"


@pytest.mark.unit
def test_unsupported_query_abstention_behavior() -> None:
    """Q39 (Spanner TrueTime) and near misses must cleanly abstain with 0 citations and no graph."""
    from engine.answer import Engine

    e = Engine()
    res = e.answer("Explain Spanner TrueTime and its prerequisites.")
    p = res["payload"]
    assert p.get("anchor_concept") is None, "Q39 should have no anchor"
    assert len(p.get("citations", [])) == 0, (
        f"Q39 returned {len(p['citations'])} citations, expected 0"
    )
    assert p.get("render_graph") is False, "Q39 should not render graph"
    assert p.get("prerequisites") == [], "Q39 should have empty prerequisites"
    assert p.get("unlocks") == [], "Q39 should have empty unlocks"


@pytest.mark.unit
def test_canonical_chunk_id_propagation() -> None:
    """LibraryGraph.cite_record must include canonical chunk_id for indexed concepts."""
    from engine.answer import Engine

    e = Engine()
    rec = e.graph.cite_record("transformer", "What is Transformer?")
    assert rec.get("chunk_id") is not None, "chunk_id missing from cite_record"
    assert rec.get("chunk_id").startswith("chunk_") or "_p" in rec.get("chunk_id")


@pytest.mark.unit
def test_human_annotation_worksheet_integrity() -> None:
    """Annotation worksheet must be present, blinded, with uncompleted reviewer fields."""
    ws_path = D5_DIR / "human_annotation_worksheet.json"
    assert ws_path.exists(), f"Missing worksheet: {ws_path}"
    ws = json.loads(ws_path.read_bytes())
    assert ws["worksheet_metadata"]["status"] == "PENDING_HUMAN_ANNOTATION"
    items = ws.get("items", [])
    assert len(items) >= 50, f"Too few items in worksheet: {len(items)}"
    # Verify reviewer assessment fields are NOT filled
    for item in items[:10]:
        assert item["reviewer_assessment"]["relevance_grade"] is None
        assert item["reviewer_assessment"]["reviewer_id"] is None
        assert item["blinded_candidate_id"].startswith("CAND-")
