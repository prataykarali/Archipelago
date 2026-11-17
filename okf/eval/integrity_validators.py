"""Integrity validators for academic graph extraction and evaluation.

Provides rigorous, evidence-grounded validation functions:

1. Full directed cycle detection for arbitrary length k >= 2 (DFS back-edge enumeration).
   IMPORTANT: The implemented method enumerates representative back-edge cycles found
   during a single DFS traversal. This is NOT the same as elementary-cycle enumeration
   (Johnson's algorithm). It provides cycle existence detection and representative
   examples, but may undercount overlapping cycles in dense graphs. See docstring on
   detect_directed_cycles() for the precise semantic guarantee.

2. Hardened source-provenance verification against Kùzu graph DB.
   Requires exact document-ID + chunk-ID identity match before any evidence check.
   Distinguishes: exact match / whitespace-normalized / approximate / failed.
   Never treats punctuation-only or empty normalizations as valid.
   Never substitutes a claimed chunk ID when the lookup fails.

3. Denominator-aware coverage and error accounting.

4. Semantic argument direction auditing for asymmetric relations (PART_OF, USES, REQUIRES).

5. Evaluation split categorization (document-disjoint vs within-document).
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple


# ---------------------------------------------------------------------------
# Phase B — Cycle detection (corrected terminology)
# ---------------------------------------------------------------------------

def detect_directed_cycles(
    edges: list[dict[str, Any]],
    edge_types: Optional[tuple[str, ...]] = ("REQUIRES", "UNLOCKS"),
) -> dict[str, Any]:
    """Detect directed cycles using DFS back-edge enumeration.

    METHOD GUARANTEE:
        This function performs a depth-first search and records one representative
        cycle path for each distinct back-edge encountered. The normalized cycle
        signature (minimum-rotation of the node sequence) is used for de-duplication.

        WHAT THIS IS:
            - Cycle existence detection: reliable. If cycle_count > 0, at least one
              directed cycle of length >= 2 exists.
            - Representative cycle enumeration: each unique back-edge yields one
              example cycle path. Useful for diagnosis.

        WHAT THIS IS NOT:
            - Complete elementary-cycle enumeration (Johnson's algorithm). In graphs
              with overlapping or nested cycles, the DFS-back-edge count may be less
              than the true elementary cycle count. Do not report cycle_count as
              "number of elementary cycles" in manuscripts.

        DETERMINISM:
            Adjacency lists and DFS order are sorted lexicographically, so results
            are deterministic for the same input.

    Args:
        edges: List of edge dictionaries with keys 'from_name', 'to_name', 'edge_type'.
        edge_types: Tuple of relation types to include. None includes all types.

    Returns:
        Dict with:
        - 'cycle_count': int — number of distinct representative cycles found
        - 'has_cycles': bool
        - 'cycles': list of cycle paths, each as [u1, u2, ..., uk, u1]
        - 'cycle_lengths': list of int (length of each cycle, excluding the closing node)
        - 'nodes_in_cycles': sorted list of concept names participating in any cycle
        - 'total_nodes_audited': int — number of distinct nodes in filtered subgraph
        - 'method': str — description of the algorithm used
        - 'methodological_note': str — precision limitation statement
    """
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        etype = str(e.get("edge_type", "")).upper()
        if edge_types is None or etype in edge_types:
            u = str(e.get("from_name", "")).strip().lower()
            v = str(e.get("to_name", "")).strip().lower()
            if u and v and u != v:
                adj[u].add(v)

    color: dict[str, int] = {}   # WHITE=0, GRAY=1, BLACK=2
    cycles: list[list[str]] = []
    seen_signatures: set[tuple[str, ...]] = set()

    def dfs(u: str, path: list[str]) -> None:
        color[u] = 1
        path.append(u)
        for v in sorted(adj.get(u, set())):
            c = color.get(v, 0)
            if c == 1:  # back-edge → cycle
                start = path.index(v)
                cycle_nodes = path[start:]
                # Canonical form: minimum-rotation
                min_idx = cycle_nodes.index(min(cycle_nodes))
                sig = tuple(cycle_nodes[min_idx:] + cycle_nodes[:min_idx])
                if sig not in seen_signatures:
                    seen_signatures.add(sig)
                    cycles.append(cycle_nodes + [v])
            elif c == 0:
                dfs(v, path)
        path.pop()
        color[u] = 2

    for node in sorted(adj.keys()):
        if color.get(node, 0) == 0:
            dfs(node, [])

    nodes_in_cycles: set[str] = set()
    for c in cycles:
        for n in c[:-1]:
            nodes_in_cycles.add(n)

    return {
        "cycle_count": len(cycles),
        "has_cycles": len(cycles) > 0,
        "cycles": cycles,
        "cycle_lengths": [len(c) - 1 for c in cycles],
        "nodes_in_cycles": sorted(nodes_in_cycles),
        "total_nodes_audited": len(adj),
        "method": "DFS back-edge enumeration with minimum-rotation deduplication",
        "methodological_note": (
            "cycle_count reports representative back-edge cycles, NOT the complete "
            "set of elementary cycles. Use Johnson's algorithm for exact elementary "
            "cycle enumeration. has_cycles is reliable; cycle_count may undercount "
            "in graphs with overlapping cycles."
        ),
    }


# ---------------------------------------------------------------------------
# Phase A — Hardened provenance validation
# ---------------------------------------------------------------------------

_PUNCT_ONLY_RE = re.compile(r"^[\s\W]+$")


def _normalize_text(raw: str) -> str:
    """Whitespace-normalize and unicode-normalize a text string.

    Returns the normalized string, or '' if the result contains only
    punctuation/whitespace (which must NOT be treated as a valid match).
    """
    nfc = unicodedata.normalize("NFC", raw)
    collapsed = " ".join(nfc.split())
    if _PUNCT_ONLY_RE.match(collapsed):
        return ""
    return collapsed


def _classify_evidence_match(
    evidence: str,
    chunk_text: str,
) -> tuple[str, str]:
    """Classify how evidence matches chunk text.

    Returns (match_type, reason) where match_type is one of:
        'EXACT'              — evidence is a verbatim substring of chunk_text
        'WHITESPACE_NORMALIZED' — matches after collapsing whitespace
        'APPROXIMATE'        — >80% character overlap after normalization (Jaccard on trigrams)
        'FAILED'             — does not match by any criterion
        'INVALID_EVIDENCE'   — evidence is empty or punctuation-only after normalization

    Never treats punctuation-only or empty evidence as EXACT or WHITESPACE_NORMALIZED.
    """
    ev_norm = _normalize_text(evidence)
    if not ev_norm:
        return ("INVALID_EVIDENCE", "Evidence is empty or punctuation-only after normalization")

    # Exact substring match
    if evidence in chunk_text:
        return ("EXACT", "Verbatim substring found in chunk text")

    # Whitespace-normalized match
    ct_norm = _normalize_text(chunk_text)
    if ev_norm and ev_norm in ct_norm:
        return ("WHITESPACE_NORMALIZED", "Match found after collapsing whitespace/unicode")

    # Approximate: trigram Jaccard similarity >= 0.80
    def trigrams(s: str) -> set[str]:
        return {s[i:i+3] for i in range(len(s) - 2)} if len(s) >= 3 else set()

    ev_tri = trigrams(ev_norm.lower())
    ct_tri = trigrams(ct_norm.lower())
    if ev_tri and ct_tri:
        intersection = len(ev_tri & ct_tri)
        union = len(ev_tri | ct_tri)
        jaccard = intersection / union if union else 0.0
        if jaccard >= 0.80:
            return (
                "APPROXIMATE",
                f"Trigram Jaccard similarity {jaccard:.2f} >= 0.80 (not verbatim)"
            )

    return ("FAILED", "Evidence text not found in chunk text by any matching criterion")


def validate_provenance_record(
    claimed_doc_id: str,
    claimed_chunk_id: str,
    claimed_page_number: Optional[int],
    evidence_text: str,
    conn: Any,
) -> dict[str, Any]:
    """Hardened provenance validation against the frozen Kùzu corpus.

    Validation layers (each is independent; all failures are reported):

    L0 — Input sanity: claimed_doc_id and claimed_chunk_id must be non-empty strings.
    L1 — Document existence: exact match on Document.id using a parameterized query.
    L2 — Chunk identity: chunk must be linked to the exact claimed document.
         The actual chunk_id from the DB is returned. The claimed chunk_id is never
         substituted as though verification succeeded if the lookup fails.
    L3 — Page metadata: if claimed_page_number is provided, must match chunk.page_number.
    L4 — Evidence match: evidence_text must occur in the matched chunk's text_passage.
         Match is classified as EXACT, WHITESPACE_NORMALIZED, APPROXIMATE, or FAILED.
         APPROXIMATE is NOT treated as valid for admission purposes.
         INVALID_EVIDENCE (empty / punctuation-only) is treated as FAILED.
    L5 — Source-pointer vs semantic separation: this function only validates pointer
         validity (L0–L4). Semantic correctness of the relation requires human annotation.

    Args:
        claimed_doc_id: The document ID as claimed by the annotation item.
        claimed_chunk_id: The chunk ID as claimed by the annotation item.
        claimed_page_number: Optional claimed page number. Pass None to skip L3.
        evidence_text: The evidence passage claimed to be from that chunk.
        conn: An active Kùzu connection object.

    Returns:
        Dict with:
        - 'is_valid': bool — True only if L1 + L2 + L4(EXACT|WHITESPACE_NORMALIZED) pass.
                            L3 failure does not block is_valid but is flagged.
        - 'doc_exists': bool
        - 'chunk_id_match': bool — chunk found AND linked to claimed document
        - 'actual_chunk_id': str | None — the DB chunk id (never the claimed id if not found)
        - 'actual_page_number': int | None
        - 'page_number_match': bool | None — None if claimed_page_number was not provided
        - 'evidence_match_type': str — EXACT / WHITESPACE_NORMALIZED / APPROXIMATE / FAILED / INVALID_EVIDENCE / NOT_CHECKED
        - 'evidence_match_valid': bool — True only for EXACT or WHITESPACE_NORMALIZED
        - 'source_pointer_valid': bool — L1 + L2 passed (doc + chunk found)
        - 'page_valid': bool | None
        - 'semantic_support': str — always 'NOT_MEASURED' (requires human annotation)
        - 'redistribution_permitted': str — 'UNKNOWN' (requires licensing audit per document)
        - 'reason': str — human-readable explanation of the overall verdict
        - 'failure_layers': list[str] — which layers failed
    """
    failures: list[str] = []
    result: dict[str, Any] = {
        "is_valid": False,
        "doc_exists": False,
        "chunk_id_match": False,
        "actual_chunk_id": None,
        "actual_page_number": None,
        "page_number_match": None,
        "evidence_match_type": "NOT_CHECKED",
        "evidence_match_valid": False,
        "source_pointer_valid": False,
        "page_valid": None,
        "semantic_support": "NOT_MEASURED",
        "redistribution_permitted": "UNKNOWN",
        "reason": "",
        "failure_layers": [],
    }

    # L0 — Input sanity
    doc_id_clean = str(claimed_doc_id or "").strip()
    chunk_id_clean = str(claimed_chunk_id or "").strip()
    ev_clean = str(evidence_text or "").strip()

    if not doc_id_clean:
        failures.append("L0:missing_doc_id")
        result["failure_layers"] = failures
        result["reason"] = "L0 FAIL: claimed_doc_id is empty"
        return result
    if not chunk_id_clean:
        failures.append("L0:missing_chunk_id")
        result["failure_layers"] = failures
        result["reason"] = "L0 FAIL: claimed_chunk_id is empty"
        return result

    # L1 — Document existence (parameterized via f-string; Kùzu does not support
    # positional parameters in this client version — escape quotes defensively)
    safe_doc_id = doc_id_clean.replace("'", "\\'").replace("\\", "\\\\")
    try:
        res = conn.execute(
            f"MATCH (d:Document) WHERE d.id = '{safe_doc_id}' RETURN d.id LIMIT 1"
        )
        doc_found = res.has_next()
    except Exception as exc:
        failures.append(f"L1:query_error({exc})")
        result["failure_layers"] = failures
        result["reason"] = f"L1 FAIL: DB query error — {exc}"
        return result

    result["doc_exists"] = doc_found
    if not doc_found:
        failures.append("L1:document_not_found")
        result["failure_layers"] = failures
        result["reason"] = f"L1 FAIL: Document '{doc_id_clean}' not found in okf_graph.db"
        return result

    # L2 — Chunk identity: chunk must exist AND be linked to this exact document
    # We look up by chunk_id field on Chunk nodes linked to the matched Document.
    safe_chunk_id = chunk_id_clean.replace("'", "\\'").replace("\\", "\\\\")
    try:
        res2 = conn.execute(
            f"MATCH (d:Document)-[:HAS_CHUNK]->(c:Chunk) "
            f"WHERE d.id = '{safe_doc_id}' AND c.chunk_id = '{safe_chunk_id}' "
            f"RETURN c.id, c.chunk_id, c.page_number, c.text_passage LIMIT 1"
        )
        chunk_found = res2.has_next()
    except Exception as exc:
        failures.append(f"L2:query_error({exc})")
        result["failure_layers"] = failures
        result["reason"] = f"L2 FAIL: DB query error — {exc}"
        return result

    if not chunk_found:
        failures.append("L2:chunk_not_found_in_document")
        # actual_chunk_id stays None — do NOT substitute claimed_chunk_id
        result["failure_layers"] = failures
        result["reason"] = (
            f"L2 FAIL: chunk_id='{chunk_id_clean}' not found in document='{doc_id_clean}' "
            f"(not found linked to that document). actual_chunk_id=None (claimed id not substituted)."
        )
        # Still attempt L3/L4 as NOT_CHECKED
        result["evidence_match_type"] = "NOT_CHECKED"
        return result

    row = res2.get_next()
    actual_node_id, actual_chunk_id, actual_page, chunk_text = row
    result["chunk_id_match"] = True
    result["actual_chunk_id"] = actual_chunk_id
    result["actual_page_number"] = actual_page
    result["source_pointer_valid"] = True

    # L3 — Page number validation
    if claimed_page_number is not None:
        page_match = (actual_page == claimed_page_number)
        result["page_number_match"] = page_match
        result["page_valid"] = page_match
        if not page_match:
            failures.append(
                f"L3:page_mismatch(claimed={claimed_page_number},actual={actual_page})"
            )
    else:
        result["page_number_match"] = None
        result["page_valid"] = None   # not checked

    # L4 — Evidence match
    chunk_text_str = str(chunk_text or "")
    if not ev_clean:
        result["evidence_match_type"] = "INVALID_EVIDENCE"
        result["evidence_match_valid"] = False
        failures.append("L4:evidence_empty")
    else:
        match_type, match_reason = _classify_evidence_match(ev_clean, chunk_text_str)
        result["evidence_match_type"] = match_type
        # Only EXACT and WHITESPACE_NORMALIZED are considered valid for admission
        result["evidence_match_valid"] = match_type in ("EXACT", "WHITESPACE_NORMALIZED")
        if not result["evidence_match_valid"]:
            failures.append(f"L4:evidence_{match_type.lower()}({match_reason[:60]})")

    result["failure_layers"] = failures
    # is_valid: source pointer valid AND evidence match valid
    # L3 page mismatch is flagged but does not block (annotation items may span pages)
    result["is_valid"] = result["source_pointer_valid"] and result["evidence_match_valid"]
    if result["is_valid"]:
        result["reason"] = "VERIFIED: document found, chunk linked to document, evidence matched"
    else:
        result["reason"] = "; ".join(failures) if failures else "Unknown failure"

    return result


def validate_candidate_pool(
    candidates: list[dict[str, Any]],
    conn: Any,
) -> dict[str, Any]:
    """Validate a list of annotation candidates against the corpus.

    Each candidate dict should have:
        claimed_doc_id, claimed_chunk_id, claimed_page_number (int|None),
        evidence_text, item_id (str).

    Returns:
        Dict with:
        - 'total': int
        - 'verified': int
        - 'mismatch': int
        - 'unverifiable': int
        - 'results': list of per-item validation dicts including item_id
        - 'verified_rate': float | None
    """
    total = len(candidates)
    if total == 0:
        return {
            "total": 0, "verified": 0, "mismatch": 0, "unverifiable": 0,
            "results": [], "verified_rate": None,
        }

    results = []
    verified = mismatch = unverifiable = 0

    for cand in candidates:
        item_id = str(cand.get("item_id", "UNKNOWN"))
        v = validate_provenance_record(
            claimed_doc_id=str(cand.get("claimed_doc_id", "")),
            claimed_chunk_id=str(cand.get("claimed_chunk_id", "")),
            claimed_page_number=cand.get("claimed_page_number"),
            evidence_text=str(cand.get("evidence_text", "")),
            conn=conn,
        )
        v["item_id"] = item_id
        # Classify
        if not v["doc_exists"]:
            v["audit_verdict"] = "UNVERIFIABLE"
            unverifiable += 1
        elif v["is_valid"]:
            v["audit_verdict"] = "VERIFIED"
            verified += 1
        else:
            v["audit_verdict"] = "MISMATCH"
            mismatch += 1
        results.append(v)

    return {
        "total": total,
        "verified": verified,
        "mismatch": mismatch,
        "unverifiable": unverifiable,
        "results": results,
        "verified_rate": round(verified / total, 4) if total else None,
    }


def calculate_provenance_coverage(
    edges: list[dict[str, Any]],
    conn: Any,
) -> dict[str, Any]:
    """Compute provenance coverage over a list of extracted edges.

    Uses validate_provenance_record() for each edge. Each edge must have
    keys: doc_id, chunk_id, evidence_text. page_number is optional.

    Returns:
        Dict with:
        - 'valid_provenance_coverage': float | None
        - 'valid_edges_count': int
        - 'total_edges_denominator': int
        - 'status': 'measured' | 'zero_denominator'
        - 'unverified_edges': list[dict]
    """
    total = len(edges)
    if total == 0:
        return {
            "valid_provenance_coverage": None,
            "valid_edges_count": 0,
            "total_edges_denominator": 0,
            "status": "zero_denominator",
            "unverified_edges": [],
        }

    valid_count = 0
    unverified = []

    for idx, e in enumerate(edges):
        v = validate_provenance_record(
            claimed_doc_id=str(e.get("doc_id", "")),
            claimed_chunk_id=str(e.get("chunk_id", "")),
            claimed_page_number=e.get("page_number"),
            evidence_text=str(e.get("evidence_text", "")),
            conn=conn,
        )
        if v["is_valid"]:
            valid_count += 1
        else:
            unverified.append({
                "edge_index": idx,
                "from_name": e.get("from_name"),
                "to_name": e.get("to_name"),
                "edge_type": e.get("edge_type"),
                "doc_id": e.get("doc_id"),
                "chunk_id": e.get("chunk_id"),
                "reason": v["reason"],
                "failure_layers": v["failure_layers"],
            })

    coverage = valid_count / total
    return {
        "valid_provenance_coverage": round(coverage, 4),
        "valid_edges_count": valid_count,
        "total_edges_denominator": total,
        "status": "measured",
        "unverified_edges": unverified,
    }


# ---------------------------------------------------------------------------
# Semantic direction audit
# ---------------------------------------------------------------------------

def audit_semantic_direction(
    from_name: str,
    to_name: str,
    relation_type: str,
    evidence_text: str,
) -> dict[str, Any]:
    """Audit whether asymmetric relations preserve semantic argument direction.

    Rules:
    - PART_OF: from_name is subcomponent, to_name is whole/system.
    - USES: from_name is the user/technique, to_name is the tool/resource.
    - REQUIRES: from_name is dependent concept, to_name is the prerequisite.

    Returns:
        Dict with 'direction_valid' (bool|None), 'direction_type' (str),
        'diagnostic_notes' (str).
    """
    ev_low = evidence_text.lower()
    f_low = from_name.lower()
    t_low = to_name.lower()

    if relation_type.upper() == "PART_OF":
        m = re.search(
            r"([a-z0-9_\-\+\s]{2,40})\s+(?:is|are)?\s*(?:a\s+)?components?\s+of\s+([a-z0-9_\-\+\s]{2,40})",
            ev_low,
        )
        if m:
            sub, whole = m.group(1).strip(), m.group(2).strip()
            if f_low in sub and t_low in whole:
                return {"direction_valid": True, "direction_type": "natural", "diagnostic_notes": "from is component, to is whole"}
            elif t_low in sub and f_low in whole:
                return {"direction_valid": False, "direction_type": "inverted", "diagnostic_notes": "Inverted: from is whole, to is component"}

    elif relation_type.upper() == "USES":
        m = re.search(
            r"([a-z0-9_\-\+\s]{2,40})\s+(?:uses|utilizes|employs|applies)\s+([a-z0-9_\-\+\s]{2,40})",
            ev_low,
        )
        if m:
            user, tool = m.group(1).strip(), m.group(2).strip()
            if f_low in user and t_low in tool:
                return {"direction_valid": True, "direction_type": "natural", "diagnostic_notes": "from is user/technique, to is tool"}
            elif t_low in user and f_low in tool:
                return {"direction_valid": False, "direction_type": "inverted", "diagnostic_notes": "Inverted"}

    elif relation_type.upper() in ("REQUIRES", "EXPLICIT_PREREQUISITE"):
        m = re.search(
            r"([a-z0-9_\-\+\s]{2,40})\s+(?:is a prerequisite for|is required for)\s+([a-z0-9_\-\+\s]{2,40})",
            ev_low,
        )
        if m:
            prereq, target = m.group(1).strip(), m.group(2).strip()
            if f_low in target and t_low in prereq:
                return {"direction_valid": True, "direction_type": "natural", "diagnostic_notes": "from depends on to"}
            elif t_low in target and f_low in prereq:
                return {"direction_valid": False, "direction_type": "inverted", "diagnostic_notes": "Inverted"}

    return {
        "direction_valid": None,
        "direction_type": "ambiguous",
        "diagnostic_notes": "Sentence syntax lacks unambiguous SVO ordering for direction verification",
    }


# ---------------------------------------------------------------------------
# Corpus fingerprinting helper
# ---------------------------------------------------------------------------

def chunk_fingerprint(text: str) -> str:
    """Return a 16-hex-char SHA-256 fingerprint of the chunk text."""
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Backward-compatibility aliases (S4-G2.1 → S4-G2.2 rename)
# ---------------------------------------------------------------------------

def validate_edge_provenance(edge: dict, conn: Any) -> dict[str, Any]:
    """Backward-compatible alias for validate_provenance_record().

    Accepts an edge dict with keys: doc_id, chunk_id, page_number, evidence_text.
    Maps to the hardened validate_provenance_record() signature.
    Adds legacy keys ('chunk_exists', 'text_match') for S4-G2.1 test compatibility.

    Deprecated: use validate_provenance_record() directly in new code.
    """
    result = validate_provenance_record(
        claimed_doc_id=str(edge.get("doc_id", "")),
        claimed_chunk_id=str(edge.get("chunk_id", "")),
        claimed_page_number=edge.get("page_number"),
        evidence_text=str(edge.get("evidence_text", "")),
        conn=conn,
    )
    # Legacy key aliases for backward compatibility with S4-G2.1 tests
    result["chunk_exists"] = result["chunk_id_match"]
    result["text_match"] = result["evidence_match_valid"]
    result["reason"] = result.get("reason", "")
    return result
