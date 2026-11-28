"""Deterministic evidence selection without padding or neighborhood dilution.

One concern: rank and select anchor-relevant citations with a focused budget,
filter low-signal end-matter/boilerplate, respect withdrawal and metadata-only
constraints, and never pad citations to an arbitrary 10.
"""

from __future__ import annotations

import re
from typing import Any

from .access_profile import is_open_access_profile, is_pearson_url
from .corpus_titles import clean_bibliographic_title
from .docmap import hf_doc_path
from .provenance import (
    CANONICAL_CHUNK_RE,
    CLAIM_SUPPORT_NOT_ASSESSED,
    PROVENANCE_CHUNK_AMBIGUOUS,
    PROVENANCE_CHUNK_UNMATCHED,
    PROVENANCE_METADATA_ONLY,
    PROVENANCE_NO_PASSAGE,
    PROVENANCE_NONE,
    PROVENANCE_VERIFIED,
    PROVENANCE_WITHDRAWN,
    build_chunk_provenance_index,
    build_grounding_trace,
    norm_text_hash,
    verify_chunk_provenance,
)
from .source_resolution import (
    SOURCE_CAT_PEARSON,
    SOURCE_CAT_TOC_INDEX,
    is_hf_resolvable_doc,
    is_toc_or_index_doc,
    resolve_source_target,
)
from .text import tokens
from .withdrawal import is_citable_source, withdrawn_documents

# Small focused evidence budget — never pad citations to an arbitrary 10.
MAX_ANCHOR_CITATIONS = 3
# Minimum characters for a passage to be considered substantive prose.
MIN_PASSAGE_CHARS = 40
# Thresholds for detecting boilerplate / attention-vis / index / bibliography dumps.
SINGLE_WORD_LINE_MIN_LINES = 8
SINGLE_WORD_LINE_RATIO = 0.6
INDEX_ENTRY_MIN_HITS = 4
BIB_YEAR_MIN_HITS = 3
# Deterministic scoring weights for anchor source ranking.
SOURCE_OVERLAP_WEIGHT = 10
SOURCE_LATER_PAGE_BONUS = 2
CANONICAL_PAPER_BONUS = 50
UNIQUE_CHUNK_BONUS = 15
HF_RESOLVABLE_BONUS = 30
UNRESOLVABLE_DOC_PENALTY = -30
TOC_INDEX_DOC_PENALTY = -50
RAW_UPLOAD_PENALTY = -25
LOW_SIGNAL_PENALTY = -40
DOMAIN_MISMATCH_PENALTY = -120
PAGING_INTRO_FLUFF_PENALTY = -45
# Additional passages beyond rank 1 must have direct lexical relevance.
EXTRA_PASSAGE_MIN_OVERLAP = 2
SECONDARY_CONCEPT_MIN_OVERLAP = 2
TEXT_DEDUP_PREFIX_LEN = 160
# Direct catalog passage scoring when graph node sources are absent or weak.
CATALOG_TOKEN_WEIGHT = 4
CATALOG_CONCEPT_WEIGHT = 2
CATALOG_PHRASE_BONUS = 12
CATALOG_MIN_SCORE = 8
CATALOG_MIN_DISTINCTIVE_TOKENS = 2
CATALOG_PASSAGE_CHAR_LIMIT = 700

# Coarse academic domain tags for cross-domain pollution prevention.
DOMAIN_OS = "OS"
DOMAIN_DB = "DB"
DOMAIN_DSA = "DSA"
DOMAIN_NETWORKS = "NETWORKS"
DOMAIN_ML_AI = "ML_AI"
DOMAIN_MATH = "MATH"
DOMAIN_PROB_STATS = "PROB_STATS"
DOMAIN_COMPILERS = "COMPILERS"
DOMAIN_SECURITY = "SECURITY"
DOMAIN_SWE = "SWE"
DOMAIN_ARCH = "ARCH"
DOMAIN_PHYSICS_EE = "PHYSICS_EE"

# Canonical D14 12-domain string -> coarse domain tag mapping.
CANONICAL_DOMAIN_MAP: dict[str, str] = {
    "operating systems": DOMAIN_OS,
    "database systems": DOMAIN_DB,
    "data structures & algorithms": DOMAIN_DSA,
    "computer networks": DOMAIN_NETWORKS,
    "compiler design": DOMAIN_COMPILERS,
    "compilers & languages": DOMAIN_COMPILERS,
    "automata theory": DOMAIN_COMPILERS,
    "automata & computation": DOMAIN_COMPILERS,
    "mathematics for ml": DOMAIN_MATH,
    "mathematics for computing": DOMAIN_MATH,
    "probability & statistics": DOMAIN_PROB_STATS,
    "information security": DOMAIN_SECURITY,
    "ai & machine learning": DOMAIN_ML_AI,
    "software engineering": DOMAIN_SWE,
    "computer architecture": DOMAIN_ARCH,
}

_INTERDISCIPLINARY_DOMAIN_BRIDGES: tuple[frozenset[str], ...] = (
    frozenset({DOMAIN_NETWORKS, DOMAIN_SECURITY}),
    frozenset({DOMAIN_OS, DOMAIN_ARCH}),
    frozenset({DOMAIN_COMPILERS, DOMAIN_DSA}),
)


def canonical_domain_to_tag(domain_name: str) -> str | None:
    """Map a canonical D14 domain label to its coarse domain tag, or None."""
    key = (domain_name or "").strip().lower()
    return CANONICAL_DOMAIN_MAP.get(key)

_DOMAIN_TEXT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        DOMAIN_OS,
        re.compile(
            r"\b(?:operating\s+systems?|ostep|virtual\s+memory|paging|page\s+tables?|page\s+faults?|"
            r"page\s+frames?|page\s+replacement|address\s+translation|address\s+spaces?|\btlbs?\b|"
            r"translation\s+lookaside|deadlocks?|semaphores?|mutex(?:es)?|cpu\s+scheduling|"
            r"context\s+switch(?:ing)?|condition\s+variables?|segmentation|\braid\b|"
            r"log[-\s]?structured\s+file\s+system|file\s+systems?|inodes?|syscalls?|thrashing)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_DB,
        re.compile(
            r"\b(?:dbms|databases?|\bsql\b|3nf|2nf|1nf|bcnf|third\s+normal\s+form|normal\s+forms?|"
            r"normalization|acid\s+properties|\bacid\b|atomicity|durability|isolation\s+levels?|"
            r"serializability|two[-\s]?phase\s+locking|write[-\s]?ahead\s+logging|"
            r"relational\s+algebra|relational\s+databases?|b\+?\s*trees?|hash\s+indexing|"
            r"foreign\s+keys?|candidate\s+keys?|primary\s+keys?|transitive\s+dependenc(?:y|ies)|"
            r"silberschatz)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_DSA,
        re.compile(
            r"\b(?:data\s+structures?|arrays?|linked\s+lists?|priority\s+queues?|binary\s+heaps?|"
            r"min[-\s]?heaps?|max[-\s]?heaps?|heapsort|quicksort|mergesort|hash\s+tables?|"
            r"binary\s+search\s+trees?|avl\s+trees?|red[-\s]?black\s+trees?|"
            r"breadth[-\s]?first|depth[-\s]?first|\bbfs\b|\bdfs\b|dijkstra|bellman[-\s]?ford|"
            r"dynamic\s+programming|topological\s+sort|spanning\s+trees?|tries?|big[-\s]?o|"
            r"asymptotic|amortized|clrs)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_NETWORKS,
        re.compile(
            r"\b(?:computer\s+networks?|networking|network\s+architecture|network\s+topology|"
            r"protocol\s+stack|\btcp\b|\budp\b|\bosi\b|osi\s+model|"
            r"congestion\s+control|slow\s+start|congestion\s+avoidance|fast\s+recovery|"
            r"fast\s+retransmit|sliding\s+window|flow\s+control|\baimd\b|\bcwnd\b|tcp/ip|"
            r"transport\s+layer|network\s+layer|data\s+link\s+layer|physical\s+layer|"
            r"application\s+layer|packet\s+loss|three[-\s]?way\s+handshake|routing\s+protocols?|"
            r"\bdns\b|\bhttp\b|sockets?|tanenbaum|ipsec)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_ML_AI,
        re.compile(
            r"\b(?:machine\s+learning|deep\s+learning|neural\s+networks?|transformers?|"
            r"self[-\s]?attention|multi[-\s]?head\s+attention|flashattention|\bbert\b|gpt[-\s]?[234]?|"
            r"\bllms?\b|\brag\b|retrieval[-\s]?augmented|graphrag|\blora\b|\bqlora\b|\bdpo\b|\brlhf\b|"
            r"constitutional\s+ai|constitutional\s+principles?|react\s+agent|chain[-\s]?of[-\s]?thought|"
            r"backpropagation|gradient\s+descent|diffusion|\bddpm\b|\bvaes?\b|autoencoders?|\bgans?\b|"
            r"adversarial\s+nets?|\blstms?\b|\bcnns?\b|\brnns?\b|convnets?|alexnet|"
            r"graph\s+attention|\bgat\b|\bgcn\b|\bvllm\b|pagedattention|kv\s+cach(?:e|ing)|"
            r"\bbm25\b|\bdpr\b|dense\s+passage|word\s+embeddings?|fine[-\s]?tuning|"
            r"in[-\s]?context\s+learning|reinforcement\s+learning|heuristic\s+search)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_MATH,
        re.compile(
            r"\b(?:linear\s+algebra|eigenvalues?|eigenvectors?|singular\s+value|\bsvd\b|"
            r"matrix\s+decomposition|matrix\s+factorization|matrix\s+multiplication|determinants?|"
            r"jacobian|hessian|convex\s+optimization|constrained\s+optimization|"
            r"lagrange\s+multipliers?|euler\s+totient|calculus|integrals?|derivatives?|"
            r"kl\s+divergence|\bpca\b|principal\s+component|orthogonal\s+projection|"
            r"gram[-\s]?schmidt|vector\s+spaces?|cholesky)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_PROB_STATS,
        re.compile(
            r"\b(?:bayes(?:'s|\s+theorem)?|bayesian|maximum\s+likelihood|\bmle\b|"
            r"gaussian\s+(?:distribution|mle|estimation)|normal\s+distribution|"
            r"probability\s+distributions?|conditional\s+probability|posterior|prior|"
            r"variance|covariance|central\s+limit|markov\s+chain|hypothesis\s+test(?:ing)?|"
            r"random\s+variables?|expectation|log[-\s]?likelihood|bernoulli|poisson|binomial)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_COMPILERS,
        re.compile(
            r"\b(?:compilers?|lexical\s+analysis|lexers?|syntax\s+analysis|parsers?|"
            r"lalr|lr\(1\)|ll\(1\)|bottom[-\s]?up\s+pars(?:ing|er)|top[-\s]?down\s+pars(?:ing|er)|"
            r"abstract\s+syntax\s+tree|context[-\s]?free\s+grammars?|\bdfa\b|\bnfa\b|"
            r"turing\s+machines?|pumping\s+lemma|chomsky|register\s+allocation|"
            r"regular\s+languages?|finite\s+automata|decidability|halting\s+problem)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_SECURITY,
        re.compile(
            r"\b(?:cryptography|encryption|decryption|\brsa\b|\baes\b|\btls\b|\bssl\b|"
            r"diffie[-\s]?hellman|public[-\s]?key|symmetric[-\s]?key|digital\s+signature|"
            r"hash\s+functions?|sha[-\s]?256|authentication|access\s+control|cipher|"
            r"modular\s+arithmetic|information\s+security|cybersecurity|tls\s+handshake)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_SWE,
        re.compile(
            r"\b(?:software\s+engineering|solid\s+principles?|design\s+patterns?|"
            r"unit\s+test(?:ing)?|integration\s+test(?:ing)?|continuous\s+integration|"
            r"agile|scrum|refactoring|version\s+control|software\s+architecture|"
            r"dependency\s+inversion|liskov\s+substitution|single\s+responsibility)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_ARCH,
        re.compile(
            r"\b(?:computer\s+architecture|instruction\s+pipelin(?:e|ing)|pipeline\s+hazards?|"
            r"cache\s+coherence|branch\s+prediction|superscalar|out[-\s]?of[-\s]?order|"
            r"risc[-\s]?v|\bisa\b|instruction\s+set|alu|memory\s+hierarchy|mesi\s+protocol)\b",
            re.I,
        ),
    ),
    (
        DOMAIN_PHYSICS_EE,
        re.compile(
            r"\b(?:modern\s+physics|wave\s+function|quantum\s+mechanics|schrodinger|"
            r"digital\s+signal\s+processing|discrete\s+fourier|fourier\s+transform|nyquist)\b",
            re.I,
        ),
    ),
)

_DOC_DOMAIN_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (DOMAIN_OS, ("ostep_three_easy_pieces", "06_address_spaces", "07_address_translation", "08_paging", "09_tlbs", "15_raid", "16_log_structured_fs", "operating_system")),
    (DOMAIN_DB, ("silberschatz", "3nf", "database_system", "dbms", "postgresql", "sqlite")),
    (DOMAIN_NETWORKS, ("computer_networks", "tanenbaum", "data_and_computer_communications", "rfc793", "rfc9293", "peterson_davie", "dordal")),
    (DOMAIN_DSA, ("introduction_to_algorithms", "clrs", "erickson", "open_data_structures", "morin")),
    (DOMAIN_MATH, ("deisenroth", "math_for_ml", "linear_algebra", "strang", "boyd")),
    (DOMAIN_PROB_STATS, ("probability", "statistics", "think_stats", "grinstead", "openintro", "downey")),
    (DOMAIN_COMPILERS, ("compiler", "crafting_interpreters", "mogensen", "automata", "sipser", "kozen", "turing")),
    (DOMAIN_SECURITY, ("cryptography", "rfc8446", "tls", "boneh", "shoup", "owasp", "nist", "infosec")),
    (DOMAIN_SWE, ("software_engineering", "swebok", "clean_code", "pragmatic", "saasbook", "sommerville")),
    (DOMAIN_ARCH, ("computer_architecture", "riscv", "patterson", "hennessy", "nand2tetris", "pipeline")),
    (
        DOMAIN_ML_AI,
        (
            "vaswani", "devlin", "brown2020_gpt3", "yao2022_react", "velickovic2017_gat",
            "dao2022_flashattention", "upload_cb7badb2", "bai2022_constitutionalai",
            "kingma2013_vae", "goodfellow2014_gan", "hu2021_lora", "dettmers2023_qlora",
            "lewis2020_rag", "edge2024_graphrag", "rafailov2023_dpo", "ouyang2022_instructgpt",
            "wei2022_chainofthought", "ho2020_ddpm", "hochreiter1997_lstm", "kipf2016_gcn",
            "krizhevsky2012_alexnet", "lecun1998_convnets", "karpukhin2020_dpr",
            "bahdanau2014_attention", "willard2023_outlines", "rumelhart1986",
            "kwon2023_vllm", "real-time network security", "data_science_2019",
            "predictive_analytics", "knowledge_representation",
        ),
    ),
    (DOMAIN_PHYSICS_EE, ("concepts_of_modern_physics", "digital_signal_processing")),
)

# Generic academic / operation tokens that must NOT alone trigger catalog citations.
_GENERIC_QUERY_TOKENS = frozenset(
    {
        "explain", "compare", "contrast", "define", "describe", "derive", "demonstrate",
        "calculate", "compute", "walk", "through", "show", "give", "provide", "include",
        "example", "examples", "concrete", "worked", "simple", "brief", "detail", "step",
        "difference", "differences", "versus", "between", "relation", "relationship",
        "connect", "connected", "related", "their", "about", "using", "used", "work", "works",
        "properties", "property", "model", "models", "layer", "layers", "form", "forms",
        "control", "system", "systems", "method", "methods", "data", "table", "tables",
        "state", "states", "action", "actions", "fast", "slow", "basic", "general",
        "reliability", "recovery", "avoidance", "start", "order", "list", "lists", "binary",
        "structure", "structures", "mechanics", "concept", "concepts", "operating",
    }
)

_PAGING_QUERY_RE = re.compile(
    r"\b(?:paging|page\s+tables?|page\s+frames?|page\s+faults?|page\s+replacement)\b", re.I
)
_INTRO_DOC_RE = re.compile(r"(?:00_dialogue|06_address_spaces|preface|front_?matter)", re.I)


def infer_text_domains(text: str) -> set[str]:
    """Infer coarse academic domains present in ``text``."""
    raw = text or ""
    if not raw.strip():
        return set()
    return {domain for domain, pat in _DOMAIN_TEXT_PATTERNS if pat.search(raw)}


def infer_doc_domains(
    doc_id: str,
    concept_id: str = "",
    text: str = "",
    explicit_domain: str = "",
    secondary_domains: list[str] | tuple[str, ...] | None = None,
) -> set[str]:
    """Infer coarse academic domains for a candidate document/passage."""
    explicit_tags: set[str] = set()
    if explicit_domain:
        tag = canonical_domain_to_tag(explicit_domain)
        if tag:
            explicit_tags.add(tag)
    for sec in secondary_domains or ():
        tag = canonical_domain_to_tag(str(sec))
        if tag:
            explicit_tags.add(tag)
    if explicit_tags:
        return explicit_tags
    doc_lower = (doc_id or "").lower()
    found = {
        domain
        for domain, hints in _DOC_DOMAIN_HINTS
        if any(hint in doc_lower for hint in hints)
    }
    if found:
        return found
    return infer_text_domains(f"{concept_id.replace('_', ' ')} {(text or '')[:400]}")


def domains_compatible(
    query_domains: set[str],
    target_domains: set[str],
    *,
    allow_math_ml_bridge: bool = True,
) -> bool:
    """Return True when ``target_domains`` are compatible with ``query_domains``."""
    if not query_domains or not target_domains:
        return True
    if query_domains & target_domains:
        return True
    if (
        allow_math_ml_bridge
        and query_domains <= {DOMAIN_MATH, DOMAIN_PROB_STATS, DOMAIN_ML_AI}
        and target_domains <= {DOMAIN_MATH, DOMAIN_PROB_STATS, DOMAIN_ML_AI}
    ):
        return True
    for bridge in _INTERDISCIPLINARY_DOMAIN_BRIDGES:
        if (query_domains & bridge) and (target_domains & bridge):
            return True
    return False


def _distinctive_tokens(text: str) -> set[str]:
    return {tok for tok in tokens(text) if tok not in _GENERIC_QUERY_TOKENS}

_INDEX_ENTRY_RE = re.compile(r"\b[a-z][a-z\s-]{2,30},\s*\d+(?:[\u2013-]\d+)?")
_BIB_YEAR_RE = re.compile(r"\((?:19|20)\d{2}[a-z]?\)")
_FRONTMATTER_RE = re.compile(
    r"(?:book:\s*about the authors|chapter file:\s*about-the-authors|"
    r"contents\s*/\s*section headings:|table of contents\b)",
    re.I,
)

# Primary paper doc_id hints for foundational concepts so canonical primary
# sources outrank secondary passing mentions on the same concept node.
PRIMARY_PAPER_HINTS: dict[str, tuple[str, ...]] = {
    "transformer": ("vaswani",),
    "self_attention": ("vaswani",),
    "multi_head_attention": ("vaswani",),
    "bert": ("devlin",),
    "masked_language_modeling": ("devlin",),
    "rag": ("lewis",),
    "retrieval_augmented_generation": ("lewis",),
    "dpr": ("karpukhin",),
    "dense_passage_retrieval": ("karpukhin",),
    "bm25": ("karpukhin",),
    "flashattention": ("dao", "upload_cb7badb2"),
    "low_rank_adaptation": ("hu2021",),
    "qlora": ("dettmers",),
    "kv_cache": ("kwon",),
    "paged_attention": ("kwon",),
    "graph_rag": ("edge2024",),
    "paging": ("08_paging",),
    "tlb": ("09_tlbs",),
    "address_translation": ("07_address_translation",),
}


def is_low_signal_passage(text: str) -> bool:
    """True when a passage is end-matter, index, bibliography, or line-per-word dump."""
    cleaned = (text or "").strip()
    if len(cleaned) < MIN_PASSAGE_CHARS:
        return True
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if len(lines) >= SINGLE_WORD_LINE_MIN_LINES:
        single_word = sum(1 for line in lines if len(line.split()) == 1)
        if (single_word / len(lines)) >= SINGLE_WORD_LINE_RATIO:
            return True
    if _FRONTMATTER_RE.search(cleaned):
        return True
    if len(_INDEX_ENTRY_RE.findall(cleaned)) >= INDEX_ENTRY_MIN_HITS:
        return True
    return len(_BIB_YEAR_RE.findall(cleaned)) >= BIB_YEAR_MIN_HITS


def _primary_paper_bonus(cid: str, raw_doc_id: str, canonical_doc_id: str) -> int:
    hints = PRIMARY_PAPER_HINTS.get(cid, ())
    if not hints:
        return 0
    combined = f"{raw_doc_id} {canonical_doc_id}".lower()
    return CANONICAL_PAPER_BONUS if any(h in combined for h in hints) else 0


def score_source_for_concept(
    cid: str,
    concept_label: str,
    source: dict[str, Any],
    query: str,
) -> tuple[int, int]:
    """Return ``(total_score, token_overlap)`` for ranking one source passage."""
    passage = str(source.get("text_passage") or "")
    wanted = set(tokens(query)) | set(tokens(concept_label))
    overlap = len(wanted & set(tokens(passage)))
    raw_doc = str(source.get("doc_id") or "")
    canonical_doc = hf_doc_path(raw_doc)
    chunk_id = str(source.get("chunk_id") or "")
    page = int(source.get("page_number") or 0)

    total = overlap * SOURCE_OVERLAP_WEIGHT
    if page > 1:
        total += SOURCE_LATER_PAGE_BONUS
    total += _primary_paper_bonus(cid, raw_doc, canonical_doc)
    if (cid == "paging" or _PAGING_QUERY_RE.search(query or "")) and (
        "06_address_spaces" in canonical_doc.lower() or "06_address_spaces" in raw_doc.lower()
    ):
        total += PAGING_INTRO_FLUFF_PENALTY
    q_domains = infer_text_domains(f"{query} {cid.replace('_', ' ')} {concept_label}")
    d_domains = infer_doc_domains(canonical_doc or raw_doc, cid, passage)
    if not domains_compatible(q_domains, d_domains):
        total += DOMAIN_MISMATCH_PENALTY
    if CANONICAL_CHUNK_RE.match(chunk_id) and not canonical_doc.startswith("upload_"):
        total += UNIQUE_CHUNK_BONUS
    if is_toc_or_index_doc(raw_doc) or is_toc_or_index_doc(canonical_doc):
        total += TOC_INDEX_DOC_PENALTY
    elif is_hf_resolvable_doc(canonical_doc) or is_hf_resolvable_doc(raw_doc):
        total += HF_RESOLVABLE_BONUS
    else:
        total += UNRESOLVABLE_DOC_PENALTY
    if canonical_doc.startswith("upload_"):
        total += RAW_UPLOAD_PENALTY
    if is_low_signal_passage(passage):
        total += LOW_SIGNAL_PENALTY
    return total, overlap


def _dedup_key(record: dict[str, Any]) -> tuple[str, str]:
    """Canonical deduplication key — never conflates distinct chunks on the same page."""
    doc_id = str(record.get("doc_id") or record.get("url") or record.get("label") or "")
    chunk_id = str(record.get("chunk_id") or "").strip()
    if chunk_id:
        return (doc_id, chunk_id)
    text_hash = norm_text_hash(str(record.get("text_passage") or ""))
    return (doc_id, f"p{record.get('page_number')}_{text_hash}")


def _text_fingerprint(record: dict[str, Any]) -> str:
    """Normalized passage prefix to deduplicate identical uploaded copies."""
    norm = re.sub(r"\s+", " ", str(record.get("text_passage") or "").strip().lower())
    return norm[:TEXT_DEDUP_PREFIX_LEN] if norm else ""


def _ranked_live_sources(
    graph: Any,
    cid: str,
    query: str,
    retired: set[str],
) -> tuple[list[tuple[int, int, dict[str, Any]]], bool]:
    """Return live sources for ``cid`` sorted best-first, plus ``all_withdrawn``."""
    raw_sources = [
        s for s in (graph.nodes.get(cid) or {}).get("sources") or [] if isinstance(s, dict)
    ]
    if not raw_sources:
        return [], False
    live = [s for s in raw_sources if is_citable_source(s, retired)]
    if not live:
        return [], True

    label = graph.label(cid)
    q_domains = infer_text_domains(f"{query} {cid.replace('_', ' ')} {label}")
    domain_ok = [
        s
        for s in live
        if domains_compatible(
            q_domains,
            infer_doc_domains(
                hf_doc_path(str(s.get("doc_id") or "")) or str(s.get("doc_id") or ""),
                cid,
                str(s.get("text_passage") or ""),
            ),
        )
    ]
    if not domain_ok:
        return [], False

    non_low_signal = [
        s for s in domain_ok if not is_low_signal_passage(str(s.get("text_passage") or ""))
    ]
    pool = non_low_signal if non_low_signal else domain_ok

    canonical_pool = [
        s for s in pool if not hf_doc_path(str(s.get("doc_id") or "")).startswith("upload_")
    ]
    if canonical_pool:
        pool = canonical_pool

    scored = []
    for src in pool:
        total, overlap = score_source_for_concept(cid, label, src, query)
        scored.append((total, overlap, src))
    scored.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            str(item[2].get("doc_id") or ""),
            str(item[2].get("chunk_id") or ""),
        )
    )
    return scored, False


def select_evidence_citations(
    graph: Any,
    anchor_cid: str,
    query: str,
    max_citations: int = MAX_ANCHOR_CITATIONS,
) -> list[dict[str, Any]]:
    """Select anchor-relevant citations without padding or neighborhood dilution."""
    if not anchor_cid or anchor_cid not in graph.nodes:
        return []

    retired = withdrawn_documents()
    scored_anchor, all_withdrawn = _ranked_live_sources(graph, anchor_cid, query, retired)
    if all_withdrawn:
        return [graph.cite_record(anchor_cid, query, index=1)]

    collected: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    seen_texts: set[str] = set()

    def _try_append(cid: str, src: dict[str, Any]) -> bool:
        rec = graph.cite_record(cid, query, index=len(collected) + 1, source_override=src)
        if not (rec.get("label") or rec.get("doc_id") or rec.get("url")):
            return False
        dkey = _dedup_key(rec)
        tfp = _text_fingerprint(rec)
        if dkey in seen_keys or (tfp and tfp in seen_texts):
            return False
        seen_keys.add(dkey)
        if tfp:
            seen_texts.add(tfp)
        collected.append(rec)
        return True

    primary_doc = ""
    is_paging_query = anchor_cid == "paging" or bool(_PAGING_QUERY_RE.search(query or ""))
    for rank_idx, (total_score, overlap, src) in enumerate(scored_anchor):
        if len(collected) >= max_citations:
            break
        src_doc = hf_doc_path(str(src.get("doc_id") or ""))
        if is_paging_query and "06_address_spaces" in src_doc.lower() and collected:
            continue
        if rank_idx == 0:
            if _try_append(anchor_cid, src):
                primary_doc = src_doc
            continue
        if total_score < 0 or overlap < EXTRA_PASSAGE_MIN_OVERLAP:
            continue
        if PRIMARY_PAPER_HINTS.get(anchor_cid) and primary_doc and src_doc != primary_doc:
            continue
        _try_append(anchor_cid, src)

    anchor_domains = infer_text_domains(
        f"{query} {anchor_cid.replace('_', ' ')} {graph.label(anchor_cid)}"
    )
    if collected and len(collected) < max_citations:
        for other_cid in graph.phrase_hits(query):
            if len(collected) >= max_citations:
                break
            if other_cid == anchor_cid or other_cid not in graph.nodes:
                continue
            other_domains = infer_text_domains(
                f"{other_cid.replace('_', ' ')} {graph.label(other_cid)}"
            )
            if not domains_compatible(anchor_domains, other_domains):
                continue
            other_scored, other_withdrawn = _ranked_live_sources(graph, other_cid, query, retired)
            if other_withdrawn or not other_scored:
                continue
            _score, overlap, src = other_scored[0]
            if _score >= 0 and overlap >= SECONDARY_CONCEPT_MIN_OVERLAP:
                _try_append(other_cid, src)

    return collected


def _query_bigrams(raw: str) -> list[str]:
    words = re.findall(r"[a-z0-9]{2,}", (raw or "").lower())
    out: list[str] = []
    for idx in range(len(words) - 1):
        w1, w2 = words[idx], words[idx + 1]
        if w1 in _GENERIC_QUERY_TOKENS and w2 in _GENERIC_QUERY_TOKENS:
            continue
        out.append(f"{w1} {w2}")
    return out


_MATH_EXPLANATORY_RE = re.compile(
    r"(?:\b(?:posterior|prior|likelihood|log[-\s]?likelihood|gaussian|normal\s+distribution|"
    r"covariance\s+matrix|eigenvector|eigenvalue|principal\s+component|variance|orthogonal|"
    r"page\s+table|virtual\s+page\s+number|physical\s+frame|page\s+offset|vpn|pfn|"
    r"defined\s+as|theorem|derivation)\b|[=∑∏∫≈])",
    re.I,
)
_INTRO_SECTION_TITLE_RE = re.compile(
    r"\b(?:table\s+of\s+contents|contents|references|bibliography|index|preface|"
    r"acknowledg(?:e)?ments|about\s+the\s+authors|dialogue)\b",
    re.I,
)
EXPLANATORY_PASSAGE_BONUS = 10
INTRO_SECTION_PENALTY = -35
NON_BODY_CLASS_PENALTY = -45
HYBRID_RANK_WEIGHT = 20.0


def _build_catalog_citation(
    entry: dict[str, Any],
    anchor_cid: str,
    index: int,
    chunk_index: dict[tuple[str, str], dict[str, Any]] | None,
    *,
    retrieval_method: str = "bm25_lexical",
    retrieval_score: float | None = None,
) -> dict[str, Any]:
    raw_doc_id = str(entry.get("doc_id") or "").strip()
    doc_id = hf_doc_path(raw_doc_id)
    page_val = entry.get("page")
    page_int = int(page_val) if isinstance(page_val, int) and page_val > 0 else 1
    chunk_id = str(entry.get("passage_id") or entry.get("chunk_id") or "").strip() or None
    entry_title = str(entry.get("source_title") or "").strip()
    resolved = resolve_source_target(
        raw_doc_id=raw_doc_id,
        canonical_doc_id=doc_id,
        page_number=page_int,
        title=entry_title,
        all_withdrawn=False,
    )
    source_category = str(resolved["source_category"])
    source_type = str(resolved["source_type"])
    reader_resolvable = bool(resolved["reader_resolvable"])
    page = resolved["page_number"]
    hf_url = str(resolved["url"] or "")
    doc_title = entry_title or resolved["resolved_title"] or (doc_id.split("/")[-1] if doc_id else "")
    if not resolved["is_pearson"] and not entry_title and (doc_id or doc_title):
        doc_title = clean_bibliographic_title(doc_id, doc_title)
    if not doc_title:
        label = ""
    elif source_category == SOURCE_CAT_PEARSON and hf_url:
        label = f"[S{index}: {doc_title} (Pearson catalogue-only — institutional login)]"
    elif source_category == SOURCE_CAT_TOC_INDEX:
        label = f"[S{index}: {doc_title} (TOC/index metadata only)]"
    elif hf_url:
        label = f"[S{index}: {doc_title}{f', #page={page}' if page else ''}]"
    else:
        label = f"[S{index}: {doc_title} (source unavailable — metadata only)]"

    passage_text = str(entry.get("text") or "")[:CATALOG_PASSAGE_CHAR_LIMIT]
    provenance = verify_chunk_provenance(
        raw_doc_id=raw_doc_id,
        canonical_doc_id=doc_id,
        chunk_id=chunk_id,
        page_number=page,
        hf_url=hf_url,
        text_passage=passage_text,
        all_withdrawn=False,
        chunk_index=chunk_index,
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
        "concept_id": str(entry.get("concept_id") or anchor_cid),
        "doc_id": doc_id,
        "chunk_id": chunk_id,
        "canonical_passage_id": provenance["canonical_passage_id"],
        "provenance_status": provenance["provenance_status"],
        "chunk_provenance_match": provenance["chunk_provenance_match"],
        "claim_support_status": provenance["claim_support_status"],
        "doc_title": doc_title,
        "authors": str(entry.get("authors") or ""),
        "page_number": page,
        "printed_page": entry.get("printed_page"),
        "pdf_url": hf_url,
        "url": hf_url,
        "withdrawn": False,
        "notice": "",
        "text_passage": passage_text,
        "passage": passage_text,
        "section": entry.get("section_title") or None,
        "domain": str(entry.get("domain") or ""),
        "corpus_version": str(entry.get("corpus_version") or ""),
        "retrieval_method": retrieval_method,
        "retrieval_score": retrieval_score,
        "doi": None,
        "publication_year": None,
        "source_provider": None,
        "retrieved_at": None,
        "verification_status": provenance["verification_status"],
        "status_level": provenance["status_level"],
        "access_status": str(resolved["access_status"]),
    }


def _hybrid_scores_by_index(
    catalog: Any,
    passages: list[dict[str, Any]],
    query: str,
    allowed_indices: set[int],
    top_k: int,
) -> tuple[dict[int, float], str]:
    """Run BM25 or genuine hybrid BM25+dense RRF over eligible passage indices."""
    if not allowed_indices:
        return {}, "bm25_lexical"
    retriever = None
    getter = getattr(catalog, "get_retriever", None)
    if callable(getter):
        retriever = getter()
    if retriever is None:
        try:
            from archipelago.inference.dense_retriever import HybridPassageRetriever

            retriever = HybridPassageRetriever(passages)
        except ImportError:
            return {}, "bm25_lexical"
    result = retriever.retrieve(
        query,
        top_k=max(top_k * 6, 24),
        allowed_indices=allowed_indices,
    )
    if not result.hits:
        return {}, result.method
    max_sc = max((h.score for h in result.hits), default=1.0) or 1.0
    id_to_idx = {id(p): idx for idx, p in enumerate(passages)}
    score_map: dict[int, float] = {}
    for hit in result.hits:
        idx = id_to_idx.get(id(hit.passage))
        if idx is not None:
            score_map[idx] = (hit.score / max_sc) * HYBRID_RANK_WEIGHT
    return score_map, result.method


def select_catalog_passages(
    catalog: Any,
    query: str,
    concept_label: str = "",
    anchor_cid: str = "",
    max_citations: int = MAX_ANCHOR_CITATIONS,
    open_access_only: bool | None = None,
    chunk_index: dict[tuple[str, str], dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Rank indexed ``catalog.passages`` with domain-aware lexical + hybrid gating.

    Works independently of whether a graph node exists (``anchor_cid=""``).
    Returns ``[]`` honestly when no passage clears domain compatibility and
    distinctive relevance thresholds; never pads citations.
    """
    passages = list(getattr(catalog, "passages", None) or [])
    if not passages or max_citations <= 0:
        return []

    dq_toks = _distinctive_tokens(query)
    dc_toks = _distinctive_tokens(f"{anchor_cid.replace('_', ' ')} {concept_label}")
    q_toks = dq_toks if dq_toks else set(tokens(query))
    c_toks = dc_toks if dc_toks else set(tokens(f"{anchor_cid.replace('_', ' ')} {concept_label}"))
    bigrams = list(dict.fromkeys(_query_bigrams(query) + _query_bigrams(concept_label)))
    if not (q_toks or c_toks or bigrams):
        return []

    query_domains = infer_text_domains(f"{query} {anchor_cid.replace('_', ' ')} {concept_label}")
    is_paging_query = anchor_cid == "paging" or bool(_PAGING_QUERY_RE.search(query or ""))
    retired = withdrawn_documents()
    oa_mode = is_open_access_profile() if open_access_only is None else open_access_only

    eligible: list[tuple[int, dict[str, Any], str, str, set[str]]] = []
    for idx, entry in enumerate(passages):
        if not isinstance(entry, dict):
            continue
        raw_doc = str(entry.get("doc_id") or "").strip()
        if not raw_doc:
            continue
        canon_doc = hf_doc_path(raw_doc)
        if not is_citable_source({"doc_id": raw_doc}, retired):
            continue
        if is_toc_or_index_doc(raw_doc) or is_toc_or_index_doc(canon_doc):
            continue
        if oa_mode and (
            is_pearson_url(raw_doc)
            or "pearson" in raw_doc.lower()
            or "pearson" in canon_doc.lower()
        ):
            continue
        text = str(entry.get("text") or "")
        if is_low_signal_passage(text):
            continue
        structural_cls = str(entry.get("structural_class") or "BODY").upper()
        if structural_cls in {"TOC", "REFERENCES", "INDEX", "FRONT_MATTER"}:
            continue
        doc_domains = infer_doc_domains(
            canon_doc or raw_doc,
            str(entry.get("concept_id") or ""),
            text,
            explicit_domain=str(entry.get("domain") or ""),
            secondary_domains=entry.get("secondary_domains"),
        )
        if not domains_compatible(query_domains, doc_domains):
            continue
        eligible.append((idx, entry, raw_doc, canon_doc, doc_domains))

    if not eligible:
        return []

    allowed_indices = {idx for idx, *_ in eligible}
    retrieval_query = f"{query} {concept_label}".strip()
    hybrid_scores, retrieval_method = _hybrid_scores_by_index(
        catalog, passages, retrieval_query, allowed_indices, max_citations
    )

    scored: list[tuple[float, dict[str, Any]]] = []
    for idx, entry, raw_doc, canon_doc, doc_domains in eligible:
        text = str(entry.get("text") or "")
        doc_tokens = set(entry.get("tokens") or tokens(text))
        doc_lower = text.lower()
        q_overlap = len(q_toks & doc_tokens)
        c_overlap = len(c_toks & doc_tokens)
        phrase_hits = sum(1 for bg in bigrams if bg in doc_lower)
        score = float(
            q_overlap * CATALOG_TOKEN_WEIGHT
            + c_overlap * CATALOG_CONCEPT_WEIGHT
            + phrase_hits * CATALOG_PHRASE_BONUS
        )
        score += hybrid_scores.get(idx, 0.0)
        score += float(_primary_paper_bonus(anchor_cid, raw_doc, canon_doc))
        section_title = str(entry.get("section_title") or "")
        if _INTRO_SECTION_TITLE_RE.search(section_title) or "00_dialogue" in raw_doc.lower():
            score += INTRO_SECTION_PENALTY
        if _MATH_EXPLANATORY_RE.search(text):
            score += EXPLANATORY_PASSAGE_BONUS
        if is_paging_query:
            if "08_paging" in canon_doc.lower() or "08_paging" in raw_doc.lower():
                score += CANONICAL_PAPER_BONUS
            elif _INTRO_DOC_RE.search(canon_doc) or _INTRO_DOC_RE.search(raw_doc):
                score += PAGING_INTRO_FLUFF_PENALTY

        single_term_ok = len(q_toks) == 1 and q_overlap == 1 and bool(query_domains & doc_domains)
        has_distinctive_match = (
            phrase_hits >= 1
            or q_overlap >= CATALOG_MIN_DISTINCTIVE_TOKENS
            or single_term_ok
            or (retrieval_method == "hybrid_bm25_dense_rrf" and idx in hybrid_scores and q_overlap >= 1)
        )
        if score >= CATALOG_MIN_SCORE and has_distinctive_match:
            scored.append((score, entry))

    scored.sort(
        key=lambda item: (
            -item[0],
            str(item[1].get("doc_id") or ""),
            int(item[1].get("page") or 0),
            str(item[1].get("passage_id") or ""),
        )
    )

    collected: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str]] = set()
    seen_texts: set[str] = set()
    for final_score, entry in scored:
        if len(collected) >= max_citations:
            break
        rec = _build_catalog_citation(
            entry,
            anchor_cid,
            len(collected) + 1,
            chunk_index,
            retrieval_method=retrieval_method,
            retrieval_score=round(final_score, 4),
        )
        dkey = _dedup_key(rec)
        tfp = _text_fingerprint(rec)
        if dkey in seen_keys or (tfp and tfp in seen_texts):
            continue
        if oa_mode and rec.get("is_pearson"):
            continue
        seen_keys.add(dkey)
        if tfp:
            seen_texts.add(tfp)
        collected.append(rec)
    return collected


__all__ = [
    "CANONICAL_DOMAIN_MAP",
    "CLAIM_SUPPORT_NOT_ASSESSED",
    "DOMAIN_ARCH",
    "DOMAIN_COMPILERS",
    "DOMAIN_DB",
    "DOMAIN_DSA",
    "DOMAIN_MATH",
    "DOMAIN_ML_AI",
    "DOMAIN_NETWORKS",
    "DOMAIN_OS",
    "DOMAIN_PHYSICS_EE",
    "DOMAIN_PROB_STATS",
    "DOMAIN_SECURITY",
    "DOMAIN_SWE",
    "MAX_ANCHOR_CITATIONS",
    "PRIMARY_PAPER_HINTS",
    "PROVENANCE_CHUNK_AMBIGUOUS",
    "PROVENANCE_CHUNK_UNMATCHED",
    "PROVENANCE_METADATA_ONLY",
    "PROVENANCE_NONE",
    "PROVENANCE_NO_PASSAGE",
    "PROVENANCE_VERIFIED",
    "PROVENANCE_WITHDRAWN",
    "build_chunk_provenance_index",
    "build_grounding_trace",
    "canonical_domain_to_tag",
    "domains_compatible",
    "infer_doc_domains",
    "infer_text_domains",
    "is_low_signal_passage",
    "score_source_for_concept",
    "select_catalog_passages",
    "select_evidence_citations",
    "verify_chunk_provenance",
]
