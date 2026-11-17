"""Auto-split from monolith — blocks are verbatim."""

from __future__ import annotations

from typing import Any

import kuzu

from okf.canonicalize import _concept_key, canonicalize_name
from okf.eval._base import FUZZY_MATCH_THRESHOLD, _rf_fuzz
from okf.eval.structural import structural_audit

from . import _deps as _rt  # noqa: F401
from .edge_extraction import _extract_edges as _extract_edges


def load_gold_graph(path: str) -> Any:
    """Load gold graph from a JSON file path."""
    import json

    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _extract_names(input_data: Any) -> set[str]:
    if isinstance(input_data, dict):
        # Gold files / graph exports often wrap payloads as
        # {"concepts": [...|...], "edges": [...]}. Prefer the nested concepts
        # payload so top-level keys like "concepts"/"edges" are never treated
        # as concept names (historical FN=2 bug).
        if "concepts" in input_data and isinstance(input_data["concepts"], (list, dict, set)):
            nested = _extract_names(input_data["concepts"])
            if nested:
                return nested
        names = set()
        for _k, v in input_data.items():
            if isinstance(v, dict):
                name = v.get("name") or v.get("concept_name")
                if name:
                    names.add(name.strip().lower())
            elif isinstance(v, str):
                names.add(v.strip().lower())
        if not names:
            # Last resort: keys as names only when values are not concept records
            # and this is not a concepts/edges wrapper (empty concepts list).
            if set(input_data.keys()) <= {
                "concepts",
                "edges",
                "stats",
                "visualization",
                "graph_rag_index",
            }:
                return set()
            names = {k.strip().lower() for k in input_data}
        return names
    elif isinstance(input_data, list):
        names = set()
        for c in input_data:
            if isinstance(c, dict):
                if "concepts" in c:
                    for sub_c in c["concepts"]:
                        name = sub_c.get("concept_name") or sub_c.get("name")
                        if name:
                            names.add(name.strip().lower())
                else:
                    name = c.get("concept_name") or c.get("name")
                    if name:
                        names.add(name.strip().lower())
            elif isinstance(c, str):
                names.add(c.strip().lower())
        return names
    elif isinstance(input_data, set):
        return {str(x).strip().lower() for x in input_data}
    return set()


def _canonical_key(name: str) -> str:
    """Gold-comparison key: alias resolution (ALIAS_MAP) + canonical form +
    concept-key normalization, so 'LoRA' and 'Low-Rank Adaptation' compare equal."""
    # _concept_key comes from okf.canonicalize via okf.eval._base
    return _concept_key(canonicalize_name(name))


def _extract_name_docs(input_data: Any) -> dict[str, set[str]]:
    """Map lowered concept name → set of provenance doc_ids.

    Only records that carry a "sources" list with doc_id entries appear here;
    names without provenance are simply absent (callers treat them as
    unrestricted when doc-scoping)."""
    docs: dict[str, set[str]] = {}

    def _record(rec: dict[str, Any]) -> None:
        name = rec.get("name") or rec.get("concept_name")
        if not name:
            return
        doc_ids = {
            str(s["doc_id"])
            for s in rec.get("sources", [])
            if isinstance(s, dict) and s.get("doc_id")
        }
        if doc_ids:
            docs.setdefault(name.strip().lower(), set()).update(doc_ids)

    if isinstance(input_data, dict):
        payload = input_data.get("concepts", input_data)
        if isinstance(payload, dict):
            for v in payload.values():
                if isinstance(v, dict):
                    _record(v)
        elif isinstance(payload, list):
            for c in payload:
                if isinstance(c, dict):
                    _record(c)
    elif isinstance(input_data, list):
        for c in input_data:
            if isinstance(c, dict):
                if isinstance(c.get("concepts"), list):
                    for sub_c in c["concepts"]:
                        if isinstance(sub_c, dict):
                            _record(sub_c)
                else:
                    _record(c)
    return docs


def compare_concepts(extracted: Any, gold: Any, doc_id: str | None = None) -> dict[str, Any]:
    """Calculate precision, recall, and F1 score of extracted concepts vs gold concepts.

    Names on BOTH sides are normalized through okf.canonicalize
    (canonicalize_name + _concept_key), so aliases like "LoRA" vs
    "Low-Rank Adaptation" count as matches. Names still unmatched after key
    normalization fall back to rapidfuzz token_set_ratio >= FUZZY_MATCH_THRESHOLD.

    If doc_id is given (gold sets are document-scoped), only extracted concepts
    whose provenance explicitly includes doc_id are evaluated; concepts lacking
    provenance are excluded and counted in ``unscopable_concepts`` rather than
    silently attributed to any document.
    """
    ext_set = _extract_names(extracted)
    gold_set = _extract_names(gold)

    unscopable_concepts: set[str] = set()
    if doc_id:
        name_docs = _extract_name_docs(extracted)
        unscopable_concepts = {n for n in ext_set if n not in name_docs}
        ext_set = {n for n in ext_set if n in name_docs and doc_id in name_docs[n]}

    base_meta = {
        "doc_id": doc_id,
        "predicted_count": len(ext_set),
        "gold_count": len(gold_set),
        "unscopable_concepts": len(unscopable_concepts),
        "normalization": "canonical_v2",
    }

    if not ext_set and not gold_set:
        return {
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "matched_pairs": [],
            **base_meta,
        }
    if not ext_set:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": len(gold_set),
            "matched_pairs": [],
            **base_meta,
        }
    if not gold_set:
        return {
            "precision": 0.0,
            "recall": 0.0,
            "f1": 0.0,
            "true_positives": 0,
            "false_positives": len(ext_set),
            "false_negatives": 0,
            "matched_pairs": [],
            **base_meta,
        }

    # Group raw names by canonical key (near-duplicate raw names collapse).
    ext_keys: dict[str, set[str]] = {}
    for n in ext_set:
        ext_keys.setdefault(_canonical_key(n), set()).add(n)
    gold_keys: dict[str, set[str]] = {}
    for n in gold_set:
        gold_keys.setdefault(_canonical_key(n), set()).add(n)

    # 1. Exact match on canonical keys
    matched_keys = ext_keys.keys() & gold_keys.keys()
    matched_pairs = [
        [sorted(ext_keys[k])[0], sorted(gold_keys[k])[0]] for k in sorted(matched_keys)
    ]
    unmatched_ext = sorted(k for k in ext_keys if k not in matched_keys)
    unmatched_gold = sorted(k for k in gold_keys if k not in matched_keys)

    # 2. Fuzzy fallback: greedy best-score pairing of remaining keys
    if _rf_fuzz is not None and unmatched_ext and unmatched_gold:
        candidates = []
        for gk in unmatched_gold:
            for ek in unmatched_ext:
                score = _rf_fuzz.token_set_ratio(gk, ek)
                if score >= FUZZY_MATCH_THRESHOLD:
                    candidates.append((score, gk, ek))
        candidates.sort(reverse=True)
        used_gold, used_ext = set(), set()
        for _score, gk, ek in candidates:
            if gk in used_gold or ek in used_ext:
                continue
            used_gold.add(gk)
            used_ext.add(ek)
            matched_pairs.append([sorted(ext_keys[ek])[0], sorted(gold_keys[gk])[0]])
        unmatched_ext = [k for k in unmatched_ext if k not in used_ext]
        unmatched_gold = [k for k in unmatched_gold if k not in used_gold]

    tp = len(matched_pairs)
    fp = len(unmatched_ext)
    fn = len(unmatched_gold)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "matched_pairs": matched_pairs,
        **base_meta,
    }


def _canonicalize_edge_set(raw_edges: set[tuple[str, str]]) -> set[tuple[str, str]]:
    """Canonicalize both endpoints deterministically via _canonical_key (no fuzzy matching)."""
    out: set[tuple[str, str]] = set()
    for u, v in raw_edges:
        cu = _canonical_key(u)
        cv = _canonical_key(v)
        if cu and cv:
            out.add((cu, cv))
    return out


def compare_edges(
    extracted: Any,
    gold: Any,
    doc_id: str | None = None,
    include_related: bool = False,
) -> dict[str, Any]:
    """Calculate precision, recall, and F1 of directed prerequisite edges, and direction accuracy.

    By default ``include_related=False`` so undirected ``RELATED`` edges do not
    pollute directed prerequisite precision/recall. Both endpoints are normalized
    deterministically with ``_canonical_key``. Empty gold & empty predictions
    yield precision=1.0, recall=1.0, f1=1.0; one empty yields 0.0.
    """
    ext_stats: dict[str, int] = {}
    ext_edges = _canonicalize_edge_set(
        _extract_edges(
            extracted,
            include_related=include_related,
            doc_id=doc_id,
            stats=ext_stats,
        )
    )
    gold_edges = _canonicalize_edge_set(
        _extract_edges(gold, include_related=include_related)
    )

    # Convert edges to undirected maps
    ext_undir: dict[frozenset[str], tuple[str, str]] = {}
    for u, v in ext_edges:
        ext_undir[frozenset([u, v])] = (u, v)

    gold_undir: dict[frozenset[str], tuple[str, str]] = {}
    for u, v in gold_edges:
        gold_undir[frozenset([u, v])] = (u, v)

    # Calculate metrics on directed edges
    if not ext_edges and not gold_edges:
        dir_metrics = {
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
        }
    else:
        tp = len(ext_edges & gold_edges)
        fp = len(ext_edges - gold_edges)
        fn = len(gold_edges - ext_edges)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        dir_metrics = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
        }

    # Calculate metrics on undirected edges
    if not ext_undir and not gold_undir:
        undir_metrics = {
            "precision": 1.0,
            "recall": 1.0,
            "f1": 1.0,
            "true_positives": 0,
            "false_positives": 0,
            "false_negatives": 0,
        }
    else:
        tp = len(ext_undir.keys() & gold_undir.keys())
        fp = len(ext_undir.keys() - gold_undir.keys())
        fn = len(gold_undir.keys() - ext_undir.keys())
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        undir_metrics = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
        }

    # Calculate direction accuracy for matched undirected edges.
    # S4-F fix (Task B): return None with explicit status when denominator=0,
    # rather than the previously spurious 1.0 (vacuous truth).
    matched_undir = ext_undir.keys() & gold_undir.keys()
    correct_directions = 0
    for edge in matched_undir:
        if ext_undir[edge] == gold_undir[edge]:
            correct_directions += 1

    if matched_undir:
        dir_accuracy: float | None = correct_directions / len(matched_undir)
        dir_accuracy_status = "computed"
    else:
        dir_accuracy = None
        dir_accuracy_status = "undefined"

    return {
        "directed": dir_metrics,
        "undirected": undir_metrics,
        "direction_accuracy": dir_accuracy,
        "direction_accuracy_status": dir_accuracy_status,
        "direction_accuracy_denominator": len(matched_undir),
        "doc_id": doc_id,
        "predicted_edge_count": len(ext_edges),
        "gold_edge_count": len(gold_edges),
        "unscopable_edges": ext_stats.get("unscopable_edges", 0),
        "skipped_related_edges": ext_stats.get("skipped_related", 0),
        "matched_directed_edges": sorted([list(e) for e in (ext_edges & gold_edges)]),
    }


def evaluate_pipeline(
    db: kuzu.Database | kuzu.Connection,
    gold_path: str,
    doc_id: str | None = None,
) -> dict[str, Any]:
    """Run the complete evaluation pipeline comparing the DB graph against gold data."""
    gold_data = load_gold_graph(gold_path)

    import kuzu

    conn = db if hasattr(db, "execute") else kuzu.Connection(db)

    from okf.graph_db import export_graph

    db_export = export_graph(conn)

    effective_doc_id = doc_id
    if effective_doc_id is None and isinstance(gold_data, dict):
        effective_doc_id = gold_data.get("doc_id")

    # Gold files use {"concepts": [...], "edges": [...]}; pass concepts list for name match.
    if isinstance(gold_data, dict) and "concepts" in gold_data:
        gold_concepts = gold_data["concepts"]
    else:
        gold_concepts = gold_data

    concept_metrics = compare_concepts(db_export["concepts"], gold_concepts, doc_id=effective_doc_id)
    edge_metrics = compare_edges(db_export, gold_data, doc_id=effective_doc_id)
    audit_metrics = structural_audit(db)

    return {
        "scope": {
            "mode": "document" if effective_doc_id else "whole_graph",
            "doc_id": effective_doc_id,
        },
        "concept_comparison": concept_metrics,
        "edge_comparison": edge_metrics,
        "structural_audit": audit_metrics,
    }
