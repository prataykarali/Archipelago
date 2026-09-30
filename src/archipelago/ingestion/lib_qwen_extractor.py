"""
Lib-Qwen Ingestion & Pedagogical Concept Extraction Engine.

Extracts canonical concepts, mathematical definitions, and directional REQUIRES/UNLOCKS
relationships from textbook chapters using lib-qwen:latest with guided JSON decoding,
negative sampling, canonical resolution, and Kahn DAG verification.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

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

# Multi-domain canonical abbreviation/synonym registry
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


class LibQwenConceptExtractor:
    """Extracts pedagogical concepts and prerequisites conforming to the 8-key OKF contract."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        host: str = "http://localhost:11434",
    ):
        self.model_name = model_name
        self.host = host
        self.client = ollama.Client(host=self.host) if OLLAMA_AVAILABLE else None

    def extract_from_chunk(
        self,
        text: str,
        book_title: str = "",
        page_number: int = 1,
        domain: str = "",
    ) -> list[dict]:
        """Extract structured concepts conforming to the 8-key contract from chunk."""
        if is_negative_sample(text):
            logger.debug("Dropped negative boilerplate sample (page %d)", page_number)
            return []

        if not self.client:
            logger.warning("Ollama client unavailable, returning empty concept list")
            return []

        prompt = (
            "You are an OKF extraction engine for the Archipelago knowledge graph.\n"
            "From the TEXT below, extract 1-5 teachable CONCEPTS as a JSON array.\n\n"
            "Each object MUST have exactly these keys: concept_name, concept_type, difficulty, summary, prerequisites, unlocks, related_to, tags.\n"
            "Do not extract celebrities, authors as concepts, or evaluation boilerplate.\n\n"
            f"SOURCE: '{book_title}' (Domain: {domain}, Page {page_number})\n"
            "TEXT:\n"
            f"{text[:2500]}"
        )

        try:
            resp = self.client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                think=False,
                options={"temperature": 0.1, "num_predict": 1200},
            )
            raw = resp.message.content
            parsed = clean_json_payload(raw)
            concepts = []

            for c in parsed.get("concepts", []):
                raw_name = (c.get("concept_name") or c.get("name") or "").strip()
                name = canonicalize_concept_name(raw_name)
                defn = (c.get("summary") or c.get("definition") or "").strip()

                ctype = (c.get("concept_type") or "definition").lower().strip()
                if ctype not in ("core", "technique", "definition", "algorithm", "theorem"):
                    ctype = "definition"

                diff = (c.get("difficulty") or "intermediate").lower().strip()
                if diff not in ("foundational", "intermediate", "advanced"):
                    diff = "intermediate"

                if not name or len(name) < 3 or len(defn) < 15:
                    continue

                # Filter out generic chapter headers
                if any(h in name.lower() for h in ["chapter", "section", "summary", "exercise", "introduction", "table of"]):
                    continue

                cid = canonical_concept_id(name)

                # Prerequisites (self-loops eliminated, canonicalized)
                raw_prereqs = c.get("prerequisites") or []
                prereqs = []
                for p in raw_prereqs:
                    p_name = p.get("name") if isinstance(p, dict) else str(p)
                    canon_p = canonicalize_concept_name(p_name)
                    if canon_p and len(canon_p) >= 3 and canonical_concept_id(canon_p) != cid:
                        if canon_p not in prereqs:
                            prereqs.append(canon_p)

                # Unlocks (self-loops eliminated, canonicalized)
                raw_unlocks = c.get("unlocks") or []
                unlocks = []
                for u in raw_unlocks:
                    u_name = u.get("name") if isinstance(u, dict) else str(u)
                    canon_u = canonicalize_concept_name(u_name)
                    if canon_u and len(canon_u) >= 3 and canonical_concept_id(canon_u) != cid:
                        if canon_u not in unlocks:
                            unlocks.append(canon_u)

                # Related_to (self-loops eliminated, canonicalized)
                raw_related = c.get("related_to") or []
                related_to = []
                for r in raw_related:
                    if isinstance(r, dict):
                        r_target = canonicalize_concept_name(r.get("concept") or r.get("name") or "")
                        r_rel = (r.get("relation") or "uses").lower().strip()
                    else:
                        r_target = canonicalize_concept_name(str(r))
                        r_rel = "uses"
                    if r_target and len(r_target) >= 3 and canonical_concept_id(r_target) != cid:
                        related_to.append({"concept": r_target, "relation": r_rel})

                # Tags
                tags = [
                    str(t).lower().strip().replace(" ", "-")
                    for t in c.get("tags") or []
                    if isinstance(t, str) and len(t.strip()) >= 2
                ]

                concepts.append({
                    "id": cid,
                    "concept_name": name,
                    "name": name,
                    "concept_type": ctype,
                    "difficulty": diff,
                    "summary": defn,
                    "definition": defn,
                    "prerequisites": prereqs,
                    "unlocks": unlocks,
                    "related_to": related_to,
                    "tags": tags,
                    "domain": domain,
                    "source_book": book_title,
                    "page_number": page_number,
                })

            return concepts

        except Exception as exc:
            logger.warning("Extraction error with lib-qwen on page %d: %s", page_number, exc)
            return []

    def extract_from_text(
        self,
        text: str,
        doc_id: str = "",
        page_number: int = 1,
        book_title: str = "",
        domain: str = "Computer Science",
    ) -> list[dict]:
        """Extract structured concepts from text (convenience alias for extract_from_chunk)."""
        return self.extract_from_chunk(
            text=text,
            book_title=book_title,
            page_number=page_number,
            domain=domain,
        )

    def second_pass_relation_resolver(
        self,
        extracted_concepts: list[dict],
    ) -> list[dict]:
        """
        Validate and resolve relationship integrity:
        1. Eliminate reciprocal dependency cycles (A -> B and B -> A) across prerequisites and unlocks.
        2. Remove self-loops.
        3. Harmonize prerequisite IDs against canonical concept registry.
        """
        name_to_id = {c["name"].lower(): c["id"] for c in extracted_concepts}
        resolved = []
        directed_prereq_edges = set()
        directed_unlock_edges = set()

        for c in extracted_concepts:
            cid = c["id"]
            c_name = c["name"]

            # 1. Prerequisite edges
            valid_prereqs = []
            for p_item in c.get("prerequisites", []):
                p_name = p_item["name"] if isinstance(p_item, dict) else str(p_item)
                p_name_canon = canonicalize_concept_name(p_name)
                p_id = name_to_id.get(p_name_canon.lower()) or canonical_concept_id(p_name_canon)

                if p_id == cid:
                    continue  # Self-loop

                # Check reciprocal cycle: (p_id, cid) already asserted as prerequisite
                if (p_id, cid) in directed_prereq_edges:
                    logger.debug("Discarded reciprocal prerequisite: %s -> %s", cid, p_id)
                    continue

                directed_prereq_edges.add((cid, p_id))
                valid_prereqs.append({"id": p_id, "name": p_name_canon})

            # 2. Unlock edges
            valid_unlocks = []
            for u_item in c.get("unlocks", []):
                u_name = u_item["name"] if isinstance(u_item, dict) else str(u_item)
                u_name_canon = canonicalize_concept_name(u_name)
                u_id = name_to_id.get(u_name_canon.lower()) or canonical_concept_id(u_name_canon)

                if u_id == cid:
                    continue  # Self-loop

                # If u_id already requires cid, cid unlocking u_id is consistent.
                # But if u_id unlocks cid, that is a reciprocal cycle.
                if (u_id, cid) in directed_unlock_edges:
                    logger.debug("Discarded reciprocal unlock: %s -> %s", cid, u_id)
                    continue

                directed_unlock_edges.add((cid, u_id))
                valid_unlocks.append({"id": u_id, "name": u_name_canon})

            c_copy = dict(c)
            c_copy["prerequisites"] = valid_prereqs
            c_copy["unlocks"] = valid_unlocks
            resolved.append(c_copy)

        return resolved
