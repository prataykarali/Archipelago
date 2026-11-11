# Dual ingestion dataset, QLoRA training, and held-out evaluation

## Decision

The locally trained candidate is **not ready for unattended ingestion**. It
improves on the earlier tiny adapter for some research cases, but neither the
academic operational negative-passage gate nor the research field F1 gate
passes. It was not activated in the running services.

## Dataset snapshot

`data/datasets/dual_ingest_multisource_v2/` contains 678 examples from 113
distinct real papers. All prompt variants from a paper stay in the same split.

| Source | Papers |
| --- | ---: |
| arXiv | 35 |
| OpenAlex | 35 |
| Crossref | 8 |
| Europe PMC | 35 |
| **Total** | **113** |

There are 79 train papers (474 examples), 11 validation papers (66 examples),
and 23 test papers (138 examples). Each paper contributes two variants of the
academic OKF task, two research abstract examples, and two research quote-span
examples. Semantic Scholar returned HTTP 429 without a configured API key;
Crossref also rate limited one query. Those statuses are recorded in
`manifest.json`.

The original 15 arXiv papers have reviewed labels. The additional labels are
source-grounded but weak: a title/abstract concept, an explicit contribution
sentence, a method phrase in method context, or a named dataset in evaluation
context. Their source URL, abstract hash, and fields are in
`label_audit.jsonl`. All 452 research targets in the snapshot pass the same
quote and field validators used at inference time. Weak labels are incomplete;
an output can be source-supported yet absent from the gold list.

## Training

- One local QLoRA adapter for `Qwen/Qwen2.5-0.5B-Instruct`, 4-bit NF4,
  LoRA rank 8, two epochs, completion-only loss.
- 474 train rows; 66 validation rows; **zero test rows used in training**.
- Final train loss **0.0647**; validation loss **0.0729**. Peak GPU memory
  **1,527 MiB** on an RTX 2050 with 4 GiB VRAM.
- Adapter and the complete training metadata are under
  `models/dual_ingest_candidate_v2/`.

## Held-out model scores

These are exact field-value scores after the production evidence validators,
not training accuracy. Each task has 46 examples from 23 held-out papers; the
two variants of each paper are correlated.

| Task | Exact F1 mean | F1 std | JSON rate | Other |
| --- | ---: | ---: | ---: | --- |
| Academic OKF | 0.609 | 0.488 | 93.5% | Schema-valid 84.8% |
| Research abstract | 0.330 | 0.443 | 100% | Verified nonempty 89.1%; field-role F1 0.428 |
| Research quote spans | 0.123 | 0.279 | 95.7% | Verified nonempty 47.8%; field-role F1 0.152 |

Across the four independently reviewed test papers (eight variants per task),
academic F1 was **0.875**, research abstract F1 **0**, and research quote-span
F1 **0.125**. Academic performance on the repository's 11 operational probes
was **0.636 F1** (std 0.481); all three negative passages wrongly produced a
concept, so the empty-passage match rate was **0%**. The candidate fails the
academic gate despite its paper-concept score.

Source-specific exact F1 exposes the domain shift:

| Source | Academic | Research abstract | Research quote spans |
| --- | ---: | ---: | ---: |
| arXiv | 0.563 | 0.125 | 0.146 |
| OpenAlex | 0.722 | 0.519 | 0.111 |
| Crossref | 0.500 | 0.361 | 0 |
| Europe PMC | 0.500 | 0.278 | 0.222 |

The earlier 54-row adapter scored 1.0 academic F1 and 0 research F1 on its
four-paper held-out set. The new adapter has broader coverage, but the
reviewed-paper research result remains poor. On QA-LoRA the new model still
proposed `LLaMA` as a dataset; the semantic validator correctly rejected it.
It also returned a source-supported contribution that the narrow reviewed
gold label omitted. Both the rejected candidate and accepted facts are visible
in `held_out_eval.json`.

## Real full-text paper check

The open [LoRA paper](https://arxiv.org/abs/2106.09685) parsed as a 26-page
PDF. The deterministic path produced four claims and a GLUE dataset reference,
with valid page-linked provenance. It produced **zero structured experiments
and zero results**, despite experimental tables in the paper. The local
full-text SLM call did not yield parseable JSON, so it contributed no
quote-verified fields in this check. Its Ollama response reached the 500-token
generation limit inside a fenced JSON block (`done_reason=length`). Sampled
candidate quotes also contained ellipses in place of literal source text and
would fail quote verification even if the JSON completed. This is a separate
gap from the abstract-derived test examples above.

After changing the local PDF SLM extractor to use six individual page-linked
spans, the same real 26-page LoRA PDF still produced **zero** fields accepted
by the exact quote/page/role validator with the currently active
`qwen3.5:0.8b` model. This removes the previous multi-span truncation as the
sole explanation; full-text performance remains unproven.

## Expanded dataset and second training run

The source-backed dataset was expanded to 910 examples while preserving the
same 138-example, 23-paper held-out test split byte for byte. The expanded
split has 680 train and 92 validation examples. Added examples target academic
negative passages and research fields whose values appear literally in the
source. The new examples are under
`data/datasets/dual_ingest_multisource_v3/`; they are local artifacts, not PDF
files committed to the repository.

A second three-epoch QLoRA run finished under
`models/dual_ingest_candidate_v3/` with train loss 0.0495 and validation loss
0.0781. Its held-out scores are:

| Task | Exact F1 mean | F1 std | JSON rate | Other |
| --- | ---: | ---: | ---: | --- |
| Academic OKF | 0.612 | 0.477 | 100% | Schema-valid 89.1% |
| Research abstract | 0.261 | 0.409 | 89.1% | Verified nonempty 80.4%; field-role F1 0.424 |
| Research quote spans | 0.220 | 0.389 | 100% | Verified nonempty 43.5%; field-role F1 0.249 |

The academic operational probes improved to 0.727 mean F1 and 66.7% correct
empty responses on the three negative passages. The research result still
fails the activation gate. On four reviewed test papers, the abstract task
has zero exact F1 and quote spans have 0.1 exact F1. The model often emits a
generic contribution when the held-out label calls for a named algorithm or
model architecture. Source-grounded extra fields also count against the narrow
weak labels, so the metric needs case-level interpretation; it is not a reason
to ignore the reviewed-paper failure.

The role-focused continuation from v3 finished two more QLoRA epochs on 138
training examples (36 single-role research examples) with the same 92
validation and 138 test examples held apart. It used zero test rows for
training. Its train loss was 0.0359, validation loss 0.0844, and peak GPU
memory 1,525 MiB. The higher validation loss is a reason to rely on the
held-out task scores rather than the lower training loss.

## Pipeline integration status

The normal academic PDF-to-OKF path now has an explicit shared-model branch.
When `ARCHIPELAGO_INGESTION_MODEL` names an evaluated Ollama tag, it uses the
same versioned academic prompt as training and keeps the existing eight-key
concept OKF output. The research queue worker resolves that setting at request
time, reports the selected tag in its heartbeat and job summary, and refuses
to claim new work if the tag is absent. Research uses separate abstract-field
and PDF quote-field prompts and validators.

The deployed Vercel research page already enqueues Supabase jobs that the
local GPU worker polls. A read-only check of a completed hosted job found 25
saved paper OKFs from OpenAlex and Crossref. All 25 were explicitly marked
`METADATA_ONLY`; this deployed queue path currently extracts abstract facts,
not legally acquired full-text PDF facts. A full PDF contract exists locally
but is not yet part of that hosted queue flow. An abstract-only result must not
be described as complete research PDF ingestion.

## Verification and limitations

- 22 focused ingestion and research tests passed.
- Ruff and targeted strict mypy passed for the new code.
- The repository quality gate passed 6/7 checks. Its strict-type pass still
  reports the existing 758-error baseline across unrelated repository code.
- The test set is paper-isolated but small, and most labels are weak or
  incomplete. The exact F1 numbers are conservative for legitimate extra
  fields, while the verified-nonempty rate alone cannot establish semantic
  correctness.
- The academic path keeps its eight-key OKF contract. The research abstract
  and full-text paths use separate field contracts and prompts. The adapter
  has not replaced either running model.
