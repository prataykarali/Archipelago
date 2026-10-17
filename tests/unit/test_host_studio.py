"""The restored graph studio remains a staff-only hosted surface."""

from __future__ import annotations

from pathlib import Path
import sys
from types import SimpleNamespace

from flask import Flask

HOST = Path(__file__).resolve().parents[2] / "host_inference"
if str(HOST) not in sys.path:
    sys.path.insert(0, str(HOST))

from hostapp.routes import static, studio  # noqa: E402


class Graph:
    corpus_source = "fixture"

    def __init__(self) -> None:
        self.nodes = {
            "ocr": {
                "label": "Optical Character Recognition",
                "summary": "Read text in images.",
                "sources": [
                    {"doc_id": "papers/ocr.pdf", "page_number": 2, "private_note": "hidden"}
                ],
            },
            "vision": {"label": "Computer Vision", "summary": "Image understanding."},
        }
        self.out = {"ocr": [("REQUIRES", "vision")]}

    def label(self, node_id: str) -> str:
        return self.nodes[node_id]["label"]


def _app(role: str | None) -> Flask:
    principal = {"id": "test-user", "role": role} if role else None
    ctx = SimpleNamespace(
        auth=SimpleNamespace(principal=lambda: (principal, None)),
        engine=SimpleNamespace(graph=Graph()),
    )
    app = Flask(__name__)
    static.register(app, ctx)
    studio.register(app, ctx)
    return app


def test_studio_denies_student_and_anonymous_requests() -> None:
    for role, page_status, api_status in ((None, 302, 401), ("student", 403, 403)):
        client = _app(role).test_client()
        assert client.get("/studio").status_code == page_status
        assert client.get("/studio/").status_code == page_status
        assert client.get("/api/studio/graph").status_code == api_status
        assert client.get("/studio/assets/js/index.js").status_code == api_status
        assert client.get("/studio/index.html").status_code == 404


def test_studio_allows_staff_and_projects_source_fields() -> None:
    for role in ("faculty", "librarian", "administrator"):
        client = _app(role).test_client()
        page = client.get("/studio")
        assert page.status_code == 200
        assert b"Knowledge Studio" in page.data
        assert client.get("/studio/assets/js/index.js").status_code == 200
        response = client.get("/api/studio/graph")
        assert response.status_code == 200
        data = response.get_json()
        assert data["corpus_source"] == "fixture"
        assert data["read_only"] is True
        assert data["nodes"][0]["sources"][0]["page_number"] == 2
        assert "private_note" not in data["nodes"][0]["sources"][0]
        assert data["edges"] == [{"source": "ocr", "target": "vision", "relation": "requires"}]
