"""Integrity tests for the chat UI source links and the two-tree dedupe.

These pin three things that were real, shipped bugs:

1. Pearson reader URLs must join query parameters with ``&`` — a second ``?``
   makes Pearson ignore the subscription id and open the wrong page.
2. The exact-source link interceptor (Pearson / Hugging Face / page links) must
   exist in the modules the chat page actually loads.
3. The hosted tree (``host_inference/ui``) must not drift from the canonical
   ``ui/chat`` tree — that drift is what caused the Pearson bug to appear only
   on the hosted deployment.
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "ui" / "chat"
HOSTED = ROOT / "host_inference" / "ui"

# A second '?' after the Pearson version parameter is always malformed.
MALFORMED_VERSION = "1.0.317.1?"

pytestmark = pytest.mark.unit


def _js_files(root: Path) -> list[Path]:
    return sorted((root / "js").glob("*.js"))


def test_no_malformed_pearson_version_parameter():
    for root in (CANONICAL, HOSTED):
        for path in _js_files(root):
            text = path.read_text(encoding="utf-8")
            assert MALFORMED_VERSION not in text, f"{path} has a double '?' Pearson URL"


def test_pearson_links_use_the_manual_page_gateway():
    """The browser must not reconstruct unsupported external page fragments."""
    for root in (CANONICAL, HOSTED):
        citation = (root / "js/02--kw-highlights.js").read_text()
        click = (root / "js/21-generate-roadmap.js").read_text()
        assert "/open/${encodeURIComponent(bId)}?page=" in citation
        assert "/open/${encodeURIComponent(bId)}?page=" in click
        assert "pearson.com/wr/" not in citation + click
        assert "pEntry.id || '0fcd531f" not in click


def test_link_interceptor_is_loaded_by_the_chat_page():
    """The entry module graph must include the exact-source click interceptor."""
    for root in (CANONICAL, HOSTED):
        index = (root / "index.html").read_text(encoding="utf-8")
        assert '<script type="module" src="/js/index.js"></script>' in index

        entry = (root / "js" / "index.js").read_text(encoding="utf-8")
        loaded = {line.split("'./")[-1].split("'")[0] for line in entry.splitlines() if "import './" in line}
        interceptor = [
            name for name in loaded
            if "addEventListener('click'" in (root / "js" / name).read_text(encoding="utf-8")
        ]
        interceptors_text = "".join(
            (root / "js" / name).read_text(encoding="utf-8") for name in interceptor
        )
        assert "huggingface.co" in interceptors_text, f"{root}: no Hugging Face link handling"
        assert "/open/" in interceptors_text, f"{root}: no Pearson gateway link handling"
        assert "citationPageUrl" in interceptors_text, f"{root}: no page-link resolution"


def test_hosted_ui_js_matches_canonical_ui_js():
    """The hosted deployment must serve the same module source as ui/chat."""
    canonical = {path.name: path.read_text(encoding="utf-8") for path in _js_files(CANONICAL)}
    hosted = {path.name: path.read_text(encoding="utf-8") for path in _js_files(HOSTED)}
    assert canonical, "no canonical chat modules found"
    assert set(canonical) == set(hosted), (
        f"module sets differ: canonical-only={sorted(set(canonical) - set(hosted))}, "
        f"hosted-only={sorted(set(hosted) - set(canonical))}"
    )
    for name, text in canonical.items():
        assert hosted[name] == text, f"{name} has drifted between ui/chat and host_inference/ui"


def test_hosted_ui_styles_match_canonical_ui_styles():
    canonical = sorted((CANONICAL / "styles").glob("*.css"))
    assert canonical, "no canonical styles found"
    for path in canonical:
        hosted = HOSTED / "styles" / path.name
        assert hosted.is_file(), f"hosted tree is missing {path.name}"
        assert hosted.read_text(encoding="utf-8") == path.read_text(encoding="utf-8"), (
            f"{path.name} has drifted between ui/chat and host_inference/ui"
        )


def test_dead_roadmap_quiz_script_is_gone():
    """roadmap_quiz.js never existed; the tag 404'd on every page load."""
    for root in (CANONICAL, HOSTED):
        index = (root / "index.html").read_text(encoding="utf-8")
        assert "roadmap_quiz.js" not in index, f"{root}/index.html still references a missing script"


def test_dataset_reader_keeps_path_separators_for_deployed_proxy():
    """The reverse proxy rejects encoded slashes in reader metadata paths."""
    for root in (CANONICAL, HOSTED):
        reader = (root / "reader.html").read_text(encoding="utf-8")
        assert "resourceId.split('/').map(encodeURIComponent).join('/')" in reader
        assert "`/api/reader/info/${routeId}?page=${pageNum}`" in reader
        assert "/api/reader/info/${encodeURIComponent(resourceId)}" not in reader
