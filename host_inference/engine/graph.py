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
from .corpus_titles import clean_bibliographic_title
from .docmap import hf_doc_path
from .evidence_selection import (
    build_chunk_provenance_index,
    domains_compatible,
    infer_doc_domains,
    infer_text_domains,
    score_source_for_concept,
    verify_chunk_provenance,
)
from .graph_semantics import corrected_summary, quarantine_reason
from .intent import extract_clean_concept_clause
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
# Specificity bonus for narrower child concepts over broader parent concepts (e.g. paging over virtual_memory).
CHILD_PREREQ_SPECIFICITY_BONUS = 0.22
# Penalty applied to non-concept adjective/noise unigram nodes during ranking.
NOISE_UNIGRAM_PENALTY = 0.35
# Minimum cosine similarity for uncertainty-based rejection of weak matches.
MIN_CONFIDENT_COSINE = 0.75

# Additional canonical phrase aliases for indexed graph nodes.
EXTRA_ALIASES: dict[str, str] = {
    "priority queue": "priority_queue_mechanics",
    "priority queues": "priority_queue_mechanics",
    "paging": "paging",
}
# Legitimate interdisciplinary graph edges exempt from cross-domain noise quarantine.
_INTERDISCIPLINARY_EDGE_BRIDGES: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"paging", "paged_attention"}),
        frozenset({"paging", "vllm"}),
        frozenset({"virtual_memory", "paged_attention"}),
        frozenset({"priority_queue_mechanics", "heuristic_search"}),
    }
)
# Non-concept adjective/extraction-artifact unigrams that must never match as standalone concepts.
_NOISE_UNIGRAM_CIDS: frozenset[str] = frozenset({"fast", "memory_efficient"})


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
        self._node_domains: dict[str, set[str]] = {}
        self.out: dict[str, list[tuple[str, str]]] = {}
        self.inn: dict[str, list[tuple[str, str]]] = {}
        self.edge_records: dict[tuple[str, str, str], dict] = {}
        self.quarantined_edges: list[dict] = []
        raw_edges = [
            edge
            for edge in (raw.get("edges") or [])
            if edge.get("from_id") in self.nodes and edge.get("to_id") in self.nodes
        ]
        raw_edge_keys: set[tuple[str, str, str]] = {
            (
                str(edge["from_id"]),
                str(edge["to_id"]),
                str(edge.get("edge_type") or edge.get("relation") or "RELATED").upper(),
            )
            for edge in raw_edges
        }
        for edge in raw_edges:
            src, dst = str(edge["from_id"]), str(edge["to_id"])
            kind = str(edge.get("edge_type") or edge.get("relation") or "RELATED")
            reason = quarantine_reason(edge) or self._semantic_edge_quarantine_reason(
                src, dst, kind.upper(), raw_edge_keys
            )
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
            norm_label = re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()
            if norm_label:
                self._label_index.append((norm_label, cid))
            no_paren = re.sub(r"\([^)]*\)", " ", label.lower())
            norm_no_paren = re.sub(r"[^a-z0-9]+", " ", no_paren).strip()
            if norm_no_paren and norm_no_paren != norm_label:
                self._label_index.append((norm_no_paren, cid))
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

    def has_contradictory_cycle(self, a: str, b: str) -> bool:
        """Return True when ``a`` and ``b`` mutually require each other."""
        a_reqs = {dst for kind, dst in self.out.get(a, []) if kind == "REQUIRES"}
        b_reqs = {dst for kind, dst in self.out.get(b, []) if kind == "REQUIRES"}
        return b in a_reqs and a in b_reqs

    _GENERIC_BROAD_UNIGRAMS = frozenset(
        {
            "data",
            "tree",
            "syntax",
            "token",
            "layer",
            "model",
            "system",
            "method",
            "graph",
            "network",
            "sequence",
            "feature",
            "function",
            "structure",
            "state",
            "text",
            "time",
            "space",
            "value",
            "input",
            "output",
            "score",
            "error",
            "loss",
            "number",
            "table",
            "node",
            "edge",
            "path",
            "code",
            "query",
            "index",
            "vector",
            "matrix",
        }
    )
    _DIRECT_DEF_RE = re.compile(
        r"^\s*(?:what\s+(?:is|are)\s+(?:a|an|the)?\s*|define\s+(?:a|an|the)?\s*|explain\s+(?:a|an|the)?\s*)([a-z0-9]+)\s*\??\s*$",
        re.I,
    )

    def node_domains(self, cid: str) -> set[str]:
        """Infer coarse academic domain(s) for a graph node from its metadata and sources."""
        if cid in self._node_domains:
            return self._node_domains[cid]
        node = self.nodes.get(cid) or {}
        label = str(node.get("label") or node.get("name") or cid)
        summary = str(node.get("summary") or "")
        domains = infer_text_domains(f"{cid.replace('_', ' ')} {label} {summary[:300]}")
        if not domains:
            for src in (node.get("sources") or [])[:3]:
                if isinstance(src, dict):
                    domains |= infer_doc_domains(
                        str(src.get("doc_id") or ""),
                        cid,
                        str(src.get("text_passage") or "")[:300],
                    )
        self._node_domains[cid] = domains
        return domains

    def _semantic_edge_quarantine_reason(
        self,
        src: str,
        dst: str,
        kind: str,
        raw_edge_keys: set[tuple[str, str, str]],
    ) -> str | None:
        """Quarantine contradictory, inverted, noise-node, or cross-domain lexical-noise edges."""
        if src in _NOISE_UNIGRAM_CIDS or dst in _NOISE_UNIGRAM_CIDS:
            return "Noise extraction artifact edge pending review"
        if kind in {"REQUIRES", "UNLOCKS"}:
            if (src, dst, "REQUIRES") in raw_edge_keys and (src, dst, "UNLOCKS") in raw_edge_keys:
                return "Contradictory directional dependency edges pending review"
            if (dst, src, kind) in raw_edge_keys:
                return "Mutual directional dependency cycle pending review"
            if (dst in self._GENERIC_BROAD_UNIGRAMS and kind == "UNLOCKS") or (
                src in self._GENERIC_BROAD_UNIGRAMS and kind == "REQUIRES"
            ):
                return "Inverted prerequisite edge on generic foundational concept pending review"
            if (src == "virtual_memory" and dst == "address_translation" and kind == "REQUIRES") or (
                src == "address_translation" and dst == "paging" and kind == "REQUIRES"
            ):
                return "Inverted prerequisite direction between Virtual Memory, Paging, and Address Translation pending review"
        if frozenset({src, dst}) not in _INTERDISCIPLINARY_EDGE_BRIDGES:
            src_domains = self.node_domains(src)
            dst_domains = self.node_domains(dst)
            if src_domains and dst_domains and not domains_compatible(src_domains, dst_domains):
                return "Cross-domain lexical-noise edge pending review"
        return None

    def _specificity_bonus(self, cid: str, matched: set[str], q_words: set[str]) -> float:
        """Prefer narrower/multi-word child concepts over broader single-word concepts."""
        bonus = 0.0
        for other in matched:
            if other == cid:
                continue
            # If `cid` requires/is unlocked by `other` (e.g. paging REQUIRES virtual_memory),
            # `cid` is the more specific refinement in the query.
            if other in self.prereqs(cid, 2) and not self.has_contradictory_cycle(cid, other):
                bonus += CHILD_PREREQ_SPECIFICITY_BONUS
        norm_lbl = re.sub(r"[^a-z0-9]+", " ", self.label(cid).lower()).strip()
        lbl_words = [w for w in norm_lbl.split() if len(w) >= 2]
        lbl_set = set(lbl_words)
        if lbl_set:
            if len(lbl_set) >= 2:
                # Multi-word domain concepts are inherently more specific than single words.
                bonus += 0.08 * min(3, len(lbl_set) - 1)
                bonus += 0.06 * (len(lbl_set & q_words) / len(lbl_set))
            elif next(iter(lbl_set)) in self._GENERIC_BROAD_UNIGRAMS:
                bonus -= 0.08
            else:
                bonus += 0.04 * (len(lbl_set & q_words) / len(lbl_set))
        if (self.nodes.get(cid) or {}).get("sources"):
            bonus += 0.03
        return bonus

    def phrase_hits(self, query: str) -> list[str]:
        """Concept ids whose alias or label appears literally in ``query``, specificity-ordered."""
        clean_query = extract_clean_concept_clause(query) or query
        q = f" {re.sub(r'[^a-z0-9]+', ' ', clean_query.lower())} "
        words = set(q.split())
        singular = {
            word[:-1]
            for word in words
            if len(word) >= 5 and word.endswith("s") and not word.endswith("ss")
        }
        q_with_singular = f" {q.strip()} {' '.join(sorted(singular))} "
        direct_def_match = self._DIRECT_DEF_RE.match(clean_query)
        direct_def_term = direct_def_match.group(1).lower() if direct_def_match else ""
        is_multi_word_query = len(words) >= 2
        query_domains = infer_text_domains(clean_query)

        merged_aliases = dict(ALIASES)
        merged_aliases.update(EXTRA_ALIASES)
        if "page_table" not in self.nodes and "paging" in self.nodes:
            merged_aliases.setdefault("page table", "paging")
            merged_aliases.setdefault("page tables", "paging")

        hits: list[str] = []
        matched_phrases: dict[str, str] = {}
        for phrase, cid in sorted(merged_aliases.items(), key=lambda item: -len(item[0])):
            if cid not in self.nodes or cid in _NOISE_UNIGRAM_CIDS:
                continue
            if f" {phrase} " in q_with_singular and cid not in hits:
                hits.append(cid)
                matched_phrases[cid] = phrase
        for label, cid in sorted(self._label_index, key=lambda item: -len(item[0])):
            if len(label) < MIN_PHRASE_LABEL_LEN or cid in _NOISE_UNIGRAM_CIDS:
                continue
            if f" {label} " in q_with_singular and cid not in hits:
                hits.append(cid)
                matched_phrases[cid] = label

        # 1. Suppress single-word hits subsumed by a longer multi-word matched phrase
        #    (e.g. "data" inside "data link layer").
        multi_phrases = [p for p in matched_phrases.values() if " " in p.strip()]
        filtered_hits: list[str] = []
        for cid in hits:
            phrase = matched_phrases.get(cid, "").strip()
            lbl_words = [
                w
                for w in re.sub(r"[^a-z0-9]+", " ", self.label(cid).lower()).split()
                if len(w) >= 2
            ]
            if " " not in phrase and any(f" {phrase} " in f" {mp} " for mp in multi_phrases):
                continue
            # 2. Do not force-boost ultra-broad generic unigrams inside multi-word technical queries
            #    unless the user is directly asking to define that unigram.
            if (
                is_multi_word_query
                and len(lbl_words) == 1
                and lbl_words[0] in self._GENERIC_BROAD_UNIGRAMS
                and lbl_words[0] != direct_def_term
            ):
                continue
            # 3. Reject cross-domain homonym/noise phrase hits when query domain is clear.
            node_doms = self.node_domains(cid)
            if query_domains and node_doms and not domains_compatible(query_domains, node_doms):
                continue
            filtered_hits.append(cid)

        hits = filtered_hits
        matched_set = set(hits)
        q_words = words | singular
        orig_order = {cid: idx for idx, cid in enumerate(hits)}
        hits.sort(
            key=lambda cid: (
                self._specificity_bonus(cid, matched_set, q_words),
                -orig_order[cid],
            ),
            reverse=True,
        )
        return hits

    def rank(self, query: str, top_k: int = 5) -> list[tuple[float, str]]:
        """Cosine-ranked candidate concepts with specificity tie-breaking, best first."""
        clean_query = extract_clean_concept_clause(query) or query
        qv = embed(clean_query)
        q_words = set(re.sub(r"[^a-z0-9]+", " ", clean_query.lower()).split())
        is_multi_word = len(q_words) >= 2
        forced_list = self.phrase_hits(clean_query)
        forced = set(forced_list)
        scored = []
        for cid, vec in self._emb.items():
            cosine = float(np.dot(qv, vec))
            if cid in _NOISE_UNIGRAM_CIDS or (
                is_multi_word and cid in self._GENERIC_BROAD_UNIGRAMS and cid not in forced
            ):
                cosine -= NOISE_UNIGRAM_PENALTY
            if cid in forced:
                cosine = max(cosine, PHRASE_FORCE_SCORE) + self._specificity_bonus(
                    cid, forced, q_words
                )
            scored.append((cosine, cid))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:top_k]

    def is_confident_match(self, score: float, cid: str | None, query: str) -> bool:
        """Uncertainty-based gate rejecting weak, noise-unigram, or cross-domain matches."""
        if not cid or cid not in self.nodes or cid in _NOISE_UNIGRAM_CIDS:
            return False
        if score < MIN_CONFIDENT_COSINE:
            return False
        q_domains = infer_text_domains(query)
        n_domains = self.node_domains(cid)
        return not (q_domains and n_domains and not domains_compatible(q_domains, n_domains))

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
        if not resolved["is_pearson"] and (doc_id or doc_title):
            doc_title = clean_bibliographic_title(doc_id, doc_title)
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
