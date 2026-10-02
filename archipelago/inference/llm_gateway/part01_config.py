"""Gateway configuration, provider selection, and availability probing.

xkiro is the PRIMARY provider; Google Gemini is the cloud failover.
"""

from __future__ import annotations

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

# Thread Safety for configuration
_config_lock = threading.Lock()
_is_configured = False
_openai_client = None

LLM_UNAVAILABLE_MSG = (
    "The library closed — the librarian is waking up and will be with you shortly. "
    "The library is currently closed. Please hold while I stoke the intellectual furnaces..."
)

# Provider & API Configuration — xkiro stays primary
XKIRO_BASE_URL = os.environ.get("XKIRO_BASE_URL", "https://api.xkiro.com/v1")
XKIRO_API_KEY = os.environ.get("XKIRO_API_KEY", "").strip()
XKIRO_DEFAULT_MODEL = os.environ.get("XKIRO_MODEL", "qwen/qwen3.8-max:free")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

DEFAULT_PROVIDER = os.environ.get("ARCHIPELAGO_LLM_PROVIDER", "xkiro").lower()

GEMINI_MODELS = {
    "gemini-3.5-flash": "gemini-3.5-flash",
    "gemini-3.5-flash-lite": "gemini-3.5-flash-lite",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.5-pro": "gemini-2.5-pro",
}

GEMINI_PURPOSE_MAP = {
    "routing": "gemini-3.5-flash-lite",
    "identity": "gemini-3.5-flash-lite",
    "chat": "gemini-3.5-flash-lite",
    "synthesis": "gemini-3.5-flash",
    "roadmap": "gemini-3.5-flash",
    "complex": "gemini-3.5-flash",
    "agent": "gemini-3.5-flash",
}

GEMINI_FALLBACK_MODEL = "gemini-2.0-flash"
GEMINI_TOOLS_FALLBACK_MODEL = "gemini-2.5-pro"

MAX_XKIRO_ATTEMPTS = 2
MAX_RETRY_AFTER_SECONDS = 3.0
MIN_RETRY_DELAY_SECONDS = 0.1
AVAILABILITY_TTL_SECONDS = 5.0
AVAILABILITY_TIMEOUT_SECONDS = 8
AVAILABILITY_MAX_TOKENS = 5
AVAILABILITY_PING = "ping"

_availability_cache = {"time": 0.0, "status": False, "provider": ""}


def xkiro_retry_delay(exc: Exception, attempt: int) -> float | None:
    """Return a short bounded retry delay for transient upstream failures."""
    status = getattr(exc, "status_code", None)
    if status is None:
        status = getattr(getattr(exc, "response", None), "status_code", None)
    retryable = status == 429 or (isinstance(status, int) and 500 <= status < 600)
    retryable = retryable or exc.__class__.__name__ in {"APITimeoutError", "APIConnectionError"}
    if not retryable or attempt >= 1:
        return None
    headers = getattr(getattr(exc, "response", None), "headers", {}) or {}
    try:
        retry_after = float(headers.get("retry-after", 0))
    except (TypeError, ValueError):
        retry_after = 0
    # Respect short Retry-After hints; long waits immediately fall back to the
    # secondary provider instead of holding a web request open.
    delay = retry_after if 0 < retry_after <= MAX_RETRY_AFTER_SECONDS else 0.25 * (2**attempt)
    return min(MAX_RETRY_AFTER_SECONDS, max(MIN_RETRY_DELAY_SECONDS, delay))


def get_active_provider() -> str:
    """Return active provider ('xkiro' or 'gemini')."""
    return os.environ.get("ARCHIPELAGO_LLM_PROVIDER", DEFAULT_PROVIDER).lower()


def configure_gateway():
    """Initialize clients with API keys from env. Thread-safe."""
    global _is_configured, _openai_client
    with _config_lock:
        if not _is_configured:
            # 1. Initialize OpenAI client for xkiro (primary)
            try:
                from openai import OpenAI

                api_key = os.environ.get("XKIRO_API_KEY", XKIRO_API_KEY).strip()
                base_url = os.environ.get("XKIRO_BASE_URL", XKIRO_BASE_URL)
                if api_key:
                    _openai_client = OpenAI(base_url=base_url, api_key=api_key)
                else:
                    logger.warning("XKIRO_API_KEY is not configured; xkiro is disabled")
            except Exception as exc:
                logger.warning("Failed to initialize OpenAI client for xkiro: %s", exc)

            # 2. Initialize Gemini GenAI client (failover)
            try:
                import google.generativeai as genai

                g_key = os.environ.get("GEMINI_API_KEY", GEMINI_API_KEY).strip()
                if g_key:
                    genai.configure(api_key=g_key)
                else:
                    logger.warning("GEMINI_API_KEY is not configured; gemini is disabled")
            except Exception as exc:
                logger.warning("Failed to configure Google Generative AI: %s", exc)

            _is_configured = True


def is_llm_available() -> bool:
    """Check if LLM API is reachable. 5-second TTL cache."""
    global _availability_cache
    now = time.time()
    if now - _availability_cache["time"] < AVAILABILITY_TTL_SECONDS:
        return _availability_cache["status"]

    configure_gateway()
    provider = get_active_provider()
    status = False

    # Try active provider (xkiro first)
    if provider == "xkiro" and _openai_client is not None:
        try:
            res = _openai_client.chat.completions.create(
                model=XKIRO_DEFAULT_MODEL,
                messages=[{"role": "user", "content": AVAILABILITY_PING}],
                max_tokens=AVAILABILITY_MAX_TOKENS,
                timeout=AVAILABILITY_TIMEOUT_SECONDS,
            )
            status = bool(res.choices)
        except Exception as e:
            logger.warning("xkiro availability check failed: %s; trying gemini fallback", e)
            provider = "gemini"

    if not status:
        try:
            import google.generativeai as genai

            list(genai.list_models())
            status = True
        except Exception as e:
            logger.error("Gemini availability check also failed: %s", e)
            status = False

    _availability_cache["status"] = status
    _availability_cache["time"] = time.time()
    _availability_cache["provider"] = provider
    return status
