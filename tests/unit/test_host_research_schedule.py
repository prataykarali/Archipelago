"""Scheduled research intake requires its own secret and stays bounded."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from hostapp.routes import research_schedule  # noqa: E402


def _app() -> Flask:
    app = Flask(__name__)
    research_schedule.register(app, None)  # type: ignore[arg-type]
    return app


def test_schedule_rejects_missing_configuration(monkeypatch) -> None:
    monkeypatch.delenv("CRON_SECRET", raising=False)
    response = _app().test_client().get("/api/research/intake/scheduled")
    assert response.status_code == 503


def test_schedule_rejects_missing_or_wrong_secret(monkeypatch) -> None:
    monkeypatch.setenv("CRON_SECRET", "test-schedule-secret")
    client = _app().test_client()
    assert client.get("/api/research/intake/scheduled").status_code == 401
    assert (
        client.get(
            "/api/research/intake/scheduled",
            headers={"Authorization": "Bearer wrong-secret"},
        ).status_code
        == 401
    )


def test_schedule_fetches_requested_topic_with_valid_secret(monkeypatch) -> None:
    monkeypatch.setenv("CRON_SECRET", "test-schedule-secret")
    calls: list[str] = []

    def discover(topic: str, updated_by: str | None):
        assert updated_by is None
        calls.append(topic)
        return [{"record_key": "paper:test"}], ["arxiv"]

    monkeypatch.setattr(research_schedule, "discover_papers", discover)
    monkeypatch.setattr(research_schedule, "save_records", lambda records: len(records))
    monkeypatch.setattr(research_schedule, "audit_action", lambda **kwargs: None)
    client = _app().test_client()
    response = client.get(
        "/api/research/intake/scheduled?topic_index=0",
        headers={"Authorization": "Bearer test-schedule-secret"},
    )
    assert response.status_code == 200
    assert calls == [research_schedule.TOPICS[0]]
    assert response.json["topics"][0]["saved"] == 1
    assert response.json["topics"][0]["scholar_review_url"].startswith(
        "https://scholar.google.com/"
    )
    assert response.json["topics"][0]["ingestion_status"] == "not_started"
    assert response.json["college"] == "not_attempted"


def test_schedule_rejects_out_of_range_topic(monkeypatch) -> None:
    monkeypatch.setenv("CRON_SECRET", "test-schedule-secret")
    response = (
        _app()
        .test_client()
        .get(
            "/api/research/intake/scheduled?topic_index=999",
            headers={"Authorization": "Bearer test-schedule-secret"},
        )
    )
    assert response.status_code == 400
