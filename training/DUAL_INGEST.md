# Dual ingestion SLM training

Academic ingestion extracts the eight-key teachable-concept OKF. Research
ingestion extracts quote-backed scientific fields. They share one candidate
adapter but use distinct versioned prompts and output contracts.

## Dataset

`python -m training.build_multi_source_dual_ingest_dataset` fetches abstracts
from arXiv, OpenAlex, Crossref, and Europe PMC through the existing scholarly
source adapters or official APIs. It also records attempted Semantic Scholar
requests and their status. The local result is
`data/datasets/dual_ingest_multisource_v2/`.

The 2026-10-25 build contains 113 distinct papers and 678 examples: 474 train,
66 validation, and 138 test. The source mix is 35 arXiv, 35 OpenAlex, 8
Crossref, and 35 Europe PMC papers. Each paper supplies two variants of each
of three tasks: academic OKF, research abstract fields, and research quote
spans. Every variant from a paper stays in one split; the test split is never
read by training. The 15 arXiv seed papers have reviewed labels. Additional
labels are weak labels from literal title/abstract and explicit contribution,
method, or named-dataset evidence. Inspect `label_audit.jsonl` and
`manifest.json` before using a rebuilt set.

The dataset stores source URLs and hashes; it does not contain PDF files.
Crossref and Semantic Scholar rate limits are represented as source statuses,
not silently converted to empty results. All 452 research target rows in this
build pass the production quote and field validators.

## Train and score

```bash
python -m training.train_dual_ingest_qlora --dry-run
python -m training.train_dual_ingest_qlora
python -m scripts.eval_dual_ingest_candidate
```

The trainer fits a local 4-bit QLoRA adapter for
`Qwen/Qwen2.5-0.5B-Instruct` and writes it under
`models/dual_ingest_candidate_v2/`. It has no network reporting and does not
change the models used by running services. The evaluator scores untouched
papers by task with the production validators, reports the reviewed-label
subset separately, and runs the existing academic operational probes. The
adapter must pass both academic and research checks before it can replace a
running ingestion model.

The expanded 2026-10-25 dataset is
`data/datasets/dual_ingest_multisource_v3/`: 910 examples from the same 113
source papers, with 680 train, 92 validation, and the original 138 test
examples. The test split was copied byte for byte. It adds hard academic
negatives and focused source-literal research fields. The completed three-epoch
adapter is `models/dual_ingest_candidate_v3/`; its per-paper evaluation is
`held_out_eval.json` in that directory. A 138-row role-focused continuation
set in `data/datasets/dual_ingest_role_focus_v4/` was used for a two-epoch
adapter continuation; validation and test are unchanged.

To evaluate a continuation, use the original expanded dataset's test split:

```bash
python -m scripts.eval_dual_ingest_candidate \
  --dataset-dir data/datasets/dual_ingest_multisource_v3 \
  --adapter-dir models/dual_ingest_candidate_v4
```

Only after all gates pass, export an isolated local Ollama tag using
`training.export_dual_ingest_ollama`, then set
`ARCHIPELAGO_INGESTION_MODEL` for both local academic ingestion and the
research queue worker. Academic ingestion keeps its teachable-concept OKF
contract; research ingestion keeps the quote-backed field contract. The
Vercel research page sends work through the hosted queue to the local worker.
Its deployed job path currently stores metadata and abstract facts as
`METADATA_ONLY`, even when the separate local PDF pipeline can extract
page-linked fields. Do not describe those hosted records as full-text results.

The academic operational gate is the repository's `extract_eval` gate:
alias-aware F1 >= 0.35, JSON >= 95%, schema >= 90%, negative-passage empty
match >= 40%, and zero celebrity concepts. For research, require JSON >= 95%,
exact quote-verified field F1 >= 0.50 on untouched papers, no wrong field role
in a real-paper audit, and a nonempty, verified full-text result on an openly
accessible paper. A low training loss alone is not an ingestion pass.
