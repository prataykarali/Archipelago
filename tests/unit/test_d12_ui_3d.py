"""D12 Sections 4, 5, and 7: Frontend 3D UI Restoration, Badge Honesty & Graph Arrow Visibility tests."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
from typing import Any

import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
HOST_UI = ROOT / "host_inference" / "ui"
CANON_UI = ROOT / "ui" / "chat"

D12_SYNCED_FILES = (
    "index.html",
    "chromatic_waves.js",
    "styles/14-d12-ui-3d.css",
    "js/01--hide-welcome-with-transitio.js",
    "js/02--kw-highlights.js",
    "js/08-send-message.js",
    "js/11-populate-topology.js",
    "js/11a-topology-layout.js",
    "js/15-inspector.js",
    "js/19-draw-horizontal-svg.js",
    "js/22-welcome-suggestions.js",
)

NODE_TIMEOUT_SECONDS = 15

NODE_DOM_SHIM = """
globalThis.window = {
    addEventListener: () => {},
    removeEventListener: () => {},
    matchMedia: () => ({ matches: false }),
    location: { origin: "http://localhost:5051", pathname: "/chat", search: "", hash: "" },
};
globalThis.document = {
    createElement: () => ({ style: {}, classList: { add() {}, remove() {}, toggle() {}, contains: () => false }, setAttribute() {}, addEventListener() {} }),
    getElementById: (id) => (id === "chat-input" ? { style: {}, addEventListener() {}, scrollHeight: 40 } : null),
    querySelector: () => null,
    querySelectorAll: () => [],
    addEventListener: () => {},
    documentElement: { dataset: {} },
};
globalThis.localStorage = { getItem: () => null, setItem: () => {}, removeItem: () => {} };
globalThis.fetch = async () => ({ ok: false, json: async () => ({}) });
"""


def _run_node_json(script: str) -> Any:
    """Execute a short ESM Node script and parse its JSON stdout."""
    node_bin = shutil.which("node")
    if not node_bin:
        pytest.skip("node runtime unavailable")
    proc = subprocess.run(
        [node_bin, "--input-type=module", "-e", script],
        capture_output=True,
        text=True,
        check=True,
        timeout=NODE_TIMEOUT_SECONDS,
    )
    return json.loads(proc.stdout.strip())


def test_d12_ui_files_byte_for_byte_synced() -> None:
    """All D12-modified UI files must stay byte-for-byte synced between host_inference/ui and ui/chat."""
    for rel_path in D12_SYNCED_FILES:
        hosted = HOST_UI / rel_path
        canonical = CANON_UI / rel_path
        assert hosted.is_file(), f"Missing hosted UI file: {rel_path}"
        assert canonical.is_file(), f"Missing canonical ui/chat file: {rel_path}"
        assert hosted.read_bytes() == canonical.read_bytes(), f"Drift detected in {rel_path}"


def test_section7_3d_aesthetic_avatar_label_and_performance() -> None:
    """3D aesthetic CSS, centered glowing avatar with label above, chromatic waves, and numbered topics are wired."""
    index_html = (HOST_UI / "index.html").read_text(encoding="utf-8")
    css_3d = (HOST_UI / "styles" / "14-d12-ui-3d.css").read_text(encoding="utf-8")
    waves_js = (HOST_UI / "chromatic_waves.js").read_text(encoding="utf-8")
    welcome_js = (HOST_UI / "js" / "22-welcome-suggestions.js").read_text(encoding="utf-8")

    # Stylesheet load order: 14-d12-ui-3d.css loads after 13-d11-b-ux-readability.css
    idx_13 = index_html.index("/styles/13-d11-b-ux-readability.css")
    idx_14 = index_html.index("/styles/14-d12-ui-3d.css")
    assert idx_14 > idx_13

    # AI Librarian label positioned cleanly ABOVE both welcome and sticky avatars (no duplicates per dock)
    dock_start = index_html.index('id="sticky-avatar-dock"')
    dock_end = index_html.index("</aside>", dock_start)
    dock_html = index_html[dock_start:dock_end]
    assert dock_html.count("AI Librarian") == 1
    assert dock_html.index("AI Librarian") < dock_html.index('id="sticky-avatar"')

    welcome_start = index_html.index('class="welcome-avatar-stack"')
    welcome_end = index_html.index('class="welcome-title', welcome_start)
    welcome_avatar_html = index_html[welcome_start:welcome_end]
    assert welcome_avatar_html.count("AI Librarian") == 1
    assert welcome_avatar_html.index("AI Librarian") < welcome_avatar_html.index('id="welcome-avatar"')

    # 3D depth, glowing ring avatar, dot-grid atmospheric depth, reduced-motion, and B+ Tree heading font
    assert "#chromatic-waves-bg" in css_3d
    assert "#chat-stage::before" in css_3d
    assert "#welcome-avatar.welcome-avatar" in css_3d
    assert "backdrop-filter: blur(18px)" in css_3d
    assert "#graph-node-title" in css_3d
    assert "prefers-reduced-motion: reduce" in css_3d

    # Performance throttling and tab visibility pause in chromatic_waves.js
    assert "FRAME_INTERVAL_MS" in waves_js
    assert "visibilitychange" in waves_js
    assert "prefers-reduced-motion: reduce" in waves_js

    # Numbered 1), 2) topics in welcome suggestions
    assert "${idx + 1})" in welcome_js


def test_section7_b_plus_tree_markdown_normalization() -> None:
    """B+ Tree and special technical characters survive markdown normalization cleanly."""
    mod_url = (HOST_UI / "js" / "01--hide-welcome-with-transitio.js").resolve().as_uri()
    result = _run_node_json(
        f"""
        {NODE_DOM_SHIM}
        const {{ normalizeTechnicalMarkdown }} = await import({json.dumps(mod_url)});
        const sample = "## B+ Tree vs B-Tree\\n\\nA B&#43; Tree in C++ supports O(log n) range scans.";
        const out = normalizeTechnicalMarkdown(sample);
        console.log(JSON.stringify({{ out }}));
        """
    )
    out = result["out"]
    assert "## B+ Tree vs B-Tree" in out
    assert "B+ Tree in C++" in out
    assert "O(log n)" in out


def test_section4_grounding_badge_honesty_and_source_kind_tags() -> None:
    """Badge never claims Evidence-Backed when citations are empty or evidence_backed is false; source kinds render honestly."""
    inspector_url = (HOST_UI / "js" / "15-inspector.js").resolve().as_uri()
    kw_url = (HOST_UI / "js" / "02--kw-highlights.js").resolve().as_uri()
    result = _run_node_json(
        f"""
        {NODE_DOM_SHIM}
        const {{ renderGroundingBadge, _renderCitation }} = await import({json.dumps(inspector_url)});
        const {{ citationPageUrl }} = await import({json.dumps(kw_url)});

        const emptyCitesBadge = renderGroundingBadge(
            {{ synthesis_mode: "verified_deterministic", grounding_status: "verified", grounded_passages: 0 }},
            {{ citations: [], evidence_backed: false }}
        );
        const explicitFalseBadge = renderGroundingBadge(
            {{ synthesis_mode: "verified_deterministic", grounding_status: "verified", grounded_passages: 2 }},
            {{ citations: [{{ doc_id: "papers/Lewis2020_RAG.pdf", source_kind: "verified_full_text_passage" }}], evidence_backed: false }}
        );
        const metadataOnlyBadge = renderGroundingBadge(
            {{ synthesis_mode: "verified_deterministic", grounding_status: "verified", grounded_passages: 1 }},
            {{ citations: [{{ title: "Tanenbaum MOS", source_kind: "metadata_only_record" }}] }}
        );
        const conversationalBadge = renderGroundingBadge(
            {{ intent: "GREETING", synthesis_mode: "verified_deterministic", grounding_status: "general" }},
            {{ citations: [], evidence_backed: false }}
        );
        const verifiedBadge = renderGroundingBadge(
            {{ synthesis_mode: "verified_deterministic", grounding_status: "verified", grounded_passages: 1 }},
            {{ citations: [{{ doc_id: "papers/Lewis2020_RAG.pdf", page_number: 2, source_kind: "verified_full_text_passage" }}], evidence_backed: true }}
        );

        const metaCite = {{ title: "Tanenbaum Modern OS", source_kind: "metadata_only_record", open_url: "/chat" }};
        const unavailCite = {{ title: "Missing Textbook", source_kind: "unavailable_document", open_url: "/read?doc=missing.pdf&page=545" }};
        const chatSelfCite = {{ title: "Self Loop Card", open_url: "/chat?q=paging" }};
        const validCite = {{ doc_id: "papers/Lewis2020_RAG.pdf", page_number: 3, source_kind: "verified_full_text_passage" }};

        console.log(JSON.stringify({{
            emptyCitesBadge,
            explicitFalseBadge,
            metadataOnlyBadge,
            conversationalBadge,
            verifiedBadge,
            metaUrl: citationPageUrl(metaCite),
            unavailUrl: citationPageUrl(unavailCite),
            chatSelfUrl: citationPageUrl(chatSelfCite),
            validUrl: citationPageUrl(validCite),
            metaCardHtml: _renderCitation(metaCite, 0),
            unavailCardHtml: _renderCitation(unavailCite, 1),
        }}));
        process.exit(0);
        """
    )

    for badge in (result["emptyCitesBadge"], result["explicitFalseBadge"], result["metadataOnlyBadge"]):
        assert "Evidence-Backed" not in badge
        assert 'data-evidence-backed="false"' in badge
        assert "No Source Passages" in badge

    assert "Evidence-Backed" not in result["conversationalBadge"]
    assert "Conversational" in result["conversationalBadge"]
    assert 'data-evidence-backed="false"' in result["conversationalBadge"]

    assert "Deterministic · Evidence-Backed" in result["verifiedBadge"]
    assert 'data-evidence-backed="true"' in result["verifiedBadge"]

    assert result["metaUrl"] == ""
    assert result["unavailUrl"] == ""
    assert result["chatSelfUrl"] == ""
    assert result["validUrl"].startswith("/read?doc=")

    assert "Metadata-Only Record" in result["metaCardHtml"]
    assert 'href="/chat"' not in result["metaCardHtml"]
    assert "Open Page in Reader" not in result["metaCardHtml"]

    assert "Unavailable Document" in result["unavailCardHtml"]
    assert "Open Page in Reader" not in result["unavailCardHtml"]


def test_section5_graph_arrow_markers_and_edge_endpoints() -> None:
    """Graph edges trim cleanly to node perimeters and SVG markers use visible userSpaceOnUse geometry."""
    layout_url = (HOST_UI / "js" / "11a-topology-layout.js").resolve().as_uri()
    result = _run_node_json(
        f"""
        import {{ buildArrowMarkerDefs, computeEdgeEndpoints }} from {json.dumps(layout_url)};
        const horiz = computeEdgeEndpoints(64, 80, 150, 80, 10, 14, 5);
        const diag = computeEdgeEndpoints(64, 40, 150, 120, 10, 14, 5);
        const defs = buildArrowMarkerDefs("sidebar-svg-map", {{ size: 8 }});
        console.log(JSON.stringify({{ horiz, diag, defs }}));
        """
    )

    horiz = result["horiz"]
    assert horiz["sx"] > 64 and horiz["ex"] < 150
    assert horiz["sy"] == 80 and horiz["ey"] == 80

    diag = result["diag"]
    assert diag["sx"] > 64 and diag["sy"] > 40
    assert diag["ex"] < 150 and diag["ey"] < 120

    defs = result["defs"]
    for marker_id in ("arr-pre-sidebar-svg-map", "arr-unl-sidebar-svg-map", "arr-rel-sidebar-svg-map"):
        assert f'id="{marker_id}"' in defs
    assert 'refX="9"' in defs
    assert 'markerUnits="userSpaceOnUse"' in defs
    assert 'overflow="visible"' in defs

    topo_js = (HOST_UI / "js" / "11-populate-topology.js").read_text(encoding="utf-8")
    horiz_js = (HOST_UI / "js" / "19-draw-horizontal-svg.js").read_text(encoding="utf-8")
    ops_html = (HOST_UI / "fragments" / "chat-operations.html").read_text(encoding="utf-8")

    # Broken refX="18" / refX="22" and objectBoundingBox edge filters are gone
    assert 'refX="18"' not in topo_js
    assert 'refX="22"' not in horiz_js
    assert 'filterUnits="userSpaceOnUse"' in topo_js
    assert 'filterUnits="userSpaceOnUse"' in horiz_js
    assert "buildArrowMarkerDefs" in topo_js
    assert "computeEdgeEndpoints" in topo_js
    assert "buildArrowMarkerDefs" in horiz_js
    assert "computeEdgeEndpoints" in horiz_js
    assert 'data-review-status' in topo_js
    assert 'data-review-status' in horiz_js
    assert "Review Pending" in ops_html
