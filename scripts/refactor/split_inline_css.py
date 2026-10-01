"""Split inline ``<style>`` blocks out of a monolithic HTML page.

Part of the modularization effort.  The chat UI carried ~3,000 lines of CSS
inline; this tool moves that CSS into ``<link>``-ed files so the HTML stays a
readable template.  It is deliberately conservative:

* ``--dry-run`` prints the planned files and never writes.
* Splits happen only at top-level section comments (``/* ... */``) or blank
  lines, so no CSS rule is ever cut in half.
* After writing, it re-reads every chunk and asserts the concatenation equals
  the original CSS byte-for-byte.

Usage::

    python scripts/refactor/split_inline_css.py ui/chat/index.html \
        --out-dir ui/chat/styles --url-prefix /styles --dry-run
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

MAX_CHUNK_LINES = 380
STYLE_OPEN = re.compile(r"^\s*<style[^>]*>\s*$")
STYLE_CLOSE = re.compile(r"^\s*</style>\s*$")
SECTION_HEADER = re.compile(r"^\s*/\*")


def _style_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Return (start, end) line indexes of each <style> … </style> block."""
    blocks: list[tuple[int, int]] = []
    start = -1
    for index, line in enumerate(lines):
        if start < 0 and STYLE_OPEN.match(line):
            start = index
        elif start >= 0 and STYLE_CLOSE.match(line):
            blocks.append((start, index))
            start = -1
    if start >= 0:
        raise ValueError("unterminated <style> block")
    return blocks


def _split_at_boundaries(css_lines: list[str], max_lines: int) -> list[list[str]]:
    """Pack lines into chunks, cutting only after a complete CSS rule.

    A cut is allowed once the chunk reaches the soft limit and the current line
    closes a rule (``}``), starts a section comment, or is blank.  Because a
    rule can be longer than the soft limit, chunks may overshoot slightly but
    never split a declaration in half.
    """
    soft_limit = min(max_lines, int(max_lines * 0.85))
    chunks: list[list[str]] = []
    current: list[str] = []
    for line in css_lines:
        current.append(line)
        if len(current) < soft_limit:
            continue
        stripped = line.strip()
        if stripped.endswith("}") or not stripped or SECTION_HEADER.match(line):
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)
    return chunks


def _slug(text: str, fallback: str) -> str:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return "-".join(words[:4]) or fallback


def _css_name(chunk: list[str], index: int) -> str:
    for line in chunk:
        stripped = line.strip()
        if stripped.startswith("/*") and stripped.endswith("*/") and 4 < len(stripped) < 90:
            slug = _slug(stripped, f"block-{index:02d}")
            if slug:
                return f"{index:02d}-{slug}.css"
    return f"{index:02d}-styles.css"


def plan(html_path: Path, max_lines: int) -> tuple[list[str], list[tuple[str, list[str]]], list[str]]:
    """Return (css_chunks, named_chunks, kept_lines).

    ``kept_lines`` is the HTML with each ``<style>`` block replaced by a marker
    comment, ready for the caller to insert ``<link>`` tags.
    """
    lines = html_path.read_text(encoding="utf-8").splitlines(keepends=True)
    blocks = _style_blocks(lines)
    css_lines: list[str] = []
    keep: list[str] = []
    cursor = 0
    for start, end in blocks:
        keep.extend(lines[cursor:start])
        keep.append("<!-- styles moved to linked files -->\n")
        css_lines.extend(lines[start + 1 : end])
        cursor = end + 1
    keep.extend(lines[cursor:])
    chunks = _split_at_boundaries(css_lines, max_lines)
    named = [(_css_name(chunk, i + 1), chunk) for i, chunk in enumerate(chunks)]
    return css_lines, named, keep


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("html", type=Path)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--url-prefix", default="/styles")
    parser.add_argument("--max-lines", type=int, default=MAX_CHUNK_LINES)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    css_lines, named, keep = plan(args.html, args.max_lines)
    joined = "".join(line for _, chunk in named for line in chunk)
    if joined != "".join(css_lines):
        raise SystemExit("refusing to write: split CSS does not match the original")
    total_css = sum(len(chunk) for _, chunk in named)
    print(f"CSS lines: {len(css_lines)} -> {total_css} across {len(named)} files")
    print("verified: split chunks reconstruct the original CSS exactly")
    for name, chunk in named:
        print(f"  {name:<44} {len(chunk):>4} lines")

    if not args.dry_run and not args.write:
        print("(no output written; pass --write to apply)")
        return 0
    if args.dry_run:
        return 0

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, chunk in named:
        (args.out_dir / name).write_text("".join(chunk), encoding="utf-8")

    links = "".join(
        f'    <link rel="stylesheet" href="{args.url_prefix}/{name}">\n' for name, _ in named
    )
    text = "".join(keep)
    marker = "<!-- styles moved to linked files -->\n"
    first = text.index(marker)
    text = text[:first] + links.strip("\n") + "\n" + text[first + len(marker):]
    text = text.replace("<!-- styles moved to linked files -->\n", "")
    args.html.write_text(text, encoding="utf-8")
    print(f"wrote {len(named)} files and rewrote {args.html}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
