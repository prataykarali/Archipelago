# SLM Extraction Eval — is `lib-qwen` ready for ingestion?

**Verdict: NO. Do not enable unattended SLM ingest.**

Reproduce:

```bash
python -m archipelago.eval.extract_eval          # report + gate, exit 1 if not ready
python -m archipelago.eval.extract_eval --json   # per-probe detail
```

---

## Measured 2026-10-02 — `lib-qwen:latest` (Qwen2.5-0.5B-Instruct, LoRA v44, Q8_0)

11 probes (`tests/fixtures/extraction_probes.jsonl`): 8 real passages, 3 negatives.

| Metric | Value | Gate | Result |
|--------|------:|------|--------|
| JSON valid | 100.0% | ≥ 95% | **PASS** |
| Schema OK (8-key contract) | 100.0% | ≥ 90% | **PASS** |
| **F1 (alias-aware)** | **0.125** (std 0.331, p95 0.650) | ≥ 0.35 | **FAIL** |
| Celebrity/person nodes | 0 | 0 | **PASS** |
| Empty-gold hit rate | 100.0% (n=3) | ≥ 40% | **PASS** |
| Self-references | 0 | ≤ 1 | **PASS** |
| Latency | mean 0.82 s, p95 1.44 s | — | fast |

**5/6 checks. `ready_for_pilot_ingest: False`.**

### Per-probe: only 1 of 8 real passages yields the right concept

| Probe | Gold | Predicted | F1 |
|-------|------|-----------|----:|
| LoRA | Low-Rank Adaptation | Low-Rank Adaptation | 1.00 |
| Linear algebra | Linear Algebra | Matrix | 0.00 |
| Adam | Adam | Adaptive Estimation | 0.00 |
| RAG | Retrieval-Augmented Generation | *(nothing)* | 0.00 |
| Transformer | Transformer | Self-Attention | 0.00 |
| Graph neural networks | Graph Neural Network | Convolutional Neural Network | 0.00 |
| Probability theory | Probability Theory | Random Experiment | 0.00 |
| LoRA (2nd passage) | Low-Rank Adaptation | Fine-Tuning | 0.00 |

---

## What the numbers mean

**The model is structurally sound and semantically weak.** It always emits valid,
schema-correct JSON; never invents a celebrity; and correctly stays silent on
bibliographies, front matter, and an index page. Those are real wins over the
v3 adapter noted in `NEXT_SESSION.md`.

But "valid JSON" was never the bar. The failure is **picking the central
concept of a passage rather than a plausible neighbouring one**. Every miss is
semantically *adjacent* — Matrix for linear algebra, Self-Attention for
Transformer, CNN for GNN, Random Experiment for probability. The model has the
vocabulary; it does not have the editorial judgement about what a passage is
*about*.

**It is also non-deterministic in judgement, not just in wording.** Two
near-identical LoRA passages produced *different wrong answers*
("Low-Rank Adaptation" vs "Fine-Tuning"). A model that changes its answer when
the input is rephrased cannot be trusted to write MERGE-d nodes into a graph
where a wrong node is effectively permanent.

### Why the alias-aware F1 matters

An earlier report showed 100% JSON validity alongside mean exact-match F1 of
0.252, which reads as "almost fine". It is not: that number was against a gold
set whose entries collapsed ambiguously, and it ignored acronym equivalence.
This harness scores `LoRA` ≡ `Low-Rank Adaptation` ≡
`Bidirectional Encoder Representations from Transformers` ≡ `BERT`, and treats
word order as irrelevant. Measured honestly, the score is **0.125**, not 0.25.

### The structural gate is genuinely green — keep it

Two of these behaviours must not regress, because they are what pollute a graph
permanently:

- **no person names** — concept nodes are MERGE-d, so a node called "Goodfellow"
  survives every rebuild until someone manually unpicks it and all its edges;
- **silence on non-prose** — a bibliography parsed as concepts injects dozens of
  phantom references.

Both currently pass at 100%. Any future fine-tune must hold them.

---

## Why the gate fails, and what would fix it

The training data is the root cause, and this matches the v3 diagnosis recorded
in `NEXT_SESSION.md` — it was never fixed, only carried forward. Inspecting
`training_data/okf_dataset_report_v5.json`:

- **37.96%** of pairs come from a single document (`Math_For_ML.pdf`, 197 of 519);
- **13.87%** have empty outputs — the model learned that declining is acceptable;
- 519 pairs / **385 unique chunks** for 100 optimizer steps, 1 epoch, final
  train loss 1.279 — one pass, no convergence.

The model learned the *style* of a single textbook's chunking. That is exactly
what "matrix, not linear algebra" looks like: the answer is locally reasonable
in the vocabulary it saw, but it is not the passage's thesis.

### To make it ready

1. **Rebuild the dataset around one concept per passage.** The gold above is the
   *central* concept; the training targets must be too. A passage naming five
   ideas should be trained to yield its thesis, with the rest as `related_to`.
2. **Balance provenance.** Cap any one document at ~5% of pairs (v5 is at 38%),
   and source across textbooks, papers, and syllabi.
3. **Cut the empty-output rate** to ≤10% (v5: 13.87%) so declining stays rare.
4. **Train to convergence** — 3+ epochs, evaluating alias F1 on the held-out
   split between runs rather than by final loss.
5. **Re-run the gate.** Ship only when `ready_for_pilot_ingest: True`.

`training_data/okf_test_pairs_v5.jsonl` and the harness are already in place, so
steps 1–5 are scriptable once the data is rebuilt.

---

## Interim guidance

Ingestion stays supervised and human-reviewed. The pipeline's existing
grounding filter is what makes the current SLM tolerable: it requires the concept
name to appear in the source passage and drops ungrounded records. That is a
correct safety net — but it is a net, not a fix, and it cannot rescue the
*centrality* failure, since an adjacent-but-grounded concept passes it.

**Recommended:** keep `lib-qwen` for candidate generation, keep the librarian
review step, and treat this metric as the release gate for removing that step.

---

## Provenance of the earlier claim

`PRODUCTION_READINESS_AND_PLATFORM_PLAN.md` §1 records "SLM verified ready —
no re-training required", based on a single smoke extraction returning "Stochastic
Gradient Descent". That smoke test passed, but a single-sample check cannot
detect a centrality or consistency failure, and this 11-probe harness shows
alias F1 of 0.125 with inconsistent answers across paraphrases. **The earlier
claim was wrong and is superseded by this report.**