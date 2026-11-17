# Archipelago Multi-Domain Human Annotation Workbook (Blinded Pool)

**Total Items:** 36 items (6 domains x 6 items per domain)
**Protocol:** Independent blinded human evaluation. System-generated labels are concealed.

---

## Domain: Operating Systems

### Item [OS-01] — Virtual Memory vs. Address Space
- **Source:** `archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf` (Page 2, Chunk `chunk_001`)
- **Passage:** > "The operating system creates an abstraction of physical memory known as the address space. Virtual memory provides each process with the illusion that it has a large, contiguous private memory space."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Virtual Memory`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Address Space`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [OS-02] — Address Translation vs. Base-and-Bounds
- **Source:** `archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf` (Page 3, Chunk `chunk_001`)
- **Passage:** > "In hardware-based address translation, the processor transforms each virtual address into a physical address. The simplest mechanism for this is base and bounds, where a base register adds an offset and bounds prevents out-of-range access."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Address Translation`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Base-and-Bounds`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [OS-03] — Page Table vs. Paging
- **Source:** `archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf` (Page 4, Chunk `chunk_002`)
- **Passage:** > "To record where each virtual page of an address space is placed in physical memory, the operating system keeps a per-process data structure known as a page table. The major role of the page table is address translation."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Page Table`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Paging`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [OS-04] — Paging vs. Segmentation
- **Source:** `archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf` (Page 1, Chunk `chunk_001`)
- **Passage:** > "Unlike segmentation, which chops space into variable-sized logical segments, paging divides address spaces into fixed-sized units called pages, completely avoiding external fragmentation."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Paging`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Segmentation`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [OS-05] — Operating System vs. Memory Management Unit (MMU)
- **Source:** `archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf` (Page 5, Chunk `chunk_002`)
- **Passage:** > "The operating system collaborates with hardware: the memory management unit (MMU) on the CPU performs fast translation on every instruction, while the OS handles setup and exceptions."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Operating System`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Memory Management Unit (MMU)`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [OS-06] — TLB vs. CPU Scheduling
- **Source:** `archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf` (Page 7, Chunk `chunk_003`)
- **Passage:** > "Modern operating systems interleave process execution. A context switch pauses one process and resumes another, saving registers to memory."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`TLB`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`CPU Scheduling`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

## Domain: Database Management Systems

### Item [DBMS-01] — Third Normal Form (3NF) vs. Functional Dependency
- **Source:** `pilot/silberschatz_3nf_card.txt` (Page 1, Chunk `chunk_001`)
- **Passage:** > "A relation schema R is in Third Normal Form (3NF) with respect to a set F of functional dependencies if, for all functional dependencies X -> A in F+, either A is in X, X is a superkey, or A is a prime attribute."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Third Normal Form (3NF)`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Functional Dependency`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [DBMS-02] — Candidate Key vs. Prime Attribute
- **Source:** `pilot/silberschatz_3nf_card.txt` (Page 1, Chunk `chunk_001`)
- **Passage:** > "An attribute A of a relation schema R is called a prime attribute if A is a member of some candidate key for R. Candidate keys form minimal superkeys."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Candidate Key`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Prime Attribute`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [DBMS-03] — B+ Tree vs. Leaf Node
- **Source:** `doc_fundamentals_of_database_system_7e` (Page 24, Chunk `chunk_001`)
- **Passage:** > "A B+ tree index structure consists of internal routing nodes and leaf nodes. The leaf nodes are linked together sequentially to support efficient range traversal."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`B+ Tree`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Leaf Node`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [DBMS-04] — Two-Phase Locking (2PL) vs. Conflict Serializability
- **Source:** `doc_fundamentals_of_database_system_7e` (Page 42, Chunk `chunk_001`)
- **Passage:** > "Under the two-phase locking protocol, transactions acquire locks during an expanding phase and release them during a shrinking phase, which guarantees conflict serializability."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Two-Phase Locking (2PL)`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Conflict Serializability`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [DBMS-05] — Relational Model vs. Domain Constraints
- **Source:** `doc_fundamentals_of_database_system_7e` (Page 15, Chunk `chunk_001`)
- **Passage:** > "In the formal relational model, relations enforce schema integrity through domain constraints, requiring all attribute values to be atomic elements from defined value domains."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Relational Model`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Domain Constraints`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [DBMS-06] — 3NF Decomposition vs. Query Optimization
- **Source:** `pilot/silberschatz_3nf_card.txt` (Page 1, Chunk `chunk_001`)
- **Passage:** > "Normalization eliminates insertion, deletion, and update anomalies by decomposing relations based on functional dependency closures."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`3NF Decomposition`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Query Optimization`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

## Domain: Computer Networks

### Item [NET-01] — Packet Switching vs. Network Topology
- **Source:** `doc_computer_networks_6_e` (Page 8, Chunk `chunk_001`)
- **Passage:** > "Packet switching networks forward discrete chunks of data across intermediate routers according to the underlying network topology and routing tables."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Packet Switching`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Network Topology`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [NET-02] — Framing vs. Bit Transmission
- **Source:** `doc_computer_networks_6_e` (Page 14, Chunk `chunk_002`)
- **Passage:** > "The data link layer encapsulates network packets into frames. Framing adds delimiters and error-detection codes before serial bit transmission across the physical medium."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Framing`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Bit Transmission`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [NET-03] — IPsec vs. Block Cipher
- **Source:** `doc_data_and_computer_communications` (Page 32, Chunk `chunk_001`)
- **Passage:** > "IPsec provides security at the network layer using cryptographic protocols. Encapsulating Security Payload (ESP) encrypts packets using symmetric block ciphers like AES."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`IPsec`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Block Cipher`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [NET-04] — Packet Switching vs. Circuit Switching
- **Source:** `doc_computer_networks_6_e` (Page 9, Chunk `chunk_001`)
- **Passage:** > "In contrast to circuit switching, which reserves dedicated end-to-end bandwidth for the duration of a call, packet switching shares communication links dynamically using statistical multiplexing."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Packet Switching`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Circuit Switching`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [NET-05] — Intrusion Detection System vs. Graph Neural Network
- **Source:** `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf` (Page 2, Chunk `chunk_003`)
- **Passage:** > "We develop a real-time network intrusion detection system (NIDS) that models packet flow graphs using graph neural networks (GNNs) to identify malicious traffic."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Intrusion Detection System`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Graph Neural Network`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [NET-06] — TCP Congestion Control vs. Graph Laplacian
- **Source:** `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf` (Page 4, Chunk `chunk_005`)
- **Passage:** > "Packet inter-arrival times and window sizes reflect network conditions during high-volume DDoS attacks across distributed nodes."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`TCP Congestion Control`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Graph Laplacian`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

## Domain: Automata Theory & Computation

### Item [TOC-01] — Deterministic Finite Automaton (DFA) vs. Regular Expression
- **Source:** `papers/Willard2023_Outlines.pdf` (Page 2, Chunk `chunk_002`)
- **Passage:** > "By Kleene theorem, every regular expression can be compiled into an equivalent deterministic finite automaton (DFA) that recognizes the corresponding regular language."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Deterministic Finite Automaton (DFA)`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Regular Expression`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [TOC-02] — Finite State Machine (FSM) vs. Formal Grammar
- **Source:** `papers/Willard2023_Outlines.pdf` (Page 3, Chunk `chunk_004`)
- **Passage:** > "To constrain language model outputs, we construct a finite state machine (FSM) derived from a formal context-free grammar or regular grammar."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Finite State Machine (FSM)`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Formal Grammar`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [TOC-03] — State Transition Function vs. Finite Automaton
- **Source:** `papers/Willard2023_Outlines.pdf` (Page 3, Chunk `chunk_003`)
- **Passage:** > "A finite automaton consists of a finite set of states Q, an alphabet Sigma, a transition function delta : Q x Sigma -> Q, an initial state, and accepting states."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`State Transition Function`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Finite Automaton`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [TOC-04] — Deterministic Finite Automaton vs. Nondeterministic Finite Automaton
- **Source:** `papers/Willard2023_Outlines.pdf` (Page 4, Chunk `chunk_005`)
- **Passage:** > "While an NFA allows epsilon-transitions and multiple next states for a single symbol, powerset construction converts any NFA into an equivalent DFA with at most 2^|Q| states."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Deterministic Finite Automaton`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Nondeterministic Finite Automaton`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [TOC-05] — Neural Text Generation vs. FSM Guidance
- **Source:** `papers/Willard2023_Outlines.pdf` (Page 1, Chunk `chunk_001`)
- **Passage:** > "We guide autoregressive neural text generation by masking invalid vocabulary logits using an efficient index built from the FSM state transition matrix."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Neural Text Generation`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`FSM Guidance`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [TOC-06] — Regular Language vs. Beam Search
- **Source:** `papers/Willard2023_Outlines.pdf` (Page 6, Chunk `chunk_008`)
- **Passage:** > "Decoding strategies for large language models generate token sequences greedily or via stochastic sampling across output probabilities."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Regular Language`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Beam Search`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

## Domain: Probability & Statistics

### Item [STAT-01] — Bayes Theorem vs. Prior Probability
- **Source:** `pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf` (Page 12, Chunk `chunk_001`)
- **Passage:** > "Bayes theorem calculates posterior probability P(w|x) by multiplying the prior probability P(w) by the class-conditional likelihood P(x|w), normalized by the evidence P(x)."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Bayes Theorem`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Prior Probability`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [STAT-02] — Probability Density Function (PDF) vs. Random Variable
- **Source:** `pattern_recognition_2009/Appendix-A---Hints-from-Probability-and-Statistics_2009_Pattern-Recognition.pdf` (Page 1, Chunk `chunk_001`)
- **Passage:** > "For a continuous random variable X, the probability density function p(x) specifies the likelihood that X falls within an infinitesimal interval [x, x + dx]."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Probability Density Function (PDF)`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Random Variable`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [STAT-03] — Area under the ROC Curve (AUC) vs. Binary Classifier
- **Source:** `data_science_2019/Index_2019_Data-Science.pdf` (Page 310, Chunk `chunk_002`)
- **Passage:** > "The area under the receiver operating characteristic curve (AUC-ROC) measures the aggregate ranking performance of a binary classifier across all possible classification thresholds."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Area under the ROC Curve (AUC)`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Binary Classifier`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [STAT-04] — Bayesian Estimation vs. Maximum Likelihood Estimation
- **Source:** `pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf` (Page 15, Chunk `chunk_002`)
- **Passage:** > "Unlike maximum likelihood estimation, which treats parameters theta as unknown fixed constants, Bayesian parameter estimation considers theta as a random variable governed by a prior distribution."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Bayesian Estimation`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Maximum Likelihood Estimation`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [STAT-05] — Nearest Neighbor vs. Probability Density Estimation
- **Source:** `pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf` (Page 13, Chunk `chunk_001`)
- **Passage:** > "Non-parametric techniques use k-nearest neighbor density estimation to approximate arbitrary multi-modal probability distributions directly from sample observations."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Nearest Neighbor`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Probability Density Estimation`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [STAT-06] — Expectation vs. Gradient Descent
- **Source:** `data_science_2019/Index_2019_Data-Science.pdf` (Page 315, Chunk `chunk_004`)
- **Passage:** > "Mathematical optimization algorithms iterate over loss surfaces to minimize empirical prediction errors across validation splits."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Expectation`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Gradient Descent`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

## Domain: Artificial Intelligence & Machine Learning

### Item [AI-01] — Transformer Encoder vs. Self-Attention
- **Source:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (Page 3, Chunk `chunk_002`)
- **Passage:** > "The Transformer encoder consists of a stack of N = 6 identical layers. Each layer has two sub-layers: a multi-head self-attention mechanism, and a simple, position-wise fully connected feed-forward network."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Transformer Encoder`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Self-Attention`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [AI-02] — Low-Rank Adaptation (LoRA) vs. Transformer Architecture
- **Source:** `papers/Hu2021_LoRA.pdf` (Page 1, Chunk `chunk_001`)
- **Passage:** > "For a pre-trained Transformer model, we propose Low-Rank Adaptation (LoRA), which freezes the pre-trained model weights and injects trainable rank decomposition matrices into each layer."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Low-Rank Adaptation (LoRA)`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Transformer Architecture`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [AI-03] — Query and Key Projections vs. Multi-Head Attention
- **Source:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf` (Page 4, Chunk `chunk_003`)
- **Passage:** > "Multi-head attention projects queries, keys, and values h times with different, learned linear projections of dimension d_k, d_k and d_v, respectively, allowing the model to jointly attend to information."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Query and Key Projections`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Multi-Head Attention`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [AI-04] — LoRA vs. Prefix Tuning
- **Source:** `papers/Hu2021_LoRA.pdf` (Page 2, Chunk `chunk_002`)
- **Passage:** > "In contrast to prefix tuning or adapter layers, which insert additional latency or reduce usable sequence length, LoRA introduces no inference latency overhead because weights can be merged."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`LoRA`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Prefix Tuning`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [AI-05] — BERT vs. Masked Language Modeling
- **Source:** `papers/Devlin2018_BERT.pdf` (Page 2, Chunk `chunk_001`)
- **Passage:** > "BERT alleviates the unidirectionality constraint by using a "masked language model" (MLM) pre-training objective. The masked language model enables the representation to fuse both left and right context."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`BERT`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Masked Language Modeling`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---

### Item [AI-06] — Attention Head vs. Hardware Barrier
- **Source:** `papers/Hu2021_LoRA.pdf` (Page 9, Chunk `chunk_027`)
- **Passage:** > "Note that the low-rank structure lowers the hardware barrier to entry which allows us to run multiple experiments in parallel across commodity GPU nodes."

| Field | Value (Annotator Entry) | Options / Scale |
|---|---|---|
| Concept A Validity (`Attention Head`) | [ ] | 1 = Valid, 0 = Invalid |
| Concept B Validity (`Hardware Barrier`) | [ ] | 1 = Valid, 0 = Invalid |
| Relation Type | [ ] | REQUIRES / UNLOCKS / PART_OF / USES / CONTRASTS_WITH / RELATED / UNRELATED |
| Prerequisite Direction | [ ] | A_BEFORE_B / B_BEFORE_A / UNDIRECTED / NONE |
| Evidence Support | [ ] | 2 = Fully Supported, 1 = Partially, 0 = Unsupported |
| Source Citation Verified | [ ] | 1 = Verified, 0 = Incorrect |
| Confidence Level | [ ] | High / Medium / Low |
| Uncertainty Flag | [ ] | 1 = Uncertain, 0 = Certain |
| Notes / Justification | | (Optional free text) |

---
