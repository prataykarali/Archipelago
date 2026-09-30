"""Streaming synthesis with Ollama SLM + grounded first paint.

Ollama is the sole generative provider. Tests mock the Ollama client
so unit runs never hit the network.
"""
from __future__ import annotations

import pytest
import archipelago.inference.synthesis as synthesis

pytestmark = pytest.mark.unit


def test_stream_system_prompt_is_ollama_based():
    """System prompt is present in the Ollama streaming path."""
    assert callable(synthesis.synthesize_with_ollama_streaming)
    assert callable(synthesis.is_readable_synthesis)
    assert callable(synthesis.enforce_sterile_prose)


def test_malformed_math_is_rejected():
    """Known SLM artifacts are detected as unreadable."""
    malformed = (
        "y'_i,j,k,l,m,n,p,q,r,s,t,u,v,w,x,y,z = begincases "
        "W_ij · x_i endcases"
    )
    assert not synthesis.is_readable_synthesis(malformed)
    assert synthesis.is_readable_synthesis(
        "LoRA freezes base weights and learns a low-rank update."
    )


def test_sterile_prose_strips_emojis_and_slang():
    """Persona-hijack post-filter removes emojis and gen-z slang."""
    dirty = "LoRA \U0001f525\U0001f525 freezes weights no cap fr fr \U0001f4af"
    clean = synthesis.enforce_sterile_prose(dirty)
    assert "\U0001f525" not in clean
    assert "no cap" not in clean
    assert "fr fr" not in clean
    assert "LoRA" in clean


def test_scrub_slm_artifacts_preserves_surrounding_prose():
    """Artifact scrubber removes known 0.8B errors without discarding clean text."""
    dirty = (
        "LoRA freezes base weights.\n"
        "begincases W_ij \u00b7 x_i endcases\n"
        "This enables efficient adaptation."
    )
    clean = synthesis._scrub_slm_artifacts(dirty)
    assert "LoRA freezes base weights" in clean
    assert "efficient adaptation" in clean
    assert "begincases" not in clean


def test_ollama_unavailable_raises_runtime_error(monkeypatch):
    """When Ollama is unreachable, synthesize_with_ollama_streaming raises."""
    import archipelago.inference.synthesis as synth

    def _fail(*_a, **_k):
        raise RuntimeError("Ollama unavailable: connection refused")

    monkeypatch.setattr(synth, "gateway_chat_stream", _fail)
    with pytest.raises(RuntimeError, match="LLM unavailable"):
        synth.synthesize_with_ollama_streaming(
            "LoRA notes [S1]",
            fallback_text="LoRA freezes base weights.",
        )


def test_empty_model_output_raises_runtime_error(monkeypatch):
    """Empty Ollama output raises RuntimeError (caller handles fallback)."""
    import archipelago.inference.synthesis as synth

    def _empty_stream(*_a, **_k):
        return iter([""])

    monkeypatch.setattr(synth, "gateway_chat_stream", _empty_stream)
    with pytest.raises(RuntimeError, match="Empty response"):
        synth.synthesize_with_ollama_streaming("LoRA notes [S1]")


def test_citation_id_pattern_matches_colon_form():
    """CITATION_ID_PATTERN matches [S1: form used in citation payloads."""
    ids1 = synthesis.st.CITATION_ID_PATTERN.findall("[S1: LoRA | paper.pdf, p.2]")
    assert ids1 == ["S1"]
    ids2 = synthesis.st.CITATION_ID_PATTERN.findall("[S9: QLoRA | paper.pdf, p.5]")
    assert ids2 == ["S9"]


def test_latex_stripper_converts_to_readable_text():
    """LaTeX expressions are converted to readable plain-text math."""
    assert "$$" not in synthesis._strip_latex("$$\\Delta W = BA$$")
    result = synthesis._strip_latex("$\\Delta W = BA$")
    assert "W" in result and "BA" in result
