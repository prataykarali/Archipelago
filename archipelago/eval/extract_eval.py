"""SLM extraction eval harness (Skill 2: distributions, not pass/fail).

Measures how the fine-tuned extraction SLM performs against a gold probe set,
and turns the numbers into an explicit go/no-go for ingestion. The point is
that "is the model ready?" gets answered by a reproducible command rather than
by impression.

Run it::

    python -m archipelago.eval.extract_eval            # report + gate
    python -m archipelago.eval.extract_eval --n 8      # quick smoke

**Metrics, and why each one exists.** A prior fine-tune reported 100% valid
JSON and a mean exact-match F1 of 0.25 while still being unusable, because
"valid JSON" says nothing about whether the concepts are right. So the gate is
dominated by *alias-aware* F1 (does it find the right concept, allowing for
acronyms and reordering?) rather than exact-string F1, and by two behavioural
probes that caught real defects: emitting a celebrity as a concept, and never
returning an empty list on a passage that should yield nothing.

Following Skill 2 the summary reports a **distribution** (mean/std/min/max/p5/
p95) rather than a single pass/fail, so a 90%-mean run with visible spread is
distinguishable from a fluke.
"""

from __future__ import annotations

import argparse
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass, field
import json
import logging
from pathlib import Path
import re
import statistics
import sys
import time
from typing import Any

from okf.config import BASE_DIR

from .extract_eval_report import report as report
from .extract_eval_vocab import (
    ACRONYM_EXPANSIONS,
    PERSON_TOKENS,
    REQUIRED_KEYS,
    VALID_DIFFICULTIES,
    VALID_TYPES,
)

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "lib-qwen:latest"
DEFAULT_PROBES = Path("tests") / "fixtures" / "extraction_probes.jsonl"

# Gate thresholds. These are the operational bar for letting the SLM write into
# the graph unattended, not an academic target.
GATE_ALIAS_F1_MIN = 0.35
GATE_JSON_VALID_MIN = 95.0
GATE_SCHEMA_OK_MIN = 90.0
GATE_EMPTY_MATCH_MIN = 40.0
GATE_MAX_CELEBRITY_CONCEPTS = 0

# Probe window: enough of a real page to be representative, small enough to
# keep a full run under a couple of minutes on CPU.
PROBE_CHAR_LIMIT = 2500


def _norm(text: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    return re.sub(r"[^a-z0-9\s]+", " ", (text or "").lower()).strip()


def _tokens(text: str) -> set[str]:
    return set(_norm(text).split())


def canonical(name: str) -> str:
    """Alias-aware canonical form of a concept name.

    Drops parenthetical expansions so ``BERT (Bidirectional Encoder…)`` matches
    ``BERT``, and expands a bare acronym into its long form so ``LoRA`` and
    ``Low-Rank Adaptation`` compare equal. Returns a space-sorted token string so
    word order never causes a false miss.
    """
    base = re.sub(r"\s*\([^)]*\)\s*", " ", (name or "")).strip()
    tokens = _tokens(base)
    # Swap the acronym token for its expansion so the two forms collide exactly
    # ("lora" -> "low rank adaptation"), rather than leaving the stray acronym
    # token alongside the expansion and never matching.
    for acronym, expansion in ACRONYM_EXPANSIONS.items():
        if acronym in tokens:
            tokens = (tokens - {acronym}) | _tokens(expansion)
            break
    return " ".join(sorted(tokens))


def prf(predicted: Iterable[str], gold: Iterable[str]) -> dict[str, float]:
    """Precision/recall/F1 over canonical concept sets."""
    pred = {canonical(p) for p in predicted if p and canonical(p)}
    gold_set = {canonical(g) for g in gold if g and canonical(g)}
    if not pred and not gold_set:
        return {"precision": 1.0, "recall": 1.0, "f1": 1.0}
    if not pred or not gold_set:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}
    hits = len(pred & gold_set)
    precision = hits / len(pred)
    recall = hits / len(gold_set)
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)
    return {"precision": precision, "recall": recall, "f1": f1}


@dataclass
class ProbeResult:
    """Outcome for a single probe."""

    probe_id: str
    tag: str
    latency_s: float
    json_valid: bool
    schema_ok: bool
    predicted: list[str] = field(default_factory=list)
    gold: list[str] = field(default_factory=list)
    f1_exact: float = 0.0
    f1_alias: float = 0.0
    empty_expected: bool = False
    celebrity_concepts: list[str] = field(default_factory=list)
    self_references: int = 0
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def looks_like_celebrity(name: str) -> bool:
    """True when a concept name reads as an author/celebrity rather than a topic.

    Heuristic and intentionally conservative: it flags a name whose tokens are
    *only* person-indicating words, so a legitimate concept that merely mentions
    a person ("Goodfellow GAN") is not flagged.
    """
    words = _tokens(name)
    if not words:
        return False
    return words <= PERSON_TOKENS


def count_self_references(concept: dict[str, Any]) -> int:
    """How many of a concept's own relations point back at itself."""
    name = concept.get("name") or concept.get("concept_name") or ""
    total = 0
    for key in ("prerequisites", "unlocks"):
        for item in concept.get(key) or []:
            target = item.get("name") if isinstance(item, dict) else item
            if str(target or "").strip().lower() == str(name).strip().lower():
                total += 1
    return total


def validate_schema(concepts: Sequence[dict[str, Any]]) -> bool:
    """Every record must carry the 8-key contract with in-vocabulary values."""
    if not concepts:
        return True
    for concept in concepts:
        if not isinstance(concept, dict):
            return False
        if not all(key in concept for key in REQUIRED_KEYS):
            return False
        if concept.get("concept_type") not in VALID_TYPES:
            return False
        if concept.get("difficulty") not in VALID_DIFFICULTIES:
            return False
        for key in ("prerequisites", "unlocks", "tags"):
            if not isinstance(concept.get(key), list):
                return False
        if not isinstance(concept.get("related_to"), list):
            return False
    return True


def load_probes(path: Path) -> list[dict[str, Any]]:
    """Read the JSONL probe set. Missing file is an error, not a silent pass."""
    if not path.is_file():
        raise FileNotFoundError(f"probe set not found: {path}")
    probes: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        try:
            record = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{line_no}: {exc}") from exc
        record.setdefault("probe_id", f"probe_{line_no}")
        record.setdefault("tag", "general")
        record.setdefault("gold", [])
        probes.append(record)
    return probes


def summarize(values: list[float]) -> dict[str, float]:
    """Distribution summary per Skill 2 (mean/std/min/max/p5/p95)."""
    if not values:
        return {"n": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "p5": 0.0, "p95": 0.0}
    ordered = sorted(values)

    def percentile(fraction: float) -> float:
        if len(ordered) == 1:
            return ordered[0]
        index = fraction * (len(ordered) - 1)
        low = int(index)
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (index - low)

    return {
        "n": len(ordered),
        "mean": round(statistics.fmean(ordered), 4),
        "std": round(statistics.pstdev(ordered), 4),
        "min": round(ordered[0], 4),
        "max": round(ordered[-1], 4),
        "p5": round(percentile(0.05), 4),
        "p95": round(percentile(0.95), 4),
    }


def run_probe(extractor: Any, probe: dict[str, Any]) -> ProbeResult:
    """Run one probe through the extractor and score it."""
    text = str(probe.get("text") or "")[:PROBE_CHAR_LIMIT]
    gold = [str(g) for g in probe.get("gold") or []]
    started = time.perf_counter()

    result = ProbeResult(
        probe_id=str(probe.get("probe_id")),
        tag=str(probe.get("tag") or "general"),
        latency_s=0.0,
        json_valid=False,
        schema_ok=False,
        gold=gold,
        empty_expected=not gold,
    )
    try:
        concepts = extractor.extract_from_text(
            text,
            book_title=str(probe.get("book_title") or ""),
            page_number=int(probe.get("page_number") or 1),
            domain=str(probe.get("domain") or ""),
        )
        result.latency_s = round(time.perf_counter() - started, 3)
        result.json_valid = isinstance(concepts, list)
        concepts = concepts if result.json_valid else []
        result.schema_ok = validate_schema(concepts)
        result.predicted = [str(c.get("name") or c.get("concept_name") or "") for c in concepts]
        result.celebrity_concepts = [n for n in result.predicted if looks_like_celebrity(n)]
        result.self_references = sum(count_self_references(c) for c in concepts)
    except Exception as exc:
        result.latency_s = round(time.perf_counter() - started, 3)
        result.error = f"{type(exc).__name__}: {exc}"
        concepts = []

    if gold:
        result.f1_exact = prf(
            [canonical(n) for n in result.predicted], [canonical(g) for g in gold]
        )["f1"]
        result.f1_alias = prf(result.predicted, gold)["f1"]
    return result


def evaluate(
    model: str = DEFAULT_MODEL,
    probes_path: Path | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Run the probe set and return metrics plus the ingestion gate verdict."""
    from archipelago.ingestion.lib_qwen_extractor import LibQwenConceptExtractor

    probes_path = probes_path or (BASE_DIR / DEFAULT_PROBES)
    probes = load_probes(probes_path)
    if limit:
        probes = probes[:limit]

    extractor = LibQwenConceptExtractor(model_name=model)
    results = [run_probe(extractor, probe) for probe in probes]

    scored = [r for r in results if r.gold]
    empty_probes = [r for r in results if r.empty_expected]
    json_valid_pct = 100.0 * sum(r.json_valid for r in results) / max(1, len(results))
    schema_ok_pct = 100.0 * sum(r.schema_ok for r in results) / max(1, len(results))
    empty_hits = sum(1 for r in empty_probes if not r.predicted)

    metrics = {
        "json_valid_pct": round(json_valid_pct, 2),
        "schema_ok_pct": round(schema_ok_pct, 2),
        "f1_exact": summarize([r.f1_exact for r in scored]),
        "f1_alias": summarize([r.f1_alias for r in scored]),
        "latency_s": summarize([r.latency_s for r in results]),
        "empty_gold_n": len(empty_probes),
        "empty_exact_match_pct": round(100.0 * empty_hits / len(empty_probes), 2)
        if empty_probes
        else 0.0,
        "celebrity_concepts": sum(len(r.celebrity_concepts) for r in results),
        "self_ref_count": sum(r.self_references for r in results),
        "errors": sum(1 for r in results if r.error),
    }

    checks = {
        "json_valid_ge_95": json_valid_pct >= GATE_JSON_VALID_MIN,
        "schema_ok_ge_90": schema_ok_pct >= GATE_SCHEMA_OK_MIN,
        "alias_f1_ge_0_35": metrics["f1_alias"]["mean"] >= GATE_ALIAS_F1_MIN,
        "no_celeb_concepts": metrics["celebrity_concepts"] <= GATE_MAX_CELEBRITY_CONCEPTS,
        # Only meaningful when the probe set actually contains empty-gold cases.
        "empty_match_ge_40_if_present": (
            metrics["empty_exact_match_pct"] >= GATE_EMPTY_MATCH_MIN if empty_probes else True
        ),
        "self_ref_low": metrics["self_ref_count"] <= 1,
    }
    passed = sum(checks.values())

    return {
        "model": model,
        "n_probes": len(results),
        "metrics": metrics,
        "gate": {
            "checks": checks,
            "pass_count": passed,
            "total": len(checks),
            "ready_for_pilot_ingest": passed == len(checks),
            "ready_for_full_replace": passed == len(checks) and metrics["f1_alias"]["mean"] >= 0.5,
        },
        "by_tag": _by_tag(results),
        "probes": [r.to_dict() for r in results],
    }


def _by_tag(results: Sequence[ProbeResult]) -> dict[str, dict[str, Any]]:
    """Per-tag alias F1, so a single bad passage class is visible."""
    out: dict[str, dict[str, Any]] = {}
    for result in results:
        if not result.gold:
            continue
        bucket = out.setdefault(result.tag, {"n": 0, "f1_alias": []})
        bucket["n"] += 1
        bucket["f1_alias"].append(result.f1_alias)
    for bucket in out.values():
        bucket["f1_alias"] = summarize(bucket["f1_alias"])
    return out


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Exit 0 when the gate passes, 1 when it does not."""
    parser = argparse.ArgumentParser(prog="archipelago.eval.extract_eval")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--probes", help="Probe JSONL path")
    parser.add_argument("--n", type=int, help="Only run the first N probes")
    parser.add_argument("--json", action="store_true", help="Emit raw JSON")
    parser.add_argument("--out", help="Write the full report here")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(message)s")
    probes_path = Path(args.probes) if args.probes else None
    try:
        payload = evaluate(model=args.model, probes_path=probes_path, limit=args.n)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps(payload, indent=2) if args.json else report(payload))
    return 0 if payload["gate"]["ready_for_pilot_ingest"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
