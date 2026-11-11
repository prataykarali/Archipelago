"""Detailed response, roadmap, ingestion, and acquisition contract checks."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit
pytest_plugins = ("tests.unit.contract_routing_fixtures",)

# ── 5. Template shape and the physical inventory card ─────────────────────────


def test_concept_answer_starts_with_the_answer(hosted_engine):
    text = hosted_engine.answer("Explain third normal form")["text"]
    assert text.startswith("**Third Normal Form (3NF).**")
    assert "### 1. Concept Definition" not in text


def test_graph_path_uses_the_requires_unlocks_notation(hosted_engine):
    text = hosted_engine.answer("What should I learn before third normal form?")["text"]
    assert "**Verified learning path.**" in text
    assert "REQUIRES" in text or "UNLOCKS" in text


def test_requested_digital_resources_are_not_called_physical_holdings(hosted_engine):
    """Pearson entries are licensed e-books, even when a concept matches."""
    result = hosted_engine.answer("Explain third normal form using library books")
    text = result["text"]
    if result["payload"].get("inventory"):
        assert "### Institutional e-books" in text
        assert "Physical holdings and circulation status are not verified" in text
        assert "Live shelf availability" not in text
        assert text.startswith("**Third Normal Form (3NF).**")


def test_no_empty_inventory_card_is_appended(hosted_engine):
    """A concept with no holdings gets no card — better none than a wrong one."""
    for prompt in ("Explain graph neural networks", "Tell me about dynamic clustering"):
        result = hosted_engine.answer(prompt)
        if not result["payload"].get("inventory"):
            assert "Physical Campus Library Inventory" not in result["text"]


def test_physical_library_answer_does_not_invent_holding(hosted_engine):
    """The Pearson export cannot establish a physical shelf or live circulation."""
    for prompt in ("Explain third normal form", "Where is Database System Concepts?"):
        text = hosted_engine.answer(prompt)["text"].lower()
        assert "rack 4" not in text
        assert "live shelf availability" not in text


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

    step = {
        "target_concept": target,
        "history": [
            {"concept_id": chain[0], "is_correct": True, "choice": "A"},
            {"concept_id": chain[1], "is_correct": True, "choice": "A"},
            {"concept_id": chain[2], "is_correct": False, "choice": "B"},
        ],
        "current_mcq": {"concept_id": chain[2], "correct_option": "A"},
    }

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
    result = hosted_engine.adaptive_step(
        {
            "target_concept": target,
            "history": [
                {"concept_id": chain[0], "is_correct": True, "choice": "A"},
                {"concept_id": chain[1], "is_correct": False, "choice": "B"},
            ],
            "current_mcq": {"concept_id": chain[1], "correct_option": "A"},
        }
    )
    statuses = {n["id"]: n["status"] for n in result["personalized_graph"]["nodes"]}
    assert statuses.get(chain[0]) == "MASTERED"
    assert statuses.get(chain[1]) in {"MISSING", "CURRENT"}
    assert statuses.get(target) in {"CURRENT", "UPCOMING"}


def test_personalized_graph_is_a_single_ordered_chain(hosted_engine):
    payload = hosted_engine.diagnostic_payload(PATH_TARGET)
    result = hosted_engine.adaptive_step(
        {
            "target_concept": PATH_TARGET,
            "history": [
                {"concept_id": cid, "is_correct": False, "choice": "B"}
                for cid in payload["chain"][:2]
            ],
            "current_mcq": payload["initial_question"],
            "user_choice": "B",
        }
    )
    graph = result["personalized_graph"]
    ids = [node["id"] for node in graph["nodes"]]
    assert len(ids) == len(set(ids))
    assert ids[-1] == PATH_TARGET
    assert [(edge["source"], edge["target"]) for edge in graph["edges"]] == [
        (ids[index], ids[index + 1]) for index in range(len(ids) - 1)
    ]


def test_diagnostic_never_completes_before_three_answers(hosted_engine):
    payload = hosted_engine.diagnostic_payload(PATH_TARGET)
    result = hosted_engine.adaptive_step(
        {
            "target_concept": PATH_TARGET,
            "current_mcq": payload["initial_question"],
            "user_choice": payload["initial_question"]["correct_option"],
            "consecutive_ticks": 2,
            "history": [],
        }
    )
    assert result["total_asked"] == 1
    assert result["completed"] is False
    assert result["next_question"] is not None


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

    assert telemetry.log_demand(
        "Rare Quantum Text", query="find rare quantum text", base_dir=tmp_path
    )
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
