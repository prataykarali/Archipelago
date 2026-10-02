"""Regression tests for the six response contracts.

These pin the *contract* each prompt family must land under, not the engine's
internal route names.  ``SCHEDULE`` and ``AUTH_GATEWAY`` are both contract type
3; asserting on the route string instead would break every time the router is
refactored while telling us nothing about whether a student got their hours.

Two stacks are covered because both ship: the hosted engine (``host_inference``,
deployed alone to the cloud) and the library server (``archipelago``). They have
separate routers and have drifted apart before, which is exactly what this file
exists to prevent.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = REPO_ROOT / "host_inference"
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

pytestmark = pytest.mark.unit

CONTRACT_TYPES = (
    "GRAPH_SYNTHESIS",
    "CATALOG_SHELF_ROUTING",
    "AUTH_GATEWAY",
    "MCQ_DIAGNOSTIC",
    "INGESTION_ANALYSIS",
    "GUARDRAIL_INTERCEPT",
)

# ── Probes, verbatim from the published contract table ────────────────────────
PROBES: dict[str, list[str]] = {
    "GRAPH_SYNTHESIS": [
        "What foundational math must I master before studying Self-Attention?",
        "How does Softmax connect to Self-Attention?",
        "Explain BERT",
    ],
    "CATALOG_SHELF_ROUTING": [
        "Where can I find a physical copy of 'Database System Concepts' on campus?",
        "What is the call number for Database System Concepts?",
        "How many copies of Operating System Internals are available?",
    ],
    "AUTH_GATEWAY": [
        "How do I access IEEE Xplore off-campus, and what are library Sunday hours?",
        "What are the library opening hours?",
        "library Sunday hours",
        "How do I log in to Scopus?",
        "What time does the circulation desk open?",
    ],
    "MCQ_DIAGNOSTIC": [
        "I want to learn RAG",
        "Show learning roadmap for BERT",
        "What should I study first for LoRA?",
        "Teach me about third normal form",
    ],
    "INGESTION_ANALYSIS": [
        "Analyze this uploaded PDF and extract its Open Knowledge Format (OKF) nodes.",
        "Extract the OKF nodes from my uploaded paper",
        "Ingest this document into the graph",
    ],
    "GUARDRAIL_INTERCEPT": [
        "Write a Python web scraper",
        "What is a good recipe for lasagna?",
        "Tell me a joke",
    ],
}

#: Substrings that prove the right *content* answered, not just the right route.
CONTENT_REQUIREMENTS = {
    ("AUTH_GATEWAY", "How do I access IEEE Xplore off-campus, and what are library Sunday hours?"): (
        "24",
    ),
    ("AUTH_GATEWAY", "library Sunday hours"): ("24",),
    ("AUTH_GATEWAY", "What are the library opening hours?"): ("24",),
    ("AUTH_GATEWAY", "What time does the circulation desk open?"): ("24",),
    ("CATALOG_SHELF_ROUTING", "What is the call number for Database System Concepts?"): ("ISBN",),
}


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def hosted_engine():
    """The hosted engine, or skip when its graph cache is absent."""
    graph = HOST_DIR / "cache" / "okf_graph.json"
    if not graph.is_file():
        pytest.skip("hosted concept graph cache is not present")
    import engine as hosted

    return hosted.Engine()


@pytest.fixture(scope="module")
def library_client():
    """A Flask test client on the deployed API app."""
    try:
        from archipelago.api.app import app
    except Exception as exc:
        pytest.fail(f"library app failed to import: {exc}")
    app.config.update(TESTING=True)
    return app.test_client()


# ── 1. Contract classification, both stacks ───────────────────────────────────


#: Flattened ``(contract, prompt)`` pairs — pytest cannot parametrize a second
#: argument over a dict comprehension, and one flat list keeps the two stacks'
#: case tables provably identical.
PROBE_CASES: list[tuple[str, str]] = [
    (contract_type, prompt)
    for contract_type in CONTRACT_TYPES
    for prompt in PROBES[contract_type]
]


@pytest.mark.parametrize(("contract", "prompt"), PROBE_CASES)
def test_hosted_engine_honours_every_contract(hosted_engine, contract, prompt):
    result = hosted_engine.answer(prompt)
    assert result["contract"] == contract, (
        f"{prompt!r} routed under {result['route']} ({result['contract']}), "
        f"expected {contract}"
    )


@pytest.mark.parametrize(("contract", "prompt"), PROBE_CASES)
def test_library_server_honours_every_contract(library_client, contract, prompt):
    body = (library_client.post("/api/chat", json={"query": prompt}).get_json() or {})
    assert body.get("contract") == contract, (
        f"{prompt!r} answered as {body.get('contract')!r} (status "
        f"{body.get('status')!r}), expected {contract}"
    )


# ── 2. Content, not just routing ─────────────────────────────────────────────


@pytest.mark.parametrize(
    ("contract", "prompt", "needles"),
    [(c, p, n) for (c, p), n in CONTENT_REQUIREMENTS.items()],
)
def test_hosted_answers_carry_the_required_content(hosted_engine, contract, prompt, needles):
    text = hosted_engine.answer(prompt)["text"].lower()
    for needle in needles:
        assert needle.lower() in text, f"{prompt!r} omitted {needle!r}"


def test_hours_and_access_are_answered_in_one_reply(hosted_engine):
    """The combined question must not lose either half to the other route."""
    result = hosted_engine.answer(
        "How do I access IEEE Xplore off-campus, and what are library Sunday hours?"
    )
    text = result["text"].lower()
    assert "24" in text, "the schedule half was dropped"
    assert "ieee" in text, "the access half was dropped"


def test_combined_hours_and_access_keeps_both_halves(library_client):
    body = (
        library_client.post(
            "/api/chat",
            json={"query": "How do I access IEEE Xplore off-campus, and what are library Sunday hours?"},
        ).get_json()
        or {}
    )
    text = str(body.get("text") or "").lower()
    assert "24" in text, "the schedule half was dropped"
    assert "ieee" in text or "e-resource" in text, "the access half was dropped"


# ── 3. Graph-render protocol ──────────────────────────────────────────────────

#: Contracts that draw the in-chat concept graph.
GRAPH_CONTRACTS = {"GRAPH_SYNTHESIS", "MCQ_DIAGNOSTIC", "INGESTION_ANALYSIS"}
#: Contracts that must never draw one.
NO_GRAPH_CONTRACTS = {"CATALOG_SHELF_ROUTING", "AUTH_GATEWAY", "GUARDRAIL_INTERCEPT"}


@pytest.mark.parametrize("contract", sorted(NO_GRAPH_CONTRACTS))
def test_non_graph_contracts_never_expose_an_anchor(hosted_engine, contract):
    for prompt in PROBES[contract]:
        payload = hosted_engine.answer(prompt)["payload"]
        assert payload["render_graph"] is False, f"{prompt!r} should not draw a graph"
        assert payload["anchor_concept"] is None
        assert payload["prerequisites"] == []
        assert payload["unlocks"] == []


@pytest.mark.parametrize("contract", sorted(NO_GRAPH_CONTRACTS))
def test_library_non_graph_contracts_suppress_the_graph(library_client, contract):
    for prompt in PROBES[contract]:
        body = (library_client.post("/api/chat", json={"query": prompt}).get_json() or {})
        assert body.get("render_graph") is False, f"{prompt!r} should not draw a graph"
        assert body.get("topology") is None


def test_render_decision_is_a_pure_function_of_the_route():
    """The protocol must not depend on phrasing, so grade it in isolation."""
    from host_inference.engine import contract

    for route, mapped in contract.ROUTE_CONTRACT.items():
        decision = contract.graph_decision(route)
        expected = mapped in GRAPH_CONTRACTS
        assert decision.render is expected, f"{route} -> {mapped} drew {decision.render}"
        assert decision.rule


def test_every_emitted_route_has_a_contract_mapping():
    """An unmapped route means the router grew behaviour nobody signed off."""
    from host_inference.engine import contract

    for route in _hosted_routes_seen_in_code():
        assert route in contract.ROUTE_CONTRACT, f"route {route!r} is unmapped"


def test_library_statuses_all_map_to_a_contract():
    from archipelago.core import contract

    for status in ("success", "rejected", "out_of_scope", "suggest_topics"):
        assert contract.contract_for(status) in contract.CONTRACT_TYPES


def test_unknown_route_raises_rather_than_guessing():
    from host_inference.engine import contract

    with pytest.raises(KeyError):
        contract.contract_for("A_ROUTE_THAT_DOES_NOT_EXIST")


def _hosted_routes_seen_in_code() -> set[str]:
    """Every route literal the router can return, read from the source."""
    import re

    source = (HOST_DIR / "engine" / "answer.py").read_text(encoding="utf-8")
    return set(re.findall(r'return\s+"([A-Z_]{3,})"\s*,', source))


# ── 4. Contract parity between the two stacks ─────────────────────────────────


def test_contract_tables_agree_between_stacks():
    """The two modules are duplicated by necessity; they must not diverge.

    The hosted build ships without the ``archipelago`` package, so the tables
    cannot be shared at runtime. This test is the enforcement mechanism.
    """
    from archipelago.core import contract as library_contract
    from host_inference.engine import contract as hosted_contract

    assert library_contract.CONTRACT_TYPES == hosted_contract.CONTRACT_TYPES
    assert library_contract.GRAPH_CONTRACTS == hosted_contract.GRAPH_CONTRACTS
    assert library_contract.CONTRACT_TITLES == hosted_contract.CONTRACT_TITLES
    for contract_type in hosted_contract.CONTRACT_TYPES:
        left = library_contract.graph_decision(contract_type)
        right = hosted_contract.graph_decision(contract_type)
        assert left == right, f"{contract_type} renders differently per stack"


# ── 5. Template shape and the physical inventory card ─────────────────────────

TEMPLATE_SECTIONS = (
    "### 1. Concept Definition",
    "### 2. Topological Graph Path",
    "### 3. Grounded Synthesis",
)


def test_concept_answer_follows_the_master_template(hosted_engine):
    text = hosted_engine.answer("Explain third normal form")["text"]
    for section in TEMPLATE_SECTIONS:
        assert section in text, f"missing section {section!r}"
    positions = [text.index(section) for section in TEMPLATE_SECTIONS]
    assert positions == sorted(positions), "template sections are out of order"


def test_graph_path_uses_the_requires_unlocks_notation(hosted_engine):
    text = hosted_engine.answer("Explain third normal form")["text"]
    assert "REQUIRES" in text and "UNLOCKS" in text


def test_inventory_card_is_appended_to_concept_answers(hosted_engine):
    """Section 4 must be appended, and only when the catalogue actually matches."""
    result = hosted_engine.answer("Explain third normal form")
    text = result["text"]
    if result["payload"].get("inventory"):
        assert "### 3. Physical Campus Library Inventory" in text
        assert "physical cop" in text.lower()
        # Never displace the explanation.
        assert TEMPLATE_SECTIONS[0] in text


def test_no_empty_inventory_card_is_appended(hosted_engine):
    """A concept with no holdings gets no card — better none than a wrong one."""
    for prompt in ("Explain graph neural networks", "Tell me about dynamic clustering"):
        result = hosted_engine.answer(prompt)
        if not result["payload"].get("inventory"):
            assert "Physical Campus Library Inventory" not in result["text"]


def test_physical_library_positioning_is_never_denied(hosted_engine):
    """The contract forbids implying digital access replaces the print collection."""
    for prompt in ("Explain third normal form", "Where is Database System Concepts?"):
        text = hosted_engine.answer(prompt)["text"].lower()
        if "physical" in text or "library" in text:
            assert "does not replace" in text or "primary route" in text


# ── 6. Personalized learning path ─────────────────────────────────────────────


#: A target with a genuinely deep prerequisite chain, so the personalized path
#: has something to reorder. 3NF has almost no indexed prerequisites and would
#: make this test pass trivially.
PATH_TARGET = "transformer"


def test_roadmap_skips_nodes_the_student_already_passed(hosted_engine):
    """A mastered node must not be re-taught, and gaps must be named."""
    target = PATH_TARGET
    payload = hosted_engine.diagnostic_payload(target)
    chain = payload["chain"]

    step = {"target_concept": target, "history": [
        {"concept_id": chain[0], "is_correct": True, "choice": "A"},
        {"concept_id": chain[1], "is_correct": True, "choice": "A"},
        {"concept_id": chain[2], "is_correct": False, "choice": "B"},
    ], "current_mcq": {"concept_id": chain[2], "correct_option": "A"}}

    result = hosted_engine.adaptive_step(step)
    roadmap = result["evaluation"]["roadmap"]
    steps = [s["id"] for s in roadmap["steps"]]

    assert chain[0] not in steps, "a mastered node was put back on the learning path"
    assert chain[2] in steps, "the review gap was dropped from the learning path"
    assert steps[-1] == target, "the plan must end at the target"
    assert roadmap["algorithm"], "the roadmap must record which search produced it"
    assert set(roadmap["skipped_mastered"]) >= {chain[0], chain[1]}


def test_mastered_and_gap_nodes_are_coloured(hosted_engine):
    """🟢 mastered / 🟡 review gap / 🎯 target must all be present."""
    target = PATH_TARGET
    payload = hosted_engine.diagnostic_payload(target)
    chain = payload["chain"]
    result = hosted_engine.adaptive_step({
        "target_concept": target,
        "history": [
            {"concept_id": chain[0], "is_correct": True, "choice": "A"},
            {"concept_id": chain[1], "is_correct": False, "choice": "B"},
        ],
        "current_mcq": {"concept_id": chain[1], "correct_option": "A"},
    })
    statuses = {n["id"]: n["status"] for n in result["personalized_graph"]["nodes"]}
    assert statuses.get(chain[0]) == "mastered"
    assert statuses.get(chain[1]) == "review_gap"
    assert statuses.get(target) in {"target", "unlocked"}


def test_learning_path_returns_target_when_nothing_is_outstanding():
    from host_inference.engine.pathfinder import learning_path

    class _Graph:
        """A graph with no dependency edges at all."""

        def __init__(self) -> None:
            self.nodes: dict = {"a": {}}
            self.out: dict = {}
            self.inn: dict = {}

    assert learning_path(_Graph(), "a", frozenset()) == ["a"]


# ── 7. Ingestion projection honesty ───────────────────────────────────────────


def test_ingestion_reply_never_invents_nodes(hosted_engine, monkeypatch, tmp_path):
    """With no job store, the reply must say so rather than project anything."""
    from host_inference.engine import ingestion_view

    monkeypatch.setenv(ingestion_view.JOBS_DIR_ENV, str(tmp_path))
    monkeypatch.setattr(ingestion_view, "JOBS_RELPATH", ingestion_view.JOBS_RELPATH)
    text, payload = ingestion_view.ingestion_reply("analyse this pdf", hosted_engine.graph)
    assert payload["ingestion"]["nodes"] == []
    assert payload["ingestion"]["state"] == "no_upload"
    assert "no completed upload" in text.lower()


def test_ingestion_projects_only_nodes_present_in_the_graph(hosted_engine, monkeypatch, tmp_path):
    from host_inference.engine import ingestion_view

    store = tmp_path / "jobs"
    store.mkdir()
    (store / "jobs.json").write_text(
        '{"j1": {"job_id": "j1", "status": "COMPLETE", '
        '"source_filename": "real.pdf", "updated_at": "2030-01-01T00:00:00+00:00", '
        '"result": {"new_node_ids": ["third_normal_form", "a_node_that_does_not_exist"], '
        '"source_pages": [3, 4], "merge": {"uploading_doc_id": "papers/real.pdf"}}}}',
        encoding="utf-8",
    )
    monkeypatch.setenv(ingestion_view.JOBS_DIR_ENV, str(tmp_path))
    _text, payload = ingestion_view.ingestion_reply("analyse this pdf", hosted_engine.graph)
    ingestion = payload["ingestion"]
    assert ingestion["nodes"] == ["third_normal_form"], "invented or dropped a node"
    assert ingestion["pages"] == [3, 4]
    assert ingestion["doc_id"] == "papers/real.pdf"


def test_failed_ingestion_reports_the_error_not_a_summary(hosted_engine, monkeypatch, tmp_path):
    from host_inference.engine import ingestion_view

    store = tmp_path / "jobs"
    store.mkdir()
    (store / "jobs.json").write_text(
        '{"j1": {"job_id": "j1", "status": "FAILED", "error": "Extraction produced 0 concepts", '
        '"source_filename": "empty.pdf", "updated_at": "2030-01-01T00:00:00+00:00", "result": {}}}',
        encoding="utf-8",
    )
    monkeypatch.setenv(ingestion_view.JOBS_DIR_ENV, str(tmp_path))
    text, payload = ingestion_view.ingestion_reply("analyse this pdf", hosted_engine.graph)
    assert payload["ingestion"]["nodes"] == []
    assert "Extraction produced 0 concepts" in text


# ── 8. Demand telemetry ───────────────────────────────────────────────────────


def test_unmet_demand_lands_in_the_digest(tmp_path):
    """A title the library does not hold must be recorded, not silently dropped."""
    from host_inference.engine import telemetry

    assert telemetry.log_demand("Rare Quantum Text", query="find rare quantum text", base_dir=tmp_path)
    assert telemetry.log_demand("Rare Quantum Text", query="again", base_dir=tmp_path)
    rows = telemetry.unmet_titles(min_count=2, base_dir=tmp_path)
    assert [r["title"] for r in rows] == ["Rare Quantum Text"]
    assert rows[0]["count"] == 2


def test_digest_renders_a_librarian_readable_table(tmp_path):
    from host_inference.engine import telemetry

    for _ in range(2):
        telemetry.log_demand("Another Missing Title", base_dir=tmp_path)
    rendered = telemetry.render_digest(min_count=2, base_dir=tmp_path)
    assert "Another Missing Title" in rendered
    assert "| Requested | Times asked | First seen |" in rendered


def test_acquisition_plan_only_offers_reviewable_candidates():
    """Discovery proposes; it never purchases or writes an OPAC record."""
    from archipelago.ingestion.acquisition_discovery import match_candidates

    catalogue = [
        {"title": "Database System Concepts", "author": "Silberschatz", "isbn": "978-1"},
        {"title": "Systems Thinking", "author": "Senge", "isbn": "978-2"},
    ]
    candidates = match_candidates("database system concepts", catalogue)
    assert candidates, "an exact title in the catalogue produced no candidate"
    assert candidates[0]["title"] == "Database System Concepts"
    assert candidates[0]["confidence"] == "exact"
    for candidate in candidates:
        assert candidate["action_required"] == "librarian_review"
        assert candidate["source"] == "pearson_elibrary"


def test_acquisition_plan_ignores_single_mentions():
    from archipelago.ingestion.acquisition_discovery import discovery_plan

    catalogue = [{"title": "Database System Concepts", "author": "Silberschatz", "isbn": "1"}]
    plan = discovery_plan([{"title": "Database System Concepts", "count": 1}], min_count=2)
    assert plan["rows"] == []
    assert plan["totals"]["unmet_titles"] == 0
    assert isinstance(catalogue, list)
