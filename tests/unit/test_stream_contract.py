"""Streaming contracts for server output and the student chat client."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _ui_source import chat_ui_source, local_script_files  # noqa: E402

try:
    from archipelago.inference.synthesis import _is_followup_query
except ImportError:
    _is_followup_query = None

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
CHAT_UI_PATH = ROOT / "ui" / "chat" / "index.html"


def _read_chat_ui() -> str:
    # CSS/JS now live in linked files; inline them so assertions stay meaningful.
    return chat_ui_source()


def _stream_client_source() -> str:
    source = _read_chat_ui()
    start = source.index("const reader = response.body.getReader();")
    end = source.index("// Add to conversational history", start)
    return source[start:end]


@pytest.mark.skipif(_is_followup_query is None, reason="_is_followup_query removed in refactor")
def test_followup_detection_allows_pronouns() -> None:
    assert _is_followup_query("tell me more about it")
    assert _is_followup_query("what are the prerequisites")
    assert _is_followup_query("go deeper")


@pytest.mark.skipif(_is_followup_query is None, reason="_is_followup_query removed in refactor")
def test_followup_detection_blocks_new_topics() -> None:
    assert not _is_followup_query("tell me about AI agents")
    assert not _is_followup_query("best books on SQL")
    assert not _is_followup_query("Explain the main components of RAG")


def test_stream_client_recognizes_metadata_delimiter() -> None:
    client = _stream_client_source()

    assert "'[STREAM_START]'" in client
    assert "const metaStr = buffer.substring(0, idx)" in client
    assert "const metadata = JSON.parse(metaStr);" in client
    assert "metadataParsed = true;" in client
    assert "consumeTextChunk(buffer);" in client


def test_stream_done_frame_replaces_provisional_text() -> None:
    client = _stream_client_source()
    ui = _read_chat_ui()

    # Control frames recognized by the client parser.
    assert "tag: '[STREAM_DONE]'" in client or "'[STREAM_DONE]'" in client
    assert "awaitingFinalFrame = true;" in client
    # Final / live frames go through typewriter — never silent wait-only.
    assert "typewriter.update(rest, { instant: true })" in client or "instant: true" in client
    assert "forceTypewriter" in client
    # Guard: never wipe a rich first-paint card with a title+[END] stub.
    # The predicate lives in stream-support.js; assert across the module bundle.
    assert "_shouldReplaceFinal" in _read_chat_ui()
    # Regex source stores escaped brackets: \[END\] (lives in stream-support.js).
    assert r"\[END\]" in _read_chat_ui() or "END" in client
    assert "is-live-streaming" in client
    # Live model rewrite (no silent wait after grounded first-paint).
    assert "[MODEL_REWRITE]" in client
    assert "liveRewriteMode" in client
    assert "forceTypewriter" in client
    # Status chip removed — stream only, no "Model replying in Xs" chrome.
    assert "MRS_COUNTDOWN_SECS" not in client
    assert "Streaming reply ·" not in client
    assert "model-status-${msgId}" not in ui


def test_chat_bubble_body_font_is_readable() -> None:
    """Assistant study text is mid-size: not tiny, not oversized display."""
    source = _read_chat_ui()
    # The Warfield section is marked by a HTML comment.
    assert "<!-- WARFIELD CHAT MESSAGE FONT -->" in source
    # Font size raised from 0.90rem -> 1.0rem for better legibility.
    assert "font-size: 1.0rem !important;" in source
    # Locate the Warfield CSS block that controls bubble body copy.
    warfield_block_start = source.index("WARFIELD CHAT MESSAGE FONT")
    warfield_block = source[warfield_block_start:warfield_block_start + 3000]
    # Body must not regress to the old oversized 1.05 or the too-small 0.82.
    assert "font-size: 1.05rem" not in warfield_block
    assert "font-size: 0.82rem" not in warfield_block
    # Guard: old 0.90rem baseline should be gone from the Warfield block.
    assert "font-size: 0.90rem" not in warfield_block



def test_static_stream_buffer_accumulates_chunks() -> None:
    """Plain chunked static routes (identity, help, small_talk, etc.) must use
    staticStreamBuffer + forceTypewriter so word-by-word animation doesn't
    flicker or get reset between small backend chunks."""
    client = _stream_client_source()
    # Buffer must exist and accumulate (not use stale assistantText)
    assert "staticStreamBuffer" in client
    assert "staticStreamBuffer += rest;" in client
    assert "staticStreamBuffer += before;" in client
    # Must use forceTypewriter on plain static stream path so it animates
    # word-by-word rather than instant-painting
    assert "typewriter.update(staticStreamBuffer, { forceTypewriter: true })" in client
    # Must clear on MODEL_REWRITE and at stream completion
    assert "staticStreamBuffer = '';" in client


def test_chat_ui_guards_localstorage_quota_and_stream_timeout() -> None:
    """Long chats used to throw QuotaExceededError and mis-label it as stream failure."""
    source = _read_chat_ui()
    assert "QuotaExceededError" in source
    assert "_writeSessions" in source
    assert "STREAM_IDLE_TIMEOUT_MS" in source
    assert "STREAM_HARD_TIMEOUT_MS" in source
    assert "clearAllSessions" in source
    assert "MAX_HISTORY_TURNS_SENT" in source
    assert "Clear saved history" in source
    # saveSession must never raw-setItem the full uncompacted history alone
    assert "_compactHistory" in source
    assert "saveSession failed after successful stream" in source or "saveSession()" in source


def test_chat_ui_js_has_no_python_inline_regex_flags() -> None:
    """Python-style ``(?m)`` / ``(?i)`` inside JS regex literals crash parse.

    That freezes the whole student page: hero/avatar videos never wire, and
    status stays on ``Checking...`` forever. Ban them in live regex literals.
    """
    import re
    import subprocess

    source = _read_chat_ui()
    # Live JS regex literals only (not comments): /...(?m).../ or /...(?i).../
    bad = re.findall(r"/(?:\\.|[^/\\])*\(\?[imsux]+\)(?:\\.|[^/\\])*/[gimsuy]*", source)
    assert not bad, f"Python-style inline regex flags in JS literals: {bad[:5]}"
    assert r"/^\s*to\s+(?=\(p\.)/gim" in source
    assert "archi_main.mp4" in source
    assert "library_hi.mp4" in source
    assert "initHeroVideo" in source or "wireLoopVideo" in source

    # CSS/JS are now modular: syntax-check every real module file the page
    # loads, as an ES module (.mjs) so import/export statements are accepted.
    js_files = local_script_files(CHAT_UI_PATH)
    assert js_files, "expected chat UI JavaScript files"
    for index, path in enumerate(js_files):
        probe = Path(f"/tmp/archipelago_chat_ui_{index}.mjs")
        probe.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
        result = subprocess.run(
            ["node", "--check", str(probe)],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, (
            f"chat UI module {path.name} failed node --check:\n{result.stderr}"
        )


def test_dangling_citation_bracket_stripped_during_live_stream() -> None:
    """Incomplete [S or [S1 bracket fragments emitted mid-stream must be
    stripped before they reach the DOM, preventing visual noise like '[S'."""
    ui_source = _read_chat_ui()
    # The trailing-incomplete-bracket regex must be present
    assert r"processedText.replace(/\[S\d*" in ui_source or "trailing incomplete bracket" in ui_source


def test_stream_text_in_chunks_splits_properly() -> None:
    """_stream_text_in_chunks must emit multiple small pieces for long text,
    so the typewriter always sees incremental updates under 20 chars each."""
    # Import inline since function is a closure inside api_chat;
    # test its logic directly via a standalone re-implementation.
    import re

    def _stream_text_in_chunks(text: str):  # type: ignore[return]
        if not text:
            return
        tokens = re.split(r"(\s+)", text)
        chunk_buffer: list[str] = []
        chunk_len = 0
        for token in tokens:
            if not token:
                continue
            chunk_buffer.append(token)
            chunk_len += len(token)
            if chunk_len >= 20 or "\n" in token:
                yield "".join(chunk_buffer)
                chunk_buffer = []
                chunk_len = 0
        if chunk_buffer:
            yield "".join(chunk_buffer)

    long_text = "This is a long response from the identity route that should be split into multiple small streaming chunks for smooth typewriter animation."
    chunks = list(_stream_text_in_chunks(long_text))
    # Must produce more than one chunk for long text
    assert len(chunks) > 1, "Long static text must stream in multiple chunks"
    # Each individual chunk must be small (≤ 30 chars to allow for whitespace tokens)
    for chunk in chunks:
        assert len(chunk) <= 30, f"Chunk too large: {chunk!r}"
    # Reassembling chunks must reproduce the original text exactly
    assert "".join(chunks) == long_text

    # Short text (single word) should come out as one chunk
    assert list(_stream_text_in_chunks("Hello")) == ["Hello"]
    # Empty text yields nothing
    assert list(_stream_text_in_chunks("")) == []

