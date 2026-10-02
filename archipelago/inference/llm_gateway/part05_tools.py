"""Agent function calling (tools) with xkiro primary and Gemini fallback."""

from __future__ import annotations

import json
import logging
import time
from typing import Dict, List, Optional, Tuple

from archipelago.inference.llm_gateway import part01_config as config
from archipelago.inference.llm_gateway.part01_config import (
    GEMINI_PURPOSE_MAP,
    GEMINI_TOOLS_FALLBACK_MODEL,
    XKIRO_DEFAULT_MODEL,
)
from archipelago.inference.llm_gateway.part02_sanitize import (
    _clean_messages_for_openai,
    _convert_messages_for_gemini,
)

logger = logging.getLogger(__name__)

TOOLS_TIMEOUT_SECONDS = 30
TOOLS_TEMPERATURE = 0.0


def _normalize_openai_tools(tools: List[Dict]) -> List[Dict]:
    """Accept both chat-completions tool specs and bare function specs."""
    oa_tools: List[Dict] = []
    for t in tools:
        if isinstance(t, dict) and t.get("type") == "function":
            oa_tools.append(t)
        elif isinstance(t, dict) and "function" in t:
            oa_tools.append({"type": "function", "function": t["function"]})
        else:
            oa_tools.append(t)
    return oa_tools


def gateway_chat_with_tools(
    messages: List[Dict],
    tools: List[Dict],
    purpose: str = "agent",
    model: Optional[str] = None,
) -> Tuple[str, List[Dict]]:
    """Execute chat with function calling. Returns (text, tool_calls)."""
    config.configure_gateway()
    provider = config.get_active_provider()
    start_time = time.time()

    cleaned_msgs = _clean_messages_for_openai(messages)

    if provider == "xkiro" and config._openai_client is not None:
        try:
            oa_tools = _normalize_openai_tools(tools)
            response = config._openai_client.chat.completions.create(
                model=model or XKIRO_DEFAULT_MODEL,
                messages=cleaned_msgs,
                tools=oa_tools if oa_tools else None,
                temperature=TOOLS_TEMPERATURE,
                timeout=TOOLS_TIMEOUT_SECONDS,
            )
            msg = response.choices[0].message
            text = msg.content or ""
            parsed_tools = []
            if msg.tool_calls:
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

        selected_model = model or GEMINI_PURPOSE_MAP.get(purpose, GEMINI_TOOLS_FALLBACK_MODEL)
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
