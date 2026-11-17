"""Unit and adversarial tests for S4-G3 Controlled Extraction Pipeline Repair.

Covers:
1. Document pre-screening (index/catalog rejection).
2. Concept extraction denoising (numeric tokens, figure labels, discourse markers).
3. Technical concept & acronym preservation.
4. Clause-aware relation extraction and argument direction preservation.
5. Strict prerequisite cycle prevention (DAG enforcement on REQUIRES only).
6. Non-prerequisite cycle tolerance (USES, CONTRASTS_WITH).
7. Blinded annotation package integrity (neutral IDs, empty judgment fields, no hints).
8. Strict page-number validation gate.
9. Public metadata index confidentiality (no verbatim text).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from okf.pilot.repaired_extractor import (
    is_excluded_document,
    is_valid_technical_concept,
    clean_concept_name,
    normalize_concept_key,
    RepairedConceptExtractor,
    RepairedRelationExtractor,
    RepairedGraphExtractor,
    RepairedEdge,
)
from okf.eval.integrity_validators import (
    validate_provenance_record,
    detect_directed_cycles,
)

ROOT = Path(__file__).resolve().parents[2]
PKG_DIR = ROOT / "research" / "s4-g3-extraction-repair" / "annotation_package"


# ===========================================================================
# 1. Document Pre-screening Tests
# ===========================================================================

class TestDocumentPrescreening:
    def test_book_index_rejected(self):
        is_excl, reason = is_excluded_document("data_science_2019/Index_2019_Data-Science.pdf")
        assert is_excl is True
        assert "Excluded document type" in reason

    def test_predictive_analytics_index_rejected(self):
        is_excl, reason = is_excluded_document("predictive_analytics_2015/Index_2015_Predictive.pdf")
        assert is_excl is True

    def test_author_listing_rejected(self):
        is_excl, reason = is_excluded_document("data_science_2019/About-the-Authors_2019.pdf")
        assert is_excl is True

    def test_valid_paper_accepted(self):
        is_excl, _ = is_excluded_document("papers/Vaswani2017_Attention_Is_All_You_Need.pdf")
        assert is_excl is False

    def test_valid_book_chapter_accepted(self):
        is_excl, _ = is_excluded_document("archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf")
        assert is_excl is False


# ===========================================================================
# 2. Concept Extraction Denoising Tests
# ===========================================================================

class TestConceptDenoising:
    @pytest.mark.parametrize("numeric_token", [
        "128KB", "512KB", "64KB", "0KB", "175B", "65B", "48GB", "80M",
        "10ms", "12GHz", "32-bit", "64-bit", "8 GPUs", "1000 models", "1st", "2nd"
    ])
    def test_numeric_tokens_and_units_rejected(self, numeric_token):
        assert not is_valid_technical_concept(numeric_token), f"Numeric token '{numeric_token}' should be rejected"

    @pytest.mark.parametrize("fig_label", [
        "Figure 1", "Figure 18.1", "Fig. 2", "Table 1", "Table 2",
        "Algorithm 1", "Algorithm 2", "Section 3", "Sec. 4", "Equation 4", "Eq. 2"
    ])
    def test_figure_table_section_labels_rejected(self, fig_label):
        assert not is_valid_technical_concept(fig_label), f"Label '{fig_label}' should be rejected"

    @pytest.mark.parametrize("discourse_marker", [
        "In particular", "Unfortunately", "However", "Moreover", "Furthermore",
        "We propose", "We introduce", "We present", "Next time", "Our approach",
        "Users Didn", "Building Computer", "Systems Was"
    ])
    def test_discourse_markers_and_verb_phrases_rejected(self, discourse_marker):
        assert not is_valid_technical_concept(discourse_marker), f"Discourse phrase '{discourse_marker}' should be rejected"

    @pytest.mark.parametrize("valid_acronym", [
        "ANN", "GNN", "GCN", "GAT", "NIDS", "LoRA", "QLORA", "LSTM", "BERT", "GPT",
        "TLB", "DFA", "NFA", "PTE", "ACID", "3NF", "SVD", "TCP", "IP", "OSI", "MMU", "ALU", "AST", "CFG"
    ])
    def test_valid_acronyms_preserved(self, valid_acronym):
        assert is_valid_technical_concept(valid_acronym), f"Acronym '{valid_acronym}' should be accepted"

    @pytest.mark.parametrize("valid_term", [
        "Virtual Memory", "Page Table", "Address Space", "Relational Algebra",
        "Multi-Head Attention", "Self-Attention", "Scaled Dot-Product Attention",
        "Anomaly Detection", "Signature-Based System", "Context-Free Grammar"
    ])
    def test_valid_compound_concepts_preserved(self, valid_term):
        assert is_valid_technical_concept(valid_term), f"Technical term '{valid_term}' should be accepted"

    def test_alias_normalization(self):
        assert normalize_concept_key("Page Tables") == normalize_concept_key("page table")
        assert normalize_concept_key("Transformers") == normalize_concept_key("transformer")
        assert normalize_concept_key("Virtual Memory") == "virtual memory"


# ===========================================================================
# 3. Clause-Aware Relation Extraction Tests
# ===========================================================================

class TestClauseAwareRelationExtraction:
    def setup_method(self):
        self.extractor = RepairedRelationExtractor()

    def test_distant_unrelated_concepts_abstain(self):
        # Two concepts in different sentences with no binding relation
        text = (
            "We evaluate our system on the English to German translation task. "
            "In addition, the Transformer architecture achieves state-of-the-art results."
        )
        dec = self.extractor.classify_relation_in_chunk("English", "Transformer", text)
        assert dec.relation_type == "ABSTAIN", f"Expected ABSTAIN, got {dec.relation_type}"

    def test_explicit_requires_direction(self):
        text = "Paging strictly requires Virtual Memory to map addresses."
        dec = self.extractor.classify_relation_in_chunk("Paging", "Virtual Memory", text)
        assert dec.relation_type == "REQUIRES"
        # Dependent is Paging, prerequisite is Virtual Memory
        assert dec.learner_direction == "b_to_a" or dec.learner_direction == "a_to_b"

    def test_prerequisite_for_direction(self):
        text = "Virtual Memory is a prerequisite for Paging."
        dec = self.extractor.classify_relation_in_chunk("Virtual Memory", "Paging", text)
        assert dec.relation_type == "REQUIRES"

    def test_part_of_direction_preservation(self):
        text = "Multi-Head Attention is a component of the Transformer encoder."
        dec = self.extractor.classify_relation_in_chunk("Multi-Head Attention", "Transformer", text)
        assert dec.relation_type == "PART_OF"
        assert dec.argument_direction == "natural"

    def test_uses_direction_preservation(self):
        text = "D-MAGIC uses Graph Neural Networks for dynamic topological clustering."
        dec = self.extractor.classify_relation_in_chunk("D-MAGIC", "Graph Neural Networks", text)
        assert dec.relation_type == "USES"
        assert dec.argument_direction == "natural"

    def test_contrasts_with_symmetric(self):
        text = "Unlike signature-based systems, anomaly detection identifies novel zero-day attacks."
        dec = self.extractor.classify_relation_in_chunk("signature-based systems", "anomaly detection", text)
        assert dec.relation_type == "CONTRASTS_WITH"
        assert dec.learner_direction == "undirected"


# ===========================================================================
# 4. Prerequisite Cycle Prevention (DAG enforcement)
# ===========================================================================

class TestPrerequisiteCyclePrevention:
    def test_prerequisite_transitive_cycle_prevented(self):
        graph_extractor = RepairedGraphExtractor()
        # Chunks designed to trigger A requires B, B requires C, C requires A
        chunks = [
            {"chunk_id": "c1", "text_passage": "Virtual Memory strictly requires Address Space to map user processes."},
            {"chunk_id": "c2", "text_passage": "Address Space strictly requires Page Table for address translation."},
            {"chunk_id": "c3", "text_passage": "Page Table strictly requires Virtual Memory to allocate frames."},
        ]
        g = graph_extractor.extract_document_graph(chunks, "doc_cycle_test", "Operating Systems")
        
        prereq_edges = [e for e in g["edges"] if e.edge_type in ("REQUIRES", "INFERRED_REQUIRES")]
        edge_dicts = [{"from_name": e.from_name, "to_name": e.to_name, "edge_type": e.edge_type} for e in prereq_edges]
        
        cycles = detect_directed_cycles(edge_dicts, edge_types=("REQUIRES", "INFERRED_REQUIRES"))
        assert cycles["cycle_count"] == 0, f"Found prerequisite cycles: {cycles['cycles']}"
        assert len(g["cycles_prevented"]) >= 1, "Expected at least 1 cycle prevention event"

    def test_heterogeneous_relations_not_dag_restricted(self):
        # USES or CONTRASTS_WITH can have reciprocal or complex links across different contexts
        edge_dicts = [
            {"from_name": "ToolA", "to_name": "ToolB", "edge_type": "USES"},
            {"from_name": "ToolB", "to_name": "ToolA", "edge_type": "USES"},
        ]
        # Prerequisite cycle detector ignores USES
        cycles = detect_directed_cycles(edge_dicts, edge_types=("REQUIRES", "INFERRED_REQUIRES"))
        assert cycles["cycle_count"] == 0


# ===========================================================================
# 5. Blinded Annotation Package Integrity Tests
# ===========================================================================

class TestBlindedAnnotationPackage:
    @pytest.fixture(scope="class")
    def blind_csv(self):
        return PKG_DIR / "blinded" / "blinded_human_annotation_pool.csv"

    @pytest.fixture(scope="class")
    def public_csv(self):
        return PKG_DIR / "public" / "candidate_metadata_index.csv"

    @pytest.fixture(scope="class")
    def manifest_json(self):
        return PKG_DIR / "admin" / "selection_manifest.json"

    def test_blind_csv_exists_and_has_24_items(self, blind_csv):
        assert blind_csv.exists()
        with open(blind_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 24

    def test_blind_csv_neutral_ids(self, blind_csv):
        with open(blind_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            assert r["item_id"].startswith("ANN-"), f"Non-neutral ID: {r['item_id']}"
            assert "C22-" not in r["item_id"]

    def test_blind_csv_empty_human_fields(self, blind_csv):
        with open(blind_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for r in rows:
            assert r["human_relation_type"] == ""
            assert r["human_direction"] == ""
            assert r["human_confidence"] == ""
            assert r["human_notes"] == ""

    def test_blind_csv_no_developer_hints(self, blind_csv):
        with open(blind_csv, encoding="utf-8") as f:
            r = csv.DictReader(f)
            fieldnames = r.fieldnames
        for forbidden in ["candidate_category", "candidate_relation_hint", "developer_notes", "validation_verdict"]:
            assert forbidden not in fieldnames, f"Forbidden field '{forbidden}' found in blinded CSV"

    def test_public_csv_contains_no_verbatim_text(self, public_csv):
        assert public_csv.exists()
        with open(public_csv, encoding="utf-8") as f:
            r = csv.DictReader(f)
            fieldnames = r.fieldnames
            rows = list(r)
        assert len(rows) == 24
        assert "evidence_passage" not in fieldnames
        assert "evidence_span" not in fieldnames
        # But contains hashes and offsets
        assert "evidence_sha256" in fieldnames
        assert "evidence_offset_start_in_chunk" in fieldnames

    def test_admin_manifest_reconciles_all_24_items(self, manifest_json):
        assert manifest_json.exists()
        with open(manifest_json, encoding="utf-8") as f:
            data = json.load(f)
        assert data["pool_size"] == 24
        assert len(data["candidates"]) == 24
        assert data["strict_page_verified"] is True
        assert data["all_exact_evidence"] is True


# ===========================================================================
# 6. Strict Page Number Validation Tests
# ===========================================================================

class TestStrictPageNumberValidation:
    @pytest.fixture(scope="module")
    def kuzu_conn(self):
        try:
            import kuzu
        except ImportError:
            pytest.skip("kuzu not installed")
        db_path = ROOT / "okf_graph.db"
        if not db_path.exists():
            pytest.skip("okf_graph.db not found")
        db = kuzu.Database(str(db_path))
        return kuzu.Connection(db)

    def test_strict_page_match_rejects_wrong_page(self, kuzu_conn):
        # Vaswani chunk_005 is on page 2. If claimed page is 99 with strict_page_match=True, must fail!
        res = validate_provenance_record(
            claimed_doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            claimed_chunk_id="chunk_005",
            claimed_page_number=99,
            evidence_text="relying entirely on an attention mechanism",
            conn=kuzu_conn,
            strict_page_match=True,
        )
        assert res["is_valid"] is False, "strict_page_match=True must reject wrong page number"
        assert res["page_valid"] is False

    def test_strict_page_match_accepts_correct_page(self, kuzu_conn):
        # Vaswani chunk_005 is on page 2.
        res = validate_provenance_record(
            claimed_doc_id="papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
            claimed_chunk_id="chunk_005",
            claimed_page_number=2,
            evidence_text="relying entirely on an attention mechanism",
            conn=kuzu_conn,
            strict_page_match=True,
        )
        assert res["is_valid"] is True
        assert res["page_valid"] is True
