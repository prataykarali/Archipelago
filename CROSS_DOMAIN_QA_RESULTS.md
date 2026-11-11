# CROSS-DOMAIN QA & EVALUATION RESULTS: ARCHIPELAGO S2-A

**Test Suite**: `tests/unit/test_s2a_cross_domain_qa.py`  
**Execution Environment**: Linux (Python 3.12.3, pytest-9.1.1)  
**Execution Date**: 2026-11-09  
**Total Tests Collected**: 21  
**Total Passed**: **21 (100.0%)**  
**Total Failed**: 0  
**Execution Time**: 11.63 seconds  

---

## 1. Executive Summary

This report documents the end-to-end evaluation of Archipelago's conversational reply engine across all four designated response classes:
- **Class A**: Academic Concept Explanations with authoritative textbook citations.
- **Class B**: Library Inventory & OPAC holding queries with structured markdown tables.
- **Class C**: Research Papers & Literature Discovery with strict mid-2024 cutoff disclosures.
- **Class D**: Diagnostic Learning Paths & MCQs generated exclusively when explicitly prompted.
- **Comparative Multi-Concept Analyses**: Tailored domain comparison matrices (Semaphore vs Mutex, B+ Tree vs Hash Index, BFS vs DFS).
- **Sequential Multi-Turn Dialogues**: 5-turn conversational context carryover.

Every test case validates intent routing classification, citation resolution, source provenance integrity, and response markdown generation.

---

## 2. Test Execution Matrix by Response Class

### Class A: Academic Concept Explanations (Authoritative Textbook Citations)

| # | Academic Query | Routed Intent | Target Concept | Verified Textbook Source | Keywords Verified | Status |
| :-: | :--- | :--- | :--- | :--- | :--- | :-: |
| 1 | *What is a context switch in operating systems?* | `GRAPH_SYNTHESIS` | `context_switch` | OSTEP (*Arpaci-Dusseau*) | PCB, register, save, restore, kernel | **PASS** |
| 2 | *Explain semaphores and how they coordinate processes* | `GRAPH_SYNTHESIS` | `semaphore` | OSTEP (*Arpaci-Dusseau*) | Dijkstra, wait, signal, atomic, counter | **PASS** |
| 3 | *What is a deadlock and what conditions cause it?* | `GRAPH_SYNTHESIS` | `deadlock` | Silberschatz (*OS Concepts*) | mutual exclusion, hold and wait, no preemption, circular wait | **PASS** |
| 4 | *How does virtual memory protect memory address spaces?* | `GRAPH_SYNTHESIS` | `virtual_memory` | OSTEP (*Arpaci-Dusseau*) | page table, translation, TLB, protection, frame | **PASS** |
| 5 | *Explain B+ trees and how they index database records* | `GRAPH_SYNTHESIS` | `b_plus_tree` | Ramakrishnan & Gehrke (*DBMS*) | leaf, internal, range scan, pointer, balanced | **PASS** |
| 6 | *What are ACID properties in database management systems?* | `GRAPH_SYNTHESIS` | `acid_properties` | Ramakrishnan & Gehrke (*DBMS*) | atomicity, consistency, isolation, durability, transaction | **PASS** |
| 7 | *How does TCP congestion control avoid network collapse?* | `GRAPH_SYNTHESIS` | `tcp_congestion_control` | Kurose & Ross (*Computer Networking*) | slow start, congestion avoidance, window, threshold | **PASS** |
| 8 | *Explain the seven layers of the OSI model* | `GRAPH_SYNTHESIS` | `osi_model` | Tanenbaum & Wetherall (*Networks*) | physical, data link, network, transport, session | **PASS** |
| 9 | *What is lexical analysis in compiler design?* | `GRAPH_SYNTHESIS` | `lexical_analysis` | Aho, Lam, Sethi, Ullman (*Dragon Book*) | token, lexeme, scanner, regular expression | **PASS** |
| 10 | *Explain deterministic finite automata in theory of computation* | `GRAPH_SYNTHESIS` | `deterministic_finite_automaton` | Sipser (*Theory of Computation*) | states, transitions, alphabet, accept, formal | **PASS** |
| 11 | *What is maximum likelihood estimation in probability?* | `GRAPH_SYNTHESIS` | `maximum_likelihood_estimation` | Deisenroth (*Math for Machine Learning*) | likelihood, parameter, estimate, log, probability | **PASS** |

### Class B: Library Inventory Queries (Structured Markdown Tables)

| # | Academic Query | Routed Intent | Expected Catalog Titles | Verified Table Headers | Status |
| :-: | :--- | :--- | :--- | :--- | :-: |
| 12 | *Which OS books are available in the library?* | `LIBRARY_LOOKUP` | OSTEP, Silberschatz, Stallings | Title, Author, Shelf / Availability, Identifier | **PASS** |
| 13 | *What DBMS books do we have in the library?* | `LIBRARY_LOOKUP` | Database System Concepts, Ramakrishnan | Title, Author, Shelf / Availability, Identifier | **PASS** |
| 14 | *Which DSA and algorithm textbooks are available?* | `LIBRARY_LOOKUP` | Cormen (CLRS), Kleinberg & Tardos | Title, Author, Shelf / Availability, Identifier | **PASS** |

### Class C: Research Papers & Literature Discovery (Mid-2024 Cutoff Disclosure)

| # | Academic Query | Routed Intent | Cutoff Notice Verified | ArXiv / Scholarly Disclosures | Status |
| :-: | :--- | :--- | :--- | :--- | :-: |
| 15 | *What recent papers discuss FlashAttention or selective state space models?* | `RESEARCH_TOPIC` | `"mid-2024"` / `"knowledge cutoff"` verified | arXiv identifier, peer-review notice, arXiv URL | **PASS** |

### Class D: Diagnostic Roadmaps & MCQs (Strict User-Prompt Gating)

| # | Academic Query | Routed Intent | Diagnostic Graph | MCQ Format Verified | Status |
| :-: | :--- | :--- | :--- | :--- | :-: |
| 16 | *Give me a diagnostic quiz and test my understanding of operating systems* | `MCQ_DIAGNOSTIC` | Prerequisite & unlock nodes bound | $\ge 2$ multiple choice questions with options and answer keys | **PASS** |

### Cross-Domain Comparative Analysis

| # | Comparative Query | Routed Intent | Comparative Matrix Generated | Domain Dimensions Checked | Status |
| :-: | :--- | :--- | :--- | :--- | :-: |
| 17 | *How do semaphores differ from mutex locks?* | `CROSS_DOMAIN` | `Semaphore vs Mutex Lock` | Ownership, capacity, signaling semantics | **PASS** |
| 18 | *Compare B+ trees and hash indexing for database queries* | `CROSS_DOMAIN` | `B+ Tree Indexing vs Hash Indexing` | Range queries, equality lookups, disk I/O pattern | **PASS** |
| 19 | *How is BFS different from DFS in graph search?* | `CROSS_DOMAIN` | `Breadth-First Search (BFS) vs Depth-First Search (DFS)` | Data structure (Queue vs Stack), shortest path optimality, memory space | **PASS** |

### Multi-Turn Context Carryover (5-Turn Sequential Flow)

| Turn | User Input | Routed Intent | Context Retained & Assertions | Status |
| :-: | :--- | :--- | :--- | :-: |
| **Turn 1** | *Which OS books are available?* | `LIBRARY_LOOKUP` | Returns inventory table containing OSTEP and Silberschatz. Sets active subject: Operating Systems. | **PASS** |
| **Turn 2** | *Which is best for learning concurrency?* | `GENERAL_EXPLANATION` | Resolves antecedent "Which" to OSTEP. Explains why OSTEP Part II Concurrency is optimal. | **PASS** |
| **Turn 3** | *Show its chapter on locks.* | `BOOK_PAGE` | Resolves "its" to OSTEP. Cites Chapter 28 (Locks), page 301, with viewer deep link. | **PASS** |
| **Turn 4** | *Can you explain semaphores from that source?* | `GRAPH_SYNTHESIS` | Resolves "that source" to OSTEP Ch 31. Explains Dijkstra semaphores with `ostep_three_easy_pieces.pdf:ch31_p365`. | **PASS** |
| **Turn 5** | *How does this differ from condition variables?* | `CROSS_DOMAIN` | Resolves "this" to Semaphore. Produces comparative matrix: Semaphore × Condition Variable. | **PASS** |

---

## 3. Sample Verification Traces

### Sample 1: Class A Concept Explanation (Turn 4 - Semaphore from OSTEP)
```
Input: "Can you explain semaphores from that source?"
Intent: GRAPH_SYNTHESIS
Concept Bound: semaphore
Citation: textbooks/ostep_three_easy_pieces.pdf:ch31_p365
Text Excerpt:
"A semaphore is an object with an integer value that we can manipulate with two 
routines: sem_wait() and sem_post(). Because the initial value of the semaphore 
determines its behavior, before calling any other routines on it, an application 
must first initialize the semaphore..."
```

### Sample 2: Class B Inventory Table (Turn 1 - OS Books)
```
Input: "Which OS books are available?"
Intent: LIBRARY_LOOKUP
Output Snippet:
| Title | Author | Shelf / Availability | Identifier |
| :--- | :--- | :--- | :--- |
| Operating Systems: Three Easy Pieces (OSTEP) | Remzi H. Arpaci-Dusseau | Available Online (Open Access) | ISBN 9781985086593 |
| Operating System Concepts | Abraham Silberschatz | Available (Stack 005 SIL) | Koha Bib #588 |
| Operating Systems: Internals and Design Principles | William Stallings | Pearson eLibrary Digital | ISBN 9789356062160 |
```

### Sample 3: Cross-Domain Comparative Analysis (Turn 5)
```
Input: "How does this differ from condition variables?"
Intent: CROSS_DOMAIN
Matrix Generated:
| Dimension | Semaphore | Condition Variable |
| :--- | :--- | :--- |
| **State Memory** | Has state: remembers past signals via its integer value | Stateless: signals sent when no thread is waiting are lost |
| **Lock Association** | Can operate independently without an associated mutex | Must always be paired with an explicit mutex lock |
| **Primitive Operations** | wait() (P) and post() / signal() (V) | wait(), signal(), and broadcast() |
| **Usage Pattern** | Resource counting and mutual exclusion | Signaling state changes and waiting for specific conditions |
```

---

## 4. Test Suite Execution Log

```
============================= test session starts ==============================
rootdir: /home/pratay-karali/Desktop/archipelago/Archipelago
collected 21 items

tests/unit/test_s2a_cross_domain_qa.py::test_class_a_academic_concept_explanations[...] PASSED [ 52%]
tests/unit/test_s2a_cross_domain_qa.py::test_class_b_library_inventory_tables[...] PASSED [ 66%]
tests/unit/test_s2a_cross_domain_qa.py::test_class_c_research_topic_recent_literature PASSED [ 71%]
tests/unit/test_s2a_cross_domain_qa.py::test_class_d_diagnostic_learning_generates_mcqs_and_graph PASSED [ 76%]
tests/unit/test_s2a_cross_domain_qa.py::test_cross_domain_comparisons[...] PASSED [ 90%]
tests/unit/test_s2a_cross_domain_qa.py::test_s2a_5_turn_sequential_flow PASSED [ 95%]
tests/unit/test_s2a_cross_domain_qa.py::test_production_graph_node_and_edge_preservation PASSED [100%]

======================= 21 passed in 11.63s ========================
```
