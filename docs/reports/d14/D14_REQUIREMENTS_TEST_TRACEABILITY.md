# D14 Requirements-to-Test Traceability Matrix

- **Phase:** D14.0 — Forensic Audit & Baseline Freeze
- **Owner:** `d14-forensic-audit`
- **Date:** 2026-11-28
- **Source Register:** `docs/reports/d14/D14_CONSOLIDATED_DEFECT_REGISTER.csv` (68 explicit defects + 1 reconciliation row accounting for recurring symptoms within the 93 D13 author observations across 36 queries / 12 domains)

---

## 1. Phase-Level Requirements & Defect Traceability (`D14.1`–`D14.8`)

| Phase | Owner | Requirement Summary | Mapped Defect IDs | Root-Cause Categories Covered | Target Automated Tests | Exit Criteria |
|---|---|---|---|---|---|---|
| **D14.1** Corpus Coverage & Ingestion | `d14-corpus-ingestion` | Expand open-access full-text coverage across all 12 tested domains (or explicit abstention where unavailable); strictly separate metadata/catalogue cards from full-text passages; emit versioned D14 corpus manifest without mutating the frozen 43-doc / 3,025-passage baseline. | `D14-DEF-001`, `D14-DEF-002` | `missing document/insufficient coverage`, `uningested doc` | `tests/unit/test_d14_corpus_coverage.py`, `tests/unit/test_d14_corpus_metadata_separation.py` | Frozen baseline SHA `93f6db39...e52` unchanged; versioned D14 corpus manifest verified; zero metadata-only records promoted as full-text passages. |
| **D14.2** OKF Graph & Concept Resolution | `d14-okf-graph` | Fix over-coarsened concept resolution (SVD, GAT, KL/VI, LALR, DDPM) and multi-concept anchor binding; close concept coverage gaps (RSA, TLS, Pumping Lemma, SE, COA) in a versioned D14 graph; quarantine/remove all 9+ invalid pedagogical/cross-domain edges; eliminate placeholder descriptions (`"X is a fundamental concept"`) and extraction artifacts (`"Equation Only"`). | `D14-DEF-003` – `D14-DEF-020` (18 defects) | `wrong concept resolution`, `missing document/insufficient coverage`, `invalid graph relationship`, `failed extraction` | `tests/unit/test_d14_okf_graph_resolution.py`, `tests/unit/test_d14_okf_graph_multi_anchor.py`, `tests/unit/test_d14_okf_graph_coverage.py`, `tests/unit/test_d14_okf_graph_semantics.py`, `tests/unit/test_d14_okf_graph_hygiene.py` | Frozen 610-concept / 1,988-edge graph (`9818ac0e8fd3...`) untouched; 0 invalid edges from D13 register remain in D14 graph; 0 placeholder/artifact nodes. |
| **D14.3** Retrieval, Domain Routing & Context Hygiene | `d14-retrieval-nlu` | Enforce domain-aware retrieval filtering (no DPO/GAN/VAE for Compiler IR, Bayes, MLE, or Networking); penalize bibliography/TOC/results pages for definition/derivation queries (OSTEP Paging, GAT Sec 2.1, Deisenroth SVD/PCA); reset retrieval context on topic shifts to eliminate multi-turn context contamination. | `D14-DEF-021` – `D14-DEF-028` (8 defects) | `irrelevant passage retrieval`, `wrong domain classification`, `context contamination` | `tests/unit/test_d14_retrieval_nlu_domain_guard.py`, `tests/unit/test_d14_retrieval_nlu_passage_quality.py`, `tests/unit/test_d14_retrieval_nlu_context_reset.py`, `tests/unit/test_d12_retrieval_nlu.py` | 0 cross-domain ML/DPO/OS leaks on 36Q dev suite; top-k passages for OSTEP Paging and GAT exclude bibliography/results-only pages; multi-turn shift test passes. |
| **D14.4** Scientific & Mathematical Correctness | `d14-synthesis-math` | Enforce math/technical verification & grounding guards across GAT worked examples (dimensionality + softmax arithmetic), DPO (no separate reward model), Gaussian MLE (constants + `1/n` vs `1/(n-1)`), KL divergence, PCA, SVD (no false abstention when in source), OSTEP Paging & Base-and-Bounds, Dijkstra non-negative weights, LALR valid CFG notation, Compiler IR semantic analysis, OSI L1/L2 & CRC detection, TCP separation, Automata language hierarchy, DB ACID isolation levels, and honest abstention for unavailable NIDS paper. | `D14-DEF-029` – `D14-DEF-044` (16 defects) | `wrong math/technical generation`, `wrong fallback status`, `unsupported citation` | `tests/unit/test_d14_synthesis_math_gat.py`, `tests/unit/test_d14_synthesis_math_dpo.py`, `tests/unit/test_d14_synthesis_math_prob.py`, `tests/unit/test_d14_synthesis_math_linalg.py`, `tests/unit/test_d14_synthesis_math_os.py`, `tests/unit/test_d14_synthesis_math_cs.py`, `tests/unit/test_d14_synthesis_math_abstention.py` | 100% pass on mathematical/technical invariant assertions and abstention guards; zero fabricated claims for unavailable papers. |
| **D14.5** Source Navigation, Reader & Provenance | `d14-reader-provenance` | Block broken `/read` links for unavailable PDFs (Tanenbaum); eliminate empty-href `/chat` redirects across all surfaces; restrict `'Verified'` badges strictly to provenance-backed full-text docs; deduplicate source cards; replace raw filenames with canonical titles; align physical PDF vs printed page offsets and OSTEP chapter numbers; enforce single-source-of-truth synchronization between chat answer grounding text and Inspector provenance status. | `D14-DEF-045` – `D14-DEF-052` (8 defects) | `broken source navigation`, `unsupported citation`, `wrong doc-to-passage mapping`, `UI/accessibility defect` | `tests/unit/test_d14_reader_provenance_links.py`, `tests/unit/test_d14_reader_provenance_badges.py`, `tests/unit/test_d14_reader_provenance_dedup.py`, `tests/unit/test_d14_reader_provenance_titles.py`, `tests/unit/test_d14_reader_provenance_pages.py`, `tests/unit/test_d14_reader_provenance_sync.py` | Zero 404/missing-doc links, zero `/chat` self-redirects, 100% answer-vs-Inspector provenance agreement, `host_inference/ui/` <-> `ui/chat/` mirror clean. |
| **D14.6** UX, Follow-Ups & Fallback Hygiene | `d14-ux-followups` | Domain-lock follow-up pills (fix RSA, TLS, Pumping Lemma, SE, COA, Compiler, DPO irrelevant pills) and filter out unavailable-doc prompts; fix deterministic fallback echo/misleading `"general explanation"` claim; fix OS topic browser listing Chain-of-Thought/RNNs; reset right-hand Inspector state atomically on every turn. | `D14-DEF-053` – `D14-DEF-062` (10 defects) | `invalid follow-up`, `wrong fallback status`, `wrong domain classification`, `UI/accessibility defect` | `tests/unit/test_d14_ux_followups_relevance.py`, `tests/unit/test_d14_ux_followups_fallback.py`, `tests/unit/test_d14_ux_followups_topic_browser.py`, `tests/unit/test_d14_ux_followups_inspector_state.py` | 0 cross-domain follow-ups on 36Q dev set; 0 AI concepts under OS topic browser; Inspector resets cleanly on turn switch. |
| **D14.7** Streaming, Auth Lifecycle & Latency | `d14-streaming-perf` | Eliminate 60s mid-stream and zero-byte timeouts via bounded TTFT + end-to-end deadlines; prevent mid-sentence truncation (e.g., `"Page Tables"`); fix stuck Stop button and permanent `"Pending completion"` status; resolve live user auth & chat-hang regressions (slow sign-in after sign-out, stuck chat, `/chat` failing to open). | `D14-DEF-063` – `D14-DEF-068` (6 defects) | `incomplete generation/truncation`, `wrong latency/execution metadata`, `UI/accessibility defect` | `tests/unit/test_d14_streaming_perf_timeouts.py`, `tests/unit/test_d14_streaming_perf_truncation.py`, `tests/unit/test_d14_streaming_perf_state_machine.py`, `tests/unit/test_d14_streaming_perf_auth_lifecycle.py`, `tests/unit/test_d14_streaming_perf_chat_load.py` | Zero stuck Stop/Pending states; auth boundary tests (401/200) and sign-out -> sign-in lifecycle <= 3s; `/chat` non-blocking load verified. |
| **D14.8** Independent Verification & Benchmark Integrity | `d14-independent-verifier`, `d14-benchmark-integrity` | Independently verify all 36 D13 dev/regression queries and reconcile the 93-observation total (`D14-DEF-RECON`); run dual evaluation on frozen baseline (610 concepts / 3,025 passages / 43 docs) vs D14 versioned artifacts; certify zero leakage/modification of 50 held-out queries and 731-item human judgment pool. | `D14-DEF-RECON` + all 68 explicit defects | All 17 taxonomy categories | `tests/e2e/test_d14_36q_regression.py`, `docs/reports/d14/D14_VERIFICATION_REPORT.md` | Independent pass report with zero production edits by verifier; zero benchmark contamination; UEM production & manuscript dirs verified untouched. |

---

## 2. Root-Cause Taxonomy Coverage Summary

| Root-Cause Category | Explicit Defect Count | Primary Phase / Owner |
|---|---:|---|
| `wrong math/technical generation` | 14 | D14.4 (`d14-synthesis-math`) |
| `invalid graph relationship` | 9 | D14.2 (`d14-okf-graph`) |
| `invalid follow-up` | 7 | D14.6 (`d14-ux-followups`) |
| `wrong concept resolution` | 6 | D14.2 (`d14-okf-graph`) |
| `irrelevant passage retrieval` | 6 | D14.3 (`d14-retrieval-nlu`) |
| `incomplete generation/truncation` | 3 | D14.7 (`d14-streaming-perf`) |
| `unsupported citation` | 3 | D14.4 / D14.5 (`d14-synthesis-math`, `d14-reader-provenance`) |
| `broken source navigation` | 3 | D14.5 (`d14-reader-provenance`) |
| `UI/accessibility defect` | 3 | D14.5 / D14.6 / D14.7 |
| `missing document/insufficient coverage` | 2 (+1 recon) | D14.1 / D14.2 (`d14-corpus-ingestion`, `d14-okf-graph`) |
| `failed extraction` | 2 | D14.2 (`d14-okf-graph`) |
| `wrong domain classification` | 2 | D14.3 / D14.6 (`d14-retrieval-nlu`, `d14-ux-followups`) |
| `wrong fallback status` | 2 | D14.4 / D14.6 (`d14-synthesis-math`, `d14-ux-followups`) |
| `wrong doc-to-passage mapping` | 2 | D14.5 (`d14-reader-provenance`) |
| `wrong latency/execution metadata` | 2 | D14.7 (`d14-streaming-perf`) |
| `uningested doc` | 1 | D14.1 (`d14-corpus-ingestion`) |
| `context contamination` | 1 | D14.3 (`d14-retrieval-nlu`) |
| **Total** | **68 explicit (+1 reconciliation row for 93 total observations)** | **All 8 D14 phases covered** |

---

## 3. Reconciliation Note on 93 Author Observations

No standalone 93-row D13 defect CSV/JSON file exists on disk outside the 70 browser screenshots captured on `2026-11-28` (`06:20`–`07:35` in `/home/pratay-karali/Pictures/Screenshots/`) and the 36-query reference files (`docs/sigir/D10_S3_ANSWERING_BEFORE_AFTER_36Q.csv`). All 66 explicit D13 defects from the author brief plus the 2 live user auth/chat-hang bugs (68 total) are individually registered and traced above; the remaining ~25 observations represent recurring manifestations of these exact root causes across the 36 queries and are explicitly tracked as `D14-DEF-RECON` (`PENDING_AUTHOR_LOG_RECONCILIATION`) to be verified across all 36 queries in Phase D14.8.
