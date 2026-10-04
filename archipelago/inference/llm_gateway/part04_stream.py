"""Streaming chat across providers with automatic failover (xkiro primary)."""

from __future__ import annotations

import logging
import time
from typing import Dict, Generator, List, Optional

from archipelago.inference.llm_gateway import part01_config as config
from archipelago.inference.llm_gateway.part01_config import (
    DEFAULT_NVIDIA_TIMEOUT_SECONDS,
    GEMINI_FALLBACK_MODEL,
    GEMINI_PURPOSE_MAP,
    MAX_XKIRO_ATTEMPTS,
    XKIRO_DEFAULT_MODEL,
)
from archipelago.inference.llm_gateway.part02_sanitize import (
    _clean_messages_for_openai,
    _convert_messages_for_gemini,
)
from archipelago.inference.llm_gateway.part03_chat import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TIMEOUT_SECONDS,
    NVIDIA_MIN_MAX_TOKENS,
    _provider_order,
)

logger = logging.getLogger(__name__)


def _stream_xkiro(
    messages: List[Dict],
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Generator[str, None, None]:
    """Stream text tokens via xkiro OpenAI-compatible API."""
    config.configure_gateway()
    client = config._openai_client
    if client is None:
        raise RuntimeError("OpenAI client for xkiro not initialized")
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
                stream=True,
            )
            break
        except Exception as exc:
            delay = config.xkiro_retry_delay(exc, attempt)
            if delay is None:
                raise
            logger.info(
                "xkiro stream was rate limited or unavailable; retrying once after %.2fs", delay
            )
            time.sleep(delay)
    for chunk in response:
        if chunk.choices and chunk.choices[0].delta:
            content = chunk.choices[0].delta.content
            if content:
                yield content


def _stream_gemini(
    messages: List[Dict],
    purpose: str = "synthesis",
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Generator[str, None, None]:
    """Stream text tokens via Gemini API."""
    config.configure_gateway()
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
        stream=True,
        request_options=RequestOptions(timeout=timeout),
    )
    for chunk in response:
        if chunk.text:
            yield chunk.text


def _stream_nvidia(
    messages: List[Dict],
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = DEFAULT_NVIDIA_TIMEOUT_SECONDS,
) -> Generator[str, None, None]:
    """Stream text tokens from NVIDIA NIM over plain HTTP SSE.

    Mirrors :func:`_chat_nvidia`: the SDK transport stalls on this endpoint, so
    the SSE frames are parsed from a ``requests`` stream instead.
    """
    import json as _json

    payload = {
        "messages": _clean_messages_for_openai(messages),
        "temperature": temperature,
        "max_tokens": max(max_tokens, NVIDIA_MIN_MAX_TOKENS),
        "stream": True,
    }
    if model:
        payload["model"] = model
    response = config.nvidia_chat(payload, stream=True, timeout=timeout)
    if response is None:
        raise RuntimeError("nvidia stream unavailable")

    for raw in response.iter_lines():
        if not raw:
            continue
        line = raw.decode("utf-8", errors="replace")
        if not line.startswith("data: "):
            continue
        frame = line[len("data: "):].strip()
        if frame == "[DONE]":
            break
        try:
            choices = _json.loads(frame)["choices"]
        except (ValueError, KeyError, TypeError):
            continue
        if not choices:
            continue
        delta = choices[0].get("delta") or {}
        if delta.get("content"):
            yield delta["content"]


def _stream_by_name(
    provider: str,
    messages: List[Dict],
    purpose: str = "general",
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Generator[str, None, None]:
    """Yield tokens from one named provider's stream."""
    if provider == "xkiro":
        return _stream_xkiro(
            messages, model=model, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout,
        )
    if provider == "nvidia":
        return _stream_nvidia(
            messages, model=model, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout,
        )
    if provider == "gemini":
        return _stream_gemini(
            messages, purpose=purpose, temperature=temperature,
            max_tokens=max_tokens, timeout=timeout,
        )
    raise RuntimeError(f"unknown provider {provider!r}")


def gateway_chat_stream(
    messages: List[Dict],
    purpose: str = "synthesis",
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> Generator[str, None, None]:
    """Stream text across the provider chain with automatic failover.

    Order is ``config.PROVIDER_FALLBACK_ORDER`` (xkiro → nvidia), matching the
    non-streaming path so a reply does not come from a different vendor purely
    because the chat client streamed it.
    """
    config.configure_gateway()
    provider = config.get_active_provider()
    start_time = time.time()
    order = _provider_order(provider)

    emitted = False
    for name in order:
        try:
            for chunk in _stream_by_name(
                name,
                messages,
                purpose=purpose,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            ):
                if chunk:
                    emitted = True
                    yield chunk
            latency_ms = (time.time() - start_time) * 1000
            print(
                f"gateway_chat_stream | Provider: {name} | Purpose: {purpose} "
                f"| Latency: {latency_ms:.2f}ms"
            )
            return
        except Exception as exc:
            if emitted:
                raise RuntimeError("Provider interrupted after output started.") from exc
            logger.warning("%s streaming failed: %s", name, exc)
            next_name = [n for n in order if n != name]
            if not next_name:
                raise
            logger.info("Failing over from %s to %s", name, next_name[0])
