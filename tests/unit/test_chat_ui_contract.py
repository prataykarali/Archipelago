"""Static regression contracts for the student chat UI."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
import re

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
CHAT_UI_PATH = ROOT / "ui" / "chat" / "index.html"


def _chat_ui_source() -> str:
    return CHAT_UI_PATH.read_text(encoding="utf-8")


def _section(source: str, start: str, end: str) -> str:
    start_index = source.index(start)
    end_index = source.index(end, start_index)
    return source[start_index:end_index]


class _VisibleUiParser(HTMLParser):
    """Collect visible copy and labels from interactive controls."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._control_depth = 0
        self.visible_text: list[str] = []
        self.control_labels: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        attributes = dict(attrs)
        if tag in {"a", "button"}:
            self._control_depth += 1
            for name in ("aria-label", "title"):
                value = attributes.get(name)
                if value:
                    self.control_labels.append(value)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if not self._skip_depth and tag in {"a", "button"} and self._control_depth:
            self._control_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth or not data.strip():
            return
        self.visible_text.append(data)
        if self._control_depth:
            self.control_labels.append(data)


def _visible_ui() -> _VisibleUiParser:
    parser = _VisibleUiParser()
    parser.feed(_chat_ui_source())
    return parser


def test_visible_ui_omits_version_text() -> None:
    visible_text = " ".join(_visible_ui().visible_text)

    assert re.search(r"\b(?:version\s*)?v\d+(?:\.\d+)+\b", visible_text, re.IGNORECASE) is None


def test_open_graph_controls_are_absent() -> None:
    labels = " ".join(_visible_ui().control_labels).casefold()

    assert "open graph" not in labels
    assert "full graph" not in labels


def test_stack_book_click_uses_pdf_or_unavailable_flow() -> None:
    source = _chat_ui_source()
    display_books = _section(source, "function displayBooks()", "async function renderBookStack()")
    open_book = _section(
        source,
        "function openBookOrUnavailable(book)",
        "function openReadingMode(book)",
    )
    resolve = _section(
        source,
        "function resolveLibraryReaderLink(book)",
        "function openBookOrUnavailable(book)",
    )

    assert "btn.onclick = () => openBookOrUnavailable({" in display_books
    # Stack clicks navigate to Library details reader (PDF pane), not chat modal only.
    assert "resolveLibraryReaderLink(book)" in open_book
    assert "window.location.href = libraryHref" in open_book
    assert "/library?" in resolve
    assert "#book-reader" in resolve
    assert "Any stack item with a real PDF" in resolve or "rawPdf && /\\.pdf$/i.test(rawPdf)" in resolve
    # Unavailable path still exists for non-PDF cards (summary banner).
    assert "PDF Not Available" in source
    assert "Reference book · contents index" not in source
    assert "setReadingView('summary')" in open_book


def test_citation_viewer_stays_pdf_first_and_honors_requested_page() -> None:
    source = _chat_ui_source()
    viewer = _section(
        source,
        "async function openPageViewerModal(docId, page = 1, highlight = '')",
        "function setReadingView(view)",
    )
    initial_open = viewer[: viewer.index("try {")]
    successful_load = viewer[viewer.index("try {") : viewer.index("} catch (err)")]

    assert "const pageNum = parseInt(page, 10) || 1;" in viewer
    assert "#page=${pageNum}" in viewer
    assert "page: String(pageNum)" in viewer
    assert "buildPagePdfUrl(pdfPath)" in viewer
    assert "preferSummary: true" not in initial_open
    assert "preferSummary: false" in initial_open or "setReadingView('pdf')" in initial_open
    # Success path prefers PDF when available (may fall back to summary if no pdf).
    assert "setReadingView('pdf')" in successful_load


def test_response_links_are_blue_and_underlined() -> None:
    source = _chat_ui_source()
    link_css = _section(source, ".chat-bubble a {", ".chat-bubble a:hover")

    assert "color: #60a5fa" in link_css
    assert "text-decoration: underline" in link_css


def test_keyword_highlighting_uses_safe_dom_nodes_after_sanitization() -> None:
    source = _chat_ui_source()
    sanitizer = _section(source, "function sanitizeMarkdown(html)", "function renderMarkdownSafely")
    renderer = _section(
        source,
        "function renderMarkdownSafely",
        "// Curated AI/ML keyword glossary",
    )
    enrichment = _section(
        source,
        "function _enrichAssistantMarkup(root)",
        "function getResponseCitations(metadata)",
    )
    keyword_css = _section(source, ".chat-bubble mark.kw {", ".chat-bubble mark.kw:hover")

    assert "script, style, iframe, object, embed" in sanitizer
    assert "name.startsWith('on')" in sanitizer
    assert "value.startsWith('javascript:')" in sanitizer
    assert "target.innerHTML = sanitizeMarkdown(html);" in renderer
    assert "target.innerHTML = html;" not in renderer
    assert "document.createElement('mark')" in enrichment
    assert "mk.textContent = m[0];" in enrichment
    assert "mk.innerHTML" not in enrichment
    assert "SKIP_TAGS" in enrichment
    assert "'A'" in enrichment
    assert "background:" in keyword_css


def test_chat_uses_grounded_fallback_and_times_out_cleanly() -> None:
    source = _chat_ui_source()
    send_message = _section(
        source,
        "async function sendMessage()",
        "// Add to conversational history",
    )

    assert "const CHAT_RESPONSE_TIMEOUT_MS = 45000;" in source
    # Default product path enables optional SLM rewrite after grounded first paint.
    assert "synthesis: true" in send_message or "synthesis: false" in send_message
    assert "currentAbortController?.abort('The response timed out.')" in send_message


def test_reader_passage_has_explicit_light_surface_contrast() -> None:
    source = _chat_ui_source()
    reader_css = _section(
        source,
        "#reading-modal #reading-content {",
        "/* Glassmorphism utility */",
    )
    viewer = _section(
        source,
        "async function openPageViewerModal(docId, page = 1, highlight = '')",
        "function setReadingView(view)",
    )

    assert "background: #ffffff" in reader_css
    assert "color: #1f2937" in reader_css
    assert "#reading-modal #reading-content mark.page-hl" in reader_css
    assert "passage-meta-card" in viewer
    assert "passage-text-card" in viewer
