# Archipelago Multi-Domain Knowledge Graph: Human Annotation Workbook (Corrected & Source-Audited)

**Benchmark Version:** S4-G2.1 Frozen Corrected Edition  
**Status:** Audited against frozen corpus `okf_graph.db`; all items annotated with source verification status.  
**Scientific Safeguard:** Zero human judgments have been fabricated. All judgment scoring fields are unadjudicated.  

---

## Domain Distribution Overview

| Domain Code | Academic Domain | Total Items | Audit Status |
| :--- | :--- | :---: | :--- |
| `OS` | Operating Systems | 6 | 6 MISMATCH (paraphrased OSTEP summaries / non-matching chunk IDs) |
| `DBMS` | Database Management Systems | 6 | 6 MISMATCH (3NF card chunk ID mismatch; DB 7e unindexed topics) |
| `NET` | Computer Networks | 6 | 6 MISMATCH (Tanenbaum p8/14/9 unindexed; Stallings p32 unindexed; Security p1 synthesized) |
| `TOC` | Automata Theory & Computation | 6 | 6 MISMATCH (Classical textbook theory falsely attributed to Willard preprint) |
| `STAT` | Probability & Statistics | 6 | 6 MISMATCH (Expository definitions attributed to back-of-book keyword indices) |
| `AIML` | Artificial Intelligence & Machine Learning | 6 | 6 MISMATCH (Paraphrased paper summaries; Vaswani / Hu / Devlin chunk discrepancies) |

---

## [OS-01] Operating Systems: `Virtual Memory` — `Address Space`

- **Claimed Source Document:** `archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 2)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf' (actual chunks include ['paging_seed_004', 'paging_seed_005', 'virtual_memory_seed_001']); Evidence text does not occur as verbatim substring in document 'archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf'.

### Candidate Evidence Passage
> The operating system creates an abstraction of physical memory known as the address space. Virtual memory provides each process with the illusion that it has a large, contiguous private memory space.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: OS-01
domain: "Operating Systems"
concept_a: "Virtual Memory"
concept_b: "Address Space"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [OS-02] Operating Systems: `Address Translation` — `Base-and-Bounds`

- **Claimed Source Document:** `archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 3)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf' (actual chunks include ['virtual_memory_seed_004', 'virtual_memory_seed_005']); Evidence text does not occur as verbatim substring in document 'archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf'.

### Candidate Evidence Passage
> In hardware-based address translation, the processor transforms each virtual address into a physical address. The simplest mechanism for this is base and bounds, where a base register adds an offset and bounds prevents out-of-range access.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: OS-02
domain: "Operating Systems"
concept_a: "Address Translation"
concept_b: "Base-and-Bounds"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [OS-03] Operating Systems: `Page Table` — `Paging`

- **Claimed Source Document:** `archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf`
- **Claimed Chunk ID:** `chunk_002` (Claimed Page: 4)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_002' does not exist in 'archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf' (actual chunks include ['paging_seed_001', 'paging_seed_002', 'paging_seed_003']); Evidence text does not occur as verbatim substring in document 'archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf'.

### Candidate Evidence Passage
> To record where each virtual page of an address space is placed in physical memory, the operating system keeps a per-process data structure known as a page table. The major role of the page table is address translation.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: OS-03
domain: "Operating Systems"
concept_a: "Page Table"
concept_b: "Paging"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [OS-04] Operating Systems: `Paging` — `Segmentation`

- **Claimed Source Document:** `archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 1)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf' (actual chunks include ['paging_seed_001', 'paging_seed_002', 'paging_seed_003']); Evidence text does not occur as verbatim substring in document 'archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf'.

### Candidate Evidence Passage
> Unlike segmentation, which chops space into variable-sized logical segments, paging divides address spaces into fixed-sized units called pages, completely avoiding external fragmentation.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: OS-04
domain: "Operating Systems"
concept_a: "Paging"
concept_b: "Segmentation"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [OS-05] Operating Systems: `Operating System` — `Memory Management Unit (MMU)`

- **Claimed Source Document:** `archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf`
- **Claimed Chunk ID:** `chunk_002` (Claimed Page: 5)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_002' does not exist in 'archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf' (actual chunks include ['virtual_memory_seed_004', 'virtual_memory_seed_005']); Evidence text does not occur as verbatim substring in document 'archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf'.

### Candidate Evidence Passage
> The operating system collaborates with hardware: the memory management unit (MMU) on the CPU performs fast translation on every instruction, while the OS handles setup and exceptions.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: OS-05
domain: "Operating Systems"
concept_a: "Operating System"
concept_b: "Memory Management Unit (MMU)"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [OS-06] Operating Systems: `TLB` — `CPU Scheduling`

- **Claimed Source Document:** `archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf`
- **Claimed Chunk ID:** `chunk_003` (Claimed Page: 7)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_003' does not exist in 'archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf' (actual chunks include ['paging_seed_004', 'paging_seed_005', 'virtual_memory_seed_001']); Evidence text does not occur as verbatim substring in document 'archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf'.

### Candidate Evidence Passage
> Modern operating systems interleave process execution. A context switch pauses one process and resumes another, saving registers to memory.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: OS-06
domain: "Operating Systems"
concept_a: "TLB"
concept_b: "CPU Scheduling"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [DBMS-01] Database Management Systems: `Third Normal Form (3NF)` — `Functional Dependency`

- **Claimed Source Document:** `pilot/silberschatz_3nf_card.txt`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 1)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'pilot/silberschatz_3nf_card.txt' (actual chunks include ['third_normal_form_seed_001']); Evidence text does not occur as verbatim substring in document 'pilot/silberschatz_3nf_card.txt'.

### Candidate Evidence Passage
> A relation schema R is in Third Normal Form (3NF) with respect to a set F of functional dependencies if, for all functional dependencies X -> A in F+, either A is in X, X is a superkey, or A is a prime attribute.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: DBMS-01
domain: "Database Management Systems"
concept_a: "Third Normal Form (3NF)"
concept_b: "Functional Dependency"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [DBMS-02] Database Management Systems: `Candidate Key` — `Prime Attribute`

- **Claimed Source Document:** `pilot/silberschatz_3nf_card.txt`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 1)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'pilot/silberschatz_3nf_card.txt' (actual chunks include ['third_normal_form_seed_001']); Evidence text does not occur as verbatim substring in document 'pilot/silberschatz_3nf_card.txt'.

### Candidate Evidence Passage
> An attribute A of a relation schema R is called a prime attribute if A is a member of some candidate key for R. Candidate keys form minimal superkeys.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: DBMS-02
domain: "Database Management Systems"
concept_a: "Candidate Key"
concept_b: "Prime Attribute"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [DBMS-03] Database Management Systems: `B+ Tree` — `Leaf Node`

- **Claimed Source Document:** `doc_fundamentals_of_database_system_7e`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 24)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'doc_fundamentals_of_database_system_7e' (actual chunks include ['doc_fundamentals_of_database_system_7e_p145_1']); Conflicting page/topic reuse of 'doc_fundamentals_of_database_system_7e::chunk_001' on page 24; document has only 1 indexed chunk in DB (chunk_id='doc_fundamentals_of_database_system_7e_p145_1', page 145, Relational Algebra), topics on page 24 are absent from the indexed corpus.

### Candidate Evidence Passage
> A B+ tree index structure consists of internal routing nodes and leaf nodes. The leaf nodes are linked together sequentially to support efficient range traversal.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: DBMS-03
domain: "Database Management Systems"
concept_a: "B+ Tree"
concept_b: "Leaf Node"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [DBMS-04] Database Management Systems: `Two-Phase Locking (2PL)` — `Conflict Serializability`

- **Claimed Source Document:** `doc_fundamentals_of_database_system_7e`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 42)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'doc_fundamentals_of_database_system_7e' (actual chunks include ['doc_fundamentals_of_database_system_7e_p145_1']); Conflicting page/topic reuse of 'doc_fundamentals_of_database_system_7e::chunk_001' on page 42; document has only 1 indexed chunk in DB (chunk_id='doc_fundamentals_of_database_system_7e_p145_1', page 145, Relational Algebra), topics on page 42 are absent from the indexed corpus.

### Candidate Evidence Passage
> Under the two-phase locking protocol, transactions acquire locks during an expanding phase and release them during a shrinking phase, which guarantees conflict serializability.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: DBMS-04
domain: "Database Management Systems"
concept_a: "Two-Phase Locking (2PL)"
concept_b: "Conflict Serializability"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [DBMS-05] Database Management Systems: `Relational Model` — `Domain Constraints`

- **Claimed Source Document:** `doc_fundamentals_of_database_system_7e`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 15)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'doc_fundamentals_of_database_system_7e' (actual chunks include ['doc_fundamentals_of_database_system_7e_p145_1']); Conflicting page/topic reuse of 'doc_fundamentals_of_database_system_7e::chunk_001' on page 15; document has only 1 indexed chunk in DB (chunk_id='doc_fundamentals_of_database_system_7e_p145_1', page 145, Relational Algebra), topics on page 15 are absent from the indexed corpus.

### Candidate Evidence Passage
> In the formal relational model, relations enforce schema integrity through domain constraints, requiring all attribute values to be atomic elements from defined value domains.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: DBMS-05
domain: "Database Management Systems"
concept_a: "Relational Model"
concept_b: "Domain Constraints"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [DBMS-06] Database Management Systems: `3NF Decomposition` — `Query Optimization`

- **Claimed Source Document:** `pilot/silberschatz_3nf_card.txt`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 1)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'pilot/silberschatz_3nf_card.txt' (actual chunks include ['third_normal_form_seed_001']); Evidence text does not occur as verbatim substring in document 'pilot/silberschatz_3nf_card.txt'.

### Candidate Evidence Passage
> Normalization eliminates insertion, deletion, and update anomalies by decomposing relations based on functional dependency closures.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: DBMS-06
domain: "Database Management Systems"
concept_a: "3NF Decomposition"
concept_b: "Query Optimization"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [NET-01] Computer Networks: `Packet Switching` — `Network Topology`

- **Claimed Source Document:** `doc_computer_networks_6_e`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 8)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'doc_computer_networks_6_e' (actual chunks include ['doc_computer_networks_6_e_p42_1', 'doc_computer_networks_6_e_p198_2']); Claimed chunk 'chunk_001' page 8 absent from DB; document has only 2 indexed chunks (p42 on OSI, p198 on sliding window).

### Candidate Evidence Passage
> Packet switching networks forward discrete chunks of data across intermediate routers according to the underlying network topology and routing tables.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: NET-01
domain: "Computer Networks"
concept_a: "Packet Switching"
concept_b: "Network Topology"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [NET-02] Computer Networks: `Framing` — `Bit Transmission`

- **Claimed Source Document:** `doc_computer_networks_6_e`
- **Claimed Chunk ID:** `chunk_002` (Claimed Page: 14)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_002' does not exist in 'doc_computer_networks_6_e' (actual chunks include ['doc_computer_networks_6_e_p42_1', 'doc_computer_networks_6_e_p198_2']); Claimed chunk 'chunk_002' page 14 absent from DB; document has only 2 indexed chunks (p42 on OSI, p198 on sliding window).

### Candidate Evidence Passage
> The data link layer encapsulates network packets into frames. Framing adds delimiters and error-detection codes before serial bit transmission across the physical medium.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: NET-02
domain: "Computer Networks"
concept_a: "Framing"
concept_b: "Bit Transmission"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [NET-03] Computer Networks: `IPsec` — `Block Cipher`

- **Claimed Source Document:** `doc_data_and_computer_communications`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 32)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'doc_data_and_computer_communications' (actual chunks include ['doc_data_and_computer_communications_p612_4']); Evidence text does not occur as verbatim substring in document 'doc_data_and_computer_communications'.

### Candidate Evidence Passage
> IPsec provides security at the network layer using cryptographic protocols. Encapsulating Security Payload (ESP) encrypts packets using symmetric block ciphers like AES.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: NET-03
domain: "Computer Networks"
concept_a: "IPsec"
concept_b: "Block Cipher"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [NET-04] Computer Networks: `Packet Switching` — `Circuit Switching`

- **Claimed Source Document:** `doc_computer_networks_6_e`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 9)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'doc_computer_networks_6_e' (actual chunks include ['doc_computer_networks_6_e_p42_1', 'doc_computer_networks_6_e_p198_2']); Claimed chunk 'chunk_001' page 9 absent from DB; document has only 2 indexed chunks (p42 on OSI, p198 on sliding window).

### Candidate Evidence Passage
> In contrast to circuit switching, which reserves dedicated end-to-end bandwidth for the duration of a call, packet switching shares communication links dynamically using statistical multiplexing.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: NET-04
domain: "Computer Networks"
concept_a: "Packet Switching"
concept_b: "Circuit Switching"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [NET-05] Computer Networks: `Intrusion Detection System` — `Graph Neural Network`

- **Claimed Source Document:** `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf`
- **Claimed Chunk ID:** `chunk_003` (Claimed Page: 2)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Evidence text does not occur as verbatim substring in document 'papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf'.

### Candidate Evidence Passage
> We develop a real-time network intrusion detection system (NIDS) that models packet flow graphs using graph neural networks (GNNs) to identify malicious traffic.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: NET-05
domain: "Computer Networks"
concept_a: "Intrusion Detection System"
concept_b: "Graph Neural Network"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [NET-06] Computer Networks: `TCP Congestion Control` — `Graph Laplacian`

- **Claimed Source Document:** `papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf`
- **Claimed Chunk ID:** `chunk_005` (Claimed Page: 4)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Evidence text does not occur as verbatim substring in document 'papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf'.

### Candidate Evidence Passage
> Packet inter-arrival times and window sizes reflect network conditions during high-volume DDoS attacks across distributed nodes.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: NET-06
domain: "Computer Networks"
concept_a: "TCP Congestion Control"
concept_b: "Graph Laplacian"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [TOC-01] Automata Theory & Computation: `Deterministic Finite Automaton (DFA)` — `Regular Expression`

- **Claimed Source Document:** `papers/Willard2023_Outlines.pdf`
- **Claimed Chunk ID:** `chunk_002` (Claimed Page: 2)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Introductory automata theory definition ('Deterministic Finite Automaton (DFA)' / 'Regular Expression') falsely attributed to specialized LLM decoding preprint; passage does not occur in Willard 2023.

### Candidate Evidence Passage
> By Kleene theorem, every regular expression can be compiled into an equivalent deterministic finite automaton (DFA) that recognizes the corresponding regular language.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: TOC-01
domain: "Automata Theory & Computation"
concept_a: "Deterministic Finite Automaton (DFA)"
concept_b: "Regular Expression"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [TOC-02] Automata Theory & Computation: `Finite State Machine (FSM)` — `Formal Grammar`

- **Claimed Source Document:** `papers/Willard2023_Outlines.pdf`
- **Claimed Chunk ID:** `chunk_004` (Claimed Page: 3)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Introductory automata theory definition ('Finite State Machine (FSM)' / 'Formal Grammar') falsely attributed to specialized LLM decoding preprint; passage does not occur in Willard 2023.

### Candidate Evidence Passage
> To constrain language model outputs, we construct a finite state machine (FSM) derived from a formal context-free grammar or regular grammar.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: TOC-02
domain: "Automata Theory & Computation"
concept_a: "Finite State Machine (FSM)"
concept_b: "Formal Grammar"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [TOC-03] Automata Theory & Computation: `State Transition Function` — `Finite Automaton`

- **Claimed Source Document:** `papers/Willard2023_Outlines.pdf`
- **Claimed Chunk ID:** `chunk_003` (Claimed Page: 3)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Introductory automata theory definition ('State Transition Function' / 'Finite Automaton') falsely attributed to specialized LLM decoding preprint; passage does not occur in Willard 2023.

### Candidate Evidence Passage
> A finite automaton consists of a finite set of states Q, an alphabet Sigma, a transition function delta : Q x Sigma -> Q, an initial state, and accepting states.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: TOC-03
domain: "Automata Theory & Computation"
concept_a: "State Transition Function"
concept_b: "Finite Automaton"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [TOC-04] Automata Theory & Computation: `Deterministic Finite Automaton` — `Nondeterministic Finite Automaton`

- **Claimed Source Document:** `papers/Willard2023_Outlines.pdf`
- **Claimed Chunk ID:** `chunk_005` (Claimed Page: 4)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Introductory automata theory definition ('Deterministic Finite Automaton' / 'Nondeterministic Finite Automaton') falsely attributed to specialized LLM decoding preprint; passage does not occur in Willard 2023.

### Candidate Evidence Passage
> While an NFA allows epsilon-transitions and multiple next states for a single symbol, powerset construction converts any NFA into an equivalent DFA with at most 2^|Q| states.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: TOC-04
domain: "Automata Theory & Computation"
concept_a: "Deterministic Finite Automaton"
concept_b: "Nondeterministic Finite Automaton"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [TOC-05] Automata Theory & Computation: `Neural Text Generation` — `FSM Guidance`

- **Claimed Source Document:** `papers/Willard2023_Outlines.pdf`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 1)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Introductory automata theory definition ('Neural Text Generation' / 'FSM Guidance') falsely attributed to specialized LLM decoding preprint; passage does not occur in Willard 2023.

### Candidate Evidence Passage
> We guide autoregressive neural text generation by masking invalid vocabulary logits using an efficient index built from the FSM state transition matrix.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: TOC-05
domain: "Automata Theory & Computation"
concept_a: "Neural Text Generation"
concept_b: "FSM Guidance"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [TOC-06] Automata Theory & Computation: `Regular Language` — `Beam Search`

- **Claimed Source Document:** `papers/Willard2023_Outlines.pdf`
- **Claimed Chunk ID:** `chunk_008` (Claimed Page: 6)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Introductory automata theory definition ('Regular Language' / 'Beam Search') falsely attributed to specialized LLM decoding preprint; passage does not occur in Willard 2023.

### Candidate Evidence Passage
> Decoding strategies for large language models generate token sequences greedily or via stochastic sampling across output probabilities.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: TOC-06
domain: "Automata Theory & Computation"
concept_a: "Regular Language"
concept_b: "Beam Search"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [STAT-01] Probability & Statistics: `Bayes Theorem` — `Prior Probability`

- **Claimed Source Document:** `pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 12)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed expository passage attributed to back-of-the-book subject index 'pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf', which contains only keyword listings, not conceptual prose.

### Candidate Evidence Passage
> Bayes theorem calculates posterior probability P(w|x) by multiplying the prior probability P(w) by the class-conditional likelihood P(x|w), normalized by the evidence P(x).

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: STAT-01
domain: "Probability & Statistics"
concept_a: "Bayes Theorem"
concept_b: "Prior Probability"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [STAT-02] Probability & Statistics: `Probability Density Function (PDF)` — `Random Variable`

- **Claimed Source Document:** `pattern_recognition_2009/Appendix-A---Hints-from-Probability-and-Statistics_2009_Pattern-Recognition.pdf`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 1)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'pattern_recognition_2009/Appendix-A---Hints-from-Probability-and-Statistics_2009_Pattern-Recognition.pdf' (actual chunks include ['Appendix-A---Hints-from-Probability-and-Statistics_2009_Pattern-Recognition__structure']); Evidence text does not occur as verbatim substring in document 'pattern_recognition_2009/Appendix-A---Hints-from-Probability-and-Statistics_2009_Pattern-Recognition.pdf'.

### Candidate Evidence Passage
> For a continuous random variable X, the probability density function p(x) specifies the likelihood that X falls within an infinitesimal interval [x, x + dx].

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: STAT-02
domain: "Probability & Statistics"
concept_a: "Probability Density Function (PDF)"
concept_b: "Random Variable"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [STAT-03] Probability & Statistics: `Area under the ROC Curve (AUC)` — `Binary Classifier`

- **Claimed Source Document:** `data_science_2019/Index_2019_Data-Science.pdf`
- **Claimed Chunk ID:** `chunk_002` (Claimed Page: 310)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed expository passage attributed to back-of-the-book subject index 'data_science_2019/Index_2019_Data-Science.pdf', which contains only keyword listings, not conceptual prose.

### Candidate Evidence Passage
> The area under the receiver operating characteristic curve (AUC-ROC) measures the aggregate ranking performance of a binary classifier across all possible classification thresholds.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: STAT-03
domain: "Probability & Statistics"
concept_a: "Area under the ROC Curve (AUC)"
concept_b: "Binary Classifier"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [STAT-04] Probability & Statistics: `Bayesian Estimation` — `Maximum Likelihood Estimation`

- **Claimed Source Document:** `pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf`
- **Claimed Chunk ID:** `chunk_002` (Claimed Page: 15)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed expository passage attributed to back-of-the-book subject index 'pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf', which contains only keyword listings, not conceptual prose.

### Candidate Evidence Passage
> Unlike maximum likelihood estimation, which treats parameters theta as unknown fixed constants, Bayesian parameter estimation considers theta as a random variable governed by a prior distribution.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: STAT-04
domain: "Probability & Statistics"
concept_a: "Bayesian Estimation"
concept_b: "Maximum Likelihood Estimation"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [STAT-05] Probability & Statistics: `Nearest Neighbor` — `Probability Density Estimation`

- **Claimed Source Document:** `pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 13)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed expository passage attributed to back-of-the-book subject index 'pattern_recognition_2009/No-title-available_2009_Pattern-Recognition.pdf', which contains only keyword listings, not conceptual prose.

### Candidate Evidence Passage
> Non-parametric techniques use k-nearest neighbor density estimation to approximate arbitrary multi-modal probability distributions directly from sample observations.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: STAT-05
domain: "Probability & Statistics"
concept_a: "Nearest Neighbor"
concept_b: "Probability Density Estimation"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [STAT-06] Probability & Statistics: `Expectation` — `Gradient Descent`

- **Claimed Source Document:** `data_science_2019/Index_2019_Data-Science.pdf`
- **Claimed Chunk ID:** `chunk_004` (Claimed Page: 315)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed expository passage attributed to back-of-the-book subject index 'data_science_2019/Index_2019_Data-Science.pdf', which contains only keyword listings, not conceptual prose.

### Candidate Evidence Passage
> Mathematical optimization algorithms iterate over loss surfaces to minimize empirical prediction errors across validation splits.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: STAT-06
domain: "Probability & Statistics"
concept_a: "Expectation"
concept_b: "Gradient Descent"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [AI-01] Artificial Intelligence & Machine Learning: `Transformer Encoder` — `Self-Attention`

- **Claimed Source Document:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf`
- **Claimed Chunk ID:** `chunk_002` (Claimed Page: 3)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Evidence passage is a paraphrased or synthesized summary rather than verbatim text; chunk_id mismatch (claimed 'chunk_002').

### Candidate Evidence Passage
> The Transformer encoder consists of a stack of N = 6 identical layers. Each layer has two sub-layers: a multi-head self-attention mechanism, and a simple, position-wise fully connected feed-forward network.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: AI-01
domain: "Artificial Intelligence & Machine Learning"
concept_a: "Transformer Encoder"
concept_b: "Self-Attention"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [AI-02] Artificial Intelligence & Machine Learning: `Low-Rank Adaptation (LoRA)` — `Transformer Architecture`

- **Claimed Source Document:** `papers/Hu2021_LoRA.pdf`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 1)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Claimed chunk_id 'chunk_001' does not exist in 'papers/Hu2021_LoRA.pdf' (actual chunks include ['chunk_036', 'chunk_035', 'chunk_005']); Evidence passage is a paraphrased or synthesized summary rather than verbatim text; chunk_id mismatch (claimed 'chunk_001').

### Candidate Evidence Passage
> For a pre-trained Transformer model, we propose Low-Rank Adaptation (LoRA), which freezes the pre-trained model weights and injects trainable rank decomposition matrices into each layer.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: AI-02
domain: "Artificial Intelligence & Machine Learning"
concept_a: "Low-Rank Adaptation (LoRA)"
concept_b: "Transformer Architecture"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [AI-03] Artificial Intelligence & Machine Learning: `Query and Key Projections` — `Multi-Head Attention`

- **Claimed Source Document:** `papers/Vaswani2017_Attention_Is_All_You_Need.pdf`
- **Claimed Chunk ID:** `chunk_003` (Claimed Page: 4)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Evidence passage is a paraphrased or synthesized summary rather than verbatim text; chunk_id mismatch (claimed 'chunk_003').

### Candidate Evidence Passage
> Multi-head attention projects queries, keys, and values h times with different, learned linear projections of dimension d_k, d_k and d_v, respectively, allowing the model to jointly attend to information.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: AI-03
domain: "Artificial Intelligence & Machine Learning"
concept_a: "Query and Key Projections"
concept_b: "Multi-Head Attention"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [AI-04] Artificial Intelligence & Machine Learning: `LoRA` — `Prefix Tuning`

- **Claimed Source Document:** `papers/Hu2021_LoRA.pdf`
- **Claimed Chunk ID:** `chunk_002` (Claimed Page: 2)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Evidence passage is a paraphrased or synthesized summary rather than verbatim text; chunk_id mismatch (claimed 'chunk_002').

### Candidate Evidence Passage
> In contrast to prefix tuning or adapter layers, which insert additional latency or reduce usable sequence length, LoRA introduces no inference latency overhead because weights can be merged.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: AI-04
domain: "Artificial Intelligence & Machine Learning"
concept_a: "LoRA"
concept_b: "Prefix Tuning"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [AI-05] Artificial Intelligence & Machine Learning: `BERT` — `Masked Language Modeling`

- **Claimed Source Document:** `papers/Devlin2018_BERT.pdf`
- **Claimed Chunk ID:** `chunk_001` (Claimed Page: 2)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Evidence passage is a paraphrased or synthesized summary rather than verbatim text; chunk_id mismatch (claimed 'chunk_001').

### Candidate Evidence Passage
> BERT alleviates the unidirectionality constraint by using a "masked language model" (MLM) pre-training objective. The masked language model enables the representation to fuse both left and right context.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: AI-05
domain: "Artificial Intelligence & Machine Learning"
concept_a: "BERT"
concept_b: "Masked Language Modeling"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---

## [AI-06] Artificial Intelligence & Machine Learning: `Attention Head` — `Hardware Barrier`

- **Claimed Source Document:** `papers/Hu2021_LoRA.pdf`
- **Claimed Chunk ID:** `chunk_027` (Claimed Page: 9)
- **Source Verification Verdict:** `MISMATCH`
- **Audit Notes:** Evidence passage is a paraphrased or synthesized summary rather than verbatim text; chunk_id mismatch (claimed 'chunk_027').

### Candidate Evidence Passage
> Note that the low-rank structure lowers the hardware barrier to entry which allows us to run multiple experiments in parallel across commodity GPU nodes.

### Human Adjudication Form (To be completed by Independent Human Evaluator)
```yaml
item_id: AI-06
domain: "Artificial Intelligence & Machine Learning"
concept_a: "Attention Head"
concept_b: "Hardware Barrier"
concept_a_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
concept_b_valid: [ ]  # 1 = valid academic concept, 0 = invalid / non-academic phrase
relation_type: [ ]    # PREREQUISITE | PART_OF | USES | CONTRASTS_WITH | RELATED | NONE
prereq_direction: [ ] # A_PREREQ_FOR_B | B_PREREQ_FOR_A | UNDIRECTED | NONE
evidence_support: [ ] # 2 = direct verbatim support, 1 = partial/inferred, 0 = unsupported
source_verified: [ ]  # 1 = confirmed in source, 0 = source unverified / mismatched
confidence: [ ]       # HIGH | MEDIUM | LOW
uncertainty_flag: [ ] # TRUE | FALSE
human_notes: ""
```

---
