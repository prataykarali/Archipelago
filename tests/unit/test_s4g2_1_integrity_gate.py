"""Unit tests for S4-G2.1: Multi-Domain Scientific Integrity Gate.

Verifies:
1. Removal of hardcoded metrics (unsupported rate, provenance coverage, cycles).
2. Full directed cycle detection for length k >= 2.
3. Provenance validation against real database chunks.
4. 36-item source verification audit results (all 36 audited, zero fabricated gold).
5. Conflicting DBMS chunk_001 page reuse detection.
6. Overgeneration and split audit integrity.
7. Semantic argument direction auditing.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
import pytest

from okf.eval.integrity_validators import (
    audit_semantic_direction,
    calculate_provenance_coverage,
    detect_directed_cycles,
    validate_edge_provenance,
)

ROOT = Path(__file__).resolve().parents[2]
GATE_DIR = ROOT / "research" / "s4-g2-1-integrity-gate"


def test_hardcoded_metrics_removed_from_results():
    """Verify that unsupported rate is NOT_MEASURED and cycles/provenance are calculated."""
    results_path = ROOT / "research" / "s4-g2-multidomain-evaluation" / "s4g2_multidomain_eval_results.json"
    assert results_path.exists(), "Results JSON must exist"

    with open(results_path, encoding="utf-8") as f:
        data = json.load(f)

    # Check across all domains and documents
    for dom_name, dom_info in data["domain_results"].items():
        for p_name, doc_list in dom_info["partitions"].items():
            for doc in doc_list:
                proto = doc["prototype"]
                # Must report NOT_MEASURED, never 0.0 or 0
                assert proto["unsupported_relation_rate"] == "NOT_MEASURED"
                assert "unsupported_rate_documentation" in proto
                # Provenance coverage must have documented denominator
                assert "provenance_total_denominator" in proto
                assert "valid_provenance_edges_count" in proto
                # Detected cycles must be present as integer
                assert isinstance(proto["detected_cycles_count"], int)


def test_cycle_detection_detects_length_3_and_arbitrary_cycles():
    """Verify that detect_directed_cycles detects length-3 cycles that 2-cycle guards miss."""
    # Triangular cycle: A -> B -> C -> A
    edges = [
        {"from_name": "A", "to_name": "B", "edge_type": "REQUIRES"},
        {"from_name": "B", "to_name": "C", "edge_type": "REQUIRES"},
        {"from_name": "C", "to_name": "A", "edge_type": "REQUIRES"},
        {"from_name": "D", "to_name": "E", "edge_type": "REQUIRES"},  # acyclic branch
    ]

    res = detect_directed_cycles(edges, edge_types=("REQUIRES", "UNLOCKS"))
    assert res["has_cycles"] is True
    assert res["cycle_count"] == 1
    assert res["cycle_lengths"] == [3]
    cycle = res["cycles"][0]
    assert cycle == ["a", "b", "c", "a"]


def test_cycle_detection_reports_zero_on_dag():
    """Verify that detect_directed_cycles reports 0 on a strict DAG."""
    edges = [
        {"from_name": "A", "to_name": "B", "edge_type": "REQUIRES"},
        {"from_name": "B", "to_name": "C", "edge_type": "REQUIRES"},
        {"from_name": "A", "to_name": "C", "edge_type": "REQUIRES"},
    ]
    res = detect_directed_cycles(edges, edge_types=("REQUIRES", "UNLOCKS"))
    assert res["has_cycles"] is False
    assert res["cycle_count"] == 0
    assert len(res["cycles"]) == 0


def test_provenance_validation_detects_fictitious_chunk():
    """Verify validate_edge_provenance rejects an edge with a fictitious chunk ID."""
    import kuzu

    db_path = ROOT / "okf_graph.db"
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)

    bad_edge = {
        "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf",
        "chunk_id": "chunk_9999_fictitious",
        "evidence_text": "Virtual memory provides an abstraction.",
    }
    res = validate_edge_provenance(bad_edge, conn)
    assert res["is_valid"] is False
    assert res["doc_exists"] is True
    assert res["chunk_exists"] is False
    assert "not found in document" in res["reason"]


def test_provenance_validation_detects_altered_text():
    """Verify validate_edge_provenance rejects an edge whose evidence snippet is not in chunk text."""
    import kuzu

    db_path = ROOT / "okf_graph.db"
    db = kuzu.Database(str(db_path), read_only=True)
    conn = kuzu.Connection(db)

    edge = {
        "doc_id": "pilot/silberschatz_3nf_card.txt",
        "chunk_id": "third_normal_form_seed_001",
        "evidence_text": "This completely fabricated sentence does not appear in the 3NF study card.",
    }
    res = validate_edge_provenance(edge, conn)
    assert res["is_valid"] is False
    assert res["chunk_exists"] is True
    assert res["text_match"] is False


def test_36_item_verification_audit_csv_exists_and_complete():
    """Verify source_verification_36_items.csv exists, has 36 items, and proper schema."""
    csv_path = GATE_DIR / "source_verification_36_items.csv"
    assert csv_path.exists(), "source_verification_36_items.csv must exist"

    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 36, "Must audit exactly 36 items"
    # Check domains
    domains = {r["domain"] for r in rows}
    assert len(domains) == 6

    # Every row must have an audit verdict
    for r in rows:
        assert r["audit_verdict"] in ("VERIFIED", "MISMATCH", "UNVERIFIABLE")
        assert len(r["exact_reason"]) > 10
        assert r["licensing_status"] != "UNKNOWN"


def test_conflicting_dbms_chunk_001_detected():
    """Verify that DBMS-03, DBMS-04, DBMS-05 are audited and flagged for conflicting chunk/page reuse."""
    csv_path = GATE_DIR / "source_verification_36_items.csv"
    with open(csv_path, encoding="utf-8") as f:
        rows = {r["item_id"]: r for r in csv.DictReader(f)}

    for it_id in ("DBMS-03", "DBMS-04", "DBMS-05"):
        item = rows[it_id]
        assert item["audit_verdict"] == "MISMATCH"
        assert item["claimed_source_doc_id"] == "doc_fundamentals_of_database_system_7e"
        assert item["claimed_chunk_id"] == "chunk_001"
        assert "Conflicting page/topic reuse" in item["exact_reason"]


def test_corrected_annotation_pool_preserves_empty_human_judgments():
    """Verify that multidomain_human_annotation_pool_corrected.csv has zero fabricated human judgments."""
    corr_csv = GATE_DIR / "human_annotation_package" / "multidomain_human_annotation_pool_corrected.csv"
    assert corr_csv.exists()

    with open(corr_csv, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 36
    for r in rows:
        assert r["human_concept_validity_a"] == ""
        assert r["human_concept_validity_b"] == ""
        assert r["human_relation_type"] == ""
        assert r["human_prereq_direction"] == ""
        assert r["human_evidence_support_0_1_2"] == ""
        assert r["human_source_verified_0_1"] == ""


def test_overgeneration_audit_csv_exists_and_identifies_failure_modes():
    """Verify overgeneration_and_cycle_analysis.csv exists and flags book index cross product."""
    csv_path = GATE_DIR / "overgeneration_and_cycle_analysis.csv"
    assert csv_path.exists()

    with open(csv_path, encoding="utf-8") as f:
        rows = {r["Doc ID"]: r for r in csv.DictReader(f)}

    # Check Data Science Index
    ds_index = rows.get("data_science_2019/Index_2019_Data-Science.pdf")
    assert ds_index is not None
    assert int(ds_index["Uses Edges"]) == 14894
    assert "BOOK_INDEX_CROSS_PRODUCT" in ds_index["Primary Failure Pattern"]

    # Check Hu2021 LoRA
    lora = rows.get("papers/Hu2021_LoRA.pdf")
    assert lora is not None
    assert int(lora["Extracted Edges Total"]) == 2427
    assert int(lora["Prereq Cycles (k>=2)"]) > 0, "LoRA has multi-hop cycles"


def test_evaluation_split_audit_classifies_toc_as_within_document():
    """Verify evaluation_split_audit.csv classifies TOC as WITHIN_DOCUMENT_CHUNK_SPLIT."""
    csv_path = GATE_DIR / "evaluation_split_audit.csv"
    assert csv_path.exists()

    with open(csv_path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    toc_rows = [r for r in rows if r["Domain Code"] == "TOC"]
    assert len(toc_rows) == 2
    for r in toc_rows:
        assert r["Split Type"] == "WITHIN_DOCUMENT_CHUNK_SPLIT"
        assert "NON_DISJOINT" in r["Split Rigor"]


def test_semantic_argument_direction_audit():
    """Verify audit_semantic_direction detects natural vs inverted relationships."""
    # Natural PART_OF: Leaf Node is a component of B+ Tree -> from: Leaf Node, to: B+ Tree
    res_nat = audit_semantic_direction(
        from_name="Leaf Node",
        to_name="B+ Tree",
        relation_type="PART_OF",
        evidence_text="A leaf node is a component of a B+ tree index structure.",
    )
    assert res_nat["direction_valid"] is True
    assert res_nat["direction_type"] == "natural"

    # Inverted PART_OF: from: B+ Tree, to: Leaf Node
    res_inv = audit_semantic_direction(
        from_name="B+ Tree",
        to_name="Leaf Node",
        relation_type="PART_OF",
        evidence_text="A leaf node is a component of a B+ tree index structure.",
    )
    assert res_inv["direction_valid"] is False
    assert res_inv["direction_type"] == "inverted"

    # Natural USES: Transformer uses Multi-Head Attention
    res_uses_nat = audit_semantic_direction(
        from_name="Transformer",
        to_name="Multi-Head Attention",
        relation_type="USES",
        evidence_text="The Transformer model utilizes multi-head attention to draw global dependencies.",
    )
    assert res_uses_nat["direction_valid"] is True
    assert res_uses_nat["direction_type"] == "natural"
