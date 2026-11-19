"""Unit and synthetic integration tests for the S5-C3 human annotation workbench."""

from __future__ import annotations

import csv
import json
from pathlib import Path
import re
import sys
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKBENCH_SCRIPTS_DIR = (
    REPO_ROOT / "research" / "s5-c3-human-adjudication-prep" / "scripts"
)
if str(WORKBENCH_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(WORKBENCH_SCRIPTS_DIR))

from annotation_workbench import (  # noqa: E402
    AnnotationSession,
    ExportValidationError,
    JudgmentRecord,
    LoadedPool,
    PoolIntegrityError,
    PrivatePathViolationError,
    ProvenanceDeclaration,
    assert_blinding_clean,
    assert_loopback_host,
    content_hash,
    create_app,
    create_timestamped_backup,
    ensure_private_path,
    export_submission,
    is_exact_verbatim_quote,
    load_blinded_pool,
    load_or_create_session,
    save_session,
    sha256_file,
    validate_pair_judgment,
    validate_provenance,
    validate_session,
)
from annotation_workbench.constants import (  # noqa: E402
    ALLOWED_HOST,
    ASSISTANCE_AI_ASSISTED,
    ASSISTANCE_EXPOSED,
    ASSISTANCE_NONE,
    DEFAULT_BLANK_WORKBOOK_BACKUP,
    DEFAULT_POOL_JSON,
    EXPECTED_PAIR_COUNT,
    EXPECTED_POOL_SHA256,
    EXPECTED_QUERY_COUNT,
    FORBIDDEN_BLINDING_TOKENS,
    HTTP_OK,
    HTTP_UNPROCESSABLE_ENTITY,
    PROVENANCE_AI_ASSISTED,
    PROVENANCE_INDEPENDENT_HUMAN,
    PROVENANCE_POST_AI_EXPOSURE,
    SUBMISSION_CSV_COLUMNS,
    SUBMISSION_SCHEMA_VERSION,
)
from annotation_workbench.ui_template import render_workbench_html  # noqa: E402
import s5_annotation_workbench as cli_mod  # noqa: E402


def _build_synthetic_pool(tmp_path: Path) -> tuple[Path, Path, LoadedPool]:
    """Create a small synthetic 3-pair blinded pool and matching passage JSON."""
    passages = {
        "S5B21-PAIR-001": (
            "An address space is the running program's view of memory in the system."
        ),
        "S5B21-PAIR-002": (
            "Paging divides memory into fixed-size units called pages for translation."
        ),
        "S5B21-PAIR-003": (
            "TCP congestion control adjusts the sending rate based on packet loss."
        ),
    }
    pool_payload: dict[str, Any] = {
        "version": "synthetic_test_pool_v1",
        "status": "TEST_ONLY",
        "randomization_seed": 20261119,
        "queries_count": 2,
        "total_candidate_pairs": 3,
        "queries": [
            {
                "query_id": "Q-SYN-01",
                "domain": "Operating Systems",
                "query_text": "What is an address space?",
                "candidate_count": 2,
                "candidates": [
                    {"pair_id": "S5B21-PAIR-001", "presentation_order": 1, "candidate_passage_id": "doc_os::chunk_1", "candidate_doc_id": "doc_os", "candidate_chunk_id": "chunk_1", "candidate_page_number": 1, "passage_sha256": content_hash(passages["S5B21-PAIR-001"])},
                    {"pair_id": "S5B21-PAIR-002", "presentation_order": 2, "candidate_passage_id": "doc_os::chunk_2", "candidate_doc_id": "doc_os", "candidate_chunk_id": "chunk_2", "candidate_page_number": 2, "passage_sha256": content_hash(passages["S5B21-PAIR-002"])},
                ],
            },
            {
                "query_id": "Q-SYN-02",
                "domain": "Computer Networks",
                "query_text": "How does TCP congestion control react to loss?",
                "candidate_count": 1,
                "candidates": [
                    {"pair_id": "S5B21-PAIR-003", "presentation_order": 1, "candidate_passage_id": "doc_net::chunk_1", "candidate_doc_id": "doc_net", "candidate_chunk_id": "chunk_1", "candidate_page_number": 4, "passage_sha256": content_hash(passages["S5B21-PAIR-003"])},
                ],
            },
        ],
    }
    pool_path = tmp_path / "synthetic_pool.json"
    passages_path = tmp_path / "synthetic_passages.json"
    pool_path.write_text(json.dumps(pool_payload, indent=2), encoding="utf-8")
    passages_path.write_text(json.dumps(passages, indent=2), encoding="utf-8")

    loaded = load_blinded_pool(
        pool_path=pool_path,
        passage_source=passages_path,
        verify_canonical_pool_sha=False,
    )
    return pool_path, passages_path, loaded


def _signed_human_provenance() -> ProvenanceDeclaration:
    """Return a valid, explicitly signed synthetic human provenance declaration."""
    return ProvenanceDeclaration(
        reviewer_identity_or_pseudonym="SYNTHETIC_HUMAN_TESTER",
        provenance_class=PROVENANCE_INDEPENDENT_HUMAN,
        assistance_declaration=ASSISTANCE_NONE,
        human_attestation_confirmed=True,
        review_start_date_utc="2026-11-19T10:00:00Z",
        review_completion_date_utc="2026-11-19T11:00:00Z",
        signed_by_human_at_utc="2026-11-19T11:00:00Z",
    )


def _complete_synthetic_session(pool: LoadedPool) -> AnnotationSession:
    """Populate valid judgments for all 3 synthetic pairs with signed provenance."""
    session = AnnotationSession(
        pool_version=pool.pool_version,
        pool_sha256=pool.pool_sha256,
        provenance=_signed_human_provenance(),
    )
    session.judgments["S5B21-PAIR-001"] = JudgmentRecord(
        pair_id="S5B21-PAIR-001",
        relevance_grade=2,
        supporting_quotation="running program's view of memory",
        confidence="HIGH",
        reviewer_notes="Directly defines an address space.",
        updated_at_utc="2026-11-19T10:15:00Z",
    )
    session.judgments["S5B21-PAIR-002"] = JudgmentRecord(
        pair_id="S5B21-PAIR-002",
        relevance_grade=1,
        supporting_quotation="fixed-size units called pages",
        confidence="MEDIUM",
        reviewer_notes="Related virtual memory background context.",
        updated_at_utc="2026-11-19T10:20:00Z",
    )
    session.judgments["S5B21-PAIR-003"] = JudgmentRecord(
        pair_id="S5B21-PAIR-003",
        relevance_grade=0,
        supporting_quotation="",
        confidence="HIGH",
        reviewer_notes="Unrelated to OS address spaces (synthetic grade 0 test).",
        updated_at_utc="2026-11-19T10:25:00Z",
    )
    return session


@pytest.mark.unit
def test_load_frozen_254_pair_blinded_pool() -> None:
    """Frozen 254-pair pool hydrates cleanly with 100% passage SHA-256 verification."""
    if not DEFAULT_BLANK_WORKBOOK_BACKUP.exists():
        pytest.skip("Private immutable blank workbook backup not present on disk.")

    before_sha = sha256_file(DEFAULT_BLANK_WORKBOOK_BACKUP)
    pool = load_blinded_pool(
        pool_path=DEFAULT_POOL_JSON,
        passage_source=DEFAULT_BLANK_WORKBOOK_BACKUP,
        verify_canonical_pool_sha=True,
    )
    assert pool.pool_sha256 == EXPECTED_POOL_SHA256
    assert len(pool.pairs) == EXPECTED_PAIR_COUNT
    assert len(pool.query_order) == EXPECTED_QUERY_COUNT
    for pair in pool.pairs:
        assert content_hash(pair.passage_text) == pair.passage_sha256
    assert sha256_file(DEFAULT_BLANK_WORKBOOK_BACKUP) == before_sha


@pytest.mark.unit
def test_quote_validation_rules(tmp_path: Path) -> None:
    """Exact verbatim quote required for grades 1/2; blank quote required for grade 0."""
    _, _, pool = _build_synthetic_pool(tmp_path)
    pair = pool.pairs_by_id["S5B21-PAIR-001"]

    assert is_exact_verbatim_quote("view of memory", pair.passage_text)
    assert not is_exact_verbatim_quote("view of physical memory", pair.passage_text)
    assert not is_exact_verbatim_quote("   ", pair.passage_text)

    bad_paraphrase = JudgmentRecord(
        pair_id=pair.pair_id,
        relevance_grade=2,
        supporting_quotation="program's view of physical memory",
        confidence="HIGH",
        reviewer_notes="Paraphrased quote should fail.",
    )
    res_bad = validate_pair_judgment(pair, bad_paraphrase)
    assert not res_bad.valid
    assert any("exact character-for-character" in err for err in res_bad.errors)

    bad_grade_zero = JudgmentRecord(
        pair_id=pair.pair_id,
        relevance_grade=0,
        supporting_quotation="view of memory",
        confidence="HIGH",
        reviewer_notes="Grade 0 with quote should fail.",
    )
    res_zero = validate_pair_judgment(pair, bad_grade_zero)
    assert not res_zero.valid
    assert any("strictly blank" in err for err in res_zero.errors)

    good_grade_zero = JudgmentRecord(
        pair_id=pair.pair_id,
        relevance_grade=0,
        supporting_quotation="",
        confidence="LOW",
        reviewer_notes="Irrelevant distractor.",
    )
    assert validate_pair_judgment(pair, good_grade_zero).complete


@pytest.mark.unit
def test_blinding_and_offline_invariants() -> None:
    """Rendered UI contains zero forbidden blinding tokens and zero external CDN URLs."""
    html = render_workbench_html()
    assert_blinding_clean(html, "unit_test_ui_html")

    lowered = html.lower()
    for token in FORBIDDEN_BLINDING_TOKENS:
        assert token not in lowered

    assert not re.search(r"https?://", html, re.IGNORECASE)

    with pytest.raises(PoolIntegrityError):
        assert_blinding_clean("Suggested by BM25 baseline_graph", "synthetic")


@pytest.mark.unit
def test_provenance_never_auto_signed_and_rejects_inconsistent(tmp_path: Path) -> None:
    """Fresh sessions start unsigned; unsigned or inconsistent provenance blocks export."""
    _, _, pool = _build_synthetic_pool(tmp_path)
    session_path = tmp_path / "session.json"
    fresh = load_or_create_session(pool, session_path)

    assert fresh.provenance.reviewer_identity_or_pseudonym == ""
    assert fresh.provenance.provenance_class == ""
    assert fresh.provenance.assistance_declaration == ""
    assert fresh.provenance.human_attestation_confirmed is False
    assert fresh.provenance.signed_by_human_at_utc == ""
    assert len(validate_provenance(fresh.provenance)) > 0

    completed = _complete_synthetic_session(pool)
    completed.provenance.human_attestation_confirmed = False
    completed.provenance.signed_by_human_at_utc = ""
    with pytest.raises(ExportValidationError):
        export_submission(
            pool,
            completed,
            output_dir=tmp_path / "exports",
            backup_dir=tmp_path / "backups",
        )

    inconsistent_indep = ProvenanceDeclaration(
        reviewer_identity_or_pseudonym="HUMAN_01",
        provenance_class=PROVENANCE_INDEPENDENT_HUMAN,
        assistance_declaration=ASSISTANCE_EXPOSED,
        human_attestation_confirmed=True,
        signed_by_human_at_utc="2026-11-19T12:00:00Z",
    )
    assert any(
        "NONE_INDEPENDENT_HUMAN" in err
        for err in validate_provenance(inconsistent_indep)
    )

    inconsistent_post = ProvenanceDeclaration(
        reviewer_identity_or_pseudonym="HUMAN_01",
        provenance_class=PROVENANCE_POST_AI_EXPOSURE,
        assistance_declaration=ASSISTANCE_NONE,
        human_attestation_confirmed=True,
        signed_by_human_at_utc="2026-11-19T12:00:00Z",
    )
    assert len(validate_provenance(inconsistent_post)) > 0

    inconsistent_ai = ProvenanceDeclaration(
        reviewer_identity_or_pseudonym="HUMAN_01",
        provenance_class=PROVENANCE_AI_ASSISTED,
        assistance_declaration=ASSISTANCE_NONE,
        human_attestation_confirmed=True,
        signed_by_human_at_utc="2026-11-19T12:00:00Z",
    )
    assert any(
        ASSISTANCE_AI_ASSISTED in err for err in validate_provenance(inconsistent_ai)
    )


@pytest.mark.unit
def test_private_path_guard_and_loopback_host() -> None:
    """Writes into tracked repo paths and non-loopback hosts are rejected."""
    tracked_path = REPO_ROOT / "research" / "forbidden_session.json"
    with pytest.raises(PrivatePathViolationError):
        ensure_private_path(tracked_path)

    private_path = REPO_ROOT / "data" / "annotation_local" / "s5c3" / "test_ok.json"
    assert ensure_private_path(private_path) == private_path.resolve()

    assert assert_loopback_host(ALLOWED_HOST) == "127.0.0.1"
    with pytest.raises(ValueError):
        assert_loopback_host("0.0.0.0")
    with pytest.raises(ValueError):
        assert_loopback_host("192.168.1.10")


@pytest.mark.unit
def test_save_resume_backup_and_export_integrity(tmp_path: Path) -> None:
    """Save/resume, timestamped backups, SHA-256 hashes, and JSON/CSV export work end-to-end."""
    _, _, pool = _build_synthetic_pool(tmp_path)
    session_path = tmp_path / "workbench" / "session.json"
    backup_dir = tmp_path / "workbench" / "backups"
    export_dir = tmp_path / "submissions"

    session = _complete_synthetic_session(pool)
    save_res = save_session(
        session, session_path, backup_dir=backup_dir, create_backup=True
    )
    assert save_res.session_path.exists()
    assert save_res.session_sha256 == sha256_file(save_res.session_path)
    assert save_res.backup_path is not None and save_res.backup_path.exists()
    assert save_res.backup_sha256 == sha256_file(save_res.backup_path)
    sidecar = save_res.backup_path.with_suffix(".json.sha256")
    assert sidecar.exists()
    assert save_res.backup_sha256 in sidecar.read_text(encoding="utf-8")

    resumed = load_or_create_session(pool, session_path)
    assert len(resumed.judgments) == 3
    assert resumed.provenance.reviewer_identity_or_pseudonym == "SYNTHETIC_HUMAN_TESTER"

    exp = export_submission(
        pool,
        resumed,
        output_dir=export_dir,
        backup_dir=backup_dir,
        filename_prefix="synthetic_rev_c",
    )
    assert exp.json_sha256 == sha256_file(exp.json_path)
    assert exp.csv_sha256 == sha256_file(exp.csv_path)
    assert exp.manifest_sha256 == sha256_file(exp.manifest_path)
    assert exp.backup_sha256 == sha256_file(exp.backup_path)

    exported_json = json.loads(exp.json_path.read_text(encoding="utf-8"))
    assert exported_json["schema_version"] == SUBMISSION_SCHEMA_VERSION
    assert exported_json["exported_pairs"] == 3
    assert exported_json["provenance"]["review_completion_status"] == "COMPLETED_3_OF_3"
    assert all(
        rec["passage_text_unchanged_verified"] is True
        for rec in exported_json["records"]
    )

    with exp.csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert tuple(reader.fieldnames or ()) == SUBMISSION_CSV_COLUMNS
        rows = list(reader)
        assert len(rows) == 3
        assert rows[0]["relevance_grade"] == "2"
        assert rows[2]["supporting_quotation"] == ""

    manifest = json.loads(exp.manifest_path.read_text(encoding="utf-8"))
    assert manifest["files"][exp.json_path.name]["sha256"] == exp.json_sha256
    assert manifest["files"][exp.csv_path.name]["sha256"] == exp.csv_sha256


@pytest.mark.unit
def test_http_endpoints_and_cli_workflow(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Flask test client and CLI subcommands support full annotation & export lifecycle."""
    pool_path, passages_path, pool = _build_synthetic_pool(tmp_path)
    session_path = tmp_path / "http_session.json"
    backup_dir = tmp_path / "http_backups"
    submissions_dir = tmp_path / "http_submissions"

    app = create_app(
        pool=pool,
        session_path=session_path,
        backup_dir=backup_dir,
        submissions_dir=submissions_dir,
    )
    client = app.test_client()

    resp_idx = client.get("/")
    assert resp_idx.status_code == HTTP_OK
    assert b"S5-C3 Blinded Human Annotation Workbench" in resp_idx.data

    resp_ready = client.get("/api/readiness")
    assert resp_ready.status_code == HTTP_OK
    assert resp_ready.get_json()["ready"] is True
    assert resp_ready.get_json()["host_policy"] == ALLOWED_HOST

    resp_pairs = client.get("/api/pairs")
    assert resp_pairs.status_code == HTTP_OK
    pairs_body = resp_pairs.get_json()
    assert len(pairs_body["pairs"]) == 3
    assert pairs_body["summary"]["completed_pairs"] == 0
    assert pairs_body["provenance"]["human_attestation_confirmed"] is False

    # Export must be blocked before completion and signing.
    resp_blocked = client.post("/api/export", json={"allow_partial": False})
    assert resp_blocked.status_code == HTTP_UNPROCESSABLE_ENTITY

    # Grade all 3 pairs via HTTP API.
    updates = [
        ("S5B21-PAIR-001", {"relevance_grade": 2, "supporting_quotation": "running program's view of memory", "confidence": "HIGH", "reviewer_notes": "Direct answer.", "flagged": False}),
        ("S5B21-PAIR-002", {"relevance_grade": 1, "supporting_quotation": "fixed-size units called pages", "confidence": "MEDIUM", "reviewer_notes": "Background context.", "flagged": True}),
        ("S5B21-PAIR-003", {"relevance_grade": 0, "supporting_quotation": "", "confidence": "HIGH", "reviewer_notes": "Distractor.", "flagged": False}),
    ]
    for pid, body in updates:
        resp_upd = client.post(f"/api/pairs/{pid}", json=body)
        assert resp_upd.status_code == HTTP_OK
        assert resp_upd.get_json()["validation"]["complete"] is True

    # Provenance saved WITHOUT attestation checkbox must NOT auto-sign.
    prov_base = {
        "reviewer_identity_or_pseudonym": "HTTP_HUMAN_01",
        "provenance_class": PROVENANCE_INDEPENDENT_HUMAN,
        "assistance_declaration": ASSISTANCE_NONE,
        "review_start_date_utc": "2026-11-19T12:00:00Z",
    }
    resp_prov_unsigned = client.post(
        "/api/provenance", json={**prov_base, "human_attestation_confirmed": False}
    )
    assert resp_prov_unsigned.status_code == HTTP_OK
    assert resp_prov_unsigned.get_json()["provenance_valid"] is False
    assert resp_prov_unsigned.get_json()["provenance"]["signed_by_human_at_utc"] == ""

    # Explicitly sign provenance.
    resp_prov_signed = client.post(
        "/api/provenance", json={**prov_base, "human_attestation_confirmed": True}
    )
    assert resp_prov_signed.status_code == HTTP_OK
    assert resp_prov_signed.get_json()["provenance_valid"] is True
    assert resp_prov_signed.get_json()["provenance"]["signed_by_human_at_utc"] != ""

    resp_bkp = client.post("/api/backup")
    assert resp_bkp.status_code == HTTP_OK
    assert Path(resp_bkp.get_json()["backup_path"]).exists()

    resp_exp = client.post(
        "/api/export", json={"allow_partial": False, "filename_prefix": "http_test"}
    )
    assert resp_exp.status_code == HTTP_OK
    exp_body = resp_exp.get_json()
    for key in ("json_path", "csv_path", "manifest_path"):
        assert Path(exp_body[key]).exists()

    # Verify CLI status, validate, backup, and export against the same session.
    common = [
        "--pool", str(pool_path), "--passage-source", str(passages_path),
        "--session", str(session_path), "--backup-dir", str(backup_dir),
    ]
    assert cli_mod.main(["status", *common]) == 0
    status_out = json.loads(capsys.readouterr().out)
    assert status_out["completed_pairs"] == 3
    assert status_out["flagged_pairs"] == 1

    assert cli_mod.main(["validate", *common]) == 0
    assert json.loads(capsys.readouterr().out)["valid_for_export"] is True

    assert cli_mod.main(["backup", *common]) == 0
    assert Path(json.loads(capsys.readouterr().out)["backup_path"]).exists()

    assert cli_mod.main(["export", *common, "--output-dir", str(submissions_dir), "--prefix", "cli_test"]) == 0
    cli_exp_out = json.loads(capsys.readouterr().out)
    assert Path(cli_exp_out["json_path"]).exists()
    assert Path(cli_exp_out["csv_path"]).exists()

    # Also verify direct backup helper and report helper.
    b_path, b_sha = create_timestamped_backup(
        load_or_create_session(pool, session_path), backup_dir=backup_dir
    )
    assert sha256_file(b_path) == b_sha
    assert validate_session(pool, load_or_create_session(pool, session_path)).valid_for_export
