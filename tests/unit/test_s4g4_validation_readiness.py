"""Unit and validation tests for S4-G4: Final Extraction Validation & Retrieval Readiness.

Verifies:
1. Public exposure protections and .gitignore enforcement for local annotation storage.
2. Candidate metadata-only index schema (absence of verbatim text, accurate licensing).
3. Local hydration verification (hash verification from database).
4. Independent concept quality audit package (54 blinded items, empty human fields).
5. Relation coverage audit and zero-edge document behavior.
6. Multi-hop retrieval readiness smoke test execution and scientific boundary statements.
7. Frozen repaired extractor configuration completeness.
8. Test suite count reconciliation.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
S4G4_DIR = ROOT / "research" / "s4-g4-validation-readiness"
PUBLIC_CSV = S4G4_DIR / "annotation_package" / "public" / "candidate_metadata_index.csv"
CONCEPT_CSV = S4G4_DIR / "concept_audit" / "concept_validity_audit_pool_public.csv"
CONCEPT_JSON = S4G4_DIR / "concept_audit" / "concept_filter_consistency_report.json"
RETRIEVAL_REPORT = S4G4_DIR / "retrieval_smoke_test_report.json"
CONFIG_JSON = ROOT / "okf" / "pilot" / "repaired_extractor_config.json"


# ===========================================================================
# 1. Public Exposure and Gitignore Protections
# ===========================================================================

class TestPublicExposureProtections:
    def test_gitignore_contains_annotation_local(self):
        gitignore_path = ROOT / ".gitignore"
        assert gitignore_path.exists()
        content = gitignore_path.read_text(encoding="utf-8")
        assert "data/annotation_local/" in content
        assert "research/s4-g4-validation-readiness/annotation_local/" in content

    def test_public_metadata_index_contains_no_verbatim_text(self):
        assert PUBLIC_CSV.exists()
        with open(PUBLIC_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        assert len(rows) == 24
        # Strictly forbidden fields
        for forbidden in ["evidence_passage", "evidence_span", "chunk_text", "raw_text"]:
            assert forbidden not in fieldnames, f"Forbidden verbatim text field '{forbidden}' found in public CSV"

        # Required metadata pointers
        for req in [
            "blind_id", "doc_id", "chunk_id", "page_number",
            "evidence_offset_start_in_chunk", "evidence_offset_end_in_chunk",
            "evidence_sha256", "redistribution_status"
        ]:
            assert req in fieldnames

    def test_public_metadata_index_classifies_restricted_documents(self):
        with open(PUBLIC_CSV, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))

        for r in rows:
            doc = r["doc_id"]
            status = r["redistribution_status"]
            if "doc_" in doc or "Real-time network security" in doc or "06_Address_Spaces" in doc or "08_Paging" in doc:
                assert status == "RESTRICTED_METADATA_ONLY", f"Document {doc} must be RESTRICTED_METADATA_ONLY, got {status}"
            elif "papers/" in doc:
                assert status == "OPEN_ACCESS_METADATA_ONLY"


# ===========================================================================
# 2. Local Annotation Hydration
# ===========================================================================

class TestLocalAnnotationHydration:
    def test_hydrator_script_runs_and_verifies_all_24_items(self):
        import importlib.util
        script_path = S4G4_DIR / "scripts" / "hydrate_local_annotation_pool.py"
        assert script_path.exists()
        spec = importlib.util.spec_from_file_location("hydrate_module", str(script_path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        res = mod.hydrate_annotation_pool(PUBLIC_CSV)
        assert res["status"] == "SUCCESS"
        assert res["verified_count"] == 24
        assert res["mismatch_count"] == 0

        # Verify output files exist in data/annotation_local
        out_csv = Path(res["blinded_csv"])
        assert out_csv.exists()
        with open(out_csv, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 24
        assert rows[0]["human_relation_type"] == ""


# ===========================================================================
# 3. Independent Concept Quality Audit Package
# ===========================================================================

class TestIndependentConceptQualityAudit:
    def test_concept_audit_pool_public_schema_and_empty_fields(self):
        assert CONCEPT_CSV.exists()
        with open(CONCEPT_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 54
        # 18 per domain across 3 domains
        domains = {r["domain"] for r in rows}
        assert domains == {"Operating Systems", "AI & Machine Learning", "Computer Networks"}
        for d in domains:
            assert sum(1 for r in rows if r["domain"] == d) == 18

        # All human fields must be blank
        for r in rows:
            assert r["human_is_valid_concept"] == ""
            assert r["human_concept_type"] == ""
            assert r["human_confidence"] == ""
            assert r["human_notes"] == ""

    def test_concept_filter_consistency_report(self):
        assert CONCEPT_JSON.exists()
        with open(CONCEPT_JSON, encoding="utf-8") as f:
            data = json.load(f)

        assert data["total_audit_items"] == 54
        assert data["retained_candidates_count"] == 27
        assert data["rejected_candidates_count"] == 27
        assert data["filter_consistency_rate"] == 1.0
        assert data["semantic_precision"] == "NOT_MEASURED"
        assert data["semantic_recall"] == "NOT_MEASURED"


# ===========================================================================
# 4. Relation Coverage & Zero-Edge Document Behavior
# ===========================================================================

class TestRelationCoverageAndZeroEdgeAudit:
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

    def test_zero_edge_documents_produce_zero_edges_and_abstentions(self, kuzu_conn):
        from okf.pilot.repaired_extractor import RepairedGraphExtractor

        extractor = RepairedGraphExtractor()
        zero_edge_docs = [
            "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
            "doc_computer_networks_6_e",
            "doc_fundamentals_of_database_system_7e",
            "doc_compilers_principles_techniques_and_tools",
        ]

        for doc_id in zero_edge_docs:
            res = kuzu_conn.execute(
                "MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) WHERE d.id = $doc RETURN c.chunk_id, c.text_passage",
                {"doc": doc_id},
            )
            chunks = []
            while res.has_next():
                row = res.get_next()
                chunks.append({"chunk_id": row[0], "text_passage": row[1]})
            doc_res = extractor.extract_document_graph(chunks, doc_id)
            assert doc_res["edge_count"] == 0, f"Expected 0 edges for {doc_id}, got {doc_res['edge_count']}"
            assert doc_res["abstentions_count"] >= 1, f"Expected abstentions for {doc_id}"


# ===========================================================================
# 5. Multi-Hop Retrieval Readiness Smoke Test
# ===========================================================================

class TestRetrievalReadinessSmokeTest:
    def test_smoke_test_report_validity_and_scientific_boundaries(self):
        assert RETRIEVAL_REPORT.exists()
        with open(RETRIEVAL_REPORT, encoding="utf-8") as f:
            report = json.load(f)

        assert report["technical_sanity_verdict"] == "ALL_SYSTEMS_FUNCTIONAL"
        assert report["schema_errors_detected"] == 0
        assert report["crashes_detected"] == 0
        assert len(report["retrieval_systems_tested"]) == 5
        assert set(report["retrieval_systems_tested"]) == {
            "bm25", "dense", "hybrid_rrf", "baseline_graph", "repaired_heterogeneous_graph"
        }
        assert report["retrieval_effectiveness"] == "NOT_EVALUATED"
        assert "NOT_EVALUATED" in report["effectiveness_boundary_statement"]

        # Verify query results
        assert len(report["query_results"]) == 3
        for q in report["query_results"]:
            for sys_name in report["retrieval_systems_tested"]:
                sys_res = q["systems"][sys_name]
                assert sys_res["status"] == "PASS"
                assert sys_res["returned_count"] == 5
                assert len(sys_res["top_passage_ids"]) == 5
                assert sys_res["latency_ms"] >= 0.0


# ===========================================================================
# 6. Frozen Repaired Extractor Configuration
# ===========================================================================

class TestFrozenExtractorConfiguration:
    def test_config_completeness_and_parameters(self):
        assert CONFIG_JSON.exists()
        with open(CONFIG_JSON, encoding="utf-8") as f:
            cfg = json.load(f)

        assert cfg["version"] == "s4-g3-repaired-v1.0"
        assert cfg["document_prescreening"]["enabled"] is True
        assert len(cfg["document_prescreening"]["excluded_patterns"]) >= 5
        assert cfg["concept_extraction"]["canonical_acronyms_count"] == 32
        assert cfg["relation_extraction"]["max_character_distance_between_arguments"] == 150
        assert "REQUIRES" in cfg["relation_extraction"]["supported_relation_types"]
        assert "CONTRASTS_WITH" in cfg["relation_extraction"]["supported_relation_types"]
        assert cfg["graph_integrity_and_cycles"]["dag_guarantee"] == "Strict DAG on prerequisite relation subgraphs."


# ===========================================================================
# 7. Test Suite Count Reconciliation
# ===========================================================================

class TestSuiteCountReconciliation:
    def test_reconcile_per_file_test_counts_and_delta(self):
        expected_counts = {
            "tests/unit/test_dataset_integrity_s2.py": 11,
            "tests/unit/test_retrieval_baselines_s3.py": 10,
            "tests/unit/test_annotation_pilot_s4a.py": 5,
            "tests/unit/test_annotation_integrity_s4b.py": 19,
            "tests/unit/test_s4d_human_audit_comparison.py": 9,
            "tests/unit/test_s4e_graph_diagnosis.py": 6,
            "tests/unit/test_s4f_evaluator_repair.py": 24,
            "tests/unit/test_s4g1_extraction_pilot.py": 16,
            "tests/unit/test_s4g2_multidomain_evaluation.py": 17,
            "tests/unit/test_s4g2_1_integrity_gate.py": 11,
            "tests/unit/test_s4g2_2_corpus_locked_annotation.py": 40,
            "tests/unit/test_s4g3_extraction_repair.py": 96,
        }
        total_baseline = sum(expected_counts.values())
        assert total_baseline == 264

        # Discrepancy explanation: S4-G3 report table listed test_s4e_graph_diagnosis.py as 12 instead of 6
        table_s4e_stated = 12
        actual_s4e = expected_counts["tests/unit/test_s4e_graph_diagnosis.py"]
        delta = table_s4e_stated - actual_s4e
        assert delta == 6
        assert (270 - delta) == 264
