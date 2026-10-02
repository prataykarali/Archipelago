"""Gateway configuration, provider selection, and availability probing.

xkiro is the PRIMARY provider; Google Gemini is the cloud failover.
"""

from __future__ import annotations

import logging
import os
import threading
import time

logger = logging.getLogger(__name__)

# Thread Safety for configuration.
_config_lock = threading.RLock()
_is_configured = False
_openai_client = None

LLM_UNAVAILABLE_MSG = (
    "The library closed — the librarian is waking up and will be with you shortly. "
    "The library is currently closed. Please hold while I stoke the intellectual furnaces..."
)

# Provider & API Configuration — the chain is xkiro → nvidia.
#
# OpenRouter was removed deliberately: NVIDIA NIM is cheaper, logs no prompts
# through a third party, and keeps the key inside one vendor.  Gemini is no
# longer in the default chain either; it stays reachable only when an operator
# pins ARCHIPELAGO_LLM_PROVIDER=gemini, which keeps the deployment honest (no
# silent third-party prompt logging) without deleting working code.
XKIRO_BASE_URL = os.environ.get("XKIRO_BASE_URL", "https://api.xkiro.com/v1")
XKIRO_API_KEY = os.environ.get("XKIRO_API_KEY", "").strip()
XKIRO_DEFAULT_MODEL = os.environ.get("XKIRO_MODEL", "qwen/qwen3.8-max:free")

NVIDIA_BASE_URL = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "").strip()
NVIDIA_DEFAULT_MODEL = os.environ.get("NVIDIA_MODEL", "deepseek-ai/deepseek-v4.1-flash")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

DEFAULT_PROVIDER = os.environ.get("ARCHIPELAGO_LLM_PROVIDER", "xkiro").lower()

#: Failover order when no provider is pinned. Both speak the OpenAI
#: chat-completions protocol, so one call path serves both.
PROVIDER_FALLBACK_ORDER = ("xkiro", "nvidia")

#: Providers reachable only when explicitly pinned, never as a silent fallback.
_PINNED_ONLY = ("gemini",)

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
# A cold NIM reasoning model needs longer to answer a one-word ping than a
# free-tier xkiro model does; probing it with the xkiro timeout reports a
# healthy NVIDIA endpoint as down and pushes traffic to whatever comes next.
NVIDIA_AVAILABILITY_TIMEOUT_SECONDS = 30
#: NVIDIA NIM reasoning models answer slowly; the SDK default of 60s is not enough.
DEFAULT_NVIDIA_TIMEOUT_SECONDS = 120
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
    """Return the pinned provider name, or the head of the fallback chain.

    ``gemini`` is accepted for backwards compatibility but is not in
    ``PROVIDER_FALLBACK_ORDER``: it is reachable only when explicitly pinned.
    """
    pinned = os.environ.get("ARCHIPELAGO_LLM_PROVIDER", "").strip().lower()
    if pinned:
        return pinned
    return PROVIDER_FALLBACK_ORDER[0]


def nvidia_chat(
    payload: dict,
    stream: bool = False,
    timeout: int = DEFAULT_NVIDIA_TIMEOUT_SECONDS,
):
    """Call NVIDIA NIM over plain HTTP and return the decoded body.

    Deliberately *not* the OpenAI SDK.  The SDK's transport (HTTP/2 plus
    Brotli/zstd content negotiation) stalls against ``integrate.api.nvidia.com``
    — every SDK call timed out at 90s while an identical ``requests.post``
    returned 200 in seconds.  The hosted engine already talks to the endpoint with
    ``requests``; this keeps the two stacks on one working transport instead of
    shipping a fallback that reports NVIDIA as permanently down.

    Returns the parsed JSON dict, or ``None`` on any failure.
    """
    import requests

    api_key = os.environ.get("NVIDIA_API_KEY", NVIDIA_API_KEY).strip()
    base_url = os.environ.get("NVIDIA_BASE_URL", NVIDIA_BASE_URL).rstrip("/")
    if not api_key:
        return None
    body = dict(payload)
    body.setdefault("model", os.environ.get("NVIDIA_MODEL", NVIDIA_DEFAULT_MODEL))
    try:
        response = requests.post(
            f"{base_url}/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                # Avoid content encodings the endpoint negotiates badly.
                "Accept-Encoding": "identity",
            },
            json=body,
            stream=stream,
            timeout=timeout,
        )
        response.raise_for_status()
        return response
    except Exception as exc:
        logger.warning("nvidia request failed: %s", exc.__class__.__name__)
        return None


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

            # 2. NVIDIA NIM needs no client object: it is called over requests
            #    in nvidia_chat, because the OpenAI SDK transport stalls on this host.

            # 3. Gemini — kept importable, not in the default chain.
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


def _probe_openai_compatible(client, model: str, label: str, timeout: int) -> bool:
    """Whether an OpenAI-compatible endpoint answers a trivial ping.

    Judged on ``res.choices`` rather than on returned text: the NVIDIA NIM
    reasoning models spend their first tokens on ``reasoning_content`` and can
    exhaust a tiny ``max_tokens`` before emitting any visible content, so an
    empty completion there means "answered, no text yet", not "unreachable".
    The timeout is passed per provider because a cold reasoning endpoint needs
    far longer than a free-tier xkiro model.
    """
    try:
        res = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": AVAILABILITY_PING}],
            max_tokens=AVAILABILITY_MAX_TOKENS,
            timeout=timeout,
        )
        return bool(res.choices)
    except Exception as exc:
        logger.warning("%s availability check failed: %s", label, exc)
        return False


def is_llm_available() -> bool:
    """Check if the provider chain is reachable. 5-second TTL cache.

    Probes each leg of ``PROVIDER_FALLBACK_ORDER`` in turn, so an xkiro outage
    reports the chain as available while NVIDIA is serving.  The probe judges
    ``res.choices``, never returned text: NVIDIA NIM reasoning models spend
    their first tokens on ``reasoning_content``, so an empty content field there
    means "answered, no prose yet", not "unreachable".
    """
    global _availability_cache
    now = time.time()
    if now - _availability_cache["time"] < AVAILABILITY_TTL_SECONDS:
        return _availability_cache["status"]

    configure_gateway()
    provider = get_active_provider()
    status = False
    last_provider = provider

    if provider == "xkiro" and _openai_client is not None and _probe_openai_compatible(
        _openai_client, XKIRO_DEFAULT_MODEL, "xkiro", AVAILABILITY_TIMEOUT_SECONDS
    ):
        status = True

    if not status:
        nvidia_body = nvidia_chat(
            {"messages": [{"role": "user", "content": AVAILABILITY_PING}],
             "max_tokens": AVAILABILITY_MAX_TOKENS},
            timeout=NVIDIA_AVAILABILITY_TIMEOUT_SECONDS,
        )
        if nvidia_body is not None:
            status, last_provider = True, "nvidia"

    # Gemini is a last resort *only* when no NVIDIA key is configured. With one
    # present the deployment stays inside the declared xkiro → nvidia chain
    # rather than silently shipping prompts to a provider nobody pinned.
    if not status and provider not in _PINNED_ONLY and not NVIDIA_API_KEY:
        try:
            import google.generativeai as genai

            list(genai.list_models())
            status, last_provider = True, "gemini"
        except Exception as exc:
            logger.error("No provider in the fallback chain is reachable: %s", exc)

    _availability_cache["status"] = status
    _availability_cache["time"] = time.time()
    _availability_cache["provider"] = last_provider
    return status
