"""S5-B2 Investigator-Audited Benchmark Correction Tests.

Verifies:
1. Frozen S5-B1.1 pilot (31 pairs, 12 queries) remains unmodified.
2. Negative-control corpus-wide audit (Q03, Q08, Q11) across all 713 passages.
3. Provenance audit classifying pilot/silberschatz_3nf_card.txt as CONSTRUCTED_PILOT_ANSWER_CARD.
4. Top-k evaluation-pool coverage audit across all 6 frozen systems (no Recall@k/MRR/nDCG claims).
5. Proposed S5-B2 blinded package: 10 active queries, 25 pairs, deterministic seed 20261119,
   zero leaked category/role/rationale/UNANSWERABLE hints, empty human fields, and dual local workbooks.
"""

from __future__ import annotations

import csv
import json
import random
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
S5B1_DIR = ROOT / "research" / "s5-b1-integrity-repair"
S5B2_DIR = ROOT / "research" / "s5-b2-benchmark-correction"
REPORTS_DIR = S5B2_DIR / "reports"
PKG_DIR = S5B2_DIR / "proposed_package"
SPECS_PATH = S5B2_DIR / "corpus" / "s5b2_proposed_blinded_query_specs.json"
LOCAL_DIR = ROOT / "data" / "annotation_local" / "s5b2"


class TestS5B1Preservation:
    def test_s5b1_frozen_package_remains_intact(self):
        with open(S5B1_DIR / "human_evaluation_package" / "retrieval_query_pool_blinded.json", encoding="utf-8") as f:
            s5b1 = json.load(f)
        assert s5b1["queries_count"] == 12
        assert s5b1["total_candidate_pairs"] == 31
        assert s5b1["randomization_seed"] == 20261118


class TestS5B2Audits:
    def test_negative_control_audit_results(self):
        with open(REPORTS_DIR / "s5b2_negative_control_audit.json", encoding="utf-8") as f:
            neg = json.load(f)
        assert neg["corpus_passage_count"] == 713
        assert neg["unconditional_unanswerable_flag_removed"] is True
        raw_txt = (REPORTS_DIR / "s5b2_negative_control_audit.json").read_text(encoding="utf-8")
        assert "verified_corpus_unanswerable" not in raw_txt
        by_q = {q["query_id"]: q for q in neg["queries"]}
        for qid in ["Q-S5B2-03", "Q-S5B2-08", "Q-S5B2-11"]:
            assert by_q[qid]["adjudication_status"] == "PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_CHECK"
            assert by_q[qid]["human_inspection_status"] == "NOT_YET_PERFORMED"
            assert by_q[qid]["human_inspection_records"] == []
            assert "manually_inspected_passage_ids" not in by_q[qid]
            assert len(by_q[qid]["semantic_search_findings_top5"]) == 5
            assert len(by_q[qid]["search_selected_candidate_passage_ids"]) >= 5
        assert by_q["Q-S5B2-03"]["exact_keyword_hits"]["cortex"]["hit_count"] == 0
        assert by_q["Q-S5B2-03"]["exact_keyword_hits"]["nanosecond"]["hit_count"] == 0
        assert by_q["Q-S5B2-08"]["exact_keyword_hits"]["llama-3"]["hit_count"] == 0
        assert by_q["Q-S5B2-08"]["exact_keyword_hits"]["h100"]["hit_count"] == 0
        assert by_q["Q-S5B2-11"]["exact_keyword_hits"]["cisco"]["hit_count"] == 0
        assert by_q["Q-S5B2-11"]["exact_keyword_hits"]["cve-"]["hit_count"] == 0

    def test_silberschatz_provenance_audit(self):
        with open(REPORTS_DIR / "s5b2_silberschatz_provenance_audit.json", encoding="utf-8") as f:
            audit = json.load(f)
        assert audit["classification"] == "CONSTRUCTED_PILOT_ANSWER_CARD"
        assert audit["defined_in_hand_chunks"] is True
        assert audit["source_pdfs_list_empty"] is True

    def test_topk_coverage_audit_reports_unjudged_without_metrics(self):
        with open(REPORTS_DIR / "s5b2_topk_pool_coverage_audit.json", encoding="utf-8") as f:
            cov = json.load(f)
        raw = (REPORTS_DIR / "s5b2_topk_pool_coverage_audit.json").read_text(encoding="utf-8")
        assert "Recall@" not in raw or "MUST NOT be computed" in raw
        assert cov["coverage"]["top_5"]["unique_unjudged_query_passage_pairs_across_all_6_systems"] == 138
        assert cov["coverage"]["top_10"]["unique_unjudged_query_passage_pairs_across_all_6_systems"] == 277

    def test_query_evidence_matrix_decisions(self):
        with open(REPORTS_DIR / "s5b2_query_evidence_matrix.json", encoding="utf-8") as f:
            matrix = json.load(f)
        assert len(matrix) == 12
        by_q = {r["query_id"]: r for r in matrix}
        assert by_q["Q-S5A-01"]["decision"] == "KEEP"
        assert by_q["Q-S5A-02"]["decision"] == "REVISE"
        assert by_q["Q-S5A-04"]["decision"] == "REVISE"
        assert "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_011" in by_q["Q-S5A-04"]["proposed_candidate_passage_ids"]
        assert by_q["Q-S5A-05"]["decision"] == "REVISE"
        assert "papers/vaswani2017_attention_is_all_you_need.pdf::chunk_012" in by_q["Q-S5A-05"]["proposed_candidate_passage_ids"]
        assert by_q["Q-S5A-06"]["decision"] == "REVISE"
        assert by_q["Q-S5A-07"]["decision"] == "REVISE"
        assert by_q["Q-S5A-09"]["decision"] == "HOLD"
        assert by_q["Q-S5A-12"]["decision"] == "HOLD"


class TestProposedS5B2BlindedPackage:
    FORBIDDEN_KEYWORDS = {
        "PREMISE_DIRECT", "PREMISE_HOP_1", "PREMISE_HOP_2",
        "PREMISE_CROSS_DOC_A", "PREMISE_CROSS_DOC_B",
        "HARD_NEGATIVE", "CORPUS_CONTROL", "BACKGROUND_CONTEXT",
        "UNANSWERABLE", "SINGLE_HOP_CONTROL", "TWO_HOP", "CROSS_DOCUMENT",
        "admin_rationale", "candidate_role", "category_distribution",
    }

    def test_proposed_package_blinding_and_counts(self):
        csv_path = PKG_DIR / "retrieval_query_candidate_pool_blinded.csv"
        json_path = PKG_DIR / "retrieval_query_pool_blinded.json"
        proto_path = PKG_DIR / "RETRIEVAL_ANNOTATION_PROTOCOL.md"

        with open(csv_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 25
        for i, row in enumerate(rows, start=1):
            assert row["pair_id"] == f"S5B2-PAIR-{i:03d}"
            assert "category" not in row
            assert row["human_relevance_grade"] == ""
            assert row["human_evidence_quote"] == ""
            assert row["human_confidence"] == ""
            assert row["human_notes"] == ""

        for p in [csv_path, json_path, proto_path, SPECS_PATH]:
            txt = p.read_text(encoding="utf-8")
            for kw in self.FORBIDDEN_KEYWORDS:
                assert kw not in txt, f"Leaked keyword {kw} in {p.name}"

    def test_proposed_package_deterministic_randomization(self):
        with open(SPECS_PATH, encoding="utf-8") as f:
            specs = json.load(f)
        with open(PKG_DIR / "retrieval_query_pool_blinded.json", encoding="utf-8") as f:
            blinded = json.load(f)

        rng = random.Random(blinded["randomization_seed"])
        assert blinded["randomization_seed"] == 20261119
        for qs, qb in zip(specs["queries"], blinded["queries"]):
            expected = sorted(qs["candidate_passage_ids"])
            rng.shuffle(expected)
            actual = [c["candidate_passage_id"] for c in qb["candidates"]]
            assert actual == expected

    def test_local_reviewer_a_and_b_workbooks_exist_and_blinded(self):
        wb_a = LOCAL_DIR / "reviewer_a_s5b2_workbook.md"
        wb_b = LOCAL_DIR / "reviewer_b_s5b2_workbook.md"
        if not (ROOT / "okf_graph.db").exists():
            pytest.skip("okf_graph.db not present")
        assert wb_a.exists() and wb_b.exists()
        txt_a = wb_a.read_text(encoding="utf-8")
        txt_b = wb_b.read_text(encoding="utf-8")
        assert "Reviewer ID:** `REV_A`" in txt_a
        assert "Reviewer ID:** `REV_B`" in txt_b
        for kw in self.FORBIDDEN_KEYWORDS:
            assert kw not in txt_a and kw not in txt_b
        for i in range(1, 26):
            tag = f"S5B2-PAIR-{i:03d}"
            assert tag in txt_a and tag in txt_b


class TestS5B2_1ApprovalBlockerResolution:
    FORBIDDEN_REVIEWER_LEAKS = {
        "PREMISE_DIRECT", "PREMISE_HOP_1", "PREMISE_HOP_2",
        "PREMISE_CROSS_DOC_A", "PREMISE_CROSS_DOC_B",
        "HARD_NEGATIVE", "CORPUS_CONTROL", "BACKGROUND_CONTEXT",
        "UNANSWERABLE", "PROVISIONAL_NEGATIVE", "SINGLE_HOP_CONTROL",
        "TWO_HOP", "CROSS_DOCUMENT", "admin_rationale", "candidate_role",
        "dense_snowflake_arctic_768d", "hybrid_rrf_e2e", "baseline_graph_1hop",
        "repaired_graph_1hop_ablation", "repaired_graph_2hop_full",
    }

    def test_passage_necessity_matrix_for_q02_q05_q10(self):
        with open(REPORTS_DIR / "s5b2_1_passage_necessity_matrix.json", encoding="utf-8") as f:
            nec = json.load(f)
        by_q = {q["query_id"]: q for q in nec["queries"]}
        assert set(by_q.keys()) == {"Q-S5B2-02", "Q-S5B2-05", "Q-S5B2-10"}
        assert by_q["Q-S5B2-02"]["second_passage_indispensable"] is True
        assert by_q["Q-S5B2-02"]["classification"] == "TWO_HOP"
        assert by_q["Q-S5B2-05"]["passage_b_alone_sufficient"] is True
        assert by_q["Q-S5B2-05"]["second_passage_indispensable"] is False
        assert by_q["Q-S5B2-05"]["classification"] == "SINGLE_HOP"
        assert by_q["Q-S5B2-10"]["second_passage_indispensable"] is True
        assert by_q["Q-S5B2-10"]["classification"] == "TWO_HOP"

    def test_corpus_provenance_registry_preserves_713_corpus(self):
        with open(REPORTS_DIR / "s5b2_1_corpus_provenance_registry.json", encoding="utf-8") as f:
            prov = json.load(f)
        assert prov["frozen_corpus_version"] == "s5a_eval_corpus_v1"
        assert prov["total_passages"] == 713
        assert prov["corpus_unaltered"] is True
        counts = prov["counts_by_verification_tier"]
        assert sum(counts.values()) == 713
        assert counts["source_verified_constructed_pilot_card"] == 1
        assert counts["source_verified_truncated_textbook_stub"] == 21
        assert counts["convention_inferred_seed_chunk"] == 16
        assert counts["convention_inferred_paper_or_upload_chunk"] == 675

    def test_refreshed_topk_pool_coverage_and_persisted_ranked_results_reproduce_pool(self):
        with open(REPORTS_DIR / "s5b2_1_topk_pool_coverage_refreshed.json", encoding="utf-8") as f:
            cov = json.load(f)
        assert cov["active_queries_count"] == 10
        assert cov["total_unique_pooled_pairs_requiring_judgment"] == 254
        for k_key in ["top_5", "top_10"]:
            for sys_name, sys_cov in cov["coverage_comparison"][k_key].items():
                assert sys_cov["pooled_v2_1_coverage_pct"] == 100.0
        raw = (REPORTS_DIR / "s5b2_1_topk_pool_coverage_refreshed.json").read_text(encoding="utf-8")
        assert "MRR" not in raw or "no Recall@k, MRR, or nDCG" in raw

        # Verify persisted ranked results reproduce exact pooled set
        with open(REPORTS_DIR / "s5b2_1_frozen_ranked_results.json", encoding="utf-8") as f:
            ranked = json.load(f)
        with open(SPECS_PATH, encoding="utf-8") as f:
            specs = json.load(f)
        union_pairs: set[tuple[str, str]] = set()
        for q in specs["queries"]:
            for pid in q["candidate_passage_ids"]:
                union_pairs.add((q["query_id"], pid))
        for sys_name, sys_data in ranked["systems"].items():
            assert len(sys_data["queries"]) == 10
            for q_res in sys_data["queries"]:
                for item in q_res["ranked_top10"]:
                    union_pairs.add((q_res["query_id"], item["passage_id"]))

        with open(S5B2_DIR / "proposed_package_v2_1" / "retrieval_query_candidate_pool_blinded.csv", encoding="utf-8") as f:
            csv_pairs = {(r["query_id"], r["candidate_passage_id"]) for r in csv.DictReader(f)}
        assert union_pairs == csv_pairs
        assert len(csv_pairs) == 254

    def test_proposed_v21_pooled_package_and_workbooks_are_blinded(self):
        v21_dir = S5B2_DIR / "proposed_package_v2_1"
        csv_path = v21_dir / "retrieval_query_candidate_pool_blinded.csv"
        json_path = v21_dir / "retrieval_query_pool_blinded.json"
        proto_path = v21_dir / "RETRIEVAL_ANNOTATION_PROTOCOL.md"

        with open(csv_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 254
        for i, row in enumerate(rows, start=1):
            assert row["pair_id"] == f"S5B21-PAIR-{i:03d}"
            assert row["human_relevance_grade"] == ""
            assert row["human_evidence_quote"] == ""

        for p in [csv_path, json_path, proto_path]:
            txt = p.read_text(encoding="utf-8")
            for kw in self.FORBIDDEN_REVIEWER_LEAKS:
                assert kw not in txt, f"Leaked {kw} in {p.name}"

        proto_txt = proto_path.read_text(encoding="utf-8")
        assert "zero** validated cross-document queries" in proto_txt
        assert "Cohen's Weighted Kappa" in proto_txt

        local_v21 = ROOT / "data" / "annotation_local" / "s5b2_1"
        if not (ROOT / "okf_graph.db").exists():
            pytest.skip("okf_graph.db not present")
        for wb_name, rev_id in [("reviewer_a_s5b2_1_workbook.md", "REV_A"), ("reviewer_b_s5b2_1_workbook.md", "REV_B")]:
            wb = (local_v21 / wb_name).read_text(encoding="utf-8")
            assert (f"Reviewer ID:** `{rev_id}`" in wb) or (f"Reviewer ID: {rev_id}" in wb)
            for kw in self.FORBIDDEN_REVIEWER_LEAKS:
                assert kw not in wb, f"Leaked {kw} in {wb_name}"
            assert "S5B21-PAIR-001" in wb and "S5B21-PAIR-254" in wb

    def test_final_release_check_hashes_match_disk(self):
        import hashlib, re
        chk_txt = (S5B2_DIR / "S5B2_1_FINAL_RELEASE_CHECK.md").read_text(encoding="utf-8")
        matches = re.findall(r"\|\s*`([^`]+)`\s*\|\s*`([0-9a-f]{64})`\s*\|", chk_txt)
        assert len(matches) == 10
        for rel_path, expected_sha in matches:
            actual_sha = hashlib.sha256((ROOT / rel_path).read_bytes()).hexdigest()
            assert actual_sha == expected_sha, f"Hash mismatch for {rel_path}"
