"""S4-G2.2 — Adversarial and regression tests for hardened integrity validators.

Tests Phase A (hardened provenance validator) and Phase B (corrected cycle terminology).

Adversarial scenarios tested:
- Wrong chunk ID on a real document
- Wrong page number on a real chunk
- Near-matching passage (not verbatim)
- Absent document
- Fabricated / hallucinated evidence quote
- Punctuation-only evidence
- Empty evidence
- claimed_chunk_id not null-substituted when lookup fails
- Multiple-chunk documents with page number conflicts
- Dense overlapping cycles (Phase B regression)
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from okf.eval.integrity_validators import (
    _classify_evidence_match,
    _normalize_text,
    chunk_fingerprint,
    detect_directed_cycles,
    validate_provenance_record,
)


# ---------------------------------------------------------------------------
# Shared Kùzu connection fixture
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def kuzu_conn():
    """Open a read-only Kùzu connection to okf_graph.db."""
    try:
        import kuzu
    except ImportError:
        pytest.skip("kuzu not installed")

    db_path = Path(__file__).resolve().parents[2] / "okf_graph.db"
    if not db_path.exists():
        pytest.skip(f"okf_graph.db not found at {db_path}")

    db = kuzu.Database(str(db_path))
    return kuzu.Connection(db)


# ---------------------------------------------------------------------------
# Phase A — _normalize_text
# ---------------------------------------------------------------------------

class TestNormalizeText:
    def test_collapses_whitespace(self):
        assert _normalize_text("hello   world") == "hello world"

    def test_empty_string_returns_empty(self):
        assert _normalize_text("") == ""

    def test_punctuation_only_returns_empty(self):
        assert _normalize_text("... --- !!!") == ""
        assert _normalize_text("   .  ") == ""

    def test_unicode_normalization(self):
        # NFC: composed form
        s = "\u00e9"   # é (precomposed)
        assert _normalize_text(s) == "\u00e9"


# ---------------------------------------------------------------------------
# Phase A — _classify_evidence_match
# ---------------------------------------------------------------------------

class TestClassifyEvidenceMatch:
    def test_exact_match(self):
        chunk = "The Transformer uses self-attention mechanisms."
        evidence = "Transformer uses self-attention"
        mtype, _ = _classify_evidence_match(evidence, chunk)
        assert mtype == "EXACT"

    def test_whitespace_normalized_match(self):
        chunk = "The   encoder maps  input to output."
        evidence = "encoder maps input to output"
        mtype, _ = _classify_evidence_match(evidence, chunk)
        assert mtype in ("EXACT", "WHITESPACE_NORMALIZED")

    def test_failed_match(self):
        chunk = "The Transformer uses self-attention mechanisms."
        evidence = "BERT uses masked language modeling for pre-training"
        mtype, _ = _classify_evidence_match(evidence, chunk)
        assert mtype == "FAILED"

    def test_approximate_match_high_jaccard(self):
        # Fabricated variant of the real text — close but not exact
        chunk = "The Transformer uses self-attention mechanisms."
        evidence = "The Transformer employs self-attention mechanisms."
        mtype, _ = _classify_evidence_match(evidence, chunk)
        assert mtype in ("APPROXIMATE", "FAILED")  # must NOT be EXACT

    def test_approximate_is_not_valid_for_admission(self):
        chunk = "QLORA reduces memory usage for finetuning large language models."
        evidence = "QLORA reduces memory usage when finetuning large models."
        mtype, _ = _classify_evidence_match(evidence, chunk)
        # Approximate is not a valid admission match
        valid = mtype in ("EXACT", "WHITESPACE_NORMALIZED")
        assert not valid or mtype == "EXACT", f"Unexpected admission for mtype={mtype}"

    def test_empty_evidence_returns_invalid(self):
        mtype, _ = _classify_evidence_match("", "Some chunk text here.")
        assert mtype == "INVALID_EVIDENCE"

    def test_punctuation_only_returns_invalid(self):
        mtype, _ = _classify_evidence_match("... --- !!!", "Some chunk text.")
        assert mtype == "INVALID_EVIDENCE"


# ---------------------------------------------------------------------------
# Phase A — validate_provenance_record (adversarial)
# ---------------------------------------------------------------------------

class TestValidateProvenanceRecordAdversarial:

    # ── Absent document ──────────────────────────────────────────────────────
    def test_absent_document_returns_doc_not_found(self, kuzu_conn):
        result = validate_provenance_record(
            claimed_doc_id="papers/DoesNotExist_2099_FakeTitle.pdf",
            claimed_chunk_id="chunk_001",
            claimed_page_number=1,
            evidence_text="Some text that does not matter.",
            conn=kuzu_conn,
        )
        assert result["is_valid"] is False
        assert result["doc_exists"] is False
        assert result["chunk_id_match"] is False
        assert result["actual_chunk_id"] is None
        assert any("L1" in f for f in result["failure_layers"])

    # ── Wrong chunk ID on real document ──────────────────────────────────────
    def test_wrong_chunk_id_on_real_document(self, kuzu_conn):
        result = validate_provenance_record(
            claimed_doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            claimed_chunk_id="chunk_FAKE_999",
            claimed_page_number=1,
            evidence_text="The Transformer uses self-attention.",
            conn=kuzu_conn,
        )
        assert result["is_valid"] is False
        assert result["doc_exists"] is True           # document exists
        assert result["chunk_id_match"] is False      # chunk does not
        # CRITICAL: actual_chunk_id must be None, not the claimed ID
        assert result["actual_chunk_id"] is None, (
            "actual_chunk_id must be None when chunk lookup fails; "
            "must NOT substitute the claimed chunk_id as though verified"
        )
        assert any("L2" in f for f in result["failure_layers"])

    # ── Wrong page number on real chunk ──────────────────────────────────────
    def test_wrong_page_number_flagged_but_does_not_block(self, kuzu_conn):
        # chunk_005 of Vaswani is on page 2 — claim page 99
        result = validate_provenance_record(
            claimed_doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            claimed_chunk_id="chunk_005",
            claimed_page_number=99,
            evidence_text=(
                "relying entirely on an attention mechanism"
            ),
            conn=kuzu_conn,
        )
        # Page mismatch: should be flagged
        assert result["page_number_match"] is False
        assert result["page_valid"] is False
        assert any("L3" in f for f in result["failure_layers"])
        # But if evidence matches, is_valid can still be True (L3 is advisory)
        # (evidence_match_valid drives is_valid)
        # We don't assert is_valid here — just that L3 is flagged

    # ── Fabricated / hallucinated evidence quote ─────────────────────────────
    def test_fabricated_evidence_fails(self, kuzu_conn):
        result = validate_provenance_record(
            claimed_doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            claimed_chunk_id="chunk_005",
            claimed_page_number=2,
            evidence_text=(
                "The Transformer model was invented in 2017 by Google Brain "
                "and achieves perfect accuracy on all NLP benchmarks."
            ),
            conn=kuzu_conn,
        )
        assert result["is_valid"] is False
        assert result["evidence_match_valid"] is False
        assert result["evidence_match_type"] in ("FAILED", "APPROXIMATE")
        assert any("L4" in f for f in result["failure_layers"])

    # ── Near-matching / paraphrased passage ──────────────────────────────────
    def test_paraphrased_passage_is_not_exact(self, kuzu_conn):
        # Paraphrase of Vaswani chunk_005 — not verbatim
        result = validate_provenance_record(
            claimed_doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            claimed_chunk_id="chunk_005",
            claimed_page_number=2,
            evidence_text=(
                "The Transformer is a novel model architecture that uses only "
                "attention mechanisms and not recurrence."
            ),
            conn=kuzu_conn,
        )
        # Is_valid requires EXACT or WHITESPACE_NORMALIZED
        assert result["evidence_match_type"] not in ("EXACT", "WHITESPACE_NORMALIZED"), (
            "Paraphrased passage must not pass as EXACT or WHITESPACE_NORMALIZED"
        )
        assert result["evidence_match_valid"] is False
        assert result["is_valid"] is False

    # ── Empty evidence ───────────────────────────────────────────────────────
    def test_empty_evidence_fails_L4(self, kuzu_conn):
        result = validate_provenance_record(
            claimed_doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            claimed_chunk_id="chunk_005",
            claimed_page_number=2,
            evidence_text="",
            conn=kuzu_conn,
        )
        assert result["is_valid"] is False
        assert result["evidence_match_type"] == "INVALID_EVIDENCE"
        assert any("L4" in f for f in result["failure_layers"])

    # ── Punctuation-only evidence ────────────────────────────────────────────
    def test_punctuation_only_evidence_fails(self, kuzu_conn):
        result = validate_provenance_record(
            claimed_doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            claimed_chunk_id="chunk_005",
            claimed_page_number=2,
            evidence_text="... --- !!!",
            conn=kuzu_conn,
        )
        assert result["is_valid"] is False
        assert result["evidence_match_type"] == "INVALID_EVIDENCE"

    # ── Exact verbatim match passes ──────────────────────────────────────────
    def test_verbatim_evidence_passes(self, kuzu_conn):
        # Exact substring from Vaswani chunk_005
        result = validate_provenance_record(
            claimed_doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            claimed_chunk_id="chunk_005",
            claimed_page_number=2,
            evidence_text="relying entirely on an attention mechanism",
            conn=kuzu_conn,
        )
        assert result["is_valid"] is True
        assert result["doc_exists"] is True
        assert result["chunk_id_match"] is True
        assert result["actual_chunk_id"] == "chunk_005"
        assert result["evidence_match_type"] == "EXACT"
        assert result["evidence_match_valid"] is True

    # ── DBMS multi-page conflict: chunk_001 claimed with wrong page ──────────
    def test_dbms_chunk_001_nonexistent_returns_null_actual(self, kuzu_conn):
        """Reproduce the S4-G2 DBMS-03/04/05 failure.

        'doc_fundamentals_of_database_system_7e::chunk_001' was claimed for
        three different pages. The actual chunk in DB is
        'doc_fundamentals_of_database_system_7e_p145_1'.
        Claiming 'chunk_001' must NOT return that chunk as actual_chunk_id.
        """
        result = validate_provenance_record(
            claimed_doc_id="doc_fundamentals_of_database_system_7e",
            claimed_chunk_id="chunk_001",
            claimed_page_number=24,
            evidence_text="B+ Tree Index",
            conn=kuzu_conn,
        )
        assert result["doc_exists"] is True
        assert result["chunk_id_match"] is False
        assert result["actual_chunk_id"] is None, (
            "Must not substitute the actual DB chunk when the claimed chunk_id does not exist"
        )

    # ── Semantic support and redistribution are always NOT_MEASURED / UNKNOWN ─
    def test_semantic_support_always_not_measured(self, kuzu_conn):
        result = validate_provenance_record(
            claimed_doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            claimed_chunk_id="chunk_005",
            claimed_page_number=2,
            evidence_text="relying entirely on an attention mechanism",
            conn=kuzu_conn,
        )
        assert result["semantic_support"] == "NOT_MEASURED"
        assert result["redistribution_permitted"] == "UNKNOWN"

    # ── Empty doc_id handled at L0 ───────────────────────────────────────────
    def test_empty_doc_id_fails_L0(self, kuzu_conn):
        result = validate_provenance_record(
            claimed_doc_id="",
            claimed_chunk_id="chunk_001",
            claimed_page_number=1,
            evidence_text="Some evidence",
            conn=kuzu_conn,
        )
        assert result["is_valid"] is False
        assert any("L0" in f for f in result["failure_layers"])


# ---------------------------------------------------------------------------
# Phase B — detect_directed_cycles (corrected terminology)
# ---------------------------------------------------------------------------

class TestDetectDirectedCycles:

    # ── Basic DAG has no cycles ───────────────────────────────────────────────
    def test_dag_has_no_cycles(self):
        edges = [
            {"from_name": "A", "to_name": "B", "edge_type": "REQUIRES"},
            {"from_name": "B", "to_name": "C", "edge_type": "REQUIRES"},
        ]
        result = detect_directed_cycles(edges)
        assert result["has_cycles"] is False
        assert result["cycle_count"] == 0

    # ── Simple 2-cycle detected ───────────────────────────────────────────────
    def test_simple_2_cycle(self):
        edges = [
            {"from_name": "A", "to_name": "B", "edge_type": "REQUIRES"},
            {"from_name": "B", "to_name": "A", "edge_type": "REQUIRES"},
        ]
        result = detect_directed_cycles(edges)
        assert result["has_cycles"] is True
        assert result["cycle_count"] >= 1

    # ── Length-3 cycle detected ───────────────────────────────────────────────
    def test_length_3_cycle(self):
        edges = [
            {"from_name": "X", "to_name": "Y", "edge_type": "REQUIRES"},
            {"from_name": "Y", "to_name": "Z", "edge_type": "REQUIRES"},
            {"from_name": "Z", "to_name": "X", "edge_type": "REQUIRES"},
        ]
        result = detect_directed_cycles(edges)
        assert result["has_cycles"] is True
        assert result["cycle_count"] >= 1
        assert any(len(c) - 1 == 3 for c in result["cycles"])

    # ── Overlapping cycles — count is representative, not necessarily complete ─
    def test_overlapping_cycles_representative(self):
        """Graph with two overlapping triangles sharing an edge.

        A→B→C→A and A→B→D→A.
        DFS-back-edge may find 1 or 2 depending on traversal order.
        has_cycles must be True; cycle_count >= 1.
        The methodological note must state limitation.
        """
        edges = [
            {"from_name": "A", "to_name": "B", "edge_type": "REQUIRES"},
            {"from_name": "B", "to_name": "C", "edge_type": "REQUIRES"},
            {"from_name": "C", "to_name": "A", "edge_type": "REQUIRES"},
            {"from_name": "B", "to_name": "D", "edge_type": "REQUIRES"},
            {"from_name": "D", "to_name": "A", "edge_type": "REQUIRES"},
        ]
        result = detect_directed_cycles(edges)
        assert result["has_cycles"] is True
        assert result["cycle_count"] >= 1
        # Methodological note must be present
        assert "methodological_note" in result
        assert "elementary" in result["methodological_note"].lower()

    # ── Method field present and descriptive ──────────────────────────────────
    def test_method_field_documented(self):
        edges = [{"from_name": "A", "to_name": "B", "edge_type": "REQUIRES"}]
        result = detect_directed_cycles(edges)
        assert "method" in result
        assert len(result["method"]) > 10

    # ── Edge type filtering respected ─────────────────────────────────────────
    def test_edge_type_filter_excludes_non_matching(self):
        edges = [
            {"from_name": "A", "to_name": "B", "edge_type": "RELATED"},
            {"from_name": "B", "to_name": "A", "edge_type": "RELATED"},
        ]
        # Filter only REQUIRES — RELATED edges should not be counted
        result = detect_directed_cycles(edges, edge_types=("REQUIRES",))
        assert result["has_cycles"] is False

    # ── Determinism — same input, same output ─────────────────────────────────
    def test_determinism(self):
        edges = [
            {"from_name": "M", "to_name": "N", "edge_type": "REQUIRES"},
            {"from_name": "N", "to_name": "O", "edge_type": "REQUIRES"},
            {"from_name": "O", "to_name": "M", "edge_type": "REQUIRES"},
        ]
        r1 = detect_directed_cycles(edges)
        r2 = detect_directed_cycles(edges)
        assert r1["cycle_count"] == r2["cycle_count"]
        assert r1["has_cycles"] == r2["has_cycles"]

    # ── nodes_in_cycles correctly identifies participants ─────────────────────
    def test_nodes_in_cycles_identified(self):
        edges = [
            {"from_name": "Alpha", "to_name": "Beta", "edge_type": "REQUIRES"},
            {"from_name": "Beta", "to_name": "Alpha", "edge_type": "REQUIRES"},
            {"from_name": "Gamma", "to_name": "Delta", "edge_type": "REQUIRES"},
        ]
        result = detect_directed_cycles(edges)
        nodes = result["nodes_in_cycles"]
        assert "alpha" in nodes
        assert "beta" in nodes
        assert "gamma" not in nodes
        assert "delta" not in nodes

    # ── Self-loop does NOT form a cycle (u != v guard) ────────────────────────
    def test_self_loop_not_a_cycle(self):
        edges = [{"from_name": "A", "to_name": "A", "edge_type": "REQUIRES"}]
        result = detect_directed_cycles(edges)
        assert result["has_cycles"] is False


# ---------------------------------------------------------------------------
# Phase A — chunk_fingerprint
# ---------------------------------------------------------------------------

class TestChunkFingerprint:
    def test_fingerprint_is_16_hex_chars(self):
        fp = chunk_fingerprint("some chunk text")
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)

    def test_fingerprint_is_deterministic(self):
        fp1 = chunk_fingerprint("hello world")
        fp2 = chunk_fingerprint("hello world")
        assert fp1 == fp2

    def test_different_text_different_fingerprint(self):
        fp1 = chunk_fingerprint("text one")
        fp2 = chunk_fingerprint("text two")
        assert fp1 != fp2


# ---------------------------------------------------------------------------
# Phase C — annotation candidate pool integration test
# ---------------------------------------------------------------------------

class TestAnnotationCandidatePool:
    """Integration test: verify the generated CSV exists, is non-empty,
    and all items have valid evidence_match_type."""

    @pytest.fixture(scope="class")
    def csv_path(self):
        p = (
            Path(__file__).resolve().parents[2]
            / "research/s4-g2-2-corpus-locked-annotation/annotation_candidates"
            / "annotation_candidates_verified.csv"
        )
        return p

    def test_candidate_csv_exists(self, csv_path):
        assert csv_path.exists(), f"Candidate CSV not found: {csv_path}"

    def test_candidate_count_in_range(self, csv_path):
        import csv as csv_mod

        if not csv_path.exists():
            pytest.skip("CSV not generated")
        with open(csv_path, encoding="utf-8") as f:
            rows = list(csv_mod.DictReader(f))
        assert 12 <= len(rows) <= 24, (
            f"Expected 12-24 candidates, got {len(rows)}"
        )

    def test_all_candidates_have_exact_evidence_match(self, csv_path):
        import csv as csv_mod

        if not csv_path.exists():
            pytest.skip("CSV not generated")
        with open(csv_path, encoding="utf-8") as f:
            rows = list(csv_mod.DictReader(f))
        for row in rows:
            assert row["evidence_match_type"] in (
                "EXACT",
                "WHITESPACE_NORMALIZED",
            ), (
                f"Item {row.get('item_id')} has match_type={row['evidence_match_type']!r} — "
                "must be EXACT or WHITESPACE_NORMALIZED for admission"
            )

    def test_all_candidates_unlabeled(self, csv_path):
        import csv as csv_mod

        if not csv_path.exists():
            pytest.skip("CSV not generated")
        with open(csv_path, encoding="utf-8") as f:
            rows = list(csv_mod.DictReader(f))
        for row in rows:
            assert row["label_category"] == "CANDIDATE_UNLABELED", (
                f"Item {row.get('item_id')} has label_category={row['label_category']!r} — "
                "human labels must not be pre-filled"
            )
            assert row["human_relation_label"] == "", (
                f"Item {row.get('item_id')} has pre-filled human_relation_label"
            )

    def test_no_candidate_reuses_original_36_item_ids(self, csv_path):
        import csv as csv_mod

        if not csv_path.exists():
            pytest.skip("CSV not generated")
        original_ids = {f"{d}-{n:02d}" for d in
                        ["OS", "DBMS", "NET", "TOC", "STAT", "AI"]
                        for n in range(1, 7)}
        with open(csv_path, encoding="utf-8") as f:
            rows = list(csv_mod.DictReader(f))
        for row in rows:
            iid = row.get("item_id", "")
            # New IDs all start with C22-
            assert iid.startswith("C22-"), (
                f"Item ID {iid!r} does not follow C22- convention"
            )
            # Must not collide with original S4-G2 item IDs
            short_id = iid.replace("C22-", "").replace("-", "-")
            assert iid not in original_ids

    def test_candidate_pool_summary_json_exists(self):
        p = (
            Path(__file__).resolve().parents[2]
            / "research/s4-g2-2-corpus-locked-annotation/annotation_candidates"
            / "candidate_pool_summary.json"
        )
        assert p.exists()
        import json
        with open(p, encoding="utf-8") as f:
            summary = json.load(f)
        assert summary["total_candidates"] >= 12
        assert summary["human_labels_generated"] is False
        assert summary["all_verified_by_provenance_gate"] is True
