"""Unit tests for the S5-v3 Module C proposed query benchmark and validator."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "research" / "s5-v3-benchmark-expansion" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from benchmark_v3.builder import QueryDraft, build_benchmark_manifest  # noqa: E402
from benchmark_v3.constants import (  # noqa: E402
    ANSWERABILITY_STATUS_UNVERIFIED,
    CAT_CROSS_DOC_MULTI,
    CAT_NEGATIVE_CONTROL,
    CAT_SAME_DOC_MULTI,
    CAT_SINGLE_PASSAGE,
    DEFAULT_CORPUS_JSONL,
    DEFAULT_GRAPH_JSON,
    DEFAULT_MANIFEST_OUTPUT,
    DEFAULT_V21_SPECS_JSON,
    DEFERRED_CS_DOMAINS,
    DEFERRED_DOMAIN_STATUS,
    MAX_QUERY_COUNT,
    MIN_QUERY_COUNT,
    PROVENANCE_STATUS_PROPOSED,
    REGIME_RICH,
    REGIME_SPARSE,
    SPLIT_DEV,
    SPLIT_TEST,
)
from benchmark_v3.corpus_index import load_corpus_metadata  # noqa: E402
from benchmark_v3.graph_anchors import GraphAnchorIndex  # noqa: E402
from benchmark_v3.leakage import load_v21_queries  # noqa: E402
from benchmark_v3.schema import (  # noqa: E402
    CorpusPassageMeta,
    EvidenceRef,
    QuerySpec,
    ShortcutCheck,
)
from benchmark_v3.validator import validate_benchmark  # noqa: E402

SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


def _sample_corpus() -> dict[str, CorpusPassageMeta]:
    return {
        "doc1::p001": CorpusPassageMeta("doc1::p001", "doc1", 1, 1, SHA_A),
        "doc1::p002": CorpusPassageMeta("doc1::p002", "doc1", 2, 3, SHA_B),
        "doc2::p001": CorpusPassageMeta("doc2::p001", "doc2", 5, 5, SHA_C),
        "doc2::p002": CorpusPassageMeta("doc2::p002", "doc2", 6, 7, SHA_D),
    }


def _sample_graph() -> GraphAnchorIndex:
    return GraphAnchorIndex(
        {
            "linear_regression": ("linear regression",),
            "gradient_descent": ("gradient descent",),
            "gaussian_distribution": ("gaussian distribution",),
        }
    )


def _make_query(
    *,
    query_id: str = "Q-S5V3-01",
    query_text: str = "How does linear regression use gradient descent updates?",
    split: str = SPLIT_DEV,
    category: str = CAT_SINGLE_PASSAGE,
    regime: str = REGIME_RICH,
    evidence: tuple[EvidenceRef, ...] | None = None,
    min_set: tuple[str, ...] | None = None,
    answer_exists: bool = True,
    answerability_status: str = ANSWERABILITY_STATUS_UNVERIFIED,
    multi_doc: bool = False,
    shortcut_found: bool = True,
    shortcut_rationale: str = "Single passage directly answers this query.",
    provenance_status: str = PROVENANCE_STATUS_PROPOSED,
) -> QuerySpec:
    ev = (
        (EvidenceRef("doc1::p001", "doc1", 1, 1, SHA_A),)
        if evidence is None
        else evidence
    )
    mset = ("doc1::p001",) if min_set is None else min_set
    return QuerySpec(
        query_id=query_id,
        query_text=query_text,
        split=split,
        category=category,
        domain_topic="Machine Learning",
        graph_anchor_regime=regime,
        graph_matched_concepts=("gradient_descent", "linear_regression"),
        exact_information_need="Explain parameter updates in linear regression.",
        supporting_evidence=ev,
        answer_exists_in_eligible_corpus=answer_exists,
        answerability_verification_status=answerability_status,
        minimum_required_evidence_set=mset,
        multi_document_truly_necessary=multi_doc,
        single_passage_shortcut_check=ShortcutCheck(
            shortcut_found=shortcut_found,
            rationale=shortcut_rationale,
        ),
        premise_audit_flags=(),
        provenance_status=provenance_status,
    )


@pytest.mark.unit
def test_schema_roundtrip_and_valid_query() -> None:
    """Valid QuerySpec round-trips cleanly and passes validation."""
    q = _make_query()
    restored = QuerySpec.from_dict(q.to_dict())
    assert restored == q

    report = validate_benchmark(
        queries=[restored],
        corpus_index=_sample_corpus(),
        graph_index=_sample_graph(),
        enforce_size_bounds=False,
    )
    assert report.is_valid, report.issues


@pytest.mark.unit
def test_evidence_existence_and_page_ref_validation() -> None:
    """Nonexistent passages, bad page ranges, and mismatched hashes fail."""
    bad_missing = _make_query(
        query_id="Q-BAD-1",
        evidence=(EvidenceRef("doc1::ghost", "doc1", 1, 1, SHA_A),),
        min_set=("doc1::ghost",),
    )
    bad_page = _make_query(
        query_id="Q-BAD-2",
        evidence=(EvidenceRef("doc1::p001", "doc1", 9, 8, SHA_A),),
        min_set=("doc1::p001",),
    )
    bad_sha = _make_query(
        query_id="Q-BAD-3",
        evidence=(EvidenceRef("doc1::p001", "doc1", 1, 1, SHA_B),),
        min_set=("doc1::p001",),
    )

    report = validate_benchmark(
        queries=[bad_missing, bad_page, bad_sha],
        corpus_index=_sample_corpus(),
        graph_index=_sample_graph(),
        enforce_size_bounds=False,
    )
    codes = {issue.code for issue in report.issues}
    assert "PASSAGE_NOT_IN_CORPUS" in codes
    assert "INVALID_PAGE_RANGE" in codes
    assert "PAGE_REF_MISMATCH" in codes
    assert "PASSAGE_SHA256_MISMATCH" in codes


@pytest.mark.unit
def test_dev_test_split_isolation() -> None:
    """Exact/near duplicate queries or shared evidence across splits fail."""
    dev_q = _make_query(
        query_id="Q-DEV-1",
        query_text="How does linear regression optimize squared loss via gradient descent?",
        split=SPLIT_DEV,
        evidence=(EvidenceRef("doc1::p001", "doc1", 1, 1, SHA_A),),
        min_set=("doc1::p001",),
    )
    test_dup = _make_query(
        query_id="Q-TEST-1",
        query_text="How does linear regression optimize squared loss using gradient descent?",
        split=SPLIT_TEST,
        evidence=(EvidenceRef("doc1::p001", "doc1", 1, 1, SHA_A),),
        min_set=("doc1::p001",),
    )

    report = validate_benchmark(
        queries=[dev_q, test_dup],
        corpus_index=_sample_corpus(),
        graph_index=_sample_graph(),
        enforce_size_bounds=False,
    )
    codes = {issue.code for issue in report.issues}
    assert "DEV_TEST_NEAR_DUPLICATE" in codes
    assert "DEV_TEST_EVIDENCE_OVERLAP" in codes


@pytest.mark.unit
def test_v21_reuse_guard() -> None:
    """Reusing a frozen v2.1 query ID or text fails validation."""
    v21 = [
        (
            "Q-S5B2-04",
            "What is the computational formula for Scaled Dot-Product Attention?",
        )
    ]
    reused = _make_query(
        query_id="Q-S5B2-04",
        query_text="What is the computational formula for Scaled Dot-Product Attention?",
        regime=REGIME_SPARSE,
    )
    report = validate_benchmark(
        queries=[reused],
        corpus_index=_sample_corpus(),
        graph_index=_sample_graph(),
        v21_queries=v21,
        enforce_size_bounds=False,
    )
    codes = {issue.code for issue in report.issues}
    assert "V21_ID_REUSE" in codes
    assert "V21_EXACT_TEXT_REUSE" in codes


@pytest.mark.unit
def test_shortcut_and_necessity_consistency() -> None:
    """Cross-doc and same-doc multi-passage invariants are strictly enforced."""
    bad_cross = _make_query(
        query_id="Q-CROSS-BAD",
        category=CAT_CROSS_DOC_MULTI,
        evidence=(
            EvidenceRef("doc1::p001", "doc1", 1, 1, SHA_A),
            EvidenceRef("doc1::p002", "doc1", 2, 3, SHA_B),
        ),
        min_set=("doc1::p001", "doc1::p002"),
        multi_doc=True,
        shortcut_found=True,
    )
    good_cross = _make_query(
        query_id="Q-CROSS-OK",
        query_text="Compare linear regression and gradient descent across both texts.",
        category=CAT_CROSS_DOC_MULTI,
        evidence=(
            EvidenceRef("doc1::p001", "doc1", 1, 1, SHA_A),
            EvidenceRef("doc2::p001", "doc2", 5, 5, SHA_C),
        ),
        min_set=("doc1::p001", "doc2::p001"),
        multi_doc=True,
        shortcut_found=False,
        shortcut_rationale="Requires combining doc1 derivation with doc2 optimization.",
    )
    bad_same = _make_query(
        query_id="Q-SAME-BAD",
        query_text="Synthesize linear regression with gradient descent in one book.",
        category=CAT_SAME_DOC_MULTI,
        evidence=(EvidenceRef("doc1::p001", "doc1", 1, 1, SHA_A),),
        min_set=("doc1::p001",),
        multi_doc=False,
        shortcut_found=False,
    )

    report = validate_benchmark(
        queries=[bad_cross, good_cross, bad_same],
        corpus_index=_sample_corpus(),
        graph_index=_sample_graph(),
        enforce_size_bounds=False,
    )
    by_qid = {i.query_id: [] for i in report.issues}
    for issue in report.issues:
        by_qid[issue.query_id].append(issue.code)

    assert "CROSS_DOC_TOO_FEW_SOURCES" in by_qid["Q-CROSS-BAD"]
    assert "CROSS_DOC_SHORTCUT_FOUND" in by_qid["Q-CROSS-BAD"]
    assert "Q-CROSS-OK" not in by_qid
    assert "SAME_DOC_MULTI_TOO_FEW_PASSAGES" in by_qid["Q-SAME-BAD"]


@pytest.mark.unit
def test_negative_control_invariants() -> None:
    """Negative controls must have answer_exists=False and empty evidence."""
    good_neg = _make_query(
        query_id="Q-NEG-OK",
        query_text="What is the exact clock frequency of the Apollo guidance computer?",
        category=CAT_NEGATIVE_CONTROL,
        regime=REGIME_SPARSE,
        evidence=(),
        min_set=(),
        answer_exists=False,
        multi_doc=False,
        shortcut_found=False,
        shortcut_rationale="Topic absent from all eligible corpus documents.",
    )
    bad_neg = _make_query(
        query_id="Q-NEG-BAD",
        query_text="What is the exact page table latency of an unreleased CPU?",
        category=CAT_NEGATIVE_CONTROL,
        regime=REGIME_SPARSE,
        evidence=(EvidenceRef("doc1::p001", "doc1", 1, 1, SHA_A),),
        min_set=("doc1::p001",),
        answer_exists=True,
        multi_doc=True,
        shortcut_found=False,
    )

    report = validate_benchmark(
        queries=[good_neg, bad_neg],
        corpus_index=_sample_corpus(),
        graph_index=_sample_graph(),
        enforce_size_bounds=False,
    )
    bad_codes = {i.code for i in report.issues if i.query_id == "Q-NEG-BAD"}
    good_issues = [i for i in report.issues if i.query_id == "Q-NEG-OK"]
    assert not good_issues
    assert "NEG_CONTROL_MARKED_ANSWERABLE" in bad_codes
    assert "NEG_CONTROL_HAS_EVIDENCE" in bad_codes
    assert "NEG_CONTROL_MULTI_DOC" in bad_codes


@pytest.mark.unit
def test_human_verification_status_enforcement() -> None:
    """Claiming human verification on AI-proposed candidates must fail."""
    forged = _make_query(
        query_id="Q-FORGED",
        provenance_status="HUMAN_VERIFIED_GOLD",
        answerability_status="HUMAN_VERIFIED",
    )
    report = validate_benchmark(
        queries=[forged],
        corpus_index=_sample_corpus(),
        graph_index=_sample_graph(),
        enforce_size_bounds=False,
    )
    codes = {i.code for i in report.issues}
    assert "INVALID_PROVENANCE_STATUS" in codes
    assert "INVALID_ANSWERABILITY_STATUS" in codes


@pytest.mark.unit
def test_builder_grounds_drafts_from_jsonl(tmp_path: Path) -> None:
    """Builder dynamically grounds drafts against JSONL and graph JSON."""
    corpus_file = tmp_path / "corpus.jsonl"
    corpus_file.write_text(
        json.dumps(
            {
                "passage_id": "doc1::p001",
                "source_doc_id": "doc1",
                "page_start": 3,
                "page_end": 4,
                "passage_sha256": SHA_A,
                "text": "Private passage text that must never be exported.",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    graph_file = tmp_path / "graph.json"
    graph_file.write_text(
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
    draft = QueryDraft(
        query_id="Q-BUILD-01",
        query_text="How does linear regression use gradient descent?",
        split=SPLIT_DEV,
        category=CAT_SINGLE_PASSAGE,
        domain_topic="Machine Learning",
        exact_information_need="Explain gradient descent for linear regression.",
        evidence_passage_ids=("doc1::p001",),
        minimum_required_evidence_ids=("doc1::p001",),
        answer_exists_in_eligible_corpus=True,
        multi_document_truly_necessary=False,
        shortcut_found=True,
        shortcut_rationale="Single passage directly states the update rule.",
    )
    manifest, report = build_benchmark_manifest(
        drafts=[draft],
        corpus_jsonl_path=corpus_file,
        graph_json_path=graph_file,
        enforce_size_bounds=False,
    )
    assert report.is_valid, report.issues
    assert manifest["provenance_status"] == PROVENANCE_STATUS_PROPOSED
    assert manifest["queries"][0]["graph_anchor_regime"] == REGIME_RICH
    assert "Private passage text" not in json.dumps(manifest)


@pytest.mark.unit
def test_live_proposed_manifest_if_built() -> None:
    """When Corpus v3 and proposed manifest exist, enforce full invariants."""
    manifest_path = REPO_ROOT / DEFAULT_MANIFEST_OUTPUT
    corpus_path = REPO_ROOT / DEFAULT_CORPUS_JSONL
    graph_path = REPO_ROOT / DEFAULT_GRAPH_JSON
    v21_path = REPO_ROOT / DEFAULT_V21_SPECS_JSON

    if not manifest_path.exists() or not corpus_path.exists():
        pytest.skip("Proposed manifest or Corpus v3 JSONL not yet built.")

    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert raw["provenance_status"] == PROVENANCE_STATUS_PROPOSED
    for domain in DEFERRED_CS_DOMAINS:
        assert raw["deferred_domains"][domain] == DEFERRED_DOMAIN_STATUS

    queries = [QuerySpec.from_dict(item) for item in raw["queries"]]
    assert MIN_QUERY_COUNT <= len(queries) <= MAX_QUERY_COUNT

    corpus_index = load_corpus_metadata(corpus_path)
    graph_index = GraphAnchorIndex.from_json_path(graph_path)
    v21_queries = load_v21_queries(v21_path)

    report = validate_benchmark(
        queries=queries,
        corpus_index=corpus_index,
        graph_index=graph_index,
        v21_queries=v21_queries,
        enforce_size_bounds=True,
    )
    assert report.is_valid, [
        f"{i.query_id}:{i.code}:{i.message}" for i in report.issues
    ]
