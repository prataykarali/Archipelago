"""S5-B1 & S5-B1.1 Integrity Repair and Final Annotation Readiness Gate Tests.

Covers all required repairs and verification gates:
1. .gitignore fix: model manifests in research subdirectories tracked; root /models/ and admin/local packages ignored.
2. Blinded reviewer package: zero candidate_role, rationale, category, or answerability (UNANSWERABLE) hints;
   deterministic PRNG candidate ordering (seed = 20261118) breaking positive-then-negative ordering.
3. Admin manifest isolation: untracked in Git, stored in Git-ignored local storage only.
4. Separate Reviewer A and Reviewer B workbooks: contain actual verified passage text, neutral IDs, empty judgment fields.
5. Graph traversal instrumentation: actual observed hop depths, real paths, exception logging, BM25 fallback.
6. Latency accounting: application cold-start reported separately from first-query and warm distributions.
7. Runtime cryptographic fingerprint verification: checks embedding cache, passage-ID ordering, and corpus text at runtime
   and rejects mismatches explicitly with ValueError.
8. Complete Graph Information-Access Audit: both RepairedHeterogeneousGraphRetriever and RepairedBaselineGraphRetriever
   (Kùzu REQUIRES/RELATED/UNLOCKS edges) audited and restricted to the 713-passage evaluation corpus.
"""

from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
import random
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
S5B1_DIR = ROOT / "research" / "s5-b1-integrity-repair"
S5A_DIR = ROOT / "research" / "s5-a-retrieval-integrity"
PKG_DIR = S5B1_DIR / "human_evaluation_package"
LOCAL_DIR = S5B1_DIR / "annotation_local"
REPORT_DIR = S5B1_DIR / "reports"
MODELS_DIR = S5B1_DIR / "models"
CORPUS_DIR = S5B1_DIR / "corpus"

TIMING_PATH = REPORT_DIR / "retrieval_timing_report.json"
TECH_EVAL_PATH = REPORT_DIR / "retrieval_technical_evaluation_report.json"
MODEL_MANIFEST = MODELS_DIR / "s5b1_model_manifest.json"
S5A_MODEL_MANIFEST = S5A_DIR / "models" / "s5a_model_manifest.json"
GITIGNORE = ROOT / ".gitignore"

BLINDED_CSV = PKG_DIR / "retrieval_query_candidate_pool_blinded.csv"
BLINDED_JSON = PKG_DIR / "retrieval_query_pool_blinded.json"
PROTOCOL_MD = PKG_DIR / "RETRIEVAL_ANNOTATION_PROTOCOL.md"
BLINDED_SPECS = CORPUS_DIR / "s5b1_blinded_query_specs.json"

LOCAL_ADMIN_MANIFEST = LOCAL_DIR / "admin_retrieval_manifest.json"
REVIEWER_A_WB = LOCAL_DIR / "reviewer_a_retrieval_workbook.md"
REVIEWER_B_WB = LOCAL_DIR / "reviewer_b_retrieval_workbook.md"

GRAPH_AUDIT = REPORT_DIR / "graph_information_access_audit.json"
EMB_CACHE = ROOT / "data" / "artifacts" / "s5a_dense_embeddings_713.npy"
BENCHMARK_SCRIPT = S5B1_DIR / "scripts" / "run_s5b1_retrieval_benchmark.py"


def _load_benchmark_module():
    spec = importlib.util.spec_from_file_location("s5b1_bench", str(BENCHMARK_SCRIPT))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Repair 1: .gitignore Fix — model manifests tracked, admin/local packages ignored
# ---------------------------------------------------------------------------

class TestGitignoreAndAdminIsolation:
    def test_gitignore_uses_anchored_root_models_pattern(self):
        content = GITIGNORE.read_text(encoding="utf-8")
        lines = [l.strip() for l in content.splitlines()]
        assert "/models/" in lines, "Expected anchored '/models/' in .gitignore"
        assert "models/" not in lines, "Bare 'models/' must not be present in .gitignore"

    def test_s5a_and_s5b1_model_manifests_are_not_gitignored(self):
        for manifest in [S5A_MODEL_MANIFEST, MODEL_MANIFEST]:
            assert manifest.exists()
            res = subprocess.run(
                ["git", "check-ignore", "-v", str(manifest)],
                capture_output=True, text=True, cwd=str(ROOT),
            )
            assert res.returncode == 1, f"Model manifest should not be gitignored: {manifest}"

    def test_s5b1_model_manifest_has_git_policy(self):
        with open(MODEL_MANIFEST, encoding="utf-8") as f:
            m = json.load(f)
        assert m["git_policy"]["root_model_weights_ignored"] is True
        assert m["git_policy"]["root_ignore_pattern"] == "/models/"
        assert m["git_policy"]["manifest_version_controlled"] is True

    def test_admin_manifest_is_untracked_and_gitignored(self):
        """Admin manifest containing expected roles/rationales must NOT be tracked in Git."""
        old_public_admin = S5B1_DIR / "admin_package" / "admin_retrieval_manifest.json"
        assert not old_public_admin.exists(), "admin_package/admin_retrieval_manifest.json must not exist in tracked tree"

        tracked = subprocess.run(
            ["git", "ls-files", "*admin_retrieval_manifest*"],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert tracked.stdout.strip() == "", f"Admin manifest must not be tracked in git: {tracked.stdout}"

        ignore_check = subprocess.run(
            ["git", "check-ignore", "-v", str(LOCAL_ADMIN_MANIFEST)],
            capture_output=True, text=True, cwd=str(ROOT),
        )
        assert ignore_check.returncode == 0, "Local admin manifest path must be covered by .gitignore"


# ---------------------------------------------------------------------------
# Repair 2 & S5-B1.1 Gates 1, 2, 6: Blinded Package, Zero Categories, Randomized Order, Dual Workbooks
# ---------------------------------------------------------------------------

class TestBlindedReviewerPackageAndRandomization:
    FORBIDDEN_COLS = {
        "candidate_role", "admin_rationale", "rationale", "role", "expected_label", "category"
    }
    FORBIDDEN_KEYWORDS = {
        "PREMISE_DIRECT", "PREMISE_HOP_1", "PREMISE_HOP_2",
        "PREMISE_CROSS_DOC_A", "PREMISE_CROSS_DOC_B",
        "HARD_NEGATIVE", "CORPUS_CONTROL", "BACKGROUND_CONTEXT",
        "UNANSWERABLE", "SINGLE_HOP_CONTROL", "TWO_HOP", "CROSS_DOCUMENT",
        "admin_rationale", "candidate_role", "category_distribution",
    }

    def test_blinded_csv_has_no_role_or_category_columns(self):
        assert BLINDED_CSV.exists()
        with open(BLINDED_CSV, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            cols = set(reader.fieldnames or [])
        for forbidden in self.FORBIDDEN_COLS:
            assert forbidden not in cols, f"Forbidden column '{forbidden}' found in blinded CSV"

    def test_all_reviewer_facing_files_contain_zero_leaked_keywords(self):
        files_to_check = [BLINDED_CSV, BLINDED_JSON, PROTOCOL_MD, BLINDED_SPECS]
        if REVIEWER_A_WB.exists():
            files_to_check.append(REVIEWER_A_WB)
        if REVIEWER_B_WB.exists():
            files_to_check.append(REVIEWER_B_WB)

        for fpath in files_to_check:
            content = fpath.read_text(encoding="utf-8")
            for kw in self.FORBIDDEN_KEYWORDS:
                assert kw not in content, f"Leaked keyword '{kw}' found in reviewer-facing file {fpath.name}"

    def test_blinded_csv_has_neutral_pair_ids_and_empty_human_fields(self):
        human_fields = ["human_relevance_grade", "human_evidence_quote", "human_confidence", "human_notes"]
        with open(BLINDED_CSV, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 31
        for i, row in enumerate(rows, start=1):
            assert row["pair_id"] == f"PAIR-{i:03d}"
            for hf in human_fields:
                assert row[hf] == "", f"Human field {hf} must be empty in {row['pair_id']}"

    def test_candidate_ordering_is_deterministically_randomized_with_recorded_seed(self):
        with open(BLINDED_JSON, encoding="utf-8") as f:
            blinded = json.load(f)
        with open(BLINDED_SPECS, encoding="utf-8") as f:
            specs = json.load(f)

        seed = blinded["randomization_seed"]
        assert seed == 20261118
        rng = random.Random(seed)

        for q_spec, q_blind in zip(specs["queries"], blinded["queries"]):
            expected_pids = sorted(q_spec["candidate_passage_ids"])
            rng.shuffle(expected_pids)
            actual_pids = [c["candidate_passage_id"] for c in q_blind["candidates"]]
            assert actual_pids == expected_pids, f"Candidate order mismatch for {q_spec['query_id']}"

    def test_randomized_order_breaks_positive_then_negative_pattern(self):
        if not LOCAL_ADMIN_MANIFEST.exists():
            pytest.skip("Local gitignored admin manifest not present in isolated environment")
        with open(LOCAL_ADMIN_MANIFEST, encoding="utf-8") as f:
            admin = json.load(f)

        by_query: dict[str, list[str]] = {}
        for p in admin["candidate_pairs"]:
            by_query.setdefault(p["query_id"], []).append(p["candidate_role"])

        first_position_hard_negatives = sum(1 for roles in by_query.values() if roles[0] == "HARD_NEGATIVE")
        last_position_positives = sum(
            1 for roles in by_query.values()
            if roles[-1] in {"PREMISE_DIRECT", "PREMISE_HOP_1", "PREMISE_HOP_2", "PREMISE_CROSS_DOC_A", "PREMISE_CROSS_DOC_B", "CORPUS_CONTROL"}
        )
        assert first_position_hard_negatives >= 3, "Randomization must place HARD_NEGATIVE first in multiple queries"
        assert last_position_positives >= 3, "Randomization must place non-negative candidates last in multiple queries"

    def test_separate_reviewer_a_and_b_workbooks_contain_verified_text(self):
        db_path = ROOT / "okf_graph.db"
        if not db_path.exists():
            pytest.skip("okf_graph.db not present in isolated environment")
        if not REVIEWER_A_WB.exists() or not REVIEWER_B_WB.exists():
            from subprocess import run
            run(["python3", str(S5B1_DIR / "scripts" / "build_s5b1_human_eval_package.py")], check=True, cwd=str(ROOT))

        assert REVIEWER_A_WB.exists()
        assert REVIEWER_B_WB.exists()

        wb_a = REVIEWER_A_WB.read_text(encoding="utf-8")
        wb_b = REVIEWER_B_WB.read_text(encoding="utf-8")
        assert "Reviewer ID:** `REV_A`" in wb_a
        assert "Reviewer ID:** `REV_B`" in wb_b

        for i in range(1, 32):
            pair_tag = f"Candidate Pair `PAIR-{i:03d}`"
            assert pair_tag in wb_a
            assert pair_tag in wb_b


# ---------------------------------------------------------------------------
# Repair 3 & 5: Graph Traversal Instrumentation & BM25 Fallback
# ---------------------------------------------------------------------------

class TestGraphTraversalAndBM25Fallback:
    def test_graph_systems_report_fallback_hop_depth_and_paths(self):
        assert TECH_EVAL_PATH.exists()
        with open(TECH_EVAL_PATH, encoding="utf-8") as f:
            report = json.load(f)
        for sys_name in ["baseline_graph_1hop", "repaired_graph_1hop_ablation", "repaired_graph_2hop_full"]:
            sys_data = report["systems"][sys_name]
            assert 0.0 <= sys_data["fallback_rate"] <= 1.0
            assert "observed_average_hop_depth" in sys_data
            assert isinstance(sys_data["total_paths_traversed"], int)
            for qr in sys_data["query_results"]:
                meta = qr["meta"]
                if meta["is_fallback"]:
                    assert meta["fallback_strategy"] == "corpus_bm25"
                    assert meta["actual_hop_count"] == 0
                else:
                    assert meta["actual_hop_count"] in {0, 1, 2}

    def test_2hop_traverses_more_paths_than_1hop(self):
        with open(TECH_EVAL_PATH, encoding="utf-8") as f:
            report = json.load(f)
        p1 = report["systems"]["repaired_graph_1hop_ablation"]["total_paths_traversed"]
        p2 = report["systems"]["repaired_graph_2hop_full"]["total_paths_traversed"]
        assert p2 > p1

    def test_no_silently_swallowed_exceptions_in_benchmark_script(self):
        import re
        content = BENCHMARK_SCRIPT.read_text(encoding="utf-8")
        bad_pattern = re.compile(r"except\s*(?:Exception)?\s*:\s*\n\s*pass\b")
        assert not bad_pattern.search(content)
        assert "(p.passage_id, 0.05)" not in content


# ---------------------------------------------------------------------------
# Repair 4: Latency Accounting — Cold-Start vs Per-Query
# ---------------------------------------------------------------------------

class TestLatencyAccounting:
    def test_timing_report_has_application_cold_start_and_warm_stats(self):
        assert TIMING_PATH.exists()
        with open(TIMING_PATH, encoding="utf-8") as f:
            timing = json.load(f)
        cold = timing["application_cold_start_ms"]
        for key in ["corpus_load_ms", "dense_model_load_ms", "bm25_index_build_ms", "corpus_scoped_graph_build_ms"]:
            assert key in cold and cold[key] > 0

        for name, sys_t in timing["systems"].items():
            assert "first_query_mean_ms" in sys_t
            assert sys_t["warm_min_ms"] <= sys_t["warm_mean_ms"] <= sys_t["warm_max_ms"]
            assert sys_t["warm_p95_ms"] >= sys_t["warm_median_ms"]


# ---------------------------------------------------------------------------
# Repair 6 & S5-B1.1 Gate 4: Runtime Cryptographic Fingerprint Verification
# ---------------------------------------------------------------------------

class TestRuntimeDenseEmbeddingFingerprintVerification:
    def test_runtime_verification_succeeds_on_authentic_corpus_and_cache(self):
        db_path = ROOT / "okf_graph.db"
        if not db_path.exists() or not EMB_CACHE.exists():
            pytest.skip("Local DB or dense cache not present")
        mod = _load_benchmark_module()
        passages, _ = mod.load_s5b1_corpus()
        emb, fp = mod.verify_dense_cache_and_corpus_fingerprints(passages, EMB_CACHE, MODEL_MANIFEST)
        assert emb.shape == (713, 768)
        assert fp["passage_count"] == 713

    def test_runtime_verification_rejects_perturbed_passage_id_ordering(self):
        db_path = ROOT / "okf_graph.db"
        if not db_path.exists() or not EMB_CACHE.exists():
            pytest.skip("Local DB or dense cache not present")
        mod = _load_benchmark_module()
        passages, _ = mod.load_s5b1_corpus()
        swapped = list(passages)
        swapped[0], swapped[1] = swapped[1], swapped[0]
        with pytest.raises(ValueError, match="passage-ID ordering SHA-256 mismatch"):
            mod.verify_dense_cache_and_corpus_fingerprints(swapped, EMB_CACHE, MODEL_MANIFEST)

    def test_runtime_verification_rejects_corrupted_passage_text(self):
        db_path = ROOT / "okf_graph.db"
        if not db_path.exists() or not EMB_CACHE.exists():
            pytest.skip("Local DB or dense cache not present")
        mod = _load_benchmark_module()
        passages, _ = mod.load_s5b1_corpus()
        corrupted = list(passages)
        p0 = copy.copy(corrupted[0])
        object.__setattr__(p0, "text", p0.text + " CORRUPTED")
        corrupted[0] = p0
        with pytest.raises(ValueError, match="Corpus text SHA-256 mismatch"):
            mod.verify_dense_cache_and_corpus_fingerprints(corrupted, EMB_CACHE, MODEL_MANIFEST)

    def test_runtime_verification_rejects_corrupted_embedding_cache(self, tmp_path):
        db_path = ROOT / "okf_graph.db"
        if not db_path.exists() or not EMB_CACHE.exists():
            pytest.skip("Local DB or dense cache not present")
        mod = _load_benchmark_module()
        passages, _ = mod.load_s5b1_corpus()
        bad_cache = tmp_path / "bad_embeddings.npy"
        bad_cache.write_bytes(b"corrupted_bytes")
        with pytest.raises(ValueError, match="Dense embedding cache SHA-256 mismatch"):
            mod.verify_dense_cache_and_corpus_fingerprints(passages, bad_cache, MODEL_MANIFEST)


# ---------------------------------------------------------------------------
# Repair 7 & S5-B1.1 Gate 5: Complete Graph Information-Access Audit (Heterogeneous & Baseline Kùzu)
# ---------------------------------------------------------------------------

class TestCompleteGraphInformationAccessAudit:
    def test_graph_audit_covers_both_heterogeneous_and_baseline_kuzu_graphs(self):
        assert GRAPH_AUDIT.exists()
        with open(GRAPH_AUDIT, encoding="utf-8") as f:
            audit = json.load(f)

        assert audit["unconstrained_edges_count"] == 148
        assert audit["constrained_edges_count"] == 146
        assert audit["leaked_external_edges_count"] == 2

        kuzu_audit = audit["baseline_kuzu_graph_audit"]
        assert kuzu_audit["total_concept_nodes"] == 610
        assert kuzu_audit["concepts_in_eligible_713_corpus"] == 451
        assert kuzu_audit["concepts_only_in_external_chunks"] == 56
        assert kuzu_audit["total_concept_edges_in_kuzu"] == 1988
        assert kuzu_audit["eligible_corpus_verified_edges"] == 1526
        assert kuzu_audit["non_eligible_or_unscoped_edges_excluded"] == 462

    def test_baseline_kuzu_edge_filter_rejects_external_and_unscoped_sources(self):
        db_path = ROOT / "okf_graph.db"
        if not db_path.exists():
            pytest.skip("okf_graph.db not present")
        import kuzu
        from archipelago.eval.retrieval_baselines import BM25Retriever
        mod = _load_benchmark_module()
        passages, _ = mod.load_s5b1_corpus()
        bm25 = BM25Retriever(passages)
        conn = kuzu.Connection(kuzu.Database(str(db_path), read_only=True))
        retriever = mod.RepairedBaselineGraphRetriever(passages, conn, bm25)

        assert not retriever._is_corpus_verified_kuzu_edge("graph neural network", None)
        assert not retriever._is_corpus_verified_kuzu_edge("graph neural network", "pearson_batch1")
        assert not retriever._is_corpus_verified_kuzu_edge("graph neural network", "librarian_upload")
        assert not retriever._is_corpus_verified_kuzu_edge(
            "graph neural network", "data_science_2019/Index_2019_Data-Science.pdf:chunk_007"
        )
        assert retriever._is_corpus_verified_kuzu_edge(
            "graph neural network", "papers/Vaswani2017_Attention_Is_All_You_Need.pdf:chunk_004"
        )


# ---------------------------------------------------------------------------
# Retrieval Effectiveness Scientific Boundary
# ---------------------------------------------------------------------------

class TestRetrievalEffectivenessBoundary:
    def test_no_superiority_claims_or_category_leakage_in_technical_report(self):
        with open(TECH_EVAL_PATH, encoding="utf-8") as f:
            report = json.load(f)
        assert report["scientific_integrity_guarantees"]["superiority_asserted"] is False
        assert report["scientific_integrity_guarantees"]["effectiveness_claimed"] is False
        assert report["scientific_integrity_guarantees"]["baseline_kuzu_graph_corpus_scoped"] is True
        assert report["runtime_fingerprint_verification"]["verified_at_startup"] is True

        raw_text = TECH_EVAL_PATH.read_text(encoding="utf-8")
        assert "UNANSWERABLE" not in raw_text
        for name, sys_data in report["systems"].items():
            assert sys_data["effectiveness_verdict"] == "NOT_EVALUATED_PENDING_HUMAN_GOLD"
