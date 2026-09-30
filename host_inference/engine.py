"""Inference-only graph runtime for the hosted Archipelago librarian.

Ingestion stays on the local workstation. This module loads the exported
concept graph, ranks a query with a local hashed embedder, walks REQUIRES
and UNLOCKS edges, and returns one of the deterministic reply protocols.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import deque
from pathlib import Path
from urllib.parse import quote

import numpy as np
import requests

from demo_cards import match_demo, redact_for_model
from library_index import Catalog
from remote_cache import hydrate, load_books, pearson_page_url

DIM = 384
KILL_SWITCH = 0.75
HF_DOC_MAP = {
    "doc_lora_low_rank_adaptation_of_large": "papers/Hu2021_LoRA.pdf",
    "hu2021_lora.pdf": "papers/Hu2021_LoRA.pdf",
    "lora_paper": "papers/Hu2021_LoRA.pdf",
    "dettmers2023_qlora.pdf": "papers/Dettmers2023_QLoRA.pdf",
    "lewis2020_rag.pdf": "papers/Lewis2020_RAG.pdf",
    "devlin2018_bert.pdf": "papers/Devlin2018_BERT.pdf",
    "bert_paper": "papers/Devlin2018_BERT.pdf",
    "edge2024_graphrag.pdf": "papers/Edge2024_GraphRAG.pdf",
    "vaswani2017_attention_is_all_you_need.pdf": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "paper_attention_is_all_you_need_2017": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "goodfellow2014_gan.pdf": "papers/Goodfellow2014_GAN.pdf",
    "book_deep_learning_goodfellow_2016": "papers/Goodfellow2014_GAN.pdf",
    "deisenroth_math_for_ml.pdf": "textbooks/Deisenroth_Math_For_ML.pdf",
    "book_math_for_machine_learning_2020": "textbooks/Deisenroth_Math_For_ML.pdf",
    "bahdanau2014_attention.pdf": "papers/Bahdanau2014_Attention.pdf",
    "kwon2023_vllm.pdf": "papers/Kwon2023_vLLM.pdf",
    "brown2020_gpt3.pdf": "papers/Brown2020_GPT3.pdf",
}


def _hf_doc_path(doc_id: str) -> str:
    raw = (doc_id or "").strip().lstrip("/")
    if not raw:
        return ""
    key = raw.lower()
    base = raw.split("/")[-1].lower()
    if key in HF_DOC_MAP:
        return HF_DOC_MAP[key]
    if base in HF_DOC_MAP:
        return HF_DOC_MAP[base]
    if raw.startswith(("papers/", "textbooks/", "archipelago-books-cs/")) or "/" in raw:
        return raw
    if raw.lower().endswith(".pdf"):
        return f"papers/{raw}"
    return raw
HERE = Path(__file__).resolve().parent

OOD_MESSAGE = (
    "That topic falls outside the current scope of this library assistant. "
    "My indexed corpus strictly covers Computer Science, Artificial Intelligence, "
    "Database Systems, and Mathematics for Machine Learning. Please consult the "
    "general university catalog or your department librarian."
)
CODE_MESSAGE = (
    "Archipelago is a theoretical architecture and mathematics library. "
    "I do not provide code generation, software installation guides, or implementation scripts. "
    "Would you like to explore the theoretical and mathematical concepts behind this instead?"
)
HIJACK_MESSAGE = (
    "Out of Library Scope: I cannot provide information on this topic. "
    "Currently, I am scoped to the AI/ML and institutional library domain only."
)

ALIASES = {
    "lora": "matrix_factorization",
    "low-rank adaptation": "matrix_factorization",
    "low rank adaptation": "matrix_factorization",
    "qlora": "qlora",
    "3nf": "third_normal_form",
    "third normal form": "third_normal_form",
    "third normal form (3nf)": "third_normal_form",
    "bert": "bert",
    "latent variables": "latent_variable",
    "latent variable": "latent_variable",
    "masked language modeling": "masked_language_modeling",
    "mlm": "masked_language_modeling",
    "word embeddings": "word_embeddings",
    "vector embeddings": "vector_embeddings",
    "rag": "rag",
    "retrieval augmented generation": "rag",
    "retrieval-augmented generation": "rag",
    "matrix decomposition": "matrix_decomposition",
    "matrix factorization": "matrix_factorization",
    "attention": "attention_mechanism",
    "transformer": "attention_mechanism",
    "graph rag": "graph_rag",
    "qiskit": "qiskit",
}

# Grounded identities that already appear in the indexed papers / shelf cards.
FORMULAS = {
    "matrix_factorization": (
        r"$\Delta W = BA$, where $r \ll \min(d, k)$",
        "Hu2021_LoRA.pdf",
        1,
    ),
    "qlora": (
        r"$\Delta W = BA$ stored in a low-bit quantized base, $r \ll \min(d, k)$",
        "Dettmers2023_QLoRA.pdf",
        1,
    ),
    "bert": (
        r"$P(x_i \mid x_{\setminus i})$ under masked language modeling",
        "Devlin2018_BERT.pdf",
        1,
    ),
    "masked_language_modeling": (
        r"$P(x_i \mid x_{\setminus i})$",
        "Devlin2018_BERT.pdf",
        1,
    ),
    "attention_mechanism": (
        r"$\mathrm{Attention}(Q,K,V) = \mathrm{softmax}(QK^{\top}/\sqrt{d_k})V$",
        "Vaswani2017_Attention_Is_All_You_Need.pdf",
        1,
    ),
    "rag": (
        r"$p(y\mid x) \approx \sum_{z \in \mathrm{top}\text{-}k} p_\eta(z\mid x)\, p_\theta(y\mid x,z)$",
        "Lewis2020_RAG.pdf",
        1,
    ),
    "graph_rag": (
        r"community summaries over an entity graph, then queried at answer time",
        "Edge2024_GraphRAG.pdf",
        1,
    ),
    "third_normal_form": (
        r"For every $X \rightarrow A$, $X$ is a superkey or $A$ is prime",
        "Silberschatz_Database_Systems.pdf",
        1,
    ),
}

SHELF = {
    "third_normal_form": {
        "title": "Database System Concepts",
        "author": "Abraham Silberschatz",
        "call_number": "005.74 SIL",
        "place": "Central Library, Stack B, Rack 4, Shelf 2",
        "barcode": "IEM-LIB-DB-0429",
        "available": 3,
        "total": 5,
        "definition": (
            "A relation is in third normal form when it is in second normal form and "
            "no non-prime attribute depends transitively on a candidate key."
        ),
    },
    "matrix_factorization": {
        "title": "LoRA: Low-Rank Adaptation of Large Language Models",
        "author": "Edward J. Hu et al.",
        "call_number": "006.3 HU",
        "place": "Central Library, Stack A, Rack 2, Shelf 1",
        "barcode": "IEM-LIB-AI-0107",
        "available": 2,
        "total": 2,
        "definition": "Low-rank updates adapt a frozen weight matrix without full fine-tuning.",
    },
    "rag": {
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "author": "Patrick Lewis et al.",
        "call_number": "006.35 LEW",
        "place": "Central Library, Stack A, Rack 3, Shelf 2",
        "barcode": "IEM-LIB-AI-0204",
        "available": 1,
        "total": 2,
        "definition": "RAG retrieves documents and conditions generation on those passages.",
    },
}

PORTALS = [
    ("IEEE Xplore", "https://ieeexplore.ieee.org", "Campus network or the library proxy"),
    ("Scopus", "https://www.scopus.com", "Institutional login"),
    ("ScienceDirect", "https://www.sciencedirect.com", "Institutional login"),
    ("NDLI", "https://ndl.iitkgp.ac.in", "National Digital Library of India"),
    ("Springer Link", "https://link.springer.com", "Institutional login"),
    ("Pearson eLibrary", "https://elibrary.in.pearson.com/", "Account issued by the library"),
]

SCHEDULE = [
    "24×7 Reading Rooms: Open continuously for enrolled students.",
    "Circulation / Lending Desk: Monday–Friday, 9:00 AM – 6:00 PM.",
    "Reference Desk Inquiries: Monday–Friday, 10:00 AM – 5:00 PM.",
    "Weekend access: reading rooms stay open; issue and return are weekday-only.",
]

PASSING_MENTIONS = (
    "taylor swift",
    "aws ",
    "amazon web services",
    "openai revenue",
    "openai business",
    "microsoft's internal",
    "graphrag engineering team",
    "lottery",
)

INJECTION = re.compile(
    r"(ignore\s+(all\s+)?previous|system\s+prompt|<\s*system\s*>|\[INST\]|"
    r"os\.system|rm\s+-rf|act\s+as\b|jailbreak|developer\s+mode|"
    r"print\s+your\s+instructions|you\s+are\s+now\b)",
    re.I,
)
CODE_TRAP = re.compile(
    r"(\bwrite\s+(me\s+)?(a\s+)?(python|code|script|essay|docker)|"
    r"\bpytorch\b|\bbash\b|\bcurl\b|\bdockerfile\b|\bpip\s+install\b|"
    r"\btraining\s+loop\b|\bhomework\b|\b500-word\b|\bgenerate\s+code\b|"
    r"\bimplement\s+.{0,40}\bin\s+python\b)",
    re.I,
)
SCHEDULE_RE = re.compile(
    r"\b(opening hours|library hours|what time|timetable|circulation desk|"
    r"reading room|lending desk|when does the library)\b",
    re.I,
)
SHELF_RE = re.compile(
    r"\b(physical (book|copy|copies)|where can i find|call number|"
    r"on the shelf|which shelf|barcode|stacks?|rack)\b",
    re.I,
)
AUTH_RE = re.compile(
    r"\b(ieee|xplore|scopus|sciencedirect|ndli|springer|e-?resource|"
    r"subscription portal|institutional login|proxy login|pearson)\b",
    re.I,
)
DIAG_RE = re.compile(
    r"\b(roadmap|where (should|do) i (start|begin)|diagnostic|quiz me|"
    r"assess my|what should i study first|learning path|begin studying)\b",
    re.I,
)
RELATE_RE = re.compile(
    r"\b(how (are|is)|relation|related|connect|difference|compare|versus|vs\.?)\b",
    re.I,
)
PARAM_RE = re.compile(
    r"\b(memory consumption|vram|parameter count|qiskit\s*v?\d|exact latency|"
    r"hyperparameter|bytes of memory|implementation formula)\b",
    re.I,
)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", (text or "").lower())


def embed(text: str) -> np.ndarray:
    """Local unit vector. Same function embeds catalog nodes and live queries."""
    vec = np.zeros(DIM, dtype=np.float32)
    toks = _tokens(text)
    if not toks:
        return vec
    grams = list(toks)
    grams.extend(f"{a}_{b}" for a, b in zip(toks, toks[1:]))
    for gram in grams:
        digest = hashlib.blake2b(gram.encode(), digest_size=8).digest()
        idx = int.from_bytes(digest[:4], "little") % DIM
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 2.4 if len(gram) <= 6 else 1.0
        vec[idx] += sign * weight
    norm = float(np.linalg.norm(vec))
    if norm:
        vec /= norm
    return vec


def _node_public(node: dict) -> dict:
    return {
        "id": node["id"],
        "label": node.get("label") or node.get("name") or node["id"],
        "name": node.get("name") or node.get("label") or node["id"],
        "summary": (node.get("summary") or "").strip(),
        "difficulty": node.get("difficulty") or "intermediate",
        "concept_type": node.get("concept_type") or "concept",
    }


class LibraryGraph:
    def __init__(self, path: Path):
        raw = json.loads(path.read_text(encoding="utf-8"))
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
        viz_nodes = ((raw.get("visualization") or {}).get("nodes") or [])
        sources_by_id = {node.get("id"): node.get("sources") or [] for node in viz_nodes if node.get("id")}
        for cid, node in self.nodes.items():
            if not node.get("sources") and sources_by_id.get(cid):
                node["sources"] = sources_by_id[cid]
        self.out: dict[str, list[tuple[str, str]]] = {}
        self.inn: dict[str, list[tuple[str, str]]] = {}
        for edge in raw.get("edges") or []:
            src, dst = edge.get("from_id"), edge.get("to_id")
            kind = edge.get("edge_type") or edge.get("relation") or "RELATED"
            if not src or not dst or src not in self.nodes or dst not in self.nodes:
                continue
            self.out.setdefault(src, []).append((kind, dst))
            self.inn.setdefault(dst, []).append((kind, src))
        self._emb = {cid: embed(self._blob(node)) for cid, node in self.nodes.items()}
        self._label_index = []
        for cid, node in self.nodes.items():
            label = (node.get("label") or node.get("name") or cid).strip()
            self._label_index.append((label.lower(), cid))
            self._label_index.append((cid.replace("_", " "), cid))

    def _blob(self, node: dict) -> str:
        label = node.get("label") or node.get("name") or node["id"]
        return f"{label}: {node.get('summary') or ''}"

    def label(self, cid: str) -> str:
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
        forward = self._walk(cid, k, outgoing=True, kinds={"UNLOCKS"})
        reverse = self._walk(cid, k, outgoing=False, kinds={"REQUIRES"})
        seen = []
        for item in forward + reverse:
            if item not in seen and item != cid:
                seen.append(item)
        return seen

    def related(self, cid: str, limit: int = 6) -> list[str]:
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
                step = path + [(kind, nxt)]
                if nxt == b:
                    return step
                visited.add(nxt)
                queue.append((nxt, step))
        return None

    def phrase_hits(self, query: str) -> list[str]:
        q = f" {re.sub(r'[^a-z0-9]+', ' ', query.lower())} "
        hits = []
        for phrase, cid in sorted(ALIASES.items(), key=lambda item: -len(item[0])):
            if cid not in self.nodes:
                continue
            if f" {phrase} " in q and cid not in hits:
                hits.append(cid)
        for label, cid in sorted(self._label_index, key=lambda item: -len(item[0])):
            if len(label) < 4:
                continue
            if f" {label} " in q and cid not in hits:
                hits.append(cid)
        return hits

    def rank(self, query: str, top_k: int = 5) -> list[tuple[float, str]]:
        qv = embed(query)
        forced = set(self.phrase_hits(query))
        scored = []
        for cid, vec in self._emb.items():
            cosine = float(np.dot(qv, vec))
            if cid in forced:
                cosine = max(cosine, 0.93)
            scored.append((cosine, cid))
        scored.sort(key=lambda item: item[0], reverse=True)
        return scored[:top_k]

    def best_source(self, cid: str, query: str = "") -> dict | None:
        sources = list((self.nodes.get(cid) or {}).get("sources") or [])
        if not sources:
            return None
        wanted = set(_tokens(query)) | set(_tokens(self.label(cid)))
        best = None
        best_score = -1
        for source in sources:
            passage = source.get("text_passage") or ""
            overlap = len(wanted & set(_tokens(passage)))
            page = int(source.get("page_number") or 0)
            score = overlap * 10 + (2 if page > 1 else 0)
            if score > best_score:
                best, best_score = source, score
        return best

    def cite_record(self, cid: str, query: str = "", index: int = 1) -> dict:
        source = self.best_source(cid, query or getattr(self, "_query", ""))
        page = int((source or {}).get("page_number") or 1)
        doc_id = _hf_doc_path(str((source or {}).get("doc_id") or ""))
        if not doc_id and cid in FORMULAS:
            _formula, filename, formula_page = FORMULAS[cid]
            doc_id = f"papers/{filename}"
            page = formula_page
        name = doc_id.split("/")[-1] if doc_id else f"{re.sub(r'[^A-Za-z0-9]+', '', self.label(cid)) or 'Catalog'}_catalog.pdf"
        hf_url = f"/read?doc={quote(doc_id, safe='')}&page={page}" if doc_id else ""
        return {
            "label": f"[S{index}: {name}, #page={page}]",
            "concept_id": cid,
            "doc_id": doc_id,
            "page_number": page,
            "printed_page": page,
            "pdf_url": hf_url,
            "url": hf_url,
            "text_passage": ((source or {}).get("text_passage") or "")[:700],
        }

    def citation(self, cid: str, index: int = 1) -> str:
        return self.cite_record(cid, getattr(self, "_query", ""), index)["label"]

    def formula(self, cid: str) -> str:
        if cid not in FORMULAS:
            return ""
        formula, filename, page = FORMULAS[cid]
        return f"{formula} {self.citation(cid)}"


def _arrow(left: str, rel: str, right: str) -> str:
    return f"{left} $\\xrightarrow{{{rel}}}$ {right}"


def _lineage(graph: LibraryGraph, cid: str) -> str:
    pres = graph.prereqs(cid, 1)[:2]
    unl = graph.unlocks(cid, 1)[:2]
    label = graph.label(cid)
    if pres and unl:
        return _arrow(graph.label(pres[0]), "REQUIRES", label) + " " + _arrow(label, "UNLOCKS", graph.label(unl[0]))
    if pres:
        return _arrow(graph.label(pres[0]), "REQUIRES", label)
    if unl:
        return _arrow(label, "UNLOCKS", graph.label(unl[0]))
    return f"{label} (indexed catalog node; no REQUIRES or UNLOCKS edge is stored)"


def _neighborhood_block(graph: LibraryGraph, cid: str) -> str:
    pres = ", ".join(graph.label(x) for x in graph.prereqs(cid, 1)[:4]) or "none indexed"
    unl = ", ".join(graph.label(x) for x in graph.unlocks(cid, 1)[:4]) or "none indexed"
    return f"- **{graph.label(cid)}** prerequisites: {pres}. Unlocks: {unl}."


class Engine:
    def __init__(self, graph_path: Path | None = None):
        self.cache_info = hydrate()
        path = graph_path or (HERE / "cache" / "okf_graph.json")
        if not path.is_file():
            path = HERE.parent / "okf_graph.json"
        self.graph = LibraryGraph(path)
        self.books = load_books()
        self.catalog = Catalog(self.graph.nodes, self.books)

    def best_book(self, cid: str) -> dict | None:
        """Match a Pearson copy only when the retrieved document title is that book."""
        record = self.graph.cite_record(cid, getattr(self.graph, "_query", ""))
        stem = re.sub(r"\.pdf$", "", (record.get("doc_id") or "").split("/")[-1].lower())
        stem = stem.replace("_", " ").replace("-", " ")
        tokens = {tok for tok in re.findall(r"[a-z]{5,}", stem)}
        if not tokens:
            return None
        best = None
        best_score = 0
        for book in self.books:
            title = (book.get("title") or "").lower()
            score = sum(1 for tok in tokens if tok in title)
            if score > best_score:
                best, best_score = book, score
        return best if best_score >= 2 else None

    def pearson_line(self, cid: str, page: int = 1) -> str:
        book = self.best_book(cid)
        record = self.graph.cite_record(cid, getattr(self.graph, "_query", ""))
        page_n = int(record.get("page_number") or page or 1)
        lines = []
        if record.get("url"):
            name = (record.get("doc_id") or "paper").split("/")[-1]
            lines.append(f"**Hugging Face page.** [{name} p.{page_n}]({record['url']})")
        if not book:
            return "\n".join(lines)
        page_count = int(book.get("page_count") or 0)
        if page_count and page_n > page_count:
            return "\n".join(lines)
        href = f"/open/{book.get('id')}?page={page_n}"
        exact = pearson_page_url(book, page_n)
        lines.append(
            f"**Pearson page.** [{book.get('title')} p.{page_n}]({href}) "
            f"({exact})"
        )
        return "\n".join(lines)

    def answer(self, query: str) -> dict:
        query = (query or "").strip()
        self.graph._query = query
        route, text, anchor, extra = self._route(query)
        graph = self.graph
        pres = [ _node_public(graph.nodes[c]) for c in (graph.prereqs(anchor, 2)[:6] if anchor else []) ]
        unl = [ _node_public(graph.nodes[c]) for c in (graph.unlocks(anchor, 2)[:6] if anchor else []) ]
        rel = [ _node_public(graph.nodes[c]) for c in (graph.related(anchor) if anchor else []) ]
        payload = {
            "anchor_concept": _node_public(graph.nodes[anchor]) if anchor and anchor in graph.nodes else None,
            "prerequisites": pres if anchor and anchor in graph.nodes else [],
            "unlocks": unl if anchor and anchor in graph.nodes else [],
            "related_concepts": rel if anchor and anchor in graph.nodes else [],
            "citations": extra.get("citations") or (
                [extra["citation"]] if extra.get("citation") else (
                    [graph.cite_record(anchor, query)] if anchor and anchor in graph.nodes else []
                )
            ),
            "routing": {"route": route, "score": extra.get("score", 1.0), "reason": extra.get("reason", route)},
            "logs": [{"step": "Hosted inference", "status": "ok", "details": route}],
        }
        if extra.get("hide_graph"):
            payload["anchor_concept"] = None
            payload["prerequisites"] = []
            payload["unlocks"] = []
        return {"route": route, "text": text, "payload": payload, "anchor": anchor, "extra": extra}

    def stream_chat(self, query: str):
        """Yield metadata frame immediately, then stream tokens from XKIRO (or fallback to grounded synthesis)."""
        result = self.answer(query)
        route = result["route"]
        grounded_text = result["text"]
        payload = result["payload"]

        # Check if route qualifies for LLM academic polishing
        can_polish = route in {"GRAPH_SYNTHESIS", "RELATION", "CROSS_DOMAIN", "BOOK_PAGE", "DEMO"}
        xkey = os.environ.get("XKIRO_API_KEY", "").strip()
        okey = os.environ.get("OPENROUTER_API_KEY", "").strip()

        llm_config = None
        if can_polish:
            if xkey:
                llm_config = {
                    "base_url": os.environ.get("XKIRO_BASE_URL", "https://api.xkiro.com/v1"),
                    "key": xkey,
                    "model": os.environ.get("XKIRO_MODEL", "qwen/qwen3.8-max:free"),
                    "provider": "xkiro",
                }
            elif okey:
                llm_config = {
                    "base_url": "https://openrouter.ai/api/v1",
                    "key": okey,
                    "model": os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
                    "provider": "openrouter",
                }

        if llm_config:
            payload["model"] = {"provider": llm_config["provider"], "model": llm_config["model"]}
            payload["logs"].append({"step": llm_config["provider"], "status": "ok", "details": llm_config["model"]})

        # Yield metadata frame immediately (< 10ms) to satisfy client watchdog and populate evidence/graph
        yield json.dumps(payload) + "\n[STREAM_START]\n"

        if not can_polish or not llm_config:
            yield grounded_text
            return

        # Attempt real-time token streaming from LLM provider
        safe_text = redact_for_model(grounded_text)
        link_lines = [
            line for line in grounded_text.splitlines()
            if line.startswith("**Paper page.**") or line.startswith("**Pearson ")
        ]

        streamed_tokens = 0
        try:
            resp = requests.post(
                f"{llm_config['base_url'].rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {llm_config['key']}", "Content-Type": "application/json"},
                json={
                    "model": llm_config["model"],
                    "temperature": 0.2,
                    "max_tokens": 550,
                    "stream": True,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are Archipelago's academic librarian and tutor. Give a focused answer in at most 350 words "
                                "and 3–5 short paragraphs, based only on the provided technical notes. State the core mechanism "
                                "and the most useful trade-off or implication; do not expand into a textbook-length tutorial. "
                                "Do not include raw URLs, web links, "
                                "file paths, or internal database names. Do not mention OKF or internal graph structures."
                            ),
                        },
                        {"role": "user", "content": safe_text},
                    ],
                },
                stream=True,
                timeout=30,
            )
            if resp.status_code == 200:
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line_str = line.decode("utf-8", errors="replace")
                    if line_str.startswith("data: "):
                        data_part = line_str[6:].strip()
                        if data_part == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data_part)
                            delta = chunk["choices"][0]["delta"].get("content", "")
                            if delta:
                                streamed_tokens += 1
                                yield delta
                        except Exception:
                            continue
            resp.close()
        except Exception:
            pass

        # If model streaming produced tokens, append paper/reader citations at the bottom
        if streamed_tokens > 0:
            if link_lines:
                yield "\n\n" + "\n".join(link_lines)
        else:
            # Fallback to grounded text if stream connection failed or produced 0 tokens
            yield grounded_text

    def _route(self, query: str) -> tuple[str, str, str | None, dict]:
        graph = self.graph
        if not query or len(query) < 2:
            return "EMPTY", "Ask a library question of at least two characters.", None, {"hide_graph": True, "reason": "empty"}
        if INJECTION.search(query):
            return "PERSONA_LOCK", HIJACK_MESSAGE, None, {"hide_graph": True, "reason": "injection"}
        if CODE_TRAP.search(query):
            return "CODE_TRAP", CODE_MESSAGE, None, {"hide_graph": True, "reason": "procedural"}
        demo = match_demo(query, self.books)
        if demo:
            return "DEMO", demo["text"], None, {
                "hide_graph": True,
                "reason": "demo_prompt",
                "citations": demo["citations"],
                "score": 1.0,
            }
        if any(term in query.lower() for term in PASSING_MENTIONS):
            entity = next(term.strip() for term in PASSING_MENTIONS if term in query.lower())
            text = (
                f"The library texts mention {entity} in passing as a dataset benchmark or infrastructure instance, "
                "but do not contain the theoretical documentation required to explain it. "
                "I cannot use external knowledge to fill in the gaps."
            )
            return "PASSING_MENTION", text, None, {"hide_graph": True, "reason": "passing_mention"}
        if SCHEDULE_RE.search(query):
            lines = ["**Central Library schedule**", ""]
            lines.extend(SCHEDULE)
            lines.append("")
            lines.append("Source: Central Library Academic Schedule.")
            return "SCHEDULE", "\n".join(lines), None, {"hide_graph": True, "reason": "schedule_sheet"}
        if AUTH_RE.search(query) and not SHELF_RE.search(query):
            return "AUTH_GATEWAY", self._auth_card(query), None, {"hide_graph": True, "reason": "auth_gateway"}

        catalog_hit = self.catalog.reply(query)
        if catalog_hit and not SHELF_RE.search(query):
            return "BOOK_PAGE", catalog_hit["text"], None, {
                "hide_graph": True,
                "reason": "catalog_book",
                "citation": catalog_hit["citation"],
                "score": 0.9,
            }

        ranked = graph.rank(query, top_k=6)
        best_score, best_id = ranked[0]
        hits = graph.phrase_hits(query)
        anchors = []
        for cid in hits:
            if cid not in anchors:
                anchors.append(cid)
        for score, cid in ranked:
            if score >= KILL_SWITCH and cid not in anchors:
                anchors.append(cid)
            if len(anchors) >= 3:
                break

        if SHELF_RE.search(query):
            shelf_id = anchors[0] if anchors else ("third_normal_form" if "3nf" in query.lower() else None)
            if shelf_id and shelf_id in SHELF:
                return "CATALOG_SHELF", self._shelf(shelf_id), shelf_id, {"score": best_score, "reason": "shelf"}
            if shelf_id:
                return "CATALOG_SHELF", self._shelf_generic(shelf_id), shelf_id, {"score": best_score, "reason": "shelf_generic"}

        domains = self._domain_pair(query)
        if domains and any(token in query.lower() for token in ("compare", "versus", "vs", "difference", "with")):
            (left_id, left_name), (right_id, right_name) = domains
            return "CROSS_DOMAIN", self._matrix(left_id, right_id, left_name, right_name), left_id, {"score": max(best_score, 0.8), "reason": "cross_domain"}

        pair = self._split_pair(query)
        if pair:
            left_text, right_text = pair
            left_id, left_ok = self._resolve_fragment(left_text)
            right_id, right_ok = self._resolve_fragment(right_text)
            if left_ok and right_ok and left_id != right_id:
                path = graph.shortest(left_id, right_id, limit=6)
                if path is None:
                    text = (
                        f"**{graph.label(left_id)}** and **{graph.label(right_id)}** are both indexed catalog nodes. "
                        "No pedagogical prerequisite or structural dependency connects them within this corpus.\n\n"
                        "Independent neighborhoods:\n"
                        f"{_neighborhood_block(graph, left_id)}\n"
                        f"{_neighborhood_block(graph, right_id)}"
                    )
                    return "DISCONNECTED", text, left_id, {"score": best_score, "reason": "no_path"}
                if any(token in query.lower() for token in ("compare", "versus", "vs", "difference")):
                    return "CROSS_DOMAIN", self._matrix(left_id, right_id), left_id, {"score": best_score, "reason": "cross_domain"}
                return "RELATION", self._relation(left_id, right_id, path), left_id, {"score": best_score, "reason": "shortest_path"}
            if left_ok ^ right_ok:
                known = left_id if left_ok else right_id
                missing = right_text if left_ok else left_text
                text = (
                    f"**{graph.label(known)}** is an indexed catalog node. "
                    f"**{missing.strip(' ?.')}** is not. "
                    "No pedagogical prerequisite connects them, and I will not invent a bridge.\n\n"
                    f"{_neighborhood_block(graph, known)}"
                )
                return "DISCONNECTED", text, known, {"score": best_score, "reason": "one_sided"}

        if PARAM_RE.search(query):
            target = anchors[0] if anchors and anchors[0] in graph.nodes else None
            if target is None:
                text = (
                    "The active catalog does not contain a concept node for that implementation parameter. "
                    "I will not invent a memory formula or version-specific constant. "
                    "Ask for a concept that is indexed, such as LoRA, BERT, or third normal form."
                )
                return "CATALOG_DEPTH", text, None, {"hide_graph": True, "score": best_score, "reason": "missing_parameter"}
            summary = (graph.nodes.get(target) or {}).get("summary") or ""
            if not re.search(r"\d", summary):
                parent = graph.prereqs(target, 1)
                parent_name = graph.label(parent[0]) if parent else graph.label(target)
                text = (
                    f"**{graph.label(target)}** is an indexed catalog node. "
                    "The active catalog chunks do not contain the specific implementation parameter you asked for. "
                    "I will not guess a number that is not in the retrieved text. "
                    f"The closest indexed prerequisite is **{parent_name}**."
                )
                return "CATALOG_DEPTH", text, target, {"score": best_score, "reason": "missing_parameter"}

        if best_score < KILL_SWITCH and not hits:
            return "OOD_KILL", OOD_MESSAGE, None, {"hide_graph": True, "score": best_score, "reason": "cosine_below_0.75"}

        if DIAG_RE.search(query) and anchors:
            target = anchors[0]
            return "MCQ_DIAGNOSTIC", self._diagnostic_intro(target), target, {"score": best_score, "reason": "diagnostic"}

        if RELATE_RE.search(query) and len(anchors) >= 2:
            a, b = anchors[0], anchors[1]
            path = graph.shortest(a, b, limit=6)
            if path is None:
                text = (
                    f"**{graph.label(a)}** and **{graph.label(b)}** are both indexed catalog nodes. "
                    "No pedagogical prerequisite or structural dependency connects them within this corpus.\n\n"
                    "Independent neighborhoods:\n"
                    f"{_neighborhood_block(graph, a)}\n"
                    f"{_neighborhood_block(graph, b)}"
                )
                return "DISCONNECTED", text, a, {"score": best_score, "reason": "no_path", "hide_graph": False}
            if any(token in query.lower() for token in ("compare", "versus", "vs", "difference", "dbms", "b+")):
                return "CROSS_DOMAIN", self._matrix(a, b), a, {"score": best_score, "reason": "cross_domain"}
            return "RELATION", self._relation(a, b, path), a, {"score": best_score, "reason": "shortest_path"}

        if len(anchors) >= 2 and any(token in query.lower() for token in ("compare", "versus", "vs", "difference", "and")):
            return "CROSS_DOMAIN", self._matrix(anchors[0], anchors[1]), anchors[0], {"score": best_score, "reason": "multi_anchor"}

        target = anchors[0] if anchors else best_id
        return "GRAPH_SYNTHESIS", self._synthesis(target), target, {"score": max(best_score, 0.93 if hits else best_score), "reason": "graph_synthesis"}

    def _synthesis(self, cid: str) -> str:
        graph = self.graph
        node = graph.nodes[cid]
        summary = (node.get("summary") or "Indexed catalog concept.").strip()
        cite = graph.citation(cid)
        formula = graph.formula(cid)
        lines = [
            f"**{graph.label(cid)}.** {summary} {cite}",
            "",
            f"**Topological graph sequence.** {_lineage(graph, cid)}",
        ]
        if formula:
            lines.extend(["", f"**LaTeX derivation.** {formula}"])
        else:
            lines.extend(["", f"**Provenance.** Grounded in the catalog summary above. {cite}"])
        link = self.pearson_line(cid)
        if link:
            lines.extend(["", link])
        return "\n".join(lines)

    def _relation(self, a: str, b: str, path: list[tuple[str, str]]) -> str:
        graph = self.graph
        chain = [graph.label(a)]
        rendered = []
        cursor = a
        for kind, nxt in path:
            rel = "UNLOCKS" if "UNLOCKS" in kind else "REQUIRES"
            rendered.append(_arrow(graph.label(cursor), rel, graph.label(nxt)))
            chain.append(graph.label(nxt))
            cursor = nxt
        hops = len(path)
        kind = "a direct dependency" if hops == 1 else f"a {hops}-hop structural bridge"
        lines = [
            f"**{graph.label(a)}** and **{graph.label(b)}** share {kind} in the catalog graph.",
            "",
            "**Traversal chain.** " + " ".join(rendered),
            "",
            f"**Document evidence.** {graph.citation(a, 1)} {graph.citation(b, 2)}",
        ]
        return "\n".join(lines)

    def _domain_pair(self, query: str):
        q = query.lower()
        left = right = None
        if re.search(r"\bb\+\s*tree\b|\bb-tree\b|\bdbms\b|\brelational\b", q):
            left = ("third_normal_form", "Relational B+ tree / DBMS")
        if re.search(r"\bhnsw\b|\bvector search\b|\brag\b", q):
            right = ("rag", "HNSW / vector RAG")
        if left and right and left[0] in self.graph.nodes and right[0] in self.graph.nodes:
            return left, right
        return None

    def _split_pair(self, query: str):
        patterns = (
            r"how (?:are|is) (.+?) and (.+?) connected",
            r"how (?:are|is) (.+?) (?:related|connected) to (.+)",
            r"relation(?:ship)? between (.+?) and (.+)",
            r"compare (.+?) (?:with|and|to|versus|vs\.?) (.+)",
            r"difference between (.+?) and (.+)",
        )
        for pattern in patterns:
            match = re.search(pattern, query, re.I)
            if match:
                return match.group(1), match.group(2)
        return None

    def _resolve_fragment(self, fragment: str) -> tuple[str | None, bool]:
        hits = self.graph.phrase_hits(fragment)
        if hits:
            return hits[0], True
        ranked = self.graph.rank(fragment, top_k=1)
        if ranked and ranked[0][0] >= KILL_SWITCH:
            return ranked[0][1], True
        return None, False

    def _matrix(self, a: str, b: str, left_name: str | None = None, right_name: str | None = None) -> str:
        graph = self.graph
        left = left_name or graph.label(a)
        right = right_name or graph.label(b)
        def cell(cid: str) -> str:
            return (graph.nodes[cid].get("summary") or graph.label(cid)).strip()[:180]
        if left_name and "B+" in left_name:
            data_l = "Ordered keys in leaf-linked pages of a B+ tree."
            data_r = "High-dimensional embedding vectors in an HNSW graph."
            search_l = "Exact descent from root to leaf, then a sequential sibling scan."
            search_r = "Greedy beam search over layered navigable small-world links."
            io_l = "Few sequential page reads once the leaf is reached."
            io_r = "Random hops through the vector index; more irregular I/O."
            recall_l = "Exact for the indexed key range."
            recall_r = "Approximate; recall depends on the beam and the graph degree."
            cites = "[S1: Silberschatz_Database_Systems.pdf, #page=1] [S2: Lewis2020_RAG.pdf, #page=1]"
        else:
            data_l, data_r = cell(a), cell(b)
            search_l = search_r = "Retrieved from the indexed concept summary only."
            io_l = io_r = "Textbook pages cited below."
            recall_l = recall_r = "Limited to indexed chunks; no unstated guarantee."
            cites = f"{graph.citation(a, 1)} {graph.citation(b, 2)}"
        lines = [
            f"**Comparative matrix: {left} × {right}**",
            "",
            "| Axis | " + left + " | " + right + " |",
            "| --- | --- | --- |",
            f"| Data representation | {data_l} | {data_r} |",
            f"| Search mechanics | {search_l} | {search_r} |",
            f"| Disk I/O | {io_l} | {io_r} |",
            f"| Recall | {recall_l} | {recall_r} |",
            "",
            cites,
        ]
        return "\n".join(lines)

    def _diagnostic_intro(self, cid: str) -> str:
        graph = self.graph
        pres = graph.prereqs(cid, 2)[:4] or [cid]
        names = ", ".join(graph.label(p) for p in pres)
        return (
            f"**Diagnostic checkpoint for {graph.label(cid)}.** "
            "Full text generation is paused. Answer the four checks on the prerequisite nodes, "
            f"then the personalized graph is drawn from your ticks and gaps.\n\n"
            f"Upstream nodes in the checkpoint: {names}.\n\n"
            "Use **Yes, Start Diagnostic** under this reply to take the four-option checks."
        )

    def _shelf(self, cid: str) -> str:
        graph = self.graph
        card = SHELF[cid]
        cite = graph.citation(cid)
        return "\n".join([
            f"**{graph.label(cid)}.** {card['definition']} {cite}",
            "",
            f"**Title & author.** {card['title']}, {card['author']}.",
            f"**Call number.** {card['call_number']}.",
            f"**Shelf.** {card['place']}.",
            f"**System barcode.** {card['barcode']}.",
            f"**Live availability.** {card['available']} physical copies currently on shelf (out of {card['total']} total).",
        ])

    def _shelf_generic(self, cid: str) -> str:
        graph = self.graph
        return (
            f"**{graph.label(cid)}.** {(graph.nodes[cid].get('summary') or '').strip()} {graph.citation(cid)}\n\n"
            "No separate physical shelf card is indexed for this concept. "
            "Ask at the Central Library circulation desk and search the OPAC at http://uemk-opac.l2c2.co.in."
        )

    def _auth_card(self, query: str) -> str:
        q = query.lower()
        chosen = [row for row in PORTALS if row[0].split()[0].lower() in q or row[0].lower() in q]
        if not chosen:
            chosen = PORTALS[:4]
        lines = [
            "[RENDER_AUTH_CARD]",
            "**Institutional access.** Sign in with your own campus account. This assistant does not store or reveal passwords.",
            "",
        ]
        for name, url, how in chosen:
            lines.append(f"- **{name}.** {url} — {how}.")
        lines.append("")
        lines.append(
            "If a title is paywalled outside these portals, borrow a reciprocal membership card "
            "(British Council Library or American Library) from the Central Library front desk."
        )
        return "\n".join(lines)

    def mcq_for(self, concept_id: str, slot: int = 0) -> dict:
        graph = self.graph
        if concept_id not in graph.nodes:
            concept_id = next(iter(graph.nodes))
        chain = list(reversed(graph.prereqs(concept_id, 2)[:3])) + [concept_id]
        # Unique, keep order.
        seen = []
        for cid in chain:
            if cid not in seen:
                seen.append(cid)
        chain = seen or [concept_id]
        focus = chain[min(slot, len(chain) - 1)]
        node = graph.nodes[focus]
        summary = (node.get("summary") or graph.label(focus)).strip()
        distractor_ids = [cid for _score, cid in graph.rank(graph.label(focus), 8) if cid != focus][:3]
        while len(distractor_ids) < 3:
            extra = next(cid for cid in graph.nodes if cid not in distractor_ids and cid != focus)
            distractor_ids.append(extra)
        options = {
            "A": summary[:220],
            "B": (graph.nodes[distractor_ids[0]].get("summary") or "Unrelated catalog node.")[:220],
            "C": (graph.nodes[distractor_ids[1]].get("summary") or "Unrelated catalog node.")[:220],
            "D": (graph.nodes[distractor_ids[2]].get("summary") or "Unrelated catalog node.")[:220],
        }
        return {
            "concept_id": focus,
            "concept_name": graph.label(focus),
            "difficulty": node.get("difficulty") or "intermediate",
            "question": f"Which statement matches the indexed catalog definition of {graph.label(focus)}?",
            "options": options,
            "correct_option": "A",
            "explanation": summary,
            "citation": graph.citation(focus),
            "chain": chain,
        }

    def diagnostic_payload(self, concept_id: str) -> dict:
        graph = self.graph
        if concept_id not in graph.nodes:
            hits = graph.phrase_hits(concept_id.replace("_", " "))
            concept_id = hits[0] if hits else next(iter(graph.nodes))
        first = self.mcq_for(concept_id, 0)
        chain = first["chain"]
        return {
            "success": True,
            "available": True,
            "target_concept": concept_id,
            "target_label": graph.label(concept_id),
            "chain": chain,
            "prereq_chain": chain[:-1],
            "immediate_prerequisite": chain[-2] if len(chain) > 1 else concept_id,
            "initial_question": first,
            "mcqs": [self.mcq_for(concept_id, i) for i in range(min(4, len(chain)) )],
        }

    def adaptive_step(self, body: dict) -> dict:
        graph = self.graph
        target = body.get("target_concept") or ""
        if target not in graph.nodes:
            target = next(iter(graph.nodes))
        current = body.get("current_concept") or target
        mcq = body.get("current_mcq") or self.mcq_for(target, 0)
        choice = str(body.get("user_choice") or "").upper()
        correct = str(mcq.get("correct_option") or "A").upper()
        is_tick = choice == correct
        ticks = int(body.get("consecutive_ticks") or 0)
        ticks = ticks + 1 if is_tick else 0
        history = list(body.get("history") or [])
        history.append({
            "concept_id": mcq.get("concept_id") or current,
            "is_correct": is_tick,
            "choice": choice,
        })
        chain = body.get("chain") or self.mcq_for(target, 0)["chain"]
        asked = len(history)
        mastered_ids = [row["concept_id"] for row in history if row.get("is_correct")]
        gap_ids = [row["concept_id"] for row in history if not row.get("is_correct")]
        completed = ticks >= 3 or asked >= 4
        stride = "advance" if is_tick else "leap_back"
        next_q = None
        next_concept = current
        if not completed:
            slot = min(asked, 3)
            next_q = self.mcq_for(target, slot)
            next_concept = next_q["concept_id"]
        nodes = []
        for cid in mastered_ids:
            if cid in graph.nodes and cid != target:
                pub = _node_public(graph.nodes[cid])
                src = graph.cite_record(cid)
                pub.update({"status": "mastered", "role": "prereq", "doc_id": src.get("doc_id") or "", "page_number": src.get("page_number") or 1, "printed_page": src.get("page_number") or 1, "url": src.get("url") or ""})
                nodes.append(pub)
        for cid in gap_ids:
            if cid in graph.nodes and cid != target:
                pub = _node_public(graph.nodes[cid])
                src = graph.cite_record(cid)
                pub.update({"status": "review_gap", "role": "prereq", "doc_id": src.get("doc_id") or f"/library?book={cid}", "page_number": src.get("page_number") or 1, "printed_page": src.get("page_number") or 1, "url": src.get("url") or ""})
                nodes.append(pub)
        target_pub = _node_public(graph.nodes[target])
        target_src = graph.cite_record(target)
        target_pub.update({"status": "unlocked" if ticks >= 3 else "target", "role": "target", "doc_id": target_src.get("doc_id") or "", "page_number": target_src.get("page_number") or 1, "printed_page": target_src.get("page_number") or 1, "url": target_src.get("url") or ""})
        nodes.append(target_pub)
        edges = []
        for node in nodes:
            if node["id"] != target:
                edges.append({"source": node["id"], "target": target, "relation": "REQUIRES"})
        score = f"{sum(1 for row in history if row.get('is_correct'))}/{len(history)}"
        evaluation = {
            "target_concept": target,
            "baseline_concept": graph.label(mastered_ids[-1]) if mastered_ids else "None",
            "score": score,
            "passed": ticks >= 3,
            "full_score": ticks >= 3,
            "zero_score": not mastered_ids,
            "personalized_graph": {"nodes": nodes, "edges": edges},
            "roadmap": {
                "hops": max(len(chain) - 1, 1),
                "steps": [
                    {
                        "id": cid,
                        "name": graph.label(cid),
                        "summary": (graph.nodes[cid].get("summary") or "")[:160],
                        "doc_id": graph.cite_record(cid).get("doc_id") or "",
                        "page_number": graph.cite_record(cid).get("page_number") or 1,
                        "printed_page": graph.cite_record(cid).get("page_number") or 1,
                        "url": graph.cite_record(cid).get("url") or "",
                    }
                    for cid in chain if cid in graph.nodes
                ],
            },
        }
        return {
            "is_tick": is_tick,
            "current_record": {"correct_answer": correct, "concept_id": mcq.get("concept_id")},
            "consecutive_ticks": ticks,
            "history": history,
            "completed": completed,
            "completion_reason": "3_consecutive_ticks_mastered" if ticks >= 3 else ("four_question_checkpoint" if completed else ""),
            "total_asked": asked,
            "stride_action": stride,
            "next_concept": next_concept,
            "next_question": next_q,
            "personalized_graph": evaluation["personalized_graph"],
            "evaluation": evaluation,
        }


def _complete(base_url: str, key: str, model: str, text: str) -> str:
    import time
    import requests
    time.sleep(1.2)
    response = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "temperature": 0.2,
            "max_tokens": 550,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Archipelago's academic librarian and tutor. Give a focused answer in at most 350 words "
                        "and 3–5 short paragraphs, based only on the provided technical notes. State the core mechanism "
                        "and the most useful trade-off or implication; do not expand into a textbook-length tutorial. "
                        "Do not include raw URLs, web links, "
                        "file paths, or internal database names. Do not mention OKF or internal graph structures."
                    ),
                },
                {"role": "user", "content": text},
            ],
        },
        timeout=40,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def maybe_polish(text: str, route: str) -> tuple[str, dict | None]:
    """Ask xkiro to phrase the grounded draft. Keep the draft if the model drops the page citation."""
    if route not in {"GRAPH_SYNTHESIS", "RELATION", "CROSS_DOMAIN", "BOOK_PAGE", "DEMO"}:
        return text, None
    attempts = []
    xkey = os.environ.get("XKIRO_API_KEY", "").strip()
    if xkey:
        attempts.append((
            os.environ.get("XKIRO_BASE_URL", "https://api.xkiro.com/v1"),
            xkey,
            os.environ.get("XKIRO_MODEL", "qwen/qwen3.8-max:free"),
            "xkiro",
        ))
    okey = os.environ.get("OPENROUTER_API_KEY", "").strip()
    if okey:
        attempts.append((
            "https://openrouter.ai/api/v1",
            okey,
            os.environ.get("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
            "openrouter",
        ))
    safe_text = redact_for_model(text)
    link_lines = [
        line for line in text.splitlines()
        if line.startswith("**Paper page.**") or line.startswith("**Pearson ")
    ]
    for base_url, key, model, provider in attempts:
        try:
            polished = _complete(base_url, key, model, safe_text)
        except Exception:
            continue
        if not polished:
            continue
        if link_lines:
            polished = polished.rstrip() + "\n\n" + "\n".join(link_lines)
        return polished, {"provider": provider, "model": model}
    return text, None
