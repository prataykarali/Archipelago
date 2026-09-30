"""
Build high-fidelity v4.4 training dataset from Pearson Academic Bookshelf.
Generates structured concept explanations, prerequisite reasoning chains, and diagnostic MCQs.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from archipelago.ingestion.pearson_connector import PearsonCatalog
from archipelago.dataset.v44_generator import V44DatasetGenerator

PEARSON_SEMINAL_CONCEPTS = [
    # AI & ML
    {"title": "Artificial Intelligence: A Modern Approach, 4/e", "name": "A* Search Algorithm", "prereqs": ["Heuristic Function", "Priority Queue"], "diff": "intermediate", "page": 102, "defn": "A* search is an informed graph traversal algorithm that finds the shortest path by evaluating nodes via f(n) = g(n) + h(n)."},
    {"title": "Artificial Intelligence: A Modern Approach, 4/e", "name": "Markov Decision Process", "prereqs": ["Probability Distribution", "Markov Property"], "diff": "advanced", "page": 645, "defn": "A Markov Decision Process (MDP) models sequential decision making under uncertainty using states, actions, transition probabilities, and reward functions."},
    {"title": "Speech and Language Processing: An Introduction to Natural Language Processing, Computational Linguistics and Speech Recognition 2/e", "name": "N-gram Language Model", "prereqs": ["Conditional Probability", "Markov Assumption"], "diff": "foundational", "page": 83, "defn": "An n-gram model predicts the probability of the next word in a sequence given the previous n-1 words."},
    {"title": "Neural Networks and Learning Machines", "name": "Multilayer Perceptron", "prereqs": ["Linear Classifier", "Activation Function"], "diff": "intermediate", "page": 156, "defn": "A Multilayer Perceptron (MLP) is a feedforward neural network comprising input, hidden, and output layers trained via error backpropagation."},
    {"title": "Computer Vision", "name": "Convolutional Feature Map", "prereqs": ["2D Discrete Convolution", "Spatial Invariance"], "diff": "intermediate", "page": 210, "defn": "A feature map is the spatial activation output produced by sliding parameterized convolutional filter kernels across an input image tensor."},
    
    # Networks & Security
    {"title": "Computer Networks, 6/e", "name": "OSI Reference Model", "prereqs": ["Protocol Layering", "Packet Encapsulation"], "diff": "foundational", "page": 45, "defn": "The OSI model is a conceptual 7-layer architectural framework defining standard communication protocols across network hosts."},
    {"title": "Computer Networks, 6/e", "name": "TCP Congestion Control", "prereqs": ["Sliding Window Protocol", "Round Trip Time"], "diff": "intermediate", "page": 580, "defn": "TCP congestion control dynamically regulates network injection rate using slow start, congestion avoidance, fast retransmit, and fast recovery algorithms."},
    {"title": "Cryptography and Network Security: Principles and Practice, 8/e", "name": "Diffie-Hellman Key Exchange", "prereqs": ["Modular Arithmetic", "Discrete Logarithm Problem"], "diff": "advanced", "page": 298, "defn": "Diffie-Hellman allows two parties to establish a shared cryptographic secret over an insecure channel without prior secret exchange."},
    
    # Compilers & Algorithms
    {"title": "Compilers Principles, Techniques, and Tools, 2e", "name": "LR Syntax Parsing", "prereqs": ["Context-Free Grammar", "Deterministic Finite Automata"], "diff": "advanced", "page": 242, "defn": "LR parsing is a bottom-up shift-reduce syntax parsing method that constructs a rightmost derivation in reverse for deterministic context-free grammars."},
    {"title": "Compilers Principles, Techniques, and Tools, 2e", "name": "Abstract Syntax Tree", "prereqs": ["Parse Tree", "Grammar Production"], "diff": "intermediate", "page": 91, "defn": "An Abstract Syntax Tree (AST) is a condensed hierarchical tree representation of source code syntax where operators are interior nodes and operands are children."},
    {"title": "Introduction to the Design and Analysis of Algorithms", "name": "Divide and Conquer", "prereqs": ["Recurrence Relation", "Mathematical Induction"], "diff": "foundational", "page": 124, "defn": "Divide-and-conquer partitions a problem into smaller independent subproblems of identical type, solves them recursively, and combines their solutions."},
    {"title": "Design and Analysis of Algorithms 2/e", "name": "Dynamic Programming", "prereqs": ["Optimal Substructure", "Overlapping Subproblems"], "diff": "intermediate", "page": 267, "defn": "Dynamic programming solves combinatorial optimization problems by storing solutions to overlapping subproblems to prevent redundant computation."},

    # Operating Systems & Architecture
    {"title": "Operating Systems: Internals and Design Principles, Global Edition", "name": "Virtual Memory Paging", "prereqs": ["Address Translation", "Page Table"], "diff": "intermediate", "page": 312, "defn": "Paging is a memory management scheme that stores and retrieves data from secondary storage in fixed-size blocks called pages."},
    {"title": "Operating Systems: Internals and Design Principles, Global Edition", "name": "Mutual Exclusion Semaphore", "prereqs": ["Race Condition", "Critical Section"], "diff": "foundational", "page": 204, "defn": "A semaphore is a synchronization variable accessed exclusively through atomic wait (P) and signal (V) operations to enforce mutual exclusion."},
    {"title": "Computer System Architecture, Revised 3/e", "name": "Instruction Pipeline", "prereqs": ["Clock Cycle", "Instruction Register"], "diff": "intermediate", "page": 320, "defn": "Pipelining is an implementation technique whereby multiple hardware instructions are overlapped in execution across dedicated execution stages."},

    # Signal Processing & Mathematics
    {"title": "Digital Signal Processing, 4e", "name": "Discrete Fourier Transform", "prereqs": ["Continuous Fourier Transform", "Discrete-Time Signal"], "diff": "intermediate", "page": 394, "defn": "The Discrete Fourier Transform (DFT) converts a finite sequence of equally-spaced samples of a function into an equivalent-length sequence of frequency components."},
    {"title": "Digital Signal Processing, 4e", "name": "Nyquist-Shannon Sampling Theorem", "prereqs": ["Signal Bandwidth", "Aliasing"], "diff": "foundational", "page": 28, "defn": "The sampling theorem states that a bandlimited signal can be perfectly reconstructed if sampled at a rate greater than twice its highest frequency."},
    {"title": "Digital Image Processing, 4e", "name": "Spatial Domain Filtering", "prereqs": ["2D Matrix Representation", "Convolution Kernel"], "diff": "intermediate", "page": 145, "defn": "Spatial domain filtering applies mathematical neighborhood operations directly on the pixel values of an image matrix."},
    {"title": "A First Course in Probability, 9e", "name": "Bayes' Theorem", "prereqs": ["Conditional Probability", "Law of Total Probability"], "diff": "foundational", "page": 65, "defn": "Bayes' theorem calculates the posterior probability of an event based on prior knowledge of conditions that might be related to the event."}
]


def main():
    cat = PearsonCatalog.load_from_file("data/catalogs/pearson_bookshelf.json")
    generator = V44DatasetGenerator("data/catalogs/pearson_bookshelf.json")
    
    concepts = []
    for item in PEARSON_SEMINAL_CONCEPTS:
        book = cat.find_by_title(item["title"])
        domain = book.domain if book else "Computer Science"
        cid = item["name"].lower().replace(" ", "_").replace("*", "_star")
        concepts.append({
            "id": cid,
            "name": item["name"],
            "domain": domain,
            "definition": item["defn"],
            "difficulty": item["diff"],
            "source_book": item["title"],
            "page_number": item["page"],
            "prerequisites": [{"id": p.lower().replace(" ", "_"), "name": p} for p in item["prereqs"]],
        })

    out_file = Path("data/datasets/pearson_v44_pairs.jsonl")
    res = generator.export_dataset(concepts, output_path=out_file, sync_to_hf=False)
    print(f"Generated {res['total_examples']} Pearson v4.4 training pairs in {out_file}")

if __name__ == "__main__":
    main()
