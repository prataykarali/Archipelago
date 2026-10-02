"""Scrub credentials from log output. Standalone copy for the hosted deploy.

``host_inference`` is deployed on its own: AntDeploy builds the
``host_inference`` directory as the image root, so the sibling ``archipelago``
package is not present and ``from archipelago.middleware.log_redaction import …``
fails with the container unable to boot. Earlier attempts to fix that with
``PYTHONPATH`` do not work either, because the platform generates the start
command itself and reported ``startCommand: null``.

So the filter lives here too. It is a deliberate copy rather than a shared import
because a deployment that cannot import its own redaction filter would log raw
bearer tokens and query-string secrets — which is a worse outcome than
duplicating thirty lines.

The two implementations are pinned together by
``tests/unit/test_host_log_redaction.py``, which runs the same corpus through both
and fails on any divergence. If the archipelago copy changes, that test says so.

Usage::

    from hostapp.log_redaction import install_log_redaction
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

_LOGGER_NAMES = ("", "werkzeug", "gunicorn.access", "gunicorn.error")


def redact(text: str) -> str:
    """Return ``text`` with JWTs, bearer tokens, and secret assignments masked."""
    text = _JWT_RE.sub(REDACTED, text)
    text = _BEARER_RE.sub(lambda m: m.group(1) + REDACTED, text)
    text = _SECRET_ASSIGN_RE.sub(lambda m: m.group(1) + m.group(2) + REDACTED, text)
    return text


class RedactingFilter(logging.Filter):
    """A logging filter that redacts credentials from records.

    Args are only rewritten when they are *text*. Converting an ``int`` arg to
    ``str`` would break ``%d`` formatting at handler time — a real crash, seen in
    the suite as ``TypeError: %d format: a real number is required, not str`` —
    so numeric and other opaque args are passed through untouched.
    """

    def filter(self, record: logging.LoggingRecord) -> bool:
        record.msg = redact(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact(v) if isinstance(v, str) else v for k, v in record.args.items()
                }
            else:
                record.args = tuple(
                    redact(a) if isinstance(a, str) else a for a in record.args
                )
        return True


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


__all__ = [
    "REDACTED",
    "RedactingFilter",
    "install_log_redaction",
    "redact",
]
