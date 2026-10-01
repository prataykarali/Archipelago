"""LLM provider integration: XKIRO (preferred) with OpenRouter fallback.

One concern: turning a grounded draft into fluent prose.  The grounded draft is
always the source of truth — if the provider is unavailable or drops the page
citation, the draft is returned unchanged.  XKIRO stays the preferred provider.
"""
from __future__ import annotations

import json
import os
import time
from collections.abc import Iterator

import requests

REPLY_SYSTEM_PROMPT = (
    "You are Archipelago's academic librarian and tutor. Answer concisely in 1–3 sentences, "
    "normally under 90 words, based only on the provided technical notes. State the direct answer "
    "and one useful implication. Expand only when the user asks for detail. "
    "Do not include raw URLs, web links, "
    "file paths, or internal database names. Do not mention OKF or internal graph structures."
)
REPLY_MAX_TOKENS = 220
REPLY_TEMPERATURE = 0.2

# Routes whose grounded draft benefits from academic phrasing.
POLISH_ROUTES = frozenset({"GRAPH_SYNTHESIS", "RELATION", "CROSS_DOMAIN", "BOOK_PAGE", "DEMO"})

XKIRO_DEFAULT_BASE_URL = "https://api.xkiro.com/v1"
XKIRO_DEFAULT_MODEL = "qwen/qwen3.8-max:free"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_DEFAULT_MODEL = "openai/gpt-4o-mini"

STREAM_TIMEOUT_SECONDS = 30
COMPLETE_TIMEOUT_SECONDS = 40
# Gentle spacing so a burst of polish calls does not trip provider rate limits.
COMPLETE_SPACING_SECONDS = 1.2


def provider_config() -> dict | None:
    """Return the preferred provider config, or ``None`` when no key is set.

    XKIRO wins whenever ``XKIRO_API_KEY`` is present; OpenRouter is the fallback.
    """
    xkey = os.environ.get("XKIRO_API_KEY", "").strip()
    if xkey:
        return {
            "base_url": os.environ.get("XKIRO_BASE_URL", XKIRO_DEFAULT_BASE_URL),
            "key": xkey,
            "model": os.environ.get("XKIRO_MODEL", XKIRO_DEFAULT_MODEL),
            "provider": "xkiro",
        }
    okey = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if okey:
        return {
            "base_url": OPENROUTER_BASE_URL,
            "key": okey,
            "model": os.environ.get("OPENROUTER_MODEL", OPENROUTER_DEFAULT_MODEL),
            "provider": "openrouter",
        }
    return None


def complete(config: dict, text: str) -> str:
    """Blocking single completion. Raises on transport or HTTP errors."""
    time.sleep(COMPLETE_SPACING_SECONDS)
    response = requests.post(
        f"{config['base_url'].rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {config['key']}", "Content-Type": "application/json"},
        json={
            "model": config["model"],
            "temperature": REPLY_TEMPERATURE,
            "max_tokens": REPLY_MAX_TOKENS,
            "messages": [
                {"role": "system", "content": REPLY_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
        },
        timeout=COMPLETE_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def stream_completion(config: dict, text: str) -> Iterator[str]:
    """Yield content deltas from the provider's SSE stream.

    Yields nothing at all when the provider errors, so the caller can detect a
    zero-token stream and fall back to the grounded draft.
    """
    try:
        resp = requests.post(
            f"{config['base_url'].rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {config['key']}", "Content-Type": "application/json"},
            json={
                "model": config["model"],
                "temperature": REPLY_TEMPERATURE,
                "max_tokens": REPLY_MAX_TOKENS,
                "stream": True,
                "messages": [
                    {"role": "system", "content": REPLY_SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
            },
            stream=True,
            timeout=STREAM_TIMEOUT_SECONDS,
        )
        if resp.status_code != 200:
            resp.close()
            return
        for line in resp.iter_lines():
            if not line:
                continue
            line_str = line.decode("utf-8", errors="replace")
            if not line_str.startswith("data: "):
                continue
            data_part = line_str[len("data: "):].strip()
            if data_part == "[DONE]":
                break
            try:
                chunk = json.loads(data_part)
                delta = chunk["choices"][0]["delta"].get("content", "")
            except Exception:
                continue
            if delta:
                yield delta
        resp.close()
    except Exception:
        return


def maybe_polish(text: str, route: str, link_lines: list[str] | None = None) -> tuple[str, dict | None]:
    """Ask the provider to phrase the grounded draft.

    Keeps the draft if the model is unavailable or drops the page citation.
    """
    if route not in POLISH_ROUTES:
        return text, None
    config = provider_config()
    if config is None:
        return text, None
    if link_lines is None:
        from .constants import CITATION_LINE_PREFIXES
        link_lines = [line for line in text.splitlines() if line.startswith(CITATION_LINE_PREFIXES)]
    try:
        polished = complete(config, text)
    except Exception:
        return text, None
    if not polished:
        return text, None
    if link_lines:
        polished = polished.rstrip() + "\n\n" + "\n".join(link_lines)
    return polished, {"provider": config["provider"], "model": config["model"]}
