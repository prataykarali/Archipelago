"""Scrub credentials from log output.

Access logs can capture query strings (``?token=…``), ``Authorization: Bearer``
headers, and JWTs. Those must never reach a log file or console. Install the
filter once at process start — it rewrites both the message and its args before
any handler formats the record.

Usage::

    from archipelago.middleware.log_redaction import install_log_redaction
    install_log_redaction()          # root + werkzeug + gunicorn.access
"""
from __future__ import annotations

import logging
import re

REDACTED = "[REDACTED]"

# JWT: three base64url segments. The header always base64-decodes to {"...".
_JWT_RE = re.compile(r"eyJ[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{6,}")

# ``token=…``/``api_key=…``/``password=…`` in a query string or key=value text.
_SECRET_ASSIGN_RE = re.compile(
    r"(?i)\b("
    r"token|access_token|refresh_token|id_token|apikey|api_key|api-key|"
    r"password|passwd|pwd|secret|client_secret|session|authorization"
    r")(\s*[:=]\s*|\s+)([^\s&\"'<>]+)"
)

# ``Bearer <token>``.
_BEARER_RE = re.compile(r"(?i)(bearer\s+)([A-Za-z0-9._\-]+)")


def redact(text: str) -> str:
    """Return ``text`` with JWTs, bearer tokens, and secret assignments masked."""
    text = _JWT_RE.sub(REDACTED, text)
    text = _BEARER_RE.sub(lambda m: m.group(1) + REDACTED, text)
    text = _SECRET_ASSIGN_RE.sub(lambda m: m.group(1) + m.group(2) + REDACTED, text)
    return text


class RedactingFilter(logging.Filter):
    """A logging filter that redacts credentials from records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact(str(v)) for k, v in record.args.items()}
            else:
                record.args = tuple(redact(str(a)) for a in record.args)
        return True


_LOGGER_NAMES = ("", "werkzeug", "gunicorn.access", "gunicorn.error")


def install_log_redaction(*extra_logger_names: str) -> None:
    """Attach :class:`RedactingFilter` to the app, server, and root loggers."""
    redacting = RedactingFilter()
    for name in _LOGGER_NAMES + tuple(extra_logger_names):
        logger = logging.getLogger(name)
        if not any(isinstance(f, RedactingFilter) for f in logger.filters):
            logger.addFilter(redacting)
        for handler in logger.handlers:
            if not any(isinstance(f, RedactingFilter) for f in handler.filters):
                handler.addFilter(redacting)
