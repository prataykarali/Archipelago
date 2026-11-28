"""Curated domain-grounded definitions replacing empty, placeholder, or contaminated v1 summaries."""

from __future__ import annotations

#: Verified textbook-grade summaries for v1 nodes that had empty, placeholder, or
#: contaminated extraction summaries. Every entry eliminates template filler
#: ("X is a fundamental concept") and factual conflation.
SUMMARY_REPLACEMENTS: dict[str, str] = {
    # --- 6 contaminated summaries from D10-S7 / graph_semantics ---
    "transformer": (
        "An attention-based encoder-decoder neural architecture for sequence transduction "
        "that replaces recurrence and convolution with multi-head self-attention and "
        "position-wise feed-forward layers (Vaswani et al., 2017)."
    ),
    "gpt": (
        "Generative Pre-trained Transformer (GPT) is an autoregressive decoder-only "
        "Transformer language model family pretrained with causal next-token prediction."
    ),
    "gpt_2": (
        "GPT-2 is a unidirectional, autoregressive Transformer decoder language model "
        "(1,024-token context window) pretrained with causal next-token prediction on "
        "WebText (Radford et al., 2019)."
    ),
    "bm25": (
        "Okapi BM25 is a probabilistic bag-of-words lexical retrieval ranking function "
        "based on term-frequency saturation, inverse document frequency, and "
        "document-length normalization (Robertson & Zaragoza, 2009)."
    ),
    "dpr": (
        "Dense Passage Retrieval (DPR) uses dual BERT encoders for questions and passages "
        "trained with contrastive in-batch and hard negatives for maximum inner-product "
        "retrieval (Karpukhin et al., 2020)."
    ),
    "transformer_encoder": (
        "A stack of bidirectional multi-head self-attention and position-wise feed-forward "
        "layers that maps an input token sequence to contextualized representations "
        "(Vaswani et al., 2017)."
    ),
    # --- 26 placeholder-summary nodes ---
    "2d_discrete_convolution": (
        "A spatial filtering operation that slides a two-dimensional kernel over an input "
        "grid, computing element-wise products and sums to extract local features."
    ),
    "bellman_equation": (
        "A recursive optimality condition in dynamic programming and reinforcement learning "
        "expressing a state's value as immediate reward plus discounted future value."
    ),
    "bradley_terry_preference_model": (
        "A probabilistic pairwise comparison model expressing the probability that option "
        "y1 is preferred over y2 as a logistic function of their latent reward difference."
    ),
    "chemical_kinetics": (
        "The study of chemical reaction rates, rate laws, activation energies, and the "
        "mechanisms by which reactants transform into products over time."
    ),
    "conditional_probability": (
        "The probability P(A | B) = P(A and B) / P(B) of event A occurring given that "
        "event B with P(B) > 0 has already occurred."
    ),
    "data_link_layer": (
        "Layer 2 of the OSI network model, responsible for node-to-node framing, physical "
        "MAC addressing, media access control, and link-level error detection (e.g., CRC)."
    ),
    "digital_logic_gates": (
        "Elementary electronic circuits implementing Boolean functions (AND, OR, NOT, "
        "NAND, NOR, XOR) that form the building blocks of combinational and sequential hardware."
    ),
    "discrete_time_signals": (
        "Sequences of values indexed by discrete integer time steps, typically obtained "
        "by sampling continuous-time signals for digital signal processing."
    ),
    "divide_and_conquer": (
        "An algorithm design paradigm that recursively partitions a problem into smaller "
        "independent subproblems, solves them, and combines their solutions."
    ),
    "eigenvalues_and_eigenvectors": (
        "For a square matrix A, a non-zero vector v and scalar lambda satisfying A v = lambda v, "
        "characterizing invariant directions and scaling factors of a linear operator."
    ),
    "enthalpy": (
        "A thermodynamic state function H = U + PV measuring total heat content of a "
        "system at constant pressure, where delta H equals heat absorbed or released."
    ),
    "entropy": (
        "In information theory, Shannon entropy H(X) = -sum p(x) log p(x) quantifies the "
        "expected uncertainty or minimum average code length of a random variable."
    ),
    "error_detection": (
        "Techniques such as parity bits, checksums, and cyclic redundancy checks (CRC) "
        "that add redundant bits to detect transmission or storage corruption."
    ),
    "inheritance": (
        "An object-oriented programming mechanism allowing a subclass to acquire fields "
        "and methods from a superclass, supporting code reuse and subtype polymorphism."
    ),
    "inheritance_hierarchy": (
        "A tree or DAG of object-oriented classes ordered by superclass-subclass "
        "specialization relationships."
    ),
    "instruction_cycle": (
        "The fetch-decode-execute-writeback loop performed by a CPU to retrieve machine "
        "instructions from memory, decode opcodes, execute operations, and store results."
    ),
    "kernel_trick": (
        "A technique in machine learning that computes inner products in high-dimensional "
        "feature spaces implicitly via a positive-definite kernel function k(x, y)."
    ),
    "memory_hierarchy": (
        "The layered organization of computer storage from fast, small registers and CPU "
        "caches to main DRAM and slower persistent disks, exploiting locality of reference."
    ),
    "modular_arithmetic": (
        "Arithmetic over equivalence classes of integers modulo a positive integer n, "
        "underpinning number theory, hashing, and public-key cryptography such as RSA."
    ),
    "multilayer_perceptron": (
        "A feedforward artificial neural network composed of an input layer, one or more "
        "nonlinear hidden layers, and an output layer trained via backpropagation."
    ),
    "network_layer": (
        "Layer 3 of the OSI model, responsible for logical addressing (IP), packet "
        "forwarding, and end-to-end routing across interconnected networks."
    ),
    "priority_queue_mechanics": (
        "An abstract data type, commonly implemented with a binary heap, supporting "
        "O(log n) insertion and extraction of the minimum- or maximum-priority element."
    ),
    "set_theory": (
        "The mathematical study of collections of distinct objects and operations including "
        "union, intersection, complement, Cartesian product, relations, and cardinality."
    ),
    "token": (
        "A discrete lexical unit—such as a keyword, identifier, word, or subword—produced "
        "by tokenization in compilers or natural language processing."
    ),
    "transfer_learning_in_nlp": (
        "Reusing representations from a language model pretrained on large text corpora "
        "and adapting them to downstream NLP tasks via fine-tuning or prompting."
    ),
    "wave_equations": (
        "Second-order linear partial differential equations governing the propagation of "
        "mechanical, acoustic, and electromagnetic waves through space and time."
    ),
    # --- 55 empty-summary nodes ---
    "additive_increase_multiplicative_decrease": (
        "A feedback congestion-control algorithm (used in TCP) that increases sending rate "
        "linearly during congestion avoidance and halves it upon packet loss."
    ),
    "address_translation": (
        "Hardware-assisted mapping of a process's virtual memory addresses to physical RAM "
        "addresses via mechanisms such as base-and-bounds, segmentation, or page tables."
    ),
    "atomic_operations": (
        "Indivisible hardware instructions (e.g., compare-and-swap, test-and-set) that "
        "complete without interruption, forming the foundation of locks and lock-free code."
    ),
    "b_tree": (
        "A self-balancing m-way search tree keeping sorted keys in internal and leaf nodes "
        "to minimize disk I/O with O(log n) search, insertion, and deletion."
    ),
    "bankers_algorithm": (
        "Dijkstra's deadlock-avoidance algorithm that tests whether granting a resource "
        "request leaves the operating system in a safe execution state."
    ),
    "chomsky_hierarchy": (
        "A containment hierarchy of formal grammars and languages: Type-3 (regular) subset "
        "Type-2 (context-free) subset Type-1 (context-sensitive) subset Type-0 (recursively enumerable)."
    ),
    "clustered_index": (
        "A database index that determines the physical storage order of table rows on disk, "
        "commonly implemented using a B+ tree."
    ),
    "computability_theory": (
        "The branch of theoretical computer science studying which problems can be solved "
        "algorithmically by formal models of computation such as Turing machines."
    ),
    "concurrency": (
        "The structuring of a program or system so multiple computations make progress "
        "over overlapping time intervals, requiring synchronization for shared state."
    ),
    "concurrency_control": (
        "Database mechanisms (such as two-phase locking, timestamps, and MVCC) ensuring "
        "correctness and isolation when multiple transactions execute concurrently."
    ),
    "condition_variable": (
        "A synchronization primitive allowing threads to sleep until another thread "
        "signals that a shared predicate protected by a mutex has become true."
    ),
    "critical_section": (
        "A code region that accesses shared mutable state and must be executed by at most "
        "one thread or process at a time to prevent race conditions."
    ),
    "database_transaction": (
        "A logical unit of database work comprising one or more read/write operations that "
        "executes with ACID atomicity, consistency, isolation, and durability guarantees."
    ),
    "decidability": (
        "The property of a decision problem for which a Turing machine exists that halts "
        "with a correct yes/no answer on every valid input."
    ),
    "demand_paging": (
        "A virtual memory strategy that loads a page from secondary storage into physical "
        "memory only when a process triggers a page fault by accessing it."
    ),
    "extendible_hashing": (
        "A dynamic hash-indexing scheme using a directory of bucket pointers that doubles "
        "only when a bucket overflows, avoiding full-table rehashing."
    ),
    "finite_automata": (
        "Abstract state machines with a finite number of states and transitions that "
        "recognize exactly the class of regular languages."
    ),
    "flow_control": (
        "A transport-layer mechanism (such as TCP's advertised receive window rwnd) that "
        "prevents a fast sender from overwhelming a slower receiver's buffer."
    ),
    "foreign_key_constraint": (
        "A relational integrity rule requiring attribute values in a referencing table to "
        "match an existing primary or candidate key in a referenced table (or be NULL)."
    ),
    "formal_languages": (
        "Sets of finite strings over a finite alphabet defined by formal rules such as "
        "grammars, regular expressions, or automata."
    ),
    "graph_traversal": (
        "Systematic visitation of vertices and edges in a graph, primarily via Breadth-First "
        "Search (BFS) and Depth-First Search (DFS)."
    ),
    "halting_problem": (
        "The canonical undecidable problem of determining whether an arbitrary Turing "
        "machine will halt or run forever on a given input."
    ),
    "hash_table": (
        "An associative data structure mapping keys to array buckets via a hash function, "
        "achieving expected O(1) lookup, insertion, and deletion."
    ),
    "intermediate_code_generation": (
        "The compiler phase translating a semantically validated AST into a target-independent "
        "intermediate representation (IR) such as three-address code or SSA."
    ),
    "kernel_mode": (
        "A privileged CPU execution ring granting the operating system unrestricted access "
        "to hardware instructions, memory mappings, and I/O devices."
    ),
    "linear_algebra": (
        "The branch of mathematics studying vector spaces, linear transformations, matrices, "
        "systems of linear equations, eigenvalues, and matrix factorizations."
    ),
    "linear_transformation": (
        "A function T: V -> W between vector spaces preserving vector addition and scalar "
        "multiplication, representable by a matrix relative to chosen bases."
    ),
    "ll_parser": (
        "A top-down predictive parser that reads input Left-to-right and constructs a "
        "Leftmost derivation using k tokens of lookahead."
    ),
    "lr_parser": (
        "A deterministic bottom-up shift-reduce parser that reads input Left-to-right and "
        "constructs a Rightmost derivation in reverse."
    ),
    "multilevel_feedback_queue": (
        "An OS CPU scheduler maintaining multiple priority queues and dynamically adjusting "
        "job priority based on observed CPU vs. I/O behavior (OSTEP Ch. 8)."
    ),
    "nondeterministic_finite_automaton": (
        "A finite automaton allowing zero, one, or multiple transitions (and epsilon moves) "
        "from a state on a symbol; equivalent in expressive power to a DFA."
    ),
    "packet_encapsulation": (
        "The wrapping of higher-layer protocol data units with headers (and trailers) at "
        "each descending layer of a network protocol stack."
    ),
    "page_fault_handling": (
        "The OS trap routine invoked when an accessed virtual page is not present in RAM, "
        "loading the page from disk, updating the page table, and restarting the instruction."
    ),
    "parse_tree": (
        "An ordered rooted tree representing the syntactic derivation of a token string "
        "according to a context-free grammar."
    ),
    "preemptive_multitasking": (
        "An OS scheduling discipline where hardware timer interrupts allow the kernel to "
        "suspend a running process and context-switch to another process."
    ),
    "process_state": (
        "The lifecycle state of an OS process (e.g., ready, running, blocked/waiting, "
        "terminated) tracked in its Process Control Block."
    ),
    "producer_consumer_problem": (
        "A classic bounded-buffer concurrency problem coordinating producer and consumer "
        "threads using mutexes and condition variables or semaphores."
    ),
    "protocol_stack": (
        "A layered architecture of network protocols (such as OSI or TCP/IP) where each "
        "layer provides services to the layer above and relies on the layer below."
    ),
    "queue_mechanics": (
        "A First-In, First-Out (FIFO) linear data structure supporting O(1) enqueue at "
        "the rear and O(1) dequeue at the front."
    ),
    "range_scan": (
        "A database index lookup retrieving all records whose search key falls within a "
        "contiguous interval [low, high], accelerated by linked B+ tree leaf pages."
    ),
    "relational_algebra": (
        "A formal procedural query language over relations defined by selection, projection, "
        "union, set difference, Cartesian product, rename, and join operators."
    ),
    "resource_allocation_graph": (
        "A directed graph of processes and resources whose cycles indicate potential "
        "deadlock conditions in operating systems."
    ),
    "round_robin_scheduling": (
        "A preemptive CPU scheduling policy giving each ready process a fixed time quantum "
        "in cyclic FIFO order to ensure fairness and responsiveness."
    ),
    "segmentation": (
        "A virtual memory scheme dividing a process's address space into variable-sized "
        "logical segments (code, heap, stack), each with its own base and bounds."
    ),
    "semantic_analysis": (
        "The compiler phase following parsing that checks type compatibility, scope rules, "
        "and symbol-table declarations before intermediate code generation."
    ),
    "shortest_path_unweighted": (
        "Finding minimum-hop paths from a source vertex in an unweighted graph in O(V + E) "
        "time using Breadth-First Search (BFS)."
    ),
    "sliding_window_protocol": (
        "A pipelined reliable-delivery protocol allowing a sender to transmit multiple "
        "unacknowledged frames or segments up to a bounded window size."
    ),
    "spin_lock": (
        "A mutual-exclusion lock where waiting threads repeatedly poll an atomic variable "
        "in a busy loop until the lock becomes available."
    ),
    "stack_mechanics": (
        "A Last-In, First-Out (LIFO) linear data structure supporting O(1) push and pop "
        "operations, central to call frames and expression evaluation."
    ),
    "strongly_connected_components": (
        "Maximal subgraphs of a directed graph in which every vertex is mutually reachable "
        "from every other vertex, computable in O(V + E) time via Tarjan's or Kosaraju's algorithm."
    ),
    "tcp_ip_model": (
        "The four-layer Internet protocol architecture comprising Link, Internet (IP), "
        "Transport (TCP/UDP), and Application layers."
    ),
    "token_stream": (
        "The ordered sequence of lexical tokens emitted by a lexer and consumed by a "
        "compiler's syntax analyzer (parser)."
    ),
    "topological_sort": (
        "A linear ordering of vertices in a directed acyclic graph (DAG) such that for "
        "every directed edge u -> v, u appears before v."
    ),
    "two_phase_locking": (
        "A database concurrency-control protocol separating lock acquisition (growing phase) "
        "from lock release (shrinking phase) to guarantee conflict serializability."
    ),
    "write_ahead_logging": (
        "A database durability and crash-recovery protocol requiring log records of updates "
        "to be flushed to stable storage before the corresponding dirty data pages."
    ),
}
