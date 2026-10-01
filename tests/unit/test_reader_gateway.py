"""Unit tests for Archipelago Reader Gateway (/open/ and /read/), PDF.js reader, and Pearson redirect."""
from __future__ import annotations

import pytest
from chat_server import app, _build_redirect_shell
from archipelago import supabase_auth


def _fake_student_principal(request):  # noqa: ANN001, ARG001
    principal = supabase_auth.AuthPrincipal(
        user_id="test-user-id",
        username="gateway-tester",
        role="student",
        access_token="unit-test-token",
    )
    return principal, None


@pytest.fixture
def client(monkeypatch):
    """Test client with an explicitly verified Supabase-style principal."""
    app.config["TESTING"] = True
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setattr(supabase_auth, "authenticate_request", _fake_student_principal)
    with app.test_client() as client:
        yield client


@pytest.fixture
def anon_client(monkeypatch):
    """Test client on the real unauthenticated code path (no session at all)."""
    app.config["TESTING"] = True
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    with app.test_client() as client:
        yield client


def test_reader_gateway_hf_textbook_redirects_to_internal_reader(client):
    """HF textbook -> /open/<id> redirects to /read/<id>."""
    # Use authenticated cookie
    client.set_cookie("archipelago_user", "authenticated")
    resp = client.get("/open/book_math_for_machine_learning_2020")
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/read/book_math_for_machine_learning_2020")


def test_reader_gateway_hf_paper_redirects_to_internal_reader(client):
    """HF paper -> /open/<id> redirects to /read/<id>."""
    client.set_cookie("archipelago_user", "authenticated")
    resp = client.get("/open/paper_attention_is_all_you_need_2017")
    assert resp.status_code == 302
    assert resp.headers["Location"].startswith("/read/paper_attention_is_all_you_need_2017")


def test_reader_gateway_exact_page_navigation(client):
    """HF PDF -> /open/<id>?page=25 preserves page query param for PDF.js."""
    client.set_cookie("archipelago_user", "authenticated")
    resp = client.get("/open/book_math_for_machine_learning_2020?page=25")
    assert resp.status_code == 302
    assert "page=25" in resp.headers["Location"]
    assert resp.headers["Location"].startswith("/read/book_math_for_machine_learning_2020?page=25")


def test_reader_gateway_book_prefix_handled(client):
    """Path with /open/book/<id> handles prefix cleanly."""
    client.set_cookie("archipelago_user", "authenticated")
    resp = client.get("/open/book/book_math_for_machine_learning_2020?page=42")
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/read/book_math_for_machine_learning_2020?page=42"


def test_reader_ui_serves_html(client):
    """GET /read/<id> serves the PDF.js reader application HTML."""
    client.set_cookie("archipelago_user", "authenticated")
    resp = client.get("/read/book_math_for_machine_learning_2020?page=25")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "pdfjsLib" in html
    assert "Archipelago Document Reader" in html
    assert "pdf-canvas" in html


def test_reader_info_api_for_hf_resource(client):
    """GET /api/reader/info/<id> returns metadata and streaming PDF URL."""
    resp = client.get("/api/reader/info/book_math_for_machine_learning_2020?page=15")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["provider"] == "huggingface"
    assert "Mathematics for Machine Learning" in data["title"]
    assert data["pdf_url"].startswith("/pdfs/")
    assert data["page"] == 15


def test_reader_gateway_pearson_book_opens_new_tab(client):
    """Pearson book -> /open/<id> returns new-tab HTML redirect shell with credentials."""
    client.set_cookie("archipelago_user", "authenticated")
    # Tanenbaum Computer Networks 6e
    resp = client.get("/open/0fcd531f-3ba1-495e-9c9e-b43b034b88d9?page=10")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "window.open" in html
    assert "_blank" in html
    assert "ebooks.elibrary.in.pearson.com" in html
    assert "0fcd531f-3ba1-495e-9c9e-b43b034b88d9" in html
    # The gateway points to the exact book/page without exposing shared credentials.
    assert "page/10" in html
    assert "library.uemk@uem.edu.in" not in html
    assert "Central-Library@#1" not in html


def test_reader_ui_pearson_redirects_to_open_gateway(client):
    """If /read/<id> is accessed for a Pearson book, it redirects to /open/<id>."""
    client.set_cookie("archipelago_user", "authenticated")
    resp = client.get("/read/0fcd531f-3ba1-495e-9c9e-b43b034b88d9?page=5")
    assert resp.status_code == 302
    assert "/open/0fcd531f-3ba1-495e-9c9e-b43b034b88d9" in resp.headers["Location"]


def test_unauthenticated_request_redirects_to_login(anon_client):
    """Unauthenticated users opening Archipelago routes must be redirected to /login."""
    # No cookies set, no verified session
    resp = anon_client.get("/chat")
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]

    resp_lib = anon_client.get("/library")
    assert resp_lib.status_code == 302
    assert "/login" in resp_lib.headers["Location"]

    resp_open = anon_client.get("/open/book_math_for_machine_learning_2020")
    assert resp_open.status_code == 302
    assert "/login" in resp_open.headers["Location"]


def test_unauthenticated_cannot_fetch_catalogs_or_pearson_metadata(anon_client):
    for path in (
        "/api/library/data",
        "/api/catalog/all",
        "/data/catalogs/pearson_bookshelf.json",
    ):
        response = anon_client.get(path)
        assert response.status_code == 401, path


def test_unauthenticated_cannot_use_chat_or_reader_apis(anon_client):
    responses = (
        anon_client.post("/api/chat", json={"query": "RAG"}),
        anon_client.get("/api/page-view?doc_id=paper.pdf&page=1"),
        anon_client.get("/api/reader/info/paper.pdf"),
    )
    assert [response.status_code for response in responses] == [401, 401, 401]
