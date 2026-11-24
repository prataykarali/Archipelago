"""Read and update existing Supabase runtime state and coordinate graceful shutdown."""

from __future__ import annotations

import atexit
from collections.abc import Callable
from functools import lru_cache
import os
from pathlib import Path
import re
import signal
import subprocess
import threading
import time
from typing import Any

import requests

RUNTIME_TIMEOUT_SECONDS = 10
DEFAULT_DRAIN_TIMEOUT_SECONDS = 5.0
_RPC_NAME_RE = re.compile(r"^[a-zA-Z0-9_]{1,128}$")

_SHUTDOWN_COND = threading.Condition()
_SHUTTING_DOWN = False
_CALLBACKS_EXECUTED = False
_IN_FLIGHT_REQUESTS = 0
_SHUTDOWN_CALLBACKS: list[Callable[[], Any]] = []
_HANDLERS_INSTALLED = False


def is_shutting_down() -> bool:
    """Return True once graceful shutdown has been initiated."""
    with _SHUTDOWN_COND:
        return _SHUTTING_DOWN


def in_flight_requests() -> int:
    """Return the number of currently active in-flight HTTP requests."""
    with _SHUTDOWN_COND:
        return _IN_FLIGHT_REQUESTS


def begin_request() -> bool:
    """Increment the active request counter if not shutting down.

    Returns True if the request was admitted, or False if the server is draining.
    """
    global _IN_FLIGHT_REQUESTS
    with _SHUTDOWN_COND:
        if _SHUTTING_DOWN:
            return False
        _IN_FLIGHT_REQUESTS += 1
        return True


def end_request() -> int:
    """Decrement the active request counter and notify any waiting shutdown drain."""
    global _IN_FLIGHT_REQUESTS
    with _SHUTDOWN_COND:
        _IN_FLIGHT_REQUESTS = max(0, _IN_FLIGHT_REQUESTS - 1)
        if _IN_FLIGHT_REQUESTS == 0:
            _SHUTDOWN_COND.notify_all()
        return _IN_FLIGHT_REQUESTS


def register_shutdown_callback(callback: Callable[[], Any]) -> Callable[[], Any]:
    """Register a cleanup callback to execute once in-flight requests drain on shutdown."""
    if not callable(callback):
        raise TypeError("Shutdown callback must be callable")
    with _SHUTDOWN_COND:
        if callback not in _SHUTDOWN_CALLBACKS:
            _SHUTDOWN_CALLBACKS.append(callback)
    return callback


on_shutdown = register_shutdown_callback


def initiate_shutdown(drain_timeout: float = DEFAULT_DRAIN_TIMEOUT_SECONDS) -> dict[str, Any]:
    """Transition to shutting-down state, wait for in-flight requests to drain, and run callbacks."""
    global _SHUTTING_DOWN, _CALLBACKS_EXECUTED
    with _SHUTDOWN_COND:
        _SHUTTING_DOWN = True
        deadline = time.monotonic() + max(0.0, float(drain_timeout))
        while _IN_FLIGHT_REQUESTS > 0:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            _SHUTDOWN_COND.wait(timeout=remaining)
        should_run = not _CALLBACKS_EXECUTED
        _CALLBACKS_EXECUTED = True
        callbacks = list(_SHUTDOWN_CALLBACKS) if should_run else []
        remaining_in_flight = _IN_FLIGHT_REQUESTS

    executed = 0
    errors = 0
    for callback in callbacks:
        try:
            callback()
            executed += 1
        except Exception:
            errors += 1
    return {
        "shutting_down": True,
        "drained": remaining_in_flight == 0,
        "in_flight": remaining_in_flight,
        "callbacks_run": executed,
        "callback_errors": errors,
    }


def reset_shutdown_state(clear_callbacks: bool = False) -> None:
    """Reset shutdown state (used by test suites after testing drain transitions)."""
    global _SHUTTING_DOWN, _CALLBACKS_EXECUTED, _IN_FLIGHT_REQUESTS
    with _SHUTDOWN_COND:
        _SHUTTING_DOWN = False
        _CALLBACKS_EXECUTED = False
        _IN_FLIGHT_REQUESTS = 0
        if clear_callbacks:
            _SHUTDOWN_CALLBACKS.clear()
        _SHUTDOWN_COND.notify_all()


def _atexit_shutdown() -> None:
    initiate_shutdown(drain_timeout=1.0)


def install_shutdown_handlers() -> None:
    """Register atexit and main-thread SIGTERM/SIGINT handlers safely."""
    global _HANDLERS_INSTALLED
    with _SHUTDOWN_COND:
        if _HANDLERS_INSTALLED:
            return
        _HANDLERS_INSTALLED = True
    try:
        atexit.register(_atexit_shutdown)
    except Exception:
        pass
    if threading.current_thread() is not threading.main_thread():
        return
    try:
        prev_term = signal.getsignal(signal.SIGTERM)

        def _handle_sigterm(signum: int, frame: Any) -> None:
            initiate_shutdown(drain_timeout=2.0)
            if callable(prev_term) and prev_term not in (signal.SIG_DFL, signal.SIG_IGN):
                prev_term(signum, frame)
            elif prev_term != signal.SIG_IGN:
                signal.signal(signum, signal.SIG_DFL)
                os.kill(os.getpid(), signum)

        signal.signal(signal.SIGTERM, _handle_sigterm)
    except (ValueError, OSError, RuntimeError):
        pass
    if not os.environ.get("PYTEST_CURRENT_TEST") and "pytest" not in os.environ.get("_", ""):
        try:
            prev_int = signal.getsignal(signal.SIGINT)

            def _handle_sigint(signum: int, frame: Any) -> None:
                initiate_shutdown(drain_timeout=1.0)
                if callable(prev_int) and prev_int not in (signal.SIG_DFL, signal.SIG_IGN):
                    prev_int(signum, frame)
                elif prev_int != signal.SIG_IGN:
                    signal.signal(signum, signal.SIG_DFL)
                    os.kill(os.getpid(), signum)

            signal.signal(signal.SIGINT, _handle_sigint)
        except (ValueError, OSError, RuntimeError):
            pass


@lru_cache(maxsize=1)
def _git_head_sha() -> str:
    """Resolve local git HEAD once for non-Vercel provenance reporting."""
    repo_root = Path(__file__).resolve().parents[2]
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        sha = (proc.stdout or "").strip()
        if proc.returncode == 0 and len(sha) >= 7:
            return sha
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def runtime_release_sha() -> str:
    """Return the active runtime release SHA from env or local git HEAD."""
    for key in ("ARCHIPELAGO_RELEASE_SHA", "ARCHIPELAGO_RELEASE", "VERCEL_GIT_COMMIT_SHA"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return _git_head_sha() or "unknown"


def hosted_runtime() -> bool:
    """Use durable runtime state on ephemeral Vercel instances."""
    return bool(os.environ.get("VERCEL"))


def runtime_rpc(name: str, payload: dict[str, Any]) -> Any:
    """Call a pre-existing server-only RPC, failing closed on storage errors."""
    if not _RPC_NAME_RE.fullmatch(name or ""):
        raise ValueError("Invalid runtime RPC identifier")
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.environ.get("SUPABASE_SECRET_KEY", "").strip()
        or os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    )
    if not url or not key:
        raise RuntimeError("Durable account state is not configured")
    try:
        response = requests.post(
            f"{url}/rest/v1/rpc/{name}",
            json=payload,
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=RUNTIME_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()
    except (requests.RequestException, ValueError) as exc:
        raise RuntimeError(f"Durable account state RPC failed ({type(exc).__name__})") from None


__all__ = [
    "begin_request",
    "end_request",
    "hosted_runtime",
    "in_flight_requests",
    "initiate_shutdown",
    "install_shutdown_handlers",
    "is_shutting_down",
    "on_shutdown",
    "register_shutdown_callback",
    "reset_shutdown_state",
    "runtime_release_sha",
    "runtime_rpc",
]
