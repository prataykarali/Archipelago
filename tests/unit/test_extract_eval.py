"""Feature regression — SLM extraction eval harness.

The harness is what makes "is the model ready for ingestion?" answerable by a
command instead of an impression. These tests pin the *scoring* logic — the part
that must not silently flatter the model — while staying fully offline by
stubbing the extractor.

Two properties matter most:

1. **Alias-aware scoring.** ``LoRA`` and ``Low-Rank Adaptation`` are the same
   concept; scoring them as a miss would hide the model's actual quality. Word
   order must likewise not matter.
2. **Gate honesty.** An empty-gold probe that correctly returns nothing must
   count as a *hit*, not a miss, and probes the model errors on must not be
   averaged away.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from archipelago.eval import extract_eval as ev  # noqa: E402

pytestmark = pytest.mark.unit


class StubExtractor:
    """Deterministic extractor returning pre-seeded concepts per probe text."""

    def __init__(self, responses: dict[str, list[dict]], raise_on: set[str] | None = None):
        self.responses = responses
        self.raise_on = raise_on or set()

    def extract_from_text(self, text, book_title="", page_number=1, domain=""):
        for marker, payload in self.responses.items():
            if marker in text:
                if marker in self.raise_on:
                    raise RuntimeError("model exploded")
                return json.loads(json.dumps(payload))
        return []


def concept(name: str, **overrides) -> dict:
    """A schema-valid concept record."""
    base = {
        "concept_name": name,
        "name": name,
        "concept_type": "definition",
        "difficulty": "intermediate",
        "summary": f"A definition of {name} used for testing purposes.",
        "prerequisites": [],
        "unlocks": [],
        "related_to": [],
        "tags": ["test"],
    }
    base.update(overrides)
    return base


# ─── Alias-aware canonicalisation ───────────────────────────────────────────


@pytest.mark.parametrize(
    "a, b",
    [
        ("LoRA", "Low-Rank Adaptation"),
        ("low rank adaptation", "LORA"),
        ("SGD", "Stochastic Gradient Descent"),
        ("BERT", "Bidirectional Encoder Representations from Transformers"),
        ("Stochastic Gradient Descent", "Gradient Descent Stochastic"),
        ("BERT (Bidirectional Encoder Representations from Transformers)", "BERT"),
    ],
)
def test_equivalent_names_canonicalize_together(a, b):
    assert ev.canonical(a) == ev.canonical(b)


@pytest.mark.parametrize(
    "a, b",
    [
        ("LoRA", "Convolutional Neural Network"),
        ("Adam", "Stochastic Gradient Descent"),
        ("Transformer", "Graph Neural Network"),
    ],
)
def test_distinct_names_do_not_canonicalize_together(a, b):
    assert ev.canonical(a) != ev.canonical(b)


def test_acronym_expansion_does_not_leave_the_acronym_behind():
    """A leftover 'lora' token would make the two forms never match."""
    assert "lora" not in ev.canonical("LoRA")
    assert "low" in ev.canonical("LoRA")


def test_prf_rewards_the_alias_match():
    assert ev.prf(["LoRA"], ["Low-Rank Adaptation"])["f1"] == 1.0


def test_prf_on_empty_prediction_and_empty_gold_is_a_perfect_score():
    assert ev.prf([], [])["f1"] == 1.0


def test_prf_on_prediction_only_is_zero():
    assert ev.prf(["Something"], [])["f1"] == 0.0


def test_prf_partial_overlap_scores_between_zero_and_one():
    score = ev.prf(["Matrix", "Vector"], ["Matrix"])["f1"]
    assert 0.0 < score < 1.0


def test_prf_counts_union_of_aliases_only_once():
    """Predicting both spellings must not be double-counted as two hits."""
    result = ev.prf(["LoRA", "Low-Rank Adaptation"], ["Low-Rank Adaptation"])
    assert result["f1"] == 1.0


# ─── Celebrity / person-name detection ───────────────────────────────────────


@pytest.mark.parametrize(
    "name", ["Goodfellow", "Ian Goodfellow", "Yann LeCun", "Geoffrey Hinton", "et al"]
)
def test_person_names_are_flagged(name):
    assert ev.looks_like_celebrity(name)


@pytest.mark.parametrize(
    "name",
    [
        "Stochastic Gradient Descent",
        "Graph Neural Network",
        "Linear Algebra",
        "Attention Mechanism",
        "Deep Learning",
        # A legitimate concept that merely names an author.
        "Goodfellow GAN",
    ],
)
def test_real_concepts_are_not_flagged(name):
    assert not ev.looks_like_celebrity(name)


def test_empty_name_is_not_a_celebrity():
    assert not ev.looks_like_celebrity("")


# ─── Schema validation ──────────────────────────────────────────────────────


def test_valid_concepts_pass_schema_validation():
    assert ev.validate_schema([concept("Adam")])


def test_empty_list_passes_schema_validation():
    assert ev.validate_schema([])


def test_missing_required_key_fails_schema_validation():
    bad = concept("Adam")
    del bad["tags"]
    assert not ev.validate_schema([bad])


def test_out_of_vocabulary_type_fails_schema_validation():
    assert not ev.validate_schema([concept("Adam", concept_type="paragraph")])


def test_out_of_vocabulary_difficulty_fails_schema_validation():
    assert not ev.validate_schema([concept("Adam", difficulty="impossible")])


def test_non_list_relation_field_fails_schema_validation():
    assert not ev.validate_schema([concept("Adam", related_to={"concept": "SGD"})])


def test_non_dict_record_fails_schema_validation():
    assert not ev.validate_schema(["not a concept"])


# ─── Self-references ────────────────────────────────────────────────────────


def test_self_reference_is_counted():
    payload = concept("Adam", prerequisites=["Adam"], unlocks=["Adam"])
    assert ev.count_self_references(payload) == 2


def test_non_self_reference_is_not_counted():
    payload = concept("Adam", prerequisites=["SGD"], unlocks=["Transformer"])
    assert ev.count_self_references(payload) == 0


def test_dict_shaped_relation_target_is_read():
    payload = concept("Adam", prerequisites=[{"name": "Adam"}])
    assert ev.count_self_references(payload) == 1


# ─── Distribution summary (Skill 2) ─────────────────────────────────────────


def test_summary_reports_the_documented_statistics():
    summary = ev.summarize([0.0, 0.5, 1.0])
    assert summary["n"] == 3
    assert summary["mean"] == 0.5
    assert summary["min"] == 0.0
    assert summary["max"] == 1.0
    assert 0.0 <= summary["p5"] <= summary["p95"] <= 1.0


def test_summary_of_a_single_value_is_stable():
    summary = ev.summarize([0.42])
    assert summary["mean"] == summary["p5"] == summary["p95"] == 0.42


def test_summary_of_nothing_is_zeroed():
    assert ev.summarize([])["n"] == 0


def test_summary_exposes_spread():
    """A wide spread must be visible; a bare mean would hide bimodality."""
    assert ev.summarize([0.0] * 9 + [1.0])["std"] > 0.2


# ─── Gate honesty ───────────────────────────────────────────────────────────


def _probe(pid, text, gold, tag="paper"):
    return {"probe_id": pid, "tag": tag, "text": text, "gold": gold}


def test_perfect_extractor_passes_the_gate(monkeypatch, tmp_path):
    probes = [
        _probe("p1", "about Adam here", ["Adam"]),
        _probe("p2", "nothing here", []),
    ]
    path = tmp_path / "probes.jsonl"
    path.write_text(
        "\n".join(json.dumps(p) for p in probes), encoding="utf-8"
    )

    stub = StubExtractor(
        {"about Adam": [concept("Adam")], "nothing here": []}
    )
    monkeypatch.setattr(
        "archipelago.ingestion.lib_qwen_extractor.LibQwenConceptExtractor",
        lambda model_name: stub,
    )

    report = ev.evaluate(probes_path=path)
    assert report["gate"]["ready_for_pilot_ingest"] is True


def test_empty_gold_probe_counted_as_a_hit_not_a_miss(monkeypatch, tmp_path):
    """The negative probes exist to catch over-extraction; returning [] is correct."""
    probes = [_probe("neg", "just boilerplate", [], tag="negative")]
    path = tmp_path / "probes.jsonl"
    path.write_text(json.dumps(probes[0]), encoding="utf-8")

    stub = StubExtractor({})
    monkeypatch.setattr(
        "archipelago.ingestion.lib_qwen_extractor.LibQwenConceptExtractor",
        lambda model_name: stub,
    )
    report = ev.evaluate(probes_path=path)
    assert report["metrics"]["empty_exact_match_pct"] == 100.0


def test_over_extraction_on_a_negative_fails_the_empty_check(monkeypatch, tmp_path):
    probes = [_probe("neg", "just boilerplate", [], tag="negative")]
    path = tmp_path / "probes.jsonl"
    path.write_text(json.dumps(probes[0]), encoding="utf-8")

    stub = StubExtractor({"just boilerplate": [concept("Some Junk")]})
    monkeypatch.setattr(
        "archipelago.ingestion.lib_qwen_extractor.LibQwenConceptExtractor",
        lambda model_name: stub,
    )
    report = ev.evaluate(probes_path=path)
    assert report["metrics"]["empty_exact_match_pct"] == 0.0
    assert report["gate"]["checks"]["empty_match_ge_40_if_present"] is False


def test_a_crashed_probe_is_recorded_as_an_error(monkeypatch, tmp_path):
    probes = [_probe("p1", "boom here", ["Adam"])]
    path = tmp_path / "probes.jsonl"
    path.write_text(json.dumps(probes[0]), encoding="utf-8")

    stub = StubExtractor({"boom here": []}, raise_on={"boom here"})
    monkeypatch.setattr(
        "archipelago.ingestion.lib_qwen_extractor.LibQwenConceptExtractor",
        lambda model_name: stub,
    )
    report = ev.evaluate(probes_path=path)
    assert report["metrics"]["errors"] == 1
    assert "model exploded" in report["probes"][0]["error"]
    assert report["gate"]["ready_for_pilot_ingest"] is False


def test_celebrity_concepts_fail_the_gate(monkeypatch, tmp_path):
    probes = [_probe("p1", "about Adam here", ["Adam"])]
    path = tmp_path / "probes.jsonl"
    path.write_text(json.dumps(probes[0]), encoding="utf-8")

    stub = StubExtractor({"about Adam": [concept("Goodfellow")]})
    monkeypatch.setattr(
        "archipelago.ingestion.lib_qwen_extractor.LibQwenConceptExtractor",
        lambda model_name: stub,
    )
    report = ev.evaluate(probes_path=path)
    assert report["metrics"]["celebrity_concepts"] == 1
    assert report["gate"]["checks"]["no_celeb_concepts"] is False


def test_report_is_rendered_with_gate_verbatim(monkeypatch, tmp_path):
    probes = [_probe("p1", "about Adam here", ["Adam"])]
    path = tmp_path / "probes.jsonl"
    path.write_text(json.dumps(probes[0]), encoding="utf-8")
    stub = StubExtractor({"about Adam": [concept("Adam")]})
    monkeypatch.setattr(
        "archipelago.ingestion.lib_qwen_extractor.LibQwenConceptExtractor",
        lambda model_name: stub,
    )
    text = ev.report(ev.evaluate(probes_path=path))
    assert "Gate:" in text
    assert "alias_f1_ge_0_35" in text


# ─── Probe loading ──────────────────────────────────────────────────────────


def test_missing_probe_file_raises():
    with pytest.raises(FileNotFoundError):
        ev.load_probes(Path("/nonexistent/probes.jsonl"))


def test_probe_loader_skips_blanks_and_comments(tmp_path):
    path = tmp_path / "p.jsonl"
    path.write_text(
        '\n// a comment\n{"probe_id": "a", "text": "t", "gold": []}\n\n', encoding="utf-8"
    )
    probes = ev.load_probes(path)
    assert len(probes) == 1
    assert probes[0]["tag"] == "general"


def test_malformed_probe_line_raises_with_line_number(tmp_path):
    path = tmp_path / "p.jsonl"
    path.write_text('{"probe_id": "a"}\nnot json\n', encoding="utf-8")
    with pytest.raises(ValueError, match=":2"):
        ev.load_probes(path)


def test_shipped_probe_set_is_valid_and_covers_the_gate_axes():
    """The committed probe set must exercise positives *and* negatives."""
    probes = ev.load_probes(REPO_ROOT / ev.DEFAULT_PROBES)
    assert len(probes) >= 8
    tags = {p["tag"] for p in probes}
    assert {"paper", "negative"} <= tags
    assert any(p["gold"] for p in probes), "needs positive probes"
    assert any(not p["gold"] for p in probes), "needs negative probes"
