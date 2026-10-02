"""Regression tests for the host_inference LLM provider fallback chain.

The chain is xkiro -> nvidia.  OpenRouter was removed on purpose, so these
tests pin the ordering, the env-var names, and the ``ARCHIPELAGO_LLM_PROVIDER``
pin so a future edit cannot silently reintroduce a third vendor or reorder the
chain behind the operator's back.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "host_inference") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "host_inference"))

from engine import llm  # noqa: E402

pytestmark = pytest.mark.unit

PROVIDER_ENV_VARS = (
    "XKIRO_API_KEY",
    "XKIRO_BASE_URL",
    "XKIRO_MODEL",
    "NVIDIA_API_KEY",
    "NVIDIA_BASE_URL",
    "NVIDIA_MODEL",
    "OPENROUTER_API_KEY",
    "OPENROUTER_BASE_URL",
    "OPENROUTER_MODEL",
    "ARCHIPELAGO_LLM_PROVIDER",
)


@pytest.fixture(autouse=True)
def _clean_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from a provider-free environment."""
    for name in PROVIDER_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def test_chain_order_is_xkiro_then_nvidia() -> None:
    assert llm.PROVIDER_ORDER == ("xkiro", "nvidia")


def test_openrouter_is_not_a_provider() -> None:
    assert "openrouter" not in llm.PROVIDER_ORDER
    for table in (
        llm.PROVIDER_KEY_ENV,
        llm.PROVIDER_BASE_URL_ENV,
        llm.PROVIDER_MODEL_ENV,
        llm.PROVIDER_BASE_URL,
        llm.PROVIDER_MODEL,
    ):
        assert "openrouter" not in table


def test_nvidia_defaults() -> None:
    assert llm.NVIDIA_BASE_URL == "https://integrate.api.nvidia.com/v1"
    assert llm.NVIDIA_DEFAULT_MODEL == "deepseek-ai/deepseek-v4.1-flash"


def test_no_key_yields_no_config() -> None:
    assert llm.provider_config() is None


def test_xkiro_wins_when_both_keys_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XKIRO_API_KEY", "xkiro-key")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvidia-key")
    config = llm.provider_config()
    assert config is not None
    assert config["provider"] == "xkiro"
    assert config["key"] == "xkiro-key"


def test_nvidia_used_as_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvidia-key")
    config = llm.provider_config()
    assert config is not None
    assert config["provider"] == "nvidia"
    assert config["base_url"] == llm.NVIDIA_BASE_URL
    assert config["model"] == llm.NVIDIA_DEFAULT_MODEL


@pytest.mark.parametrize("name", ["XKIRO_API_KEY", "NVIDIA_API_KEY"])
def test_blank_key_counts_as_unset(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    monkeypatch.setenv(name, "   ")
    assert llm.provider_config() is None


def test_pinned_provider_wins_over_order(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XKIRO_API_KEY", "xkiro-key")
    monkeypatch.setenv("NVIDIA_API_KEY", "nvidia-key")
    monkeypatch.setenv("ARCHIPELAGO_LLM_PROVIDER", "nvidia")
    config = llm.provider_config()
    assert config is not None
    assert config["provider"] == "nvidia"


def test_pin_without_matching_key_yields_no_config(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pinned provider with no key must degrade, not silently use another."""
    monkeypatch.setenv("NVIDIA_API_KEY", "nvidia-key")
    monkeypatch.setenv("ARCHIPELAGO_LLM_PROVIDER", "xkiro")
    assert llm.provider_config() is None


def test_unknown_pin_disables_polish(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XKIRO_API_KEY", "xkiro-key")
    monkeypatch.setenv("ARCHIPELAGO_LLM_PROVIDER", "gemini")
    assert llm.provider_config() is None


@pytest.mark.parametrize(
    ("env_var", "expected"),
    [("NVIDIA_BASE_URL", "base_url"), ("NVIDIA_MODEL", "model")],
)
def test_nvidia_overrides(monkeypatch: pytest.MonkeyPatch, env_var: str, expected: str) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvidia-key")
    monkeypatch.setenv(
        env_var, "https://override.example/v1" if expected == "base_url" else "override-model"
    )
    config = llm.provider_config()
    assert config is not None
    assert config[expected] == os.environ[env_var]


def test_maybe_polish_is_a_noop_without_provider() -> None:
    text, meta = llm.maybe_polish("Grounded draft.", "GRAPH_SYNTHESIS")
    assert text == "Grounded draft."
    assert meta is None


def test_maybe_polish_skips_routes_without_prose_needs() -> None:
    text, meta = llm.maybe_polish("Grounded draft.", "GUARDRAIL_INTERCEPT")
    assert text == "Grounded draft."
    assert meta is None
