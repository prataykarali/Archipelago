"""Phase D14.6 UX, Follow-Up Quality, 12-Domain Suggestions, Source Badges & Inspector tests.

Covers DEF-18 (suggestions.py 12-domain word-boundary classification) and
D14-DEF-053 through D14-DEF-062.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOST_INFERENCE = ROOT / "host_inference"
HOST_UI = HOST_INFERENCE / "ui"
CANON_UI = ROOT / "ui" / "chat"

if str(HOST_INFERENCE) not in sys.path:
    sys.path.insert(0, str(HOST_INFERENCE))

from engine.conversational import (  # noqa: E402
    build_unindexed_academic_fallback,
    build_unsupported_reply,
    discover_domain_coverage,
    strip_prior_context,
)
from engine.followups import (  # noqa: E402
    MAX_FALLBACK_FOLLOW_UPS,
    MAX_FOLLOW_UP_QUESTIONS,
    build_follow_up_questions,
)
from engine.suggestions import _KNOWLEDGE_AREA_SPECS, discover_knowledge_areas  # noqa: E402

pytestmark = pytest.mark.unit

NODE_TIMEOUT_SECONDS = 15
MIN_ANCHORED_FOLLOW_UPS = 3
EXPECTED_GRAPH_V2_DOMAIN_COUNT = 12

D14_6_SYNCED_FILES = (
    "js/01--hide-welcome-with-transitio.js", "js/02--kw-highlights.js",
    "js/03-wrap-library-inventory-secti.js", "js/04-start-new-chat.js",
    "js/11-populate-topology.js", "js/11a-topology-layout.js",
    "js/15-inspector.js", "js/16-render-personalized-graph-ca.js",
    "js/17-draw-personalized-svg.js", "js/19-draw-horizontal-svg.js",
    "js/23-followups-export.js", "styles/14-d12-ui-3d.css",
)


class _StubGraph:
    """Minimal graph stub for deterministic unit testing."""

    def __init__(self, nodes: dict[str, dict[str, Any]]) -> None:
        self.nodes = nodes


def _run_node_json(script: str) -> Any:
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


# ── 1. DEF-18: 12-domain word-boundary classification in suggestions.py ───────


def test_suggestions_align_with_12_graph_v2_domains_and_block_os_misclassification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DEF-18: 12 domains match graph_v2_d14; Chain-of-Thought & RNNs never classify under OS."""
    assert len(_KNOWLEDGE_AREA_SPECS) == EXPECTED_GRAPH_V2_DOMAIN_COUNT
    expected_labels = {
        "Operating Systems", "AI & Machine Learning", "Mathematics for Computing",
        "Probability & Statistics", "Data Structures & Algorithms", "Database Systems",
        "Computer Networks", "Compilers & Languages", "Automata & Computation",
        "Information Security", "Software Engineering", "Computer Architecture",
    }
    assert {label for _key, label, _pat in _KNOWLEDGE_AREA_SPECS} == expected_labels

    monkeypatch.setattr("engine.suggestions.load_d14_source_registry", dict)
    monkeypatch.setattr(
        "engine.suggestions.load_hf_paths",
        lambda: [
            "ostep_three_easy_pieces/08_Paging.pdf",
            "papers/Wei2022_ChainOfThought.pdf",
            "papers/Hochreiter1997_LSTM.pdf",
        ],
    )
    graph = _StubGraph(
        {
            "paging": {
                "label": "Paging",
                "summary": "Virtual memory paging divides address spaces into fixed-size pages.",
                "sources": [{"doc_id": "ostep_three_easy_pieces/08_Paging.pdf"}],
            },
            "chain_of_thought": {
                "label": "Chain-of-Thought Prompting",
                "summary": "A step-by-step reasoning process that unlocks LLM arithmetic reasoning.",
                "sources": [{"doc_id": "papers/Wei2022_ChainOfThought.pdf"}],
            },
            "rnn": {
                "label": "Recurrent Neural Networks (RNNs)",
                "summary": "Neural networks that process sequential inputs step by step.",
                "sources": [{"doc_id": "papers/Hochreiter1997_LSTM.pdf"}],
            },
            "rsa": {
                "label": "RSA Encryption",
                "summary": "Public-key cryptography using modular exponentiation.",
                "sources": [{"doc_id": "catalog_rsa.pdf"}],
            },
        }
    )

    areas = {a["key"]: a for a in discover_knowledge_areas(graph)}
    assert "os" in areas
    os_samples = " | ".join(areas["os"]["sample_concepts"]).lower()
    assert "paging" in os_samples
    assert "chain-of-thought" not in os_samples
    assert "recurrent neural" not in os_samples
    assert "rnn" not in os_samples

    assert "ai_ml" in areas
    ai_samples = " | ".join(areas["ai_ml"]["sample_concepts"]).lower()
    assert "chain-of-thought" in ai_samples
    assert "recurrent neural" in ai_samples

    coverage = discover_domain_coverage(graph)
    full_text_keys = {a["key"] for a in coverage["full_text"]}
    graph_only_keys = {a["key"] for a in coverage["graph_only"]}
    unavailable_keys = {a["key"] for a in coverage["unavailable"]}

    assert {"os", "ai_ml"} <= full_text_keys
    assert "security" in graph_only_keys
    assert "architecture" in unavailable_keys
    assert "software_eng" in unavailable_keys

    reply = build_unsupported_reply(graph, "Explain compiler register allocation", reason="corpus_coverage_gap")
    assert "Supported full-text domains" in reply
    assert "Graph-only domains" in reply
    assert "Unavailable domains" in reply


# ── 2. Follow-up relevance & cross-domain elimination (D14-DEF-053..059) ─────


def test_cross_domain_followups_eliminated_for_unanchored_academic_queries() -> None:
    """D14-DEF-053..058: Unanchored academic queries never pull unrelated ML/DB/graph pills."""
    graph = _StubGraph(
        {
            "feature_adaptation": {
                "label": "Feature Adaptation",
                "summary": "Transfer learning domain feature adaptation.",
                "sources": [{"doc_id": "papers/Hu2021_LoRA.pdf"}],
            },
            "forward_chaining": {
                "label": "Forward-Chaining",
                "summary": "Rule-based inference engine.",
                "sources": [{"doc_id": "papers/Wei2022_ChainOfThought.pdf"}],
            },
            "graph_laplacian": {
                "label": "Graph Laplacian",
                "summary": "Spectral graph theory matrix.",
                "sources": [{"doc_id": "papers/Kipf2016_GCN.pdf"}],
            },
            "random_forest": {
                "label": "Random Forest",
                "summary": "Ensemble decision trees with MAE metric.",
                "sources": [{"doc_id": "textbooks/Deisenroth_Math_For_ML.pdf"}],
            },
            "b_plus_tree": {
                "label": "B+ Tree",
                "summary": "Database indexing structure for SQL DBMS.",
                "sources": [{"doc_id": "textbooks/silberschatz_dbms.pdf"}],
            },
            "dpo": {
                "label": "Direct Preference Optimization",
                "summary": "LLM alignment without separate reward model.",
                "sources": [{"doc_id": "papers/Rafailov2023_DPO.pdf"}],
            },
        }
    )

    cases = (
        ("Explain RSA public-key encryption", ("feature adaptation",)),
        ("How does the TLS handshake work?", ("forward-chaining",)),
        ("Prove a language is non-regular using the pumping lemma", ("graph laplacian",)),
        ("Explain SOLID principles in software engineering", ("random forest", "mae")),
        ("Explain CPU pipelining and data hazards in computer architecture", ("b+ tree", "database")),
        ("How does a compiler build an intermediate representation?", ("dpo", "preference optimization")),
    )

    for query, banned_terms in cases:
        followups = build_follow_up_questions(
            graph,
            {"anchor_concept": None, "citations": []},
            query,
            "GENERAL_EXPLANATION",
            reason="academic_general_not_indexed",
        )
        assert len(followups) <= MAX_FALLBACK_FOLLOW_UPS
        joined = " | ".join(followups).lower()
        for banned in banned_terms:
            assert banned not in joined
        assert followups == []


def test_dpo_followups_block_misleading_rl_unavailable_docs_and_repetition() -> None:
    """D14-DEF-059: DPO never suggests RL as unlocked/prereq, skips unavailable docs, no repeats."""
    graph = _StubGraph(
        {
            "dpo": {
                "label": "Direct Preference Optimization",
                "summary": "Closed-form preference optimization for language models.",
                "sources": [{"doc_id": "papers/Rafailov2023_DPO.pdf"}],
            },
            "reinforcement_learning": {
                "label": "Reinforcement Learning",
                "summary": "Sequential decision making with rewards in machine learning.",
                "sources": [{"doc_id": "papers/Ouyang2022_InstructGPT.pdf"}],
            },
            "rlhf": {
                "label": "RLHF",
                "summary": "Reinforcement learning from human feedback for LLMs.",
                "sources": [{"doc_id": "papers/Ouyang2022_InstructGPT.pdf"}],
            },
            "transformer": {
                "label": "Transformer",
                "summary": "Self-attention sequence architecture for LLMs.",
                "sources": [{"doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf"}],
            },
        }
    )
    payload = {
        "anchor_concept": {"id": "dpo", "label": "Direct Preference Optimization"},
        "prerequisites": [{"id": "reinforcement_learning"}, {"id": "transformer"}],
        "unlocks": [{"id": "reinforcement_learning"}, {"id": "transformer"}],
        "related_concepts": [{"id": "rlhf"}],
        "citations": [
            {
                "doc_id": "tanenbaum_unavailable.pdf",
                "doc_title": "Unavailable Book",
                "source_kind": "unavailable_document",
                "evidence_backed": False,
                "text_passage": "Metadata stub only.",
            },
            {
                "doc_id": "meta_only_card.pdf",
                "doc_title": "Metadata Only Paper",
                "source_kind": "metadata_only_record",
                "metadata_only": True,
                "text_passage": "Catalog summary.",
            },
            {
                "doc_id": "papers/Rafailov2023_DPO.pdf",
                "doc_title": "Direct Preference Optimization",
                "source_kind": "verified_full_text_passage",
                "evidence_backed": True,
                "text_passage": "DPO optimizes the policy directly on preference pairs without training a separate reward model.",
            },
        ],
    }

    followups = build_follow_up_questions(
        graph,
        payload,
        "How does DPO work? (Earlier user topics: Operating Systems paging)",
        "GRAPH_SYNTHESIS",
    )
    assert MIN_ANCHORED_FOLLOW_UPS <= len(followups) <= MAX_FOLLOW_UP_QUESTIONS
    joined = " | ".join(followups).lower()
    assert "reinforcement learning" not in joined
    assert "unavailable book" not in joined
    assert "metadata only paper" not in joined
    assert "paging" not in joined
    assert sum("transformer" in f.lower() for f in followups) == 1
    assert any("direct preference optimization" in f.lower() for f in followups)


# ── 3. Fallback honesty (D14-DEF-060) ────────────────────────────────────────


def test_fallback_never_echoes_question_as_fake_general_explanation_or_leaks_prior_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D14-DEF-060: Distinguish genuine general explanation vs honest abstention; strip prior context."""
    monkeypatch.setattr("engine.suggestions.load_d14_source_registry", dict)
    monkeypatch.setattr(
        "engine.suggestions.load_hf_paths",
        lambda: ["ostep_three_easy_pieces/08_Paging.pdf"],
    )
    graph = _StubGraph(
        {
            "paging": {
                "label": "Paging",
                "summary": "Virtual memory page table translation in OSTEP.",
                "sources": [{"doc_id": "ostep_three_easy_pieces/08_Paging.pdf"}],
            }
        }
    )

    raw_query = (
        "Explain how branch target buffers prevent control hazards in superscalar pipelines "
        "(Earlier user topics: Graph Attention Networks; Bayes Theorem)"
    )
    assert "earlier user topics" not in strip_prior_context(raw_query).lower()

    route_abs, text_abs, meta_abs = build_unindexed_academic_fallback(
        graph, raw_query, allow_general_explanation=False, general_explanation_text=""
    )
    assert route_abs == "GUARDRAIL_INTERCEPT"
    assert meta_abs["fallback_mode"] == "abstention"
    assert meta_abs["evidence_backed"] is False
    assert meta_abs["hide_graph"] is True
    assert "general explanation" not in text_abs.lower()
    assert "cannot answer" in text_abs.lower()
    assert "graph attention networks" not in text_abs.lower()

    route_echo, text_echo, meta_echo = build_unindexed_academic_fallback(
        graph, "Explain RSA encryption", allow_general_explanation=True, general_explanation_text="Explain RSA encryption"
    )
    assert route_echo == "GUARDRAIL_INTERCEPT"
    assert meta_echo["fallback_mode"] == "abstention"
    assert "general explanation" not in text_echo.lower()

    route_gen, text_gen, meta_gen = build_unindexed_academic_fallback(
        graph,
        raw_query,
        allow_general_explanation=True,
        general_explanation_text=(
            "A branch target buffer caches predicted target addresses for branch instructions "
            "so the fetch stage can redirect early without waiting for branch resolution."
        ),
    )
    assert route_gen == "GENERAL_EXPLANATION"
    assert meta_gen["fallback_mode"] == "general_explanation"
    assert meta_gen["evidence_backed"] is False
    assert "general explanation (not grounded in the indexed corpus)" in text_gen.lower()


# ── 4. Unified 4-state source badge rendering & Inspector state (D14-DEF-062) ─


def test_unified_four_state_source_badges_never_render_clickable_open_source_for_non_readable() -> None:
    """metadata_only_record and unavailable_document never produce clickable Open source links."""
    kw_url = (HOST_UI / "js" / "02--kw-highlights.js").resolve().as_uri()
    insp_url = (HOST_UI / "js" / "15-inspector.js").resolve().as_uri()
    result = _run_node_json(
        f"""
        const stubEl = {{ addEventListener: () => {{}}, classList: {{ add() {{}}, remove() {{}}, toggle() {{}}, contains() {{ return false; }} }}, setAttribute() {{}}, style: {{}} }};
        globalThis.window = {{ addEventListener: () => {{}}, matchMedia: () => ({{ matches: false }}), location: {{ origin: 'http://localhost:5051', pathname: '/chat', search: '', hash: '' }} }};
        globalThis.document = {{
            getElementById: (id) => (id === 'chat-input' ? stubEl : null),
            querySelector: () => null,
            querySelectorAll: () => [],
            addEventListener: () => {{}},
            removeEventListener: () => {{}},
            documentElement: {{ dataset: {{}} }},
        }};
        globalThis.localStorage = {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }};
        globalThis.fetch = async () => ({{ json: async () => ({{}}) }});

        const {{ citationPageUrl, isNonReadableSourceKind, normalizeSourceKind }} = await import({json.dumps(kw_url)});
        const {{ _renderCitation }} = await import({json.dumps(insp_url)});

        const metaCite = {{ doc_id: 'papers/Vaswani2017_Attention_Is_All_You_Need.pdf', title: 'Attention', source_kind: 'metadata_only_record', url: '/read?doc=papers/Vaswani2017_Attention_Is_All_You_Need.pdf' }};
        const unavailCite = {{ doc_id: 'papers/Vaswani2017_Attention_Is_All_You_Need.pdf', title: 'Missing Book', source_kind: 'unavailable_document', url: '/read?doc=missing.pdf' }};
        const flagMetaCite = {{ doc_id: 'papers/Hu2021_LoRA.pdf', title: 'LoRA Meta', metadata_only: true }};
        const flagUnavailCite = {{ doc_id: 'papers/Hu2021_LoRA.pdf', title: 'LoRA Unavail', pdf_available: false }};
        const verifiedCite = {{ doc_id: 'papers/Vaswani2017_Attention_Is_All_You_Need.pdf', title: 'Attention', source_kind: 'verified_full_text_passage', page_number: 3 }};

        console.log(JSON.stringify({{
            metaUrl: citationPageUrl(metaCite), unavailUrl: citationPageUrl(unavailCite),
            flagMetaUrl: citationPageUrl(flagMetaCite), flagUnavailUrl: citationPageUrl(flagUnavailCite),
            verifiedUrl: citationPageUrl(verifiedCite), metaKind: normalizeSourceKind(flagMetaCite),
            unavailKind: normalizeSourceKind(flagUnavailCite), metaNonRead: isNonReadableSourceKind(flagMetaCite),
            metaHtml: _renderCitation(metaCite, 0), unavailHtml: _renderCitation(unavailCite, 1),
            verifiedHtml: _renderCitation(verifiedCite, 2),
        }}));
        process.exit(0);
        """
    )

    assert result["metaUrl"] == ""
    assert result["unavailUrl"] == ""
    assert result["flagMetaUrl"] == ""
    assert result["flagUnavailUrl"] == ""
    assert "/read?doc=" in result["verifiedUrl"]
    assert result["metaKind"] == "metadata_only_record"
    assert result["unavailKind"] == "unavailable_document"
    assert result["metaNonRead"] is True
    assert "<a " not in result["metaHtml"]
    assert "<a " not in result["unavailHtml"]
    assert "Metadata-Only Record" in result["metaHtml"]
    assert "Unavailable Document" in result["unavailHtml"]
    assert "Open Page in Reader" in result["verifiedHtml"]


def test_inspector_stale_state_clears_on_fallback_and_new_turn() -> None:
    """D14-DEF-062: populateTopology(null) clears stale graph, evidence, and trace DOM."""
    mod_url = (HOST_UI / "js" / "11-populate-topology.js").resolve().as_uri()
    result = _run_node_json(
        f"""
        const elements = {{}};
        const makeEl = (id, initialText = '', initialHtml = '') => ({{
            id, textContent: initialText, innerHTML: initialHtml, style: {{}},
            classList: {{
                _set: new Set(),
                add(...c) {{ c.forEach(x => this._set.add(x)); }},
                remove(...c) {{ c.forEach(x => this._set.delete(x)); }},
                contains(c) {{ return this._set.has(c); }},
            }},
            addEventListener() {{}}, setAttribute() {{}},
        }});
        for (const [id, txt, html] of [
            ['sidebar-svg-map', '', '<path data-from="old"/>'], ['bottom-svg-map', '', '<circle/>'],
            ['graph-node-title', 'Stale Previous Concept', ''], ['graph-node-summary', 'Old summary from turn 1', ''],
            ['graph-node-type', 'Anchor', ''], ['graph-node-diff', 'Hard', ''],
            ['okf-rel-requires', '', '<span>Stale Prereq</span>'], ['okf-rel-unlocks', '', '<span>Stale Unlock</span>'],
            ['okf-rel-connects', '', '<span>Stale Related</span>'], ['citations-list', '', '<div>Stale Cite</div>'],
            ['citations-placeholder', '', ''], ['logs-list', '', '<div>Stale Log</div>'],
            ['logs-placeholder', '', ''], ['evidence-list', '', '<div>Stale Evidence</div>'],
            ['trace-content', '', '<div>Stale Trace</div>'], ['topology-placeholder', '', ''],
            ['topology-view', '', ''], ['bottom-svg-map-container', '', ''], ['chat-input', '', ''],
        ]) elements[id] = makeEl(id, txt, html);

        globalThis.window = {{ addEventListener: () => {{}}, matchMedia: () => ({{ matches: false }}), location: {{ origin: 'http://localhost:5051', pathname: '/chat', search: '', hash: '' }} }};
        globalThis.document = {{
            getElementById: (id) => elements[id] || null, querySelector: () => null,
            querySelectorAll: () => [], createElement: () => makeEl('tmp'),
            addEventListener: () => {{}}, removeEventListener: () => {{}}, documentElement: {{ dataset: {{}} }},
        }};
        globalThis.localStorage = {{ getItem: () => null, setItem: () => {{}}, removeItem: () => {{}} }};
        globalThis.fetch = async () => ({{ json: async () => ({{}}) }});

        const {{ populateTopology }} = await import({json.dumps(mod_url)});
        populateTopology(null, [], [], [], true);
        console.log(JSON.stringify({{
            sidebarSvg: elements['sidebar-svg-map'].innerHTML, bottomSvg: elements['bottom-svg-map'].innerHTML,
            nodeTitle: elements['graph-node-title'].textContent, nodeSummary: elements['graph-node-summary'].textContent,
            requiresHtml: elements['okf-rel-requires'].innerHTML, citationsHtml: elements['citations-list'].innerHTML,
            evidenceHtml: elements['evidence-list'].innerHTML, traceHtml: elements['trace-content'].innerHTML,
            viewHidden: elements['topology-view'].classList.contains('hidden'), neighborhood: globalThis.window._graphNeighborhood,
        }}));
        process.exit(0);
        """
    )

    assert result["sidebarSvg"] == ""
    assert result["bottomSvg"] == ""
    assert "Stale" not in result["nodeTitle"]
    assert "Old summary" not in result["nodeSummary"]
    assert "Stale Prereq" not in result["requiresHtml"]
    assert result["citationsHtml"] == ""
    assert result["evidenceHtml"] == ""
    assert result["traceHtml"] == ""
    assert result["viewHidden"] is True
    assert result["neighborhood"]["anchor"] is None


def test_d14_6_ui_mirrors_avatar_legend_and_reduced_motion_contracts() -> None:
    """All D14.6 UI files stay byte-for-byte synced and preserve identity + edge legends."""
    for rel_path in D14_6_SYNCED_FILES:
        hosted = HOST_UI / rel_path
        canonical = CANON_UI / rel_path
        assert hosted.is_file(), f"Missing {rel_path}"
        assert canonical.is_file(), f"Missing mirror {rel_path}"
        assert hosted.read_bytes() == canonical.read_bytes(), f"Mirror drift in {rel_path}"

    new_chat_js = (HOST_UI / "js" / "04-start-new-chat.js").read_text(encoding="utf-8")
    assert "welcome-avatar-stack" in new_chat_js
    assert "AI Librarian" in new_chat_js

    layout_js = (HOST_UI / "js" / "11a-topology-layout.js").read_text(encoding="utf-8")
    horiz_js = (HOST_UI / "js" / "19-draw-horizontal-svg.js").read_text(encoding="utf-8")
    assert "sidebar-graph-legend" in layout_js
    assert "RELATED_TO" in layout_js
    assert "data-relation" in horiz_js
    assert "graph-edge-legend" in horiz_js
    assert "RELATED_TO" in horiz_js

    css_3d = (HOST_UI / "styles" / "14-d12-ui-3d.css").read_text(encoding="utf-8")
    assert "8.25rem" in css_3d
    assert "6.75rem" in css_3d
    assert ".katex-display" in css_3d
    assert "prefers-reduced-motion: reduce" in css_3d
    assert "overflow-anchor: auto" in css_3d
