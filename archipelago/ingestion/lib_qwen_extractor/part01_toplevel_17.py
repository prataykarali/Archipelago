"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import json
import logging
import re
from . import _deps as _rt  # noqa: F401


try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


logger = logging.getLogger("archipelago.ingestion.lib_qwen")


DEFAULT_MODEL = "lib-qwen:latest"


MAX_NEW_CONCEPTS_PER_BATCH = 150


NEGATIVE_SAMPLE_PATTERNS = [
    r"\bbibliography\b",
    r"\breferences\b",
    r"\btable of contents\b",
    r"\bindex\b",
    r"\bpreface\b",
    r"\babout the authors?\b",
    r"\backnowledgements?\b",
    r"\ball rights reserved\b",
    r"\bprinted in\b",
    r"\bpublisher\b",
    r"\banswers to (odd|even|selected) exercises\b",
]


CANONICAL_ALIAS_MAP: dict[str, str] = {
    # AI / ML & Linear Algebra
    "svd": "Singular Value Decomposition",
    "backprop": "Error Backpropagation Algorithm",
    "backpropagation": "Error Backpropagation Algorithm",
    "mdp": "Markov Decision Process",
    "pca": "Principal Component Analysis",
    "lora": "Low-Rank Adaptation",
    "qlora": "Quantized Low-Rank Adaptation",
    "mle": "Maximum Likelihood Estimation",
    "svm": "Support Vector Machine",
    "support vector machines": "Support Vector Machine",
    "mlp": "Multilayer Perceptron",
    "cnn": "Convolutional Neural Network",
    "rnn": "Recurrent Neural Network",
    "lstm": "Long Short-Term Memory",
    "bert": "BERT",
    "gpt": "Generative Pre-Trained Transformer",
    "vllm": "PagedAttention vLLM",
    "pagedattention": "PagedAttention Memory Management",
    "rag": "Retrieval-Augmented Generation",
    "graphrag": "Graph-Augmented Generation",
    "gcn": "Graph Convolutional Network",
    "gat": "Graph Attention Network",
    "dpo": "Direct Preference Optimization",
    "rlhf": "Reinforcement Learning from Human Feedback",
    "sgd": "Stochastic Gradient Descent",
    "adam": "Adam Optimizer",
    "cot": "Chain of Thought Prompting",
    # Computer Networks & Security
    "tcp": "Transmission Control Protocol",
    "ip": "Internet Protocol",
    "tcp/ip": "Transmission Control Protocol/Internet Protocol",
    "osi": "OSI 7-Layer Reference Model",
    "osi model": "OSI 7-Layer Reference Model",
    "rsa": "RSA Public-Key Cryptosystem",
    "aes": "Advanced Encryption Standard",
    "des": "Data Encryption Standard",
    "dns": "Domain Name System",
    "dhcp": "Dynamic Host Configuration Protocol",
    "http": "Hypertext Transfer Protocol",
    "https": "Hypertext Transfer Protocol Secure",
    "crc": "Cyclic Redundancy Check",
    "nat": "Network Address Translation",
    "bgp": "Border Gateway Protocol",
    "ospf": "Open Shortest Path First",
    # Operating Systems & Architecture
    "vm": "Virtual Memory",
    "tlb": "Translation Lookaside Buffer",
    "isa": "Instruction Set Architecture",
    "risc": "Reduced Instruction Set Computer",
    "cisc": "Complex Instruction Set Computer",
    "dma": "Direct Memory Access",
    "mmu": "Memory Management Unit",
    "pcb": "Process Control Block",
    "ipc": "Inter-Process Communication",
    "lru": "Least Recently Used Page Replacement",
    # Compilers & Algorithms
    "ast": "Abstract Syntax Tree",
    "cfg": "Control Flow Graph",
    "dfa": "Deterministic Finite Automaton",
    "nfa": "Nondeterministic Finite Automaton",
    "dp": "Dynamic Programming",
    "dag": "Directed Acyclic Graph",
    # Databases & Web
    "dbms": "Database Management System",
    "rdbms": "Relational Database Management System",
    "acid": "ACID Transaction Properties",
    "sql": "Structured Query Language",
    "b-tree": "B-Tree Index",
    "b+ tree": "B+ Tree Index",
    "rest": "RESTful Architecture",
    "mvc": "Model View Controller",
    # Electronics, Embedded & DSP
    "op-amp": "Operational Amplifier",
    "opamp": "Operational Amplifier",
    "bjt": "Bipolar Junction Transistor",
    "mosfet": "Metal-Oxide-Semiconductor Field-Effect Transistor",
    "pwm": "Pulse Width Modulation",
    "isr": "Interrupt Service Routine",
    "mcu": "Microcontroller Unit",
    "dsp": "Digital Signal Processing",
    "dft": "Discrete Fourier Transform",
    "fft": "Fast Fourier Transform",
    "fir": "Finite Impulse Response Filter",
    "iir": "Infinite Impulse Response Filter",
    "dip": "Digital Image Processing",
    # Biotech & Chemistry
    "dna": "Deoxyribonucleic Acid",
    "rna": "Ribonucleic Acid",
    "atp": "Adenosine Triphosphate",
    "pcr": "Polymerase Chain Reaction",
    "tca cycle": "Citric Acid Cycle",
    "krebs cycle": "Citric Acid Cycle",
    "nmr": "Nuclear Magnetic Resonance Spectroscopy",
    "sn1": "Unimolecular Nucleophilic Substitution",
    "sn2": "Bimolecular Nucleophilic Substitution",
}


def is_negative_sample(text: str) -> bool:
    """Detect boilerplate non-pedagogical sections (bibliographies, prefaces, indexes)."""
    if not text or len(text.strip()) < 100:
        return True
    sample = text[:1000].lower()
    for pat in NEGATIVE_SAMPLE_PATTERNS:
        if re.search(pat, sample):
            first_lines = "\n".join(sample.splitlines()[:5])
            if re.search(pat, first_lines):
                return True
    return False


def canonicalize_concept_name(name: str) -> str:
    """Normalize and resolve acronyms/synonyms to canonical title-case concept names."""
    if not name:
        return ""
    clean = name.strip()
    clean = clean.replace("_", " ")
    clean = re.sub(r"\s+", " ", clean).strip().rstrip(".")
    # Remove short parenthetical abbreviations like "Support Vector Machine (SVM)"
    clean = re.sub(r"\s*\([^)]{1,10}\)\s*$", "", clean)

    low = clean.lower()
    if low in CANONICAL_ALIAS_MAP:
        return CANONICAL_ALIAS_MAP[low]

    # Enforce title-cased words under 5 words
    words = clean.split()
    if len(words) > 5:
        clean = " ".join(words[:5])

    # Keep acronyms intact
    if clean == clean.lower() or (clean == clean.upper() and len(clean) > 5):
        clean = clean.title()

    return clean


def canonical_concept_id(name: str) -> str:
    """Generate deterministic snake_case concept identifier from canonical name."""
    canon = canonicalize_concept_name(name)
    clean = re.sub(r"[^\w\s-]", " ", canon).strip().lower()
    return re.sub(r"[-\s]+", "_", clean)


def clean_json_payload(raw_content: str) -> dict:
    """Strip markdown code fences and normalize top-level JSON objects/arrays."""
    if not raw_content:
        return {"concepts": []}

    cleaned = raw_content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
            except Exception:
                return {"concepts": []}
        else:
            return {"concepts": []}

    if isinstance(data, list):
        return {"concepts": data}
    if isinstance(data, dict):
        if "concepts" in data and isinstance(data["concepts"], list):
            return data
        if "concept_name" in data or "name" in data:
            return {"concepts": [data]}
        return {"concepts": []}
    return {"concepts": []}
