"""Reply-style decorations must never leak into user-visible answers."""
from archipelago.inference.reply_styles import (
    REPLY_STYLES,
    strip_style_artifacts,
    style_instruction,
)


def test_styles_do_not_instruct_printable_cite_first():
    blob = " ".join(REPLY_STYLES)
    assert "/// CITE FIRST ///" not in blob
    assert "THE END." not in blob or "no filler footer" in blob.lower()


def test_strip_style_artifacts_removes_cite_first():
    dirty = (
        "/// CITE FIRST /// Retrieval-Augmented Generation (RAG) combines "
        "retrieval with generation [S1]. THE END."
    )
    clean = strip_style_artifacts(dirty)
    assert "CITE FIRST" not in clean.upper()
    assert "THE END" not in clean.upper()
    assert "Retrieval-Augmented" in clean or "RAG" in clean


def test_strip_style_artifacts_removes_end_markers():
    dirty = "Self-attention scores query keys [S1].\n\n[END]\n[DONE]"
    clean = strip_style_artifacts(dirty)
    assert "[END]" not in clean.upper()
    assert "[DONE]" not in clean.upper()
    assert "Self-attention" in clean


def test_style_instruction_forbids_printing_decorations():
    prompt = style_instruction("What is RAG?")
    assert "Never print style labels" in prompt or "control tokens" in prompt
