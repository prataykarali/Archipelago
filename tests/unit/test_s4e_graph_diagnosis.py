"""
S4-E Research Integrity & Graph Diagnosis Unit Tests.

Verifies:
1. S1 document-scoped evaluation reproduction (LoRA Concept F1 ~19.05%, Attention Concept F1 ~40.00%, Edge F1 0.00%)
2. Detection and root-cause classification of the 9 graph cycles (8 symmetric librarian_upload, 1 multi-paper)
3. Audit of the 157 edge provenance issues and invariant of 101 unscopable directed edges
4. Invariant of 1,334 skipped RELATED edges in the baseline evaluator
5. Source redistribution audit: local preservation of full text and tracked repository-safe sanitization
6. Identification of the vacuous direction accuracy defect (1.0 when TP=0)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOCAL_ONLY = ROOT / "artifacts" / "validation" / "local_only"
RESEARCH_S4B = ROOT / "research" / "s4-b-annotation-integrity"
RESEARCH_S4E = ROOT / "research" / "s4-e-graph-diagnosis"

import sys
sys.path.insert(0, str(ROOT))

import kuzu
from okf.eval.gold.edge_extraction import _extract_edges, _edge_matches_doc
from okf.eval.gold.part01_load_gold_graph import evaluate_pipeline
from okf.eval.structural import structural_audit
from okf.graph_db import export_graph


@pytest.fixture(scope="module")
def db_conn():
    db_path = ROOT / "okf_graph.db"
    assert db_path.exists(), f"Database missing at {db_path}"
    return kuzu.Connection(kuzu.Database(str(db_path), read_only=True))


@pytest.fixture(scope="module")
def db_export(db_conn):
    return export_graph(db_conn)


@pytest.fixture(scope="module")
def db_audit(db_conn):
    return structural_audit(db_conn)


def test_s1_document_scoped_evaluation_reproduction(db_conn) -> None:
    # 1. LoRA Document-Scoped
    lora_path = ROOT / "pilot_corpus" / "gold" / "gold_lora.json"
    lora_rep = evaluate_pipeline(db_conn, str(lora_path), doc_id="papers/Hu2021_LoRA.pdf")
    
    c_lora = lora_rep["concept_comparison"]
    e_lora = lora_rep["edge_comparison"]

    assert abs(c_lora["f1"] - 0.190476) < 1e-4, f"LoRA Concept F1 mismatch: {c_lora['f1']}"
    assert c_lora["true_positives"] == 4
    assert c_lora["false_positives"] == 18
    assert c_lora["false_negatives"] == 16

    assert e_lora["directed"]["f1"] == 0.0, f"LoRA Directed Edge F1 should be 0.0: {e_lora['directed']}"
    assert e_lora["undirected"]["f1"] == 0.0, f"LoRA Undirected Edge F1 should be 0.0: {e_lora['undirected']}"
    assert e_lora["unscopable_edges"] == 101, f"Expected 101 unscopable edges, got {e_lora['unscopable_edges']}"

    # 2. Attention Document-Scoped
    att_path = ROOT / "pilot_corpus" / "gold" / "gold_attention.json"
    att_rep = evaluate_pipeline(db_conn, str(att_path), doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf")

    c_att = att_rep["concept_comparison"]
    e_att = att_rep["edge_comparison"]

    assert abs(c_att["f1"] - 0.4000) < 1e-4, f"Attention Concept F1 mismatch: {c_att['f1']}"
    assert c_att["true_positives"] == 11
    assert c_att["false_positives"] == 19
    assert c_att["false_negatives"] == 14

    assert e_att["directed"]["f1"] == 0.0, f"Attention Directed Edge F1 should be 0.0: {e_att['directed']}"
    assert e_att["undirected"]["f1"] == 0.0, f"Attention Undirected Edge F1 should be 0.0: {e_att['undirected']}"
    assert e_att["unscopable_edges"] == 101, f"Expected 101 unscopable edges, got {e_att['unscopable_edges']}"


def test_vacuous_direction_accuracy_reproduced(db_conn) -> None:
    lora_path = ROOT / "pilot_corpus" / "gold" / "gold_lora.json"
    rep = evaluate_pipeline(db_conn, str(lora_path), doc_id="papers/Hu2021_LoRA.pdf")
    # Demonstrating the defect: returns 1.0 (100%) even though matched undirected edges is 0
    assert rep["edge_comparison"]["directed"]["true_positives"] == 0
    assert rep["edge_comparison"]["direction_accuracy"] == 1.0


def test_exactly_nine_cycles_detected_and_eight_are_librarian_upload(db_audit, db_export) -> None:
    raw_cycles = db_audit.get("cycles", [])

    # The DFS cycle detector can report the same cycle from multiple entry points.
    # Canonicalise each cycle to its minimum-rotation, deduplicate, then assert on
    # the unique set.  Raw count is 9–10 depending on traversal order (non-deterministic);
    # unique count is always 9.
    def canonical_cycle(c: list) -> tuple:
        body = c[:-1]  # strip repeated tail node
        rots = [tuple(body[i:] + body[:i]) for i in range(len(body))]
        return min(rots)

    seen: set = set()
    unique_cycles: list = []
    for cyc in raw_cycles:
        key = canonical_cycle(cyc)
        if key not in seen:
            seen.add(key)
            unique_cycles.append(cyc)

    assert len(unique_cycles) == 9, (
        f"Expected 9 unique cycles (raw={len(raw_cycles)}), got {len(unique_cycles)}"
    )

    edges_by_pair = {}
    for e in db_export["edges"]:
        pair = (e["from_id"], e["to_id"])
        edges_by_pair.setdefault(pair, []).append(e)

    len_2_count = 0
    len_6_count = 0
    librarian_upload_cycle_count = 0

    for cyc in unique_cycles:
        hop_len = len(cyc) - 1
        if hop_len == 2:
            len_2_count += 1
            # Check if source is librarian_upload
            u, v = cyc[0], cyc[1]
            matches = edges_by_pair.get((u, v), []) + edges_by_pair.get((v, u), [])
            if any(m.get("source") == "librarian_upload" for m in matches):
                librarian_upload_cycle_count += 1
        elif hop_len == 6:
            len_6_count += 1

    assert len_2_count == 8, f"Expected 8 2-node cycles, got {len_2_count}"
    assert len_6_count == 1, f"Expected 1 6-node cycle, got {len_6_count}"
    assert librarian_upload_cycle_count == 8, "All 8 2-node cycles should be from librarian_upload"


def test_edge_provenance_audit_157_issues_and_101_unscopable(db_audit) -> None:
    issues = db_audit.get("edge_provenance_issues", [])
    assert len(issues) == 157, f"Expected 157 edge provenance issues, got {len(issues)}"

    none_count = sum(1 for iss in issues if iss.get("provenance") is None)
    pearson_count = sum(1 for iss in issues if iss.get("provenance") == "pearson_batch1")
    librarian_count = sum(1 for iss in issues if iss.get("provenance") == "librarian_upload")

    assert none_count == 98, f"Expected 98 None provenance, got {none_count}"
    assert pearson_count == 30, f"Expected 30 pearson_batch1 provenance, got {pearson_count}"
    assert librarian_count == 29, f"Expected 29 librarian_upload provenance, got {librarian_count}"

    # Verify directed edges count among provenance issues equals 101
    directed_issues = sum(1 for iss in issues if iss.get("edge_type") in ("REQUIRES", "UNLOCKS"))
    assert directed_issues == 101, f"Expected 101 directed issues, got {directed_issues}"


def test_1334_related_edges_skipped_by_evaluator(db_export) -> None:
    stats = db_export["stats"]
    assert stats["related_edges"] == 1334, f"Expected 1334 RELATED edges, got {stats['related_edges']}"

    ext_stats = {}
    _extract_edges(db_export, include_related=False, stats=ext_stats)
    assert ext_stats.get("skipped_related") == 1334


def test_source_redistribution_audit_local_provenance_preservation() -> None:
    full_local = LOCAL_ONLY / "human_audit_original_full.md"
    assert full_local.exists(), f"Full local audit missing at {full_local}"

    import hashlib
    h = hashlib.sha256(full_local.read_bytes()).hexdigest()
    assert h == "655c498ad75a998f0659ee59d4f6e05581ee3615e54c09de11562837fda8c051"

    tracked_md = RESEARCH_S4B / "human_audit_original.md"
    assert tracked_md.exists()
    content = tracked_md.read_text(encoding="utf-8")

    # Ensure no large verbatim text remains in tracked markdown
    import re
    blockquotes = re.findall(r"> (.*?)(?=\n\n|\Z)", content, re.DOTALL)
    for b in blockquotes:
        assert len(b) < 600, "Tracked markdown contains unexpected large blockquote"
        assert "Verbatim passage text omitted for repository copyright compliance" in b

    # Ensure all 24 questions, candidate IDs and scores are present
    assert content.count("### Passage") == 24
    assert content.count("My relevance score") == 24
