"""Deterministic extractors for EPUB, LibreTexts HTML, PDF, and LaTeX OA sources."""

from __future__ import annotations

import hashlib
from pathlib import Path
import re
import zipfile

from bs4 import BeautifulSoup, Tag
import fitz

from .constants import FORBIDDEN_SOURCE_PATTERNS
from .models import ExtractedUnit

HASH_CHUNK_BYTES = 65536
LIGATURE_MAP: dict[str, str] = {
    "\ufb00": "ff",
    "\ufb01": "fi",
    "\ufb02": "fl",
    "\ufb03": "ffi",
    "\ufb04": "ffl",
    "\u00ad": "",
}
HYPHEN_LINEBREAK_RE = re.compile(r"([A-Za-z])-\n([a-z])")
MULTI_SPACE_RE = re.compile(r"[ \t]+")
EXCESS_NEWLINE_RE = re.compile(r"\n{3,}")
LATEX_COMMENT_RE = re.compile(r"(?<!\\)%[^\n]*")
LATEX_BLOCK_STRIP_RE = re.compile(
    r"\\begin\{(tikzpicture|pgfpicture|figure|table|minted|lstlisting|verbatim)\*?\}"
    r".*?\\end\{\1\*?\}",
    re.DOTALL,
)
LATEX_HEADING_RE = re.compile(
    r"\\(?:section|subsection|subsubsection|chapter|lecture)\*?\{([^}]+)\}"
)
LATEX_INLINE_UNWRAP_RE = re.compile(
    r"\\(?:textbf|textit|emph|texttt|text|textrm|mathrm|mathbf|mathsf|url|footnote|alert)"
    r"\{([^{}]*)\}"
)
LATEX_CMD_ARG_DROP_RE = re.compile(
    r"\\(?:cite|citep|citet|ref|eqref|label|includegraphics|vspace|hspace|"
    r"bibliographystyle|bibliography|hypertarget|pause|only|uncover|visible)"
    r"(?:\[[^\]]*\])?(?:\{[^{}]*\})?"
)
LATEX_BARE_CMD_RE = re.compile(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?")
LATEX_BRACES_RE = re.compile(r"[{}]")
EPUB_HEADING_TAGS: tuple[str, ...] = ("h1", "h2", "h3", "h4")
EPUB_BLOCK_TAGS: tuple[str, ...] = ("h1", "h2", "h3", "h4", "p", "li")
HTML_SKIP_SELECTORS: tuple[str, ...] = (
    "nav",
    "script",
    "style",
    "footer",
    "header",
    ".mt-page-navigation",
    ".elm-nav-container",
)
UNWRAP_PASSES = 3


class ForbiddenSourceError(ValueError):
    """Raised when a forbidden or unverified source path is encountered."""


def check_not_forbidden(path_or_url: str) -> None:
    """Reject any path or URL matching forbidden source rules."""
    lowered = path_or_url.lower().replace("\\", "/")
    for pattern in FORBIDDEN_SOURCE_PATTERNS:
        if pattern in lowered:
            raise ForbiddenSourceError(f"Source matches forbidden rule '{pattern}': {path_or_url}")


def compute_file_sha256(path: Path) -> str:
    """Compute streaming hex SHA-256 of a local file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            block = handle.read(HASH_CHUNK_BYTES)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def compute_directory_sha256(directory: Path, pattern: str = "*.html") -> str:
    """Compute deterministic composite SHA-256 over sorted matching files."""
    digest = hashlib.sha256()
    for file_path in sorted(directory.glob(pattern)):
        digest.update(file_path.name.encode("utf-8"))
        digest.update(b":")
        digest.update(compute_file_sha256(file_path).encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()


def clean_text(raw: str) -> str:
    """Normalize ligatures, hyphenated linebreaks, and whitespace."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    for src, dst in LIGATURE_MAP.items():
        if src in text:
            text = text.replace(src, dst)
    text = HYPHEN_LINEBREAK_RE.sub(r"\1\2", text)
    lines = [MULTI_SPACE_RE.sub(" ", line).strip() for line in text.split("\n")]
    return EXCESS_NEWLINE_RE.sub("\n\n", "\n".join(lines)).strip()


def extract_epub_units(epub_path: Path) -> list[ExtractedUnit]:
    """Extract section-grouped prose units from an EPUB (page_number=None)."""
    check_not_forbidden(str(epub_path))
    units: list[ExtractedUnit] = []
    with zipfile.ZipFile(epub_path) as archive:
        xhtml_names = sorted(
            name
            for name in archive.namelist()
            if name.endswith((".xhtml", ".html", ".htm")) and "nav" not in Path(name).name.lower()
        )
        section_idx = 0
        for name in xhtml_names:
            raw_html = archive.read(name).decode("utf-8", errors="replace")
            soup = BeautifulSoup(raw_html, "lxml")
            for tag in soup.find_all(["script", "style", "nav"]):
                tag.decompose()

            current_heading = "Introduction"
            buffer: list[str] = []
            for elem in soup.find_all(list(EPUB_BLOCK_TAGS)):
                if not isinstance(elem, Tag):
                    continue
                txt = clean_text(elem.get_text(" ", strip=True))
                if not txt:
                    continue
                if elem.name in EPUB_HEADING_TAGS:
                    if buffer:
                        section_idx += 1
                        units.append(
                            ExtractedUnit(
                                section_heading=current_heading,
                                section_ref=f"epub_sec_{section_idx:03d}",
                                page_number=None,
                                text="\n\n".join(buffer),
                            )
                        )
                        buffer = []
                    current_heading = txt
                else:
                    buffer.append(txt)
            if buffer:
                section_idx += 1
                units.append(
                    ExtractedUnit(
                        section_heading=current_heading,
                        section_ref=f"epub_sec_{section_idx:03d}",
                        page_number=None,
                        text="\n\n".join(buffer),
                    )
                )
    return units


def extract_libretexts_html_units(html_dir: Path) -> list[ExtractedUnit]:
    """Extract chapter/section units from downloaded LibreTexts HTML chapters."""
    check_not_forbidden(str(html_dir))
    units: list[ExtractedUnit] = []
    chapter_files = sorted(html_dir.glob("ch*.html"))
    for ch_file in chapter_files:
        soup = BeautifulSoup(ch_file.read_bytes(), "lxml")
        container = soup.find("section", class_="mt-content-container")
        if not isinstance(container, Tag):
            continue
        for selector in HTML_SKIP_SELECTORS:
            for bad in container.select(selector):
                bad.decompose()

        title_tag = soup.find("h1")
        chapter_title = (
            clean_text(title_tag.get_text(" ", strip=True))
            if isinstance(title_tag, Tag)
            else ch_file.stem
        )
        current_heading = chapter_title
        sub_idx = 0
        buffer: list[str] = []

        for elem in container.find_all(["h2", "h3", "p", "li"]):
            if not isinstance(elem, Tag):
                continue
            txt = clean_text(elem.get_text(" ", strip=True))
            if not txt:
                continue
            if elem.name in ("h2", "h3"):
                if buffer:
                    sub_idx += 1
                    units.append(
                        ExtractedUnit(
                            section_heading=current_heading,
                            section_ref=f"{ch_file.stem}_sec_{sub_idx:02d}",
                            page_number=None,
                            text="\n\n".join(buffer),
                        )
                    )
                    buffer = []
                current_heading = f"{chapter_title} — {txt}"
            else:
                buffer.append(txt)
        if buffer:
            sub_idx += 1
            units.append(
                ExtractedUnit(
                    section_heading=current_heading,
                    section_ref=f"{ch_file.stem}_sec_{sub_idx:02d}",
                    page_number=None,
                    text="\n\n".join(buffer),
                )
            )
    return units


def extract_pdf_units(pdf_path: Path) -> list[ExtractedUnit]:
    """Extract exact 1-based per-page text units from an OA PDF via PyMuPDF."""
    check_not_forbidden(str(pdf_path))
    units: list[ExtractedUnit] = []
    with fitz.open(str(pdf_path)) as doc:
        for idx in range(len(doc)):
            text = clean_text(str(doc[idx].get_text("text")))
            if not text:
                continue
            page_num = idx + 1
            units.append(
                ExtractedUnit(
                    section_heading=f"Page {page_num}",
                    section_ref=f"page_{page_num:04d}",
                    page_number=page_num,
                    text=text,
                )
            )
    return units


def _strip_latex_markup(raw_tex: str) -> str:
    """Convert LaTeX prose to clean plain text while removing figures/commands."""
    text = LATEX_COMMENT_RE.sub("", raw_tex)
    text = LATEX_BLOCK_STRIP_RE.sub("\n\n", text)
    text = LATEX_CMD_ARG_DROP_RE.sub("", text)
    for _ in range(UNWRAP_PASSES):
        text = LATEX_INLINE_UNWRAP_RE.sub(r"\1", text)
    text = text.replace(r"\\", "\n").replace("~", " ")
    text = LATEX_BARE_CMD_RE.sub(" ", text)
    text = LATEX_BRACES_RE.sub("", text)
    return clean_text(text)


def extract_latex_units(tex_path: Path) -> list[ExtractedUnit]:
    """Extract section-grouped prose units from LaTeX source (page_number=None)."""
    check_not_forbidden(str(tex_path))
    raw_tex = tex_path.read_text(encoding="utf-8", errors="replace")
    matches = list(LATEX_HEADING_RE.finditer(raw_tex))
    if not matches:
        cleaned = _strip_latex_markup(raw_tex)
        return (
            [
                ExtractedUnit(
                    section_heading=tex_path.stem,
                    section_ref="tex_sec_001",
                    page_number=None,
                    text=cleaned,
                )
            ]
            if cleaned
            else []
        )

    units: list[ExtractedUnit] = []
    for idx, match in enumerate(matches):
        heading = clean_text(_strip_latex_markup(match.group(1)))
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_tex)
        body = _strip_latex_markup(raw_tex[start:end])
        if body:
            units.append(
                ExtractedUnit(
                    section_heading=heading or f"Section {idx + 1}",
                    section_ref=f"tex_sec_{idx + 1:03d}",
                    page_number=None,
                    text=body,
                )
            )
    return units
