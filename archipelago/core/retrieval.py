"""
src/core/retrieval.py — Two-Pass Hybrid Retrieval, Bounded Graph Traversal, and Suggestion Engine.

Features:
- Dense vector anchor lookup with lexical/alias fallback
- Dual-entity shortest path resolution (fixing TC-04 bug)
- Directed recursive k-hop Cypher traversals for REQUIRES and UNLOCKS
- Strict lineage passage retrieval with #page=N coordinates (capped at MAX_CHUNKS=3)
- Tier-2 Fuzzy Concept Discovery & Topic Suggestion Engine
"""

from __future__ import annotations

from collections import deque
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# Strict limits for context isolation
MAX_CHUNKS = 3
MAX_PREREQS = 4
MAX_UNLOCKS = 4


_STOPWORDS = {
    "a", "an", "the", "and", "or", "to", "of", "in", "for", "on", "with", "by", "at",
    "is", "are", "was", "were", "what", "which", "how", "why", "explain", "tell", "me",
    "about", "something", "vaguely", "related", "concept", "topic", "information",
}


def _clean_query_tokens(text: str) -> str:
    """Filter generic noise words and stopwords before lexical/fuzzy matching."""
    tokens = re.findall(r"\w+", text.lower())
    meaningful = [t for t in tokens if t not in _STOPWORDS]
    return " ".join(meaningful) if meaningful else text.strip().lower()


class TwoPassHybridRetriever:
    """Two-Pass Hybrid Retriever combining vector similarity and KùzuDB graph traversals."""

    def __init__(
        self,
        kuzu_conn: Optional[Any] = None,
        concepts_data: Optional[Dict[str, Any]] = None,
        concept_embeddings: Optional[Dict[str, np.ndarray]] = None,
    ) -> None:
        self.conn = kuzu_conn
        self.concepts_data: Dict[str, Any] = concepts_data or {}
        self.concept_embeddings: Dict[str, np.ndarray] = concept_embeddings or {}
        self._concept_keys: List[str] = list(self.concept_embeddings.keys())
        self._embed_matrix: Optional[np.ndarray] = None
        if self._concept_keys:
            try:
                self._embed_matrix = np.array([self.concept_embeddings[k] for k in self._concept_keys])
            except Exception as e:
                logger.warning("Failed to initialize embed matrix: %s", e)

        # Build alias & fuzzy index for fast exact/fuzzy resolution
        self._alias_map: Dict[str, str] = {}
        self._build_alias_index()

    def _build_alias_index(self) -> None:
        """Index concept names, labels, and acronyms for fast fuzzy & exact matches."""
        for cid, cdata in self.concepts_data.items():
            name = (cdata.get("name") or cdata.get("label") or cid).strip()
            self._alias_map[cid.lower()] = cid
            self._alias_map[name.lower()] = cid

            # Strip parenthetical clarifications, e.g. "Low-Rank Adaptation (LoRA)" -> "LoRA"
            if "(" in name and ")" in name:
                paren_val = name[name.find("(") + 1 : name.find(")")].strip()
                if paren_val:
                    self._alias_map[paren_val.lower()] = cid
                base_name = name[: name.find("(")].strip()
                if base_name:
                    self._alias_map[base_name.lower()] = cid

    def resolve_anchor(self, query: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """Resolve concept anchor nodes using dense cosine similarity and lexical matching.

        Returns:
            List of (concept_id, score) tuples sorted by descending relevance.
        """
        qn = query.strip().lower()
        if not qn:
            return []

        # 1. Exact alias match check
        if qn in self._alias_map:
            cid = self._alias_map[qn]
            return [(cid, 1.0)]

        clean_q = _clean_query_tokens(qn)
        if clean_q in self._alias_map:
            cid = self._alias_map[clean_q]
            return [(cid, 1.0)]

        # 2. Vector search if embedding matrix is available
        results: List[Tuple[str, float]] = []
        if self._embed_matrix is not None and len(self._embed_matrix) > 0:
            try:
                from archipelago.inference import embeddings as emb_mod
                q_vec = emb_mod.get_snowflake_embedding(query)
                if q_vec is not None:
                    q_norm = q_vec / (np.linalg.norm(q_vec) + 1e-9)
                    sims = np.dot(self._embed_matrix, q_norm)
                    top_indices = np.argsort(-sims)[:top_k]
                    for idx in top_indices:
                        results.append((self._concept_keys[idx], float(sims[idx])))
                    if results and results[0][1] >= 0.70:
                        return results
            except Exception as exc:
                logger.debug("Vector search fallback to lexical: %s", exc)

        # 3. Lexical / Fuzzy scoring fallback via string similarity
        from thefuzz import fuzz

        scored: List[Tuple[str, float]] = []
        for alias, cid in self._alias_map.items():
            ratio = fuzz.token_set_ratio(clean_q, alias) / 100.0
            if ratio >= 0.50:
                scored.append((cid, ratio))

        # Deduplicate by concept_id keeping max score
        best_scores: Dict[str, float] = {}
        for cid, score in scored:
            if cid not in best_scores or score > best_scores[cid]:
                best_scores[cid] = score

        sorted_scored = sorted(best_scores.items(), key=lambda x: -x[1])[:top_k]
        if sorted_scored:
            return sorted_scored

        return results


    def find_shortest_path(self, entity_a: str, entity_b: str, max_depth: int = 3) -> Optional[List[str]]:
        """Resolve shortest topological path between two concepts (Fixing TC-04 bug).

        Executes Cypher shortestPath or BFS over bidirectional graph edges.
        """
        id_a = self._alias_map.get(entity_a.lower(), entity_a)
        id_b = self._alias_map.get(entity_b.lower(), entity_b)

        # 1. Try KùzuDB query if connection exists
        if self.conn is not None:
            try:
                # Directed / undirected 1..3 hop Cypher query
                query = """
                MATCH p = (a:Concept {id: $id_a})-[*1..3]-(b:Concept {id: $id_b})
                RETURN [n IN nodes(p) | n.id] AS path LIMIT 1;
                """
                res = self.conn.execute(query, {"id_a": id_a, "id_b": id_b})
                if res.has_next():
                    row = res.get_next()
                    if row and row[0]:
                        return list(row[0])
            except Exception as exc:
                logger.debug("Kuzu Cypher shortest path error: %s; using BFS fallback", exc)

        # 2. In-memory BFS fallback over concepts_data
        return self._bfs_shortest_path(id_a, id_b, max_depth=max_depth)

    def _bfs_shortest_path(self, start_id: str, end_id: str, max_depth: int = 4) -> Optional[List[str]]:
        """In-memory BFS pathfinder over concept adjacency."""
        if start_id == end_id:
            return [start_id]

        queue = deque([(start_id, [start_id])])
        visited = {start_id}

        while queue:
            curr, path = queue.popleft()
            if len(path) > max_depth:
                continue

            c_info = self.concepts_data.get(curr, {})
            neighbors: Set[str] = set()
            for p in c_info.get("prerequisites", []):
                pid = self._alias_map.get(p.lower(), p)
                neighbors.add(pid)
            for u in c_info.get("unlocks", []):
                uid = self._alias_map.get(u.lower(), u)
                neighbors.add(uid)
            for r in c_info.get("related_to", []) or c_info.get("related", []):
                rid = self._alias_map.get(r.lower(), r)
                neighbors.add(rid)

            for nbr in neighbors:
                if nbr == end_id:
                    return path + [nbr]
                if nbr not in visited and nbr in self.concepts_data:
                    visited.add(nbr)
                    queue.append((nbr, path + [nbr]))

        return None

    def get_upstream_prerequisites(self, anchor_id: str, max_hops: int = 2) -> List[Dict[str, Any]]:
        """Traverse upstream foundational prerequisites along REQUIRES edges (k <= 2)."""
        prereqs: List[Dict[str, Any]] = []

        if self.conn is not None:
            try:
                # Bounded directed Cypher traversal
                query = f"""
                MATCH (c:Concept {{id: $concept_id}})-[:REQUIRES*1..{max_hops}]->(p:Concept)
                RETURN DISTINCT p.id AS id, p.name AS name, p.difficulty AS difficulty, p.summary AS summary
                LIMIT {MAX_PREREQS};
                """
                res = self.conn.execute(query, {"concept_id": anchor_id})
                while res.has_next():
                    row = res.get_next()
                    prereqs.append({
                        "id": row[0],
                        "name": row[1] or row[0],
                        "difficulty": row[2] or "foundational",
                        "summary": row[3] or "",
                    })
                if prereqs:
                    return prereqs
            except Exception as exc:
                logger.debug("Kuzu Cypher upstream traversal notice: %s", exc)

        # Fallback to in-memory graph
        cdata = self.concepts_data.get(anchor_id, {})
        for p in (cdata.get("prerequisites") or [])[:MAX_PREREQS]:
            pid = self._alias_map.get(p.lower(), p)
            p_info = self.concepts_data.get(pid, {})
            prereqs.append({
                "id": pid,
                "name": p_info.get("name") or p_info.get("label") or p,
                "difficulty": p_info.get("difficulty", "foundational"),
                "summary": p_info.get("summary", ""),
            })
        return prereqs

    def get_downstream_unlocks(self, anchor_id: str, max_hops: int = 2) -> List[Dict[str, Any]]:
        """Traverse downstream application concepts along UNLOCKS edges (k <= 2)."""
        unlocks: List[Dict[str, Any]] = []

        if self.conn is not None:
            try:
                # Bounded directed Cypher traversal
                query = f"""
                MATCH (c:Concept {{id: $concept_id}})-[:UNLOCKS*1..{max_hops}]->(u:Concept)
                RETURN DISTINCT u.id AS id, u.name AS name, u.difficulty AS difficulty, u.summary AS summary
                LIMIT {MAX_UNLOCKS};
                """
                res = self.conn.execute(query, {"concept_id": anchor_id})
                while res.has_next():
                    row = res.get_next()
                    unlocks.append({
                        "id": row[0],
                        "name": row[1] or row[0],
                        "difficulty": row[2] or "intermediate",
                        "summary": row[3] or "",
                    })
                if unlocks:
                    return unlocks
            except Exception as exc:
                logger.debug("Kuzu Cypher downstream traversal notice: %s", exc)

        # Fallback to in-memory graph
        cdata = self.concepts_data.get(anchor_id, {})
        for u in (cdata.get("unlocks") or [])[:MAX_UNLOCKS]:
            uid = self._alias_map.get(u.lower(), u)
            u_info = self.concepts_data.get(uid, {})
            unlocks.append({
                "id": uid,
                "name": u_info.get("name") or u_info.get("label") or u,
                "difficulty": u_info.get("difficulty", "intermediate"),
                "summary": u_info.get("summary", ""),
            })
        return unlocks

    def get_evidence_chunks(self, anchor_id: str, max_chunks: int = MAX_CHUNKS) -> List[Dict[str, Any]]:
        """Retrieve verified raw PDF text passages with strict #page=N lineage."""
        chunks: List[Dict[str, Any]] = []

        if self.conn is not None:
            try:
                query = f"""
                MATCH (d:Document)-[:HAS_CHUNK]->(ch:Chunk)-[:MENTIONS]->(c:Concept {{id: $concept_id}})
                RETURN d.id AS doc_id, d.title AS doc_title, ch.chunk_id AS chunk_id,
                       ch.page_number AS page_number, ch.section_title AS section_title,
                       ch.text_passage AS text_passage
                LIMIT {max_chunks};
                """
                res = self.conn.execute(query, {"concept_id": anchor_id})
                while res.has_next():
                    row = res.get_next()
                    chunks.append({
                        "doc_id": row[0],
                        "doc_title": row[1] or row[0],
                        "chunk_id": row[2] or f"chunk_{len(chunks)+1}",
                        "page_number": int(row[3]) if row[3] is not None else 1,
                        "section_title": row[4] or "",
                        "text_passage": (row[5] or "").strip(),
                    })
                if chunks:
                    return chunks
            except Exception as exc:
                logger.debug("Kuzu Cypher chunk retrieval notice: %s", exc)

        # In-memory source passages fallback
        cdata = self.concepts_data.get(anchor_id, {})
        sources = cdata.get("sources") or []
        for s in sources[:max_chunks]:
            chunks.append({
                "doc_id": s.get("doc_id", "Institutional Repository"),
                "doc_title": s.get("doc_title") or s.get("doc_id", "Library Document"),
                "chunk_id": s.get("chunk_id", f"chunk_{len(chunks)+1}"),
                "page_number": int(s.get("page_number", 1)),
                "section_title": s.get("section_title", ""),
                "text_passage": s.get("text_passage", "").strip(),
            })
        return chunks

    def suggest_topics(self, term: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Fuzzy Concept Discovery & Topic Suggestion Engine (Tier 2).

        Matches ambiguous user prompts to top 3-5 candidate nodes, fetching their
        1-hop requires and unlocks for structured roadmap options.
        """
        from thefuzz import fuzz

        candidates: List[Dict[str, Any]] = []
        qn = term.strip().lower()
        clean_q = _clean_query_tokens(qn)

        scored: List[Tuple[str, float]] = []
        for cid, cdata in self.concepts_data.items():
            name = (cdata.get("name") or cdata.get("label") or cid).strip()
            score = max(
                fuzz.token_set_ratio(clean_q, name.lower()) / 100.0,
                fuzz.partial_ratio(clean_q, name.lower()) / 100.0,
            )
            if score >= 0.45:
                scored.append((cid, score))


        scored.sort(key=lambda x: -x[1])
        top_cids = [c[0] for c in scored[:top_k]]

        for cid in top_cids:
            cinfo = self.concepts_data.get(cid, {})
            cname = cinfo.get("name") or cinfo.get("label") or cid
            prereqs = self.get_upstream_prerequisites(cid, max_hops=1)
            unlocks = self.get_downstream_unlocks(cid, max_hops=1)
            candidates.append({
                "id": cid,
                "name": cname,
                "difficulty": cinfo.get("difficulty", "intermediate"),
                "summary": cinfo.get("summary", ""),
                "prerequisites": [p["name"] for p in prereqs[:3]],
                "unlocks": [u["name"] for u in unlocks[:3]],
            })

        return candidates
