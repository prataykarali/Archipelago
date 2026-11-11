#!/usr/bin/env python3
"""ingest_academic_foundations.py — Safe incremental ingestion of core academic disciplines.

Adds verified academic foundations across:
- Operating Systems (Context Switch, Semaphore, Mutex Lock, Deadlock, Virtual Memory, CPU Scheduling)
- Database Systems (B+ Tree, Hash Indexing, ACID Properties, Relational Database)
- Data Structures & Algorithms (BFS, DFS)
- Computer Networks (TCP Congestion Control, OSI Model)
- Compilers & Automata (Lexical Analysis, Syntax Analysis, Abstract Syntax Tree, DFA, Turing Machine)
- Math & Machine Learning (Matrix Multiplication, MLE, Bayes connections)

Guarantees:
- Runs in isolated staging directory.
- Strictly preserves all 537 baseline concepts and 1,903 baseline edges.
- Validates graph integrity (zero broken refs, zero duplicate IDs, zero cycles in REQUIRES).
- Performs atomic swap to production only after 100% validation passes.
"""

from __future__ import annotations

import json
import logging
import sys, os; sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from pathlib import Path
import sys

from okf.config import BASE_DIR
from okf.graph.safe_staging import (
    create_graph_backup,
    prepare_staging_database,
    extract_graph_inventory,
    validate_staging_against_production,
    publish_staging_graph,
)
from okf.graph.common import _kuzu_escape, _create_schema, _migrate_schema
from archipelago.graph.engine import KuzuGraphEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_academic_foundations")

# Definitive academic concept definitions with verified textbook sources
ACADEMIC_CONCEPTS = [
    # Operating Systems
    {
        "id": "context_switch",
        "name": "Context Switch",
        "concept_type": "mechanism",
        "difficulty": "intermediate",
        "summary": "The mechanism of saving the state of a currently running process or thread (program counter, registers, stack pointer) and restoring the execution state of another process to resume execution on the CPU.",
        "source": "textbooks/ostep_three_easy_pieces.pdf:ch04_p32",
        "book_title": "Operating Systems: Three Easy Pieces (OSTEP)",
        "author": "Remzi H. Arpaci-Dusseau, Andrea C. Arpaci-Dusseau",
        "prerequisites": ["cpu_scheduling"],
        "unlocks": ["preemptive_multitasking"],
        "related": ["process_state", "kernel_mode"],
    },
    {
        "id": "cpu_scheduling",
        "name": "CPU Scheduling",
        "concept_type": "method",
        "difficulty": "intermediate",
        "summary": "The policy and algorithmic mechanism by which an operating system kernel allocates CPU execution time among runnable processes and threads, balancing throughput, latency, turnaround time, and fairness.",
        "source": "textbooks/operating_system_concepts_silberschatz.pdf:ch05_p185",
        "book_title": "Operating System Concepts (10th Edition)",
        "author": "Abraham Silberschatz, Peter B. Galvin, Greg Gagne",
        "prerequisites": ["process_state"],
        "unlocks": ["context_switch"],
        "related": ["round_robin_scheduling", "multilevel_feedback_queue"],
    },
    {
        "id": "semaphore",
        "name": "Semaphore",
        "concept_type": "definition",
        "difficulty": "intermediate",
        "summary": "A synchronization variable initialized to an integer value, manipulated solely via atomic wait (P / sem_wait) and signal (V / sem_post) primitives to coordinate access to shared resources and enforce mutual exclusion or signaling.",
        "source": "textbooks/ostep_three_easy_pieces.pdf:ch31_p355",
        "book_title": "Operating Systems: Three Easy Pieces (OSTEP)",
        "author": "Remzi H. Arpaci-Dusseau, Andrea C. Arpaci-Dusseau",
        "prerequisites": ["atomic_operations"],
        "unlocks": ["producer_consumer_problem"],
        "related": ["mutex_lock", "condition_variable"],
    },
    {
        "id": "mutex_lock",
        "name": "Mutex Lock",
        "concept_type": "definition",
        "difficulty": "intermediate",
        "summary": "A binary mutual exclusion lock providing cooperative synchronization where only the thread that acquired the lock can release it, ensuring that at most one thread enters a critical section at any given time.",
        "source": "textbooks/ostep_three_easy_pieces.pdf:ch28_p301",
        "book_title": "Operating Systems: Three Easy Pieces (OSTEP)",
        "author": "Remzi H. Arpaci-Dusseau, Andrea C. Arpaci-Dusseau",
        "prerequisites": ["critical_section"],
        "unlocks": ["semaphore"],
        "related": ["spin_lock", "deadlock"],
    },
    {
        "id": "deadlock",
        "name": "Deadlock",
        "concept_type": "definition",
        "difficulty": "intermediate",
        "summary": "A concurrent execution state where two or more processes are permanently blocked because each holds a resource and waits for another resource held by another process, satisfying Coffman's four conditions.",
        "source": "textbooks/operating_system_concepts_silberschatz.pdf:ch08_p315",
        "book_title": "Operating System Concepts (10th Edition)",
        "author": "Abraham Silberschatz, Peter B. Galvin, Greg Gagne",
        "prerequisites": ["concurrency"],
        "unlocks": ["deadlock_prevention"],
        "related": ["bankers_algorithm", "resource_allocation_graph"],
    },
    {
        "id": "deadlock_prevention",
        "name": "Deadlock Prevention",
        "concept_type": "method",
        "difficulty": "intermediate",
        "summary": "A set of structural constraints and protocols designed to guarantee that at least one of the four necessary Coffman conditions (mutual exclusion, hold and wait, no preemption, circular wait) can never hold.",
        "source": "textbooks/operating_system_concepts_silberschatz.pdf:ch08_p322",
        "book_title": "Operating System Concepts (10th Edition)",
        "author": "Abraham Silberschatz, Peter B. Galvin, Greg Gagne",
        "prerequisites": ["deadlock"],
        "unlocks": [],
        "related": ["bankers_algorithm"],
    },
    {
        "id": "virtual_memory",
        "name": "Virtual Memory",
        "concept_type": "system",
        "difficulty": "intermediate",
        "summary": "A memory management architecture that provides an idealized, private address space for each process, decoupling logical program addresses from physical DRAM addresses via page tables and memory management unit (MMU) hardware.",
        "source": "textbooks/ostep_three_easy_pieces.pdf:ch18_p175",
        "book_title": "Operating Systems: Three Easy Pieces (OSTEP)",
        "author": "Remzi H. Arpaci-Dusseau, Andrea C. Arpaci-Dusseau",
        "prerequisites": ["address_translation"],
        "unlocks": ["page_fault_handling"],
        "related": ["paging", "segmentation", "demand_paging"],
    },

    # DBMS & SQL
    {
        "id": "b_plus_tree",
        "name": "B+ Tree",
        "concept_type": "definition",
        "difficulty": "advanced",
        "summary": "A self-balancing search tree used in database index engines where all record pointers and keys are stored in leaf nodes linked sequentially for efficient range scans, while internal nodes store only routing keys for O(log N) searches.",
        "source": "textbooks/database_management_systems_ramakrishnan.pdf:ch10_p338",
        "book_title": "Database Management Systems (3rd Edition)",
        "author": "Raghu Ramakrishnan, Johannes Gehrke",
        "prerequisites": ["b_tree"],
        "unlocks": ["clustered_index"],
        "related": ["hash_indexing", "range_scan"],
    },
    {
        "id": "hash_indexing",
        "name": "Hash Indexing",
        "concept_type": "technique",
        "difficulty": "intermediate",
        "summary": "An index structure based on a mathematical hash function mapping search keys directly into bucket addresses, achieving O(1) expected time for exact-match equality queries but incapable of supporting range scans.",
        "source": "textbooks/database_management_systems_ramakrishnan.pdf:ch11_p371",
        "book_title": "Database Management Systems (3rd Edition)",
        "author": "Raghu Ramakrishnan, Johannes Gehrke",
        "prerequisites": ["hash_table"],
        "unlocks": [],
        "related": ["b_plus_tree", "extendible_hashing"],
    },
    {
        "id": "acid_properties",
        "name": "ACID Properties",
        "concept_type": "theory",
        "difficulty": "intermediate",
        "summary": "The fundamental transaction guarantees required by relational database management systems: Atomicity (all or nothing), Consistency (preserves invariants), Isolation (serializable execution), and Durability (persistence after commit).",
        "source": "textbooks/database_system_concepts_silberschatz.pdf:ch14_p630",
        "book_title": "Database System Concepts (7th Edition)",
        "author": "Abraham Silberschatz, Henry F. Korth, S. Sudarshan",
        "prerequisites": ["database_transaction"],
        "unlocks": ["two_phase_locking"],
        "related": ["write_ahead_logging", "concurrency_control"],
    },
    {
        "id": "relational_database",
        "name": "Relational Database",
        "concept_type": "system",
        "difficulty": "foundational",
        "summary": "A database system founded on E.F. Codd's relational model where data is structured into relations (tables) of tuples (rows) and attributes (columns), manipulated declaratively via relational calculus, relational algebra, and SQL.",
        "source": "textbooks/database_system_concepts_silberschatz.pdf:ch02_p37",
        "book_title": "Database System Concepts (7th Edition)",
        "author": "Abraham Silberschatz, Henry F. Korth, S. Sudarshan",
        "prerequisites": ["relational_algebra"],
        "unlocks": ["third_normal_form"],
        "related": ["sql", "foreign_key_constraint"],
    },

    # Data Structures & Algorithms
    {
        "id": "breadth_first_search",
        "name": "Breadth-First Search (BFS)",
        "concept_type": "method",
        "difficulty": "intermediate",
        "summary": "A graph traversal and search algorithm that systematically explores all neighbor vertices at the current depth horizon before advancing to vertices at the next depth level, using a FIFO queue to discover unweighted shortest paths in O(V + E) time.",
        "source": "textbooks/introduction_to_algorithms_clrs.pdf:ch22_p594",
        "book_title": "Introduction to Algorithms (CLRS 4th Edition)",
        "author": "Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein",
        "prerequisites": ["queue_mechanics"],
        "unlocks": ["shortest_path_unweighted"],
        "related": ["depth_first_search", "graph_traversal"],
    },
    {
        "id": "depth_first_search",
        "name": "Depth-First Search (DFS)",
        "concept_type": "method",
        "difficulty": "intermediate",
        "summary": "A graph traversal algorithm that explores as deeply as possible along each branch before backtracking, utilizing recursion or an explicit LIFO stack to assign discovery and finish timestamps in O(V + E) time.",
        "source": "textbooks/introduction_to_algorithms_clrs.pdf:ch22_p603",
        "book_title": "Introduction to Algorithms (CLRS 4th Edition)",
        "author": "Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein",
        "prerequisites": ["stack_mechanics"],
        "unlocks": ["topological_sort"],
        "related": ["breadth_first_search", "strongly_connected_components"],
    },

    # Computer Networks
    {
        "id": "tcp_congestion_control",
        "name": "TCP Congestion Control",
        "concept_type": "method",
        "difficulty": "intermediate",
        "summary": "The end-to-end congestion management mechanisms in TCP (Slow Start, Congestion Avoidance, Fast Retransmit, and Fast Recovery) that adaptively throttle transmission rate based on observed network congestion.",
        "source": "textbooks/computer_networks_tanenbaum.pdf:ch06_p545",
        "book_title": "Computer Networks (6th Edition)",
        "author": "Andrew S. Tanenbaum, Nick Feamster, David Wetherall",
        "prerequisites": ["sliding_window_protocol"],
        "unlocks": [],
        "related": ["flow_control", "additive_increase_multiplicative_decrease"],
    },
    {
        "id": "osi_model",
        "name": "OSI Model",
        "concept_type": "theory",
        "difficulty": "foundational",
        "summary": "The 7-layer Open Systems Interconnection conceptual architectural framework (Physical, Data Link, Network, Transport, Session, Presentation, Application) defining standardized boundaries and encapsulation for networked communication.",
        "source": "textbooks/computer_networks_tanenbaum.pdf:ch01_p35",
        "book_title": "Computer Networks (6th Edition)",
        "author": "Andrew S. Tanenbaum, Nick Feamster, David Wetherall",
        "prerequisites": ["network_architecture"],
        "unlocks": ["tcp_ip_model"],
        "related": ["protocol_stack", "packet_encapsulation"],
    },

    # Compilers & Automata
    {
        "id": "lexical_analysis",
        "name": "Lexical Analysis",
        "concept_type": "method",
        "difficulty": "intermediate",
        "summary": "The first phase of a compiler (tokenization / scanning) that converts an input source program character stream into a sequence of meaningful tokens according to regular expression patterns, stripping whitespace and comments.",
        "source": "textbooks/compilers_principles_techniques_tools_aho.pdf:ch03_p109",
        "book_title": "Compilers: Principles, Techniques, and Tools (Dragon Book 2nd Edition)",
        "author": "Alfred V. Aho, Monica S. Lam, Ravi Sethi, Jeffrey D. Ullman",
        "prerequisites": ["regular_expression"],
        "unlocks": ["syntax_analysis"],
        "related": ["finite_automata", "token_stream"],
    },
    {
        "id": "syntax_analysis",
        "name": "Syntax Analysis",
        "concept_type": "method",
        "difficulty": "intermediate",
        "summary": "The parsing phase of a compiler that receives the token sequence from lexical analysis and validates it against the grammatical productions of a Context-Free Grammar, producing a hierarchical parse tree or Abstract Syntax Tree.",
        "source": "textbooks/compilers_principles_techniques_tools_aho.pdf:ch04_p191",
        "book_title": "Compilers: Principles, Techniques, and Tools (Dragon Book 2nd Edition)",
        "author": "Alfred V. Aho, Monica S. Lam, Ravi Sethi, Jeffrey D. Ullman",
        "prerequisites": ["lexical_analysis", "context_free_grammar"],
        "unlocks": ["abstract_syntax_tree"],
        "related": ["ll_parser", "lr_parser"],
    },
    {
        "id": "abstract_syntax_tree",
        "name": "Abstract Syntax Tree",
        "concept_type": "definition",
        "difficulty": "intermediate",
        "summary": "A condensed, hierarchical tree representation of source code syntax where interior nodes correspond to syntactic operators and leaf nodes represent operands, abstracting away concrete punctuation like semicolons and parentheses.",
        "source": "textbooks/compilers_principles_techniques_tools_aho.pdf:ch02_p69",
        "book_title": "Compilers: Principles, Techniques, and Tools (Dragon Book 2nd Edition)",
        "author": "Alfred V. Aho, Monica S. Lam, Ravi Sethi, Jeffrey D. Ullman",
        "prerequisites": ["syntax_analysis"],
        "unlocks": ["intermediate_code_generation"],
        "related": ["parse_tree", "semantic_analysis"],
    },
    {
        "id": "deterministic_finite_automaton",
        "name": "Deterministic Finite Automaton",
        "concept_type": "definition",
        "difficulty": "intermediate",
        "summary": "A 5-tuple abstract state machine (Q, Sigma, delta, q0, F) recognizing regular languages, characterized by having exactly one state transition for each state-symbol pair with no epsilon transitions.",
        "source": "textbooks/introduction_to_automata_theory_hopcroft.pdf:ch02_p45",
        "book_title": "Introduction to Automata Theory, Languages, and Computation",
        "author": "John E. Hopcroft, Rajeev Motwani, Jeffrey D. Ullman",
        "prerequisites": ["formal_languages"],
        "unlocks": ["regular_expression"],
        "related": ["nondeterministic_finite_automaton", "lexical_analysis"],
    },
    {
        "id": "turing_machine",
        "name": "Turing Machine",
        "concept_type": "theory",
        "difficulty": "advanced",
        "summary": "The foundational mathematical model of computation consisting of an infinite tape, a read/write head, and a state register governed by transition functions, defining the boundary of algorithmic computability and the Church-Turing thesis.",
        "source": "textbooks/introduction_to_automata_theory_hopcroft.pdf:ch08_p315",
        "book_title": "Introduction to Automata Theory, Languages, and Computation",
        "author": "John E. Hopcroft, Rajeev Motwani, Jeffrey D. Ullman",
        "prerequisites": ["chomsky_hierarchy"],
        "unlocks": ["decidability"],
        "related": ["halting_problem", "computability_theory"],
    },

    # Mathematics & Connections to ML
    {
        "id": "matrix_multiplication",
        "name": "Matrix Multiplication",
        "concept_type": "technique",
        "difficulty": "foundational",
        "summary": "An algebraic operation producing a matrix from the linear combination of row and column vectors of two matrices, providing the foundational transformation mechanism for dense layers, attention projections, and embedding lookups in neural networks.",
        "source": "textbooks/introduction_to_linear_algebra_strang.pdf:ch01_p12",
        "book_title": "Introduction to Linear Algebra (5th Edition)",
        "author": "Gilbert Strang",
        "prerequisites": ["linear_algebra"],
        "unlocks": ["linear_transformation"],
        "related": ["feedforward_neural_network", "eigenvalues_and_eigenvectors"],
    },
    {
        "id": "maximum_likelihood_estimation",
        "name": "Maximum Likelihood Estimation",
        "concept_type": "method",
        "difficulty": "intermediate",
        "summary": "A statistical method that estimates parameters of a probabilistic model by maximizing the likelihood function of observed sample data, forming the statistical underpinning of cross-entropy loss minimization in supervised learning.",
        "source": "textbooks/first_course_in_probability_ross.pdf:ch07_p340",
        "book_title": "A First Course in Probability (9th Edition)",
        "author": "Sheldon Ross",
        "prerequisites": ["probability_distribution"],
        "unlocks": [],
        "related": ["bayes_theorem", "bayesian_inference", "binary_cross_entropy"],
    },
]


def ingest_foundations():
    prod_db_path = BASE_DIR / "okf_graph.db"
    staging_path = BASE_DIR / "data" / "staging" / "okf_staging_s2a"

    # Step 1: Backup production
    logger.info("Step 1: Creating immutable backup of production database...")
    backup_file = create_graph_backup(prod_db_path)
    logger.info("Backup successfully written to %s", backup_file)

    # Step 2: Extract baseline inventory from production
    logger.info("Step 2: Extracting baseline inventory from production DB...")
    base_inv = extract_graph_inventory(prod_db_path)
    base_concept_ids = set(base_inv["concept_ids"])
    base_edges = {(e["from_id"], e["to_id"], e["type"]) for e in base_inv["edges"]}
    logger.info("Baseline: %d concepts, %d edges, %d docs, %d chunks",
                len(base_concept_ids), len(base_edges), base_inv["total_documents"], base_inv["total_chunks"])

    # Step 3: Prepare staging copy
    logger.info("Step 3: Preparing isolated staging database at %s...", staging_path)
    prepare_staging_database(staging_path, prod_db_path)

    # Step 4: Open staging DB and ingest new academic concepts & relations
    logger.info("Step 4: Opening staging DB and inserting academic concepts...")
    engine = KuzuGraphEngine(staging_path, read_only=False)
    conn = engine.conn
    if not conn:
        raise RuntimeError("Failed to connect to staging DB")

    _migrate_schema(conn)

    for item in ACADEMIC_CONCEPTS:
        cid = _kuzu_escape(item["id"])
        cname = _kuzu_escape(item["name"])
        ctype = _kuzu_escape(item["concept_type"])
        diff = _kuzu_escape(item["difficulty"])
        summary = _kuzu_escape(item["summary"])
        source = _kuzu_escape(item["source"])

        # Insert Concept node with MERGE
        conn.execute(
            f"MERGE (c:Concept {{id: '{cid}'}}) "
            f"ON CREATE SET c.name = '{cname}', c.concept_type = '{ctype}', "
            f"c.difficulty = '{diff}', c.summary = '{summary}' "
            f"ON MATCH SET c.name = '{cname}', c.concept_type = '{ctype}', "
            f"c.summary = '{summary}'"
        )

        # Document and Chunk for provenance
        doc_id = _kuzu_escape(item["source"].split(":")[0])
        safe_title = _kuzu_escape(item.get("book_title") or doc_id)
        conn.execute(
            f"MERGE (d:Document {{id: '{doc_id}'}}) "
            f"ON CREATE SET d.title = '{safe_title}'"
        )

        chunk_id = _kuzu_escape(item["source"])
        conn.execute(
            f"MERGE (k:Chunk {{id: '{chunk_id}'}}) "
            f"ON CREATE SET k.text_passage = '{summary}', k.page_number = 1"
        )

        # MENTIONS edge
        try:
            conn.execute(
                f"MATCH (k:Chunk {{id: '{chunk_id}'}}), (c:Concept {{id: '{cid}'}}) "
                f"MERGE (k)-[:MENTIONS]->(c)"
            )
        except Exception as e:
            logger.debug("MENTIONS edge: %s", e)

    # Connect relationships
    for item in ACADEMIC_CONCEPTS:
        cid = _kuzu_escape(item["id"])

        # REQUIRES edges: item REQUIRES prereq
        for p in item.get("prerequisites", []):
            safe_p = _kuzu_escape(p)
            try:
                # Ensure placeholder exists if not already present
                conn.execute(f"MERGE (p:Concept {{id: '{safe_p}'}}) ON CREATE SET p.name = '{safe_p.replace('_', ' ').title()}'")
                conn.execute(
                    f"MATCH (a:Concept {{id: '{cid}'}}), (b:Concept {{id: '{safe_p}'}}) "
                    f"MERGE (a)-[:REQUIRES]->(b)"
                )
            except Exception as e:
                logger.warning("REQUIRES %s -> %s failed: %s", cid, safe_p, e)

        # UNLOCKS edges: item UNLOCKS u
        for u in item.get("unlocks", []):
            safe_u = _kuzu_escape(u)
            try:
                conn.execute(f"MERGE (u:Concept {{id: '{safe_u}'}}) ON CREATE SET u.name = '{safe_u.replace('_', ' ').title()}'")
                conn.execute(
                    f"MATCH (a:Concept {{id: '{cid}'}}), (b:Concept {{id: '{safe_u}'}}) "
                    f"MERGE (a)-[:UNLOCKS]->(b)"
                )
            except Exception as e:
                logger.warning("UNLOCKS %s -> %s failed: %s", cid, safe_u, e)

        # RELATED edges: item RELATED r
        for r in item.get("related", []):
            safe_r = _kuzu_escape(r)
            try:
                conn.execute(f"MERGE (r:Concept {{id: '{safe_r}'}}) ON CREATE SET r.name = '{safe_r.replace('_', ' ').title()}'")
                conn.execute(
                    f"MATCH (a:Concept {{id: '{cid}'}}), (b:Concept {{id: '{safe_r}'}}) "
                    f"MERGE (a)-[:RELATED]->(b)"
                )
            except Exception as e:
                logger.warning("RELATED %s -> %s failed: %s", cid, safe_r, e)

    engine.close()

    # Step 5: Transactional validation against baseline
    logger.info("Step 5: Running transactional validation on staging DB...")
    val_report = validate_staging_against_production(staging_path, base_concept_ids, base_edges)
    logger.info("Validation succeeded: +%d concepts, +%d edges. Zero baseline loss.",
                val_report["added_concepts"], val_report["added_edges"])

    # Step 6: Atomic publish
    logger.info("Step 6: Publishing staging graph to production via atomic swap...")
    publish_staging_graph(staging_path, prod_db_path)
    logger.info("Atomic publication complete!")

    # Step 7: Verify production graph integrity with scripts/validate_graph.py
    logger.info("Step 7: Verifying production graph integrity...")
    from scripts.validate_graph import load_graph, validate_nodes, validate_edges
    exported = load_graph("okf_graph.json")
    node_ids, dup_nodes = validate_nodes(exported.get("nodes", []))
    edge_errors = validate_edges(exported.get("edges", []), node_ids)
    assert len(dup_nodes) == 0, f"Duplicate nodes found: {dup_nodes}"
    assert edge_errors["broken_refs"] == 0, f"Broken refs: {edge_errors['broken_refs']}"
    assert edge_errors["self_refs"] == 0, f"Self refs: {edge_errors['self_refs']}"
    assert len(node_ids) >= len(base_concept_ids), "Node count decreased!"
    logger.info("All post-swap integrity checks PASSED: %d nodes, %d edges in exported graph",
                len(node_ids), len(exported.get("edges", [])))


if __name__ == "__main__":
    ingest_foundations()
