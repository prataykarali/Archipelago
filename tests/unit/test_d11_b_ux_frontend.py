"""D11-B-UX Frontend contract and runtime unit tests."""

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

SYNCED_FILES = (
    "auth_bridge.js",
    "index.html",
    "chromatic_waves.js",
    "styles/13-d11-b-ux-readability.css",
    "js/03-wrap-library-inventory-secti.js",
    "js/04-start-new-chat.js",
    "js/05-display-books.js",
    "js/07-open-page-viewer-modal.js",
    "js/08-send-message.js",
    "js/08-stream-cleanup.js",
    "js/11-populate-topology.js",
    "js/11a-topology-layout.js",
    "js/22-welcome-suggestions.js",
    "js/23-followups-export.js",
    "js/expose.js",
    "js/index.js",
)

MAX_FOLLOW_UPS = 5
MIN_SUGGESTIONS = 4
MAX_SUGGESTIONS = 5
NODE_TIMEOUT_SECONDS = 15


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


def test_ui_chat_and_host_inference_ui_byte_for_byte_synced() -> None:
    """Every D11-B-UX UI asset and auth_bridge.js must stay byte-for-byte synced."""
    for rel_path in SYNCED_FILES:
        hosted = HOST_UI / rel_path
        canonical = CANON_UI / rel_path
        assert hosted.is_file(), f"Missing hosted UI file: {rel_path}"
        assert canonical.is_file(), f"Missing canonical ui/chat file: {rel_path}"
        assert hosted.read_bytes() == canonical.read_bytes(), f"Drift detected in {rel_path}"


def test_welcome_suggestions_normalization_shuffle_and_open_access_profile() -> None:
    """Welcome suggestions normalize backend payloads, shuffle 4-5 items, and detect open-access."""
    mod_url = (HOST_UI / "js" / "22-welcome-suggestions.js").resolve().as_uri()
    result = _run_node_json(
        f"""
        import {{
            normalizeSuggestionsPayload,
            pickShuffledQuestions,
            isOpenAccessProfile,
        }} from {json.dumps(mod_url)};

        const openPayload = {{
            access_profile: "open_access",
            open_access_only: true,
            knowledge_areas: [
                {{ index: 1, key: "os", label: "Operating Systems", concept_count: 14 }},
                {{ index: 2, key: "db", label: "Databases", concept_count: 11 }},
            ],
            suggested_questions: [
                "How does paging work in OSTEP?",
                "How do I access Pearson eLibrary textbooks?",
                "Compare B-Trees and LSM-Trees.",
                "Explain base-and-bounds translation.",
                "How does Linux CFS schedule tasks?",
                "Explain RAG retrieval pipelines.",
            ],
        }};
        const normOpen = normalizeSuggestionsPayload(openPayload);
        const normFallback = normalizeSuggestionsPayload({{}});
        const firstPick = pickShuffledQuestions(normFallback.questions, 5, []);
        const secondPick = pickShuffledQuestions(normFallback.questions, 5, firstPick);

        console.log(JSON.stringify({{
            normOpen,
            normFallbackCount: normFallback.questions.length,
            firstPick,
            secondPick,
            isOpenTrue: isOpenAccessProfile(openPayload),
            isOpenInstitutional: isOpenAccessProfile({{ access_profile: "institutional", open_access_only: false }}),
            isOpenEmpty: isOpenAccessProfile({{}}),
        }}));
        """
    )
    assert result["isOpenTrue"] is True
    assert result["isOpenInstitutional"] is False
    assert result["isOpenEmpty"] is False
    assert result["normOpen"]["areas"] == ["Operating Systems (14)", "Databases (11)"]
    assert all("pearson" not in q.lower() for q in result["normOpen"]["questions"])
    assert MIN_SUGGESTIONS <= len(result["firstPick"]) <= MAX_SUGGESTIONS
    assert MIN_SUGGESTIONS <= len(result["secondPick"]) <= MAX_SUGGESTIONS
    assert len(set(result["firstPick"])) == len(result["firstPick"])
    assert set(result["firstPick"]) != set(result["secondPick"])


def test_followup_chips_limit_and_no_auto_execution() -> None:
    """Follow-up chips cap at 5 unique strings and only execute on explicit click."""
    mod_url = (HOST_UI / "js" / "23-followups-export.js").resolve().as_uri()
    result = _run_node_json(
        f"""
        import {{ extractFollowUpQuestions }} from {json.dumps(mod_url)};
        const qs = extractFollowUpQuestions({{
            follow_up_questions: [
                "How do TLBs speed up paging?",
                "How do TLBs speed up paging?",
                "What is a page fault?",
                "How do multi-level page tables save RAM?",
                "Compare segmentation and paging.",
                "How does copy-on-write fork work?",
                "Seventh question should be trimmed.",
            ],
        }});
        console.log(JSON.stringify({{ qs }}));
        """
    )
    assert len(result["qs"]) == MAX_FOLLOW_UPS
    assert "Seventh question should be trimmed." not in result["qs"]

    src = (HOST_UI / "js" / "23-followups-export.js").read_text(encoding="utf-8")
    assert "addEventListener('click'" in src
    assert "verified edge" not in src.lower()


def test_evidence_export_strips_all_credentials_and_formats_markdown() -> None:
    """Evidence export includes answer/citations/passages/edges/trace and strips secrets."""
    mod_url = (HOST_UI / "js" / "23-followups-export.js").resolve().as_uri()
    result = _run_node_json(
        f"""
        import {{
            buildSanitizedEvidenceBundle,
            formatEvidenceMarkdown,
        }} from {json.dumps(mod_url)};

        const bundle = buildSanitizedEvidenceBundle({{
            query: "Explain paging in OSTEP",
            answerText: "Paging divides virtual memory into fixed-size pages.",
            metadata: {{
                anchor_concept: {{ id: "paging", label: "Paging" }},
                prerequisites: [{{ id: "virtual_memory", label: "Virtual Memory" }}],
                unlocks: [{{ id: "tlb", label: "TLB" }}],
                citations: [
                    {{
                        title: "OSTEP Paging",
                        doc_id: "ostep/18_Paging.pdf",
                        passage_id: "ostep:p1:c0",
                        page_number: 1,
                        snippet: "Paging splits address space into fixed units.",
                        auth_token: "secret-should-drop",
                    }},
                ],
                trace: {{
                    route: "CONCEPT_GRAPH",
                    passage_ids: ["ostep:p1:c0"],
                    cookie: "sb-session=supersecret",
                    authorization: "Bearer abc.def.ghi",
                    session_id: "sess_private_123",
                    nested_note: "Header Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTYifQ.sigvalue",
                }},
            }},
        }});
        const md = formatEvidenceMarkdown(bundle);
        console.log(JSON.stringify({{ bundle, md }}));
        """
    )
    bundle = result["bundle"]
    serialized = json.dumps(bundle) + "\n" + result["md"]
    assert bundle["query"] == "Explain paging in OSTEP"
    assert "ostep:p1:c0" in bundle["passage_ids"]
    assert len(bundle["graph_edges"]) == 2
    req_edge = next(e for e in bundle["graph_edges"] if e["relation"] == "REQUIRES")
    assert req_edge["source"] == "paging"
    assert req_edge["target"] == "virtual_memory"
    assert "Paging --[REQUIRES]--> Virtual Memory" in result["md"]
    assert bundle["execution_trace"]["route"] == "CONCEPT_GRAPH"
    assert "## Citations" in result["md"]
    assert "## Graph Edges" in result["md"]
    for forbidden in (
        "secret-should-drop",
        "sb-session=supersecret",
        "abc.def.ghi",
        "sess_private_123",
        "eyJhbGciOiJIUzI1NiJ9",
    ):
        assert forbidden not in serialized


def test_topology_deduplicates_canonical_nodes_and_avoids_label_overlap() -> None:
    """Duplicate canonical concept IDs merge into one node with multi-relation edges and non-overlapping labels."""
    mod_url = (HOST_UI / "js" / "11a-topology-layout.js").resolve().as_uri()
    result = _run_node_json(
        f"""
        import {{
            buildDeduplicatedTopology,
            resolveLabelPositions,
        }} from {json.dumps(mod_url)};

        const topo = buildDeduplicatedTopology({{
            anchor: {{ id: "paging", label: "Paging" }},
            prereqs: [
                {{ id: "address_translation", label: "Address Translation" }},
                {{ id: "virtual_memory", label: "Virtual Memory" }},
            ],
            unlocks: [
                {{ id: "Address Translation", label: "Address Translation" }},
                {{ id: "tlb", label: "TLB" }},
            ],
            related: [
                {{ id: "address-translation", label: "Address Translation" }},
                {{ id: "segmentation", label: "Segmentation" }},
            ],
            width: 300,
            height: 160,
            large: false,
        }});

        const specs = topo.nodes.map((n) => ({{
            id: n.canonicalId,
            x: n.x,
            y: n.y,
            radius: n.type === "anchor" ? 14 : 10,
            textWidth: n.label.length * 6,
        }}));
        const placed = resolveLabelPositions(specs, 300, 160);
        console.log(JSON.stringify({{
            nodeIds: topo.nodes.map((n) => n.canonicalId),
            addrRelations: topo.nodes.find((n) => n.canonicalId === "address_translation")?.relations || [],
            edgeCount: topo.edges.length,
            placed,
        }}));
        """
    )
    node_ids = result["nodeIds"]
    assert len(node_ids) == len(set(node_ids)), "Duplicate canonical nodes must be merged"
    assert node_ids.count("address_translation") == 1
    assert set(result["addrRelations"]) == {"prereq", "unlock", "related"}
    assert result["edgeCount"] >= 6

    placed = result["placed"]
    for idx, a in enumerate(placed):
        for b in placed[idx + 1 :]:
            ax1, ax2 = a["labelX"] - a["textWidth"] / 2, a["labelX"] + a["textWidth"] / 2
            bx1, bx2 = b["labelX"] - b["textWidth"] / 2, b["labelX"] + b["textWidth"] / 2
            ay1, ay2 = a["labelY"] - 11, a["labelY"] + 3
            by1, by2 = b["labelY"] - 11, b["labelY"] + 3
            overlaps = not (ax2 < bx1 or ax1 > bx2 or ay2 < by1 or ay1 > by2)
            assert not overlaps, f"Overlapping graph labels detected between {a['id']} and {b['id']}"


def test_never_stuck_stop_button_and_readability_contracts() -> None:
    """Stop button safeguards, readability CSS, reduced-motion, and open-access CSS are wired."""
    modal_js = (HOST_UI / "js" / "07-open-page-viewer-modal.js").read_text(encoding="utf-8")
    cleanup_js = (HOST_UI / "js" / "08-stream-cleanup.js").read_text(encoding="utf-8")
    send_js = (HOST_UI / "js" / "08-send-message.js").read_text(encoding="utf-8")
    css = (HOST_UI / "styles" / "13-d11-b-ux-readability.css").read_text(encoding="utf-8")
    index_html = (HOST_UI / "index.html").read_text(encoding="utf-8")
    waves_js = (HOST_UI / "chromatic_waves.js").read_text(encoding="utf-8")

    # Never-stuck Stop button contracts
    assert "btn.dataset.sendState = 'stop'" in modal_js
    assert "btn.dataset.sendState = 'send'" in modal_js
    assert "state.activeStreamReader" in modal_js
    assert "state.activeTypewriter" in modal_js
    assert "isStopVisual" in modal_js
    assert "typewriter.stop()" in cleanup_js
    assert "setSendButtonState('send')" in cleanup_js
    assert "renderFollowUpChips" in send_js
    assert "renderEvidenceExportBar" in send_js

    # Readability, reduced motion, compact avatar, welcome card & open-access profile
    assert "13-d11-b-ux-readability.css" in index_html
    assert 'id="welcome-suggestions-card"' in index_html
    assert "prefers-reduced-motion: reduce" in css
    assert "prefers-reduced-motion: reduce" in waves_js
    assert 'html[data-corpus-profile="open_access"] [data-type-filter="library_pearson"]' in css
    assert "#sticky-avatar-dock .avatar-shell" in css
    assert "2.125rem" in css
