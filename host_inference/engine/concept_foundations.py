"""Versioned concept foundation text used by existing reply composition."""

from __future__ import annotations

VERIFIED_CONCEPT_FOUNDATIONS: dict[str, str] = {
    "transformer": (
        "The foundational sequence-to-sequence neural architecture introduced by Vaswani et al. (2017) "
        "relying entirely on stacked self-attention and encoder-decoder cross-attention mechanisms, "
        "dispensing with recurrence and convolutions."
    ),
    "self_attention": (
        "An attention mechanism mapping query, key, and value vectors computed from the same sequence, "
        "enabling each token position to dynamically compute contextual attention weights across all sequence positions."
    ),
    "attention_mechanism": (
        "A neural computational module calculating dynamic alignment weights over input states, "
        "allowing the model to selectively focus on salient contextual features."
    ),
    "bert": (
        "Bidirectional Encoder Representations from Transformers (Devlin et al., 2018): an encoder-only architecture "
        "pretrained bidirectionally using Masked Language Modeling (MLM) and Next Sentence Prediction (NSP)."
    ),
    "low_rank_adaptation": (
        "Parameter-efficient fine-tuning (PEFT) method (Hu et al., 2021) that freezes pre-trained backbone weights "
        "and injects trainable rank-decomposition matrices (W0 + B x A) into dense attention layers, "
        "dramatically reducing trainable parameters without adding inference latency."
    ),
    "qlora": (
        "Efficient LLM fine-tuning technique (Dettmers et al., 2023) combining 4-bit NormalFloat (NF4) quantization, "
        "Double Quantization, and Paged Optimizers with Low-Rank Adaptation."
    ),
    "rag": (
        "Retrieval-Augmented Generation (Lewis et al., 2020): an architecture augmenting autoregressive language models "
        "with an external non-parametric retrieval index (dense vector index or knowledge graph) to supply retrieved context."
    ),
    "knowledge_graph": (
        "A structured knowledge base representing entities as nodes and verified semantic relations as directed or typed edges."
    ),
    # Academic Foundations — Operating Systems
    "context_switch": (
        "The kernel mechanism of saving the state of a currently running process or thread (program counter, registers, stack pointer) "
        "to its Process Control Block (PCB) and restoring the execution state of another process to resume execution on the CPU."
    ),
    "semaphore": (
        "A synchronization primitive initialized to an integer value, manipulated solely via atomic wait (P / sem_wait) "
        "and signal (V / sem_post) operations to coordinate access to shared resources and enforce mutual exclusion or signaling."
    ),
    "mutex_lock": (
        "A binary mutual exclusion lock providing cooperative synchronization where only the thread that acquired the lock can release it, "
        "ensuring that at most one thread executes within a critical section at any given time."
    ),
    "deadlock": (
        "A concurrent execution state where two or more processes are permanently blocked because each holds a resource and waits for another resource "
        "held by another process, satisfying Coffman's four conditions (mutual exclusion, hold and wait, no preemption, circular wait)."
    ),
    "deadlock_prevention": (
        "A set of structural constraints and design protocols ensuring that at least one of Coffman's four necessary conditions "
        "(such as circular wait, by establishing a strict global total resource ordering) can never hold."
    ),
    "virtual_memory": (
        "A memory management architecture that provides an idealized, private address space for each process, decoupling logical program addresses "
        "from physical DRAM addresses via page tables and memory management unit (MMU) hardware."
    ),
    "cpu_scheduling": (
        "The kernel policy and algorithmic mechanism (e.g. Round Robin, MLFQ, CFS) by which an operating system allocates CPU execution time "
        "among runnable threads, balancing throughput, turnaround time, latency, and fairness."
    ),
    # Academic Foundations — DBMS & SQL
    "b_plus_tree": (
        "A self-balancing search tree used in database index engines where all record pointers and keys are stored in leaf nodes linked sequentially "
        "for efficient range scans, while internal nodes store only routing keys for O(log N) searches."
    ),
    "hash_indexing": (
        "An index structure based on a mathematical hash function mapping search keys directly into bucket addresses, achieving O(1) expected time "
        "for exact-match equality queries but incapable of supporting range scans or ordered traversals."
    ),
    "acid_properties": (
        "The fundamental transaction guarantees required by relational database management systems: Atomicity (all or nothing), "
        "Consistency (preserves schema invariants), Isolation (serializable execution), and Durability (persistence across crashes)."
    ),
    "relational_database": (
        "A database system founded on E.F. Codd's relational model where data is structured into relations (tables) of tuples (rows) and attributes (columns), "
        "manipulated declaratively via relational calculus, relational algebra, and SQL."
    ),
    # Academic Foundations — Data Structures & Algorithms
    "breadth_first_search": (
        "A graph traversal and search algorithm that systematically explores all neighbor vertices at the current depth horizon before advancing "
        "to vertices at the next depth level, using a FIFO queue to discover unweighted shortest paths in O(V + E) time."
    ),
    "depth_first_search": (
        "A graph traversal algorithm that explores as deeply as possible along each branch before backtracking, utilizing recursion or an explicit LIFO stack "
        "to assign discovery and finish timestamps in O(V + E) time."
    ),
    # Academic Foundations — Computer Networks
    "tcp_congestion_control": (
        "The end-to-end congestion management mechanisms in TCP (Slow Start, Congestion Avoidance, Fast Retransmit, and Fast Recovery) that adaptively throttle "
        "transmission rate based on observed packet loss or round-trip delay feedback."
    ),
    "osi_model": (
        "The 7-layer Open Systems Interconnection conceptual architectural framework (Physical, Data Link, Network, Transport, Session, Presentation, Application) "
        "defining standardized boundaries and encapsulation for networked communication."
    ),
    # Academic Foundations — Compilers & Automata
    "lexical_analysis": (
        "The first phase of a compiler (tokenization / scanning) that converts an input source program character stream into a sequence of meaningful tokens "
        "according to regular expression patterns, stripping whitespace and comments."
    ),
    "syntax_analysis": (
        "The parsing phase of a compiler that receives the token sequence from lexical analysis and validates it against the grammatical productions of a "
        "Context-Free Grammar, producing a hierarchical parse tree or Abstract Syntax Tree."
    ),
    "abstract_syntax_tree": (
        "A condensed, hierarchical tree representation of source code syntax where interior nodes correspond to syntactic operators and leaf nodes represent operands, "
        "abstracting away concrete punctuation like semicolons and parentheses."
    ),
    "deterministic_finite_automaton": (
        "A 5-tuple abstract state machine (Q, Sigma, delta, q0, F) recognizing regular languages, characterized by having exactly one deterministic state transition "
        "for each state-symbol pair with no epsilon transitions."
    ),
    "turing_machine": (
        "The foundational mathematical model of computation consisting of an infinite tape, a read/write head, and a state register governed by transition functions, "
        "defining the boundary of algorithmic computability and the Church-Turing thesis."
    ),
    # Academic Foundations — Math & Machine Learning
    "matrix_multiplication": (
        "An algebraic operation producing a matrix from the linear combination of row and column vectors of two matrices, providing the foundational transformation "
        "mechanism for dense layers, attention projections, and embedding lookups in neural networks."
    ),
    "maximum_likelihood_estimation": (
        "A statistical method that estimates parameters of a probabilistic model by maximizing the likelihood function of observed sample data, forming the statistical "
        "underpinning of cross-entropy loss minimization in supervised machine learning."
    ),
    "bayes_theorem": (
        "A foundational probability theorem stating P(A|B) = P(B|A)P(A) / P(B), providing the principled mathematical basis for Bayesian inference, "
        "Maximum A Posteriori (MAP) estimation, and generative probabilistic modeling in machine learning."
    ),
}
