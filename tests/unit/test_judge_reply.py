"""Unit coverage for SoFerence judge-ready reply architecture."""
from __future__ import annotations

import json

import pytest

from archipelago.inference.judge_reply import (
    JUDGE_MAX_OUTPUT_TOKENS,
    JUDGE_SYSTEM_PROMPT,
    JUDGE_TEMPERATURE,
    build_judge_user_content,
    has_judge_section_headings,
)
from archipelago.inference.sanitizer import (
    sanitize_archipelago_output,
    sanitize_stream_final,
)
import archipelago.inference.synthesis as synthesis


pytestmark = pytest.mark.unit


def test_judge_system_prompt_has_four_tiers():
    prompt = JUDGE_SYSTEM_PROMPT.casefold()
    assert "overview" in prompt
    assert "mathematical formulation" in prompt
    assert "learning path" in prompt
    assert "evidence" in prompt
    assert "pilot" in prompt
    assert "dbms" in prompt
    assert "never invent" in prompt


def test_stream_system_prompt_is_judge_architecture():
    assert synthesis.stream_system_prompt() is synthesis._STREAM_SYSTEM_PROMPT
    assert synthesis._STREAM_SYSTEM_PROMPT is JUDGE_SYSTEM_PROMPT
    assert "Learning Path" in synthesis.stream_system_prompt()


def test_build_judge_user_content_is_json_and_fixed_presentation():
    raw = build_judge_user_content(
        context="LoRA freezes W0 [S1]",
        user_query="What is LoRA?",
        allowed_evidence_ids={"S1", "S2"},
    )
    assert raw.startswith("UNTRUSTED_DATA_JSON:\n")
    payload = json.loads(raw.split("\n", 1)[1])
    assert payload["user_query"] == "What is LoRA?"
    assert payload["allowed_evidence_ids"] == ["S1", "S2"]
    assert "8-tier" in payload["presentation"] or "SoFerence" in payload["presentation"]
    assert payload["reply_architecture"][0] == "Overview"
    assert "LAYOUT:" not in raw


def test_has_judge_section_headings():
    good = (
        "### Overview\nLoRA freezes base weights [S1].\n\n"
        "### Mathematical Formulation\n$$\\Delta W = BA$$\n\n"
        "### Learning Path\n🧠 SVD → LoRA\n\n"
        "### Evidence\nHu2021_LoRA.pdf — Pages 1, 3\n"
    )
    assert has_judge_section_headings(good)
    assert not has_judge_section_headings("Just a short paragraph about LoRA.")


def test_sanitize_strips_orphan_query_params_and_dedupes():
    dirty = (
        "LoRA adapts models [S1].\n\n"
        "c_id=papers%2FHu2021_LoRA.pdf&page=1&highlight=LoRA\n\n"
        "LoRA adapts models [S1].\n\n"
        "### Technical or Mathematical Mechanism\n"
        "Update is $\\Delta W = BA$."
    )
    clean = sanitize_stream_final(dirty)
    assert "c_id=" not in clean
    assert "highlight=" not in clean
    assert clean.count("LoRA adapts models") == 1
    assert "Technical or Mathematical Mechanism" in clean
    # Aggressive model sanitizer also strips orphans without flattening tiers.
    aggressive = sanitize_archipelago_output(dirty)
    assert "c_id=" not in aggressive
    assert "Technical or Mathematical Mechanism" in aggressive


def test_malformed_math_synthesis_is_rejected() -> None:
    malformed = (
        "y'_i,j,k,l,m,n,p,q,r,s,t,u,v,w,x,y,z = begincases "
        "W_ij · x_i endcases"
    )

    assert not synthesis.is_readable_synthesis(malformed)
    assert synthesis.is_readable_synthesis("LoRA freezes base weights and learns a low-rank update.")
