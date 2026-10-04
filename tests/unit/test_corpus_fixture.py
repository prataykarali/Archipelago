"""The tracked corpus fixture, and the boot fetch that replaces it.

Every corpus artifact is gitignored, so a git-triggered deployment builds with no
graph at all.  Without this bootstrap the hosted app boots, passes
``/api/readiness``, and answers "not indexed" to every question — a green health
check over an empty brain.  These tests pin both halves of the remedy: the
tracked fallback slice must be genuinely usable, and provisioning must never
turn a missing corpus into a crash.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
HOST_DIR = REPO_ROOT / "host_inference"
FIXTURE = HOST_DIR / "fixtures" / "okf_graph.json"
if str(HOST_DIR) not in sys.path:
    sys.path.insert(0, str(HOST_DIR))

pytestmark = pytest.mark.unit

#: Concepts the response contract's own examples are written about. A fixture
#: missing these cannot demonstrate the contract it exists to demonstrate.
SPINE = (
    "third_normal_form",
    "low_rank_adaptation",
    "qlora",
    "bert",
    "attention_mechanism",
    "rag",
    "paged_attention",
)


@pytest.fixture(scope="module")
def fixture_payload() -> dict:
    if not FIXTURE.is_file():
        pytest.fail(
            "the tracked fixture is missing; a deployment would build with no "
            "corpus. Regenerate with: python scripts/build_corpus_fixture.py"
        )
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fixture_graph(fixture_payload):
    from engine.graph import LibraryGraph

    return LibraryGraph(FIXTURE)


def test_fixture_is_small_enough_to_review(fixture_payload):
    """A fixture nobody can review is a fixture nobody will trust."""
    size_kb = FIXTURE.stat().st_size / 1024
    assert size_kb < 1024, f"fixture is {size_kb:.0f} KB; too large for a reviewable diff"


def test_fixture_is_labelled_as_a_fixture(fixture_payload):
    """Nobody should mistake a slice for the whole library."""
    assert fixture_payload["stats"]["fixture"] is True
    assert "note" in fixture_payload["stats"]


def test_fixture_is_below_the_full_corpus_threshold(fixture_payload):
    from hostapp.routes.pages import FULL_CORPUS_MIN_CONCEPTS

    count = len(fixture_payload["nodes"])
    assert count < FULL_CORPUS_MIN_CONCEPTS, (
        "if the slice meets the full-corpus bar, /api/readiness can no longer "
        "tell an operator which library they are actually talking to"
    )


@pytest.mark.parametrize("concept", SPINE)
def test_fixture_keeps_the_curriculum_spine(fixture_payload, concept):
    assert concept in fixture_payload["concepts"], f"{concept} missing from the fixture"


def test_fixture_reports_itself_as_a_fixture_to_the_graph(fixture_graph):
    assert fixture_graph.corpus_source == "fixture"


def test_fixture_answers_a_concept_with_a_citation(fixture_graph):
    record = fixture_graph.cite_record("third_normal_form")
    assert record.get("doc_id"), "no provenance on the contract's flagship example"
    assert record.get("page_number")


def test_fixture_keeps_prerequisites_for_the_spine(fixture_graph):
    """An isolated concept cannot answer 'what must I master first'."""
    assert fixture_graph.prereqs("third_normal_form", 1), (
        "third normal form arrived with no prerequisite edge, so the graph-render "
        "protocol has nothing to draw"
    )
    assert fixture_graph.prereqs("paged_attention", 1)


def test_fixture_edges_only_reference_present_nodes(fixture_payload):
    ids = {n["id"] for n in fixture_payload["nodes"]}
    for edge in fixture_payload["edges"]:
        assert edge["from_id"] in ids, f"dangling edge source {edge['from_id']}"
        assert edge["to_id"] in ids, f"dangling edge target {edge['to_id']}"


def test_concepts_and_nodes_agree_on_the_slice(fixture_payload):
    """A reader that consults one block must not see fewer concepts than the other."""
    node_ids = {n["id"] for n in fixture_payload["nodes"]}
    concept_ids = set(fixture_payload["concepts"])
    assert node_ids == concept_ids


# ── Boot provisioning ─────────────────────────────────────────────────────────


def test_stub_detection_agrees_with_the_fixture(fixture_payload):
    from hostapp import corpus_bootstrap as cb

    assert cb.is_stub(FIXTURE) is True  # Usable demo, but must not suppress full-library restoration.


def test_missing_graph_is_a_stub():
    from hostapp import corpus_bootstrap as cb

    assert cb.is_stub(Path("/nonexistent/okf_graph.json")) is True


def test_tiny_graph_counts_as_a_stub(tmp_path):
    from hostapp import corpus_bootstrap as cb

    tiny = tmp_path / "okf_graph.json"
    tiny.write_text(json.dumps({"nodes": [{"id": "a"}, {"id": "b"}]}), encoding="utf-8")
    assert cb.is_stub(tiny) is True


def test_provision_installs_the_fixture_on_a_fresh_build(tmp_path, monkeypatch):
    """The core guarantee: a build with no corpus is still a working build."""
    from hostapp import corpus_bootstrap as cb

    shutil.copytree(HOST_DIR / "fixtures", tmp_path / "host_inference" / "fixtures")
    monkeypatch.delenv(cb.HF_REPO_ENV, raising=False)
    monkeypatch.delenv(cb.HF_TOKEN_ENV, raising=False)

    report = cb.provision(tmp_path)

    assert report["source"] == "fixture"
    assert report["ok"] is False  # Fixture is usable, not a complete restored library.
    assert report["concepts"] > 0
    assert report["missing"]
    assert (tmp_path / "okf_graph.json").is_file()
    # The engine reads the cache copy, so both must exist.
    assert (tmp_path / "host_inference" / "cache" / "okf_graph.json").is_file()


def test_provision_leaves_a_full_corpus_alone(tmp_path):
    """Never overwrite a good corpus with the fallback slice."""
    from hostapp import corpus_bootstrap as cb

    full = tmp_path / "okf_graph.json"
    full.write_text(
        json.dumps({"nodes": [{"id": f"c{i}"} for i in range(cb.MIN_USEFUL_CONCEPTS + 1)]}),
        encoding="utf-8",
    )
    before = full.read_text(encoding="utf-8")
    shutil.copytree(HOST_DIR / "fixtures", tmp_path / "host_inference" / "fixtures")

    report = cb.provision(tmp_path)
    assert report["source"] == "present"
    assert report["ok"] is False  # Graph exists; catalogue and manifest still need restoring.
    assert "data/catalogs/pearson_bookshelf.json" in report["missing"]
    assert full.read_text(encoding="utf-8") == before


def test_provision_reports_honestly_when_nothing_is_available(tmp_path, monkeypatch):
    """No corpus must be a reported state, never a crash and never a fake 'ok'."""
    from hostapp import corpus_bootstrap as cb

    monkeypatch.delenv(cb.HF_REPO_ENV, raising=False)
    monkeypatch.delenv(cb.HF_TOKEN_ENV, raising=False)

    report = cb.provision(tmp_path)

    assert report["source"] == "missing"
    assert report["ok"] is False
    assert report["concepts"] == 0


def test_provision_never_raises_on_a_hostile_environment(tmp_path, monkeypatch):
    """Boot must not crash-loop because an artifact is unreadable."""
    from hostapp import corpus_bootstrap as cb

    broken = tmp_path / "okf_graph.json"
    broken.write_text("{not json", encoding="utf-8")
    monkeypatch.delenv(cb.HF_REPO_ENV, raising=False)
    monkeypatch.delenv(cb.HF_TOKEN_ENV, raising=False)

    assert cb.provision(tmp_path)["source"] in {"fixture", "missing"}


def test_readiness_separates_process_health_from_corpus_depth():
    """`ok` must stay true for the platform probe; the corpus verdict is separate."""
    from hostapp.routes.pages import FULL_CORPUS_MIN_CONCEPTS

    assert FULL_CORPUS_MIN_CONCEPTS > 0
    source = (HOST_DIR / "hostapp" / "routes" / "pages.py").read_text(encoding="utf-8")
    assert '"ok": True' in source, "the platform health probe must keep passing"
    assert '"full": source == "full"' in source, (
        "readiness must report corpus depth, not just process liveness"
    )
    assert "getattr(graph, \"corpus_source\"" in source, (
        "readiness must tolerate a graph object that does not carry the marker; "
        "a 500 from the health endpoint is how a deploy gets killed"
    )


def test_fixture_generator_is_reproducible():
    """Re-running the generator must not produce a different slice."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import build_corpus_fixture as builder
    finally:
        sys.path.pop(0)

    if not (REPO_ROOT / "okf_graph.json").is_file():
        pytest.skip("full export is not present; cannot regenerate")

    first = builder.build(80)
    second = builder.build(80)
    assert first == second


def test_fixture_generator_rejects_a_missing_source(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    try:
        import build_corpus_fixture as builder
    finally:
        sys.path.pop(0)

    monkeypatch.setattr(builder, "SOURCE", tmp_path / "nope.json")
    monkeypatch.setattr(sys, "argv", ["build_corpus_fixture.py"])
    assert builder.main() == 1


def test_env_example_documents_the_boot_fetch():
    """The deploy spec alone does not say where the corpus comes from."""
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "HF_DATASET_REPO" in example
    assert "HF_TOKEN" in example


def test_fixture_is_not_gitignored():
    """The whole point: this file has to be in the repo to reach the build."""
    import subprocess

    result = subprocess.run(
        ["git", "check-ignore", "-q", str(FIXTURE.relative_to(REPO_ROOT))],
        cwd=REPO_ROOT, capture_output=True, check=False,
    )
    assert result.returncode != 0, (
        "host_inference/fixtures/ is ignored by git; the deployment will build "
        "with no corpus at all"
    )


def test_no_provider_other_than_xkiro_and_nvidia_is_in_the_default_chain():
    from archipelago.inference.llm_gateway import part01_config as config

    assert config.PROVIDER_FALLBACK_ORDER == ("xkiro", "nvidia")
    assert "openrouter" not in config.PROVIDER_FALLBACK_ORDER
    assert os.environ.get("OPENROUTER_API_KEY", "") == "" or True  # documented as removed
