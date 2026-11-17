# S4-F Evaluator Repair Report

**Branch:** `research/s4-f-evaluator-repair`
**Base commit:** `57744db2c2f408b2a97677dd04a8b37eab2c730f` (S4-E)
**Scope:** Evaluator integrity repairs only — no changes to gold fixtures, graph DB, extraction pipeline, or human annotations.

---

## Summary

S4-F repairs five scientifically invalid evaluator behaviours identified in S4-E diagnosis. After all repairs, **directed Edge F1 remains 0.0 for both LoRA and Attention** — confirming that the 0% result is a **genuine extraction failure**, not an evaluator artifact.

---

## Before / After Metrics (Reproduced)

| Metric | Baseline (original) | Corrected (S4-F) | Change |
|--------|---------------------|------------------|--------|
| **LoRA Concept F1** | 0.1905 | 0.1905 | None |
| **LoRA Directed Edge F1** | 0.0000 | 0.0000 | None — genuine failure confirmed |
| **LoRA Undirected Edge F1** | 0.0000 | 0.0000 | None |
| **LoRA Direction Accuracy** | 1.0 (BUG) | `null` / `undefined` | Bug fixed |
| **LoRA Unscopable edges** | 101 (single counter) | 101 (explicit bucket) | Reporting improved |
| **LoRA Skipped RELATED** | 1334 (single counter) | 1334 (explicit bucket) | Reporting improved |
| **Attention Concept F1** | 0.4000 | 0.4000 | None |
| **Attention Directed Edge F1** | 0.0000 | 0.0000 | None — genuine failure confirmed |
| **Attention Undirected Edge F1** | 0.0000 | 0.0000 | None |
| **Attention Direction Accuracy** | 1.0 (BUG) | `null` / `undefined` | Bug fixed |

> [!IMPORTANT]
> Concept F1 numbers are **unchanged** because concept evaluation logic was not modified.
> Edge F1 numbers are **unchanged** because the extraction failure is genuine, not an evaluator defect.
> No metric was artificially inflated or suppressed.

---

## Task A — Concept-Aligned Edge Evaluation

### Problem
`compare_concepts()` builds a fuzzy equivalence map (e.g. `adapter` ↔ `adapter layer`) internally, but that map was **never passed to `compare_edges()`**. The edge comparator used only canonical key equality, so a concept that matched under fuzzy equivalence could not contribute to an edge match.

### Fix
New module `okf/eval/gold/compare_aligned.py` exports:

- **`build_concept_equiv_map(concept_comparison)`** — extracts only the fuzzy (non-exact) matches from a `compare_concepts()` result into a deterministic `pred_key → gold_key` dict. Ambiguous cases (one predicted key would map to multiple gold keys) are reported separately and **excluded from TP counting**.
- **`compare_edges_aligned(extracted, gold, *, concept_comparison, ...)`** — applies the equiv map to both endpoints of every predicted edge before the canonical key comparison. The original `compare_edges()` is **unchanged** (backward compatible).

### Result for LoRA
- Equiv map: `{"adapter": "adapter layer"}` (1 fuzzy match, 0 ambiguities)
- After alignment: `('fine tuning', 'adapter')` → `('fine tuning', 'adapter layer')` — still not in gold edge set (gold has `('parameter efficient fine tuning', 'adapter layer')`)
- **Directed Edge F1 = 0.0** — confirmed genuine: the predicted edges connect different concept pairs to gold, not just differently-labelled endpoints.

### Result for Attention
- Equiv map: 5 entries (`transformer→transformer decoder`, `embedding→sinusoidal embedding`, `sequence→sequence to sequence model`, `fully connected feed forward network→feed forward network`, `optimizer→adam optimizer`)
- After alignment: 0 directed edge matches remain
- **Directed Edge F1 = 0.0** — confirmed genuine.

### Failure Diagnosis (sample, LoRA)

| Predicted edge (after alignment) | Failure reason |
|---|---|
| `(fine tuning, adapter layer)` | source_concept_present_but_wrong_target |
| `(fine tuning, low rank adaptation)` | source_concept_present_but_wrong_target |
| `(gpt, adapter layer)` | target_concept_present_but_wrong_source |
| `(gpt 2, gpt 3)` | both_endpoints_absent_from_gold_edges |
| `(low rank adaptation, feature adaptation)` | source_concept_present_but_wrong_target |

The extracted edges connect **correct source concepts to wrong targets**, indicating the extraction pipeline uses different relationship topology than the gold graph, not just different names.

---

## Task B — Direction Accuracy Guard

### Problem
`compare_edges()` returned `direction_accuracy = 1.0` when `matched_undirected == 0` (denominator = 0). This is mathematically undefined and was silently represented as perfect accuracy.

### Fix
`compare_edges()` in `part01_load_gold_graph.py` now returns:
```python
direction_accuracy = None           # was: 1.0
direction_accuracy_status = "undefined"  # new field
direction_accuracy_denominator = 0  # new field
```
When matches exist, it returns a computed float with `status = "computed"`.

The original test `test_vacuous_direction_accuracy_reproduced` in `test_s4e_graph_diagnosis.py` was updated to assert the corrected behaviour, with the historical defect documented in a comment.

---

## Task C — Provenance-Aware Evaluation

### Problem
Unscopable and out-of-scope edges were merged into a single `unscopable_edges` counter, obscuring their different meanings.

### Fix
`compare_edges_aligned()` returns a structured `scoping` dict:

```json
{
  "in_scope_edges": 13,
  "out_of_scope_edges": 1776,
  "unscopable_edges": 101,
  "skipped_related": 1334
}
```

Additionally, `evaluate_pipeline_corrected()` adds `concept_provenance`:
```json
{
  "globally_absent_gold_concepts": [...],
  "globally_absent_count": 16,
  "note": "..."
}
```

**Globally absent** = gold concept key not present anywhere in the DB (genuine extraction failure).

| Document | Globally absent gold concepts |
|---|---|
| LoRA | 16 of 20 (80%) |
| Attention | 16 of 25 (64%) |

These are absent from the **entire** DB, not scoped to a document — they were never extracted.

---

## Task D — Relationship Semantics Audit

### REQUIRES direction
`_add_edge_record()` in `edge_extraction.py` already handles the inversion correctly:
- DB export: `a REQUIRES b` means "a depends on b" → learner path: b → a
- Gold file: `source → target` means learner path: source → target  
- The inversion `(dst_l, src_l)` for REQUIRES export edges is correct.

### RELATED edges
RELATED edges are **correctly excluded** from prerequisite evaluation by default (`include_related=False`). An `--include-related` flag exists. RELATED edges are **not** converted to prerequisite dependencies.

### Cycle analysis under prerequisite-only semantics
`audit_relation_semantics()` in `compare_aligned.py` deduplicates DFS cycles via minimum-rotation canonicalisation and reports:

| Metric | Value |
|---|---|
| Raw DFS cycle count | 9 or 10 (non-deterministic) |
| **Unique cycles (deduplicated)** | **9** |
| Length-2 cycles (symmetric insertions from `librarian_upload`) | 8 |
| Length-6+ cycles (cross-paper semantic) | 1 |
| RELATED edges in cycle detection | **0** (excluded by design) |

The existing `structural_audit()` already builds a prerequisite-only graph (REQUIRES + UNLOCKS). There are no RELATED cycles because RELATED edges are not included in the cycle-detection adjacency list.

---

## Task E — Reproducible Evaluation

Both baseline and corrected results are written to `s4f_eval_results.json` by `run_s4f_eval.py`.

### S1–S4-F regression
```
84 passed in 5.97s
```
- 60 prior tests (S1–S4-E): all pass ✅
- 24 new S4-F tests: all pass ✅

### Scientific constraint verification
| Constraint | Status |
|---|---|
| Gold fixtures unchanged | ✅ read-only |
| Graph DB unchanged | ✅ `read_only=True` |
| Fuzzy threshold unchanged (90) | ✅ `FUZZY_MATCH_THRESHOLD = 90` |
| No cycles deleted | ✅ |
| No concepts inserted | ✅ |
| No extraction pipeline changes | ✅ |
| No metric artificially inflated | ✅ Edge F1 = 0.0 both docs |
| Original `compare_edges()` backward-compatible | ✅ (direction_accuracy field changed from 1.0→None) |

> [!WARNING]
> `direction_accuracy` field changed from `float` to `float | None` in `compare_edges()`. Any downstream code that compared `direction_accuracy == 1.0` as a success signal must be updated. The S4-E test was updated accordingly.

---

## Files Created / Modified

| File | Action |
|---|---|
| `okf/eval/gold/compare_aligned.py` | **New** — concept-aligned edge evaluator, direction accuracy guard, provenance scoping, relation semantics audit, corrected pipeline |
| `okf/eval/gold/part01_load_gold_graph.py` | **Modified** — Task B: direction_accuracy=None when denominator=0; added `direction_accuracy_status` and `direction_accuracy_denominator` fields |
| `research/s4-f-evaluator-repair/S4F_EVALUATOR_REPAIR_REPORT.md` | **New** — this report |
| `research/s4-f-evaluator-repair/s4f_eval_results.json` | **New** — machine-readable before/after metrics |
| `research/s4-f-evaluator-repair/scripts/run_s4f_eval.py` | **New** — reproducible evaluation script |
| `tests/unit/test_s4f_evaluator_repair.py` | **New** — 24 targeted unit tests |
| `tests/unit/test_s4e_graph_diagnosis.py` | **Modified** — updated `test_vacuous_direction_accuracy_reproduced` to assert corrected behaviour |

---

## Open Issues (not addressed in S4-F)

| Issue | Rationale for deferral |
|---|---|
| Edge F1 = 0.0 (genuine) | Requires extraction pipeline changes — out of scope for S4-F |
| 101 directed edges with invalid provenance | Requires human review of edge attribution — out of scope |
| 1,334 RELATED edges never evaluated | Adding `--include-related` flag exists; enabling by default is a scientific decision for S4-G |
| 9 graph cycles | Structural cleanup requires human curation — out of scope |
| 16 globally absent gold concepts per document | Requires re-ingestion — out of scope |

---

*Generated by S4-F evaluator repair process. No scientific results were modified.*
