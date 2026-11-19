# Bibliography Audit (`references.bib`)

**Source File:** `research/s5-e0-pre-results-paper-prep/E03_VERIFIED_REFERENCES.bib`  
**Output File:** `research/s5-e0-pre-results-paper-prep/manuscript/references.bib`  
**Audit Summary:**
- **Total source entries inspected:** 26
- **Entries retained in `references.bib`:** 26
- **Entries excluded:** 0
- **Entries flagged for non-archival / preprint status:** 2 (`merrick2024arctic`, `edge2024local`)
- **Entries with arXiv eprints accompanying archival NeurIPS proceedings:** 2 (`thakur2021beir`, `gutierrez2024hipporag`)

---

## Audit Policy

1. Only references with confirmable author lists, exact titles, publication years, venues, and authoritative persistent identifiers (DOI or arXiv identifier) are retained.
2. Zero references were invented, guessed, or added beyond the verified 26-entry bibliography.
3. Preprints without archival peer-reviewed proceedings are explicitly flagged so the author can update them if archival versions are published before final camera-ready submission.
4. Internal Archipelago artifacts (manifests, scripts, audit reports) are cited by repository path and SHA-256 hash rather than external BibTeX entries.

---

## Entry-by-Entry Audit Table

| # | BibTeX Key | Type | Year | Identifier | Audit Verdict | Flag / Note |
|---|---|---|---|---|---|---|
| 1 | `robertson1994some` | `@inproceedings` | 1994 | DOI `10.1007/978-1-4471-2099-5_24` | **RETAINED** | Archival SIGIR '94 proceedings |
| 2 | `robertson2009probabilistic` | `@article` | 2009 | DOI `10.1561/1500000019` | **RETAINED** | Archival FnTIR monograph |
| 3 | `trotman2014improvements` | `@inproceedings` | 2014 | DOI `10.1145/2682862.2682863` | **RETAINED** | Archival ADCS '14 proceedings |
| 4 | `reimers2019sentence` | `@inproceedings` | 2019 | DOI `10.18653/v1/D19-1410` | **RETAINED** | Archival EMNLP-IJCNLP 2019 |
| 5 | `karpukhin2020dense` | `@inproceedings` | 2020 | DOI `10.18653/v1/2020.emnlp-main.550` | **RETAINED** | Archival EMNLP 2020 |
| 6 | `thakur2021beir` | `@inproceedings` | 2021 | arXiv `2104.08663` | **RETAINED** | Archival NeurIPS 2021 Datasets & Benchmarks (arXiv identifier; add OpenReview/NeurIPS URL if required by target venue) |
| 7 | `merrick2024arctic` | `@misc` | 2024 | arXiv `2405.05374` | **RETAINED (FLAGGED)** | **Preprint:** Technical report for Snowflake Arctic-Embed; confirm whether an archival venue version exists prior to submission |
| 8 | `cormack2009reciprocal` | `@inproceedings` | 2009 | DOI `10.1145/1571941.1572114` | **RETAINED** | Archival SIGIR '09 proceedings |
| 9 | `luan2021sparse` | `@article` | 2021 | DOI `10.1162/tacl_a_00369` | **RETAINED** | Archival TACL journal |
| 10 | `bruch2023analysis` | `@article` | 2023 | DOI `10.1145/3596512` | **RETAINED** | Archival ACM TOIS journal |
| 11 | `xiong2017explicit` | `@inproceedings` | 2017 | DOI `10.1145/3038912.3052558` | **RETAINED** | Archival WWW '17 proceedings |
| 12 | `dietz2018utilizing` | `@inproceedings` | 2018 | DOI `10.1145/3209978.3210187` | **RETAINED** | Archival SIGIR '18 tutorial/proceedings |
| 13 | `yasunaga2021qagnn` | `@inproceedings` | 2021 | DOI `10.18653/v1/2021.naacl-main.45` | **RETAINED** | Archival NAACL-HLT 2021 |
| 14 | `edge2024local` | `@misc` | 2024 | arXiv `2404.16130` | **RETAINED (FLAGGED)** | **Preprint:** GraphRAG technical report; confirm whether an archival venue version exists prior to submission |
| 15 | `gutierrez2024hipporag` | `@inproceedings` | 2024 | arXiv `2405.14831` | **RETAINED** | Archival NeurIPS 2024 proceedings (arXiv identifier; add NeurIPS proceedings page range if required by target venue) |
| 16 | `yang2018hotpotqa` | `@inproceedings` | 2018 | DOI `10.18653/v1/D18-1259` | **RETAINED** | Archival EMNLP 2018 |
| 17 | `min2019compositional` | `@inproceedings` | 2019 | DOI `10.18653/v1/P19-1416` | **RETAINED** | Archival ACL 2019 |
| 18 | `ho2020constructing` | `@inproceedings` | 2020 | DOI `10.18653/v1/2020.coling-main.580` | **RETAINED** | Archival COLING 2020 |
| 19 | `trivedi2022musique` | `@article` | 2022 | DOI `10.1162/tacl_a_00475` | **RETAINED** | Archival TACL journal |
| 20 | `cohen1968weighted` | `@article` | 1968 | DOI `10.1037/h0026256` | **RETAINED** | Archival Psychological Bulletin |
| 21 | `zobel1998reliable` | `@inproceedings` | 1998 | DOI `10.1145/290941.291014` | **RETAINED** | Archival SIGIR '98 proceedings |
| 22 | `voorhees2000variations` | `@article` | 2000 | DOI `10.1016/S0306-4573(00)00010-8` | **RETAINED** | Archival Information Processing & Management |
| 23 | `jarvelin2002cumulated` | `@article` | 2002 | DOI `10.1145/582415.582418` | **RETAINED** | Archival ACM TOIS journal |
| 24 | `buckley2004retrieval` | `@inproceedings` | 2004 | DOI `10.1145/1008992.1009000` | **RETAINED** | Archival SIGIR '04 proceedings |
| 25 | `sakai2016statistical` | `@inproceedings` | 2016 | DOI `10.1145/2911451.2911492` | **RETAINED** | Archival SIGIR '16 proceedings |
| 26 | `faggioli2023perspectives` | `@inproceedings` | 2023 | DOI `10.1145/3578337.3605136` | **RETAINED** | Archival ICTIR '23 proceedings |

---

## Excluded Entries

None. All 26 entries from `E03_VERIFIED_REFERENCES.bib` carry confirmable bibliographic metadata and persistent identifiers.
