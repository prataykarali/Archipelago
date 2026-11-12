# S5 research benchmark

Five required topics were fetched from live APIs on 2026-11-12 UTC. Each saved JSON contains provider status, retrieval time, paper IDs, provenance and ranking reasons. These are coverage diagnostics, not precision or NDCG claims: no independent relevance judgments have been collected.

| Topic | Candidates | Filtered | Top-K | DOI present | Verified in-set citations |
|---|---:|---:|---:|---:|---:|
| OCR and document understanding | 43 | 40 | 10 | 8 | 0 |
| Pedestrian detection | 43 | 43 | 10 | 6 | 5 |
| Bengali automatic speech recognition | 41 | 41 | 10 | 6 | 1 |
| Skin cancer image classification | 48 | 47 | 10 | 9 | 1 |
| Fake news detection | 37 | 37 | 10 | 10 | 10 |

All five top tens had abstracts. A repeated title in skin cancer corresponds to a preprint DOI and a journal DOI with matching authors; they remain separate records pending version review. Semantic Scholar rate limited these final runs. The live sample files are a human-reviewable queue, but no human has yet signed off on relevance, identity, author or venue judgments. Precision, recall, ranking quality and disambiguation accuracy are therefore **not measured**. Mocked unit tests verify filters, owner isolation, formula-safe Excel cells, graph edge rules and monitoring idempotency. Live and mocked evidence are separate.

## Required five-topic review queue

The existing live snapshots cover the five topics requested for S5-B. Reviewers can judge each paper's title, year, provider provenance and ranking reasons in the referenced JSON. These are candidate sets, not human labels.

| Topic | Snapshot | Candidates | Filtered | Selected | Human relevance labels |
|---|---|---:|---:|---:|---|
| Efficient retrieval-augmented generation | `efficient_rag.json` | 77 | 67 | 20 | PENDING |
| Continual learning | `continual_learning.json` | 76 | 76 | 20 | PENDING |
| Graph neural networks | `live-graph-neural-networks.json` | 63 | 62 | 20 | PENDING |
| OCR and document understanding | `ocr.json` | 43 | 40 | 10 | PENDING |
| Bengali ASR | `bengali_asr.json` | 41 | 41 | 10 | PENDING |

Precision@K, nDCG@K and deduplication precision remain **PENDING** until independent judgments and duplicate labels are recorded. No score is inferred from result counts.
