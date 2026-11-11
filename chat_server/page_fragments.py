"""Assemble the static chat and library shells from focused HTML sections."""

from __future__ import annotations

from pathlib import Path
import re

from flask import Response

_INCLUDE = re.compile(r"<!-- include: ([a-z0-9-]+\.html) -->\n")


def assembled_page(root: Path, name: str) -> Response:
    """Serve a local HTML shell with its same-directory fragments inlined."""
    html = (root / name).read_text(encoding="utf-8")

    def insert(match: re.Match[str]) -> str:
        return (root / "fragments" / match.group(1)).read_text(encoding="utf-8")

    return Response(_INCLUDE.sub(insert, html), mimetype="text/html")
