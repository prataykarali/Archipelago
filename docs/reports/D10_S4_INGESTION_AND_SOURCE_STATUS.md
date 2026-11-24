# D10-S4 ingestion and source status

Candidate base: `bcb4989cbd72f47e66785e40cc76a8815c9e4668`. The final code revision is recorded in `D10_S4_FINAL_GO_HOLD.md`. The frozen held-out benchmark and remote datasets were not changed.

## Inventory and revision

Read-only Hugging Face inspection found `Prataykarali/Library_books` at `b0561c76a4c5a7a8cb1fe3bd91b389280d504cbd` (175 repository files) and `Prataykarali/graphier` at `86e29828c38dbf0f8cea5d50ed6a341ccde3a8f3` (151 files). The canonical rights-approved inventory contains 43 reader-backed PDFs: 25 papers, 17 OSTEP chapters, and one Deisenroth textbook. Mirrors, research artifacts, and test uploads were excluded.

The candidate's packaged `host_inference/fixtures/okf_graph.json` is byte-identical to `graph/okf_graph.json` at the inspected graphier revision: SHA-256 `9818ac0e8fd30e2e94afef67677267c0dfde09e9b87e83be7a582cd8bae42f76`, 610 nodes, 1,988 edges. Its source records mention 24 distinct paper document names and only three OSTEP chapters. Document-name presence does not prove complete body extraction or claim support. The 194 earlier uncertain semantic edges remain unapproved; the D10-S4 runtime quarantine additionally suppresses 54 questionable RAG-adjacent edge assertions and records them separately.

## Deterministic candidate passages

`scripts/ops/build_d10_candidate_passages.py` downloads the 43 approved originals at the pinned library revision, verifies remote LFS SHA-256 when available, hashes every downloaded PDF, and extracts page-confined fixed-size passages. Its local output `/tmp/archipelago_d10_s4_candidate_passages.jsonl` contains 3,025 passages and has SHA-256 `93f6db39cb10d03beeb41c48469d138be27b62ed90aa59d20dd4c5107fbb2e52`. The committed `D10_S4_CANDIDATE_PASSAGE_MANIFEST.json` contains document checksums and counts, not source text. One source lacked a remotely reported LFS checksum; its downloaded bytes were still hashed locally and that limitation is explicit in the manifest.

Each passage records the original document ID, PDF SHA-256, one-based physical page, zero-based PDF page index, printed page label when explicitly present, text offsets, and a stable passage ID. The catalog loader reads this optional index from `ARCHIPELAGO_CANDIDATE_PASSAGES`; thus the body chunks are available to the candidate answering pipeline when launched with the index attached. The original D10 base-and-bounds query now returns OSTEP PDF page 7 and passage `38d81af0ae91:p7:c0` instead of a GPT-3 paper. The index remains local because it contains source text. It has not been deployed or published to HF.

The shared PDF ingestion path also fixes `get_page_labels()` handling: PyMuPDF returns label rules, so each physical page is now resolved through `Page.get_label()` only when the PDF has explicit labels. New PDF ingestion chunks include `pdf_page_index` and `printed_page`. Synthetic tests cover Roman front matter and unlabeled PDFs.

No `lib-qwen` concept or edge predictions were promoted. Pearson remains catalogue-only, with authenticated book-level redirects and no invented page citation.

## Remaining limitations

This is a candidate passage index, not a rebuilt semantic graph. Only catalog and explicit audited source routes consume its body chunks; other graph routes still use the packaged graph's existing source passages. The candidate code must be launched with `ARCHIPELAGO_CANDIDATE_PASSAGES` pointing to the verified local JSONL file. A hosted staging run, authenticated reader redirects, and human claim-support review remain required before release.
