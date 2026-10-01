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
CITATION_LINE_PREFIXES = ("**Paper page.**", "**Hugging Face page.**", "**Pearson ")

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
