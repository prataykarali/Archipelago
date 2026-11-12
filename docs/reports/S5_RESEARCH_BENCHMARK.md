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
