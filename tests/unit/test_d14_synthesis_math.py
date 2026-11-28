"""D14.4 unit tests for epistemic synthesis, deterministic math validation, and claim support."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_INFERENCE_DIR = REPO_ROOT / "host_inference"
if str(HOST_INFERENCE_DIR) not in sys.path:
    sys.path.append(str(HOST_INFERENCE_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine import answer as answer_mod  # noqa: E402
from engine import math_guard, reply_plan, source_answer_fixes  # noqa: E402
from engine.answer import Engine  # noqa: E402

from archipelago.inference import math_validator  # noqa: E402

pytestmark = pytest.mark.unit
FIXTURE_GRAPH = HOST_INFERENCE_DIR / "fixtures" / "okf_graph.json"
MATH_TESTS_JSON = REPO_ROOT / "docs" / "reports" / "d14" / "D14_MATHEMATICAL_VALIDATION_TESTS.json"
PROMPT_FILE = HOST_INFERENCE_DIR / "engine" / "prompts" / "chat_reply.txt"

EXPECTED_EPISTEMIC_COUNT = 5
MIN_MATH_JSON_CASES = 18


def _load_math_cases() -> list[dict[str, Any]]:
    data = json.loads(MATH_TESTS_JSON.read_text(encoding="utf-8"))
    return list(data["cases"])


# ── 1. Deterministic Mathematical Validation Suite ───────────────────────────


@pytest.mark.parametrize("case", _load_math_cases(), ids=lambda c: c["id"])
def test_mathematical_validation_json_suite(case: dict[str, Any]) -> None:
    """Every case in D14_MATHEMATICAL_VALIDATION_TESTS.json matches expected pass/fail."""
    fn = getattr(math_validator, case["validator"])
    kwargs = dict(case["inputs"])
    if case["validator"] == "verify_svd_dimensions":
        kwargs["u_shape"] = tuple(kwargs["u_shape"])
        kwargs["s_shape"] = tuple(kwargs["s_shape"])
        kwargs["vt_shape"] = tuple(kwargs["vt_shape"])
    result = fn(**kwargs)
    assert result.passed is case["expected_passed"], f"{case['id']}: {result.message}"


def test_math_validation_json_has_full_coverage() -> None:
    """Validation JSON covers required regression count and symbolic equivalence."""
    cases = _load_math_cases()
    assert len(cases) >= MIN_MATH_JSON_CASES
    sym_ok = math_validator.verify_symbolic_equivalence("(x + 1)**2", "x**2 + 2*x + 1")
    assert sym_ok.passed is True
    sym_bad = math_validator.verify_symbolic_equivalence("(x + 1)**2", "x**2 + 1")
    assert sym_bad.passed is False


def test_gat_softmax_and_dimensions() -> None:
    """GAT prose audit catches wrong softmax(0.23, 0.19)=0.55/0.45 and 2D-vs-4D dim mismatch."""
    bad_prose = (
        "With attention vector a in R^2 applied to concatenated features in R^4, "
        "we compute softmax(0.23, 0.19) = (0.55, 0.45)."
    )
    results = math_validator.audit_numeric_text(bad_prose)
    names = {r.name for r in results if not r.passed}
    assert "softmax_arithmetic" in names
    assert "gat_attention_dimensions" in names

    audit = math_guard.audit_scientific_response(bad_prose, query="Explain GAT attention")
    assert audit["passed"] is False
    rule_ids = {item["rule_id"] for item in audit["issues"]}
    assert "softmax_arithmetic" in rule_ids
    assert "gat_attention_dimensions" in rule_ids
    assert audit["qualification_note"] is not None

    good_prose = (
        "With attention vector a in R^4 applied to concatenated features in R^4, "
        "we compute softmax(0.23, 0.19) ≈ (0.51, 0.49)."
    )
    clean_audit = math_guard.audit_scientific_response(good_prose, query="Explain GAT attention")
    assert clean_audit["passed"] is True


# ── 2. Five Explicit Epistemic States ────────────────────────────────────────


def test_five_epistemic_states_classification_and_prompt() -> None:
    """All 5 epistemic states are defined in prompt and classified deterministically."""
    prompt_text = PROMPT_FILE.read_text(encoding="utf-8")
    assert len(math_validator.EPISTEMIC_STATES) == EXPECTED_EPISTEMIC_COUNT
    for state in math_validator.EPISTEMIC_STATES:
        assert state in prompt_text

    # 1. DIRECTLY_SUPPORTED (+ INDEPENDENTLY_DERIVED_EXAMPLE when worked example requested)
    direct = reply_plan.classify_epistemic_state(
        {
            "evidence_backed": True,
            "citations": [{"source_kind": "verified_full_text_passage"}],
            "anchor_concept": {"id": "paging"},
        },
        route="CONCEPT_EXPLANATION",
        query="Explain paging with a worked example.",
    )
    assert direct["primary_state"] == reply_plan.EPISTEMIC_DIRECTLY_SUPPORTED
    assert reply_plan.EPISTEMIC_INDEPENDENTLY_DERIVED in direct["allowed_states"]

    # 3. GENERAL_MODEL_KNOWLEDGE
    general = reply_plan.classify_epistemic_state(
        {"evidence_backed": False, "citations": [], "anchor_concept": {"id": "tcp"}},
        route="GENERAL_EXPLANATION",
        query="Explain TCP flow control.",
    )
    assert general["primary_state"] == reply_plan.EPISTEMIC_GENERAL_KNOWLEDGE

    # 4. METADATA_ONLY
    meta_only = reply_plan.classify_epistemic_state(
        {
            "evidence_backed": False,
            "citations": [{"source_kind": "metadata_only_record"}],
            "anchor_concept": {"id": "b_plus_tree"},
        },
        route="CONCEPT_EXPLANATION",
        query="Explain B+ trees.",
    )
    assert meta_only["primary_state"] == reply_plan.EPISTEMIC_METADATA_ONLY

    # 5. UNAVAILABLE_OR_UNCERTAIN
    unavailable = reply_plan.classify_epistemic_state(
        {"evidence_backed": False, "citations": [], "anchor_concept": None},
        route="OUT_OF_DOMAIN",
        query="Explain unindexed paper.",
    )
    assert unavailable["primary_state"] == reply_plan.EPISTEMIC_UNAVAILABLE


# ── 3. Scientific & Technical Guardrails (D14-DEF-030 through D14-DEF-044) ───


def test_dpo_guardrail() -> None:
    """DPO guard flags explicit reward model claims and accepts implicit reward explanation."""
    bad = "DPO trains a separate reward model before updating the policy."
    assert math_guard.audit_scientific_response(bad)["passed"] is False
    good = "DPO eliminates a separate reward model by reparameterizing the implicit reward."
    assert math_guard.audit_scientific_response(good)["passed"] is True
    guidance = math_guard.build_scientific_guard_guidance(
        "How does Direct Preference Optimization (DPO) work?", evidence_backed=True
    )
    assert "eliminates a separate explicit reward model" in guidance


def test_gaussian_mle_and_kl_guards() -> None:
    """Gaussian MLE, Bayes' theorem, and KL divergence guards catch derivation errors."""
    bad_mle = "The Gaussian MLE variance divides by n-1 in the denominator."
    assert math_guard.audit_scientific_response(bad_mle)["passed"] is False
    bad_bayes = "By Bayes' theorem, P(A|B) = P(B|A) regardless of base rates."
    assert math_guard.audit_scientific_response(bad_bayes)["passed"] is False
    good_bayes = "By Bayes' theorem, P(A|B) is not equal to P(B|A) unless P(A) = P(B)."
    assert math_guard.audit_scientific_response(good_bayes)["passed"] is True
    bad_kl = "KL divergence is symmetric and is a true distance metric."
    assert math_guard.audit_scientific_response(bad_kl)["passed"] is False
    good_kl = "KL divergence is not symmetric and is not a true distance metric."
    assert math_guard.audit_scientific_response(good_kl)["passed"] is True


def test_pca_and_svd_guards() -> None:
    """PCA centering/repeated-eigenvalue guard and SVD false-abstention guard."""
    bad_pca = "PCA does not require mean-centering before computing principal components."
    assert math_guard.audit_scientific_response(bad_pca)["passed"] is False
    svd_cites = [{"text_passage": "Singular Value Decomposition factorizes A = U Sigma V^T."}]
    bad_svd = "The SVD formulation is unavailable in the corpus."
    audit = math_guard.audit_scientific_response(
        bad_svd, query="Derive Singular Value Decomposition (SVD)", citations=svd_cites
    )
    assert audit["passed"] is False
    assert any(i["rule_id"] == "svd_false_abstention" for i in audit["issues"])


def test_os_paging_and_base_bounds() -> None:
    """Paging offset/fault guards and base-and-bounds [0, bounds) interval."""
    bad_paging = "With a 4 KiB page size, VA 0x12345 translates to PA 0x46346."
    assert math_guard.audit_worked_address_translation(bad_paging) is not None
    bad_disk = "Every page fault requires disk I/O."
    assert math_guard.audit_scientific_response(bad_disk)["passed"] is False
    bad_bb = "In base-and-bounds translation, valid addresses satisfy virtual_addr <= bounds."
    assert math_guard.audit_scientific_response(bad_bb)["passed"] is False

    engine = Engine(FIXTURE_GRAPH)
    paging_res = source_answer_fixes.source_grounded_os_reply(
        engine.graph, engine.catalog, "How do paging and page faults work?"
    )
    assert paging_res is not None
    assert "hardware MMU/TLB" in paging_res[1]
    assert "demand-zero" in paging_res[1]


def test_cfg_and_compiler_guards() -> None:
    """LALR CFG notation guard and compiler IR semantic-analysis omission guard."""
    bad_cfg = "In bottom-up LALR parsing, reduce using rule F * F -> T."
    audit_cfg = math_guard.audit_scientific_response(bad_cfg, query="LALR parsing example")
    assert audit_cfg["passed"] is False
    assert any(i["rule_id"] == "lalr_cfg_production" for i in audit_cfg["issues"])

    bad_ir = "Compiler pipeline goes from lexical analysis to syntax analysis (parsing) directly to IR generation."
    audit_ir = math_guard.audit_scientific_response(
        bad_ir, query="What are prerequisites for compiler intermediate representation?"
    )
    assert audit_ir["passed"] is False
    assert any(i["rule_id"] == "compiler_ir_semantic_omission" for i in audit_ir["issues"])


def test_cs_systems_scientific_guards() -> None:
    """Dijkstra, OSI/CRC, TCP, Automata, and DB ACID isolation guards."""
    cases = [
        (
            "Dijkstra's algorithm works correctly with negative edge weights.",
            "dijkstra_negative_weights",
        ),
        ("CRC performs forward error correction on corrupted frames.", "osi_crc_correction"),
        ("In TCP, rwnd controls network congestion control.", "tcp_rwnd_cwnd_conflation"),
        (
            "Finite automata are a proper subset of context-free grammars.",
            "automata_machine_subset_grammar",
        ),
        ("All SQL isolation levels guarantee serializability.", "db_all_isolation_serializable"),
    ]
    for bad_text, expected_rule in cases:
        audit = math_guard.audit_scientific_response(bad_text)
        assert audit["passed"] is False, f"Expected failure for: {bad_text}"
        assert any(i["rule_id"] == expected_rule for i in audit["issues"])


def test_unavailable_paper_abstention_guard() -> None:
    """Fabricated paper claims when evidence_backed=False are flagged."""
    bad_nids = "The paper proposes an unsupervised zero-shot architecture achieving 99% accuracy."
    audit = math_guard.audit_scientific_response(
        bad_nids, query="Summarize the network intrusion detection paper", evidence_backed=False
    )
    assert audit["passed"] is False
    assert any(i["rule_id"] == "unavailable_paper_fabrication" for i in audit["issues"])


# ── 4. Claim-to-Passage Support & Stream Validation Invariants ───────────────


def test_strip_unsupported_citations_and_verify_claim_support() -> None:
    """Unsupported markers are stripped; unassessed is explicitly UNASSESSED; incomplete is never validated."""
    citations = [
        {
            "evidence_id": "S1",
            "source_kind": "verified_full_text_passage",
            "text_passage": "Paging maps virtual pages to physical frames using a page table.",
        },
        {
            "evidence_id": "S2",
            "source_kind": "metadata_only_record",
            "text_passage": "",
        },
    ]
    raw = "Paging maps virtual pages to physical frames [S1] and uses metadata [S2] and fake [S9]."
    cleaned, stripped = math_guard.strip_unsupported_citations(raw, citations)
    assert "[S1]" in cleaned
    assert "[S2]" not in cleaned
    assert "[S9]" not in cleaned
    assert stripped == ["[S2]", "[S9]"]

    verified = math_guard.verify_claim_support(cleaned, citations, stream_status="complete")
    assert verified["status"] == math_guard.CLAIM_STATUS_VERIFIED
    assert verified["validated"] is True

    unassessed = math_guard.verify_claim_support(
        "General explanation without inline citation markers.", citations, stream_status="complete"
    )
    assert unassessed["status"] == math_guard.CLAIM_STATUS_UNASSESSED
    assert unassessed["validated"] is False

    missing_passage_cites = [
        {"evidence_id": "S1", "source_kind": "verified_full_text_passage", "text_passage": ""}
    ]
    unassessed_no_text = math_guard.verify_claim_support(
        "Claim citing a passage without loaded text [S1].",
        missing_passage_cites,
        stream_status="complete",
    )
    assert unassessed_no_text["status"] == math_guard.CLAIM_STATUS_UNASSESSED
    assert unassessed_no_text["validated"] is False

    incomplete = math_guard.verify_claim_support(
        cleaned, citations, stream_status="truncated_token_limit"
    )
    assert incomplete["status"] == math_guard.CLAIM_STATUS_INCOMPLETE
    assert incomplete["validated"] is False


def test_stream_chat_partial_never_validated_and_post_audit_emitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Truncated streams emit validated=False/INCOMPLETE_UNVALIDATED; bad math emits audit note."""
    engine = Engine(FIXTURE_GRAPH)
    query = "How does Graph Attention Network (GAT) compute attention weights?"
    prepared = engine.answer(query)
    monkeypatch.setattr(
        answer_mod,
        "provider_config",
        lambda: {
            "provider": "xkiro",
            "base_url": "https://xkiro.invalid",
            "key": "k",
            "model": "m",
        },
    )
    monkeypatch.setattr(answer_mod, "fallback_config", lambda _cfg: None)
    monkeypatch.setattr(answer_mod, "last_provider_error", lambda: None)

    # Case A: Truncated stream -> NEVER marked validated
    monkeypatch.setattr(
        answer_mod,
        "stream_completion",
        lambda *_a, **_kw: iter(["### Direct Answer\nPartial output ending at Page"]),
    )
    monkeypatch.setattr(
        answer_mod,
        "last_stream_outcome",
        lambda: {"status": "truncated_token_limit", "finish_reason": "length"},
    )
    raw_trunc = "".join(engine.stream_chat(query, prepared=prepared))
    meta_trunc = json.loads(raw_trunc.split("[STREAM_META:", 1)[1].split("]", 1)[0])
    assert meta_trunc["validated"] is False
    assert meta_trunc["claim_support_status"] == math_guard.CLAIM_STATUS_INCOMPLETE

    # Case B: Complete stream with wrong softmax + unsupported [S9] -> flagged in prose & meta
    monkeypatch.setattr(
        answer_mod,
        "stream_completion",
        lambda *_a, **_kw: iter(
            [
                "### Direct Answer\nGAT computes attention scores and softmax(0.23, 0.19) = (0.55, 0.45) [S9]."
            ]
        ),
    )
    monkeypatch.setattr(
        answer_mod,
        "last_stream_outcome",
        lambda: {"status": "complete", "finish_reason": "stop"},
    )
    raw_bad = "".join(engine.stream_chat(query, prepared=prepared))
    assert "Scientific & numerical consistency check" in raw_bad
    assert "Claim support notice" in raw_bad
    meta_bad = json.loads(raw_bad.split("[STREAM_META:", 1)[1].split("]", 1)[0])
    assert meta_bad["math_validation_passed"] is False
    assert meta_bad["claim_support_status"] == math_guard.CLAIM_STATUS_PARTIAL_OR_UNSUPPORTED
    assert meta_bad["validated"] is False
