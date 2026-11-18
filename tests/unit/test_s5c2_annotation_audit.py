"""S5-C2 Human Annotation Validation & Agreement Audit Tests."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
S5C2_DIR = ROOT / "research" / "s5-c2-annotation-audit"
REPORTS_DIR = S5C2_DIR / "reports"
LOCAL_DIR = ROOT / "data" / "annotation_local" / "s5c2"


class TestS5C2ValidationAndAgreement:
    def test_audit_summary_validation_counts(self):
        with open(REPORTS_DIR / "s5c2_audit_summary.json", encoding="utf-8") as f:
            s = json.load(f)
        assert s["total_pairs"] == 254
        assert s["readiness_decision"] == "HOLD_FOR_DISAGREEMENT_ADJUDICATION_AND_REV_B_INDEPENDENCE_CHECK"
        for rev in ["REV_A", "REV_B"]:
            v = s["validation"][rev]
            assert v["expected_pair_count"] == 254
            assert v["parsed_pair_count"] == 254
            assert v["missing_pairs"] == []
            assert v["duplicate_pairs"] == []
            assert v["invalid_grades"] == []
            assert v["invalid_confidences"] == []
            assert v["passage_id_mismatches"] == []
            assert v["sha_mismatches"] == []
            assert v["missing_quotes_for_grades_1_2"] == []
            assert v["nonempty_quotes_for_grade_0"] == []
            assert v["quote_mismatches"] == []

        assert s["preserved_originals"]["reviewer_a"]["ai_assisted_notes_count"] == 0
        assert s["preserved_originals"]["reviewer_b"]["ai_assisted_notes_count"] == 254

    def test_descriptive_agreement_and_ai_disclosure(self):
        with open(REPORTS_DIR / "s5c2_audit_summary.json", encoding="utf-8") as f:
            s = json.load(f)
        agr = s["descriptive_agreement_pre_adjudication"]
        assert agr["independence_status"] == "UNVERIFIED_AI_ASSISTED_SUBMISSION_IN_REV_B"
        assert agr["agreement_count"] == 203
        assert agr["disagreement_count"] == 51
        assert agr["raw_agreement_pct"] == 79.92
        assert agr["cohens_weighted_kappa_quadratic"] == 0.7677
        cm = agr["confusion_matrix_rows_rev_a_cols_rev_b"]
        assert sum(sum(r) for r in cm) == 254

        agr_md = (REPORTS_DIR / "S5C2_INTER_ANNOTATOR_AGREEMENT.md").read_text(encoding="utf-8")
        assert "descriptive agreement between the submitted annotation sets" in agr_md
        assert "NOT validated inter-human reliability" in agr_md

    def test_negative_control_verification_sheet_has_empty_fields(self):
        txt = (REPORTS_DIR / "S5C2_NEGATIVE_CONTROL_VERIFICATION.md").read_text(encoding="utf-8")
        for qid in ["Q-S5B2-03", "Q-S5B2-08", "Q-S5B2-11"]:
            assert qid in txt
        assert "PROVISIONAL_NEGATIVE_PENDING_INDEPENDENT_HUMAN_VERIFICATION" in txt
        assert len(re.findall(r"`verifier_id`:\s*$", txt, re.MULTILINE)) == 3

    def test_private_disagreement_docket_has_51_pairs_and_empty_adjudication(self):
        docket = LOCAL_DIR / "S5C2_DISAGREEMENT_ADJUDICATION.md"
        if not docket.exists():
            pytest.skip("Local gitignored disagreement docket not present")
        txt = docket.read_text(encoding="utf-8")
        headers = re.findall(r"^## `(S5B21-PAIR-\d+)`", txt, re.MULTILINE)
        assert len(headers) == 51
        assert len(re.findall(r"^- \*\*final_adjudicated_grade \(0 \| 1 \| 2\):\*\*\s*$", txt, re.MULTILINE)) == 51
        assert len(re.findall(r"^- \*\*adjudicator_id:\*\*\s*$", txt, re.MULTILINE)) == 51
