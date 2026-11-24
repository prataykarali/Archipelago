"""The in-memory concept graph: loading, traversal and citation lookup.

One concern: turning the exported ``okf_graph.json`` into a queryable structure
and answering structural questions about it (prerequisites, unlocks, shortest
dependency path, best supporting source, citation record).
"""

from __future__ import annotations

from collections import deque
from hashlib import sha256
import json
from pathlib import Path
import re

import numpy as np

from .academic_sources import ACADEMIC_SOURCES_BY_ID
from .constants import ALIASES, FORMULAS
from .docmap import hf_doc_path
from .evidence_selection import (
    build_chunk_provenance_index,
    score_source_for_concept,
    verify_chunk_provenance,
)
from .graph_semantics import corrected_summary, quarantine_reason
from .source_resolution import (
    SOURCE_CAT_PEARSON,
    SOURCE_CAT_TOC_INDEX,
    resolve_source_target,
)
from .text import embed
from .withdrawal import best_live_source, withdrawal_notice_for_doc, withdrawn_documents

# How much of a source passage is retained on a citation record.
PASSAGE_CHAR_LIMIT = 700
# Reciprocal-rank bump given to a node whose alias/label literally appears.
PHRASE_FORCE_SCORE = 0.93
# Minimum label length before it is considered for a literal phrase match.
MIN_PHRASE_LABEL_LEN = 4
# A source only outranks another for a later page when it shares query tokens.
SOURCE_OVERLAP_WEIGHT = 10
SOURCE_LATER_PAGE_BONUS = 2


class LibraryGraph:
    """Queryable view over one exported concept graph."""

    def __init__(self, path: Path):
        source_bytes = path.read_bytes()
        raw = json.loads(source_bytes)
        self.graph_version = sha256(source_bytes).hexdigest()[:12]
        self.last_sync = path.stat().st_mtime
        # ``stats.fixture`` is stamped by scripts/build_corpus_fixture.py. Tracked
        # here so /api/readiness can say "this deployment is on the fallback
        # slice" rather than presenting a 59-concept graph as the whole library.
        stats = raw.get("stats") or {}
        self.corpus_source = "fixture" if stats.get("fixture") else "full"
        self.nodes: dict[str, dict] = {}
        for node in raw.get("nodes") or []:
            if node.get("id"):
                self.nodes[node["id"]] = node
        for cid, concept in (raw.get("concepts") or {}).items():
            if cid in self.nodes:
                continue
            merged = dict(concept)
            merged.setdefault("id", cid)
            merged.setdefault("label", merged.get("name") or cid)
            merged.setdefault("name", merged.get("label") or cid)
            self.nodes[cid] = merged
        viz_nodes = (raw.get("visualization") or {}).get("nodes") or []
        sources_by_id = {
            node.get("id"): node.get("sources") or [] for node in viz_nodes if node.get("id")
        }
        for cid, node in self.nodes.items():
            node["summary"] = corrected_summary(cid, str(node.get("summary") or ""))
            if not node.get("sources"):
                if sources_by_id.get(cid):
                    node["sources"] = sources_by_id[cid]
                elif cid in ACADEMIC_SOURCES_BY_ID:
                    node["sources"] = [ACADEMIC_SOURCES_BY_ID[cid]]
        self.out: dict[str, list[tuple[str, str]]] = {}
        self.inn: dict[str, list[tuple[str, str]]] = {}
        self.edge_records: dict[tuple[str, str, str], dict] = {}
        self.quarantined_edges: list[dict] = []
        for edge in raw.get("edges") or []:
            src, dst = edge.get("from_id"), edge.get("to_id")
            kind = edge.get("edge_type") or edge.get("relation") or "RELATED"
            if not src or not dst or src not in self.nodes or dst not in self.nodes:
                continue
            reason = quarantine_reason(edge)
            if reason:
                self.quarantined_edges.append({**edge, "quarantine_reason": reason})
                continue
            self.out.setdefault(src, []).append((kind, dst))
            self.inn.setdefault(dst, []).append((kind, src))
            self.edge_records[(src, dst, kind)] = edge
        self._emb = {cid: embed(self._blob(node)) for cid, node in self.nodes.items()}
        self._chunk_provenance_index = build_chunk_provenance_index(self.nodes)
        self._label_index = []
        for cid, node in self.nodes.items():
            label = (node.get("label") or node.get("name") or cid).strip()
            self._label_index.append((label.lower(), cid))
            self._label_index.append((cid.replace("_", " "), cid))

    def _blob(self, node: dict) -> str:
        label = node.get("label") or node.get("name") or node["id"]
        return f"{label}: {node.get('summary') or ''}"

    def label(self, cid: str) -> str:
        """Human-readable label for ``cid`` (falls back to the id)."""
        node = self.nodes.get(cid) or {}
        return node.get("label") or node.get("name") or cid

    def prereqs(self, cid: str, k: int = 2) -> list[str]:
        """Outgoing REQUIRES plus incoming UNLOCKS (what enables this node)."""
        found = self._walk(cid, k, outgoing=True, kinds={"REQUIRES"})
        for item in self._walk(cid, k, outgoing=False, kinds={"UNLOCKS"}):
            if item not in found:
                found.append(item)
        return found

    def unlocks(self, cid: str, k: int = 2) -> list[str]:
        """Outgoing UNLOCKS plus reverse REQUIRES (what this node enables)."""
        forward = self._walk(cid, k, outgoing=True, kinds={"UNLOCKS"})
        reverse = self._walk(cid, k, outgoing=False, kinds={"REQUIRES"})
        seen = []
        for item in forward + reverse:
            if item not in seen and item != cid:
                seen.append(item)
        return seen

    def related(self, cid: str, limit: int = 6) -> list[str]:
        """RELATED neighbours in either direction, capped at ``limit``."""
        found = []
        for kind, other in self.out.get(cid, []):
            if kind == "RELATED" and other not in found:
                found.append(other)
        for kind, other in self.inn.get(cid, []):
            if kind == "RELATED" and other not in found:
                found.append(other)
        return found[:limit]

    def _walk(self, start: str, k: int, outgoing: bool, kinds: set[str]) -> list[str]:
        table = self.out if outgoing else self.inn
        seen: list[str] = []
        queue = deque([(start, 0)])
        visited = {start}
        while queue:
            cur, dist = queue.popleft()
            if dist == k:
                continue
            for kind, nxt in table.get(cur, []):
                if kind not in kinds or nxt in visited:
                    continue
                visited.add(nxt)
                seen.append(nxt)
                queue.append((nxt, dist + 1))
        return seen

    def shortest(self, a: str, b: str, limit: int = 6) -> list[tuple[str, str]] | None:
        """Bidirectional walk over REQUIRES and UNLOCKS. Returns (relation, node) steps."""
        if a == b:
            return []
        queue = deque([(a, [])])
        visited = {a}
        while queue:
            cur, path = queue.popleft()
            if len(path) >= limit:
                continue
            hops = []
            for kind, nxt in self.out.get(cur, []):
                if kind in {"REQUIRES", "UNLOCKS"}:
                    hops.append((kind, nxt))
            for kind, nxt in self.inn.get(cur, []):
                if kind in {"REQUIRES", "UNLOCKS"}:
                    hops.append((f"inv-{kind}", nxt))
            for kind, nxt in hops:
                if nxt in visited:
                    continue
                step = [*path, (kind, nxt)]
                if nxt == b:
                    return step
                visited.add(nxt)
                queue.append((nxt, step))
        return None

    def phrase_hits(self, query: str) -> list[str]:
        """Concept ids whose alias or label appears literally in ``query``."""
        q = f" {re.sub(r'[^a-z0-9]+', ' ', query.lower())} "
        words = set(q.split())
        singular = {
            word[:-1]
            for word in words
            if len(word) >= 5 and word.endswith("s") and not word.endswith("ss")
        }
        q_with_singular = f" {q.strip()} {' '.join(sorted(singular))} "
        hits = []
        for phrase, cid in sorted(ALIASES.items(), key=lambda item: -len(item[0])):
            if cid not in self.nodes:
                continue
            if f" {phrase} " in q_with_singular and cid not in hits:
                hits.append(cid)
        for label, cid in sorted(self._label_index, key=lambda item: -len(item[0])):
            if len(label) < MIN_PHRASE_LABEL_LEN:
                continue
            if f" {label} " in q_with_singular and cid not in hits:
                hits.append(cid)
        return hits

    def rank(self, query: str, top_k: int = 5) -> list[tuple[float, str]]:
        """Cosine-ranked candidate concepts, best first."""
        qv = embed(query)
        forced = set(self.phrase_hits(query))
        scored = []
        for cid, vec in self._emb.items():
            cosine = float(np.dot(qv, vec))
            if cid in forced:
                cosine = max(cosine, PHRASE_FORCE_SCORE)
            scored.append((cosine, cid))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:top_k]

    def best_source(self, cid: str, query: str = "") -> dict | None:
        """Pick the citable source passage whose text best overlaps the query.

        Documents the lifecycle ledger marks ``withdrawn`` are skipped, so a
        title Pearson or Hugging Face has removed cannot be cited. If every
        passage for this concept came from a withdrawn document, the concept
        simply has no source here (``None``) — the caller then reports the
        title as no longer in records rather than inventing a citation.
        """
        return self.best_live_source(cid, query)[0]

    def best_live_source(self, cid: str, query: str = "") -> tuple[dict | None, bool]:
        """``(best citable source, all_withdrawn)`` for a concept."""
        sources = list((self.nodes.get(cid) or {}).get("sources") or [])
        if not sources:
            return None, False
        label = self.label(cid)
        retired = withdrawn_documents()

        def score(source: dict) -> int:
            total, _overlap = score_source_for_concept(cid, label, source, query)
            return total

        return best_live_source(sources, score, retired)

    def cite_record(
        self, cid: str, query: str = "", index: int = 1, source_override: dict | None = None
    ) -> dict:
        """Build the structured citation record the chat payload carries.

        When every passage behind this concept came from a withdrawn document,
        the record is marked ``withdrawn`` and carries no URL — the chat UI can
        then say the title is no longer in records instead of offering a link
        that will 404.
        """
        retired = withdrawn_documents()
        source, all_withdrawn = self.best_live_source(cid, query or getattr(self, "_query", ""))
        if source_override is not None and source_override in (self.nodes.get(cid) or {}).get(
            "sources", []
        ):
            override_raw_doc = str(source_override.get("doc_id") or "").strip()
            override_canonical_doc = hf_doc_path(override_raw_doc)
            if override_raw_doc not in retired and override_canonical_doc not in retired:
                source, all_withdrawn = source_override, False
        raw_page = (source or {}).get("page_number")
        raw_page_int = int(raw_page) if raw_page and not all_withdrawn else None
        chunk_id = (source or {}).get("chunk_id")
        raw_doc_id = str((source or {}).get("doc_id") or "")
        doc_id = hf_doc_path(raw_doc_id)
        if not doc_id and not all_withdrawn and cid in FORMULAS:
            _formula, filename, _formula_page = FORMULAS[cid]
            doc_id = f"papers/{filename}"
        raw_title = str((source or {}).get("title") or "").strip()
        resolved = resolve_source_target(
            raw_doc_id=raw_doc_id,
            canonical_doc_id=doc_id,
            page_number=raw_page_int if source else None,
            title=raw_title,
            all_withdrawn=bool(all_withdrawn),
        )
        source_category = str(resolved["source_category"])
        source_type = str(resolved["source_type"])
        reader_resolvable = bool(resolved["reader_resolvable"])
        page = resolved["page_number"]
        hf_url = str(resolved["url"] or "") if source else ""
        name = resolved["resolved_title"] or (doc_id.split("/")[-1] if doc_id else "")

        if not name or all_withdrawn:
            label = ""
        elif source_category == SOURCE_CAT_PEARSON and hf_url:
            label = f"[S{index}: {name} (Pearson catalogue-only — institutional login)]"
        elif source_category == SOURCE_CAT_TOC_INDEX:
            label = f"[S{index}: {name} (TOC/index metadata only)]"
        elif hf_url:
            label = f"[S{index}: {name}{f', #page={page}' if page else ''}]"
        else:
            label = f"[S{index}: {name} (source unavailable — metadata only)]"

        doc_title = resolved["resolved_title"] or raw_title
        authors = (source or {}).get("authors") or ""
        if "FlashAttention" in doc_id or "upload_cb7badb2" in raw_doc_id:
            if not doc_title:
                doc_title = (
                    "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness"
                )
            if not authors:
                authors = "Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, Christopher Ré"
        passage_text = ((source or {}).get("text_passage") or "")[:PASSAGE_CHAR_LIMIT]
        provenance = verify_chunk_provenance(
            raw_doc_id=raw_doc_id,
            canonical_doc_id=doc_id,
            chunk_id=chunk_id,
            page_number=page,
            hf_url=hf_url,
            text_passage=passage_text,
            all_withdrawn=bool(all_withdrawn),
            chunk_index=self._chunk_provenance_index,
            source_category=source_category,
            reader_resolvable=reader_resolvable,
        )
        return {
            "label": label,
            "evidence_id": f"S{index}",
            "source_type": source_type,
            "source_category": source_category,
            "reader_resolvable": reader_resolvable,
            "page_verified": bool(resolved["page_verified"]),
            "is_pearson": bool(resolved["is_pearson"]),
            "book_id": str(resolved["book_id"] or ""),
            "book_type": str(resolved["book_type"] or ""),
            "hf_path": str(resolved["hf_path"] or ""),
            "concept_id": cid,
            "doc_id": doc_id,
            "chunk_id": chunk_id,
            "canonical_passage_id": provenance["canonical_passage_id"],
            "provenance_status": provenance["provenance_status"],
            "chunk_provenance_match": provenance["chunk_provenance_match"],
            "claim_support_status": provenance["claim_support_status"],
            "doc_title": doc_title,
            "authors": authors,
            "page_number": page,
            "printed_page": (source or {}).get("printed_page"),
            "pdf_url": hf_url,
            "url": hf_url,
            "withdrawn": bool(all_withdrawn),
            "notice": withdrawal_notice_for_doc(doc_id) if all_withdrawn else "",
            "text_passage": passage_text,
            "passage": passage_text,
            "section": (source or {}).get("section") or (source or {}).get("section_title"),
            "doi": (source or {}).get("doi"),
            "publication_year": (source or {}).get("publication_year"),
            "source_provider": (source or {}).get("source_provider"),
            "retrieved_at": (source or {}).get("retrieved_at"),
            "verification_status": provenance["verification_status"],
            "status_level": provenance["status_level"],
            "access_status": str(resolved["access_status"]),
        }

    def citation(self, cid: str, index: int = 1) -> str:
        """Short ``[S#: file, #page=N]`` label for inline prose."""
        return self.cite_record(cid, getattr(self, "_query", ""), index)["label"]

    def formula(self, cid: str) -> str:
        """Rendered formula plus citation, or an empty string when none exists."""
        if cid not in FORMULAS:
            return ""
        formula, _filename, _page = FORMULAS[cid]
        return f"{formula} {self.citation(cid)}"
