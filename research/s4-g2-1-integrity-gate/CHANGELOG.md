# S4-G2.1 Human Annotation Pool Verification Changelog

**Audit Date:** 2026-11-17
**Scope:** All 36 items in `multidomain_human_annotation_pool.csv` verified against frozen Kùzu corpus (`okf_graph.db`).

## Summary of Findings

- **Total Items Audited:** 36
- **VERIFIED:** 0 (0.0%)
- **MISMATCH:** 36 (100.0%)
- **UNVERIFIABLE:** 0 (0.0%)

> [!IMPORTANT]
> **Key Integrity Discovery:** The 36-item pilot annotation package constructed in S4-G2 was composed of idealized > textbook/domain summary statements authored from general computer science domain knowledge, rather than verbatim extracts > from the indexed corpus chunks. Furthermore, repeated chunk identifiers were assigned conflicting page numbers > (e.g., `doc_fundamentals_of_database_system_7e::chunk_001` on pages 24, 42, and 15), and back-of-the-book indices > were cited as sources for expository theory. All 36 items have been formally classified as `MISMATCH` with exact reasons.

## Item-by-Item Verification Log

### Item OS-01 (Operating Systems: `Virtual Memory` — `Address Space`)
- **Claimed Source:** `archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf::chunk_001` (Page 2)
- **Licensing:** `OPEN_TEXTBOOK_CC_BY_NC_ND`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf' (actual chunks include ['paging_seed_004', 'paging_seed_005', 'virtual_memory_seed_001']); Evidence text does not occur as verbatim substring in document 'archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item OS-02 (Operating Systems: `Address Translation` — `Base-and-Bounds`)
- **Claimed Source:** `archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf::chunk_001` (Page 3)
- **Licensing:** `OPEN_TEXTBOOK_CC_BY_NC_ND`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf' (actual chunks include ['virtual_memory_seed_004', 'virtual_memory_seed_005']); Evidence text does not occur as verbatim substring in document 'archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item OS-03 (Operating Systems: `Page Table` — `Paging`)
- **Claimed Source:** `archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf::chunk_002` (Page 4)
- **Licensing:** `OPEN_TEXTBOOK_CC_BY_NC_ND`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_002' does not exist in 'archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf' (actual chunks include ['paging_seed_001', 'paging_seed_002', 'paging_seed_003']); Evidence text does not occur as verbatim substring in document 'archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item OS-04 (Operating Systems: `Paging` — `Segmentation`)
- **Claimed Source:** `archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf::chunk_001` (Page 1)
- **Licensing:** `OPEN_TEXTBOOK_CC_BY_NC_ND`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf' (actual chunks include ['paging_seed_001', 'paging_seed_002', 'paging_seed_003']); Evidence text does not occur as verbatim substring in document 'archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item OS-05 (Operating Systems: `Operating System` — `Memory Management Unit (MMU)`)
- **Claimed Source:** `archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf::chunk_002` (Page 5)
- **Licensing:** `OPEN_TEXTBOOK_CC_BY_NC_ND`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_002' does not exist in 'archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf' (actual chunks include ['virtual_memory_seed_004', 'virtual_memory_seed_005']); Evidence text does not occur as verbatim substring in document 'archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item OS-06 (Operating Systems: `TLB` — `CPU Scheduling`)
- **Claimed Source:** `archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf::chunk_003` (Page 7)
- **Licensing:** `OPEN_TEXTBOOK_CC_BY_NC_ND`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_003' does not exist in 'archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf' (actual chunks include ['paging_seed_004', 'paging_seed_005', 'virtual_memory_seed_001']); Evidence text does not occur as verbatim substring in document 'archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item DBMS-01 (Database Management Systems: `Third Normal Form (3NF)` — `Functional Dependency`)
- **Claimed Source:** `pilot/silberschatz_3nf_card.txt::chunk_001` (Page 1)
- **Licensing:** `INTERNAL_STUDY_CARD`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'pilot/silberschatz_3nf_card.txt' (actual chunks include ['third_normal_form_seed_001']); Evidence text does not occur as verbatim substring in document 'pilot/silberschatz_3nf_card.txt'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item DBMS-02 (Database Management Systems: `Candidate Key` — `Prime Attribute`)
- **Claimed Source:** `pilot/silberschatz_3nf_card.txt::chunk_001` (Page 1)
- **Licensing:** `INTERNAL_STUDY_CARD`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'pilot/silberschatz_3nf_card.txt' (actual chunks include ['third_normal_form_seed_001']); Evidence text does not occur as verbatim substring in document 'pilot/silberschatz_3nf_card.txt'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item DBMS-03 (Database Management Systems: `B+ Tree` — `Leaf Node`)
- **Claimed Source:** `doc_fundamentals_of_database_system_7e::chunk_001` (Page 24)
- **Licensing:** `COPYRIGHT_RESTRICTED_CATALOG_EXCERPT`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `UNINDEXED_TOPIC_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'doc_fundamentals_of_database_system_7e' (actual chunks include ['doc_fundamentals_of_database_system_7e_p145_1']); Conflicting page/topic reuse of 'doc_fundamentals_of_database_system_7e::chunk_001' on page 24; document has only 1 indexed chunk in DB (chunk_id='doc_fundamentals_of_database_system_7e_p145_1', page 145, Relational Algebra), topics on page 24 are absent from the indexed corpus.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item DBMS-04 (Database Management Systems: `Two-Phase Locking (2PL)` — `Conflict Serializability`)
- **Claimed Source:** `doc_fundamentals_of_database_system_7e::chunk_001` (Page 42)
- **Licensing:** `COPYRIGHT_RESTRICTED_CATALOG_EXCERPT`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `UNINDEXED_TOPIC_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'doc_fundamentals_of_database_system_7e' (actual chunks include ['doc_fundamentals_of_database_system_7e_p145_1']); Conflicting page/topic reuse of 'doc_fundamentals_of_database_system_7e::chunk_001' on page 42; document has only 1 indexed chunk in DB (chunk_id='doc_fundamentals_of_database_system_7e_p145_1', page 145, Relational Algebra), topics on page 42 are absent from the indexed corpus.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item DBMS-05 (Database Management Systems: `Relational Model` — `Domain Constraints`)
- **Claimed Source:** `doc_fundamentals_of_database_system_7e::chunk_001` (Page 15)
- **Licensing:** `COPYRIGHT_RESTRICTED_CATALOG_EXCERPT`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `UNINDEXED_TOPIC_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'doc_fundamentals_of_database_system_7e' (actual chunks include ['doc_fundamentals_of_database_system_7e_p145_1']); Conflicting page/topic reuse of 'doc_fundamentals_of_database_system_7e::chunk_001' on page 15; document has only 1 indexed chunk in DB (chunk_id='doc_fundamentals_of_database_system_7e_p145_1', page 145, Relational Algebra), topics on page 15 are absent from the indexed corpus.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item DBMS-06 (Database Management Systems: `3NF Decomposition` — `Query Optimization`)
- **Claimed Source:** `pilot/silberschatz_3nf_card.txt::chunk_001` (Page 1)
- **Licensing:** `INTERNAL_STUDY_CARD`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'pilot/silberschatz_3nf_card.txt' (actual chunks include ['third_normal_form_seed_001']); Evidence text does not occur as verbatim substring in document 'pilot/silberschatz_3nf_card.txt'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item NET-01 (Computer Networks: `Packet Switching` — `Network Topology`)
- **Claimed Source:** `doc_computer_networks_6_e::chunk_001` (Page 8)
- **Licensing:** `COPYRIGHT_RESTRICTED_CATALOG_EXCERPT`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `UNINDEXED_TOPIC_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'doc_computer_networks_6_e' (actual chunks include ['doc_computer_networks_6_e_p42_1', 'doc_computer_networks_6_e_p198_2']); Claimed chunk 'chunk_001' page 8 absent from DB; document has only 2 indexed chunks (p42 on OSI, p198 on sliding window).
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item NET-02 (Computer Networks: `Framing` — `Bit Transmission`)
- **Claimed Source:** `doc_computer_networks_6_e::chunk_002` (Page 14)
- **Licensing:** `COPYRIGHT_RESTRICTED_CATALOG_EXCERPT`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `UNINDEXED_TOPIC_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_002' does not exist in 'doc_computer_networks_6_e' (actual chunks include ['doc_computer_networks_6_e_p42_1', 'doc_computer_networks_6_e_p198_2']); Claimed chunk 'chunk_002' page 14 absent from DB; document has only 2 indexed chunks (p42 on OSI, p198 on sliding window).
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item NET-03 (Computer Networks: `IPsec` — `Block Cipher`)
- **Claimed Source:** `doc_data_and_computer_communications::chunk_001` (Page 32)
- **Licensing:** `COPYRIGHT_RESTRICTED_CATALOG_EXCERPT`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'doc_data_and_computer_communications' (actual chunks include ['doc_data_and_computer_communications_p612_4']); Evidence text does not occur as verbatim substring in document 'doc_data_and_computer_communications'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item NET-04 (Computer Networks: `Packet Switching` — `Circuit Switching`)
- **Claimed Source:** `doc_computer_networks_6_e::chunk_001` (Page 9)
- **Licensing:** `COPYRIGHT_RESTRICTED_CATALOG_EXCERPT`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `UNINDEXED_TOPIC_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'doc_computer_networks_6_e' (actual chunks include ['doc_computer_networks_6_e_p42_1', 'doc_computer_networks_6_e_p198_2']); Claimed chunk 'chunk_001' page 9 absent from DB; document has only 2 indexed chunks (p42 on OSI, p198 on sliding window).
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item NET-05 (Computer Networks: `Intrusion Detection System` — `Graph Neural Network`)
- **Claimed Source:** `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf::chunk_003` (Page 2)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Evidence text does not occur as verbatim substring in document 'papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item NET-06 (Computer Networks: `TCP Congestion Control` — `Graph Laplacian`)
- **Claimed Source:** `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf::chunk_005` (Page 4)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Evidence text does not occur as verbatim substring in document 'papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item TOC-01 (Automata Theory & Computation: `Deterministic Finite Automaton (DFA)` — `Regular Expression`)
- **Claimed Source:** `papers/Willard2023_Outlines.pdf::chunk_002` (Page 2)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `EXTERNAL_THEORY_SYNTHESIS`
- **Reason:** Introductory automata theory definition ('Deterministic Finite Automaton (DFA)' / 'Regular Expression') falsely attributed to specialized LLM decoding preprint; passage does not occur in Willard 2023.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item TOC-02 (Automata Theory & Computation: `Finite State Machine (FSM)` — `Formal Grammar`)
- **Claimed Source:** `papers/Willard2023_Outlines.pdf::chunk_004` (Page 3)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `EXTERNAL_THEORY_SYNTHESIS`
- **Reason:** Introductory automata theory definition ('Finite State Machine (FSM)' / 'Formal Grammar') falsely attributed to specialized LLM decoding preprint; passage does not occur in Willard 2023.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item TOC-03 (Automata Theory & Computation: `State Transition Function` — `Finite Automaton`)
- **Claimed Source:** `papers/Willard2023_Outlines.pdf::chunk_003` (Page 3)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `EXTERNAL_THEORY_SYNTHESIS`
- **Reason:** Introductory automata theory definition ('State Transition Function' / 'Finite Automaton') falsely attributed to specialized LLM decoding preprint; passage does not occur in Willard 2023.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item TOC-04 (Automata Theory & Computation: `Deterministic Finite Automaton` — `Nondeterministic Finite Automaton`)
- **Claimed Source:** `papers/Willard2023_Outlines.pdf::chunk_005` (Page 4)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `EXTERNAL_THEORY_SYNTHESIS`
- **Reason:** Introductory automata theory definition ('Deterministic Finite Automaton' / 'Nondeterministic Finite Automaton') falsely attributed to specialized LLM decoding preprint; passage does not occur in Willard 2023.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item TOC-05 (Automata Theory & Computation: `Neural Text Generation` — `FSM Guidance`)
- **Claimed Source:** `papers/Willard2023_Outlines.pdf::chunk_001` (Page 1)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `EXTERNAL_THEORY_SYNTHESIS`
- **Reason:** Introductory automata theory definition ('Neural Text Generation' / 'FSM Guidance') falsely attributed to specialized LLM decoding preprint; passage does not occur in Willard 2023.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item TOC-06 (Automata Theory & Computation: `Regular Language` — `Beam Search`)
- **Claimed Source:** `papers/Willard2023_Outlines.pdf::chunk_008` (Page 6)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `EXTERNAL_THEORY_SYNTHESIS`
- **Reason:** Introductory automata theory definition ('Regular Language' / 'Beam Search') falsely attributed to specialized LLM decoding preprint; passage does not occur in Willard 2023.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item STAT-01 (Probability & Statistics: `Bayes Theorem` — `Prior Probability`)
- **Claimed Source:** `pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf::chunk_001` (Page 12)
- **Licensing:** `COPYRIGHT_RESTRICTED_BOOK_EXCERPT`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `INDEX_LISTING_ATTRIBUTION_ERROR`
- **Reason:** Claimed expository passage attributed to back-of-the-book subject index 'pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf', which contains only keyword listings, not conceptual prose.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item STAT-02 (Probability & Statistics: `Probability Density Function (PDF)` — `Random Variable`)
- **Claimed Source:** `pattern_recognition_2009/Appendix-A---Hints-from-Probability-and-Statistics_2009_Pattern-Recognition.pdf::chunk_001` (Page 1)
- **Licensing:** `COPYRIGHT_RESTRICTED_BOOK_EXCERPT`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'pattern_recognition_2009/Appendix-A---Hints-from-Probability-and-Statistics_2009_Pattern-Recognition.pdf' (actual chunks include ['Appendix-A---Hints-from-Probability-and-Statistics_2009_Pattern-Recognition__structure']); Evidence text does not occur as verbatim substring in document 'pattern_recognition_2009/Appendix-A---Hints-from-Probability-and-Statistics_2009_Pattern-Recognition.pdf'.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item STAT-03 (Probability & Statistics: `Area under the ROC Curve (AUC)` — `Binary Classifier`)
- **Claimed Source:** `data_science_2019/Index_2019_Data-Science.pdf::chunk_002` (Page 310)
- **Licensing:** `COPYRIGHT_RESTRICTED_BOOK_INDEX`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `INDEX_LISTING_ATTRIBUTION_ERROR`
- **Reason:** Claimed expository passage attributed to back-of-the-book subject index 'data_science_2019/Index_2019_Data-Science.pdf', which contains only keyword listings, not conceptual prose.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item STAT-04 (Probability & Statistics: `Bayesian Estimation` — `Maximum Likelihood Estimation`)
- **Claimed Source:** `pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf::chunk_002` (Page 15)
- **Licensing:** `COPYRIGHT_RESTRICTED_BOOK_EXCERPT`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `INDEX_LISTING_ATTRIBUTION_ERROR`
- **Reason:** Claimed expository passage attributed to back-of-the-book subject index 'pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf', which contains only keyword listings, not conceptual prose.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item STAT-05 (Probability & Statistics: `Nearest Neighbor` — `Probability Density Estimation`)
- **Claimed Source:** `pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf::chunk_001` (Page 13)
- **Licensing:** `COPYRIGHT_RESTRICTED_BOOK_EXCERPT`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `INDEX_LISTING_ATTRIBUTION_ERROR`
- **Reason:** Claimed expository passage attributed to back-of-the-book subject index 'pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf', which contains only keyword listings, not conceptual prose.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item STAT-06 (Probability & Statistics: `Expectation` — `Gradient Descent`)
- **Claimed Source:** `data_science_2019/Index_2019_Data-Science.pdf::chunk_004` (Page 315)
- **Licensing:** `COPYRIGHT_RESTRICTED_BOOK_INDEX`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `INDEX_LISTING_ATTRIBUTION_ERROR`
- **Reason:** Claimed expository passage attributed to back-of-the-book subject index 'data_science_2019/Index_2019_Data-Science.pdf', which contains only keyword listings, not conceptual prose.
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item AI-01 (Artificial Intelligence & Machine Learning: `Transformer Encoder` — `Self-Attention`)
- **Claimed Source:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf::chunk_002` (Page 3)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Evidence passage is a paraphrased or synthesized summary rather than verbatim text; chunk_id mismatch (claimed 'chunk_002').
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item AI-02 (Artificial Intelligence & Machine Learning: `Low-Rank Adaptation (LoRA)` — `Transformer Architecture`)
- **Claimed Source:** `papers/Hu2021_LoRA.pdf::chunk_001` (Page 1)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Claimed chunk_id 'chunk_001' does not exist in 'papers/Hu2021_LoRA.pdf' (actual chunks include ['chunk_036', 'chunk_035', 'chunk_005']); Evidence passage is a paraphrased or synthesized summary rather than verbatim text; chunk_id mismatch (claimed 'chunk_001').
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item AI-03 (Artificial Intelligence & Machine Learning: `Query and Key Projections` — `Multi-Head Attention`)
- **Claimed Source:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf::chunk_003` (Page 4)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Evidence passage is a paraphrased or synthesized summary rather than verbatim text; chunk_id mismatch (claimed 'chunk_003').
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item AI-04 (Artificial Intelligence & Machine Learning: `LoRA` — `Prefix Tuning`)
- **Claimed Source:** `papers/Hu2021_LoRA.pdf::chunk_002` (Page 2)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Evidence passage is a paraphrased or synthesized summary rather than verbatim text; chunk_id mismatch (claimed 'chunk_002').
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item AI-05 (Artificial Intelligence & Machine Learning: `BERT` — `Masked Language Modeling`)
- **Claimed Source:** `papers/Devlin2018_BERT.pdf::chunk_001` (Page 2)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Evidence passage is a paraphrased or synthesized summary rather than verbatim text; chunk_id mismatch (claimed 'chunk_001').
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.

### Item AI-06 (Artificial Intelligence & Machine Learning: `Attention Head` — `Hardware Barrier`)
- **Claimed Source:** `papers/Hu2021_LoRA.pdf::chunk_027` (Page 9)
- **Licensing:** `OPEN_ACCESS_RESEARCH_PAPER`
- **Audit Verdict:** `MISMATCH`
- **Match Type:** `PARAPHRASED_SYNTHESIS`
- **Reason:** Evidence passage is a paraphrased or synthesized summary rather than verbatim text; chunk_id mismatch (claimed 'chunk_027').
- **Correction:** Preserved original candidate text, annotated with explicit `MISMATCH` status and documented chunk/page discrepancies. Human judgment fields remain unadjudicated.
