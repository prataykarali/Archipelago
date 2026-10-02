"""Synchronous chat across providers with automatic failover (xkiro primary)."""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

from archipelago.inference.llm_gateway import part01_config as config
from archipelago.inference.llm_gateway.part01_config import (
    DEFAULT_NVIDIA_TIMEOUT_SECONDS,
    GEMINI_FALLBACK_MODEL,
    GEMINI_PURPOSE_MAP,
    MAX_XKIRO_ATTEMPTS,
    XKIRO_DEFAULT_MODEL,
    _PINNED_ONLY,
)
from archipelago.inference.llm_gateway.part02_sanitize import (
    _clean_messages_for_openai,
    _convert_messages_for_gemini,
)

logger = logging.getLogger(__name__)

DEFAULT_MAX_TOKENS = 2048
DEFAULT_TIMEOUT_SECONDS = 30

#: NVIDIA NIM reasoning models (``deepseek-*``, ``qwen*-thinking``) spend their
#: first tokens on ``reasoning_content`` and only then emit visible content.  A
#: reply budget below this floor therefore returns an empty completion from a
#: perfectly healthy endpoint, which looks exactly like an outage.  Requests for
#: fewer tokens are raised to the floor rather than silently returning nothing.
NVIDIA_MIN_MAX_TOKENS = 512


def _chat_xkiro(
    messages: List[Dict],
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[str]:
    """Execute chat via xkiro OpenAI-compatible API."""
    config.configure_gateway()
    client = config._openai_client
    if client is None:
        return None
    model_name = model or XKIRO_DEFAULT_MODEL
    cleaned_msgs = _clean_messages_for_openai(messages)
    for attempt in range(MAX_XKIRO_ATTEMPTS):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=cleaned_msgs,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            if response.choices and response.choices[0].message:
                return response.choices[0].message.content or ""
            return None
        except Exception as exc:
            delay = config.xkiro_retry_delay(exc, attempt)
            if delay is None:
                logger.warning("xkiro chat attempt failed (%s)", exc.__class__.__name__)
                break
            logger.info("xkiro returned a transient error; retrying once after %.2fs", delay)
            time.sleep(delay)
    return None


def _chat_gemini(
    messages: List[Dict],
    purpose: str = "general",
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[str]:
    """Execute chat via Gemini API."""
    config.configure_gateway()
    try:
        import google.generativeai as genai
        from google.generativeai.types import RequestOptions

        selected_model = model or GEMINI_PURPOSE_MAP.get(purpose, GEMINI_FALLBACK_MODEL)
        system_instruction, formatted_history = _convert_messages_for_gemini(messages)

        kwargs = {
            "model_name": selected_model,
            "generation_config": genai.GenerationConfig(
                temperature=temperature,
                max_output_tokens=max_tokens,
            ),
        }
        if system_instruction:
            kwargs["system_instruction"] = system_instruction

        gemini_model = genai.GenerativeModel(**kwargs)
        response = gemini_model.generate_content(
            formatted_history,
            request_options=RequestOptions(timeout=timeout),
        )
        return response.text
    except Exception as exc:
        logger.warning("Gemini chat attempt failed: %s", exc)
    return None


def _chat_nvidia(
    messages: List[Dict],
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = DEFAULT_NVIDIA_TIMEOUT_SECONDS,
) -> Optional[str]:
    """Execute chat via NVIDIA NIM.

    The fallback leg of the xkiro → nvidia chain.  Uses ``config.nvidia_chat``
    (plain HTTP) rather than the OpenAI SDK, whose transport stalls on this
    endpoint — see that function for the measurement.
    """
    payload = {
        "messages": _clean_messages_for_openai(messages),
        "temperature": temperature,
        "max_tokens": max(max_tokens, NVIDIA_MIN_MAX_TOKENS),
    }
    if model:
        payload["model"] = model
    response = config.nvidia_chat(payload, timeout=timeout)
    if response is None:
        return None
    try:
        choices = response.json()["choices"]
    except (ValueError, KeyError, IndexError, TypeError):
        logger.warning("nvidia returned an unparseable completion")
        return None
    if not choices:
        return None
    return choices[0].get("message", {}).get("content") or ""


def _provider_order(provider: str) -> tuple:
    """Providers to try, in order, starting at ``provider``.

    A pinned-but-not-in-chain provider (gemini) stands alone, so pinning it is
    an explicit opt-in rather than a silent reordering of the chain.
    """
    if provider in _PINNED_ONLY:
        return (provider,)
    if provider in config.PROVIDER_FALLBACK_ORDER:
        return config.PROVIDER_FALLBACK_ORDER
    return (provider, *config.PROVIDER_FALLBACK_ORDER)


def _chat_by_name(
    provider: str,
    messages: List[Dict],
    purpose: str = "general",
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[str]:
    """Dispatch one chat call to the named provider."""
    if provider == "xkiro":
        return _chat_xkiro(
            messages, model=model, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout,
        )
    if provider == "nvidia":
        return _chat_nvidia(
            messages, model=model, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout,
        )
    if provider == "gemini":
        return _chat_gemini(
            messages, purpose=purpose, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout,
        )
    logger.warning("Unknown provider %r; skipping", provider)
    return None


def gateway_chat(
    messages: List[Dict],
    purpose: str = "general",
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Optional[str]:
    """Synchronous chat across the provider chain with automatic failover.

    Order is ``config.PROVIDER_FALLBACK_ORDER`` (xkiro → nvidia). ``gemini`` is
    attempted only when an operator has pinned it, so no prompt leaves for a
    third-party processor by accident.
    """
    config.configure_gateway()
    provider = config.get_active_provider()
    start_time = time.time()

    order = _provider_order(provider)
    text = None
    for name in order:
        text = _chat_by_name(
            name, messages, purpose=purpose, model=model,
            temperature=temperature, max_tokens=max_tokens, timeout=timeout,
        )
        if text is not None:
            break
        logger.info("Failing over from %s to the next provider for purpose: %s", name, purpose)

    if text is not None:
        latency_ms = (time.time() - start_time) * 1000
        print(
            f"gateway_chat | Provider: {provider} | Purpose: {purpose} | Latency: {latency_ms:.2f}ms"
        )
    return text
