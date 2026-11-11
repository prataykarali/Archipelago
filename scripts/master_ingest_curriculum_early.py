"""Master ingestion curriculum, batches 2 through 10."""

from __future__ import annotations

from typing import Any

EARLY_BATCHES: dict[int, dict[str, Any]] = {
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
                """,
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
                """,
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
                """,
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
                """,
            },
        ],
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
                """,
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
                """,
            },
        ],
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
                """,
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
                """,
            },
        ],
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
                """,
            }
        ],
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
                """,
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
                """,
            },
        ],
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
                """,
            }
        ],
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
                """,
            }
        ],
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
                """,
            }
        ],
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
                """,
            }
        ],
    },
}
