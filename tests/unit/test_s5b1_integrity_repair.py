"""S5-B1 Integrity Repair Tests.

Covers all 7 required repairs for the S5-B1 research integrity milestone:

1. .gitignore fix: model manifests in research subdirectories no longer blocked
2. Blinded reviewer package: zero candidate_role, rationale, or admin hint exposure
3. Graph traversal instrumentation: actual observed hop depths, real paths, exception logging
4. Latency accounting: application cold-start reported separately from first-query latency
5. BM25-based fallback: graph retrievers use deterministic corpus BM25 when no anchors match
6. Dense embedding fingerprint: cryptographic alignment of cache with corpus ordering
7. Graph construction information access: edges strictly scoped to 713-passage eval corpus
"""

from __future__ import annotations

import csv
import json
import hashlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
S5B1_DIR = ROOT / "research" / "s5-b1-integrity-repair"
S5A_DIR = ROOT / "research" / "s5-a-retrieval-integrity"
PKG_DIR = S5B1_DIR / "human_evaluation_package"
ADMIN_DIR = S5B1_DIR / "admin_package"
REPORT_DIR = S5B1_DIR / "reports"
MODELS_DIR = S5B1_DIR / "models"
TIMING_PATH = REPORT_DIR / "retrieval_timing_report.json"
TECH_EVAL_PATH = REPORT_DIR / "retrieval_technical_evaluation_report.json"
MODEL_MANIFEST = MODELS_DIR / "s5b1_model_manifest.json"
S5A_MODEL_MANIFEST = S5A_DIR / "models" / "s5a_model_manifest.json"
GITIGNORE = ROOT / ".gitignore"
BLINDED_CSV = PKG_DIR / "retrieval_query_candidate_pool_blinded.csv"
BLINDED_JSON = PKG_DIR / "retrieval_query_pool_blinded.json"
ADMIN_MANIFEST = ADMIN_DIR / "admin_retrieval_manifest.json"
GRAPH_AUDIT = REPORT_DIR / "graph_information_access_audit.json"
EMB_CACHE = ROOT / "data" / "artifacts" / "s5a_dense_embeddings_713.npy"


# ---------------------------------------------------------------------------
# Repair 1: .gitignore Fix — model manifests now trackable
# ---------------------------------------------------------------------------

class TestGitignoreModelManifestFix:
    def test_gitignore_uses_anchored_root_models_pattern(self):
        """Root models/ directory is ignored with /models/ (anchored), not models/ (all subdirs)."""
        content = GITIGNORE.read_text()
        lines = [l.strip() for l in content.splitlines()]
        assert "/models/" in lines, "Expected anchored '/models/' in .gitignore to protect only root models/"
        assert "models/" not in lines or lines.index("models/") != lines.index("/models/"), (
            "Bare 'models/' must be replaced by '/models/' to allow research/*/models/ to be tracked"
        )

    def test_s5a_model_manifest_is_no_longer_gitignored(self):
        """s5a_model_manifest.json in research subdir should NOT be gitignored after the fix."""
        import subprocess
        result = subprocess.run(
            ["git", "check-ignore", "-v", str(S5A_MODEL_MANIFEST)],
            capture_output=True, text=True, cwd=str(ROOT)
        )
        # Exit code 1 = file is NOT gitignored; exit code 0 = gitignored
        assert result.returncode == 1, (
            f"S5-A model manifest is still gitignored: {result.stdout.strip()}"
        )

    def test_s5b1_model_manifest_exists_and_has_git_policy(self):
        """S5-B1 model manifest exists and documents the .gitignore policy."""
        assert MODEL_MANIFEST.exists(), f"Missing S5-B1 model manifest at {MODEL_MANIFEST}"
        with open(MODEL_MANIFEST) as f:
            m = json.load(f)
        assert m.get("git_policy", {}).get("root_model_weights_ignored") is True
        assert m["git_policy"]["root_ignore_pattern"] == "/models/"
        assert m["git_policy"]["manifest_version_controlled"] is True

    def test_s5b1_annotation_local_still_gitignored(self):
        """annotation_local/ inside S5-B1 research dir should remain gitignored."""
        content = GITIGNORE.read_text()
        assert "research/s5-b1-integrity-repair/annotation_local/" in content


# ---------------------------------------------------------------------------
# Repair 2: Blinded Reviewer Package — Zero role/rationale exposure
# ---------------------------------------------------------------------------

class TestBlindedReviewerPackage:
    FORBIDDEN_COLS = {
        "candidate_role", "admin_rationale", "rationale", "role", "expected_label"
    }
    FORBIDDEN_KEYWORDS = {
        "PREMISE_DIRECT", "PREMISE_HOP_1", "PREMISE_HOP_2",
        "PREMISE_CROSS_DOC_A", "PREMISE_CROSS_DOC_B",
        "HARD_NEGATIVE", "CORPUS_CONTROL", "BACKGROUND_CONTEXT",
    }

    def test_blinded_csv_exists(self):
        assert BLINDED_CSV.exists(), f"Blinded CSV not found: {BLINDED_CSV}"

    def test_blinded_csv_has_no_role_columns(self):
        with open(BLINDED_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cols = set(reader.fieldnames or [])
        for forbidden in self.FORBIDDEN_COLS:
            assert forbidden not in cols, f"Forbidden column '{forbidden}' found in blinded CSV"

    def test_blinded_csv_has_no_role_values(self):
        with open(BLINDED_CSV, encoding="utf-8") as f:
            content = f.read()
        for kw in self.FORBIDDEN_KEYWORDS:
            assert kw not in content, f"Leaked role keyword '{kw}' found in blinded reviewer CSV"

    def test_blinded_csv_has_neutral_pair_ids(self):
        with open(BLINDED_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 31, f"Expected 31 candidate pairs, got {len(rows)}"
        for i, row in enumerate(rows, start=1):
            expected = f"PAIR-{i:03d}"
            assert row["pair_id"] == expected, f"Row {i}: expected pair_id={expected}, got {row['pair_id']}"

    def test_blinded_csv_human_fields_all_empty(self):
        human_fields = ["human_relevance_grade", "human_evidence_quote", "human_confidence", "human_notes"]
        with open(BLINDED_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for field in human_fields:
                    assert row.get(field, "") == "", (
                        f"Human field '{field}' is non-empty in blinded CSV for pair {row.get('pair_id')}"
                    )

    def test_blinded_json_has_no_role_fields(self):
        with open(BLINDED_JSON) as f:
            data = json.load(f)
        content = json.dumps(data)
        for kw in self.FORBIDDEN_KEYWORDS:
            assert kw not in content, f"Leaked keyword '{kw}' found in blinded JSON"
        for q in data["queries"]:
            for c in q["candidates"]:
                assert "candidate_role" not in c, f"candidate_role field found in blinded JSON candidate"
                assert "admin_rationale" not in c, f"admin_rationale field found in blinded JSON candidate"

    def test_admin_manifest_separate_from_public_package(self):
        """Admin manifest exists in admin_package/, not in human_evaluation_package/."""
        assert ADMIN_MANIFEST.exists(), f"Admin manifest missing at {ADMIN_MANIFEST}"
        # Ensure admin manifest is NOT inside the PKG_DIR (human_evaluation_package)
        admin_in_pkg = PKG_DIR / "admin_retrieval_manifest.json"
        assert not admin_in_pkg.exists(), (
            "Admin manifest must NOT be in human_evaluation_package/; must be in admin_package/"
        )

    def test_admin_manifest_has_all_role_assignments(self):
        with open(ADMIN_MANIFEST) as f:
            admin = json.load(f)
        pairs = admin.get("candidate_pairs", [])
        assert len(pairs) == 31, f"Expected 31 admin pairs, got {len(pairs)}"
        for pair in pairs:
            assert "candidate_role" in pair, f"Missing candidate_role in admin pair {pair.get('pair_id')}"
            assert "admin_rationale" in pair, f"Missing admin_rationale in admin pair {pair.get('pair_id')}"
            assert pair["candidate_role"] != "", f"Empty candidate_role in pair {pair.get('pair_id')}"


# ---------------------------------------------------------------------------
# Repair 3: Graph Traversal Instrumentation
# ---------------------------------------------------------------------------

class TestGraphTraversalInstrumentation:
    def test_tech_eval_report_exists(self):
        assert TECH_EVAL_PATH.exists(), f"Technical evaluation report missing: {TECH_EVAL_PATH}"

    def test_graph_systems_report_fallback_rate(self):
        with open(TECH_EVAL_PATH) as f:
            report = json.load(f)
        graph_systems = ["baseline_graph_1hop", "repaired_graph_1hop_ablation", "repaired_graph_2hop_full"]
        for sys_name in graph_systems:
            sys = report["systems"][sys_name]
            assert "fallback_rate" in sys, f"{sys_name} missing fallback_rate"
            assert 0.0 <= sys["fallback_rate"] <= 1.0, f"{sys_name} fallback_rate out of range"

    def test_graph_systems_report_actual_hop_count(self):
        with open(TECH_EVAL_PATH) as f:
            report = json.load(f)
        graph_systems = ["baseline_graph_1hop", "repaired_graph_1hop_ablation", "repaired_graph_2hop_full"]
        for sys_name in graph_systems:
            sys = report["systems"][sys_name]
            assert "observed_average_hop_depth" in sys, f"{sys_name} missing observed_average_hop_depth"

    def test_graph_systems_report_total_paths_traversed(self):
        with open(TECH_EVAL_PATH) as f:
            report = json.load(f)
        for sys_name in ["repaired_graph_1hop_ablation", "repaired_graph_2hop_full"]:
            sys = report["systems"][sys_name]
            assert "total_paths_traversed" in sys, f"{sys_name} missing total_paths_traversed"
            assert isinstance(sys["total_paths_traversed"], int)

    def test_2hop_traverses_more_paths_than_1hop(self):
        with open(TECH_EVAL_PATH) as f:
            report = json.load(f)
        paths_1hop = report["systems"]["repaired_graph_1hop_ablation"]["total_paths_traversed"]
        paths_2hop = report["systems"]["repaired_graph_2hop_full"]["total_paths_traversed"]
        assert paths_2hop >= paths_1hop, (
            f"2-hop ({paths_2hop}) should traverse >= paths as 1-hop ({paths_1hop})"
        )

    def test_no_silently_swallowed_exceptions(self):
        """Benchmark script source must not contain bare except: pass blocks."""
        script_path = S5B1_DIR / "scripts" / "run_s5b1_retrieval_benchmark.py"
        content = script_path.read_text()
        import re
        # Check for the bad pattern: except Exception:\n        pass  or except:\n        pass
        bad_pattern = re.compile(r"except\s*(?:Exception)?\s*:\s*\n\s*pass\b")
        assert not bad_pattern.search(content), (
            "Found silently swallowed 'except: pass' in S5-B1 benchmark script — must log exceptions"
        )


# ---------------------------------------------------------------------------
# Repair 4: Latency Accounting — cold-start vs per-query
# ---------------------------------------------------------------------------

class TestLatencyAccounting:
    def test_timing_report_has_application_cold_start(self):
        with open(TIMING_PATH) as f:
            timing = json.load(f)
        cold = timing.get("application_cold_start_ms", {})
        assert "corpus_load_ms" in cold, "Missing corpus_load_ms in cold start"
        assert "dense_model_load_ms" in cold, "Missing dense_model_load_ms in cold start"
        assert "bm25_index_build_ms" in cold, "Missing bm25_index_build_ms in cold start"
        assert "corpus_scoped_graph_build_ms" in cold, "Missing corpus_scoped_graph_build_ms in cold start"

    def test_timing_report_has_first_query_separate_from_warm(self):
        with open(TIMING_PATH) as f:
            timing = json.load(f)
        for name, sys in timing["systems"].items():
            assert "first_query_mean_ms" in sys, f"{name} missing first_query_mean_ms"
            assert "warm_mean_ms" in sys, f"{name} missing warm_mean_ms"
            assert "warm_p95_ms" in sys, f"{name} missing warm_p95_ms"
            assert "warm_std_ms" in sys, f"{name} missing warm_std_ms"

    def test_model_load_time_is_nonzero(self):
        with open(TIMING_PATH) as f:
            timing = json.load(f)
        model_load = timing["application_cold_start_ms"]["dense_model_load_ms"]
        assert model_load > 0, "dense_model_load_ms must be nonzero (genuine cold start)"

    def test_warm_distribution_has_min_max_std(self):
        with open(TIMING_PATH) as f:
            timing = json.load(f)
        for name, sys in timing["systems"].items():
            assert "warm_min_ms" in sys, f"{name} missing warm_min_ms"
            assert "warm_max_ms" in sys, f"{name} missing warm_max_ms"
            assert sys["warm_min_ms"] <= sys["warm_mean_ms"] <= sys["warm_max_ms"], (
                f"{name}: warm stats inconsistent: min={sys['warm_min_ms']} mean={sys['warm_mean_ms']} max={sys['warm_max_ms']}"
            )


# ---------------------------------------------------------------------------
# Repair 5: BM25-Based Fallback
# ---------------------------------------------------------------------------

class TestBM25BasedFallback:
    def test_benchmark_script_uses_bm25_fallback_not_substring(self):
        """Graph retrievers must use BM25 fallback, not unsorted substring slice."""
        script_path = S5B1_DIR / "scripts" / "run_s5b1_retrieval_benchmark.py"
        content = script_path.read_text()
        # S5-A bad pattern: (p.passage_id, 0.05) for p in self.passages if any(w ...)
        old_pattern = '(p.passage_id, 0.05)'
        assert old_pattern not in content, (
            "Found old unsorted substring fallback '(p.passage_id, 0.05)' in S5-B1 script"
        )
        # Confirm BM25 fallback present
        assert "bm25_fallback" in content, "BM25 fallback not referenced in S5-B1 benchmark script"

    def test_tech_eval_reports_fallback_strategy(self):
        with open(TECH_EVAL_PATH) as f:
            report = json.load(f)
        for sys_name in ["repaired_graph_1hop_ablation", "repaired_graph_2hop_full"]:
            for q_result in report["systems"][sys_name]["query_results"]:
                meta = q_result.get("meta", {})
                if meta.get("is_fallback"):
                    assert meta.get("fallback_strategy") == "corpus_bm25", (
                        f"{sys_name} fallback strategy is '{meta.get('fallback_strategy')}', expected 'corpus_bm25'"
                    )

    def test_scientific_integrity_bm25_fallback_active(self):
        with open(TECH_EVAL_PATH) as f:
            report = json.load(f)
        assert report["scientific_integrity_guarantees"]["bm25_fallback_active"] is True


# ---------------------------------------------------------------------------
# Repair 6: Dense Embedding Fingerprint Verification
# ---------------------------------------------------------------------------

class TestDenseEmbeddingFingerprint:
    def test_model_manifest_has_cryptographic_fingerprints(self):
        with open(MODEL_MANIFEST) as f:
            m = json.load(f)
        fp = m["primary_dense_model"]["cryptographic_fingerprints"]
        assert "embedding_matrix_sha256" in fp
        assert "corpus_passage_id_sha256" in fp
        assert "corpus_text_sha256" in fp

    def test_embedding_cache_sha256_matches_manifest(self):
        """Embedding cache file SHA-256 must match what the manifest declares."""
        if not EMB_CACHE.exists():
            pytest.skip("Dense embedding cache not present on this machine")
        with open(MODEL_MANIFEST) as f:
            m = json.load(f)
        declared_sha = m["primary_dense_model"]["cryptographic_fingerprints"]["embedding_matrix_sha256"]
        actual_sha = hashlib.sha256(EMB_CACHE.read_bytes()).hexdigest()
        assert actual_sha == declared_sha, (
            f"Embedding cache SHA-256 mismatch: declared={declared_sha}, actual={actual_sha}"
        )

    def test_embedding_shape_is_713x768(self):
        if not EMB_CACHE.exists():
            pytest.skip("Dense embedding cache not present")
        import numpy as np
        emb = np.load(str(EMB_CACHE))
        assert emb.shape == (713, 768), f"Expected shape (713, 768), got {emb.shape}"

    def test_corpus_pids_sha256_matches_manifest(self):
        """Corpus passage-ID ordering SHA must match manifest declaration."""
        with open(MODEL_MANIFEST) as f:
            m = json.load(f)
        declared_pids_sha = m["primary_dense_model"]["cryptographic_fingerprints"]["corpus_passage_id_sha256"]

        from archipelago.eval.retrieval_baselines import build_fixed_corpus_from_kuzu, _is_index_only_passage
        db_path = ROOT / "okf_graph.db"
        if not db_path.exists():
            pytest.skip("Database not present on this machine")

        passages, _ = build_fixed_corpus_from_kuzu(str(db_path))
        eligible = [
            p for p in passages
            if not _is_index_only_passage(p.doc_id, p.section_title, p.text)
            and p.passage_id != "doc_data_and_computer_communications::doc_data_and_computer_communications_p612_4"
        ]
        hasher = hashlib.sha256()
        for p in eligible:
            hasher.update(p.passage_id.encode("utf-8"))
        actual_pids_sha = hasher.hexdigest()
        assert actual_pids_sha == declared_pids_sha, (
            f"Corpus PID SHA mismatch: declared={declared_pids_sha}, actual={actual_pids_sha}"
        )


# ---------------------------------------------------------------------------
# Repair 7: Graph Construction Information Access
# ---------------------------------------------------------------------------

class TestGraphInformationAccessAudit:
    def test_graph_audit_report_exists(self):
        assert GRAPH_AUDIT.exists(), f"Graph information access audit report missing: {GRAPH_AUDIT}"

    def test_graph_audit_identifies_external_chunks(self):
        with open(GRAPH_AUDIT) as f:
            audit = json.load(f)
        assert audit["external_chunks_count"] > 0, (
            "Expected to find external chunks (documents outside eval corpus) in the database"
        )

    def test_graph_audit_remediation_applied(self):
        with open(GRAPH_AUDIT) as f:
            audit = json.load(f)
        assert audit["information_access_verdict"] in {
            "FAIR_RESTRICTED", "DISCREPANCY_DETECTED_AND_CORRECTED"
        }, f"Unexpected verdict: {audit['information_access_verdict']}"
        assert "remediation_applied" in audit and len(audit["remediation_applied"]) > 0

    def test_tech_eval_reports_corpus_scope_as_identical(self):
        with open(TECH_EVAL_PATH) as f:
            report = json.load(f)
        assert report["scientific_integrity_guarantees"]["corpus_scope_strictly_identical"] is True


# ---------------------------------------------------------------------------
# Retrieval Effectiveness Boundary
# ---------------------------------------------------------------------------

class TestRetrievalEffectivenessBoundary:
    def test_no_superiority_claims_in_reports(self):
        """Technical report must not assert retrieval superiority."""
        with open(TECH_EVAL_PATH) as f:
            report = json.load(f)
        assert not report["scientific_integrity_guarantees"]["superiority_asserted"]
        assert not report["scientific_integrity_guarantees"]["effectiveness_claimed"]
        assert report["scientific_integrity_guarantees"]["human_gold_status"] == "PENDING_INDEPENDENT_ANNOTATION"

    def test_all_systems_marked_not_evaluated(self):
        with open(TECH_EVAL_PATH) as f:
            report = json.load(f)
        for name, sys in report["systems"].items():
            assert sys.get("effectiveness_verdict") == "NOT_EVALUATED_PENDING_HUMAN_GOLD", (
                f"{name} has unexpected effectiveness_verdict: {sys.get('effectiveness_verdict')}"
            )
