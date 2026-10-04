"""Reader failures must not masquerade as verified books or PDFs."""
from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask
import pytest
import requests

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "host_inference"))
from hostapp import hf_delivery  # noqa: E402
from hostapp.routes import reader  # noqa: E402
from pearson_handoff import handoff  # noqa: E402
from remote_cache import pearson_page_url  # noqa: E402

from archipelago.resolver import pearson  # noqa: E402

pytestmark = pytest.mark.unit
BOOK = {"id": "fixture-book", "title": "Synthetic Reader Test", "book_type": "pdf", "page_count": 20, "subscription_id": "test-sub"}
PATH = "textbooks/synthetic.pdf"


@pytest.fixture
def client(monkeypatch):
    app = Flask(__name__)
    app.config["TESTING"] = True
    reader.register(app, None)
    monkeypatch.setattr(reader, "load_books", lambda: [BOOK])
    monkeypatch.setattr(reader, "_hf_doc_path", lambda value: value)
    def resolve(value):
        return PATH if value == PATH else ""
    monkeypatch.setattr(reader, "resolve_hf_path", resolve)
    monkeypatch.setattr(hf_delivery, "resolve_hf_path", resolve)
    monkeypatch.setenv("HF_TOKEN", "synthetic-test-credential")
    return app.test_client()


class Upstream:
    def __init__(self, status=200, chunks=None):
        self.status_code = status
        self.chunks = chunks if chunks is not None else [b"%PDF-1.7\n", b"synthetic test bytes"]
        self.closed = False

    def iter_content(self, _size):
        yield from self.chunks

    def close(self):
        self.closed = True


@pytest.mark.parametrize("page", ["0", "-1", "garbage", "1.5"])
@pytest.mark.parametrize("route", ["/api/page-view?doc=fixture-book&page=", "/open/fixture-book?page=", "/api/reader/info/fixture-book?page="])
def test_invalid_pages_are_not_silently_changed(client, page, route):
    assert client.get(route + page).status_code == 400


def test_unknown_manifest_document_rejected_before_network(client, monkeypatch):
    monkeypatch.setattr(hf_delivery.requests, "get", lambda *a, **k: pytest.fail("unknown file fetched"))
    for route in ("/api/page-view?doc=unknown.pdf&format=json", "/api/reader/info/unknown.pdf", "/papers/unknown.pdf"):
        assert client.get(route).status_code == 404


def test_missing_credential_is_explicit(client, monkeypatch):
    monkeypatch.delenv("HF_TOKEN")
    response = client.get(f"/papers/{PATH}")
    assert response.status_code == 503
    assert response.json["error"] == "unavailable"


@pytest.mark.parametrize("status,expected,code", [(401, 503, "dataset_access_denied"), (403, 503, "dataset_access_denied"), (404, 404, "not_found"), (500, 502, "upstream_unavailable")])
def test_upstream_errors_distinguished_and_closed(client, monkeypatch, status, expected, code):
    upstream = Upstream(status)
    monkeypatch.setattr(hf_delivery.requests, "get", lambda *a, **k: upstream)
    result = client.get(f"/papers/{PATH}")
    assert result.status_code == expected
    assert result.json["error"] == code
    assert "synthetic-test-credential" not in result.text
    assert upstream.closed


@pytest.mark.parametrize("chunks", [[b"<html>login</html>"], [b""], [b"%PD"], [b'{"error":"denied"}']])
def test_200_non_pdf_is_not_delivered_as_pdf(client, monkeypatch, chunks):
    upstream = Upstream(chunks=chunks)
    monkeypatch.setattr(hf_delivery.requests, "get", lambda *a, **k: upstream)
    result = client.get(f"/papers/{PATH}")
    assert result.status_code == 502
    assert result.json["error"] == "invalid_pdf"
    assert upstream.closed


def test_pdf_signature_and_custom_dataset_and_stream_cleanup(client, monkeypatch):
    upstream = Upstream(chunks=[b"%P", b"DF", b"-1.7\n", b"synthetic"])
    def fetch(url, **kwargs):
        assert "/datasets/owner/CaseSensitive/resolve/main/textbooks/synthetic.pdf" in url
        assert kwargs["headers"]["Authorization"] == "Bearer synthetic-test-credential"
        return upstream
    monkeypatch.setenv("HF_DATASET_REPO", "owner/CaseSensitive")
    monkeypatch.setattr(hf_delivery.requests, "get", fetch)
    result = client.get(f"/papers/{PATH}")
    assert result.status_code == 200
    assert result.data.startswith(b"%PDF-")
    assert result.headers["Cache-Control"] == "private, no-store"
    assert result.mimetype == "application/pdf"
    result.close()
    assert upstream.closed


def test_network_failure_is_not_file_not_found(client, monkeypatch):
    def fail(*a, **k):
        raise requests.Timeout("synthetic secret-bearing upstream error")
    monkeypatch.setattr(hf_delivery.requests, "get", fail)
    result = client.get(f"/papers/{PATH}")
    assert result.status_code == 502
    assert "secret-bearing" not in result.text


def test_manifest_resolution_not_page_verification(client):
    result = client.get(f"/api/page-view?doc={PATH}&page=3&format=json")
    assert result.json["status"] == "manifest_only"
    assert result.json["page_verified"] is False
    assert result.json["page"] == 3


def test_pearson_manual_handoff_not_fake_deep_link(client):
    url = pearson_page_url(BOOK, 12)
    assert "#book/fixture-book" in url and "/page/" not in url
    for path in ("/open/fixture-book?page=12", "/open/book/fixture-book?page=12"):
        response = client.get(path)
        assert response.status_code == 200
        assert "page 12" in response.text
        assert "not verified" in response.text
        assert "window.location" not in response.text
        assert "/page/12" not in response.text
    assert client.get("/open/fixture-book?page=21").status_code == 400
    info = client.get("/api/reader/info/fixture-book?page=12").json
    assert info["reader_url"] == "/open/fixture-book?page=12"
    assert info["page_verified"] is False


def test_resolver_does_not_claim_authentication(monkeypatch):
    monkeypatch.setattr(pearson, "_PEARSON_CATALOG_CACHE", [BOOK])
    for kwargs in ({"book_id": BOOK["id"]}, {"existing_url": pearson_page_url(BOOK)}, {"book_id": "other", "subscription_id": "sub"}):
        result = pearson.resolve_pearson_url(**kwargs)
        assert result["url_available"]
        assert not result["verified"] and not result["access_verified"] and not result["page_verified"]
        assert result["status"] == "unverified" and result["last_verified"] is None


@pytest.mark.parametrize("url", ["https://pearson.com.evil.invalid/", "https://evil.invalid/?x=pearson.com", "javascript:alert(1)", "http://ebooks.elibrary.in.pearson.com/"])
def test_pearson_url_allowlist(client, monkeypatch, url):
    monkeypatch.setattr(pearson, "_PEARSON_CATALOG_CACHE", [])
    assert not pearson.resolve_pearson_url(existing_url=url)["working"]
    with client.application.app_context(), pytest.raises(ValueError):
        handoff("test", url, 1)


def test_pearson_title_is_escaped(client):
    with client.application.app_context():
        body = handoff("<script>bad</script>", pearson_page_url(BOOK), 3)
        assert "<script>" not in body
        assert "&lt;script&gt;" in body


def test_empty_and_partial_book_names_are_not_guessed(client):
    assert client.get("/api/page-view?format=json").status_code == 404
    assert client.get("/api/page-view?doc=Synthetic&format=json").status_code == 404
    response = client.get("/api/page-view?doc=Synthetic%20Reader%20Test&format=json")
    assert response.json["doc_id"] == BOOK["id"]
