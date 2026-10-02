"""The hosted deploy carries its own redaction filter; keep the two identical.

``host_inference`` is built as its own image root, so it cannot import
``archipelago.middleware.log_redaction``. That leaves two implementations of a
security control, which is only acceptable while a test proves they agree on
every shape of secret. If the shared one is edited, this fails.
"""
from __future__ import annotations

from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = REPO_ROOT / "host_inference"
# Both roots: host_inference for the flat modules the app imports, the repo root
# so ``host_inference.hostapp`` is importable as a package.
for _root in (REPO_ROOT, HOST_DIR):
    if str(_root) not in sys.path:
        sys.path.insert(0, str(_root))

pytestmark = pytest.mark.unit

#: Every shape a credential can arrive in, and the part that must not survive.
SECRET_CORPUS = (
    ("GET /api/chat?token=sk-abc123&page=2", "sk-abc123"),
    ("Authorization: Bearer nvapi-abc.def-ghi", "nvapi-abc.def-ghi"),
    ("password=hunter2", "hunter2"),
    ("client_secret: s3cr3t-value", "s3cr3t-value"),
    ("api_key=abcdef123456", "abcdef123456"),
    ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.dBjftJeZ4CVP", "eyJhbGciOiJIUzI1NiJ9"),
    ("access_token tok_live_99", "tok_live_99"),
    ("SESSION=abc123xyz", "abc123xyz"),
)


def _shared_redact():
    """The shared implementation, or skip when the package is absent."""
    shared = pytest.importorskip(
        "archipelago.middleware.log_redaction",
        reason="the shared redaction filter is not importable from here",
    )
    return shared.redact


@pytest.mark.parametrize(("text", "secret"), SECRET_CORPUS)
def test_local_filter_removes_the_secret(text, secret):
    from host_inference.hostapp.log_redaction import redact

    assert secret not in redact(text), f"{secret!r} survived redaction"


@pytest.mark.parametrize(("text", "secret"), SECRET_CORPUS)
def test_local_and_shared_filters_agree(text, secret):
    """The duplication is only safe while the two behave identically."""
    from host_inference.hostapp.log_redaction import redact as local

    shared = _shared_redact()
    assert local(text) == shared(text), f"filters diverged on {text!r}"
    assert secret not in local(text)


def test_local_filter_leaves_ordinary_text_alone():
    from host_inference.hostapp.log_redaction import redact

    clean = "answered third normal form from Silberschatz page 214"
    assert redact(clean) == clean


def test_numeric_log_args_are_not_stringified():
    """``%d`` formatting must survive; stringifying args was a real crash."""
    import logging

    from host_inference.hostapp.log_redaction import RedactingFilter

    record = logging.LogRecord("t", logging.INFO, __file__, 1, "took %d ms", (42,), None)
    assert RedactingFilter().filter(record) is True
    assert record.args == (42,)
    assert "took " + str(record.args[0]) + " ms" == "took 42 ms"


def test_dict_args_are_walked_and_shaped_secrets_masked():
    """Named args go through ``redact`` individually, not as one blob."""
    import logging

    from host_inference.hostapp.log_redaction import RedactingFilter

    record = logging.LogRecord("t", logging.INFO, __file__, 1, "auth", (), None)
    record.args = {
        "url": "https://x/api?token=sk-abc123",
        "attempts": 3,
    }
    RedactingFilter().filter(record)
    assert "sk-abc123" not in record.args["url"]
    # Non-string args are passed through untouched so %d still formats.
    assert record.args["attempts"] == 3


def test_a_bare_token_is_a_known_gap():
    """Documented limitation, not an accident.

    The filter matches secrets by *shape* — ``key=value``, ``Bearer x``, or a
    JWT.  A bare credential value is not recognised, however it is passed: as a
    positional argument (``logger.info("sending %s", token)``) or as the value
    under a named key.  The key names the secret but the filter does not treat a
    key as a pattern to redact its value.

    Pinned so the gap stays visible; when it is closed in the shared filter this
    test is what will say which behaviour changed.
    """
    import logging

    from host_inference.hostapp.log_redaction import RedactingFilter

    record = logging.LogRecord(
        "t", logging.INFO, __file__, 1, "sending %s", ("sk-abc123",), None
    )
    RedactingFilter().filter(record)
    assert record.args == ("sk-abc123",), (
        "the bare-arg gap has been closed; update SECRET_CORPUS expectations and "
        "the shared filter together, and say so in the README"
    )


def test_hosted_app_does_not_import_archipelago_at_module_level():
    """The import that broke the container must not creep back in."""
    source = (HOST_DIR / "hostapp" / "factory.py").read_text(encoding="utf-8")
    module_level = [
        line
        for line in source.splitlines()
        if line.startswith(("import ", "from ")) and "archipelago" in line
    ]
    assert not module_level, f"module-level archipelago import(s): {module_level}"


def test_installation_is_idempotent():
    """Two filters on one logger double-redact and hide the original message."""
    import logging

    from host_inference.hostapp.log_redaction import install_log_redaction

    install_log_redaction("archipelago.test.redaction")
    install_log_redaction("archipelago.test.redaction")
    logger = logging.getLogger("archipelago.test.redaction")
    installed = [f for f in logger.filters if type(f).__name__ == "RedactingFilter"]
    assert len(installed) == 1
