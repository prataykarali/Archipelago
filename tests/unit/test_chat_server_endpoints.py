"""Unit tests for chat_server endpoints and video asset serving."""

import pytest
from unittest.mock import patch, MagicMock
from chat_server import ASSETS_DIR, _STREAM_CHUNK_BYTES, app

pytestmark = pytest.mark.usefixtures("verified_student_auth")


@pytest.mark.unit
def test_chat_server_assets_exist():
    """Verify librarian avatar video assets exist in ui/assets."""
    assert (ASSETS_DIR / "library_hi.mp4").exists()
    assert (ASSETS_DIR / "library_think.mp4").exists()
    assert (ASSETS_DIR / "archi_main.mp4").exists()


@pytest.mark.unit
def test_chat_server_serves_video_assets_200():
    """Verify Flask client serves video assets with HTTP 200 OK and video/mp4 MIME type."""
    client = app.test_client()
    for asset in ["library_hi.mp4", "library_think.mp4", "archi_main.mp4"]:
        resp = client.get(f"/ui/assets/{asset}")
        assert resp.status_code == 200, f"Failed for {asset}"
        assert "video/mp4" in resp.content_type.lower(), f"Expected video/mp4 for {asset}, got {resp.content_type}"


@pytest.mark.unit
def test_chat_server_serves_video_assets_206_range():
    """Verify Flask client serves video assets with HTTP 206 Partial Content when Range header is provided."""
    client = app.test_client()
    for asset in ["library_hi.mp4", "library_think.mp4"]:
        resp = client.get(f"/ui/assets/{asset}", headers={"Range": "bytes=0-100"})
        assert resp.status_code == 206, f"Expected 206 Partial Content for {asset}, got {resp.status_code}"
        assert "video/mp4" in resp.content_type.lower()
        assert "bytes 0-100/" in resp.headers.get("Content-Range", "")


@pytest.mark.unit
def test_chat_server_serves_index():
    """Verify Flask client serves / index page."""
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code in (200, 404)  # 200 if static index exists, handled gracefully


@pytest.mark.unit
def test_chat_server_api_chat_options():
    """Verify OPTIONS preflight request to /api/chat returns 204 No Content."""
    client = app.test_client()
    resp = client.options("/api/chat")
    assert resp.status_code == 204
    assert resp.headers.get("Access-Control-Allow-Origin") == "*"


@pytest.mark.unit
def test_chat_server_api_chat_proxy_success():
    """Verify POST /api/chat proxies streaming response from upstream inference server."""
    client = app.test_client()
    mock_upstream = MagicMock()
    mock_upstream.status_code = 200
    mock_upstream.headers = {"Content-Type": "text/event-stream"}
    mock_upstream.iter_content.return_value = [b"data: hello\n\n"]

    with patch("chat_server._requests.post", return_value=mock_upstream) as mock_post:
        resp = client.post("/api/chat", json={"prompt": "Hello"})
        assert resp.status_code == 200
        assert resp.data == b"data: hello\n\n"
        mock_post.assert_called_once()
        mock_upstream.iter_content.assert_called_once_with(
            chunk_size=_STREAM_CHUNK_BYTES
        )


@pytest.mark.unit
def test_chat_server_api_chat_proxy_upstream_down():
    """Verify POST /api/chat returns HTTP 502 Bad Gateway when upstream server is down."""
    client = app.test_client()
    with patch("chat_server._requests.post", side_effect=Exception("Connection refused")):
        resp = client.post("/api/chat", json={"prompt": "Hello"})
        assert resp.status_code == 502
        assert resp.is_json
        assert "error" in resp.get_json()
