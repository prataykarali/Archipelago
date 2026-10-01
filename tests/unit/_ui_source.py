"""Shared reader for the modularised UI source trees.

The chat/graph pages used to be single self-contained HTML files.  We now keep
the markup in the page and move CSS/JS into linked files under ``styles/`` and
``js/``.  Contract tests still assert on the *logical* source, so this helper
returns the page with every local linked asset inlined, in document order,
following relative ES-module ``import`` statements so module bodies are visible.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

_LINK_RE = re.compile(
    r'<link[^>]*rel="stylesheet"[^>]*href="([^"]+)"[^>]*>', re.IGNORECASE
)
_SCRIPT_RE = re.compile(r'<script[^>]*src="([^"]+)"[^>]*>\s*</script>', re.IGNORECASE)
# Matches both `import { x } from './m.js'` and side-effect `import './m.js'`.
_IMPORT_RE = re.compile(r"""import\s+(?:[^;]*?from\s*)?['"](\./[^'"]+)['"]""")


def _resolve(page_dir: Path, href: str) -> Path | None:
    """Resolve a page-relative asset path; return None for remote URLs."""
    if href.startswith(("http://", "https://", "//")):
        return None
    relative = href.lstrip("/")
    for candidate in (page_dir / relative, page_dir / relative.split("/", 1)[-1]):
        if candidate.is_file():
            return candidate
    return None


def _module_bundle(path: Path) -> str:
    """Return a module's source followed by its relative imports, recursively.

    Ordering follows the entry module's own import list first (so a barrel
    ``index.js`` yields modules in authored order), with any nested-only
    imports appended afterwards in discovery order.
    """
    entry_text = path.read_text(encoding="utf-8")
    direct = [t for href in _IMPORT_RE.findall(entry_text) if (t := _resolve(path.parent, href))]
    extra: list[Path] = []
    seen: set[Path] = set()

    def collect(module: Path) -> None:
        if module in seen:
            return
        seen.add(module)
        for href in _IMPORT_RE.findall(module.read_text(encoding="utf-8")):
            target = _resolve(module.parent, href)
            if target is not None and target not in direct:
                extra.append(target)
                collect(target)

    for module in direct:
        collect(module)
    ordered = [*direct, *[m for m in extra if m not in direct]]
    parts = [entry_text, *(m.read_text(encoding="utf-8") for m in ordered)]
    return "\n".join(parts)


def _inline(page: Path, regex: re.Pattern[str], tag: str, bundle: bool) -> str:
    text = page.read_text(encoding="utf-8")
    cache: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        href = match.group(1)
        asset = _resolve(page.parent, href)
        if asset is None:
            return match.group(0)
        if href not in cache:
            cache[href] = _module_bundle(asset) if bundle else asset.read_text(encoding="utf-8")
        return f"<{tag}>\n{cache[href]}\n</{tag}>"

    return regex.sub(replace, text)


def ui_source(page: Path) -> str:
    """Return a UI page with its local linked CSS and JS inlined in place."""
    inlined = _inline(page, _LINK_RE, "style", bundle=False)
    return _inline_text(page, inlined, _SCRIPT_RE, "script", bundle=True)


def _inline_text(page: Path, text: str, regex: re.Pattern[str], tag: str, bundle: bool) -> str:
    cache: dict[str, str] = {}

    def replace(match: re.Match[str]) -> str:
        href = match.group(1)
        asset = _resolve(page.parent, href)
        if asset is None:
            return match.group(0)
        if href not in cache:
            cache[href] = _module_bundle(asset) if bundle else asset.read_text(encoding="utf-8")
        return f"<{tag}>\n{cache[href]}\n</{tag}>"

    return regex.sub(replace, text)


def local_script_files(page: Path) -> list[Path]:
    """Every local JS file the page loads, following relative module imports."""
    text = page.read_text(encoding="utf-8")
    files: list[Path] = []
    seen: set[Path] = set()

    def visit(module: Path) -> None:
        if module in seen:
            return
        seen.add(module)
        files.append(module)
        for href in _IMPORT_RE.findall(module.read_text(encoding="utf-8")):
            target = _resolve(module.parent, href)
            if target is not None:
                visit(target)

    for href in _SCRIPT_RE.findall(text):
        asset = _resolve(page.parent, href)
        if asset is not None:
            visit(asset)
    return files


def chat_ui_source() -> str:
    """Logical source of the canonical student chat UI."""
    return ui_source(ROOT / "ui" / "chat" / "index.html")


def graph_ui_source() -> str:
    """Logical source of the canonical graph UI."""
    return ui_source(ROOT / "ui" / "graph" / "index.html")
