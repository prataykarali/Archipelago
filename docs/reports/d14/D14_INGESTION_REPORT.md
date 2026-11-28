# Archipelago D14.1 — Corpus Reconstruction & Ingestion Report (`corpus_v3_d14`)

- **Corpus Version:** `corpus_v3_d14`
- **Parent Baseline Preserved Untouched:** `corpus_v2_d10_3025` (Manifest SHA-256: `9965352d75840a802e47a50cdc8a434815005c26ca79e2eda00842f394d35dbf`, Passage JSONL SHA-256: `93f6db39cb10d03beeb41c48469d138be27b62ed90aa59d20dd4c5107fbb2e52`)
- **Output Passage JSONL (gitignored):** `data/artifacts/corpus_v3_d14/d14_candidate_passages_v3.jsonl`
- **Output Passage JSONL SHA-256:** `6fe7f4d8cc27a91ebbf2e86c55267a661adf36f81425ed0cb7ab17c5f7ec4ffc`
- **Ingested Full-Text Documents:** `68` (41 re-extracted from `corpus_v2_d10_3025` + 27 newly acquired OA sources)
- **Excluded Commercial / Metadata-Only Holdings:** `12` (blocked deterministically by `archipelago.corpus.license_gate`)
- **Validated Body Passages:** `11768` (total words: `2,441,002`, mean words/passage: `207.43`)
- **Domains Meeting >=2 Independent Authoritative OA Sources:** `12/12`

---

## 1. Before vs. After 12-Domain Full-Text Coverage Matrix

| Domain | Baseline v2 Docs | Baseline v2 Passages | D14 v3 Docs | D14 v3 Indep. Sources | D14 v3 Passages | Excluded Commercial | >=2 Sources? |
|---|---:|---:|---:|---:|---:|---:|:---:|
| Operating Systems | 17 | 482 | 19 | 3 | 781 | 2 | YES |
| Database Systems | 0 | 0 | 2 | 2 | 223 | 1 | YES |
| Data Structures & Algorithms | 0 | 0 | 2 | 2 | 1145 | 1 | YES |
| Computer Networks | 0 | 0 | 3 | 3 | 455 | 1 | YES |
| Compiler Design | 0 | 0 | 3 | 3 | 1478 | 1 | YES |
| Automata Theory | 0 | 0 | 2 | 2 | 725 | 1 | YES |
| Mathematics for ML | 1 | 775 | 2 | 2 | 1213 | 0 | YES |
| Probability & Statistics | 0 | 0 | 2 | 2 | 1058 | 1 | YES |
| Information Security | 0 | 0 | 4 | 4 | 868 | 1 | YES |
| AI & Machine Learning | 25 | 1768 | 24 | 24 | 1985 | 1 | YES |
| Software Engineering | 0 | 0 | 3 | 3 | 887 | 1 | YES |
| Computer Architecture | 0 | 0 | 2 | 2 | 950 | 1 | YES |

---

## 2. Structural Noise Filtering & Extraction Quality

- **Filtered Table of Contents (TOC) units/chunks:** `43`
- **Filtered References / Bibliography units/chunks:** `113`
- **Filtered Back-of-Book Index units/chunks:** `71`
- **Filtered Front Matter / Copyright stubs:** `3`
- **Filtered Low-Quality / Tiny fragments:** `1144`
- **Filtered Exact Normalized Duplicates:** `8`
- **Passages with Mapped Printed Page Labels:** `11583`
- **Concept-Linked Passages (`okf_graph.json` read-only match):** `8632`
- **Lexical Vocabulary Size:** `46,150` terms

---

## 3. Acquisition Gaps, Failures & Legal Restrictions

All authorized open-access sources were acquired and validated with zero download failures.

### Quality-Filtered Legacy Baseline PDFs (2 of 43 baseline PDFs)
- `books/papers/Rumelhart1986_Backpropagation.pdf`: Image-only scanned PDF with 0 extractable native text units (`extracted_units=0`, `kept_passages=0`). Excluded rather than emitting empty/OCR-corrupted chunks.
- `books/papers/LeCun1998_ConvNets.pdf`: Legacy 1998 IEEE Type-3 font encoding failing printable/alpha extraction quality validation across all 46 pages (`extracted_units=46`, `filtered_noise_units=46`, `kept_passages=0`). Excluded from `corpus_v3_d14` to prevent corrupted text pollution.

### Legal Compliance & Isolation
- Zero commercial textbooks (CLRS, Tanenbaum, Dragon Book, Silberschatz, Hopcroft, Sommerville, Ross, Stallings, Russell & Norvig, Mano, or UEM Pearson eLibrary holdings) were downloaded, extracted, or promoted to full-text passages.
- `docs/reports/D10_S4_CANDIDATE_PASSAGE_MANIFEST.json` (`corpus_v2_d10_3025`) and `host_inference/fixtures/okf_graph.json` (`graph_v1_okf610`) were read read-only and remain byte-identical.
- Raw downloaded PDFs/HTMLs/RFCs and `d14_candidate_passages_v3.jsonl` reside under `data/artifacts/corpus_v3_d14/` (gitignored per `.gitignore` line 143).
