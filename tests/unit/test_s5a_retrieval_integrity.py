"""Unit and integrity regression tests for S5-A: Retrieval Baseline Integrity.

Verifies:
1. Public source-text exposure protections (metadata-only public pool, untracked legacy files).
2. Versioned corpus manifest and index/invalid-page exclusions (713 eligible passages).
3. Pretrained dense embedding model manifest and 768-dim embedding cache.
4. Passage-ID scoping and zero cross-document collision guarantee in graph retrieval.
5. Graph anchor coverage, hop count metadata, and fallback rate tracking.
6. Hybrid RRF end-to-end latency accounting and timing distribution report.
7. Human evaluation package schema and empty judgment fields.
8. Retrieval effectiveness scientific boundary (strictly NOT_EVALUATED).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
S5A_DIR = ROOT / "research" / "s5-a-retrieval-integrity"
CORPUS_MANIFEST = S5A_DIR / "corpus" / "s5a_corpus_manifest.json"
MODEL_MANIFEST = S5A_DIR / "models" / "s5a_model_manifest.json"
TECH_REPORT = S5A_DIR / "retrieval_technical_evaluation_report.json"
TIMING_REPORT = S5A_DIR / "retrieval_timing_report.json"
CANDIDATE_POOL_CSV = S5A_DIR / "human_evaluation_package" / "retrieval_query_candidate_pool.csv"
QUERY_MANIFEST = S5A_DIR / "human_evaluation_package" / "retrieval_query_manifest.json"
PROTOCOL_MD = S5A_DIR / "human_evaluation_package" / "RETRIEVAL_ANNOTATION_PROTOCOL.md"
S4G4_CONCEPT_CSV = ROOT / "research" / "s4-g4-validation-readiness" / "concept_audit" / "concept_validity_audit_pool_public.csv"


# ===========================================================================
# 1. Source Exposure Protections
# ===========================================================================

class TestSourceExposureProtections:
    def test_s4g4_concept_audit_public_contains_no_verbatim_text(self):
        assert S4G4_CONCEPT_CSV.exists()
        with open(S4G4_CONCEPT_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames or []
        assert "context_snippet" not in fieldnames, "Verbatim context_snippet must not be in public CSV"
        assert "context_offset_start" in fieldnames
        assert "context_offset_end" in fieldnames
        assert "context_sha256" in fieldnames

    def test_s4g3_blinded_pool_untracked_on_s5a_branch(self):
        # The verbatim CSV must not exist in git-tracked files
        legacy_csv = ROOT / "research" / "s4-g3-extraction-repair" / "annotation_package" / "blinded" / "blinded_human_annotation_pool.csv"
        assert not legacy_csv.exists(), "Legacy verbatim annotation pool must not be tracked on s5-a branch"

    def test_gitignore_covers_s5a_annotation_local(self):
        gi_path = ROOT / ".gitignore"
        assert gi_path.exists()
        content = gi_path.read_text(encoding="utf-8")
        assert "research/s5-a-retrieval-integrity/annotation_local/" in content
        assert "data/annotation_local/" in content


# ===========================================================================
# 2. Versioned Corpus Manifest & Exclusions
# ===========================================================================

class TestCorpusManifestAndExclusions:
    def test_corpus_manifest_structure_and_counts(self):
        assert CORPUS_MANIFEST.exists()
        with open(CORPUS_MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)

        assert manifest["corpus_version"] == "s5a_eval_corpus_v1"
        audit = manifest["audit_and_exclusions"]
        assert audit["total_s3_passages"] == 764
        assert audit["index_only_passages_excluded"] == 50
        assert audit["invalid_page_passages_excluded"] == 1
        assert audit["total_exclusions"] == 51
        assert audit["eligible_passages_count"] == 713
        assert audit["unique_documents_count"] == 53
        assert len(audit["corpus_sha256"]) == 64


# ===========================================================================
# 3. Embedding Model Manifest & Precomputed Cache
# ===========================================================================

class TestEmbeddingModelManifest:
    def test_model_manifest_parameters(self):
        assert MODEL_MANIFEST.exists()
        with open(MODEL_MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)

        primary = manifest["primary_dense_model"]
        assert primary["model_identifier"] == "Snowflake/snowflake-arctic-embed-m-v1.5"
        assert primary["embedding_dimension"] == 768
        assert "Represent this sentence" in primary["query_prefix"]
        assert "L2 unit sphere" in primary["normalization"]

        debug = manifest["debugging_baseline"]
        assert debug["usage_role"] == "DEBUGGING_ONLY (Fast offline non-semantic baseline for CI pipelines and sanity tests)"

    def test_precomputed_embeddings_cache_validity(self):
        cache_path = ROOT / "data" / "artifacts" / "s5a_dense_embeddings_713.npy"
        if not cache_path.exists():
            from sentence_transformers import SentenceTransformer
            from archipelago.eval.retrieval_baselines import build_fixed_corpus_from_kuzu, _is_index_only_passage
            passages, _ = build_fixed_corpus_from_kuzu("okf_graph.db")
            eligible = [
                p for p in passages
                if not _is_index_only_passage(p.doc_id, p.section_title, p.text)
                and p.passage_id != "doc_data_and_computer_communications::doc_data_and_computer_communications_p612_4"
            ]
            texts = [p.text for p in eligible]
            model = SentenceTransformer("Snowflake/snowflake-arctic-embed-m-v1.5", local_files_only=True)
            emb = model.encode(texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False)
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            import numpy as np
            np.save(cache_path, emb)
        import numpy as np
        emb = np.load(cache_path)
        assert emb.shape == (713, 768)
        # Check unit normalization
        norms = np.linalg.norm(emb, axis=1)
        assert np.allclose(norms, 1.0, atol=1e-5)


# ===========================================================================
# 4. Passage-ID Mapping & Graph Retrieval Correctness
# ===========================================================================

class TestGraphPassageIdMappingAndAblation:
    @pytest.fixture(scope="class")
    def tech_report_data(self):
        assert TECH_REPORT.exists()
        with open(TECH_REPORT, encoding="utf-8") as f:
            return json.load(f)

    def test_zero_cross_document_passage_id_collisions(self, tech_report_data):
        assert tech_report_data["technical_sanity_verdict"] == "ALL_SYSTEMS_FUNCTIONAL"
        assert tech_report_data["cross_document_passage_id_collisions"] == 0
        assert tech_report_data["schema_errors_detected"] == 0
        assert tech_report_data["crashes_detected"] == 0

    def test_graph_systems_return_canonical_passage_ids(self, tech_report_data):
        for q in tech_report_data["queries"]:
            for sys_name in ["baseline_graph_1hop", "repaired_graph_1hop_ablation", "repaired_graph_2hop_full"]:
                top_pids = q["systems"][sys_name]["top_5_passage_ids"]
                assert len(top_pids) <= 5
                for pid in top_pids:
                    assert "::" in pid, f"Passage ID must be canonical {{doc_id}}::{{chunk_id}}, got {pid}"

    def test_graph_anchor_coverage_and_fallback_tracking(self, tech_report_data):
        anchor_stats = tech_report_data["graph_anchor_coverage_and_fallback"]
        for sys_name in ["baseline_graph_1hop", "repaired_graph_1hop_ablation", "repaired_graph_2hop_full"]:
            stat = anchor_stats[sys_name]
            assert 0.0 <= stat["anchor_coverage_rate"] <= 1.0
            assert 0.0 <= stat["fallback_rate"] <= 1.0
            assert stat["queries_with_anchors"] + stat["fallback_count"] == stat["total_queries"]


# ===========================================================================
# 5. Hybrid RRF End-to-End Latency Accounting
# ===========================================================================

class TestHybridRRFTimingAccounting:
    def test_timing_report_distributions(self):
        assert TIMING_REPORT.exists()
        with open(TIMING_REPORT, encoding="utf-8") as f:
            report = json.load(f)

        assert report["num_warm_repetitions"] == 5
        systems = report["systems"]
        assert "hybrid_rrf_e2e" in systems
        rrf = systems["hybrid_rrf_e2e"]
        # End-to-end timing must account for BM25 + Dense + Fusion
        bm25_t = systems["bm25"]["warm_mean_ms"]
        dense_t = systems["dense_snowflake_arctic_768d"]["warm_mean_ms"]
        assert rrf["warm_mean_ms"] >= (bm25_t + dense_t) * 0.8
        assert rrf["warm_median_ms"] > 10.0  # Cannot be isolated 0.04ms artifact!
        assert rrf["warm_p95_ms"] >= rrf["warm_median_ms"]


# ===========================================================================
# 6. Human Evaluation Package Integrity
# ===========================================================================

class TestHumanEvaluationPackageIntegrity:
    def test_query_suite_manifest_counts(self):
        assert QUERY_MANIFEST.exists()
        with open(QUERY_MANIFEST, encoding="utf-8") as f:
            data = json.load(f)

        assert data["queries_count"] == 12
        assert data["total_candidate_pairs"] == 31
        cats = data["category_distribution"]
        assert cats["SINGLE_HOP_CONTROL"] == 3
        assert cats["TWO_HOP"] == 4
        assert cats["CROSS_DOCUMENT"] == 2
        assert cats["UNANSWERABLE"] == 3

    def test_candidate_pool_csv_empty_human_fields(self):
        assert CANDIDATE_POOL_CSV.exists()
        with open(CANDIDATE_POOL_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 31
        for r in rows:
            assert r["human_relevance_grade"] == "", "Human judgment fields must be blank"
            assert r["human_evidence_quote"] == ""
            assert r["human_confidence"] == ""
            assert r["human_notes"] == ""
            assert len(r["passage_sha256"]) == 64

    def test_annotation_protocol_document_exists(self):
        assert PROTOCOL_MD.exists()
        content = PROTOCOL_MD.read_text(encoding="utf-8")
        assert "Graded Relevance Scale" in content
        assert "Cohen's Weighted Kappa" in content


# ===========================================================================
# 7. Scientific Boundaries & Retrieval Effectiveness
# ===========================================================================

class TestRetrievalEffectivenessBoundary:
    def test_retrieval_effectiveness_strictly_not_evaluated(self):
        assert TECH_REPORT.exists()
        with open(TECH_REPORT, encoding="utf-8") as f:
            report = json.load(f)

        assert report["retrieval_effectiveness"] == "NOT_EVALUATED"
        assert "NOT_EVALUATED" in report["effectiveness_boundary_statement"]
        assert "No claims of retrieval superiority" in report["effectiveness_boundary_statement"]
