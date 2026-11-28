"""Unit tests for Phase D14.2 OKF Graph Reconstruction & Semantic Validation."""

from __future__ import annotations

import csv
from hashlib import sha256
import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT / "host_inference") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "host_inference"))

from engine.graph import LibraryGraph  # noqa: E402

from okf.graph.d14_concept_resolver import ConceptResolver  # noqa: E402
from okf.graph.d14_curation_nodes import DUPLICATE_MERGES, REMOVED_ARTIFACT_IDS  # noqa: E402
from okf.graph.d14_reconstruct import (  # noqa: E402
    PLACEHOLDER_PATTERN,
    find_strongly_connected_components,
)
from okf.graph.d14_schema import (  # noqa: E402
    ACADEMIC_DOMAINS,
    ENV_GRAPH_PATH,
    ENV_GRAPH_VERSION,
    GRAPH_V1_FILENAME,
    GRAPH_V1_ID,
    GRAPH_V1_SHA256,
    GRAPH_V2_FILENAME,
    GRAPH_V2_ID,
    REL_CONTRASTS_WITH,
    REL_ENABLES,
    REL_RELATED_TO,
    REL_REQUIRES,
    REL_USES,
    REVIEW_HUMAN_VERIFIED,
    REVIEW_PENDING,
    VALID_REVIEW_STATUSES,
    VALID_TYPED_RELATIONS,
)

FIXTURES_DIR = REPO_ROOT / "host_inference" / "fixtures"
REPORTS_DIR = REPO_ROOT / "docs" / "reports" / "d14"
V1_PATH = FIXTURES_DIR / GRAPH_V1_FILENAME
V2_PATH = FIXTURES_DIR / GRAPH_V2_FILENAME

V1_EXPECTED_CONCEPTS = 610
V1_EXPECTED_EDGES = 1988


@pytest.fixture(scope="module")
def graph_v2_data() -> dict:
    """Load the emitted versioned graph_v2_d14 JSON artifact."""
    return json.loads(V2_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def resolver_v2(graph_v2_data: dict) -> ConceptResolver:
    """Instantiate ConceptResolver over graph_v2_d14."""
    return ConceptResolver(graph_v2_data)


@pytest.mark.unit
def test_graph_v1_baseline_untouched() -> None:
    """graph_v1_okf610 must remain byte-identical to its frozen SHA-256 anchor."""
    raw_bytes = V1_PATH.read_bytes()
    assert sha256(raw_bytes).hexdigest() == GRAPH_V1_SHA256
    data = json.loads(raw_bytes.decode("utf-8"))
    assert len(data["nodes"]) == V1_EXPECTED_CONCEPTS
    assert len(data["edges"]) == V1_EXPECTED_EDGES


@pytest.mark.unit
def test_version_selection_via_env_preserves_v1_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """LibraryGraph defaults to v1 and cleanly switches to v2 via env without code edits."""
    monkeypatch.delenv(ENV_GRAPH_PATH, raising=False)
    monkeypatch.delenv(ENV_GRAPH_VERSION, raising=False)
    g_default = LibraryGraph(V1_PATH)
    assert g_default.graph_artifact_version == GRAPH_V1_ID
    assert len(g_default.nodes) == V1_EXPECTED_CONCEPTS

    monkeypatch.setenv(ENV_GRAPH_VERSION, GRAPH_V2_ID)
    g_v2_env = LibraryGraph(V1_PATH)
    assert g_v2_env.graph_artifact_version == GRAPH_V2_ID
    assert "singular_value_decomposition" in g_v2_env.nodes

    monkeypatch.delenv(ENV_GRAPH_VERSION, raising=False)
    monkeypatch.setenv(ENV_GRAPH_PATH, str(V2_PATH))
    g_v2_path = LibraryGraph(V1_PATH)
    assert g_v2_path.graph_artifact_version == GRAPH_V2_ID


@pytest.mark.unit
def test_requires_and_combined_prerequisite_dag_acyclic(graph_v2_data: dict) -> None:
    """Zero cycles in hard REQUIRES edges and combined REQUIRES + inv(ENABLES) subgraph."""
    req_adj: dict[str, set[str]] = {}
    comb_adj: dict[str, set[str]] = {}
    for edge in graph_v2_data["edges"]:
        src, dst, rel = edge["from_id"], edge["to_id"], edge["relation"]
        assert src != dst, f"Self-loop found on {src}"
        if rel == REL_REQUIRES:
            req_adj.setdefault(src, set()).add(dst)
            comb_adj.setdefault(src, set()).add(dst)
        elif rel == REL_ENABLES:
            comb_adj.setdefault(dst, set()).add(src)
    assert find_strongly_connected_components(req_adj) == []
    assert find_strongly_connected_components(comb_adj) == []


@pytest.mark.unit
def test_typed_edge_validity_and_related_never_prerequisite(graph_v2_data: dict) -> None:
    """All edges use the 6 canonical typed relations and RELATED_TO is never a prerequisite."""
    for edge in graph_v2_data["edges"]:
        assert edge["relation"] in VALID_TYPED_RELATIONS
        assert edge["edge_type"] == edge["relation"]
        assert edge["review_status"] in VALID_REVIEW_STATUSES
        assert edge["review_status"] != REVIEW_HUMAN_VERIFIED
        assert edge["review_status"] == REVIEW_PENDING
        assert str(edge.get("source") or "").strip()

    lib = LibraryGraph(V2_PATH)
    # PagedAttention USES paging & RELATED_TO virtual_memory -> neither should appear in prereqs
    pa_prereqs = set(lib.prereqs("paged_attention", k=2))
    assert "paging" not in pa_prereqs
    assert "virtual_memory" not in pa_prereqs
    assert "paging" in lib.related("paged_attention", limit=10)
    # Clustered index USES b_plus_tree -> NOT mandatory prerequisite
    assert "b_plus_tree" not in set(lib.prereqs("clustered_index", k=1))
    assert "b_plus_tree" in lib.related("clustered_index", limit=10)


@pytest.mark.unit
def test_invalid_defect_edges_removed_or_corrected(graph_v2_data: dict) -> None:
    """All 9 invalid defect edges (D14-DEF-010..018) are fixed and interdisciplinary bridge kept."""
    edge_set = {(e["from_id"], e["to_id"], e["relation"]) for e in graph_v2_data["edges"]}
    edge_pairs = {(e["from_id"], e["to_id"]) for e in graph_v2_data["edges"]}

    # D14-DEF-010: Neural Network must not be a prerequisite of MLE
    lib = LibraryGraph(V2_PATH)
    assert "neural_network" not in set(lib.prereqs("maximum_likelihood_estimation", k=3))
    assert ("probability_distribution", "neural_network", REL_REQUIRES) not in edge_set

    # D14-DEF-011: DPO must not unlock RL; contrasts with RL/RLHF instead
    assert ("direct_preference_optimization", "reinforcement_learning", REL_ENABLES) not in edge_set
    assert (
        "direct_preference_optimization",
        "reinforcement_learning",
        REL_CONTRASTS_WITH,
    ) in edge_set

    # D14-DEF-012: Attention Mechanism requires Neural Network (not inverted)
    assert ("attention_mechanism", "neural_network", REL_ENABLES) not in edge_set
    assert ("neural_network", "attention_mechanism", REL_REQUIRES) not in edge_set
    assert ("attention_mechanism", "neural_network", REL_REQUIRES) in edge_set

    # D14-DEF-013: DFA / Regex -> Autonomous System removed
    assert ("deterministic_finite_automaton", "autonomous_system") not in edge_pairs
    assert ("regular_expression", "autonomous_system") not in edge_pairs

    # D14-DEF-014, 015, 018: Cross-domain contamination edges removed
    assert ("probability", "inheritance_hierarchy") not in edge_pairs
    assert ("web_traffic", "principal_component_analysis") not in edge_pairs
    assert ("principal_component_analysis", "web_traffic") not in edge_pairs
    assert ("tcp", "constitutional_principle") not in edge_pairs

    # D14-DEF-016: OSI layer direction corrected (Bit Transmission precedes Data Link Layer)
    assert ("bit_transmission", "data_link_layer", REL_REQUIRES) not in edge_set
    assert ("bit_transmission", "packet_switching", REL_REQUIRES) not in edge_set
    assert ("data_link_layer", "bit_transmission", REL_REQUIRES) in edge_set

    # D14-DEF-017: Clustered index USES B+ tree (not mandatory ENABLES/REQUIRES)
    assert ("b_plus_tree", "clustered_index", REL_ENABLES) not in edge_set
    assert ("clustered_index", "b_plus_tree", REL_USES) in edge_set

    # Interdisciplinary bridge preserved accurately
    assert ("paged_attention", "paging", REL_USES) in edge_set
    assert ("paged_attention", "virtual_memory", REL_RELATED_TO) in edge_set


@pytest.mark.unit
def test_zero_placeholders_empties_artifacts_and_duplicates(graph_v2_data: dict) -> None:
    """Zero placeholder summaries, empty summaries, malformed artifacts, or merged duplicates."""
    node_ids = {n["id"] for n in graph_v2_data["nodes"]}
    for artifact_id in REMOVED_ARTIFACT_IDS:
        assert artifact_id not in node_ids
    for dup_id in DUPLICATE_MERGES:
        assert dup_id not in node_ids
    for node in graph_v2_data["nodes"]:
        summary = str(node.get("summary") or "").strip()
        assert summary, f"Empty summary on {node['id']}"
        assert not PLACEHOLDER_PATTERN.search(summary), f"Placeholder summary on {node['id']}"

    domains_present = {str(n.get("domain") or "") for n in graph_v2_data["nodes"]}
    for domain in ACADEMIC_DOMAINS:
        assert domain in domains_present, f"Missing academic domain: {domain}"


@pytest.mark.unit
@pytest.mark.parametrize(
    ("query", "expected_primary"),
    [
        (
            "Explain Singular Value Decomposition (SVD) in linear algebra",
            "singular_value_decomposition",
        ),
        ("How do Graph Attention Networks (GAT) compute attention?", "graph_attention_network"),
        ("Explain LALR bottom-up parsing in syntax analysis", "lalr"),
        (
            "How do Denoising Diffusion Probabilistic Models (DDPM) work?",
            "denoising_diffusion_probabilistic_models",
        ),
        ("How does RSA encryption use modular arithmetic?", "rsa_cryptosystem"),
        ("Explain the TLS handshake over TCP", "tls_protocol"),
        ("How is the pumping lemma used for regular languages?", "pumping_lemma"),
        ("Explain SOLID principles in software engineering", "solid_principles"),
        ("How do pipeline hazards affect CPU instruction pipelining?", "pipeline_hazards"),
    ],
)
def test_alias_specificity_and_coverage_resolution(
    resolver_v2: ConceptResolver, query: str, expected_primary: str
) -> None:
    """Specific target concepts outrank broad parents and resolve abbreviations cleanly."""
    res = resolver_v2.resolve_query(query)
    assert res.primary is not None
    assert res.primary.cid == expected_primary


@pytest.mark.unit
def test_multi_concept_resolution_and_connecting_subgraph(resolver_v2: ConceptResolver) -> None:
    """Multi-concept queries capture all queried concepts and their connecting typed subgraph."""
    res_prob = resolver_v2.resolve_query(
        "Explain KL divergence and variational inference in probability"
    )
    anchor_ids = {a.cid for a in res_prob.anchors}
    assert {"kl_divergence", "variational_inference"}.issubset(anchor_ids)
    assert any(
        e["from_id"] == "variational_inference" and e["to_id"] == "kl_divergence"
        for e in res_prob.connecting_edges
    )

    res_os = resolver_v2.resolve_query("How do paging, page tables, and TLB work together?")
    os_ids = {a.cid for a in res_os.anchors}
    assert {"paging", "page_table", "translation_lookaside_buffer"}.issubset(os_ids)
    assert len(res_os.connecting_edges) >= 2

    res_aut = resolver_v2.resolve_query("Compare DFA, context-free grammar, and Turing machine")
    aut_ids = {a.cid for a in res_aut.anchors}
    assert {"deterministic_finite_automaton", "context_free_grammar", "turing_machine"}.issubset(
        aut_ids
    )


@pytest.mark.unit
def test_d14_report_artifacts_present_and_consistent(graph_v2_data: dict) -> None:
    """All 5 D14.2 report artifacts exist and match the emitted graph_v2_d14 checksum."""
    manifest = json.loads((REPORTS_DIR / "D14_GRAPH_V2_MANIFEST.json").read_text(encoding="utf-8"))
    changelog = json.loads((REPORTS_DIR / "D14_GRAPH_CHANGELOG.json").read_text(encoding="utf-8"))
    audit_md = (REPORTS_DIR / "D14_GRAPH_SEMANTIC_AUDIT.md").read_text(encoding="utf-8")

    actual_v2_sha = sha256(V2_PATH.read_bytes()).hexdigest()
    assert manifest["graph_sha256"] == actual_v2_sha
    assert manifest["parent_graph_sha256"] == GRAPH_V1_SHA256
    assert changelog["output_graph_sha256"] == actual_v2_sha
    assert manifest["invariants"]["requires_dag_cycles"] == 0
    assert manifest["invariants"]["auto_promoted_human_verified_edges"] == 0
    assert GRAPH_V2_ID in audit_md

    with (REPORTS_DIR / "D14_CONCEPT_ALIAS_REGISTER.csv").open(encoding="utf-8") as handle:
        alias_rows = list(csv.DictReader(handle))
    assert len(alias_rows) >= len(graph_v2_data["nodes"])

    with (REPORTS_DIR / "D14_EDGE_PROVENANCE.csv").open(encoding="utf-8") as handle:
        prov_rows = list(csv.DictReader(handle))
    assert len(prov_rows) == len(graph_v2_data["edges"])
    assert all(row["review_status"] == REVIEW_PENDING for row in prov_rows)
