"""Unit tests for credential redaction in log output."""
from __future__ import annotations

import logging

import pytest

from archipelago.middleware.log_redaction import (
    REDACTED,
    RedactingFilter,
    install_log_redaction,
    redact,
)

pytestmark = pytest.mark.unit

# A structurally valid (dummy) JWT: header.payload.signature.
DUMMY_JWT = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
    ".eyJzdWIiOiJ1bml0LXRlc3QiLCJyb2xlIjoic3R1ZGVudCJ9"
    ".c2lnbmF0dXJlLWRvLW5vdC11c2U"
)


def test_redacts_jwt() -> None:
    out = redact(f"GET /?token={DUMMY_JWT}")
    assert DUMMY_JWT not in out
    assert REDACTED in out


def test_redacts_bearer_header() -> None:
    out = redact(f"Authorization: Bearer {DUMMY_JWT}")
    assert DUMMY_JWT not in out
    assert REDACTED in out


def test_redacts_bare_authorization_token() -> None:
    out = redact("Authorization: opaque-token-abc123")
    assert "opaque-token-abc123" not in out
    assert REDACTED in out


@pytest.mark.parametrize(
    "text",
    [
        "?token=abc123secret",
        "?access_token=abc123secret",
        "?api_key=abc123secret",
        "password=abc123secret",
        "client_secret=abc123secret",
    ],
)
def test_redacts_secret_assignments(text: str) -> None:
    out = redact(f"GET /login {text}")
    assert "abc123secret" not in out
    assert REDACTED in out


def test_leaves_benign_text_untouched() -> None:
    text = "GET /api/roadmap?concept=bert HTTP/1.1 200"
    assert redact(text) == text


def test_filter_rewrites_message_and_args() -> None:
    record = logging.LogRecord(
        name="werkzeug",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="%s -> %s",
        args=(f"/?token={DUMMY_JWT}", "200"),
        exc_info=None,
    )
    assert RedactingFilter().filter(record) is True
    assert DUMMY_JWT not in record.getMessage()
    assert "200" in record.getMessage()


def test_install_is_idempotent() -> None:
    install_log_redaction()
    install_log_redaction()
    filters = [f for f in logging.getLogger().filters if isinstance(f, RedactingFilter)]
    assert len(filters) == 1


def test_filter_preserves_numeric_args_for_percent_formatting() -> None:
    """Regression: a numeric arg must survive the filter so ``%d`` still works.

    The filter used to stringify every arg. Once installed process-wide (it is,
    in the apps), any ``logger.warning("n=%d", 180)`` raised
    ``TypeError: %d format: a real number is required, not str`` inside the
    logging handler — which surfaced as an unrelated test failing only when the
    full suite had already installed redaction.
    """
    record = logging.LogRecord(
        name="archipelago.graph.graph_fusion",
        level=logging.WARNING,
        pathname="",
        lineno=0,
        msg="Batch size (%d) exceeds max threshold (%d).",
        args=(180, 150),
        exc_info=None,
    )
    assert RedactingFilter().filter(record) is True
    assert record.getMessage() == "Batch size (180) exceeds max threshold (150)."


def test_filter_still_redacts_numeric_looking_secret_strings() -> None:
    """A secret passed as a string is still masked, even if it looks numeric."""
    record = logging.LogRecord(
        name="archipelago",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="pin=%s",
        args=("token=999888777",),
        exc_info=None,
    )
    assert RedactingFilter().filter(record) is True
    assert "999888777" not in record.getMessage()
    assert REDACTED in record.getMessage()


def test_filter_preserves_mapping_arg_types() -> None:
    """Dict-style args keep their value types so ``%(name)d`` still works."""
    # logging stores mapping args wrapped in a 1-tuple for LogRecord compatibility.
    record = logging.LogRecord(
        name="archipelago",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="count=%(count)d",
        args=({"count": 42},),
        exc_info=None,
    )
    assert RedactingFilter().filter(record) is True
    assert record.getMessage() == "count=42"
