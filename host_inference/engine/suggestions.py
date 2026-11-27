"""Dynamic welcome suggestions and supported-topic discovery from the active graph.

One concern: inspect the live ``LibraryGraph`` and open-access corpus inventory
to derive numbered knowledge areas (with zero hardcoded domain counts) and
shuffled starter questions grounded strictly in indexed concepts.
"""

from __future__ import annotations

import random
import re
from typing import Any

from library_index import load_hf_paths

from .access_profile import active_access_profile, is_open_access_profile

DEFAULT_SUGGESTION_COUNT = 5
MIN_SUGGESTION_COUNT = 4
MAX_SUGGESTION_COUNT = 5
QUESTION_BANK_SIZE = 40
NON_AI_FALLBACK_SUGGESTION_COUNT = 3
MAX_SAMPLE_CONCEPTS = 4
MIN_LABEL_LEN = 3
MAX_LABEL_LEN = 60

# Classifier descriptors (keys, display labels, doc/text markers).
# Counts are NEVER hardcoded — they are computed live from ``graph.nodes``
# and ``load_hf_paths()``.
_KNOWLEDGE_AREA_SPECS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "os",
        "Operating Systems",
        (
            "ostep",
            "operating system",
            "paging",
            "virtual memory",
            "address translation",
            "cpu scheduling",
            "deadlock",
            "semaphore",
            "mutex",
            "thread",
            "process",
            "tlb",
            "raid",
            "file system",
            "concurrency",
            "lock",
        ),
    ),
    (
        "llm_nlp",
        "Transformers, LLMs & Retrieval",
        (
            "vaswani",
            "devlin",
            "bert",
            "gpt3",
            "brown2020",
            "lora",
            "qlora",
            "rag",
            "graphrag",
            "dpr",
            "karpukhin",
            "vllm",
            "kwon2023",
            "dpo",
            "rafailov",
            "instructgpt",
            "ouyang",
            "constitutionalai",
            "chainofthought",
            "react",
            "yao2022",
            "outlines",
            "willard2023",
            "bahdanau",
            "flashattention",
            "attention",
            "transformer",
            "prompt",
            "language model",
            "retrieval",
        ),
    ),
    (
        "deep_learning",
        "Deep Learning & Generative Models",
        (
            "backpropagation",
            "rumelhart",
            "convnet",
            "lecun",
            "alexnet",
            "krizhevsky",
            "lstm",
            "hochreiter",
            "gan",
            "goodfellow",
            "vae",
            "kingma",
            "ddpm",
            "ho2020",
            "diffusion",
            "neural network",
            "convolutional",
            "recurrent",
            "generative",
            "autoencoder",
        ),
    ),
    (
        "graph_ml",
        "Graph Neural Networks & Graph Learning",
        (
            "kipf",
            "gcn",
            "velickovic",
            "gat",
            "graph convolutional",
            "graph attention",
            "message passing",
            "node embedding",
            "knowledge graph",
        ),
    ),
    (
        "math_ml",
        "Mathematics for Machine Learning",
        (
            "deisenroth",
            "math_for_ml",
            "linear algebra",
            "eigenvalue",
            "eigenvector",
            "gradient descent",
            "probability",
            "bayes",
            "matrix",
            "vector space",
            "calculus",
            "optimization",
            "singular value",
            "pca",
            "gaussian",
        ),
    ),
    (
        "dbms",
        "Database Systems",
        (
            "database",
            "dbms",
            "sql",
            "acid",
            "normal form",
            "3nf",
            "b-tree",
            "b+ tree",
            "transaction",
            "relational",
            "query optimization",
            "indexing",
        ),
    ),
    (
        "networks_sec",
        "Computer Networks & Security",
        (
            "network security",
            "tcp",
            "udp",
            "routing",
            "packet",
            "cryptography",
            "encryption",
            "tls",
            "congestion",
            "socket",
            "dns",
            "http",
        ),
    ),
    (
        "algorithms_systems",
        "Algorithms, Compilers & Architecture",
        (
            "algorithm",
            "dynamic programming",
            "dijkstra",
            "sorting",
            "binary search",
            "compiler",
            "parser",
            "syntax tree",
            "automata",
            "turing",
            "cache",
            "pipeline",
        ),
    ),
)

_QUESTION_TEMPLATES: tuple[str, ...] = (
    "Explain {label} and how it works.",
    "What are the foundational ideas behind {label}?",
    "Walk through how {label} is used in practice.",
    "What should I review before studying {label}?",
)


def _classify_text_area(text: str) -> str:
    low = (text or "").lower()
    for key, _label, markers in _KNOWLEDGE_AREA_SPECS:
        if any(marker in low for marker in markers):
            return key
    return ""


def _open_corpus_paths() -> list[str]:
    """Deduplicated open-access corpus paths (excluding librarian test uploads)."""
    seen_base: set[str] = set()
    unique: list[str] = []
    for path in sorted(load_hf_paths(), key=lambda p: (0 if "/" in p else 1, p.lower())):
        if "librarian_uploads/" in path.lower():
            continue
        base = path.rsplit("/", 1)[-1].lower()
        if base in seen_base:
            continue
        seen_base.add(base)
        unique.append(path)
    return unique


def _node_is_supported(node: dict[str, Any], *, open_only: bool) -> bool:
    label = str(node.get("label") or node.get("name") or "").strip()
    if len(label) < MIN_LABEL_LEN or len(label) > MAX_LABEL_LEN:
        return False
    if re.search(r"^(?:doc_|upload_|chunk_)", label, re.I):
        return False
    sources = node.get("sources") or []
    if not sources:
        return False
    if not open_only:
        return True
    for src in sources:
        if not isinstance(src, dict):
            continue
        doc_id = str(src.get("doc_id") or "").lower()
        if any(
            marker in doc_id
            for marker in ("papers/", "textbooks/", "ostep", "deisenroth", ".pdf")
        ) and not doc_id.startswith("upload_"):
            return True
    return False


def discover_knowledge_areas(graph: Any) -> list[dict[str, Any]]:
    """Derive numbered knowledge areas from the actual graph and open corpus inventory."""
    nodes = getattr(graph, "nodes", None) or {}
    open_only = is_open_access_profile()
    area_labels = {key: label for key, label, _ in _KNOWLEDGE_AREA_SPECS}
    area_concepts: dict[str, list[tuple[int, str]]] = {key: [] for key, _, _ in _KNOWLEDGE_AREA_SPECS}
    area_docs: dict[str, set[str]] = {key: set() for key, _, _ in _KNOWLEDGE_AREA_SPECS}

    for path in _open_corpus_paths():
        area = _classify_text_area(path)
        if area:
            area_docs[area].add(path)

    for cid, node in nodes.items():
        if not isinstance(node, dict) or not _node_is_supported(node, open_only=open_only):
            continue
        label = str(node.get("label") or node.get("name") or cid).strip()
        summary = str(node.get("summary") or "")
        doc_ids = " ".join(
            str(s.get("doc_id") or "") for s in (node.get("sources") or []) if isinstance(s, dict)
        )
        area = _classify_text_area(f"{doc_ids} {label} {summary}")
        if not area:
            continue
        weight = int(node.get("source_count") or len(node.get("sources") or [])) + int(
            node.get("degree") or 0
        )
        area_concepts[area].append((weight, label))

    populated: list[dict[str, Any]] = []
    for key, _label, _markers in _KNOWLEDGE_AREA_SPECS:
        concepts = area_concepts[key]
        docs = area_docs[key]
        if not concepts and not docs:
            continue
        concepts.sort(key=lambda item: (-item[0], item[1].lower()))
        samples = [lbl for _, lbl in concepts[:MAX_SAMPLE_CONCEPTS]]
        populated.append(
            {
                "key": key,
                "label": area_labels[key],
                "concept_count": len(concepts),
                "doc_count": len(docs),
                "sample_concepts": samples,
            }
        )

    populated.sort(key=lambda item: (-item["concept_count"], -item["doc_count"], item["label"]))
    for idx, item in enumerate(populated, start=1):
        item["index"] = idx
    return populated


def generate_starter_questions(
    graph: Any,
    *,
    count: int = DEFAULT_SUGGESTION_COUNT,
    seed: int | None = None,
) -> list[str]:
    """Return ``count`` (4-5) shuffled starter questions grounded in indexed concepts."""
    clamped = max(MIN_SUGGESTION_COUNT, min(MAX_SUGGESTION_COUNT, int(count)))
    nodes = getattr(graph, "nodes", None) or {}
    open_only = is_open_access_profile()
    rng = random.Random(seed)

    # Gather diverse supported concepts across knowledge areas.
    candidates: list[tuple[str, str, str]] = []
    for cid, node in sorted(nodes.items()):
        if not isinstance(node, dict) or not _node_is_supported(node, open_only=open_only):
            continue
        label = str(node.get("label") or node.get("name") or cid).strip()
        doc_ids = " ".join(
            str(s.get("doc_id") or "") for s in (node.get("sources") or []) if isinstance(s, dict)
        )
        area = _classify_text_area(f"{doc_ids} {label} {node.get('summary') or ''}") or "general"
        candidates.append((area, cid, label))

    if not candidates:
        return []

    rng.shuffle(candidates)
    selected_questions: list[str] = []
    used_areas: set[str] = set()
    used_cids: set[str] = set()

    # First pass: pick one concept per distinct area for topic breadth.
    for area, cid, label in candidates:
        if len(selected_questions) >= clamped:
            break
        if area in used_areas or cid in used_cids:
            continue
        used_areas.add(area)
        used_cids.add(cid)
        template = rng.choice(_QUESTION_TEMPLATES)
        selected_questions.append(template.format(label=label))

    # Second pass: fill remaining slots if fewer areas than requested count.
    for _area, cid, label in candidates:
        if len(selected_questions) >= clamped:
            break
        if cid in used_cids:
            continue
        used_cids.add(cid)
        template = rng.choice(_QUESTION_TEMPLATES)
        selected_questions.append(template.format(label=label))

    return selected_questions


def generate_question_bank(
    graph: Any,
    *,
    size: int = QUESTION_BANK_SIZE,
    seed: int = 42,
) -> list[str]:
    """Build a diverse 30-50 question bank grounded strictly in indexed concepts."""
    nodes = getattr(graph, "nodes", None) or {}
    open_only = is_open_access_profile()
    rng = random.Random(seed)

    by_area: dict[str, list[tuple[str, str]]] = {}
    for cid, node in sorted(nodes.items()):
        if not isinstance(node, dict) or not _node_is_supported(node, open_only=open_only):
            continue
        label = str(node.get("label") or node.get("name") or cid).strip()
        doc_ids = " ".join(
            str(s.get("doc_id") or "") for s in (node.get("sources") or []) if isinstance(s, dict)
        )
        area = _classify_text_area(f"{doc_ids} {label} {node.get('summary') or ''}") or "general"
        by_area.setdefault(area, []).append((cid, label))

    if not by_area:
        return []

    for area_items in by_area.values():
        rng.shuffle(area_items)

    bank: list[str] = []
    seen_cids: set[str] = set()
    area_keys = sorted(by_area.keys())
    round_idx = 0
    while len(bank) < size:
        added_any = False
        for area in area_keys:
            items = by_area[area]
            if round_idx < len(items):
                cid, label = items[round_idx]
                if cid not in seen_cids:
                    seen_cids.add(cid)
                    tpl = _QUESTION_TEMPLATES[(len(bank) + round_idx) % len(_QUESTION_TEMPLATES)]
                    bank.append(tpl.format(label=label))
                    added_any = True
                    if len(bank) >= size:
                        break
        if not added_any:
            break
        round_idx += 1
    return bank


def sample_fallback_questions(
    graph: Any,
    *,
    count: int = NON_AI_FALLBACK_SUGGESTION_COUNT,
    seed: int | None = None,
) -> list[str]:
    """Sample up to ``count`` (max 3) questions from the generated 30-50 question bank."""
    cap = max(1, min(NON_AI_FALLBACK_SUGGESTION_COUNT, int(count)))
    bank = generate_question_bank(graph, size=QUESTION_BANK_SIZE)
    if not bank:
        return []
    rng = random.Random(seed)
    if len(bank) <= cap:
        return list(bank)
    return rng.sample(bank, cap)


def build_suggestions_payload(
    graph: Any,
    *,
    count: int = DEFAULT_SUGGESTION_COUNT,
    seed: int | None = None,
) -> dict[str, Any]:
    """Assemble the complete ``GET /api/chat/suggestions`` JSON payload."""
    nodes = getattr(graph, "nodes", None) or {}
    areas = discover_knowledge_areas(graph)
    questions = generate_starter_questions(graph, count=count, seed=seed)
    open_docs = _open_corpus_paths()
    return {
        "access_profile": active_access_profile(),
        "open_access_only": is_open_access_profile(),
        "total_concepts": len(nodes),
        "total_open_docs": len(open_docs),
        "knowledge_areas": areas,
        "suggested_questions": questions,
    }


__all__ = [
    "DEFAULT_SUGGESTION_COUNT",
    "MAX_SUGGESTION_COUNT",
    "MIN_SUGGESTION_COUNT",
    "NON_AI_FALLBACK_SUGGESTION_COUNT",
    "QUESTION_BANK_SIZE",
    "build_suggestions_payload",
    "discover_knowledge_areas",
    "generate_question_bank",
    "generate_starter_questions",
    "sample_fallback_questions",
]
