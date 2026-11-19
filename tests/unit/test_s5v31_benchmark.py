"""Unit tests for the S5-v3.1 Stage D benchmark & blinded human audit package."""

from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = (
    REPO_ROOT / "research" / "s5-v3-1-oa-corpus-expansion" / "scripts"
)
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmark_v31.audit_validator import (  # noqa: E402
    validate_blank_workbook,
    validate_completed_submission,
)
from benchmark_v31.audit_workbook import (  # noqa: E402
    generate_private_audit_workbooks,
)
from benchmark_v31.builder import (  # noqa: E402
    QueryDraft,
    build_benchmark_manifest,
    write_manifest,
)
from benchmark_v31.constants import (  # noqa: E402
    ANSWERABILITY_STATUS_UNVERIFIED,
    CAT_CROSS_DOC_MULTI,
    CAT_NEGATIVE_CONTROL,
    CAT_SINGLE_PASSAGE,
    DEFAULT_CORPUS_V31_JSONL,
    DEFAULT_GRAPH_JSON,
    DEFAULT_MANIFEST_OUTPUT,
    DEFAULT_PRIVATE_AUDIT_DIR,
    DEFAULT_V21_SPECS_JSON,
    MAX_QUERY_COUNT,
    MIN_QUERY_COUNT,
    PROVENANCE_STATUS_PROPOSED,
    PROVISIONAL_STATUS,
    REGIME_RICH,
    REGIME_SPARSE,
    SPLIT_DEV,
    SPLIT_TEST,
    WORKBOOK_STATUS_SUBMITTED,
)
from benchmark_v31.corpus_index import load_corpus_metadata  # noqa: E402
from benchmark_v31.graph_anchors import GraphAnchorIndex  # noqa: E402
from benchmark_v31.leakage import load_v21_queries  # noqa: E402
from benchmark_v31.schema import (  # noqa: E402
    CorpusPassageMeta,
    EvidenceRef,
    QuerySpec,
    ShortcutCheck,
)
from benchmark_v31.validator import validate_benchmark  # noqa: E402

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def _sample_corpus() -> dict[str, CorpusPassageMeta]:
    return {
        "doc1::p001": CorpusPassageMeta(
            "doc1::p001", "doc1", "Operating Systems", 1, 1, "Ch 1", SHA_A
        ),
        "doc1::p002": CorpusPassageMeta(
            "doc1::p002", "doc1", "Operating Systems", None, None, "Ch 2", SHA_B
        ),
        "doc2::p001": CorpusPassageMeta(
            "doc2::p001", "doc2", "Databases", 4, 5, "Ch 3", SHA_C
        ),
    }


def _sample_graph() -> GraphAnchorIndex:
    return GraphAnchorIndex(
        {
            "linear_regression": ("linear regression",),
            "gradient_descent": ("gradient descent",),
            "acid_properties": ("acid properties",),
        }
    )


def _make_query(
    *,
    query_id: str = "Q-S5V31-01",
    query_text: str = "How does linear regression use gradient descent updates?",
    split: str = SPLIT_DEV,
    category: str = CAT_SINGLE_PASSAGE,
    category_status: str = PROVISIONAL_STATUS,
    necessity_status: str = PROVISIONAL_STATUS,
    regime: str = REGIME_RICH,
    evidence: tuple[EvidenceRef, ...] | None = None,
    min_set: tuple[str, ...] | None = None,
    answer_exists: bool = True,
    multi_doc: bool = False,
    shortcut_found: bool = True,
    provenance_status: str = PROVENANCE_STATUS_PROPOSED,
) -> QuerySpec:
    ev = (
        (
            EvidenceRef(
                "doc1::p001", "doc1", "Operating Systems", 1, 1, "Ch 1", SHA_A
            ),
        )
        if evidence is None
        else evidence
    )
    mset = ("doc1::p001",) if min_set is None else min_set
    return QuerySpec(
        query_id=query_id,
        query_text=query_text,
        split=split,
        category=category,
        category_status=category_status,
        domain="Operating Systems",
        domain_topic="OS / Scheduling",
        origin_v3_query_id=None,
        graph_anchor_regime=regime,
        graph_matched_concepts=("gradient_descent", "linear_regression"),
        exact_information_need="Explain parameter update rule.",
        supporting_evidence=ev,
        answer_exists_in_eligible_corpus=answer_exists,
        answerability_verification_status=ANSWERABILITY_STATUS_UNVERIFIED,
        minimum_required_evidence_set=mset,
        multi_document_truly_necessary=multi_doc,
        necessity_status=necessity_status,
        single_passage_shortcut_check=ShortcutCheck(
            shortcut_found=shortcut_found,
            rationale="Audited against corpus passages.",
        ),
        premise_audit_flags=(),
        provenance_status=provenance_status,
    )


@pytest.mark.unit
def test_schema_roundtrip_and_provisional_enforcement() -> None:
    """Valid QuerySpec round-trips; non-provisional status is rejected."""
    valid_q = _make_query()
    assert QuerySpec.from_dict(valid_q.to_dict()) == valid_q
    ok_rep = validate_benchmark(
        [valid_q],
        _sample_corpus(),
        _sample_graph(),
        enforce_size_bounds=False,
    )
    assert ok_rep.is_valid, ok_rep.issues

    bad_q = _make_query(
        query_id="Q-BAD-PROV",
        category_status="FINAL_APPROVED",
        necessity_status="FINAL_APPROVED",
        provenance_status="HUMAN_VERIFIED",
    )
    bad_rep = validate_benchmark(
        [bad_q],
        _sample_corpus(),
        _sample_graph(),
        enforce_size_bounds=False,
    )
    codes = {i.code for i in bad_rep.issues}
    assert "INVALID_CATEGORY_STATUS" in codes
    assert "INVALID_NECESSITY_STATUS" in codes
    assert "INVALID_PROVENANCE_STATUS" in codes


@pytest.mark.unit
def test_evidence_grounding_and_null_page_refs() -> None:
    """Non-PDF sources with page_start=None are valid; missing IDs fail."""
    web_q = _make_query(
        query_id="Q-WEB-01",
        evidence=(
            EvidenceRef(
                "doc1::p002",
                "doc1",
                "Operating Systems",
                None,
                None,
                "Ch 2",
                SHA_B,
            ),
        ),
        min_set=("doc1::p002",),
    )
    rep_ok = validate_benchmark(
        [web_q], _sample_corpus(), _sample_graph(), enforce_size_bounds=False
    )
    assert rep_ok.is_valid, rep_ok.issues

    ghost_q = _make_query(
        query_id="Q-GHOST",
        evidence=(
            EvidenceRef(
                "doc1::ghost", "doc1", "Operating Systems", 1, 1, "Ch 1", SHA_A
            ),
        ),
        min_set=("doc1::ghost",),
    )
    rep_bad = validate_benchmark(
        [ghost_q], _sample_corpus(), _sample_graph(), enforce_size_bounds=False
    )
    assert any(i.code == "PASSAGE_NOT_IN_CORPUS" for i in rep_bad.issues)


@pytest.mark.unit
def test_dev_test_isolation_and_multi_doc_consistency() -> None:
    """Shared evidence across dev/test and contradictory shortcut flags fail."""
    dev_q = _make_query(query_id="Q-DEV", split=SPLIT_DEV)
    test_q = _make_query(
        query_id="Q-TEST",
        query_text="Explain how linear regression applies gradient descent step updates.",
        split=SPLIT_TEST,
    )
    bad_cross = _make_query(
        query_id="Q-CROSS-BAD",
        query_text="Compare OS scheduling with database indexing methods.",
        category=CAT_CROSS_DOC_MULTI,
        regime=REGIME_SPARSE,
        evidence=(
            EvidenceRef(
                "doc1::p001", "doc1", "Operating Systems", 1, 1, "Ch 1", SHA_A
            ),
        ),
        min_set=("doc1::p001",),
        multi_doc=True,
        shortcut_found=True,
    )
    rep = validate_benchmark(
        [dev_q, test_q, bad_cross],
        _sample_corpus(),
        _sample_graph(),
        enforce_size_bounds=False,
    )
    codes = {i.code for i in rep.issues}
    assert "DEV_TEST_EVIDENCE_OVERLAP" in codes
    assert "CROSS_DOC_TOO_FEW_SOURCES" in codes
    assert "CROSS_DOC_SHORTCUT_FOUND" in codes


@pytest.mark.unit
def test_audit_workbook_generation_and_validators(tmp_path: Path) -> None:
    """Blinded workbook rejects pre-filled/unsigned approvals and grades."""
    corpus_path = tmp_path / "corpus.jsonl"
    corpus_path.write_text(
        json.dumps(
            {
                "passage_id": "doc1::p001",
                "source_doc_id": "doc1",
                "domain": "Operating Systems",
                "page_start": 1,
                "page_end": 1,
                "section_heading": "Ch 1",
                "passage_sha256": SHA_A,
                "text": "Private textbook passage excerpt for reviewer only.",
                "quality_flags": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    graph_path = tmp_path / "graph.json"
    graph_path.write_text(
        json.dumps(
            {
                "concepts": {
                    "linear_regression": {"name": "Linear Regression"},
                    "gradient_descent": {"name": "Gradient Descent"},
                }
            }
        ),
        encoding="utf-8",
    )
    drafts = [
        QueryDraft(
            query_id="Q-S5V31-01",
            query_text="How does linear regression use gradient descent?",
            split=SPLIT_DEV,
            category=CAT_SINGLE_PASSAGE,
            domain="Operating Systems",
            domain_topic="OS",
            exact_information_need="Explain update.",
            evidence_passage_ids=("doc1::p001",),
            minimum_required_evidence_ids=("doc1::p001",),
            answer_exists_in_eligible_corpus=True,
            multi_document_truly_necessary=False,
            shortcut_found=True,
            shortcut_rationale="Single passage suffices.",
        ),
        QueryDraft(
            query_id="Q-S5V31-02",
            query_text="What is the exact clock speed of an unreleased quantum CPU?",
            split=SPLIT_TEST,
            category=CAT_NEGATIVE_CONTROL,
            domain="Systems (Absent)",
            domain_topic="Absent",
            exact_information_need="Negative control.",
            evidence_passage_ids=(),
            minimum_required_evidence_ids=(),
            answer_exists_in_eligible_corpus=False,
            multi_document_truly_necessary=False,
            shortcut_found=False,
            shortcut_rationale="Absent from corpus.",
        ),
    ]
    manifest, rep = build_benchmark_manifest(
        drafts, corpus_path, graph_path, enforce_size_bounds=False
    )
    assert rep.is_valid, rep.issues
    manifest_path = tmp_path / "proposed.json"
    write_manifest(manifest, manifest_path)

    priv_dir = tmp_path / "private_audit"
    schema_path = tmp_path / "schema.json"
    info = generate_private_audit_workbooks(
        manifest_path, corpus_path, priv_dir, schema_path
    )
    assert Path(info["private_md"]).exists()
    assert Path(info["private_csv"]).exists()
    assert schema_path.exists()

    expected = frozenset({"Q-S5V31-01", "Q-S5V31-02"})
    blank = json.loads(Path(info["private_json"]).read_text(encoding="utf-8"))
    assert validate_blank_workbook(blank, expected).is_valid

    # Reject pre-filled decision on a blank workbook
    prefilled = copy.deepcopy(blank)
    prefilled["items"][0]["human_decision"] = "ACCEPT"
    assert any(
        i.code == "PREFILLED_HUMAN_DECISION"
        for i in validate_blank_workbook(prefilled, expected).issues
    )

    # Reject unsigned completed submission
    sub = copy.deepcopy(blank)
    sub["workbook_status"] = WORKBOOK_STATUS_SUBMITTED
    for item in sub["items"]:
        item["human_decision"] = "ACCEPT"
        item["human_necessity_verified"] = "YES"
        item["human_shortcut_found"] = "NO"
        item["human_negative_control_classification"] = (
            "NOT_APPLICABLE_POSITIVE_QUERY"
        )
    assert any(
        i.code == "UNSIGNED_ATTESTATION"
        for i in validate_completed_submission(sub, expected).issues
    )

    # Accept properly signed completed submission
    sub["reviewer_attestation"]["reviewer_id"] = "REV_HUMAN_1"
    sub["reviewer_attestation"]["reviewer_attestation_signed"] = True
    sub["reviewer_attestation"]["attestation_signer"] = "Dr. Reviewer"
    sub["reviewer_attestation"]["signed_timestamp_utc"] = "2026-11-19T12:00:00Z"
    assert validate_completed_submission(sub, expected).is_valid

    # Reject relevance grade field injection
    sub["items"][0]["relevance_grade"] = 2
    assert any(
        i.code == "FORBIDDEN_RELEVANCE_GRADE_FIELD"
        for i in validate_completed_submission(sub, expected).issues
    )


@pytest.mark.unit
def test_live_v31_manifest_and_private_workbook_if_built() -> None:
    """When Corpus v3.1 and v3.1 manifest exist, validate all invariants."""
    manifest_path = REPO_ROOT / DEFAULT_MANIFEST_OUTPUT
    corpus_path = REPO_ROOT / DEFAULT_CORPUS_V31_JSONL
    graph_path = REPO_ROOT / DEFAULT_GRAPH_JSON
    v21_path = REPO_ROOT / DEFAULT_V21_SPECS_JSON
    priv_json = (
        REPO_ROOT / DEFAULT_PRIVATE_AUDIT_DIR / "s5v31_query_audit_workbook.json"
    )

    if not manifest_path.exists() or not corpus_path.exists():
        pytest.skip("S5-v3.1 proposed manifest or Corpus v3.1 not yet built.")

    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert raw["provenance_status"] == PROVENANCE_STATUS_PROPOSED
    assert raw["category_and_necessity_status"] == PROVISIONAL_STATUS

    queries = [QuerySpec.from_dict(item) for item in raw["queries"]]
    assert MIN_QUERY_COUNT <= len(queries) <= MAX_QUERY_COUNT

    report = validate_benchmark(
        queries=queries,
        corpus_index=load_corpus_metadata(corpus_path),
        graph_index=GraphAnchorIndex.from_json_path(graph_path),
        v21_queries=load_v21_queries(v21_path),
        enforce_size_bounds=True,
    )
    assert report.is_valid, [
        f"{i.query_id}:{i.code}:{i.message}" for i in report.issues
    ]

    if priv_json.exists():
        expected = frozenset(q.query_id for q in queries)
        blank = json.loads(priv_json.read_text(encoding="utf-8"))
        res = validate_blank_workbook(blank, expected_query_ids=expected)
        assert res.is_valid, res.issues
