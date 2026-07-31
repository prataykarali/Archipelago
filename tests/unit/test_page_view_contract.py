"""Citation page links must never silently show an unrelated chunk."""

from archipelago.inference.state import app
import archipelago.inference.routes_page_view as page_view_routes


class _NoRows:
    def has_next(self):
        return False


class _NoPageConnection:
    def __init__(self):
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        return _NoRows()


def test_missing_cited_page_is_explicit_not_a_first_chunk_fallback(monkeypatch):
    connection = _NoPageConnection()
    monkeypatch.setattr(page_view_routes, "get_db_connection", lambda: connection)

    with app.test_client() as client:
        response = client.get("/api/page-view?doc_id=paper.pdf&page=42&highlight=attention")

    assert response.status_code == 404
    body = response.get_json()
    assert "cited page 42" in body["error"] or "not found" in body["error"].lower()
    # Chunk lookup + optional document-only fallback
    assert len(connection.calls) >= 1
    assert body.get("pdf_available") is False
