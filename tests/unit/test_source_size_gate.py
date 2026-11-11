"""Tests for the roadmap's cross-language source-size gate."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.source_size_gate import oversized_sources, source_files


@pytest.mark.unit
def test_source_size_gate_covers_app_ui_scripts_and_tests(tmp_path: Path) -> None:
    """The gate reports each hand-written source above its line limit."""
    app = tmp_path / "archipelago" / "large.py"
    ui = tmp_path / "frontend" / "page.tsx"
    test = tmp_path / "tests" / "unit" / "test_large.py"
    for path in (app, ui, test):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("line\n" * 4, encoding="utf-8")

    found = {path for path, _ in oversized_sources(tmp_path, limit=3)}

    assert found == {
        Path("archipelago/large.py"),
        Path("frontend/page.tsx"),
        Path("tests/unit/test_large.py"),
    }


@pytest.mark.unit
def test_source_size_gate_skips_generated_and_vendor_files(tmp_path: Path) -> None:
    """Generated, minified, and vendor content do not trigger the gate."""
    folder = tmp_path / "frontend"
    folder.mkdir()
    for name in ("bundle.min.js", "schema.generated.ts"):
        (folder / name).write_text("line\n" * 4, encoding="utf-8")
    vendor = folder / "vendor" / "library.js"
    vendor.parent.mkdir()
    vendor.write_text("line\n" * 4, encoding="utf-8")
    ordinary = folder / "app.js"
    ordinary.write_text("line\n" * 4, encoding="utf-8")

    assert source_files(tmp_path) == [ordinary]
    assert oversized_sources(tmp_path, limit=3) == [(Path("frontend/app.js"), 4)]
