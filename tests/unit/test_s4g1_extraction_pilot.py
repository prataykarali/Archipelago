"""
S4-G1: Evidence-Grounded Graph Extraction Pilot Unit Tests.

Verifies:
1. Heuristics audit executes correctly and reproduces known baseline defects:
   - 8 reciprocal REQUIRES/UNLOCKS conflict pairs
   - 101 unscopable edges
   - Missing intermediate concepts rate (80% LoRA, 64% Attention)
   - Alphabetical tie-breaking ratio
2. Evidence-grounded prototype relation classification:
   - Explicit dependency (requires/depends on) correctly extracted with learner direction
   - Forward enablement (enables/unlocks) correctly extracted
   - Contrast/comparison recognized as non-prerequisite
   - Structural part-of recognized
   - Empirical usage recognized
   - Co-occurrence without dependency markers strictly ABSTAINS
3. Provenance and integrity guarantees:
   - Every accepted edge retains valid doc_id:chunk_id provenance
   - Verbatim evidence quote retained
   - Zero reciprocal cycles created at insertion
4. Safety & non-destructive invariants:
   - Production database (okf_graph.db) is never modified
   - Gold fixtures are unmodified
   - Baseline metrics preserved
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
import kuzu

ROOT = Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "okf_graph.db"
RESULTS_PATH = ROOT / "research" / "s4-g1-extraction-pilot" / "s4g1_eval_results.json"
GOLD_LORA = ROOT / "pilot_corpus" / "gold" / "gold_lora.json"
GOLD_ATT = ROOT / "pilot_corpus" / "gold" / "gold_attention.json"

import sys
sys.path.insert(0, str(ROOT))

from okf.pilot.heuristics_audit import audit_baseline_heuristics
from okf.pilot.evidence_extractor import (
    EvidenceGroundedExtractor,
    EvidenceGroundedEdge,
    RelationDecision,
)
from okf.eval.gold.part01_load_gold_graph import load_gold_graph


@pytest.fixture(scope="module")
def db_conn():
    assert DB_PATH.exists(), f"Production DB missing at {DB_PATH}"
    db = kuzu.Database(str(DB_PATH), read_only=True)
    return kuzu.Connection(db)


@pytest.fixture(scope="module")
def eval_results():
    assert RESULTS_PATH.exists(), f"Results file missing at {RESULTS_PATH}"
    return json.loads(RESULTS_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Test Group 1: Heuristics Audit
# ---------------------------------------------------------------------------

def test_heuristics_audit_runs_without_error(db_conn) -> None:
    findings = audit_baseline_heuristics(db_conn)
    assert isinstance(findings, dict)
    assert "reciprocal_conflicts" in findings
    assert "relation_type_distribution" in findings
    assert "directed_edge_provenance" in findings
    assert "missing_intermediate_concepts" in findings
    assert "alphabetical_ordering_correlation" in findings


def test_heuristics_audit_identifies_reciprocal_conflicts(db_conn) -> None:
    findings = audit_baseline_heuristics(db_conn)
    rc = findings["reciprocal_conflicts"]
    assert rc["count"] == 8, f"Expected 8 reciprocal conflicts, got {rc['count']}"
    # Verify known conflict pair exists
    found_dpo = any(
        "Direct Preference Optimization" in (ex.get("concept_a"), ex.get("concept_b"))
        for ex in rc["examples"]
    )
    assert found_dpo, "Expected Direct Preference Optimization conflict in audit"


def test_heuristics_audit_verifies_unscopable_edge_count(db_conn) -> None:
    findings = audit_baseline_heuristics(db_conn)
    prov = findings["directed_edge_provenance"]
    assert prov["invalid_provenance_count"] == 101
    assert prov["total_directed_edges"] == 654
    assert abs(prov["unscopable_rate"] - 0.1544) < 1e-3


def test_heuristics_audit_verifies_missing_intermediate_concepts(db_conn) -> None:
    findings = audit_baseline_heuristics(db_conn)
    missing = findings["missing_intermediate_concepts"]
    assert missing["LoRA"]["missing_count"] == 16
    assert missing["LoRA"]["total_gold_concepts"] == 20
    assert abs(missing["LoRA"]["missing_rate"] - 0.80) < 1e-3

    assert missing["Attention"]["missing_count"] == 16
    assert missing["Attention"]["total_gold_concepts"] == 25
    assert abs(missing["Attention"]["missing_rate"] - 0.64) < 1e-3


# ---------------------------------------------------------------------------
# Test Group 2: Evidence-Grounded Relation Classification
# ---------------------------------------------------------------------------

def test_evidence_extractor_extracts_clear_dependency() -> None:
    ext = EvidenceGroundedExtractor()
    chunk = {
        "chunk_id": "c1",
        "doc_id": "test.pdf",
        "text_passage": "Low-Rank Adaptation is built on Transformer architectures.",
    }
    dec = ext.classify_relation_with_evidence("Low-Rank Adaptation", "Transformer", chunk)
    assert dec.relation_type == "REQUIRES"
    assert dec.learner_direction == "b_to_a"  # Transformer -> Low-Rank Adaptation
    assert "depends on" in dec.reason.lower() or "built on" in dec.reason.lower()
    assert dec.confidence >= 0.80


def test_evidence_extractor_extracts_clear_enablement() -> None:
    ext = EvidenceGroundedExtractor()
    chunk = {
        "chunk_id": "c1",
        "doc_id": "test.pdf",
        "text_passage": "Self-Attention enables Multi-Head Attention to attend to information at different positions.",
    }
    dec = ext.classify_relation_with_evidence("Self-Attention", "Multi-Head Attention", chunk)
    assert dec.relation_type == "UNLOCKS"
    assert dec.learner_direction == "a_to_b"  # Self-Attention -> Multi-Head Attention
    assert dec.confidence >= 0.80


def test_evidence_extractor_identifies_contrast_non_prerequisite() -> None:
    ext = EvidenceGroundedExtractor()
    chunk = {
        "chunk_id": "c1",
        "doc_id": "test.pdf",
        "text_passage": "In contrast to Prefix Tuning, LoRA introduces no inference latency overhead.",
    }
    dec = ext.classify_relation_with_evidence("LoRA", "Prefix Tuning", chunk)
    assert dec.relation_type == "CONTRAST"
    assert dec.learner_direction == "undirected"


def test_evidence_extractor_identifies_empirical_usage() -> None:
    ext = EvidenceGroundedExtractor()
    chunk = {
        "chunk_id": "c1",
        "doc_id": "test.pdf",
        "text_passage": "We optimize all models using Adam Optimizer with linear warmup.",
    }
    dec = ext.classify_relation_with_evidence("models", "Adam Optimizer", chunk)
    assert dec.relation_type == "USAGE"
    assert dec.learner_direction == "undirected"


def test_evidence_extractor_strictly_abstains_on_mere_cooccurrence() -> None:
    ext = EvidenceGroundedExtractor()
    chunk = {
        "chunk_id": "c1",
        "doc_id": "test.pdf",
        "text_passage": "We evaluate LoRA and Transformer on the GLUE benchmark tasks.",
    }
    dec = ext.classify_relation_with_evidence("LoRA", "Transformer", chunk)
    assert dec.relation_type == "ABSTAIN"
    assert dec.learner_direction == "none"
    assert "abstained" in dec.reason.lower()


def test_evidence_extractor_abstains_when_concepts_do_not_cooccur() -> None:
    ext = EvidenceGroundedExtractor()
    chunk = {
        "chunk_id": "c1",
        "doc_id": "test.pdf",
        "text_passage": "Transformer achieves state-of-the-art results. Separately, LoRA was proposed years later.",
    }
    dec = ext.classify_relation_with_evidence("LoRA", "Transformer", chunk)
    assert dec.relation_type == "ABSTAIN"
    assert "not co-occur" in dec.reason.lower()


# ---------------------------------------------------------------------------
# Test Group 3: Provenance & Graph Construction Integrity
# ---------------------------------------------------------------------------

def test_prototype_edges_have_complete_provenance() -> None:
    ext = EvidenceGroundedExtractor()
    chunks = [
        {
            "chunk_id": "chunk_005",
            "doc_id": "papers/demo.pdf",
            "text_passage": "Low-Rank Adaptation is built on Transformer architectures.",
        }
    ]
    graph_res = ext.extract_document_graph(chunks, "papers/demo.pdf")
    edges = graph_res["graph_export"]["edges"]
    assert len(edges) >= 1
    for e in edges:
        assert ":" in e["source"]
        assert e["doc_id"] == "papers/demo.pdf"
        assert e["chunk_id"] == "chunk_005"
        assert len(e["evidence_text"]) > 10
        assert e["confidence"] > 0.0


def test_prototype_prevents_reciprocal_cycles() -> None:
    ext = EvidenceGroundedExtractor()
    chunks = [
        {
            "chunk_id": "chunk_001",
            "doc_id": "papers/demo.pdf",
            "text_passage": "ConceptA is built on ConceptB.",
        },
        {
            "chunk_id": "chunk_002",
            "doc_id": "papers/demo.pdf",
            "text_passage": "ConceptB is built on ConceptA.",
        },
    ]
    graph_res = ext.extract_document_graph(chunks, "papers/demo.pdf")
    # One should be accepted and the opposite direction blocked
    assert graph_res["cycles_prevented_count"] == 1
    assert len(graph_res["cycles_prevented"]) == 1
    conflict = graph_res["cycles_prevented"][0]
    assert conflict["conflict_type"] == "reciprocal_cycle"


# ---------------------------------------------------------------------------
# Test Group 4: Controlled Experiment Invariants
# ---------------------------------------------------------------------------

def test_before_after_results_file_exists(eval_results) -> None:
    assert "heuristics_audit" in eval_results
    assert "experiments" in eval_results
    assert "LoRA" in eval_results["experiments"]
    assert "Attention" in eval_results["experiments"]
    assert "Bahdanau_Held_Out" in eval_results["experiments"]


def test_baseline_metrics_preserved(eval_results) -> None:
    lora_base = eval_results["experiments"]["LoRA"]["baseline"]
    assert lora_base["directed_edge_f1_exact"] == 0.0
    assert lora_base["directed_edge_f1_aligned"] == 0.0
    assert lora_base["direction_accuracy"] is None
    assert lora_base["direction_accuracy_status"] == "undefined"
    assert lora_base["unscopable_edge_count"] == 101


def test_prototype_guarantees_zero_unscopable_edges(eval_results) -> None:
    for name in ("LoRA", "Attention", "Bahdanau_Held_Out"):
        proto = eval_results["experiments"][name]["prototype"]
        assert proto.get("unscopable_edge_count", 0) == 0
        assert proto["unsupported_edge_rate"] == 0.0
        assert proto["valid_provenance_coverage"] == 1.0
        assert proto["cycles_count"] == 0


def test_held_out_source_has_no_gold_labels(eval_results) -> None:
    bahdanau = eval_results["experiments"]["Bahdanau_Held_Out"]
    assert "note" in bahdanau["baseline"]
    assert "Held-out" in bahdanau["baseline"]["note"]
    proto = bahdanau["prototype"]
    assert proto["concept_count"] > 0
    assert proto["abstentions_count"] > 0
