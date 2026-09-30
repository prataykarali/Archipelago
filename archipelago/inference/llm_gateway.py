import os
import re
import time
import threading
import logging
from typing import Generator, List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Thread Safety for configuration
_config_lock = threading.Lock()
_is_configured = False
_openai_client = None

# Constants
LLM_UNAVAILABLE_MSG = (
    "The library closed — the librarian is waking up and will be with you shortly. "
    "The library is currently closed. Please hold while I stoke the intellectual furnaces..."
)

# Provider & API Configuration
XKIRO_BASE_URL = os.environ.get("XKIRO_BASE_URL", "https://api.xkiro.com/v1")
XKIRO_API_KEY = os.environ.get("XKIRO_API_KEY", "").strip()
XKIRO_DEFAULT_MODEL = os.environ.get("XKIRO_MODEL", "qwen/qwen3.8-max:free")

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()

# Default provider: xkiro (primary), fallback to gemini
DEFAULT_PROVIDER = os.environ.get("ARCHIPELAGO_LLM_PROVIDER", "xkiro").lower()

# Model mappings for Gemini
GEMINI_MODELS = {
    "gemini-3.5-flash": "gemini-3.5-flash",
    "gemini-3.5-flash-lite": "gemini-3.5-flash-lite",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.5-pro": "gemini-2.5-pro",
}

# Purpose to Gemini model mapping
GEMINI_PURPOSE_MAP = {
    "routing": "gemini-3.5-flash-lite",
    "identity": "gemini-3.5-flash-lite",
    "chat": "gemini-3.5-flash-lite",
    "synthesis": "gemini-3.5-flash",
    "roadmap": "gemini-3.5-flash",
    "complex": "gemini-3.5-flash",
    "agent": "gemini-3.5-flash",
}

_availability_cache = {"time": 0.0, "status": False, "provider": ""}


def _xkiro_retry_delay(exc: Exception, attempt: int) -> float | None:
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
    delay = retry_after if 0 < retry_after <= 3 else 0.25 * (2 ** attempt)
    return min(3.0, max(0.1, delay))


def get_active_provider() -> str:
    """Return active provider ('xkiro' or 'gemini')."""
    return os.environ.get("ARCHIPELAGO_LLM_PROVIDER", DEFAULT_PROVIDER).lower()


def configure_gateway():
    """Initialize clients with API keys from env. Thread-safe."""
    global _is_configured, _openai_client
    with _config_lock:
        if not _is_configured:
            # 1. Initialize OpenAI client for xkiro
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

            # 2. Initialize Gemini GenAI client
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
    if now - _availability_cache["time"] < 5.0:
        return _availability_cache["status"]

    configure_gateway()
    provider = get_active_provider()
    status = False

    # Try active provider
    if provider == "xkiro" and _openai_client is not None:
        try:
            res = _openai_client.chat.completions.create(
                model=XKIRO_DEFAULT_MODEL,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=5,
                timeout=8,
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


def sanitize_for_external_llm(text: str) -> str:
    """Strictly redact any links, URLs, and OKF references before sending to external LLMs (e.g. xkiro)."""
    if not text:
        return ""
    # Strip markdown links [label](url) -> label
    clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", str(text))
    # Strip full URLs
    clean = re.sub(r"https?://\S+", "", clean)
    clean = re.sub(r"ftp://\S+", "", clean)
    # Strip internal routes and file paths
    clean = re.sub(r"/(?:api/page-view|read|open|papers|pdfs)\S*", "", clean)
    clean = re.sub(r"[\w./-]+\.(?:pdf|json|db|ods)", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"archipelago-books-\S+", "", clean, flags=re.IGNORECASE)
    # Strip OKF and database internals
    clean = re.sub(r"\bOKF\b|\bOKFGraph\b|\bokf_graph\b|\bkuzu\b|\bcypher\b|subscriptionId", "", clean, flags=re.IGNORECASE)
    # Strip UUIDs
    clean = re.sub(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", "", clean, flags=re.IGNORECASE)
    # Collapse excess whitespace
    clean = re.sub(r"[ \t]+", " ", clean)
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    return clean.strip()


def _convert_messages_for_gemini(messages: List[Dict]) -> Tuple[Optional[str], List[Dict]]:
    """Convert standard messages to Gemini format with leak sanitization."""
    system_instruction = None
    formatted_history = []

    for msg in messages:
        role = msg.get("role")
        raw_content = str(msg.get("content", ""))
        content = sanitize_for_external_llm(raw_content)

        if role == "system":
            system_instruction = content
        elif role == "user":
            formatted_history.append({"role": "user", "parts": [content]})
        elif role in ("assistant", "model"):
            formatted_history.append({"role": "model", "parts": [content]})

    return system_instruction, formatted_history


def _clean_messages_for_openai(messages: List[Dict]) -> List[Dict]:
    """Ensure messages have valid roles ('system', 'user', 'assistant') and sanitized string content."""
    clean = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "model":
            role = "assistant"
        raw_content = str(msg.get("content", ""))
        sanitized = sanitize_for_external_llm(raw_content)
        clean.append({"role": role, "content": sanitized})
    return clean


# ── Core Synchronous Chat ─────────────────────────────────────────────────────

def _chat_xkiro(
    messages: List[Dict],
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    timeout: int = 30,
) -> Optional[str]:
    """Execute chat via xkiro OpenAI API."""
    configure_gateway()
    if _openai_client is None:
        return None
    model_name = model or XKIRO_DEFAULT_MODEL
    cleaned_msgs = _clean_messages_for_openai(messages)
    for attempt in range(2):
        try:
            response = _openai_client.chat.completions.create(
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
            delay = _xkiro_retry_delay(exc, attempt)
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
    max_tokens: int = 2048,
    timeout: int = 30,
) -> Optional[str]:
    """Execute chat via Gemini API."""
    configure_gateway()
    try:
        import google.generativeai as genai
        from google.generativeai.types import RequestOptions

        selected_model = model or GEMINI_PURPOSE_MAP.get(purpose, "gemini-2.0-flash")
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


def gateway_chat(
    messages: List[Dict],
    purpose: str = "general",
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    timeout: int = 30,
) -> Optional[str]:
    """Synchronous chat across providers with automatic failover."""
    configure_gateway()
    provider = get_active_provider()
    start_time = time.time()

    text = None
    if provider == "xkiro":
        text = _chat_xkiro(messages, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
        if text is None:
            logger.info("Failing over from xkiro to Gemini for purpose: %s", purpose)
            text = _chat_gemini(messages, purpose=purpose, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
    else:
        text = _chat_gemini(messages, purpose=purpose, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout)
        if text is None:
            logger.info("Failing over from Gemini to xkiro for purpose: %s", purpose)
            text = _chat_xkiro(messages, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout)

    latency_ms = (time.time() - start_time) * 1000
    if text is not None:
        print(f"gateway_chat | Provider: {provider} | Purpose: {purpose} | Latency: {latency_ms:.2f}ms")
    return text


# ── Streaming Chat ────────────────────────────────────────────────────────────

def _stream_xkiro(
    messages: List[Dict],
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    timeout: int = 30,
) -> Generator[str, None, None]:
    """Stream text tokens via xkiro OpenAI API."""
    configure_gateway()
    if _openai_client is None:
        raise RuntimeError("OpenAI client for xkiro not initialized")
    model_name = model or XKIRO_DEFAULT_MODEL
    cleaned_msgs = _clean_messages_for_openai(messages)
    for attempt in range(2):
        try:
            response = _openai_client.chat.completions.create(
                model=model_name,
                messages=cleaned_msgs,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
                stream=True,
            )
            break
        except Exception as exc:
            delay = _xkiro_retry_delay(exc, attempt)
            if delay is None:
                raise
            logger.info("xkiro stream was rate limited or unavailable; retrying once after %.2fs", delay)
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
    max_tokens: int = 2048,
    timeout: int = 30,
) -> Generator[str, None, None]:
    """Stream text tokens via Gemini API."""
    configure_gateway()
    import google.generativeai as genai
    from google.generativeai.types import RequestOptions

    selected_model = model or GEMINI_PURPOSE_MAP.get(purpose, "gemini-2.0-flash")
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


def gateway_chat_stream(
    messages: List[Dict],
    purpose: str = "synthesis",
    model: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    timeout: int = 30,
) -> Generator[str, None, None]:
    """Streaming chat across providers with automatic failover."""
    configure_gateway()
    provider = get_active_provider()
    start_time = time.time()

    if provider == "xkiro":
        try:
            tokens_emitted = 0
            for chunk in _stream_xkiro(messages, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout):
                tokens_emitted += 1
                yield chunk
            latency_ms = (time.time() - start_time) * 1000
            print(f"gateway_chat_stream | Provider: xkiro | Purpose: {purpose} | Latency: {latency_ms:.2f}ms")
            return
        except Exception as exc:
            logger.warning("xkiro streaming failed: %s; failing over to Gemini", exc)
            for chunk in _stream_gemini(messages, purpose=purpose, temperature=temperature, max_tokens=max_tokens, timeout=timeout):
                yield chunk
            return
    else:
        try:
            for chunk in _stream_gemini(messages, purpose=purpose, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout):
                yield chunk
            latency_ms = (time.time() - start_time) * 1000
            print(f"gateway_chat_stream | Provider: gemini | Purpose: {purpose} | Latency: {latency_ms:.2f}ms")
            return
        except Exception as exc:
            logger.warning("Gemini streaming failed: %s; failing over to xkiro", exc)
            for chunk in _stream_xkiro(messages, model=model, temperature=temperature, max_tokens=max_tokens, timeout=timeout):
                yield chunk
            return


# ── Agent Function Calling (Tools) ───────────────────────────────────────────

def gateway_chat_with_tools(
    messages: List[Dict],
    tools: List[Dict],
    purpose: str = "agent",
    model: Optional[str] = None,
) -> Tuple[str, List[Dict]]:
    """Execute chat with function calling. Returns (text, tool_calls)."""
    configure_gateway()
    provider = get_active_provider()
    start_time = time.time()

    cleaned_msgs = _clean_messages_for_openai(messages)

    if provider == "xkiro" and _openai_client is not None:
        try:
            oa_tools = []
            for t in tools:
                if isinstance(t, dict) and t.get("type") == "function":
                    oa_tools.append(t)
                elif isinstance(t, dict) and "function" in t:
                    oa_tools.append({"type": "function", "function": t["function"]})
                else:
                    oa_tools.append(t)

            response = _openai_client.chat.completions.create(
                model=model or XKIRO_DEFAULT_MODEL,
                messages=cleaned_msgs,
                tools=oa_tools if oa_tools else None,
                temperature=0.0,
                timeout=30,
            )
            msg = response.choices[0].message
            text = msg.content or ""
            parsed_tools = []
            if msg.tool_calls:
                import json
                for tc in msg.tool_calls:
                    fn_name = tc.function.name
                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except Exception:
                        args = {"query": tc.function.arguments}
                    parsed_tools.append({"name": fn_name, "args": args})

            latency_ms = (time.time() - start_time) * 1000
            print(f"gateway_chat_with_tools | Provider: xkiro | Latency: {latency_ms:.2f}ms")
            return text, parsed_tools
        except Exception as exc:
            logger.warning("xkiro tools call failed: %s; trying Gemini fallback", exc)

    # Gemini fallback
    try:
        import google.generativeai as genai
        selected_model = model or GEMINI_PURPOSE_MAP.get(purpose, "gemini-2.5-pro")
        system_instruction, formatted_history = _convert_messages_for_gemini(messages)

        kwargs = {"model_name": selected_model}
        if system_instruction:
            kwargs["system_instruction"] = system_instruction
        gemini_model = genai.GenerativeModel(**kwargs)

        res = gemini_model.generate_content(formatted_history)
        text_content = ""
        tool_calls = []
        if res.parts:
            for part in res.parts:
                if hasattr(part, "text") and part.text:
                    text_content += part.text
                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    tool_calls.append({"name": fc.name, "args": dict(fc.args)})

        return text_content, tool_calls
    except Exception as exc:
        logger.error("Tool execution failed on all providers: %s", exc)
        return "", []
