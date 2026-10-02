"""Unit tests for LLM Gateway, multi-provider failover, and Query Cache."""
from unittest.mock import MagicMock, patch
import pytest

from archipelago.inference.llm_gateway import (
    gateway_chat,
    gateway_chat_stream,
    gateway_chat_with_tools,
    is_llm_available,
    configure_gateway,
    LLM_UNAVAILABLE_MSG,
    get_active_provider,
)
from archipelago.inference.query_cache import (
    normalize_query,
    get_cached_response,
    set_cached_response,
    clear_cache,
)


def test_query_cache_normalization():
    assert normalize_query("  What IS Attention??? ") == "what is attention"
    assert normalize_query("Tell me about: RAG / LLM!!") == "tell me about rag llm"
    assert normalize_query("") == ""


def test_query_cache_set_and_get():
    clear_cache()
    query = "What is backpropagation?"
    resp = {"answer": "Chain rule application."}
    set_cached_response(query, resp, ttl=60.0)
    
    cached = get_cached_response(query)
    assert cached == resp
    assert get_cached_response("what is backpropagation") == resp
    assert get_cached_response("different query") is None


def test_query_cache_expiry():
    clear_cache()
    set_cached_response("quick query", "temp data", ttl=-1.0)
    assert get_cached_response("quick query") is None


def test_gateway_configuration():
    configure_gateway()
    assert get_active_provider() in ("xkiro", "gemini")


def test_is_llm_available_mock():
    with patch("archipelago.inference.llm_gateway.part01_config._openai_client") as mock_oa:
        mock_oa.chat.completions.create.return_value = MagicMock(choices=[MagicMock()])
        with patch("archipelago.inference.llm_gateway.part01_config.get_active_provider", return_value="xkiro"):
            available = is_llm_available()
            assert isinstance(available, bool)


def test_gateway_chat_xkiro():
    with patch("archipelago.inference.llm_gateway.part03_chat._chat_xkiro", return_value="Test answer from xkiro"):
        with patch("archipelago.inference.llm_gateway.part01_config.get_active_provider", return_value="xkiro"):
            result = gateway_chat([{"role": "user", "content": "hello"}], purpose="chat")
            assert result == "Test answer from xkiro"


def test_gateway_chat_failover():
    with patch("archipelago.inference.llm_gateway.part03_chat._chat_xkiro", return_value=None):
        with patch("archipelago.inference.llm_gateway.part03_chat._chat_gemini", return_value="Fallback answer from Gemini"):
            with patch("archipelago.inference.llm_gateway.part01_config.get_active_provider", return_value="xkiro"):
                result = gateway_chat([{"role": "user", "content": "hello"}], purpose="synthesis")
                assert result == "Fallback answer from Gemini"


def test_gateway_stream_mock():
    with patch("archipelago.inference.llm_gateway.part04_stream._stream_xkiro", return_value=iter(["chunk1 ", "chunk2"])):
        with patch("archipelago.inference.llm_gateway.part01_config.get_active_provider", return_value="xkiro"):
            chunks = list(gateway_chat_stream([{"role": "user", "content": "hi"}], purpose="synthesis"))
            assert chunks == ["chunk1 ", "chunk2"]


def test_xkiro_retries_once_after_short_rate_limit():
    from types import SimpleNamespace
    from archipelago.inference.llm_gateway import _chat_xkiro

    class RateLimitError(Exception):
        status_code = 429
        response = SimpleNamespace(headers={"retry-after": "0.1"})

    client = MagicMock()
    client.chat.completions.create.side_effect = [
        RateLimitError("rate limited"),
        MagicMock(choices=[MagicMock(message=MagicMock(content="ok"))]),
    ]
    with patch("archipelago.inference.llm_gateway.part01_config.configure_gateway"), \
         patch("archipelago.inference.llm_gateway.part01_config._openai_client", client), \
         patch("archipelago.inference.llm_gateway.part03_chat.time.sleep") as sleep:
        assert _chat_xkiro([{"role": "user", "content": "ping"}], max_tokens=5) == "ok"
    assert client.chat.completions.create.call_count == 2
    sleep.assert_called_once_with(0.1)


def test_llm_unavailable_msg_constant():
    assert "library closed" in LLM_UNAVAILABLE_MSG.lower()
