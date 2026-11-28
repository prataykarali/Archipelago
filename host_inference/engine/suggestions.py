"""Dynamic welcome suggestions and 12-domain topic discovery from the active graph.

One concern: inspect the live ``LibraryGraph`` and open-access corpus inventory
to derive numbered knowledge areas aligned with the 12 domains in ``graph_v2_d14``
(using word-boundary, score-ranked classification and zero hardcoded counts) and
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
DEFAULT_BANK_SEED = 42
NON_AI_FALLBACK_SUGGESTION_COUNT = 3
MAX_SAMPLE_CONCEPTS = 4
MIN_LABEL_LEN = 3
MAX_LABEL_LEN = 60
SUMMARY_PREVIEW_CHARS = 300
DOC_MATCH_WEIGHT = 3
LABEL_MATCH_WEIGHT = 2
SUMMARY_MATCH_WEIGHT = 1

_OPEN_ACCESS_DOC_MARKERS: tuple[str, ...] = ("papers/", "textbooks/", "ostep", "deisenroth", ".pdf")

# 12 canonical domains aligned with graph_v2_d14.
# Word-boundary patterns prevent bare "process", "lock", or "thread" substrings
# from misclassifying Chain-of-Thought, RNNs, or other AI concepts under OS.
_KNOWLEDGE_AREA_SPECS: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    (
        "os",
        "Operating Systems",
        re.compile(
            r"\b(?:ostep|operating\s+systems?|virtual\s+memory|paging|page\s+tables?|"
            r"page\s+faults?|page\s+frames?|address\s+translation|address\s+spaces?|\btlbs?\b|"
            r"cpu\s+scheduling|context\s+switch(?:ing)?|deadlocks?|semaphores?|mutex(?:es)?|"
            r"spinlocks?|condition\s+variables?|process\s+api|limited\s+direct\s+execution|"
            r"file\s+systems?|inodes?|log[-\s]?structured\s+fs|\braid\b|concurrency\s+bugs?)\b",
            re.I,
        ),
    ),
    (
        "ai_ml",
        "AI & Machine Learning",
        re.compile(
            r"\b(?:vaswani|devlin|\bbert\b|gpt[-\s]?[234]?|brown2020|\blora\b|\bqlora\b|"
            r"\brag\b|retrieval[-\s]?augmented|graphrag|\bdpr\b|karpukhin|\bvllm\b|kwon2023|"
            r"pagedattention|\bdpo\b|rafailov|direct\s+preference\s+optimization|instructgpt|"
            r"ouyang|constitutional\s+ai|chain[-\s]?of[-\s]?thought|wei2022|react\s+agent|"
            r"yao2022|willard2023|bahdanau|flashattention|self[-\s]?attention|"
            r"multi[-\s]?head\s+attention|transformers?|prompting|language\s+models?|"
            r"in[-\s]?context\s+learning|rlhf|backpropagation|rumelhart|convnets?|lecun|"
            r"alexnet|krizhevsky|\blstms?\b|hochreiter|\brnns?\b|recurrent\s+neural|\bgans?\b|"
            r"goodfellow|\bvaes?\b|kingma|\bddpm\b|ho2020|diffusion\s+models?|neural\s+networks?|"
            r"convolutional|autoencoders?|deep\s+learning|machine\s+learning|kipf|\bgcn\b|"
            r"velickovic|\bgat\b|graph\s+neural|message\s+passing|knowledge\s+graphs?|"
            r"reinforcement\s+learning|random\s+forest|decision\s+trees?|gradient\s+boosting)\b",
            re.I,
        ),
    ),
    (
        "math_computing",
        "Mathematics for Computing",
        re.compile(
            r"\b(?:deisenroth|math_for_ml|linear\s+algebra|eigenvalues?|eigenvectors?|"
            r"eigendecomposition|singular\s+value|\bsvd\b|matrix\s+decomposition|vector\s+spaces?|"
            r"gradient\s+descent|convex\s+optimization|calculus|jacobian|hessian|\bpca\b|"
            r"principal\s+component|discrete\s+mathematics|recurrence\s+relations?|"
            r"number\s+theory|graph\s+theory|combinatorics|propositional\s+logic)\b",
            re.I,
        ),
    ),
    (
        "prob_stats",
        "Probability & Statistics",
        re.compile(
            r"\b(?:probability|statistics|bayes(?:'s)?\s+theorem|bayesian|"
            r"maximum\s+likelihood|\bmle\b|kl\s+divergence|kullback[-\s]?leibler|"
            r"variational\s+inference|gaussian\s+distribution|normal\s+distribution|"
            r"random\s+variables?|conditional\s+probability|markov\s+chains?|"
            r"hypothesis\s+testing|central\s+limit\s+theorem|expectations?)\b",
            re.I,
        ),
    ),
    (
        "dsa",
        "Data Structures & Algorithms",
        re.compile(
            r"\b(?:algorithms?|data\s+structures?|dynamic\s+programming|dijkstra|"
            r"bellman[-\s]?ford|binary\s+search|priority\s+queues?|heaps?|linked\s+lists?|"
            r"hash\s+tables?|avl\s+trees?|red[-\s]?black\s+trees?|topological\s+sort|\bclrs\b|"
            r"breadth[-\s]?first|depth[-\s]?first|minimum\s+spanning\s+tree|quicksort|mergesort)\b",
            re.I,
        ),
    ),
    (
        "dbms",
        "Database Systems",
        re.compile(
            r"\b(?:databases?|dbms|\bsql\b|acid\s+properties|normal\s+forms?|\b3nf\b|\bbcnf\b|"
            r"b\+?\s*trees?|lsm[-\s]?trees?|transactions?|relational\s+algebra|"
            r"query\s+optimization|buffer\s+pool|serializability|silberschatz|"
            r"two[-\s]?phase\s+locking|write[-\s]?ahead\s+logging)\b",
            re.I,
        ),
    ),
    (
        "networks",
        "Computer Networks",
        re.compile(
            r"\b(?:computer\s+networks?|\btcp\b|\budp\b|congestion\s+control|flow\s+control|"
            r"routing\s+protocols?|osi\s+model|data\s+link\s+layer|transport\s+layer|"
            r"three[-\s]?way\s+handshake|\bdns\b|\bhttp\b|tanenbaum|sliding\s+window|"
            r"distance\s+vector|link\s+state|\bbgp\b|packet\s+switching)\b",
            re.I,
        ),
    ),
    (
        "compilers",
        "Compilers & Languages",
        re.compile(
            r"\b(?:compilers?|lexical\s+analysis|syntax\s+analysis|\blalr\b|parsers?|"
            r"abstract\s+syntax\s+tree|semantic\s+analysis|intermediate\s+representation|"
            r"three[-\s]?address\s+code|register\s+allocation|code\s+generation|"
            r"symbol\s+tables?|type\s+checking|shift[-\s]?reduce)\b",
            re.I,
        ),
    ),
    (
        "automata",
        "Automata & Computation",
        re.compile(
            r"\b(?:automata|pumping\s+lemma|regular\s+languages?|regular\s+expressions?|"
            r"\bdfa\b|\bnfa\b|finite\s+automat(?:a|on)|context[-\s]?free\s+grammars?|\bcfg\b|"
            r"\bpda\b|pushdown\s+automat(?:a|on)|turing\s+machines?|decidability|halting\s+problem|"
            r"chomsky\s+hierarchy|np[-\s]?complete(?:ness)?|formal\s+languages?)\b",
            re.I,
        ),
    ),
    (
        "security",
        "Information Security",
        re.compile(
            r"\b(?:cryptography|information\s+security|network\s+security|\brsa\b|\baes\b|"
            r"\btls\b|\bssl\b|public[-\s]?key|digital\s+signatures?|intrusion\s+detection|"
            r"\bnids\b|encryption|diffie[-\s]?hellman|\bhmac\b|x\.?509|access\s+control)\b",
            re.I,
        ),
    ),
    (
        "software_eng",
        "Software Engineering",
        re.compile(
            r"\b(?:software\s+engineering|\bsdlc\b|agile\s+methodology|scrum|waterfall\s+model|"
            r"requirements\s+engineering|\buml\b|design\s+patterns?|solid\s+principles?|"
            r"unit\s+testing|integration\s+testing|refactoring|technical\s+debt|"
            r"coupling\s+and\s+cohesion|software\s+architecture|continuous\s+integration)\b",
            re.I,
        ),
    ),
    (
        "architecture",
        "Computer Architecture",
        re.compile(
            r"\b(?:computer\s+architecture|computer\s+organization|cpu\s+pipelin(?:e|ing)|"
            r"pipeline\s+hazards?|data\s+hazards?|control\s+hazards?|structural\s+hazards?|"
            r"branch\s+prediction|branch\s+target\s+buffer|cache\s+coherence|cache\s+hierarchy|"
            r"\bisa\b|\brisc\b|\bcisc\b|\balu\b|superscalar|tomasulo|instruction\s+cycle)\b",
            re.I,
        ),
    ),
)

_DOMAIN_LABEL_TO_KEY: dict[str, str] = {
    label.lower(): key for key, label, _ in _KNOWLEDGE_AREA_SPECS
}

_QUESTION_TEMPLATES: tuple[str, ...] = (
    "Explain {label} and how it works.",
    "What are the foundational ideas behind {label}?",
    "Walk through how {label} is used in practice.",
    "What should I review before studying {label}?",
)


def classify_domain_best(
    doc_text: str,
    label_text: str,
    summary_text: str = "",
    explicit_domain: str = "",
) -> str:
    """Score all 12 domains with word-boundary regexes and return the best domain key."""
    best_key = ""
    best_score = 0
    for key, _label, pattern in _KNOWLEDGE_AREA_SPECS:
        score = (
            len(pattern.findall(doc_text)) * DOC_MATCH_WEIGHT
            + len(pattern.findall(label_text)) * LABEL_MATCH_WEIGHT
            + len(pattern.findall(summary_text)) * SUMMARY_MATCH_WEIGHT
        )
        if score > best_score:
            best_score = score
            best_key = key
    if best_key:
        return best_key
    norm_explicit = (explicit_domain or "").strip().lower()
    return _DOMAIN_LABEL_TO_KEY.get(norm_explicit, "")


def _classify_text_area(text: str) -> str:
    cleaned = (text or "").replace("_", " ").replace("/", " ")
    return classify_domain_best("", cleaned, "")


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
        if any(m in doc_id for m in _OPEN_ACCESS_DOC_MARKERS) and not doc_id.startswith("upload_"):
            return True
    return False


def _node_area(cid: str, node: dict[str, Any]) -> str:
    label = str(node.get("label") or node.get("name") or cid).strip()
    summary = str(node.get("summary") or "")
    doc_ids = " ".join(
        str(s.get("doc_id") or "").replace("_", " ").replace("/", " ")
        for s in (node.get("sources") or [])
        if isinstance(s, dict)
    )
    return classify_domain_best(
        doc_ids,
        f"{cid.replace('_', ' ')} {label}",
        summary[:SUMMARY_PREVIEW_CHARS],
        explicit_domain=str(node.get("domain") or ""),
    )


def discover_domain_coverage(graph: Any) -> dict[str, list[dict[str, Any]]]:
    """Classify live corpus & graph into full-text, graph-only, and unavailable tiers."""
    nodes = getattr(graph, "nodes", None) or {}
    open_only = is_open_access_profile()
    area_labels = {key: label for key, label, _ in _KNOWLEDGE_AREA_SPECS}
    area_concepts: dict[str, list[tuple[int, str]]] = {k: [] for k, _, _ in _KNOWLEDGE_AREA_SPECS}
    area_docs: dict[str, set[str]] = {k: set() for k, _, _ in _KNOWLEDGE_AREA_SPECS}

    for path in _open_corpus_paths():
        dom = classify_domain_best(path.replace("_", " ").replace("/", " "), "")
        if dom:
            area_docs[dom].add(path)

    for cid, node in nodes.items():
        if not isinstance(node, dict) or not _node_is_supported(node, open_only=open_only):
            continue
        dom = _node_area(cid, node)
        if not dom:
            continue
        label = str(node.get("label") or node.get("name") or cid).strip()
        weight = int(node.get("source_count") or len(node.get("sources") or [])) + int(
            node.get("degree") or 0
        )
        area_concepts[dom].append((weight, label))

    full_text: list[dict[str, Any]] = []
    graph_only: list[dict[str, Any]] = []
    unavailable: list[dict[str, Any]] = []

    for key, _label, _pat in _KNOWLEDGE_AREA_SPECS:
        concepts = area_concepts[key]
        docs = area_docs[key]
        concepts.sort(key=lambda item: (-item[0], item[1].lower()))
        entry = {
            "key": key,
            "label": area_labels[key],
            "concept_count": len(concepts),
            "doc_count": len(docs),
            "sample_concepts": [lbl for _, lbl in concepts[:MAX_SAMPLE_CONCEPTS]],
        }
        if docs:
            entry["coverage_tier"] = "full_text"
            full_text.append(entry)
        elif concepts:
            entry["coverage_tier"] = "graph_only"
            graph_only.append(entry)
        else:
            entry["coverage_tier"] = "unavailable"
            unavailable.append(entry)

    full_text.sort(key=lambda item: (-item["concept_count"], -item["doc_count"], item["label"]))
    graph_only.sort(key=lambda item: (-item["concept_count"], item["label"]))
    for idx, item in enumerate(full_text, start=1):
        item["index"] = idx
    for idx, item in enumerate(graph_only, start=len(full_text) + 1):
        item["index"] = idx

    return {"full_text": full_text, "graph_only": graph_only, "unavailable": unavailable}


def discover_knowledge_areas(graph: Any) -> list[dict[str, Any]]:
    """Derive numbered knowledge areas from the actual graph and open corpus inventory."""
    coverage = discover_domain_coverage(graph)
    populated = list(coverage["full_text"]) + list(coverage["graph_only"])
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

    candidates: list[tuple[str, str, str]] = []
    for cid, node in sorted(nodes.items()):
        if not isinstance(node, dict) or not _node_is_supported(node, open_only=open_only):
            continue
        label = str(node.get("label") or node.get("name") or cid).strip()
        area = _node_area(cid, node) or "general"
        candidates.append((area, cid, label))

    if not candidates:
        return []

    rng.shuffle(candidates)
    selected_questions: list[str] = []
    used_areas: set[str] = set()
    used_cids: set[str] = set()

    for area, cid, label in candidates:
        if len(selected_questions) >= clamped:
            break
        if area in used_areas or cid in used_cids:
            continue
        used_areas.add(area)
        used_cids.add(cid)
        selected_questions.append(rng.choice(_QUESTION_TEMPLATES).format(label=label))

    for _area, cid, label in candidates:
        if len(selected_questions) >= clamped:
            break
        if cid in used_cids:
            continue
        used_cids.add(cid)
        selected_questions.append(rng.choice(_QUESTION_TEMPLATES).format(label=label))

    return selected_questions


def generate_question_bank(
    graph: Any,
    *,
    size: int = QUESTION_BANK_SIZE,
    seed: int = DEFAULT_BANK_SEED,
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
        area = _node_area(cid, node) or "general"
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
    "DEFAULT_BANK_SEED",
    "DEFAULT_SUGGESTION_COUNT",
    "MAX_SUGGESTION_COUNT",
    "MIN_SUGGESTION_COUNT",
    "NON_AI_FALLBACK_SUGGESTION_COUNT",
    "QUESTION_BANK_SIZE",
    "build_suggestions_payload",
    "classify_domain_best",
    "discover_domain_coverage",
    "discover_knowledge_areas",
    "generate_question_bank",
    "generate_starter_questions",
    "sample_fallback_questions",
]
