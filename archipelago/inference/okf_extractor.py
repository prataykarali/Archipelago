"""OKF Extraction Engine & Modular Ingestion Pipeline - 40 Pearson Textbooks, Papers & Koha Catalogs.

Parses high-density textbook sections (Chapter Intros, Summaries, Definitions),
enforces lineage contracts, performs canonical entity resolution, applies Kahn's DAG Cycle Gate,
and binds exact reader URLs.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("archipelago.okf_extractor")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
PEARSON_CATALOG_PATH = DATA_DIR / "catalogs" / "pearson_bookshelf.json"

# Canonical Entity Resolution Alias Dictionary
CANONICAL_ALIASES: Dict[str, str] = {
    "CRC": "Cyclic Redundancy Check",
    "3NF": "Third Normal Form",
    "2NF": "Second Normal Form",
    "1NF": "First Normal Form",
    "BCNF": "Boyce-Codd Normal Form",
    "GAN": "Generative Adversarial Network",
    "LSTM": "Long Short-Term Memory",
    "BERT": "Bidirectional Encoder Representations from Transformers",
    "RAG": "Retrieval-Augmented Generation",
    "LoRA": "Low-Rank Adaptation",
    "QLoRA": "Quantized Low-Rank Adaptation",
    "DSP": "Digital Signal Processing",
    "FFT": "Fast Fourier Transform",
    "DFT": "Discrete Fourier Transform",
    "CNN": "Convolutional Neural Network",
    "RNN": "Recurrent Neural Network",
    "ALU": "Arithmetic Logic Unit",
    "CPU": "Central Processing Unit",
    "OS": "Operating System",
    "TCP": "Transmission Control Protocol",
    "IP": "Internet Protocol",
    "UDP": "User Datagram Protocol",
}


def resolve_canonical_concept_name(raw_name: str) -> str:
    """Step 2: Canonical Entity Resolution.
    
    Maps alias variants to canonical concept names.
    """
    cleaned = raw_name.strip()
    return CANONICAL_ALIASES.get(cleaned, CANONICAL_ALIASES.get(cleaned.upper(), cleaned))


def check_dag_cycle(concepts: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Step 3: Kahn's Algorithm Topological Cycle Gate.
    
    Filters out any cyclic prerequisite edges (A -> B -> A) to guarantee a Directed Acyclic Graph (DAG).
    """
    node_ids = {c["concept_name"] for c in concepts if "concept_name" in c}
    in_degree = {n: 0 for n in node_ids}
    adj = {n: [] for n in node_ids}
    valid_edges = []

    for edge in edges:
        u = resolve_canonical_concept_name(edge.get("source_concept", ""))
        v = resolve_canonical_concept_name(edge.get("target_concept", ""))
        if u in node_ids and v in node_ids and u != v:
            adj[u].append(v)
            in_degree[v] = in_degree.get(v, 0) + 1
            valid_edges.append({**edge, "source_concept": u, "target_concept": v})

    queue = [n for n, deg in in_degree.items() if deg == 0]
    visited = set()

    while queue:
        curr = queue.pop(0)
        visited.add(curr)
        for neighbor in adj[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # Return edges where both source and target are part of topologically valid nodes
    return [e for e in valid_edges if e["source_concept"] in visited and e["target_concept"] in visited]


def generate_lineage_chunk(
    doc_id: str,
    book_title: str,
    edition: str,
    section_title: str,
    page_number: int,
    text_passage: str,
    subscription_id: str | None = None,
    book_id: str | None = None,
) -> Dict[str, Any]:
    """Step 4 & Lineage Contract: Build standardized provenance chunk object."""
    clean_doc_id = re.sub(r"[^a-zA-Z0-9_]", "_", doc_id.lower())
    chunk_id = f"chunk_{clean_doc_id}_p{page_number}"

    if subscription_id and (book_id or doc_id):
        b_target = book_id or doc_id
        reader_url = f"https://ebooks.elibrary.in.pearson.com/wr/pdfviewer.html?subscriptionId={subscription_id}#book/{b_target}/page/{page_number}"
    else:
        reader_url = f"https://huggingface.co/datasets/Prataykarali/Library_books/blob/main/textbooks/{doc_id}.pdf#page={page_number}"

    return {
        "chunk_id": chunk_id,
        "document_id": doc_id,
        "book_title": book_title,
        "edition": edition,
        "section_title": section_title,
        "page_number": page_number,
        "text_passage": text_passage,
        "reader_url": reader_url,
    }


def load_pearson_40_catalog() -> List[Dict[str, Any]]:
    """Load the complete 40 Pearson titles with subscription IDs & reader URLs."""
    if not PEARSON_CATALOG_PATH.is_file():
        return []

    try:
        with open(PEARSON_CATALOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        books = data.get("books", []) if isinstance(data, dict) else (data if isinstance(data, list) else [])
        catalog = []
        for b in books:
            if not isinstance(b, dict):
                continue
            sub_id = b.get("subscription_id", "10b6426b-3f9a-46ac-9758-678f65277e8b")
            book_id = b.get("id", "13ddfc73-f7ee-4ab8-8cf3-e5c4a4bcfdbf")

            reader_url = b.get("reader_base_url") or f"https://ebooks.elibrary.in.pearson.com/wr/pdfviewer.html?subscriptionId={sub_id}#book/{book_id}/page/1"

            catalog.append({
                "doc_id": book_id,
                "title": b.get("title", ""),
                "authors": b.get("author", ""),
                "isbn": b.get("isbn", ""),
                "domain": b.get("domain", "Computer Science"),
                "subscription_id": sub_id,
                "reader_url": reader_url,
                "is_pearson": True,
            })
        return catalog
    except Exception as e:
        logger.error("Error loading Pearson catalog: %s", e)
        return []


def process_okf_extraction_step(
    raw_concepts: List[Dict[str, Any]],
    raw_edges: List[Dict[str, Any]],
    doc_info: Dict[str, Any],
) -> Dict[str, Any]:
    """Four-Step OKF Extraction Engine."""
    # Step 1 & 2: Parse, validate 8-key schema, resolve canonical names
    resolved_concepts = []
    for c in raw_concepts:
        c_name = resolve_canonical_concept_name(c.get("concept_name", ""))
        if not c_name:
            continue
        resolved_concepts.append({
            "concept_name": c_name,
            "concept_type": c.get("concept_type", "algorithm"),
            "difficulty": c.get("difficulty", "intermediate"),
            "summary": c.get("summary", ""),
            "prerequisites": [resolve_canonical_concept_name(p) for p in c.get("prerequisites", [])],
            "unlocks": [resolve_canonical_concept_name(u) for u in c.get("unlocks", [])],
            "related_to": c.get("related_to", []),
            "tags": c.get("tags", []),
        })

    # Step 3: Kahn's Algorithm DAG Cycle Gate
    valid_edges = check_dag_cycle(resolved_concepts, raw_edges)

    # Step 4: Reader Link Binding
    sub_id = doc_info.get("subscription_id")
    b_id = doc_info.get("doc_id") or doc_info.get("id")
    page_num = doc_info.get("page_number", 1)

    chunk = generate_lineage_chunk(
        doc_id=doc_info.get("doc_id", "doc"),
        book_title=doc_info.get("title", "Textbook"),
        edition=doc_info.get("edition", "1st Edition"),
        section_title=doc_info.get("section_title", "Introduction"),
        page_number=page_num,
        text_passage=doc_info.get("text_passage", ""),
        subscription_id=sub_id,
        book_id=b_id,
    )

    return {
        "concepts": resolved_concepts,
        "edges": valid_edges,
        "lineage_chunk": chunk,
        "reader_url": chunk["reader_url"],
    }


if __name__ == "__main__":
    books = load_pearson_40_catalog()
    print(f"Loaded {len(books)} Pearson titles.")
    if books:
        sample = generate_lineage_chunk(
            doc_id=books[0]["doc_id"],
            book_title=books[0]["title"],
            edition="6th Edition",
            section_title="3.2 Error Detection and Correction",
            page_number=192,
            text_passage="Cyclic Redundancy Checks (CRCs)...",
            subscription_id=books[0]["subscription_id"],
            book_id=books[0]["doc_id"],
        )
        print("Sample lineage chunk:", json.dumps(sample, indent=2))
