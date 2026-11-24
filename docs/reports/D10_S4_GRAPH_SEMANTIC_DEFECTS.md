# D10-S4 graph semantic defects — candidate review

Runtime input: `host_inference/fixtures/okf_graph.json`, SHA-256 prefix `9818ac0e8fd3`. The exported graph is left intact. `LibraryGraph` records every suppressed edge in `quarantined_edges` before traversal, and the itemized source IDs and reasons are in `D10_S4_GRAPH_EDGE_QUARANTINE.csv` (54 rows). This review is limited to edges touching `rag` or `retrieval_augmented_generation`; the older 194 uncertain graph edges remain outside this decision.

## Confirmed defects

| Stored edge | Source ID | Problem | Candidate action |
|---|---|---|---|
| Retrieval-Augmented Generation `UNLOCKS` GPT-2 | `papers/Lewis2020_RAG.pdf:chunk_037` | GPT-2 predates RAG; the direction is historically impossible. | Quarantined |
| TriviaQA and Natural Questions `UNLOCKS` RAG / Retrieval-Augmented Generation | `papers/Lewis2020_RAG.pdf:chunk_019` | Evaluation datasets do not automatically constitute conceptual prerequisites. | Quarantined |
| GPT-2 `REQUIRES` RAG | `papers/Lewis2020_RAG.pdf:chunk_037` | Chronology and conceptual dependency are reversed. | Quarantined |
| Retrieval-Augmented Generation `UNLOCKS` language model, deep learning, GAN, LSTM, knowledge graph | See itemized CSV | Papers mention these concepts; mention does not prove an unlock relation. | Quarantined |
| Retrieval-Augmented Generation `RELATED` GPT-2 with subtype `uses` | `papers/Lewis2020_RAG.pdf:chunk_037` | Exact use claim lacks direct edge review. | Quarantined |

Every RAG-adjacent `REQUIRES` and `UNLOCKS` edge was checked. The candidate permits only the explicit specialization pairs `vector_rag → retrieval_augmented_generation` and `advanced_rag → rag` as `REQUIRES`, with their inverse `UNLOCKS` directions. Other RAG-adjacent dependency edges are withheld pending claim-level human review. For `RELATED`, literal `co_mention` is retained; stronger semantic subtypes are withheld. This is a cautious runtime filter, not a final graph adjudication.

The Transformer node's canonical candidate summary now describes the original encoder-decoder attention architecture and separates BERT's masked-language-model objective from GPT-style next-token pretraining. The erroneous exported summary remains available for audit. Its immediate source is the exported `transformer` node; `data/catalogs/batch12_ingestion_summary.json` also contains a similar conflated extraction summary. The exact upstream ingestion step that promoted it has not yet been proven.

The answer renderer now labels stored learning paths as pending edge review. Edge presence and endpoint citations are not claim entailment. The candidate graph uses a runtime overlay and therefore must be loaded through `LibraryGraph` for this quarantine to apply; a raw client of the JSON export can still see the original edges.

## Verification

`python3 -m pytest tests/unit/test_d10_s4_graph_semantics.py -q`: 2 passed. The tests assert the input JSON remains unchanged, the suspect RAG edges cannot enter prerequisites, unlocks or related concepts, and their original source IDs survive in the review record.
