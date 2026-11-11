"""Static tables and reply constants for the hosted librarian engine.

One concern: every literal value the engine needs that is not ``0``, ``1`` or
``-1`` lives here as a named constant, so the routing and rendering modules read
as prose rather than as a wall of data.
"""

from __future__ import annotations

from pathlib import Path

# ``HERE`` is the ``host_inference`` directory (the package's parent), not the
# package directory, so cache and graph lookups stay where they always were.
_HERE = Path(__file__).resolve().parent.parent
HERE = _HERE

# Local hashed embedder dimension and the similarity below which a query is
# treated as out of domain.
DIM = 384
KILL_SWITCH = 0.75

# Every citation line the grounded text can emit.  The streaming layer keeps
# these lines out of the model prompt and re-appends them verbatim so the
# reader always gets a working page link even when the LLM paraphrases.
CITATION_LINE_PREFIXES = ("**Paper page.**", "**Hugging Face page.**", "**Pearson ", "[", "→ ")

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

# A curriculum request for a legitimate syllabus topic we have not indexed yet.
# Deliberately different from OOD_MESSAGE: the student is *not* off-topic, the
# library simply has not ingested that node. Telling someone studying for an
# exam that their topic "falls outside the scope" is misleading and erodes
# trust in every other answer we give.
UNINDEXED_CURRICULUM_MESSAGE = (
    "**{subject}** is a recognised subject area, but the library has not indexed a "
    "concept node for it yet, so I cannot ground a lesson or roadmap in retrieved text.\n\n"
    "I will not invent a curriculum for a topic I cannot cite. If you upload the "
    "textbook chapter or syllabus, the librarian can ingest it and this assistant "
    "will build the prerequisite graph from your own course material.\n\n"
    "Indexed subjects you can explore include Operating Systems, Database Systems, "
    "Data Structures & Algorithms, Computer Networks, Compilers, and AI & Machine Learning."
)

ALIASES = {
    "lora": "low_rank_adaptation",
    "low-rank adaptation": "low_rank_adaptation",
    "low rank adaptation": "low_rank_adaptation",
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
    # Academic Foundations — Operating Systems
    "context switch": "context_switch",
    "context switching": "context_switch",
    "semaphore": "semaphore",
    "semaphores": "semaphore",
    "mutex": "mutex_lock",
    "mutexes": "mutex_lock",
    "mutex lock": "mutex_lock",
    "mutex locks": "mutex_lock",
    "deadlock": "deadlock",
    "deadlocks": "deadlock",
    "deadlock prevention": "deadlock_prevention",
    "condition variable": "condition_variable",
    "condition variables": "condition_variable",
    "virtual memory": "virtual_memory",
    "cpu scheduling": "cpu_scheduling",
    # Academic Foundations — DBMS & SQL
    "b tree": "b_plus_tree",
    "b trees": "b_plus_tree",
    "b plus tree": "b_plus_tree",
    "b plus trees": "b_plus_tree",
    "hash indexing": "hash_indexing",
    "hash index": "hash_indexing",
    "acid": "acid_properties",
    "acid properties": "acid_properties",
    "relational database": "relational_database",
    "relational databases": "relational_database",
    # Academic Foundations — DSA
    "bfs": "breadth_first_search",
    "breadth first search": "breadth_first_search",
    "dfs": "depth_first_search",
    "depth first search": "depth_first_search",
    # Academic Foundations — Computer Networks
    "tcp congestion control": "tcp_congestion_control",
    "congestion control": "tcp_congestion_control",
    "osi model": "osi_model",
    "osi": "osi_model",
    # Academic Foundations — Compilers & Automata
    "lexical analysis": "lexical_analysis",
    "lexer": "lexical_analysis",
    "tokenization": "lexical_analysis",
    "syntax analysis": "syntax_analysis",
    "parsing": "syntax_analysis",
    "parser": "syntax_analysis",
    "abstract syntax tree": "abstract_syntax_tree",
    "ast": "abstract_syntax_tree",
    "deterministic finite automaton": "deterministic_finite_automaton",
    "deterministic finite automata": "deterministic_finite_automaton",
    "dfa": "deterministic_finite_automaton",
    "turing machine": "turing_machine",
    "turing machines": "turing_machine",
    # Academic Foundations — Math & Machine Learning
    "matrix multiplication": "matrix_multiplication",
    "maximum likelihood estimation": "maximum_likelihood_estimation",
    "mle": "maximum_likelihood_estimation",
    "bayes theorem": "bayes_theorem",
    "bayes": "bayes_theorem",
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
    "24×7 Reading Rooms: Open continuously for enrolled students.",  # noqa: RUF001
    "Circulation / Lending Desk: Monday–Friday, 9:00 AM – 6:00 PM.",  # noqa: RUF001
    "Reference Desk Inquiries: Monday–Friday, 10:00 AM – 5:00 PM.",  # noqa: RUF001
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
