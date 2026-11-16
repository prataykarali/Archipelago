"""Browser regression for provider author lists containing null IDs."""

from __future__ import annotations

from pathlib import Path
import shutil

import pytest

ROOT = Path(__file__).resolve().parents[2]
RESEARCH_SCRIPTS = (
    ROOT / "host_inference/ui/research_intelligence.js",
    ROOT / "host_research/ui/research_intelligence.js",
)
PAGE = """
<section id="intelligence-results" hidden></section>
<a id="topic-dossier-link"></a><p id="retrieved-at"></p>
<p id="provider-status"></p><a id="excel-link"></a>
<div id="paper-results"></div>
"""


@pytest.mark.e2e
@pytest.mark.parametrize("script", RESEARCH_SCRIPTS)
def test_research_page_renders_null_author_ids(script: Path) -> None:
    """A provider's null author ID must not hide otherwise valid papers."""
    playwright = pytest.importorskip("playwright.sync_api")
    chrome = shutil.which("google-chrome") or shutil.which("chromium")
    if chrome is None:
        pytest.skip("Chrome is not installed")
    run = {
        "retrieved_at": "2026-11-17T00:00:00Z",
        "candidate_count": 2,
        "filtered_count": 2,
        "sources": [{"source": "openalex", "status": "live", "record_count": 2}],
        "author_observations": [{"id": "A1", "metrics": {"h_index": 3}}],
        "papers": [
            {
                "title": "Omni AI models",
                "authors": [{"name": "Unknown Author"}, {"name": "Known Author"}],
                "source_metadata": {"author_openalex_ids": [None, "https://openalex.org/A1"]},
                "citation_count": 5,
            },
            {
                "title": "Multimodal AI systems",
                "authors": [{"name": "Unknown Author"}],
                "source_metadata": {"author_openalex_ids": [None]},
            },
        ],
    }
    with playwright.sync_playwright() as runtime:
        browser = runtime.chromium.launch(headless=True, executable_path=chrome)
        page = browser.new_page()
        page.set_content(PAGE)
        page.add_script_tag(path=str(script))
        result = page.evaluate(
            """run => {
                activeRunId = '12345678-1234-1234-1234-123456789abc';
                showRun(run);
                return {
                    papers: document.querySelectorAll('#paper-results article').length,
                    authors: [...document.querySelectorAll('#paper-results h4')].map(el => el.textContent),
                    exportLink: document.querySelector('#excel-link').getAttribute('href')
                };
            }""",
            run,
        )
        browser.close()
    assert result["papers"] == 2
    assert result["authors"] == ["Unknown Author", "Known Author", "Unknown Author"]
    assert result["exportLink"].endswith("/xlsx?mode=standard")
