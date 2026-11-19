"""Unit tests for Module 4 — S5-C3 Negative-Control Human Verification.

Uses strictly synthetic fixtures under tmp_path; never touches real frozen corpus
or private human review files.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import threading
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

_SCRIPTS_DIR = (
    Path(__file__).resolve().parents[2]
    / "research"
    / "s5-c3-human-adjudication-prep"
    / "scripts"
)
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from neg_control import constants as const  # noqa: E402
from neg_control.corpus import CorpusEligibilityError, CorpusIndex  # noqa: E402
from neg_control.schema import (  # noqa: E402
    add_evidence_citation,
    create_blank_worksheet,
    export_markdown_report,
    get_query_record,
    load_worksheet,
    record_search_log,
    save_worksheet,
    sha256_file,
)
from neg_control.ui_server import NegativeControlAppState, create_local_server  # noqa: E402
from neg_control.validator import validate_worksheet  # noqa: E402
import s5_negative_control_verifier as cli  # noqa: E402


def _synthetic_raw_passages() -> list[dict[str, Any]]:
    """Build a synthetic corpus containing both eligible and ineligible passages."""
    return [
        {
            "passage_id": "papers/ostep_paging.pdf::chunk_001", "doc_id": "papers/ostep_paging.pdf",
            "chunk_id": "chunk_001", "page_number": 4, "section_title": "Multi-Level Page Tables",
            "text": (
                "Multi-level page tables reduce memory overhead by allocating page "
                "table directories on demand; walk latency depends on TLB miss rate."
            ),
        },
        {
            "passage_id": "papers/llama_systems.pdf::chunk_002", "doc_id": "papers/llama_systems.pdf",
            "chunk_id": "chunk_002", "page_number": 7, "section_title": "Training Efficiency",
            "text": (
                "QLoRA reduces memory footprint during finetuning of 65B models on "
                "single GPUs without reporting utility bills for LLaMA-3 405B."
            ),
        },
        {
            "passage_id": "papers/netsec_2024.pdf::chunk_003", "doc_id": "papers/netsec_2024.pdf",
            "chunk_id": "chunk_003", "page_number": 9, "section_title": "Switch Telemetry",
            "text": (
                "Graph-based anomaly detection monitors enterprise switch traffic; "
                "exact synthetic CVE-2025-99999 patched in firmware 17.9.4 is mentioned "
                "only in this synthetic test passage."
            ),
        },
        {
            "passage_id": "data_science_2019/index_2019_data-science.pdf::chunk_001",
            "doc_id": "data_science_2019/index_2019_data-science.pdf",
            "chunk_id": "chunk_001", "page_number": 400, "section_title": "Index",
            "text": "ARM Cortex-A78 latency 12 ns, 14, 15, 16, 17, 18, 19, 20",
        },
        {
            "passage_id": const.INVALID_PAGE_EXCLUDED_PASSAGE_ID,
            "doc_id": "doc_data_and_computer_communications",
            "chunk_id": "doc_data_and_computer_communications_p612_4",
            "page_number": 612, "section_title": "Erroneous Page",
            "text": "Cisco Catalyst 9300 buffer overflow invalid page stub.",
        },
        {
            "passage_id": "external/leaked_web_doc.pdf::chunk_001",
            "doc_id": "external/leaked_web_doc.pdf",
            "chunk_id": "chunk_001", "page_number": 1, "section_title": "External Web",
            "text": "ARM Cortex-A78 walk latency is 42 nanoseconds in external blog.",
            "corpus_eligibility_status": const.ELIGIBILITY_OUT_OF_CORPUS,
        },
    ]


def _synthetic_audit_data() -> dict[str, Any]:
    return {
        "queries": [
            {
                "query_id": "Q-S5B2-03", "legacy_query_id": "Q-S5A-03",
                "query_text": "What is the exact page table walk latency for ARM Cortex-A78?",
                "search_selected_candidate_passage_ids": [
                    "papers/ostep_paging.pdf::chunk_001",
                    "data_science_2019/index_2019_data-science.pdf::chunk_001",
                ],
            },
            {
                "query_id": "Q-S5B2-08", "legacy_query_id": "Q-S5A-08",
                "query_text": "What was the exact electric utility bill for LLaMA-3 405B?",
                "search_selected_candidate_passage_ids": ["papers/llama_systems.pdf::chunk_002"],
            },
            {
                "query_id": "Q-S5B2-11", "legacy_query_id": "Q-S5A-11",
                "query_text": "What is the 2025 Cisco Catalyst 9300 buffer overflow CVE?",
                "search_selected_candidate_passage_ids": ["papers/netsec_2024.pdf::chunk_003"],
            },
        ]
    }


def _build_synthetic_corpus() -> CorpusIndex:
    return CorpusIndex.from_raw_records(
        _synthetic_raw_passages(),
        corpus_version="synthetic_s5a_eval_corpus_v1",
    )


def _populate_valid_human_provenance(record: dict[str, Any]) -> None:
    record["human_provenance"] = {
        "verifier_id": "HUMAN_VERIFIER_SYNTHETIC_01",
        "provenance_class": const.PROVENANCE_INDEPENDENT_HUMAN,
        "human_attestation_confirmed": True,
        "human_attestation_text": "I personally verified all passages in the frozen eligible corpus.",
        "ai_assistance_disclosure": "NONE_INDEPENDENT_HUMAN",
        "verification_date_utc": "2026-11-19T12:15:00Z",
    }


def _populate_complete_valid_worksheet(corpus: CorpusIndex) -> dict[str, Any]:
    """Build a valid synthetic worksheet exercising multiple classification states."""
    ws = create_blank_worksheet(corpus, audit_data=_synthetic_audit_data(), is_synthetic=True)

    q03 = get_query_record(ws, "Q-S5B2-03")
    q03["hydrated_candidates"][0]["contains_answer"] = "NO"
    q03["hydrated_candidates"][0]["inspection_note"] = "Paging background only; no Cortex-A78."
    q03["checked_passage_ids"] = ["papers/ostep_paging.pdf::chunk_001"]
    q03["human_answerability_classification"] = const.CLASS_NO_ANSWER_IN_FROZEN_CORPUS
    q03["d1_evaluation_impact"] = const.IMPACT_RETAIN_AS_NEGATIVE
    q03["external_factual_premise_assessment"] = const.PREMISE_VERIFIED_REAL
    q03["corpus_scope_checked"] = const.SCOPE_FULL_CORPUS_SEARCH
    q03["verification_rationale"] = (
        "Searched entire eligible corpus for ARM, Cortex, A78, and nanosecond; zero matches."
    )
    _populate_valid_human_provenance(q03)

    q08 = get_query_record(ws, "Q-S5B2-08")
    q08["hydrated_candidates"][0]["contains_answer"] = "NO"
    q08["hydrated_candidates"][0]["inspection_note"] = "Mentions QLoRA only; no utility bill."
    q08["checked_passage_ids"] = ["papers/llama_systems.pdf::chunk_002"]
    q08["human_answerability_classification"] = const.CLASS_AMBIGUOUS_OR_UNSUPPORTED
    q08["d1_evaluation_impact"] = const.IMPACT_EXCLUDE_AMBIGUOUS
    q08["external_factual_premise_assessment"] = const.PREMISE_UNVERIFIED_OR_UNREPORTED
    q08["corpus_scope_checked"] = const.SCOPE_CANDIDATES_AND_INVENTORY
    q08["verification_rationale"] = (
        "No corpus passage reports LLaMA-3 405B utility bills, and external figure is unreported."
    )
    q08["revision_or_exclusion_notes"] = (
        "Exclude from standard answerable averages due to unreported external utility-bill premise."
    )
    _populate_valid_human_provenance(q08)

    q11 = get_query_record(ws, "Q-S5B2-11")
    q11["hydrated_candidates"][0]["contains_answer"] = "YES"
    q11["hydrated_candidates"][0]["inspection_note"] = "Contains synthetic CVE-2025-99999."
    add_evidence_citation(
        ws,
        corpus,
        query_id="Q-S5B2-11",
        passage_id="papers/netsec_2024.pdf::chunk_003",
        verbatim_excerpt="exact synthetic CVE-2025-99999 patched in firmware 17.9.4",
        search_query_used="CVE-2025-99999",
        note="Synthetic test evidence proving answerability.",
    )
    q11["human_answerability_classification"] = const.CLASS_ANSWERABLE_IN_FROZEN_CORPUS
    q11["d1_evaluation_impact"] = const.IMPACT_RECLASSIFY_ANSWERABLE
    q11["external_factual_premise_assessment"] = const.PREMISE_SYNTHETIC_OR_FALSE
    q11["corpus_scope_checked"] = const.SCOPE_FULL_CORPUS_SEARCH
    q11["verification_rationale"] = (
        "Found direct synthetic CVE passage in eligible corpus; reclassify for D1."
    )
    _populate_valid_human_provenance(q11)
    return ws


@pytest.mark.unit
def test_corpus_restriction_excludes_ineligible_and_out_of_corpus() -> None:
    corpus = _build_synthetic_corpus()
    assert corpus.passage_count == 3
    assert corpus.document_count == 3
    assert corpus.excluded_count == 3

    assert corpus.get_eligibility_status("papers/ostep_paging.pdf::chunk_001") == const.ELIGIBILITY_ELIGIBLE
    assert (
        corpus.get_eligibility_status("data_science_2019/index_2019_data-science.pdf::chunk_001")
        == const.ELIGIBILITY_EXCLUDED_INDEX_ONLY
    )
    assert (
        corpus.get_eligibility_status(const.INVALID_PAGE_EXCLUDED_PASSAGE_ID)
        == const.ELIGIBILITY_EXCLUDED_INVALID_PAGE
    )
    assert (
        corpus.get_eligibility_status("external/leaked_web_doc.pdf::chunk_001")
        == const.ELIGIBILITY_OUT_OF_CORPUS
    )
    assert corpus.get_eligibility_status("nonexistent::chunk_999") == const.ELIGIBILITY_OUT_OF_CORPUS

    # Both Cortex-A78 occurrences are ineligible -> MUST return 0 hits
    res = corpus.search("Cortex-A78", mode=const.SEARCH_MODE_SUBSTRING)
    assert res.total_hits == 0
    assert res.hits == ()

    with pytest.raises(CorpusEligibilityError):
        corpus.inspect_passage("data_science_2019/index_2019_data-science.pdf::chunk_001")
    with pytest.raises(CorpusEligibilityError):
        corpus.inspect_passage(const.INVALID_PAGE_EXCLUDED_PASSAGE_ID)
    with pytest.raises(CorpusEligibilityError):
        corpus.get_document_passages("external/leaked_web_doc.pdf")
    with pytest.raises(CorpusEligibilityError):
        corpus.search("latency", doc_id="external/leaked_web_doc.pdf")


@pytest.mark.unit
def test_manifest_allowlist_rejects_unlisted_documents() -> None:
    corpus = CorpusIndex.from_raw_records(
        _synthetic_raw_passages(),
        allowed_doc_ids=frozenset({"papers/ostep_paging.pdf"}),
    )
    assert corpus.passage_count == 1
    assert (
        corpus.get_eligibility_status("papers/llama_systems.pdf::chunk_002")
        == const.ELIGIBILITY_EXCLUDED_MANIFEST
    )


@pytest.mark.unit
def test_search_modes_and_evidence_provenance() -> None:
    corpus = _build_synthetic_corpus()

    sub = corpus.search("TLB miss", mode=const.SEARCH_MODE_SUBSTRING)
    assert sub.total_hits == 1
    hit = sub.hits[0]
    assert hit.passage_id == "papers/ostep_paging.pdf::chunk_001"
    assert hit.corpus_eligibility_status == const.ELIGIBILITY_ELIGIBLE
    assert hit.matched_excerpt in hit.full_text

    tok = corpus.search("QLoRA utility", mode=const.SEARCH_MODE_TOKENS)
    assert tok.total_hits == 1
    assert tok.hits[0].passage_id == "papers/llama_systems.pdf::chunk_002"

    reg = corpus.search(r"CVE-2025-\d+", mode=const.SEARCH_MODE_REGEX)
    assert reg.total_hits == 1
    assert reg.hits[0].passage_id == "papers/netsec_2024.pdf::chunk_003"


@pytest.mark.unit
def test_blank_worksheet_never_auto_classifies_or_auto_signs() -> None:
    corpus = _build_synthetic_corpus()
    ws = create_blank_worksheet(corpus, audit_data=_synthetic_audit_data(), is_synthetic=True)

    for q in ws["queries"]:
        assert q["human_answerability_classification"] is None
        assert q["d1_evaluation_impact"] is None
        assert q["external_factual_premise_assessment"] is None
        assert q["corpus_scope_checked"] is None
        assert q["verification_rationale"] == ""
        prov = q["human_provenance"]
        assert prov["verifier_id"] == ""
        assert prov["provenance_class"] is None
        assert prov["human_attestation_confirmed"] is False
        for cand in q["hydrated_candidates"]:
            assert cand["contains_answer"] is None
            assert cand["corpus_eligibility_status"] == const.ELIGIBILITY_ELIGIBLE

    q03 = get_query_record(ws, "Q-S5B2-03")
    assert [c["passage_id"] for c in q03["hydrated_candidates"]] == [
        "papers/ostep_paging.pdf::chunk_001"
    ]

    report = validate_worksheet(ws, corpus)
    assert report.valid is False
    assert report.ready_for_d1 is False
    codes = {issue.code for issue in report.issues}
    assert "MISSING_OR_INVALID_CLASSIFICATION" in codes
    assert "UNSIGNED_HUMAN_ATTESTATION" in codes
    assert "UNINSPECTED_HYDRATED_CANDIDATES" in codes


@pytest.mark.unit
def test_valid_mixed_classifications_and_d1_readiness() -> None:
    corpus = _build_synthetic_corpus()
    ws = _populate_complete_valid_worksheet(corpus)
    report = validate_worksheet(ws, corpus)
    assert report.valid is True
    assert report.ready_for_d1 is True
    assert report.error_count == 0


@pytest.mark.unit
def test_selected_passages_only_and_revision_requiring_states() -> None:
    corpus = _build_synthetic_corpus()
    ws = _populate_complete_valid_worksheet(corpus)

    q03 = get_query_record(ws, "Q-S5B2-03")
    q03["human_answerability_classification"] = const.CLASS_NO_ANSWER_IN_SELECTED_PASSAGES
    q03["d1_evaluation_impact"] = const.IMPACT_HOLD_UNVERIFIED
    q03["corpus_scope_checked"] = const.SCOPE_CANDIDATES_ONLY

    q11 = get_query_record(ws, "Q-S5B2-11")
    q11["human_answerability_classification"] = const.CLASS_REQUIRES_REVISION
    q11["d1_evaluation_impact"] = const.IMPACT_EXCLUDE_REVISION
    q11["revision_or_exclusion_notes"] = "Malformed synthetic CVE; exclude and revise in v2.2."

    report = validate_worksheet(ws, corpus)
    assert report.valid is True
    assert report.ready_for_d1 is False

    q11["revision_or_exclusion_notes"] = ""
    report_missing = validate_worksheet(ws, corpus)
    assert report_missing.valid is False
    assert any(i.code == "MISSING_REVISION_OR_EXCLUSION_NOTES" for i in report_missing.issues)


@pytest.mark.unit
def test_guardrails_reject_invalid_scope_evidence_provenance_and_hash() -> None:
    corpus = _build_synthetic_corpus()

    ws = _populate_complete_valid_worksheet(corpus)
    get_query_record(ws, "Q-S5B2-03")["corpus_scope_checked"] = const.SCOPE_CANDIDATES_ONLY
    assert any(
        i.code == "INSUFFICIENT_SCOPE_FOR_CORPUS_WIDE_NEGATIVE"
        for i in validate_worksheet(ws, corpus).issues
    )

    ws2 = _populate_complete_valid_worksheet(corpus)
    get_query_record(ws2, "Q-S5B2-11")["supporting_evidence"] = []
    assert any(
        i.code == "MISSING_ANSWERABLE_EVIDENCE" for i in validate_worksheet(ws2, corpus).issues
    )

    ws3 = _populate_complete_valid_worksheet(corpus)
    get_query_record(ws3, "Q-S5B2-11")["supporting_evidence"].append(
        {
            "passage_id": "external/leaked_web_doc.pdf::chunk_001",
            "doc_id": "external/leaked_web_doc.pdf",
            "verbatim_excerpt": "42 nanoseconds",
            "search_query_used": "42 nanoseconds",
            "corpus_eligibility_status": const.ELIGIBILITY_ELIGIBLE,
        }
    )
    assert any(i.code == "OUT_OF_CORPUS_EVIDENCE" for i in validate_worksheet(ws3, corpus).issues)

    ws4 = _populate_complete_valid_worksheet(corpus)
    get_query_record(ws4, "Q-S5B2-08")["human_provenance"]["provenance_class"] = (
        const.PROVENANCE_AI_ASSISTED
    )
    assert any(
        i.code == "AI_ASSISTED_PROVENANCE_DISALLOWED"
        for i in validate_worksheet(ws4, corpus).issues
    )

    ws5 = _populate_complete_valid_worksheet(corpus)
    ws5["corpus_sha256"] = "0" * 64
    assert any(i.code == "CORPUS_SHA256_MISMATCH" for i in validate_worksheet(ws5, corpus).issues)


@pytest.mark.unit
def test_save_resume_backup_hash_and_markdown_export(tmp_path: Path) -> None:
    corpus = _build_synthetic_corpus()
    ws = _populate_complete_valid_worksheet(corpus)
    record_search_log(ws, "Q-S5B2-03", corpus.search("TLB", mode=const.SEARCH_MODE_SUBSTRING))

    ws_path = tmp_path / "private_ws.json"
    manifest = save_worksheet(ws, ws_path, backup_dir=tmp_path / "backups")

    backup_path = Path(manifest["backup_path"])
    assert ws_path.exists() and backup_path.exists()
    assert manifest["worksheet_sha256"] == sha256_file(ws_path)
    assert manifest["backup_sha256"] == sha256_file(backup_path)
    assert Path(f"{ws_path}.sha256.json").exists()

    reloaded = load_worksheet(ws_path)
    assert len(get_query_record(reloaded, "Q-S5B2-03")["search_audit_log"]) == 1

    md_path = tmp_path / "export.md"
    exp = export_markdown_report(reloaded, md_path)
    assert exp["export_sha256"] == sha256_file(md_path)
    assert "[SYNTHETIC]" in md_path.read_text(encoding="utf-8")


@pytest.mark.unit
def test_local_ui_server_loopback_only_and_endpoints(tmp_path: Path) -> None:
    corpus = _build_synthetic_corpus()
    ws = _populate_complete_valid_worksheet(corpus)
    ws_path = tmp_path / "ui_ws.json"
    state = NegativeControlAppState(
        corpus=corpus,
        worksheet=ws,
        worksheet_path=ws_path,
        backup_dir=tmp_path / "backups",
    )

    with pytest.raises(ValueError, match="non-loopback"):
        create_local_server(state, host="0.0.0.0", port=0)

    server = create_local_server(state, host=const.LOCALHOST_BIND, port=0)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f"http://{const.LOCALHOST_BIND}:{port}"
        with urlopen(f"{base}/") as resp:
            html = resp.read().decode("utf-8")
            assert resp.status == 200
            assert "Offline 127.0.0.1" in html
            assert "http://" not in html and "https://" not in html

        with urlopen(f"{base}/api/state") as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            assert payload["validation"]["valid"] is True
            assert len(payload["documents"]) == 3

        with urlopen(f"{base}/api/passage?passage_id=papers/ostep_paging.pdf::chunk_001") as resp:
            assert resp.status == 200

        with pytest.raises(HTTPError) as exc_info:
            urlopen(
                f"{base}/api/passage?passage_id="
                "data_science_2019/index_2019_data-science.pdf::chunk_001"
            )
        assert exc_info.value.code == 403

        req = Request(
            f"{base}/api/search",
            data=json.dumps({"query": "Cortex-A78", "query_id": "Q-S5B2-03"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req) as resp:
            assert json.loads(resp.read().decode("utf-8"))["result"]["total_hits"] == 0

        save_req = Request(
            f"{base}/api/save",
            data=json.dumps({"worksheet": ws}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(save_req) as resp:
            assert json.loads(resp.read().decode("utf-8"))["validation"]["valid"] is True
            assert ws_path.exists()
    finally:
        server.shutdown()
        server.server_close()


@pytest.mark.unit
def test_cli_end_to_end_on_synthetic_fixture(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    corpus_json = tmp_path / "synthetic_corpus.json"
    corpus_json.write_text(
        json.dumps(
            {"corpus_version": "synthetic_s5a_eval_corpus_v1", "passages": _synthetic_raw_passages()}
        ),
        encoding="utf-8",
    )
    audit_json = tmp_path / "synthetic_audit.json"
    audit_json.write_text(json.dumps(_synthetic_audit_data()), encoding="utf-8")
    ws_path = tmp_path / "ws.json"
    md_path = tmp_path / "ws.md"

    common = ["--corpus-json", str(corpus_json), "--no-manifest-filter"]
    assert cli.main(["init", *common, "--audit-json", str(audit_json), "--output", str(ws_path), "--synthetic"]) == 0
    capsys.readouterr()

    assert cli.main(["validate", *common, "--worksheet", str(ws_path)]) == 1
    capsys.readouterr()

    assert cli.main(["search", *common, "--query", "QLoRA", "--worksheet", str(ws_path), "--query-id", "Q-S5B2-08"]) == 0
    assert json.loads(capsys.readouterr().out)["total_hits"] == 1

    assert cli.main(["inspect", *common, "--passage-id", const.INVALID_PAGE_EXCLUDED_PASSAGE_ID]) == 2
    capsys.readouterr()

    assert cli.main(["export", *common, "--worksheet", str(ws_path), "--output-md", str(md_path)]) == 0
    assert md_path.exists()
