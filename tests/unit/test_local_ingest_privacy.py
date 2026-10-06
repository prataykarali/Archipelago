"""Raw library uploads must never leave the local appliance boundary."""

from __future__ import annotations

from io import BytesIO
from types import SimpleNamespace

import pytest

from archipelago.middleware.local_ingest_origin import local_ingest_origin

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _disable_auth_for_transport_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ARCHIPELAGO_ENV", "development")
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")
    monkeypatch.setenv("ARCHIPELAGO_INFERENCE_URL", "https://cloud.example")
    monkeypatch.delenv("ARCHIPELAGO_LOCAL_INGEST_URL", raising=False)


@pytest.mark.parametrize(
    "origin",
    ["https://cloud.example", "http://cloud.example", "http://127.0.0.1@cloud.example"],
)
def test_cloud_ingest_origins_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
    origin: str,
) -> None:
    monkeypatch.setenv("ARCHIPELAGO_LOCAL_INGEST_URL", origin)
    assert local_ingest_origin() is None


@pytest.mark.parametrize("app_name", ["chat_server", "graph_server"])
def test_upload_never_falls_back_to_cloud(
    monkeypatch: pytest.MonkeyPatch,
    app_name: str,
) -> None:
    import chat_server
    import graph_server

    def forbidden_network_call(*args: object, **kwargs: object) -> None:
        raise AssertionError("raw upload reached an upstream")

    monkeypatch.setattr(
        chat_server.merged08_librarian_upload._requests, "post", forbidden_network_call
    )
    monkeypatch.setattr(graph_server.requests, "request", forbidden_network_call)
    app = chat_server.app if app_name == "chat_server" else graph_server.app
    response = app.test_client().post(
        "/api/ingest",
        data={"file": (BytesIO(b"private PDF bytes"), "private.pdf")},
    )
    assert response.status_code == 503


def test_local_upload_does_not_follow_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    import chat_server

    monkeypatch.setenv("ARCHIPELAGO_LOCAL_INGEST_URL", "http://127.0.0.1:5151")
    monkeypatch.setattr(
        chat_server.merged08_librarian_upload,
        "_inference_auth_headers",
        lambda: {"Authorization": "Bearer verified-session"},
    )
    calls: list[tuple[str, bool, object]] = []

    def local_post(url: str, **kwargs: object) -> SimpleNamespace:
        calls.append((url, kwargs["allow_redirects"] is False, kwargs["headers"]))
        return SimpleNamespace(
            content=b"redirect blocked",
            status_code=302,
            headers={"Content-Type": "text/plain", "Location": "https://cloud.example"},
        )

    monkeypatch.setattr(chat_server.merged08_librarian_upload._requests, "post", local_post)
    response = chat_server.app.test_client().post(
        "/api/librarian/upload",
        data={"file": (BytesIO(b"private PDF bytes"), "private.pdf")},
        headers={"Authorization": "Bearer untrusted-header"},
    )
    assert response.status_code == 302
    assert calls == [
        (
            "http://127.0.0.1:5151/api/ingest",
            True,
            {"Authorization": "Bearer verified-session"},
        )
    ]


def test_graph_proxy_rejects_raw_body_on_cloud_route(monkeypatch: pytest.MonkeyPatch) -> None:
    import graph_server

    def forbidden_network_call(*args: object, **kwargs: object) -> None:
        raise AssertionError("raw body reached cloud inference")

    monkeypatch.setattr(graph_server.requests, "request", forbidden_network_call)
    response = graph_server.app.test_client().post(
        "/api/other-route",
        data=b"private PDF bytes",
        content_type="application/pdf",
    )
    assert response.status_code == 415


def test_graph_upload_targets_explicit_local_service(monkeypatch: pytest.MonkeyPatch) -> None:
    import graph_server

    monkeypatch.setenv(
        "ARCHIPELAGO_LOCAL_INGEST_URL",
        "http://archipelago-ingestion:5151",
    )
    targets: list[tuple[str, bool]] = []

    def local_request(method: str, url: str, **kwargs: object) -> SimpleNamespace:
        targets.append((url, kwargs["allow_redirects"] is False))
        return SimpleNamespace(
            headers={"Content-Type": "application/json"},
            status_code=202,
            iter_content=lambda chunk_size: iter([b'{"status":"queued"}']),
        )

    monkeypatch.setattr(graph_server.requests, "request", local_request)
    response = graph_server.app.test_client().post(
        "/api/ingest",
        data={"file": (BytesIO(b"private PDF bytes"), "private.pdf")},
    )
    assert response.status_code == 202
    assert targets == [("http://archipelago-ingestion:5151/api/ingest", True)]
