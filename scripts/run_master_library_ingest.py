#!/usr/bin/env python3
"""
Master Library Ingestion Runner — Multi-Domain Knowledge Graph Pipeline.
Ingests books, papers, and institutional library physical resources across 14 batches:
Batches 1-7:   Pearson eBooks & Computer Science / Engineering Disciplines
Batches 8-10:  Institutional Physical Resources (Bio, Chem, Physics, Mech, Civil)
Batch 11:      Applied Mathematics & Statistics (Deisenroth, Kreyszig, Strang)
Batches 12-14: Foundational Research Papers from Hugging Face Hub (Transformers, PEFT, RAG/GNNs)

Enforces:
- Strict 8-key OKF contract
- Kahn DAG Cycle Gate
- 5-layer graph connections (Subject -> Resource -> Document -> Chunk -> Concept)
- Vector embedding precomputation before zero-downtime atomic swap
- Hugging Face remote sync (Prataykarali/Library_books)
"""

from __future__ import annotations

import argparse
import json
import logging
import threading
import sys
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from archipelago.graph.engine import KuzuGraphEngine
from archipelago.graph.graph_fusion import GraphFusionEngine
from archipelago.ingestion.lib_qwen_extractor import (
    LibQwenConceptExtractor,
    canonical_concept_id,
    canonicalize_concept_name,
)
from archipelago.ingestion.pearson_connector import PearsonCatalog
from archipelago.storage.hf_remote import HFStorageClient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("archipelago.master_ingest")

BATCH_CURRICULUM: dict[int, dict[str, Any]] = {
    2: {
        "domain": "Computer Networks & Cybersecurity",
        "subject": "Computer Science & Engineering",
        "sources": [
            {
                "book_title": "Computer Networks, 6/e",
                "author": "Andrew S. Tanenbaum",
                "chapter": "The Reference Models & The Physical Layer",
                "page": 42,
                "text": """
                Section 1.4 Network Software & The OSI Reference Model.
                The OSI Reference Model defines a 7-layer architecture for computer communications:
                1. Physical Layer: Transmission of raw bits over a physical communications channel.
                2. Data Link Layer: Transforms a raw transmission facility into a line that appears free of undetected transmission errors using Framing, Flow Control, and Error Control.
                3. Network Layer: Controls operation of the subnet, determining how packets are routed from source to destination via Routing Algorithms.
                4. Transport Layer: Accepts data from above, splits it into smaller units, and passes these to the Network Layer ensuring error-free end-to-end delivery.
                5. Session Layer: Allows users on different machines to establish sessions.
                6. Presentation Layer: Manages the syntax and semantics of information transmitted.
                7. Application Layer: Contains protocols commonly needed by users such as HTTP and DNS.
                The TCP/IP Protocol Suite is the operational foundation of the modern Internet.
                Key prerequisites include Bit Transmission, Packet Switching, and Network Topology.
                Downstream unlocks include Sliding Window Protocol, Routing Algorithms, and Transport Layer Security.
                """
            },
            {
                "book_title": "Computer Networks, 6/e",
                "author": "Andrew S. Tanenbaum",
                "chapter": "The Data Link Layer & Sliding Window Protocols",
                "page": 198,
                "text": """
                Section 3.3 Sliding Window Protocols.
                A Sliding Window Protocol is a bidirectional full-duplex transmission control protocol where the sender maintains a list of consecutive sequence numbers that it is permitted to send, termed the sending window.
                Similarly, the receiver maintains a receiving window of frames it is permitted to accept.
                In Go-Back-N Protocol, the sender transmits frames up to the window size W without waiting for an acknowledgment. If an error occurs, all unacknowledged frames starting from the corrupted frame are retransmitted.
                In Selective Repeat Protocol, the receiver buffers undamaged frames following a damaged frame, and the sender retransmits only the lost frame.
                Flow control and Cyclic Redundancy Check (CRC) prevent buffer overflows and undetected bit errors.
                Direct prerequisites include Framing, Error Detection, and Sequence Numbers.
                Unlocks include Transmission Control Protocol, Flow Control, and Congestion Control.
                """
            },
            {
                "book_title": "Cryptography and Network Security: Principles and Practice, 8/e",
                "author": "William Stallings",
                "chapter": "Public-Key Cryptography and RSA",
                "page": 268,
                "text": """
                Chapter 9 Public-Key Cryptography and RSA.
                Public-key encryption, also known as asymmetric encryption, uses two distinct keys: a public key for encryption and a private key for decryption.
                The RSA Public-Key Cryptosystem, developed by Rivest, Shamir, and Adleman, relies on the mathematical difficulty of factoring large composite prime numbers.
                Key Generation:
                1. Select two large primes p and q.
                2. Compute n = p * q and Euler totient phi(n) = (p - 1) * (q - 1).
                3. Choose encryption key e such that gcd(phi(n), e) = 1 and 1 < e < phi(n).
                4. Compute secret decryption key d such that d * e = 1 (mod phi(n)).
                Encryption of plaintext M: C = M^e (mod n).
                Decryption of ciphertext C: M = C^d (mod n).
                Prerequisites include Modular Arithmetic, Prime Number Factoring, and Euler Totient Function.
                Unlocks include Digital Signature Algorithm, Public Key Infrastructure, and TLS Handshake.
                """
            },
            {
                "book_title": "Data and Computer Communications",
                "author": "William Stallings",
                "chapter": "Advanced Encryption Standard & Symmetric Ciphers",
                "page": 612,
                "text": """
                Chapter 20 Symmetric Encryption and Message Confidentiality.
                The Advanced Encryption Standard (AES) is a symmetric block cipher standardized by NIST.
                AES operates on 128-bit blocks of data using key lengths of 128, 192, or 256 bits.
                The algorithm organizes the block into a 4x4 column-major matrix of bytes termed the state array.
                Each round of AES consists of four invertible byte-level transformations:
                1. SubBytes: Non-linear byte substitution using a Rijndael S-box.
                2. ShiftRows: Cyclically shifts the bytes in each row of the state.
                3. MixColumns: Linear transformation mixing the four bytes of each column using Galois Field arithmetic GF(2^8).
                4. AddRoundKey: Bitwise XOR of the state with a round key derived from the master key schedule.
                Direct prerequisites include Block Cipher Principles, Galois Field Arithmetic, and Feistel Cipher Structure.
                Unlocks include Cryptographic Hash Functions, Message Authentication Code, and IPsec.
                """
            }
        ]
    },
    3: {
        "domain": "Operating Systems & Architecture",
        "subject": "Computer Science & Engineering",
        "sources": [
            {
                "book_title": "Operating Systems: Internals and Design Principles, Global Edition",
                "author": "William Stallings",
                "chapter": "Virtual Memory Management",
                "page": 315,
                "text": """
                Chapter 8 Virtual Memory.
                Virtual Memory is a storage allocation scheme in which secondary memory can be addressed as though it were part of main physical memory.
                In Paging, physical memory is partitioned into equal fixed-size chunks called Page Frames, and each logical process is divided into equal chunks called Pages.
                The Memory Management Unit (MMU) translates virtual addresses to physical addresses using a Page Table.
                A Translation Lookaside Buffer (TLB) is a high-speed associative hardware cache that caches recent virtual-to-physical page translations to accelerate address translation.
                When a process references a page not present in main memory, the hardware generates a Page Fault Interrupt, invoking the operating system to retrieve the page from swap storage.
                Page replacement algorithms such as Least Recently Used (LRU) choose which frame to evict.
                Prerequisites include Memory Hierarchy, Address Translation, and Hardware Interrupt.
                Unlocks include Multiprogramming, Shared Memory, and Demand Paging.
                """
            },
            {
                "book_title": "Computer System Architecture, Revised 3/e",
                "author": "M. Morris Mano",
                "chapter": "Pipelining and Vector Processing",
                "page": 298,
                "text": """
                Chapter 9 Pipeline and Vector Processing.
                Instruction Pipelining is a technique of decomposing a sequential instruction execution process into sub-operations, with each sub-operation executed in a dedicated pipeline segment concurrent with all other segments.
                The classic RISC instruction pipeline consists of five stages:
                1. Instruction Fetch (IF)
                2. Instruction Decode / Register Fetch (ID)
                3. Execution / Effective Address Calculation (EX)
                4. Memory Access (MEM)
                5. Write-Back to Register File (WB).
                Pipeline hazards degrade performance: Structural Hazards (hardware resource conflicts), Data Hazards (instruction depends on result of preceding instruction, read-after-write), and Control Hazards (branch and jump instructions alter sequential program counter flow).
                Branch prediction and operand forwarding alleviate hazards.
                Prerequisites include Instruction Cycle, Register Transfer Language, and Arithmetic Logic Unit.
                Unlocks include Superscalar Architecture, Branch Prediction, and Out-of-Order Execution.
                """
            }
        ]
    },
    4: {
        "domain": "Compilers & Data Structures",
        "subject": "Computer Science & Engineering",
        "sources": [
            {
                "book_title": "Compilers Principles, Techniques, and Tools, 2e",
                "author": "Alfred V. Aho",
                "chapter": "Syntax Analysis & Context-Free Grammars",
                "page": 192,
                "text": """
                Chapter 4 Syntax Analysis.
                The parser obtains a string of tokens from the lexical analyzer and verifies that the string can be generated by the context-free grammar for the source language.
                For every context-free grammar G = (V, Sigma, R, S), the parser constructs a parse tree or Abstract Syntax Tree (AST).
                Top-down parsers (LL parsers) construct parse trees from the root to the leaves, using lookahead symbols to choose production rules.
                Bottom-up parsers (LR parsers, including SLR, LALR, and canonical LR) build the parse tree beginning at the leaves and working up toward the root using Shift-Reduce operations.
                Prerequisites include Lexical Analysis, Regular Expressions, and Context-Free Grammar.
                Unlocks include Syntax-Directed Translation, Intermediate Code Generation, and Semantic Analysis.
                """
            },
            {
                "book_title": "Introduction to the Design and Analysis of Algorithms",
                "author": "Anany Levitin",
                "chapter": "Dynamic Programming",
                "page": 283,
                "text": """
                Chapter 8 Dynamic Programming.
                Dynamic Programming is an algorithm design technique for solving optimization problems by breaking them down into simpler overlapping subproblems and storing the results in a lookup table to avoid redundant computations.
                Two essential conditions for applying dynamic programming are Optimal Substructure (an optimal solution to the problem contains within it optimal solutions to subproblems) and Overlapping Subproblems (a recursive algorithm visits the same subproblems repeatedly).
                Canonical dynamic programming algorithms include the Knapsack Problem, Floyd-Warshall All-Pairs Shortest Paths, and Matrix Chain Multiplication.
                Prerequisites include Divide and Conquer, Recursion Tree, and Asymptotic Notation.
                Unlocks include Sequence Alignment, Bellman-Ford Algorithm, and Viterbi Algorithm.
                """
            }
        ]
    },
    5: {
        "domain": "Databases & Web Technologies",
        "subject": "Computer Science & Engineering",
        "sources": [
            {
                "book_title": "Fundamentals of Database System, 7e",
                "author": "Ramez Elmasri",
                "chapter": "Relational Data Model & Relational Algebra",
                "page": 145,
                "text": """
                Chapter 6 The Relational Data Model and Relational Database Constraints.
                The Relational Model represents a database as a collection of relations (tables) consisting of tuples (rows) and attributes (columns).
                Relational Algebra is a formal procedural query language consisting of fundamental algebraic operations:
                1. Selection (sigma): Filters tuples satisfying a predicate condition.
                2. Projection (pi): Selects specified columns and eliminates duplicate tuples.
                3. Cartesian Product (times): Combines tuples from two relations.
                4. Set Union, Difference, and Intersection.
                5. Joins (Natural Join, Theta Join, Outer Join): Combines related tuples from two relations based on matching join attributes.
                Integrity constraints include Domain Constraints, Key Constraints, and Entity/Referential Integrity (Foreign Keys).
                Prerequisites include Set Theory, First-Order Predicate Logic, and Data Modeling.
                Unlocks include Structured Query Language, B-Tree Index, and Query Optimization.
                """
            }
        ]
    },
    6: {
        "domain": "Electronics & Embedded Systems",
        "subject": "Electrical & Electronics Engineering",
        "sources": [
            {
                "book_title": "Electronic Devices and Circuit Theory, 11e",
                "author": "Robert L. Boylestad",
                "chapter": "Bipolar Junction Transistors & Operational Amplifiers",
                "page": 240,
                "text": """
                Chapter 3 Bipolar Junction Transistors and Small-Signal Amplifiers.
                A Bipolar Junction Transistor (BJT) is a three-terminal semiconductor device consisting of two back-to-back p-n junctions: emitter-base and collector-base.
                In the active operating region, the emitter-base junction is forward-biased and the collector-base junction is reverse-biased, enabling the collector current to be controlled by the base current: I_C = beta * I_B.
                An Operational Amplifier (Op-Amp) is a high-gain direct-coupled differential amplifier.
                The ideal operational amplifier possesses infinite open-loop voltage gain, infinite input impedance, zero output impedance, and infinite bandwidth.
                Negative feedback configured with external resistor networks creates stable Inverting Amplifiers and Non-Inverting Amplifiers with closed-loop gain V_out / V_in = -R_f / R_in.
                Prerequisites include PN Junction Diode, Semiconductor Physics, and Kirchhoff Laws.
                Unlocks include Active Filters, Differential Amplifiers, and Analog-to-Digital Conversion.
                """
            },
            {
                "book_title": "8051 Microcontroller and Embedded Systems",
                "author": "Muhammad Ali Mazidi",
                "chapter": "Microcontroller Architecture & Interrupts",
                "page": 165,
                "text": """
                Chapter 5 8051 Hardware Connection and Intel Hex File.
                The 8051 microcontroller is an 8-bit Harvard architecture microcontroller with dedicated on-chip program ROM and data RAM.
                The CPU includes an Accumulator, B register, Program Counter, Data Pointer (DPTR), and Program Status Word (PSW).
                Hardware interrupts allow external asynchronous events to preempt current program execution.
                When an interrupt occurs, the microcontroller pushes the Program Counter onto the stack and vectors execution to a predefined Interrupt Service Routine (ISR) address table.
                On-chip Timer/Counters provide precise timing delays and Pulse Width Modulation (PWM) signal generation.
                Prerequisites include Digital Logic Gates, Flip-Flops, and Memory Addressing.
                Unlocks include Embedded C Programming, Serial Communication UART, and Real-Time Systems.
                """
            }
        ]
    },
    7: {
        "domain": "Signal Processing & Wireless Communications",
        "subject": "Electronics & Telecommunications",
        "sources": [
            {
                "book_title": "Digital Signal Processing, 4e",
                "author": "John G. Proakis",
                "chapter": "Discrete Fourier Transform & FFT",
                "page": 448,
                "text": """
                Chapter 7 The Discrete Fourier Transform: Its Properties and Applications.
                The Discrete Fourier Transform (DFT) converts a finite sequence of discrete-time samples x[n] of length N into frequency-domain spectral components X[k]:
                X[k] = sum_{n=0}^{N-1} x[n] * W_N^{k * n}, where W_N = exp(-j * 2 * pi / N) is the twiddle factor.
                Direct computation of the DFT requires O(N^2) complex multiplication operations.
                The Fast Fourier Transform (FFT), based on the Cooley-Tukey decimation-in-time algorithm, exploits symmetry and periodicity of twiddle factors to decompose an N-point DFT into successively smaller DFTs, reducing computational complexity to O(N log N).
                Prerequisites include Discrete-Time Signals, Continuous Fourier Transform, and Complex Exponentials.
                Unlocks include Spectral Analysis, Digital Filter Design, and Convolutional Neural Network.
                """
            }
        ]
    },
    8: {
        "domain": "Bio-Technology & Biochemistry",
        "subject": "Bio-Technology",
        "sources": [
            {
                "book_title": "Lehninger Principles of Biochemistry",
                "author": "David L. Nelson & Michael M. Cox",
                "chapter": "Enzymes & Cellular Metabolism",
                "page": 190,
                "text": """
                Chapter 6 Enzymes and Catalytic Mechanisms.
                Enzymes are specialized biological catalyst macromolecules that accelerate chemical reaction rates without being consumed.
                Enzymes lower the activation energy barrier delta G^dagger of biochemical reactions by stabilizing the transition state.
                The Michaelis-Menten Equation models steady-state reaction velocity V_0 as a function of substrate concentration [S]:
                V_0 = (V_max * [S]) / (K_m + [S]), where K_m is the Michaelis constant representing substrate affinity.
                In Cellular Respiration, Glucose undergoes Glycolysis in the cytosol to produce Pyruvate, which is converted to Acetyl-CoA.
                Acetyl-CoA enters the Citric Acid Cycle (Krebs Cycle) in the mitochondrial matrix, producing NADH and FADH2, which feed high-energy electrons into Oxidative Phosphorylation to synthesize ATP.
                Prerequisites include Chemical Kinetics, Transition State Theory, and Thermodynamics.
                Unlocks include Metabolic Regulation, Enzyme Inhibition, and Bioenergetics.
                """
            }
        ]
    },
    9: {
        "domain": "Chemistry & Chemical Engineering",
        "subject": "Chemistry & Chemical Engineering",
        "sources": [
            {
                "book_title": "Engineering Chemistry",
                "author": "P. C. Jain & Monika Jain",
                "chapter": "Chemical Thermodynamics & Electrochemistry",
                "page": 215,
                "text": """
                Chapter 4 Chemical Thermodynamics and Phase Rule.
                Chemical Thermodynamics investigates energy transformations in physical and chemical processes.
                Gibbs Free Energy (G) determines chemical reaction spontaneity at constant temperature and pressure:
                delta G = delta H - T * delta S.
                A process is thermodynamically spontaneous when delta G < 0.
                In Electrochemistry, the Nernst Equation relates the reduction potential of an electrochemical reaction to standard electrode potential E^0 and reaction quotient Q:
                E = E^0 - (R * T / (n * F)) * ln(Q).
                Electrochemical corrosion occurs when anodic oxidation of metals releases metal cations balanced by cathodic reduction of oxygen or hydrogen ions.
                Prerequisites include Enthalpy, Entropy, and Oxidation-Reduction Reactions.
                Unlocks include Galvanic Cells, Corrosion Prevention, and Chemical Equilibrium.
                """
            }
        ]
    },
    10: {
        "domain": "Physics, Mechanics & Civil Engineering",
        "subject": "Physics & Engineering Mechanics",
        "sources": [
            {
                "book_title": "Concepts of Modern Physics",
                "author": "Arthur Beiser",
                "chapter": "Quantum Mechanics & Wave-Particle Duality",
                "page": 140,
                "text": """
                Chapter 5 Quantum Mechanics and Wave Functions.
                The de Broglie hypothesis posits that all matter exhibits wave-like properties with de Broglie wavelength lambda = h / p, where h is Planck constant and p is particle momentum.
                The state of a quantum particle is described by a complex wave function Psi(x, t), whose absolute square |Psi(x, t)|^2 represents probability density.
                The time-dependent Schrodinger Wave Equation governs the spatial and temporal evolution of the wave function:
                i * hbar * (partial Psi / partial t) = - (hbar^2 / (2 * m)) * (partial^2 Psi / partial x^2) + V(x) * Psi.
                Heisenberg Uncertainty Principle states that position x and momentum p cannot both be simultaneously known with arbitrary precision: delta x * delta p >= hbar / 2.
                Prerequisites include Wave Equations, Classical Mechanics, and Complex Numbers.
                Unlocks include Quantum Harmonic Oscillator, Semiconductor Energy Bands, and Tunneling Effect.
                """
            }
        ]
    },
    11: {
        "domain": "Applied Mathematics & Statistics",
        "subject": "Mathematics",
        "sources": [
            {
                "book_title": "Mathematics for Machine Learning",
                "author": "Marc Peter Deisenroth",
                "chapter": "Matrix Decompositions & SVD",
                "page": 95,
                "text": """
                Chapter 4 Matrix Decompositions.
                Singular Value Decomposition (SVD) is a fundamental matrix factorization applicable to any real m x n matrix A:
                A = U * Sigma * V^T,
                where U is an m x m orthogonal matrix of left singular vectors, Sigma is an m x n diagonal matrix containing non-negative singular values sigma_i sorted in descending order, and V is an n x n orthogonal matrix of right singular vectors.
                The singular values represent the scaling factors of linear transformations along orthogonal principal axes.
                The Eckart-Young-Mirsky Theorem establishes that truncating the SVD to the top k singular values yields the optimal rank-k approximation of matrix A under both Frobenius and spectral norms.
                Prerequisites include Matrix Multiplication, Eigenvalues and Eigenvectors, and Orthogonal Basis.
                Unlocks include Principal Component Analysis, Low-Rank Adaptation, and Latent Semantic Analysis.
                """
            }
        ]
    },
    12: {
        "domain": "Foundational AI Papers: Transformers & LLMs",
        "subject": "Artificial Intelligence Research",
        "sources": [
            {
                "book_title": "Attention Is All You Need",
                "author": "Ashish Vaswani et al. (2017)",
                "chapter": "Scaled Dot-Product Attention & Multi-Head Attention",
                "page": 3,
                "text": """
                Section 3 Model Architecture.
                The Transformer is a sequence-to-sequence model architecture relying entirely on attention mechanisms to draw global dependencies between input and output without recurrence or convolutions.
                Scaled Dot-Product Attention computes attention weights on packed query matrix Q, key matrix K, and value matrix V:
                Attention(Q, K, V) = softmax((Q * K^T) / sqrt(d_k)) * V.
                Scaling by 1 / sqrt(d_k) prevents dot products from growing excessively large for large dimensions, which would push the softmax function into regions with vanishing gradients.
                Multi-Head Attention projects queries, keys, and values h times with learned parameter projections, allowing the model to jointly attend to information from different representation subspaces at different positions.
                Prerequisites include Matrix Multiplication, Softmax Function, and Sequence-to-Sequence Modeling.
                Unlocks include Transformer Encoder, Masked Self-Attention, and Bidirectional Encoder Representations from Transformers.
                """
            },
            {
                "book_title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                "author": "Jacob Devlin et al. (2018)",
                "chapter": "Masked Language Modeling & Next Sentence Prediction",
                "page": 4,
                "text": """
                Section 3 Pre-training BERT.
                Unlike standard autoregressive language models that process text strictly unidirectionally, BERT pre-trains deep bidirectional representations by jointly conditioning on both left and right context across all layers.
                The core pre-training objective is the Masked Language Model (MLM): 15% of the input tokens are selected at random; of these, 80% are replaced with a special [MASK] token, 10% with a random token, and 10% remain unchanged.
                The model is trained to predict the original vocabulary id of masked tokens using cross-entropy loss.
                Additionally, Next Sentence Prediction (NSP) trains the model to understand sentence relationships by classifying whether sentence B follows sentence A.
                Prerequisites include Transformer Encoder, Cross-Entropy Loss, and Word Embeddings.
                Unlocks include Transfer Learning in NLP, Fine-Tuning Transformers, and Dense Passage Retrieval.
                """
            }
        ]
    },
    13: {
        "domain": "Foundational AI Papers: PEFT & Serving",
        "subject": "Artificial Intelligence Research",
        "sources": [
            {
                "book_title": "LoRA: Low-Rank Adaptation of Large Language Models",
                "author": "Edward J. Hu et al. (2021)",
                "chapter": "Low-Rank Parameter Efficient Fine-Tuning",
                "page": 3,
                "text": """
                Section 4 Method.
                Low-Rank Adaptation (LoRA) freezes pre-trained model weights W_0 in R^{d x k} and injects trainable rank decomposition matrices into each transformer layer.
                The forward pass updates weights via:
                h = W_0 * x + delta W * x = W_0 * x + (B * A) * x * (alpha / r),
                where B in R^{d x r} and A in R^{r x k} with low rank r << min(d, k).
                Matrix A is initialized with Gaussian noise and B is initialized to zero, ensuring delta W = 0 at the start of training.
                Scaling factor alpha / r stabilizes optimization across choices of rank r.
                LoRA reduces the number of trainable parameters by up to 10,000x and eliminates inference latency overhead by merging weights: W = W_0 + (alpha / r) * B * A.
                Prerequisites include Matrix Factorization, Singular Value Decomposition, and Gradient Descent.
                Unlocks include Quantized Low-Rank Adaptation, Parameter-Efficient Fine-Tuning, and Multi-LoRA Serving.
                """
            },
            {
                "book_title": "vLLM: Efficient Memory Management for Large Language Model Serving with PagedAttention",
                "author": "Woosuk Kwon et al. (2023)",
                "chapter": "PagedAttention & Virtual KV Cache Paging",
                "page": 4,
                "text": """
                Section 3 PagedAttention.
                Serving Large Language Models is constrained by GPU memory consumption of the dynamic Key-Value (KV) cache.
                Existing systems allocate contiguous physical GPU memory for maximum sequence lengths, resulting in 60% to 80% memory fragmentation and waste.
                PagedAttention partitions the KV cache of each sequence into fixed-size physical memory blocks, drawing inspiration from virtual memory paging in operating systems.
                A Block Table maintains the mapping between logical KV blocks and non-contiguous physical GPU memory pages.
                PagedAttention allows keys and values to be stored in non-contiguous physical blocks and fetched dynamically during attention computation without copying.
                This enables near-zero memory waste (<4%) and facilitates memory sharing across parallel sampling requests and prefix caching.
                Prerequisites include Virtual Memory, Paging and Segmentation, and Multi-Head Attention.
                Unlocks include High-Throughput LLM Serving, Prefix Caching, and Continuous Batching.
                """
            }
        ]
    },
    14: {
        "domain": "Foundational AI Papers: RAG, GNNs & Alignment",
        "subject": "Artificial Intelligence Research",
        "sources": [
            {
                "book_title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
                "author": "Patrick Lewis et al. (2020)",
                "chapter": "Dense Passage Retrieval & RAG-Sequence",
                "page": 3,
                "text": """
                Section 2 Methods.
                Retrieval-Augmented Generation (RAG) combines pre-trained parametric memory (a sequence-to-sequence transformer generator) with non-parametric memory (a dense vector index of Wikipedia passages retrieved using Dense Passage Retrieval).
                The retriever p_eta(z | x) encodes query x and document passages z using dense dual-encoder embeddings, retrieving top-k candidate passages via maximum inner product search.
                In RAG-Sequence, the model uses the same retrieved document to generate the entire target sequence y:
                p(y | x) = sum_{z in top-k} p_eta(z | x) * prod_{i=1}^N p_theta(y_i | x, z, y_{1:i-1}).
                In RAG-Token, the model marginalizes across different retrieved passages at each token generation step.
                RAG grounds generation in authoritative external documents, reducing hallucinations.
                Prerequisites include Dense Passage Retrieval, Sequence-to-Sequence Modeling, and Approximate Nearest Neighbor Search.
                Unlocks include Graph-Augmented Generation, Self-RAG, and Citation Grounding.
                """
            },
            {
                "book_title": "Direct Preference Optimization: Your Language Model is Secretly a Reward Model",
                "author": "Rafael Rafailov et al. (2023)",
                "chapter": "Direct Preference Optimization & Bradley-Terry Alignment",
                "page": 4,
                "text": """
                Section 4 Direct Preference Optimization.
                Reinforcement Learning from Human Feedback (RLHF) typically fits a reward model r_phi(x, y) to human preference pairs (y_w > y_l) under the Bradley-Terry preference model, then optimizes the policy pi_theta using PPO.
                Direct Preference Optimization (DPO) derives an exact closed-form analytical expression for optimal policy probabilities without explicitly training a separate reward model or sampling during training.
                The DPO loss directly optimizes the language model policy parameters theta using preference pairs:
                L_DPO(pi_theta; pi_ref) = - E_{(x, y_w, y_l)} [ log sigma(beta * log(pi_theta(y_w | x) / pi_ref(y_w | x)) - beta * log(pi_theta(y_l | x) / pi_ref(y_l | x))) ].
                Parameter beta controls the strength of the implicit KL-divergence penalty relative to reference policy pi_ref.
                Prerequisites include Bradley-Terry Preference Model, Cross-Entropy Loss, and Reinforcement Learning from Human Feedback.
                Unlocks include Direct Alignment, Preference Fine-Tuning, and Constitutional AI.
                """
            }
        ]
    }
}


def run_batch_ingest(
    batch_num: int,
    target_db_path: str | Path = "okf_graph.db",
    sync_to_hf: bool = True,
) -> dict[str, Any]:
    """Execute ingestion curriculum for a specific batch with Kahn DAG gate and 5-layer graph commit."""
    target_db = Path(target_db_path)
    if batch_num not in BATCH_CURRICULUM:
        raise ValueError(f"Unknown batch number {batch_num}. Valid batches: {list(BATCH_CURRICULUM.keys())}")

    batch_def = BATCH_CURRICULUM[batch_num]
    domain = batch_def["domain"]
    subject_name = batch_def["subject"]
    sources = batch_def["sources"]

    logger.info("================================================================================")
    logger.info("=== Starting Batch %d Ingestion: %s ===", batch_num, domain)
    logger.info("=== Subject: %s | Target DB: %s ===", subject_name, target_db)
    logger.info("================================================================================")

    extractor = LibQwenConceptExtractor(model_name="lib-qwen:latest")
    fusion = GraphFusionEngine(db_path=target_db)
    engine = KuzuGraphEngine(db_path=target_db, read_only=False)

    logger.info("Extractor model=%s host=%s", extractor.model_name, extractor.host)
    try:
        import subprocess
        gpu = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,power.draw,memory.used,temperature.gpu", "--format=csv,noheader"],
            text=True,
        ).strip()
        logger.info("GPU before extraction: %s", gpu)
    except Exception as gpu_err:
        logger.warning("nvidia-smi unavailable: %s", gpu_err)

    all_raw_concepts: list[dict[str, Any]] = []

    for idx, item in enumerate(sources, 1):
        book_title = item["book_title"]
        author = item.get("author", "Unknown Author")
        chapter = item.get("chapter", "Core Theory")
        page = int(item.get("page", 1))
        text = item["text"]

        logger.info("[%d/%d] Extracting: '%s' (p. %d) — %s", idx, len(sources), book_title, page, chapter)
        extracted = extractor.extract_from_text(
            text=text,
            doc_id=f"batch{batch_num}_{idx}",
            page_number=page,
            book_title=book_title,
            domain=domain,
        )
        logger.info("    -> Extracted %d concepts conforming to 8-key OKF contract", len(extracted))
        try:
            import subprocess
            gpu = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=utilization.gpu,power.draw,memory.used,temperature.gpu", "--format=csv,noheader"],
                text=True,
            ).strip()
            logger.info("    GPU after chunk %d: %s", idx, gpu)
        except Exception:
            pass
        for c in extracted:
            c["author"] = author
            c["chapter"] = chapter
            all_raw_concepts.append(c)

    # 1. Entity resolution and reciprocal cycle resolution
    logger.info("Executing entity resolution & second-pass cycle resolver...")
    resolved = extractor.second_pass_relation_resolver(all_raw_concepts)
    logger.info("Total resolved concepts: %d", len(resolved))

    # 2. Kahn DAG Cycle Gate
    logger.info("Running Kahn DAG Cycle Gate verification...")
    merge_report = fusion.merge_batch(
        extracted_concepts=resolved,
        kuzu_engine=engine,
        max_batch_nodes=150,
    )
    logger.info("Merge report: %s", merge_report)

    # 3. Interconnect 5 Layers: Subject -> Resource -> Document -> Chunk -> Concept
    logger.info("Interconnecting 5 graph layers (Subject -> Resource -> Document -> Chunk -> Concept)...")
    conn = engine.conn

    # Ensure Subject exists
    safe_subj = subject_name.replace("'", "''")
    conn.execute(f"MERGE (s:Subject {{subject_name: '{safe_subj}'}}) ON CREATE SET s.total_titles = 1")

    for idx, item in enumerate(sources, 1):
        b_title = item["book_title"]
        b_author = item.get("author", "Unknown Author")
        b_page = int(item.get("page", 1))
        b_chapter = item.get("chapter", "Core Section")
        b_text = item["text"][:350].replace("'", "''")

        res_id = f"res_{canonical_concept_id(b_title)}"
        doc_id = f"doc_{canonical_concept_id(b_title)}"
        chunk_id = f"{doc_id}_p{b_page}_{idx}"

        safe_btitle = b_title.replace("'", "''")
        safe_bauthor = b_author.replace("'", "''")
        safe_bchap = b_chapter.replace("'", "''")

        # 1. Subject -> Resource
        conn.execute(
            f"MERGE (r:Resource {{id: '{res_id}'}}) "
            f"ON CREATE SET r.title = '{safe_btitle}', r.author = '{safe_bauthor}', "
            f"r.copyright_year = 2024, r.publisher = 'Institutional Library', "
            f"r.biblionumber = '0', r.total_copies = 1, r.available_copies = 1, "
            f"r.barcodes = '[]', r.overdue_items = 0, r.is_periodical = false"
        )
        conn.execute(f"MATCH (s:Subject {{subject_name: '{safe_subj}'}}), (r:Resource {{id: '{res_id}'}}) MERGE (s)-[:CATEGORIZES]->(r)")

        # 2. Resource -> Document
        conn.execute(
            f"MERGE (d:Document {{id: '{doc_id}'}}) "
            f"ON CREATE SET d.title = '{safe_btitle}', d.doc_hash = '{doc_id}', "
            f"d.page_count = 500, d.edition = 'Global', d.pdf_url = 'remote_hf/{canonical_concept_id(b_title)}.pdf'"
        )
        conn.execute(f"MATCH (r:Resource {{id: '{res_id}'}}), (d:Document {{id: '{doc_id}'}}) MERGE (r)-[:PROVIDES_TEXT]->(d)")

        # 3. Document -> Chunk
        conn.execute(
            f"MERGE (chk:Chunk {{id: '{chunk_id}'}}) "
            f"ON CREATE SET chk.chunk_id = '{chunk_id}', chk.page_number = {b_page}, "
            f"chk.section_title = '{safe_bchap}', chk.text_passage = '{b_text}'"
        )
        conn.execute(f"MATCH (d:Document {{id: '{doc_id}'}}), (chk:Chunk {{id: '{chunk_id}'}}) MERGE (d)-[:HAS_CHUNK]->(chk)")

        # 4. Chunk -> Concept (MENTIONS)
        for c in resolved:
            if c.get("source_book") == b_title or c.get("chapter") == b_chapter:
                cid = c["id"]
                try:
                    conn.execute(
                        f"MATCH (chk:Chunk {{id: '{chunk_id}'}}), (c:Concept {{id: '{cid}'}}) "
                        f"MERGE (chk)-[:MENTIONS]->(c)"
                    )
                except Exception:
                    pass

    # Verify counts in DB
    res_concepts = conn.execute("MATCH (c:Concept) RETURN count(c);").get_as_df().iloc[0, 0]
    res_requires = conn.execute("MATCH ()-[r:REQUIRES]->() RETURN count(r);").get_as_df().iloc[0, 0]
    res_mentions = conn.execute("MATCH ()-[r:MENTIONS]->() RETURN count(r);").get_as_df().iloc[0, 0]
    res_provides = conn.execute("MATCH ()-[r:PROVIDES_TEXT]->() RETURN count(r);").get_as_df().iloc[0, 0]

    logger.info("KùzuDB Status: %d Concepts, %d REQUIRES edges, %d MENTIONS edges, %d PROVIDES_TEXT edges",
                res_concepts, res_requires, res_mentions, res_provides)

    engine.close()

    # Build summary
    summary_path = ROOT / "data" / "catalogs" / f"batch{batch_num}_ingestion_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_data = {
        "status": "success",
        "batch_num": batch_num,
        "domain": domain,
        "subject": subject_name,
        "sources_count": len(sources),
        "total_extracted": len(all_raw_concepts),
        "committed_nodes": merge_report.get("committed_nodes", 0),
        "committed_edges": merge_report.get("committed_edges", 0),
        "db_total_concepts": int(res_concepts),
        "db_total_requires": int(res_requires),
        "db_total_mentions": int(res_mentions),
        "db_total_provides_text": int(res_provides),
        "timestamp": time.time(),
        "sample_concepts": [
            {
                "name": c["name"],
                "concept_type": c.get("concept_type", "definition"),
                "difficulty": c.get("difficulty", "intermediate"),
                "summary": c.get("summary", ""),
                "prerequisites": [p["name"] if isinstance(p, dict) else str(p) for p in c.get("prerequisites", [])],
                "unlocks": [u["name"] if isinstance(u, dict) else str(u) for u in c.get("unlocks", [])],
            }
            for c in resolved[:8]
        ]
    }
    summary_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    logger.info("Batch %d summary saved to %s", batch_num, summary_path)

    # Sync summary to Hugging Face remote dataset
    if sync_to_hf:
        try:
            client = HFStorageClient()
            if client.is_available:
                client.upload_file(
                    local_path=summary_path,
                    remote_path=f"catalogs/batch{batch_num}_ingestion_summary.json",
                    commit_message=f"Ingestion curriculum: Batch {batch_num} ({domain})",
                )
                logger.info("Synchronized batch summary to Hugging Face dataset %s", client.repo_id)
        except Exception as hf_err:
            logger.warning("Could not sync summary to Hugging Face: %s", hf_err)

    return summary_data


def _subgraph_hammer(stop: threading.Event, results: list[dict[str, Any]]) -> None:
    """Hit live graph APIs and a read-only Kùzu count while the staging swap runs."""
    import urllib.request

    from archipelago.graph.engine import KuzuGraphEngine

    urls = [
        "http://127.0.0.1:5150/api/graph",
        "http://127.0.0.1:5052/api/graph/subgraph?target_id=transmission_control_protocol&max_nodes=8",
    ]
    prod = ROOT / "okf_graph.db"
    while not stop.is_set():
        t0 = time.time()
        hit = {"ok": False, "ms": 0}
        for url in urls:
            try:
                with urllib.request.urlopen(url, timeout=8) as resp:
                    hit = {"ok": True, "status": resp.status, "url": url, "ms": int((time.time() - t0) * 1000)}
                    break
            except Exception as exc:
                hit = {"ok": False, "error": str(exc), "url": url, "ms": int((time.time() - t0) * 1000)}
        if prod.exists():
            try:
                engine = KuzuGraphEngine(db_path=prod, read_only=True)
                n = int(engine.conn.execute("MATCH (c:Concept) RETURN count(c);").get_as_df().iloc[0, 0])
                engine.close()
                hit["kuzu_count"] = n
                hit["kuzu_ok"] = True
            except Exception as exc:
                hit["kuzu_ok"] = False
                hit["kuzu_error"] = str(exc)
        results.append(hit)
        stop.wait(0.4)


def main():
    parser = argparse.ArgumentParser(description="Master Multi-Domain Knowledge Graph Ingestion Runner")
    parser.add_argument("--batch", type=int, default=2, help="Batch number to ingest (1-14). Default: 2")
    parser.add_argument("--all", action="store_true", help="Ingest all batches 2 through 14 sequentially")
    parser.add_argument("--target-db", type=str, default="okf_graph.db", help="Target KùzuDB database path")
    parser.add_argument("--no-sync-hf", action="store_true", help="Disable Hugging Face dataset remote sync")
    parser.add_argument(
        "--direct-prod",
        action="store_true",
        help="Write directly to production (unsafe). Default is staging + embed + atomic swap.",
    )
    parser.add_argument("--max-delta", type=int, default=150, help="Abort publish if concept delta exceeds this")
    args = parser.parse_args()

    sync_hf = not args.no_sync_hf

    from archipelago.ingestion.librarian_worker import (
        PROD_DB_PATH,
        STAGING_DB_PATH,
        clone_production_to_staging,
        count_concepts,
        publish_staging,
    )

    if args.direct_prod:
        target_db = Path(args.target_db)
        logger.warning("DIRECT PRODUCTION WRITE enabled (%s) — skipping staging swap.", target_db)
        baseline = count_concepts(target_db) if target_db.exists() else 0
    else:
        baseline = count_concepts(PROD_DB_PATH) if PROD_DB_PATH.exists() else 0
        clone_production_to_staging(force=True)
        target_db = STAGING_DB_PATH
        logger.info("Staging pipeline: baseline=%d concepts, staging=%s", baseline, target_db)

    if args.all:
        logger.info("=== Starting Master Full Ingestion Curriculum: Batches 2 through 14 ===")
        results = {}
        for b_num in sorted(BATCH_CURRICULUM.keys()):
            results[b_num] = run_batch_ingest(b_num, target_db_path=target_db, sync_to_hf=sync_hf)
            time.sleep(1.0)
        last = results[max(results)]
        logger.info("All batches completed successfully!")
    else:
        last = run_batch_ingest(args.batch, target_db_path=target_db, sync_to_hf=sync_hf)

    if args.direct_prod:
        return

    staged_total = int(last.get("db_total_concepts") or count_concepts(target_db))
    delta = staged_total - baseline
    logger.info("Concept cardinality: baseline=%d staged=%d delta=%d (max %d)", baseline, staged_total, delta, args.max_delta)
    if delta > args.max_delta:
        raise SystemExit(
            f"Refusing to publish: concept delta {delta} exceeds --max-delta {args.max_delta}. Staging DB left in place."
        )

    hammer_stop = threading.Event()
    hammer_results: list[dict[str, Any]] = []
    hammer = threading.Thread(target=_subgraph_hammer, args=(hammer_stop, hammer_results), daemon=True)
    hammer.start()
    try:
        publish = publish_staging()
        logger.info("Publish result: %s", publish)
    finally:
        hammer_stop.set()
        hammer.join(timeout=5.0)

    ok_hits = sum(1 for r in hammer_results if r.get("ok"))
    logger.info("Concurrent /api/graph/subgraph during swap: %d/%d succeeded", ok_hits, len(hammer_results))
    for r in hammer_results:
        if not r.get("ok"):
            logger.warning("  subgraph miss: %s", r)


if __name__ == "__main__":
    main()
