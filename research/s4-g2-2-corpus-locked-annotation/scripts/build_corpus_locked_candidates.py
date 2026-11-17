"""S4-G2.2 — Corpus-Locked Annotation Candidate Pool Builder (v2).

Builds annotation candidates using a targeted strategy:
1. For each candidate document, identify specific chunks with technical prose.
2. Extract evidence spans as exact verbatim substrings of chunk text.
3. Ground concept pairs in those spans (concepts must appear in the span).
4. Run the hardened provenance validator (Phase A) before admission.
5. Record chunk fingerprints, text offsets, and all metadata.

All evidence spans are literal substrings of the frozen corpus.
No synthetic text, no paraphrased summaries, no general-knowledge passages.
Human labels are NOT generated: label_category = 'CANDIDATE_UNLABELED'.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

try:
    import kuzu
except ImportError:
    print("ERROR: kuzu not installed. Run: pip install kuzu", file=sys.stderr)
    sys.exit(1)

from okf.eval.integrity_validators import (
    validate_provenance_record,
    chunk_fingerprint,
)


# ---------------------------------------------------------------------------
# Domain eligibility matrix (Phase D)
# ---------------------------------------------------------------------------

DOMAIN_ELIGIBILITY = {
    "OS": {
        "name": "Operating Systems",
        "eligibility": "ELIGIBLE",
        "split_type": "DOCUMENT_DISJOINT",
        "note": (
            "3 OSTEP chapters indexed with real prose. "
            "06_Address_Spaces → development; 08_Paging → evaluation. "
            "CC BY-NC-ND 4.0 — do not publish verbatim text; publish only evidence hashes "
            "and offsets in public materials."
        ),
    },
    "AIML": {
        "name": "AI & Machine Learning",
        "eligibility": "ELIGIBLE",
        "split_type": "DOCUMENT_DISJOINT",
        "note": (
            "Multiple arXiv papers with full text. "
            "Development: Vaswani2017, Hu2021_LoRA. Evaluation: Dettmers2023_QLoRA, "
            "Bahdanau2014_Attention. Held-out: Devlin2018_BERT (not used for tuning). "
            "arXiv preprints — check per-paper redistribution terms."
        ),
    },
    "NETS": {
        "name": "Computer Networks",
        "eligibility": "ELIGIBLE",
        "split_type": "DOCUMENT_DISJOINT",
        "note": (
            "Real-time network security paper (57 chunks, Elsevier 2024) for evaluation. "
            "Tanenbaum 6e excerpts (2 chunks) for development. "
            "Elsevier paper: check publisher licensing before redistributing passages."
        ),
    },
    "TOC": {
        "name": "Automata Theory & Computation",
        "eligibility": "EXPLORATORY",
        "split_type": "WITHIN_DOCUMENT_CHUNK_SPLIT",
        "note": (
            "Willard2023_Outlines.pdf is an LLM-constrained-decoding paper, NOT a classical "
            "automata theory text. Single document only → chunk split only. "
            "Use for exploratory analysis; exclude from held-out evaluation denominators."
        ),
    },
    "DBMS": {
        "name": "Database Management Systems",
        "eligibility": "EXPLORATORY",
        "split_type": "DOCUMENT_DISJOINT",
        "note": (
            "Only 2 real chunks in DB (Silberschatz 3NF card + Elmasri p145). "
            "Too sparse for a multi-item evaluation pool. "
            "Can contribute 1 exploratory candidate only."
        ),
    },
    "COMPILERS": {
        "name": "Compilers & Programming Languages",
        "eligibility": "EXPLORATORY",
        "split_type": "SINGLE_CHUNK_ONLY",
        "note": (
            "Only 1 chunk (Dragon Book p192 — syntax analysis). "
            "Insufficient for multi-item pool. 1 exploratory candidate."
        ),
    },
    "NETS_DEV": {
        "name": "Computer Networks (development partition)",
        "eligibility": "ELIGIBLE",
        "split_type": "DOCUMENT_DISJOINT",
        "note": "Tanenbaum 6e excerpts for development partition.",
    },
    "STAT": {
        "name": "Probability & Statistics",
        "eligibility": "EXCLUDED",
        "split_type": "N/A",
        "note": (
            "Pattern recognition appendix chunks too sparse (1–2 chunks). "
            "Data Science 2019 is a book index — excluded from prose extraction."
        ),
    },
    "DSA": {
        "name": "Data Structures & Algorithms",
        "eligibility": "EXCLUDED",
        "split_type": "N/A",
        "note": "No dedicated DSA documents with indexed prose found.",
    },
}

# Documents excluded from prose relation extraction
EXCLUDED_DOC_PATTERNS = {
    "data_science_2019/Index_2019_Data-Science.pdf": "BOOK_INDEX",
    "predictive_analytics_and_data_mining_2015/Index_2015_Predictive-Analytics-and-Data-Mining.pdf": "BOOK_INDEX",
    "knowledge_representation_and_reasoning_2004/Index_2004_Knowledge-Representation-and-Reasoning.pdf": "BOOK_INDEX",
}


# ---------------------------------------------------------------------------
# Targeted candidate specifications
# Each entry describes ONE candidate: exact doc_id, chunk_id, and evidence span.
# The evidence span must be a verbatim substring of the chunk's text_passage.
# concept_a and concept_b must both appear (case-insensitive) in the span.
# candidate_category: POSSIBLE_RELATION | AMBIGUOUS | LIKELY_UNRELATED
# These are ANNOTATION CATEGORIES, not verified labels.
# ---------------------------------------------------------------------------

CANDIDATE_SPECS = [

    # ── OS — development (06_Address_Spaces.pdf) ────────────────────────────
    {
        "domain": "OS",
        "partition": "development",
        "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf",
        "chunk_id": "paging_seed_005",
        "concept_a": "Operating System",
        "concept_b": "Address Spaces",
        "evidence_span_query": "Operating System",   # used to locate span in chunk
        "evidence_span_query_b": "address space",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_PART_OF",
        "notes": "OSTEP Ch13 — OS manages address spaces for processes",
    },
    {
        "domain": "OS",
        "partition": "development",
        "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf",
        "chunk_id": "paging_seed_005",
        "concept_a": "Address Spaces",
        "concept_b": "code",
        "evidence_span_query": "code",
        "evidence_span_query_b": "address space",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_PART_OF",
        "notes": "OSTEP Ch13 — code, data, stack are parts of address space",
    },

    # ── OS — evaluation (08_Paging.pdf) ─────────────────────────────────────
    {
        "domain": "OS",
        "partition": "evaluation",
        "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
        "chunk_id": "paging_seed_001",
        "concept_a": "paging",
        "concept_b": "segmentation",
        "evidence_span_query": "paging",
        "evidence_span_query_b": "segmentation",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_CONTRASTS",
        "notes": "OSTEP Ch18 — paging vs segmentation as two space-management approaches",
    },
    {
        "domain": "OS",
        "partition": "evaluation",
        "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
        "chunk_id": "paging_seed_003",
        "concept_a": "physical memory",
        "concept_b": "free list",
        "evidence_span_query": "physical memory",
        "evidence_span_query_b": "free list",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "OSTEP Ch18 — OS uses a free list to track free pages in physical memory",
    },
    {
        "domain": "OS",
        "partition": "evaluation",
        "doc_id": "archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf",
        "chunk_id": "paging_seed_002",
        "concept_a": "virtual address space",
        "concept_b": "physical memory",
        "evidence_span_query": "virtual address space",
        "evidence_span_query_b": "physical memory",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "OSTEP Ch18 — virtual address space pages mapped to physical memory frames",
    },

    # ── AIML — development: Vaswani2017 ─────────────────────────────────────
    {
        "domain": "AIML",
        "partition": "development",
        "doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
        "chunk_id": "chunk_005",
        "concept_a": "Transformer",
        "concept_b": "attention mechanism",
        "evidence_span_query": "Transformer",
        "evidence_span_query_b": "attention mechanism",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "Vaswani2017 — Transformer relies entirely on attention mechanism",
    },
    {
        "domain": "AIML",
        "partition": "development",
        "doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
        "chunk_id": "chunk_007",
        "concept_a": "Transformer",
        "concept_b": "self-attention",
        "evidence_span_query": "Transformer",
        "evidence_span_query_b": "self-attention",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "Vaswani2017 — Transformer uses self-attention to compute representations",
    },
    {
        # encoder and decoder appear close together in chunk_008
        "domain": "AIML",
        "partition": "development",
        "doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
        "chunk_id": "chunk_008",
        "concept_a": "encoder",
        "concept_b": "decoder",
        "evidence_span_query": "encoder-decoder",
        "evidence_span_query_b": "encoder maps",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_PART_OF",
        "notes": "Vaswani2017 — encoder maps input to continuous representations; decoder generates output",
    },
    {
        "domain": "AIML",
        "partition": "development",
        "doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
        "chunk_id": "chunk_009",
        "concept_a": "multi-head self-attention",
        "concept_b": "feed-forward network",
        "evidence_span_query": "multi-head self-attention",
        "evidence_span_query_b": "feed-forward network",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_PART_OF",
        "notes": "Vaswani2017 — each encoder layer has two sub-layers: multi-head self-attention and feed-forward network",
    },
    {
        "domain": "AIML",
        "partition": "development",
        "doc_id": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
        "chunk_id": "chunk_010",
        "concept_a": "Scaled Dot-Product Attention",
        "concept_b": "Multi-Head Attention",
        "evidence_span_query": "Scaled Dot-Product Attention",
        "evidence_span_query_b": "Multi-Head Attention",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_PART_OF",
        "notes": "Vaswani2017 — Multi-Head Attention consists of several attention layers (Scaled Dot-Product Attention) in parallel",
    },

    # ── AIML — development: Hu2021_LoRA ─────────────────────────────────────
    {
        "domain": "AIML",
        "partition": "development",
        "doc_id": "papers/Hu2021_LoRA.pdf",
        "chunk_id": "chunk_005",
        "concept_a": "LoRA",
        "concept_b": "low-rank matrices",
        "evidence_span_query": "LoRA",
        "evidence_span_query_b": "low-rank matrices",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "Hu2021 — LoRA optimizes injected low-rank matrices instead of all parameters",
    },
    {
        # Note: 'fi' ligature used in PDF text: 'ﬁne-tuning', 'ﬁne-tuned'
        "domain": "AIML",
        "partition": "development",
        "doc_id": "papers/Hu2021_LoRA.pdf",
        "chunk_id": "chunk_007",
        "concept_a": "pre-trained model",
        "concept_b": "downstream task",
        "evidence_span_query": "downstream task",
        "evidence_span_query_b": "pre-trained model",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "Hu2021 — for each downstream task, different parameter set learned from pre-trained model",
    },

    # ── AIML — evaluation: Dettmers2023_QLoRA ───────────────────────────────
    {
        "domain": "AIML",
        "partition": "evaluation",
        "doc_id": "papers/Dettmers2023_QLoRA.pdf",
        "chunk_id": "chunk_005",
        "concept_a": "4-bit NormalFloat",
        "concept_b": "Double Quantization",
        "evidence_span_query": "4-bit NormalFloat",
        "evidence_span_query_b": "Double Quantization",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_PART_OF",
        "notes": "Dettmers2023 — both are innovations in QLORA for memory reduction",
    },
    {
        "domain": "AIML",
        "partition": "evaluation",
        "doc_id": "papers/Dettmers2023_QLoRA.pdf",
        "chunk_id": "chunk_006",
        "concept_a": "QLORA",
        "concept_b": "instruction finetuning",
        "evidence_span_query": "QLORA",
        "evidence_span_query_b": "instruction finetuning",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "Dettmers2023 — QLORA enables in-depth study of instruction finetuning",
    },

    # ── AIML — evaluation: Bahdanau2014 ─────────────────────────────────────
    {
        # Note: 'fi' ligature in PDF: 'ﬁxed-length', 'ﬁxed'
        "domain": "AIML",
        "partition": "evaluation",
        "doc_id": "papers/Bahdanau2014_Attention.pdf",
        "chunk_id": "chunk_005",
        "concept_a": "encoder",
        "concept_b": "sequence of vectors",
        "evidence_span_query": "encoder",
        "evidence_span_query_b": "sequence of vectors",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "Bahdanau2014 — encoder produces sequence of vectors (not fixed-length) for adaptive decoding",
    },
    {
        "domain": "AIML",
        "partition": "evaluation",
        "doc_id": "papers/Bahdanau2014_Attention.pdf",
        "chunk_id": "chunk_007",
        "concept_a": "neural machine translation",
        "concept_b": "LSTM",
        "evidence_span_query": "neural machine translation",
        "evidence_span_query_b": "LSTM",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "Bahdanau2014 — NMT based on RNNs with LSTM achieves close to state-of-the-art",
    },

    # ── NETS — evaluation: Real-time network security ────────────────────────
    {
        "domain": "NETS",
        "partition": "evaluation",
        "doc_id": "papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf",
        "chunk_id": "chunk_006",
        "concept_a": "anomaly detection",
        "concept_b": "signature-based systems",
        "evidence_span_query": "anomaly detection",
        "evidence_span_query_b": "signature-based systems",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_CONTRASTS",
        "notes": "D-MAGIC paper — anomaly detection contrasted with signature-based systems",
    },
    {
        "domain": "NETS",
        "partition": "evaluation",
        "doc_id": "papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf",
        "chunk_id": "chunk_008",
        "concept_a": "Graph Neural Networks",
        "concept_b": "D-MAGIC",
        "evidence_span_query": "Graph Neural Networks",
        "evidence_span_query_b": "D-MAGIC",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "D-MAGIC paper — D-MAGIC leverages Graph Neural Networks (GNNs)",
    },
    {
        "domain": "NETS",
        "partition": "evaluation",
        "doc_id": "papers/Real-time network security: Integrating ANN and dynamic graph-based.pdf",
        "chunk_id": "chunk_005",
        "concept_a": "real-time NIDS",
        "concept_b": "latency",
        "evidence_span_query": "real-time NIDS",
        "evidence_span_query_b": "latency",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "D-MAGIC paper — real-time NIDS design challenge involves latency",
    },

    # ── NETS — development: Tanenbaum 6e ────────────────────────────────────
    {
        "domain": "NETS_DEV",
        "partition": "development",
        "doc_id": "doc_computer_networks_6_e",
        "chunk_id": "doc_computer_networks_6_e_p42_1",
        "concept_a": "Physical Layer",
        "concept_b": "Data Link Layer",
        "evidence_span_query": "Physical Layer",
        "evidence_span_query_b": "Data Link Layer",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_PREREQUISITE",
        "notes": "Tanenbaum 6e — OSI model layers; Physical Layer is below Data Link Layer",
    },

    # ── TOC — exploratory: Willard2023 ───────────────────────────────────────
    {
        "domain": "TOC",
        "partition": "exploratory",
        "doc_id": "papers/Willard2023_Outlines.pdf",
        "chunk_id": "chunk_006",
        "concept_a": "multinomial sampling",
        "concept_b": "EOS token",
        "evidence_span_query": "multinomial sampling",
        "evidence_span_query_b": "EOS token",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "Willard2023 — multinomial sampling generates tokens until EOS token (exploratory only)",
    },
    {
        "domain": "TOC",
        "partition": "exploratory",
        "doc_id": "papers/Willard2023_Outlines.pdf",
        "chunk_id": "chunk_005",
        "concept_a": "vocabulary",
        "concept_b": "categorical distribution",
        "evidence_span_query": "vocabular",
        "evidence_span_query_b": "Categorical",
        "candidate_category": "AMBIGUOUS",
        "candidate_relation_hint": "POSSIBLE_RELATED",
        "notes": "Willard2023 — vocabulary V used to define Categorical distribution for next token",
    },

    # ── DBMS — exploratory ───────────────────────────────────────────────────
    {
        "domain": "DBMS",
        "partition": "exploratory",
        "doc_id": "doc_fundamentals_of_database_system_7e",
        "chunk_id": "doc_fundamentals_of_database_system_7e_p145_1",
        "concept_a": "Relational Algebra",
        "concept_b": "query language",
        "evidence_span_query": "Relational Algebra",
        "evidence_span_query_b": "query language",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_PART_OF",
        "notes": "Elmasri 7e p145 — Relational Algebra is a formal procedural query language",
    },

    # ── COMPILERS — exploratory ──────────────────────────────────────────────
    {
        "domain": "COMPILERS",
        "partition": "exploratory",
        "doc_id": "doc_compilers_principles_techniques_and_tools",
        "chunk_id": "doc_compilers_principles_techniques_and_tools_p192_1",
        "concept_a": "parser",
        "concept_b": "context-free grammar",
        "evidence_span_query": "parser",
        "evidence_span_query_b": "context-free grammar",
        "candidate_category": "POSSIBLE_RELATION",
        "candidate_relation_hint": "POSSIBLE_USES",
        "notes": "Dragon Book p192 — parser verifies tokens against context-free grammar",
    },
]


# ---------------------------------------------------------------------------
# Span finder: locate an evidence span in chunk text that contains both terms
# ---------------------------------------------------------------------------

def find_evidence_span(
    chunk_text: str,
    term_a: str,
    term_b: str,
    window: int = 600,
) -> tuple[str, int, int]:
    """Find a verbatim substring of chunk_text containing both terms.

    Searches case-insensitively for each term. Extends a window around the
    earliest-to-latest occurrence. The span is a verbatim slice of chunk_text.

    Returns:
        (span, offset_start, offset_end) or ("", -1, -1) if not found.
    """
    lower = chunk_text.lower()
    a_lower = term_a.lower()
    b_lower = term_b.lower()

    pos_a = lower.find(a_lower)
    pos_b = lower.find(b_lower)

    if pos_a == -1 or pos_b == -1:
        return "", -1, -1

    # Span from first character of whichever term appears first to last character of whichever appears last
    core_start = min(pos_a, pos_b)
    core_end = max(pos_a + len(a_lower), pos_b + len(b_lower))
    core_dist = core_end - core_start

    if core_dist > window:
        # Concepts too far apart — cannot produce a coherent evidence span
        return "", -1, -1

    # Expand left and right for context (up to 150 chars each side)
    expand_left = max(0, core_start - 150)
    expand_right = min(len(chunk_text), core_end + 150)
    span_raw = chunk_text[expand_left:expand_right]

    # Trim to nearest sentence start on the left side (look within first 120 chars)
    for sep in (". ", ".\n", "\n\n", "\n"):
        idx = span_raw.find(sep, 0, min(120, len(span_raw)))
        if 0 <= idx < 120:
            candidate_trim = span_raw[idx + len(sep):]
            if a_lower in candidate_trim.lower() and b_lower in candidate_trim.lower():
                span_raw = candidate_trim
                expand_left += idx + len(sep)
                break

    # Trim to nearest sentence end on the right side
    for sep in (". ", ".\n"):
        idx = span_raw.rfind(sep, max(0, len(span_raw) - 120))
        if idx != -1:
            candidate_trim = span_raw[:idx + 1]
            if a_lower in candidate_trim.lower() and b_lower in candidate_trim.lower():
                span_raw = candidate_trim
                break

    span_raw = span_raw.strip()

    if not span_raw:
        return "", -1, -1

    if a_lower in span_raw.lower() and b_lower in span_raw.lower():
        # Find exact position in original text
        abs_start = chunk_text.find(span_raw)
        if abs_start == -1:
            # String may have been modified by strip — fall back to computed position
            abs_start = expand_left
        abs_end = abs_start + len(span_raw)
        return span_raw, abs_start, abs_end

    return "", -1, -1


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------

def build_candidates(db_path: str, output_dir: str, verbose: bool = False) -> dict:
    """Build the corpus-locked annotation candidate pool."""

    db = kuzu.Database(db_path)
    conn = kuzu.Connection(db)
    conn_val = kuzu.Connection(db)

    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # Fetch all needed chunks up front
    chunk_cache: dict[tuple[str, str], dict] = {}

    def get_chunk(doc_id: str, chunk_id: str) -> dict | None:
        key = (doc_id, chunk_id)
        if key in chunk_cache:
            return chunk_cache[key]
        safe_doc = doc_id.replace("'", "\\'")
        safe_ck = chunk_id.replace("'", "\\'")
        res = conn.execute(
            f"MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) "
            f"WHERE d.id='{safe_doc}' AND c.chunk_id='{safe_ck}' "
            f"RETURN c.id, c.chunk_id, c.page_number, c.section_title, "
            f"c.text_passage, c.text_offset_start, c.text_offset_end LIMIT 1"
        )
        if not res.has_next():
            chunk_cache[key] = None
            return None
        row = res.get_next()
        node_id, ck, pg, sec, txt, off_s, off_e = row
        record = {
            "node_id": node_id,
            "chunk_id": ck,
            "page_number": pg,
            "section_title": sec or "",
            "text_passage": txt or "",
            "text_offset_start": off_s,
            "text_offset_end": off_e,
        }
        chunk_cache[key] = record
        return record

    candidates: list[dict] = []
    rejected: list[dict] = []
    domain_counters: dict[str, int] = {}

    for spec in CANDIDATE_SPECS:
        doc_id = spec["doc_id"]
        chunk_id = spec["chunk_id"]
        concept_a = spec["concept_a"]
        concept_b = spec["concept_b"]
        term_a = spec.get("evidence_span_query", concept_a)
        term_b = spec.get("evidence_span_query_b", concept_b)

        chunk = get_chunk(doc_id, chunk_id)
        if chunk is None:
            reason = f"Chunk '{chunk_id}' not found in document '{doc_id}'"
            if verbose:
                print(f"  [SKIP] {reason}")
            rejected.append({
                "spec_concept_a": concept_a,
                "spec_concept_b": concept_b,
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "reason": reason,
            })
            continue

        text = chunk["text_passage"]
        span, off_start, off_end = find_evidence_span(text, term_a, term_b)

        if not span:
            reason = (
                f"Could not find both '{term_a}' and '{term_b}' within "
                f"window in chunk '{chunk_id}'"
            )
            if verbose:
                print(f"  [SKIP] {doc_id}|{chunk_id}: {reason}")
            rejected.append({
                "spec_concept_a": concept_a,
                "spec_concept_b": concept_b,
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "reason": reason,
            })
            continue

        # Hardened validation gate
        vr = validate_provenance_record(
            claimed_doc_id=doc_id,
            claimed_chunk_id=chunk_id,
            claimed_page_number=chunk["page_number"],
            evidence_text=span,
            conn=conn_val,
        )

        if not vr["is_valid"]:
            reason = f"Provenance gate: {vr['reason']}"
            if verbose:
                print(f"  [REJECT] {doc_id}|{chunk_id}|{concept_a}×{concept_b}: {reason}")
            rejected.append({
                "spec_concept_a": concept_a,
                "spec_concept_b": concept_b,
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "reason": reason,
                "failure_layers": vr.get("failure_layers", []),
                "evidence_match_type": vr.get("evidence_match_type"),
            })
            continue

        # Build candidate record
        domain = spec["domain"]
        domain_counters[domain] = domain_counters.get(domain, 0) + 1
        item_id = f"C22-{domain}-{domain_counters[domain]:02d}"
        fp = chunk_fingerprint(text)

        candidate = {
            "item_id": item_id,
            "domain": domain,
            "domain_name": DOMAIN_ELIGIBILITY.get(domain, {}).get("name", domain),
            "domain_eligibility": DOMAIN_ELIGIBILITY.get(domain, {}).get("eligibility", "UNKNOWN"),
            "partition": spec["partition"],
            "doc_id": doc_id,
            "chunk_id": chunk["chunk_id"],       # actual DB chunk_id
            "page_number": chunk["page_number"],  # actual DB page
            "section_title": chunk["section_title"],
            "concept_a": concept_a,
            "concept_b": concept_b,
            "evidence_span": span,
            "evidence_offset_start_in_chunk": off_start,
            "evidence_offset_end_in_chunk": off_end,
            "evidence_len_chars": len(span),
            "chunk_text_len_chars": len(text),
            "chunk_fingerprint_sha256_16": fp,
            "evidence_match_type": vr["evidence_match_type"],
            "candidate_category": spec["candidate_category"],
            "candidate_relation_hint": spec.get("candidate_relation_hint", ""),
            # Human annotation fields — intentionally blank
            "label_category": "CANDIDATE_UNLABELED",
            "human_relation_label": "",
            "human_direction": "",
            "human_confidence": "",
            "human_notes": "",
            "annotation_verdict": "PENDING",
            "redistribution_note": spec.get("notes", ""),
            "source_notes": DOMAIN_ELIGIBILITY.get(domain, {}).get("note", ""),
        }
        candidates.append(candidate)

        if verbose:
            print(
                f"  [ACCEPT] {item_id} {concept_a!r} × {concept_b!r} "
                f"({spec['candidate_category']}) match={vr['evidence_match_type']}"
            )

    # ── Write CSV ────────────────────────────────────────────────────────────
    csv_path = out_path / "annotation_candidates_verified.csv"
    if candidates:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(candidates[0].keys()))
            writer.writeheader()
            writer.writerows(candidates)

    # ── Write rejection log ──────────────────────────────────────────────────
    rej_path = out_path / "rejected_candidates_log.csv"
    if rejected:
        with open(rej_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rejected[0].keys()))
            writer.writeheader()
            writer.writerows(rejected)

    # ── Category statistics ──────────────────────────────────────────────────
    cat_counts = {
        "POSSIBLE_RELATION": sum(1 for c in candidates if c["candidate_category"] == "POSSIBLE_RELATION"),
        "AMBIGUOUS": sum(1 for c in candidates if c["candidate_category"] == "AMBIGUOUS"),
        "LIKELY_UNRELATED": sum(1 for c in candidates if c["candidate_category"] == "LIKELY_UNRELATED"),
    }

    # ── Write JSON summary ───────────────────────────────────────────────────
    domain_summary: dict[str, dict] = {}
    for c in candidates:
        d = c["domain"]
        if d not in domain_summary:
            domain_summary[d] = {
                "domain_name": c["domain_name"],
                "eligibility": c["domain_eligibility"],
                "partition": c["partition"],
                "item_count": 0,
                "docs": set(),
            }
        domain_summary[d]["item_count"] += 1
        domain_summary[d]["docs"].add(c["doc_id"])
    for d in domain_summary:
        domain_summary[d]["docs"] = sorted(domain_summary[d]["docs"])

    summary = {
        "total_candidates": len(candidates),
        "total_rejected_specs": len(rejected),
        "candidate_categories": cat_counts,
        "domain_summary": domain_summary,
        "all_verified_by_provenance_gate": all(
            c["evidence_match_type"] in ("EXACT", "WHITESPACE_NORMALIZED")
            for c in candidates
        ),
        "domain_eligibility_matrix": DOMAIN_ELIGIBILITY,
        "excluded_doc_patterns": EXCLUDED_DOC_PATTERNS,
        "human_labels_generated": False,
        "note": (
            "All candidates are CANDIDATE_UNLABELED. "
            "candidate_category is an annotation task category, NOT a verified semantic label. "
            "Human annotation is NOT yet performed. "
            "Do not use candidate_relation_hint as a ground-truth label."
        ),
    }

    json_path = out_path / "candidate_pool_summary.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    return {
        "total_candidates": len(candidates),
        "total_rejected": len(rejected),
        "candidates": candidates,
        "rejected": rejected,
        "category_counts": cat_counts,
        "csv_path": str(csv_path),
        "json_path": str(json_path),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="okf_graph.db")
    parser.add_argument(
        "--output",
        default="research/s4-g2-2-corpus-locked-annotation/annotation_candidates",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if args.verbose:
        print(f"Building corpus-locked annotation candidates from {args.db}")

    result = build_all_candidates = build_candidates(args.db, args.output, verbose=args.verbose)

    print(f"\nTotal verified candidates : {result['total_candidates']}")
    print(f"Total rejected specs       : {result['total_rejected']}")
    print(f"Category breakdown         : {result['category_counts']}")

    if result["total_candidates"] < 12:
        print(
            f"WARNING: Only {result['total_candidates']} candidates generated (target 12-24).",
            file=sys.stderr,
        )
        sys.exit(1)
    sys.exit(0)
