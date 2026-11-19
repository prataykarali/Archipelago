"""Unit tests for Module 3: Independent A/C Comparison, Human Adjudication, and Gold v2."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
S5C3_SCRIPTS = ROOT / "research" / "s5-c3-human-adjudication-prep" / "scripts"
SCHEMA_PATH = (
    ROOT / "research" / "s5-c3-human-adjudication-prep" / "schemas" / "s5_gold_label_ac_v2.schema.json"
)
POOL_PATH = (
    ROOT / "research" / "s5-b2-benchmark-correction" / "proposed_package_v2_1" / "retrieval_query_pool_blinded.json"
)
LEGACY_EVAL_PATH = (
    ROOT / "research" / "s5-d0-experimental-analysis-prep" / "scripts" / "evaluate_gold_labels_readonly.py"
)

if str(S5C3_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(S5C3_SCRIPTS))

from ac_adjudication.comparison import (  # noqa: E402
    assemble_gold_v2,
    build_blank_adjudication_worksheet,
    render_adjudication_worksheet_markdown,
)
from ac_adjudication.constants import (  # noqa: E402
    ADJUDICATION_SOURCE_ADJUDICATED,
    ADJUDICATION_SOURCE_AGREEMENT,
    ASSISTANCE_NONE,
    EXPECTED_PAIR_COUNT,
    GOLD_STATUS_AC_V2_FINAL,
    PRIOR_EXPOSURE_NONE,
    PROVENANCE_ADJUDICATED_HUMAN,
    PROVENANCE_AI_ASSISTED,
    PROVENANCE_INDEPENDENT_HUMAN,
    PROVENANCE_NOT_REQUIRED_ZERO,
    PROVISIONAL_NEG_CONTROL_IDS,
    ROLE_REV_A,
    ROLE_REV_B,
    ROLE_REV_C,
    SCHEMA_VERSION_AC_V2,
)
from ac_adjudication.pool_index import FrozenPool, load_frozen_pool, sha256_text  # noqa: E402
from ac_adjudication.server import (  # noqa: E402
    create_adjudication_app,
    run_local_adjudication_server,
)
from ac_adjudication.validation import (  # noqa: E402
    ACValidationError,
    validate_adjudication_worksheet,
    validate_gold_v2_payload,
    validate_reviewer_submission,
)
import s5_ac_adjudication as cli_mod  # noqa: E402

SYNTHETIC_TS = "2026-11-19T12:00:00Z"
SYNTHETIC_SHA_A = "a" * 64
SYNTHETIC_SHA_C = "c" * 64
SYNTHETIC_SHA_WS = "d" * 64


def _load_legacy_evaluator() -> Any:
    spec = importlib.util.spec_from_file_location("legacy_eval_v1", LEGACY_EVAL_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_submission(
    pool: FrozenPool,
    *,
    role: str,
    reviewer_id: str,
    grade_overrides: dict[str, int] | None = None,
    quote_overrides: dict[str, str] | None = None,
) -> dict[str, Any]:
    overrides = grade_overrides or {}
    quotes = quote_overrides or {}
    judgments = []
    for idx, pid in enumerate(pool.ordered_pair_ids):
        entry = pool.entries_by_pair_id[pid]
        grade = overrides.get(pid, idx % 3)
        quote = quotes.get(pid, "" if grade == 0 else f"Verbatim evidence for {pid}")
        judgments.append(
            {
                "pair_id": pid,
                "query_id": entry.query_id,
                "passage_id": entry.passage_id,
                "passage_sha256": entry.passage_sha256,
                "relevance_grade": grade,
                "supporting_quotation": quote,
                "confidence": "HIGH",
                "reviewer_notes": f"Human judgment note for {pid}",
            }
        )
    return {
        "reviewer_role": role,
        "pool_version": pool.version,
        "pool_sha256": pool.pool_sha256,
        "provenance": {
            "reviewer_id": reviewer_id,
            "provenance_class": PROVENANCE_INDEPENDENT_HUMAN,
            "assistance_declaration": ASSISTANCE_NONE,
            "prior_exposure_disclosure": PRIOR_EXPOSURE_NONE,
            "human_attestation_signed": True,
            "attestation_signer": reviewer_id,
            "signed_timestamp_utc": SYNTHETIC_TS,
        },
        "judgments": judgments,
    }


def _make_neg_controls() -> dict[str, Any]:
    return {
        qid: {
            "human_answerability_classification": "NO_ANSWER_IN_FROZEN_CORPUS",
            "verifier_id": "HUMAN_VERIFIER_01",
            "provenance_class": PROVENANCE_INDEPENDENT_HUMAN,
            "human_attestation_signed": True,
            "signed_timestamp_utc": SYNTHETIC_TS,
        }
        for qid in PROVISIONAL_NEG_CONTROL_IDS
    }


def _make_investigator_signoff() -> dict[str, Any]:
    return {
        "investigator_id": "PI_HUMAN_01",
        "approval_declaration": "Approved independent human A/C gold v2 after full audit.",
        "human_signoff_confirmed": True,
        "signed_timestamp_utc": SYNTHETIC_TS,
    }


def _make_adjudicator_prov(prov_class: str = PROVENANCE_ADJUDICATED_HUMAN) -> dict[str, Any]:
    return {
        "adjudicator_id": "HUMAN_ADJ_01",
        "provenance_class": prov_class,
        "assistance_declaration": ASSISTANCE_NONE,
        "human_attestation_signed": True,
        "attestation_signer": "HUMAN_ADJ_01",
        "signed_timestamp_utc": SYNTHETIC_TS,
    }


@pytest.fixture(scope="module")
def frozen_pool() -> FrozenPool:
    pool = load_frozen_pool(POOL_PATH)
    assert pool.pair_count == EXPECTED_PAIR_COUNT
    return pool


@pytest.mark.unit
def test_valid_ac_full_agreement_assembles_gold_v2(frozen_pool: FrozenPool) -> None:
    sub_a = _make_submission(frozen_pool, role=ROLE_REV_A, reviewer_id="HUMAN_REV_A_01")
    sub_c = _make_submission(frozen_pool, role=ROLE_REV_C, reviewer_id="HUMAN_REV_C_01")
    ws = build_blank_adjudication_worksheet(
        sub_a, sub_c, frozen_pool, rev_a_sha256=SYNTHETIC_SHA_A, rev_c_sha256=SYNTHETIC_SHA_C
    )
    assert ws["disagreements_count"] == 0
    assert ws["inter_annotator_agreement"]["exact_agreement_rate"] == 1.0
    assert ws["adjudicator_provenance"]["human_attestation_signed"] is False

    ws["adjudicator_provenance"] = _make_adjudicator_prov(PROVENANCE_NOT_REQUIRED_ZERO)
    gold = assemble_gold_v2(
        rev_a_payload=sub_a,
        rev_c_payload=sub_c,
        worksheet_payload=ws,
        neg_controls_payload=_make_neg_controls(),
        investigator_signoff_payload=_make_investigator_signoff(),
        pool=frozen_pool,
        rev_a_sha256=SYNTHETIC_SHA_A,
        rev_c_sha256=SYNTHETIC_SHA_C,
        worksheet_sha256=SYNTHETIC_SHA_WS,
        schema_path=SCHEMA_PATH,
    )
    assert gold["schema_version"] == SCHEMA_VERSION_AC_V2
    assert gold["status"] == GOLD_STATUS_AC_V2_FINAL
    assert gold["historical_reviewer_b_excluded_from_gold"] is True
    assert gold["legacy_reviewer_b_provenance"]["provenance_class"] == PROVENANCE_AI_ASSISTED
    assert len(gold["judgments"]) == EXPECTED_PAIR_COUNT
    assert all(j["adjudication_source"] == ADJUDICATION_SOURCE_AGREEMENT for j in gold["judgments"])
    validate_gold_v2_payload(gold, frozen_pool, schema_path=SCHEMA_PATH)


@pytest.mark.unit
def test_valid_ac_with_human_adjudicated_disagreements(frozen_pool: FrozenPool) -> None:
    p0, p1 = frozen_pool.ordered_pair_ids[0], frozen_pool.ordered_pair_ids[1]
    sub_a = _make_submission(
        frozen_pool, role=ROLE_REV_A, reviewer_id="HUMAN_REV_A_01", grade_overrides={p0: 0, p1: 2}
    )
    sub_c = _make_submission(
        frozen_pool, role=ROLE_REV_C, reviewer_id="HUMAN_REV_C_01", grade_overrides={p0: 2, p1: 1}
    )
    ws = build_blank_adjudication_worksheet(
        sub_a, sub_c, frozen_pool, rev_a_sha256=SYNTHETIC_SHA_A, rev_c_sha256=SYNTHETIC_SHA_C
    )
    assert ws["disagreements_count"] == 2
    assert "**Disagreements Requiring Human Adjudication:** 2" in render_adjudication_worksheet_markdown(ws)

    with pytest.raises(ACValidationError, match=r"adjudicated_grade|human_attestation_signed"):
        validate_adjudication_worksheet(ws, [p0, p1], frozen_pool)

    ws["disagreements"][0].update(
        {
            "adjudicated_grade": 1,
            "adjudication_evidence_quote": f"Verbatim evidence for {p0}",
            "adjudication_rationale": "Passage gives partial background context without full answer.",
            "adjudicator_id": "HUMAN_ADJ_01",
            "decision_timestamp_utc": SYNTHETIC_TS,
        }
    )
    ws["disagreements"][1].update(
        {
            "adjudicated_grade": 0,
            "adjudication_evidence_quote": "",
            "adjudication_rationale": "Keyword overlap only; passage does not answer the query.",
            "adjudicator_id": "HUMAN_ADJ_01",
            "decision_timestamp_utc": SYNTHETIC_TS,
        }
    )
    ws["adjudicator_provenance"] = _make_adjudicator_prov()

    gold = assemble_gold_v2(
        rev_a_payload=sub_a,
        rev_c_payload=sub_c,
        worksheet_payload=ws,
        neg_controls_payload=_make_neg_controls(),
        investigator_signoff_payload=_make_investigator_signoff(),
        pool=frozen_pool,
        rev_a_sha256=SYNTHETIC_SHA_A,
        rev_c_sha256=SYNTHETIC_SHA_C,
        worksheet_sha256=SYNTHETIC_SHA_WS,
        schema_path=SCHEMA_PATH,
    )
    by_pid = {row["pair_id"]: row for row in gold["judgments"]}
    assert by_pid[p0]["final_grade"] == 1 and by_pid[p0]["adjudication_source"] == ADJUDICATION_SOURCE_ADJUDICATED
    assert by_pid[p1]["final_grade"] == 0 and by_pid[p1]["adjudication_source"] == ADJUDICATION_SOURCE_ADJUDICATED
    assert gold["adjudication_summary"]["adjudicated_count"] == 2

    bad_signoff = _make_investigator_signoff()
    bad_signoff["human_signoff_confirmed"] = False
    with pytest.raises(ACValidationError, match="human_signoff_confirmed"):
        assemble_gold_v2(
            rev_a_payload=sub_a,
            rev_c_payload=sub_c,
            worksheet_payload=ws,
            neg_controls_payload=_make_neg_controls(),
            investigator_signoff_payload=bad_signoff,
            pool=frozen_pool,
            rev_a_sha256=SYNTHETIC_SHA_A,
            rev_c_sha256=SYNTHETIC_SHA_C,
            worksheet_sha256=SYNTHETIC_SHA_WS,
            schema_path=SCHEMA_PATH,
        )


@pytest.mark.unit
def test_rejects_missing_reviewer_and_incomplete_pairs(frozen_pool: FrozenPool, tmp_path: Path) -> None:
    sub_a = _make_submission(frozen_pool, role=ROLE_REV_A, reviewer_id="HUMAN_REV_A_01")
    rev_a_path = tmp_path / "rev_a.json"
    rev_a_path.write_text(json.dumps(sub_a), encoding="utf-8")

    rc = cli_mod.main(
        [
            "compare", "--rev-a", str(rev_a_path), "--rev-c", str(tmp_path / "missing_rev_c.json"),
            "--output-worksheet", str(tmp_path / "ws.json"), "--pool", str(POOL_PATH),
        ]
    )
    assert rc == 2 and not (tmp_path / "ws.json").exists()

    incomplete_c = _make_submission(frozen_pool, role=ROLE_REV_C, reviewer_id="HUMAN_REV_C_01")
    incomplete_c["judgments"].pop()
    with pytest.raises(ACValidationError, match="Incomplete submission: missing 1"):
        build_blank_adjudication_worksheet(
            sub_a, incomplete_c, frozen_pool, rev_a_sha256=SYNTHETIC_SHA_A, rev_c_sha256=SYNTHETIC_SHA_C
        )


@pytest.mark.unit
def test_rejects_unsigned_and_ai_generated_provenance(frozen_pool: FrozenPool) -> None:
    unsigned_a = _make_submission(frozen_pool, role=ROLE_REV_A, reviewer_id="HUMAN_REV_A_01")
    unsigned_a["provenance"]["human_attestation_signed"] = False
    with pytest.raises(ACValidationError, match="human_attestation_signed"):
        validate_reviewer_submission(unsigned_a, frozen_pool, expected_role=ROLE_REV_A)

    ai_c = _make_submission(frozen_pool, role=ROLE_REV_C, reviewer_id="HUMAN_REV_C_01")
    ai_c["provenance"]["provenance_class"] = PROVENANCE_AI_ASSISTED
    ai_c["provenance"]["assistance_declaration"] = "LLM_ASSISTED"
    with pytest.raises(ACValidationError, match="rejected AI"):
        validate_reviewer_submission(ai_c, frozen_pool, expected_role=ROLE_REV_C)

    rev_b = _make_submission(frozen_pool, role=ROLE_REV_B, reviewer_id="HUMAN_REV_B_01")
    with pytest.raises(ACValidationError, match="REV_B"):
        validate_reviewer_submission(rev_b, frozen_pool, expected_role=ROLE_REV_C)

    p0 = frozen_pool.ordered_pair_ids[0]
    sub_a = _make_submission(frozen_pool, role=ROLE_REV_A, reviewer_id="HUMAN_REV_A_01", grade_overrides={p0: 0})
    sub_c = _make_submission(frozen_pool, role=ROLE_REV_C, reviewer_id="HUMAN_REV_C_01", grade_overrides={p0: 2})
    ws = build_blank_adjudication_worksheet(
        sub_a, sub_c, frozen_pool, rev_a_sha256=SYNTHETIC_SHA_A, rev_c_sha256=SYNTHETIC_SHA_C
    )
    ws["disagreements"][0].update(
        {
            "adjudicated_grade": 2,
            "adjudication_evidence_quote": f"Verbatim evidence for {p0}",
            "adjudication_rationale": "Detailed human rationale explaining direct evidence.",
            "adjudicator_id": "HUMAN_ADJ_01",
        }
    )
    ws["adjudicator_provenance"] = {
        "adjudicator_id": "HUMAN_ADJ_01",
        "provenance_class": PROVENANCE_AI_ASSISTED,
        "assistance_declaration": "AI_GENERATED",
        "human_attestation_signed": True,
        "attestation_signer": "HUMAN_ADJ_01",
        "signed_timestamp_utc": SYNTHETIC_TS,
    }
    with pytest.raises(ACValidationError, match="rejected AI"):
        validate_adjudication_worksheet(ws, [p0], frozen_pool)


@pytest.mark.unit
def test_rejects_missing_rationale_and_passage_hash_or_quote_mismatch(frozen_pool: FrozenPool) -> None:
    bad_hash_a = _make_submission(frozen_pool, role=ROLE_REV_A, reviewer_id="HUMAN_REV_A_01")
    bad_hash_a["judgments"][0]["passage_sha256"] = "0" * 64
    with pytest.raises(ACValidationError, match="passage_sha256 mismatch"):
        validate_reviewer_submission(bad_hash_a, frozen_pool, expected_role=ROLE_REV_A)

    p0 = frozen_pool.ordered_pair_ids[0]
    p0_entry = frozen_pool.entries_by_pair_id[p0]
    canonical_text = "Exact canonical passage text for testing quote verification."
    custom_pool = FrozenPool(
        version=frozen_pool.version,
        pool_sha256=frozen_pool.pool_sha256,
        entries_by_pair_id={
            p0: type(p0_entry)(
                pair_id=p0_entry.pair_id,
                query_id=p0_entry.query_id,
                domain=p0_entry.domain,
                query_text=p0_entry.query_text,
                passage_id=p0_entry.passage_id,
                doc_id=p0_entry.doc_id,
                chunk_id=p0_entry.chunk_id,
                page_number=p0_entry.page_number,
                passage_sha256=sha256_text(canonical_text),
                passage_text=canonical_text,
            )
        },
        ordered_pair_ids=(p0,),
    )
    bad_quote_sub = _make_submission(
        custom_pool, role=ROLE_REV_A, reviewer_id="HUMAN_REV_A_01",
        grade_overrides={p0: 2}, quote_overrides={p0: "Not a substring at all"},
    )
    with pytest.raises(ACValidationError, match="exact verbatim substring"):
        validate_reviewer_submission(bad_quote_sub, custom_pool, expected_role=ROLE_REV_A)

    sub_a = _make_submission(frozen_pool, role=ROLE_REV_A, reviewer_id="HUMAN_REV_A_01", grade_overrides={p0: 0})
    sub_c = _make_submission(frozen_pool, role=ROLE_REV_C, reviewer_id="HUMAN_REV_C_01", grade_overrides={p0: 2})
    ws = build_blank_adjudication_worksheet(
        sub_a, sub_c, frozen_pool, rev_a_sha256=SYNTHETIC_SHA_A, rev_c_sha256=SYNTHETIC_SHA_C
    )
    ws["disagreements"][0].update(
        {
            "adjudicated_grade": 2,
            "adjudication_evidence_quote": f"Verbatim evidence for {p0}",
            "adjudication_rationale": "short",
            "adjudicator_id": "HUMAN_ADJ_01",
        }
    )
    ws["adjudicator_provenance"] = _make_adjudicator_prov()
    with pytest.raises(ACValidationError, match="adjudication_rationale"):
        validate_adjudication_worksheet(ws, [p0], frozen_pool)


@pytest.mark.unit
def test_legacy_reviewer_b_contract_preserved_untouched() -> None:
    legacy = _load_legacy_evaluator()
    pool_index, exp_ver, exp_sha = legacy.load_frozen_pool_index(POOL_PATH)
    legacy_payload = legacy.expected_gold_label_schema()
    legacy_payload["reviewer_b_independence_confirmed"] = False
    with pytest.raises(legacy.GoldLabelValidationError, match="reviewer_b_independence_confirmed"):
        legacy.validate_adjudicated_gold_labels(legacy_payload, pool_index, exp_ver, exp_sha)


@pytest.mark.unit
def test_offline_local_ui_and_cli_roundtrip(frozen_pool: FrozenPool, tmp_path: Path) -> None:
    p0 = frozen_pool.ordered_pair_ids[0]
    sub_a = _make_submission(frozen_pool, role=ROLE_REV_A, reviewer_id="HUMAN_REV_A_01", grade_overrides={p0: 0})
    sub_c = _make_submission(frozen_pool, role=ROLE_REV_C, reviewer_id="HUMAN_REV_C_01", grade_overrides={p0: 2})
    rev_a_path, rev_c_path = tmp_path / "rev_a.json", tmp_path / "rev_c.json"
    ws_path, md_path = tmp_path / "worksheet.json", tmp_path / "worksheet.md"
    rev_a_path.write_text(json.dumps(sub_a), encoding="utf-8")
    rev_c_path.write_text(json.dumps(sub_c), encoding="utf-8")

    assert cli_mod.main(
        [
            "compare", "--rev-a", str(rev_a_path), "--rev-c", str(rev_c_path),
            "--output-worksheet", str(ws_path), "--output-markdown", str(md_path),
            "--pool", str(POOL_PATH),
        ]
    ) == 0
    assert ws_path.exists() and md_path.exists()

    with pytest.raises(ValueError, match=r"127\.0\.0\.1"):
        run_local_adjudication_server(ws_path, frozen_pool, host="0.0.0.0")

    client = create_adjudication_app(ws_path, frozen_pool).test_client()
    assert client.get("/api/readiness").get_json()["ready"] is True
    html = client.get("/").get_data(as_text=True)
    assert "http://" not in html and "https://" not in html

    assert client.post(
        "/api/decision",
        json={
            "pair_id": p0, "adjudicated_grade": 2, "adjudication_evidence_quote": "Valid quote",
            "adjudication_rationale": "", "adjudicator_id": "HUMAN_ADJ_01",
        },
    ).status_code == 400

    assert client.post(
        "/api/decision",
        json={
            "pair_id": p0, "adjudicated_grade": 2,
            "adjudication_evidence_quote": f"Verbatim evidence for {p0}",
            "adjudication_rationale": "Direct factual answer present in the canonical passage.",
            "adjudicator_id": "HUMAN_ADJ_01",
        },
    ).status_code == 200

    assert client.post(
        "/api/provenance",
        json={
            "adjudicator_id": "HUMAN_ADJ_01", "provenance_class": PROVENANCE_AI_ASSISTED,
            "assistance_declaration": "AI_ASSISTED", "attestation_signer": "HUMAN_ADJ_01",
            "human_attestation_signed": True,
        },
    ).status_code == 400

    assert client.post(
        "/api/provenance",
        json={
            "adjudicator_id": "HUMAN_ADJ_01", "provenance_class": PROVENANCE_ADJUDICATED_HUMAN,
            "assistance_declaration": ASSISTANCE_NONE, "attestation_signer": "HUMAN_ADJ_01",
            "human_attestation_signed": True,
        },
    ).status_code == 200

    neg_path, signoff_path, gold_path = tmp_path / "neg.json", tmp_path / "signoff.json", tmp_path / "gold_v2.json"
    neg_path.write_text(json.dumps(_make_neg_controls()), encoding="utf-8")
    signoff_path.write_text(json.dumps(_make_investigator_signoff()), encoding="utf-8")

    assert cli_mod.main(
        [
            "validate-adjudication", "--worksheet", str(ws_path),
            "--rev-a", str(rev_a_path), "--rev-c", str(rev_c_path), "--pool", str(POOL_PATH),
        ]
    ) == 0
    assert cli_mod.main(
        [
            "assemble-gold", "--rev-a", str(rev_a_path), "--rev-c", str(rev_c_path),
            "--worksheet", str(ws_path), "--neg-controls", str(neg_path),
            "--investigator-signoff", str(signoff_path), "--output", str(gold_path),
            "--pool", str(POOL_PATH), "--schema", str(SCHEMA_PATH),
        ]
    ) == 0
    assert cli_mod.main(
        ["validate-gold", "--gold", str(gold_path), "--pool", str(POOL_PATH), "--schema", str(SCHEMA_PATH)]
    ) == 0
