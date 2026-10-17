"""Focused safeguards for the staff-only research pipeline."""

from __future__ import annotations

import hashlib
import json
import logging
from types import SimpleNamespace
import uuid

from flask import Flask
import pytest

from archipelago.scholarly.access import ResearchCapability, allowed, audit_action
from archipelago.scholarly.acquisition.rights_resolver import RightsResolver
from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    StatusEnum,
)
from archipelago.scholarly.discovery.canonicalizer import Canonicalizer
from archipelago.scholarly.discovery.live_sources import LiveResearchSources, SourceResponse
from archipelago.scholarly.features.feature_engine import FeatureEngine
from archipelago.scholarly.pipeline.postgres_store import PostgresResearchStore
from archipelago.scholarly.pipeline.projection import rebuild_projection, refresh_pending_projection
from archipelago.scholarly.pipeline.relevance import shortlist
from archipelago.scholarly.pipeline.research_job import ResearchJobRunner
from archipelago.scholarly.pipeline.routes import register_research_routes

pytestmark = pytest.mark.unit


def _candidate(title: str, doi: str, citations: int | None = None) -> dict:
    return {
        "source": "crossref",
        "paper": PaperRecord(
            title=title,
            abstract="Optical character recognition method",
            identifiers=PaperIdentifiers(doi=doi),
            authors=[PaperAuthor(name="A Researcher")],
        ),
        "citation_count": citations,
    }


def test_role_matrix_is_default_deny() -> None:
    for role in (None, "student"):
        for capability in ResearchCapability:
            assert not allowed(role, capability)
    for role in ("faculty", "librarian", "administrator"):
        assert allowed(role, ResearchCapability.JOB_CREATE)
        assert allowed(role, ResearchCapability.EVIDENCE_READ)
    assert not allowed("faculty", ResearchCapability.REFRESH_CONTROL)
    assert allowed("faculty", ResearchCapability.REFRESH_CONTROL, {"refresh_control"})
    assert allowed("librarian", ResearchCapability.REVIEW)
    assert not allowed("librarian", ResearchCapability.CONNECTOR_CONFIG)
    assert allowed("administrator", ResearchCapability.CONNECTOR_CONFIG)


def test_research_api_denies_student_and_is_disabled_for_staff(monkeypatch) -> None:
    from archipelago import supabase_auth

    role = {"value": None}

    def authenticate(_request):
        if role["value"] is None:
            return None, "missing"
        return SimpleNamespace(user_id="user-one", role=role["value"]), None

    monkeypatch.setattr(supabase_auth, "authenticate_request", authenticate)
    monkeypatch.delenv("ARCHIPELAGO_RESEARCH_ENABLED", raising=False)
    app = Flask(__name__)
    register_research_routes(app)
    client = app.test_client()
    for candidate_role, expected in ((None, 401), ("student", 403), ("faculty", 503)):
        role["value"] = candidate_role
        assert client.post("/api/research/jobs", json={"topic": "OCR"}).status_code == expected
        assert client.get(f"/api/research/jobs/{uuid.uuid4()}").status_code == expected
    role["value"] = "faculty"
    assert (
        client.patch(f"/api/research/topics/{uuid.uuid4()}/refresh", json={"hours": 24}).status_code
        == 403
    )


def test_research_routes_enforce_all_four_roles(monkeypatch) -> None:
    from archipelago import supabase_auth
    from archipelago.scholarly.pipeline import routes

    role = {"value": "student"}
    job_id = str(uuid.uuid4())
    paper_id = str(uuid.uuid4())
    digest = "a" * 64
    audits = []

    class Store:
        def create_job(self, **kwargs):
            return {"job_id": job_id, "topic": kwargs["topic"]}

        def get_job(self, _job_id):
            return {"job_id": job_id, "user_id": "staff-one", "topic": "OCR"}

        def job_has_paper(self, *_):
            return True

        def get_features(self, *_):
            return []

        def get_evidence(self, *_):
            return []

        def source_summaries(self, *_):
            return []

        def track_topic(self, **kwargs):
            return {"topic": kwargs["topic"]}

        def set_topic_refresh(self, *_):
            return True

        def review_evidence(self, *_, **__):
            return True

        def audit(self, **kwargs):
            audits.append(kwargs)

    monkeypatch.setattr(
        supabase_auth,
        "authenticate_request",
        lambda _request: (SimpleNamespace(user_id="staff-one", role=role["value"]), None),
    )
    monkeypatch.setattr(routes, "_store", Store)
    app = Flask(__name__)
    register_research_routes(app)
    client = app.test_client()
    job_url = f"/api/research/jobs/{job_id}"
    paper_url = f"{job_url}/papers/{paper_id}"
    restricted = (
        ("post", "/api/research/jobs", {"topic": "OCR"}),
        ("get", job_url, None),
        ("get", f"{paper_url}/features", None),
        ("get", f"{paper_url}/evidence", None),
        ("post", "/api/research/topics", {"topic": "OCR"}),
    )
    for method, path, body in restricted:
        assert getattr(client, method)(path, json=body).status_code == 403
    role["value"] = "faculty"
    for method, path, body in restricted:
        assert getattr(client, method)(path, json=body).status_code in {200, 201, 202}
    assert client.get(f"{job_url}/sources").status_code == 403
    assert (
        client.post(
            f"{paper_url}/evidence/{digest}/review", json={"decision": "approve"}
        ).status_code
        == 403
    )
    role["value"] = "librarian"
    assert client.get(f"{job_url}/sources").status_code == 200
    assert (
        client.patch(f"/api/research/topics/{uuid.uuid4()}/refresh", json={"hours": 24}).status_code
        == 200
    )
    assert (
        client.post(
            f"{paper_url}/evidence/{digest}/review", json={"decision": "approve"}
        ).status_code
        == 200
    )
    role["value"] = "administrator"
    assert (
        client.post(
            f"{paper_url}/evidence/{digest}/review", json={"decision": "reject"}
        ).status_code
        == 200
    )
    assert [audit["action"] for audit in audits].count("evidence_review") == 2


def test_identity_requires_identifiers_and_reviews_title_match() -> None:
    first = _candidate("Optical Character Recognition", "10.1000/a")
    second = _candidate("Optical Character Recognition", "10.1000/b")
    canonical = Canonicalizer().canonicalize_candidates([first, second])
    assert len(canonical) == 2
    assert canonical[1]["identity_review"] == [canonical[0]["paper"].paper_id]
    duplicate = _candidate("OCR: improved methods", "10.1000/a")
    merged = Canonicalizer().canonicalize_candidates([first, duplicate])
    assert len(merged) == 1
    assert merged[0]["merge_history"][0]["signals"]["reason"] == "exact_doi_match"
    versioned = PaperRecord(
        title="Another paper", identifiers=PaperIdentifiers(arxiv_id="2401.00001v3")
    )
    assert ("arxiv_id", "2401.00001") in PostgresResearchStore._identifier_pairs(versioned)


def test_evidence_pointer_needs_a_real_location() -> None:
    pointer = SimpleNamespace(
        provenance_id="p1",
        artifact_sha256="abc",
        page=2,
        tei_xpath=None,
        char_start=None,
        char_end=None,
        bbox=None,
        table_id=None,
    )
    claim = SimpleNamespace(provenance_ids=["p1"])
    extraction = {"provenance": [pointer], "claims": [claim]}
    assert not ResearchJobRunner._verify_evidence(extraction, "abc")
    pointer.tei_xpath = "/TEI/text/body/p"
    assert ResearchJobRunner._verify_evidence(extraction, "abc")


def test_rights_and_missing_features_never_invent_values() -> None:
    rights = RightsResolver()
    denied = rights.resolve_access(True, None, "https://publisher.example/paper.pdf")
    assert not denied["can_fetch_fulltext"]
    assert not rights.resolve_access(
        True, "https://creativecommons.org/licenses/by/4.0/", "http://example.org/pdf"
    )["can_fetch_fulltext"]
    assert rights.resolve_access(True, None, "https://arxiv.org/pdf/2401.00001.pdf")[
        "can_fetch_fulltext"
    ]
    paper = PaperRecord(title="Optical character recognition", abstract=None)
    features = {f.feature_name: f for f in FeatureEngine().compute_features(paper, "OCR", {})}
    for name in (
        "abstract_query_similarity",
        "citation_count_snapshot",
        "log_citations",
        "evidence_backed_claim_ratio",
        "code_available",
        "BM25",
    ):
        assert features[name].value is None
        assert features[name].status in {StatusEnum.UNKNOWN, StatusEnum.NOT_REPORTED}


def test_shortlist_is_unaffected_by_citations_or_author_reputation() -> None:
    relevant = _candidate("Optical character recognition for manuscripts", "10.1000/a", 0)
    irrelevant = _candidate("Quantum spin in metals", "10.1000/b", 999999)
    irrelevant["paper"].abstract = "Magnetic states and electron spin"
    irrelevant["h_index"] = 500
    irrelevant["institution_prestige"] = 100
    result = shortlist([irrelevant, relevant], "optical character recognition")
    assert [paper["doi"] for paper in result] == ["10.1000/a"]
    assert result[0]["topic_relevance_reason"]


def test_rate_limit_preserves_response_hash_and_failure_state() -> None:
    body = b'{"error":"rate limit"}'
    response = SimpleNamespace(
        status_code=429,
        ok=False,
        content=body,
        headers={"x-request-id": "req-1"},
    )
    session = SimpleNamespace(get=lambda *args, **kwargs: response)
    result = LiveResearchSources(session=session).search("semantic_scholar", "OCR", 5)
    assert result.status == "rate_limited"
    assert len(result.records) == 0
    assert result.raw_sha256 == hashlib.sha256(body).hexdigest()
    assert result.request_id == "req-1"


def test_runner_checkpoints_real_states_without_ingesting_fulltext() -> None:
    class Store:
        def __init__(self):
            self.saved = []
            self.states = []
            self.events = []

        def source_payload(self, *_):
            return None

        def save_source(self, *_):
            return None

        def update_job(self, _job_id, **state):
            self.states.append(state)

        def resolve_identity(self, paper):
            return paper.paper_id

        def save_paper(self, _job_id, item):
            self.saved.append(item)

        def save_features(self, *_):
            return None

        def enqueue_projection(self, job_id):
            self.events.append(job_id)

    class Sources:
        def search(self, source, _topic, _limit):
            records = [_candidate("Optical character recognition", "10.1000/a")]
            if source != "openalex":
                records = []
            return SourceResponse(
                source=source,
                requested_at="2026-10-16T00:00:00Z",
                status="live" if records else "live_empty",
                records=records,
            )

    store = Store()
    job_id = str(uuid.uuid4())
    result = ResearchJobRunner(store, sources=Sources()).run(
        {"job_id": job_id, "topic": "optical character recognition"}
    )
    assert result["counts"]["metadata_validated"] == 1
    assert result["counts"]["metadata_only"] == 1
    assert result["counts"]["fulltext_parsed"] == 0
    assert result["status"] == "partial"
    assert "fewer_than_five_relevant_papers" in result["coverage_gaps"]
    assert store.events == [job_id]


def test_job_audit_has_required_fields(caplog) -> None:
    with caplog.at_level(logging.INFO, logger="archipelago.research.audit"):
        audit_action(
            user_id="staff-1",
            role="faculty",
            action="job_create",
            research_job_id="job-1",
            topic="OCR",
            result="accepted",
        )
    event = json.loads(caplog.records[-1].message)
    assert set(event) == {
        "user_id",
        "role",
        "action",
        "research_job_id",
        "topic",
        "timestamp",
        "result",
    }


def test_graph_projection_rebuilds_from_canonical_records(tmp_path) -> None:
    paper_id = str(uuid.uuid4())
    paper = PaperRecord(
        paper_id=paper_id,
        title="Optical character recognition",
        identifiers=PaperIdentifiers(doi="10.1000/ocr"),
        authors=[PaperAuthor(name="A Researcher")],
        venue="A Journal",
    )
    store = SimpleNamespace(
        projection_records=lambda: [{"paper_id": paper_id, "paper": paper.model_dump(mode="json")}],
        projection_evidence=lambda: [],
    )
    path = tmp_path / "research.kuzu"
    first = rebuild_projection(store, path)
    assert first["papers"] == 1 and first["authors"] == 1
    assert (
        json.loads(path.with_suffix(".vector-inputs.jsonl").read_text().splitlines()[0])["paper_id"]
        == paper_id
    )
    path.unlink()
    path.with_suffix(".vector-inputs.jsonl").unlink()
    second = rebuild_projection(store, path)
    assert first == second


def test_projection_refresh_publishes_pointer_after_rebuild(tmp_path) -> None:
    paper_id = str(uuid.uuid4())
    paper = PaperRecord(title="Bengali speech recognition", paper_id=paper_id)
    completed = []
    store = SimpleNamespace(
        projection_records=lambda: [{"paper_id": paper_id, "paper": paper.model_dump(mode="json")}],
        projection_evidence=lambda: [],
        pending_projection_events=lambda: ["research-job:test"],
        complete_projection_events=lambda keys, path: completed.append((keys, path)),
    )
    result = refresh_pending_projection(store, tmp_path / "projections")
    pointer = json.loads((tmp_path / "projections/current.json").read_text())
    assert pointer["graph_path"] == result["graph_path"]
    assert completed[0][0] == ["research-job:test"]
