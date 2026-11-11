"""Grounded concept seed records for the SoFerence pilot."""

from __future__ import annotations

# ── Seed catalog ──────────────────────────────────────────────────────────
SEEDS: list[dict] = [
    {
        "id": "ai_agent",
        "name": "AI Agent",
        "concept_type": "method",
        "difficulty": "intermediate",
        "summary": (
            "An AI agent is an autonomous system that perceives its environment, "
            "maintains internal state, and selects actions to achieve goals. "
            "Agent architectures range from stimulus-response and planning agents "
            "to multi-level (three-level) designs with reactive, executive, and "
            "deliberative layers (Nilsson, Artificial Intelligence: A New Synthesis)."
        ),
        "requires": ["reinforcement_learning"],
        "unlocks": [],
        "aliases_note": "agent, ai agent, intelligent agent",
        "pdfs": [
            (
                "archipelago-books-cs/artificial_intelligence_a_new_synthesis_1998/"
                "25---Agent-Architectures_1998_Artificial-Intelligence--A-New-Synthesis.pdf",
                [1, 2, 3],
            ),
            (
                "archipelago-books-cs/artificial_intelligence_a_new_synthesis_1998/"
                "2---Stimulus-Response-Agents_1998_Artificial-Intelligence--A-New-Synthesis.pdf",
                [1, 2],
            ),
        ],
    },
    {
        "id": "paging",
        "name": "Paging",
        "concept_type": "method",
        "difficulty": "intermediate",
        "summary": (
            "Paging divides virtual address spaces into fixed-size pages mapped to "
            "physical page frames via a page table. It simplifies free-space management "
            "versus variable-size segmentation and is foundational for virtual memory "
            "(OSTEP, Three Easy Pieces — Paging)."
        ),
        "requires": [],
        "unlocks": ["paged_attention"],
        "pdfs": [
            ("archipelago-books-cs/ostep_three_easy_pieces/08_Paging.pdf", [1, 2, 3]),
            ("archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf", [1, 2]),
        ],
    },
    {
        "id": "virtual_memory",
        "name": "Virtual Memory",
        "concept_type": "method",
        "difficulty": "intermediate",
        "summary": (
            "Virtual memory gives each process an abstract address space, typically "
            "implemented with paging and/or segmentation, isolating processes and "
            "allowing more memory than physically present via demand loading."
        ),
        "requires": [],
        "unlocks": ["paging"],
        "pdfs": [
            ("archipelago-books-cs/ostep_three_easy_pieces/06_Address_Spaces.pdf", [1, 2, 3]),
            ("archipelago-books-cs/ostep_three_easy_pieces/07_Address_Translation.pdf", [1, 2]),
        ],
    },
    {
        "id": "paged_attention",
        "name": "PagedAttention",
        "concept_type": "method",
        "difficulty": "advanced",
        "summary": (
            "PagedAttention manages the KV cache of transformer LLMs like OS virtual "
            "memory: logical KV blocks map to non-contiguous physical blocks, reducing "
            "fragmentation and enabling higher batch throughput in vLLM "
            "(Kwon et al., 2023)."
        ),
        "requires": ["paging", "attention_mechanism", "self_attention"],
        "unlocks": ["vllm"],
        "pdfs": [
            ("papers/Kwon2023_vLLM.pdf", [1, 2, 3, 4]),
        ],
    },
    {
        "id": "vllm",
        "name": "vLLM",
        "concept_type": "system",
        "difficulty": "advanced",
        "summary": (
            "vLLM is a high-throughput LLM serving system that uses PagedAttention for "
            "efficient KV-cache memory management, continuous batching, and reduced "
            "waste from reservation and fragmentation (Kwon et al., SOSP 2023)."
        ),
        "requires": ["paged_attention", "paging"],
        "unlocks": [],
        "pdfs": [
            ("papers/Kwon2023_vLLM.pdf", [1, 2, 3, 5]),
        ],
    },
    {
        "id": "qlora",
        "name": "QLoRA",
        "concept_type": "method",
        "difficulty": "advanced",
        "summary": (
            "QLoRA finetunes quantized LLMs by freezing a 4-bit (NF4) base model and "
            "learning LoRA adapters in higher precision, with double quantization and "
            "paged optimizers to fit 65B models on a single 48GB GPU "
            "(Dettmers et al., 2023)."
        ),
        "requires": ["low_rank_adaptation"],
        "unlocks": [],
        "pdfs": [
            ("papers/Dettmers2023_QLoRA.pdf", [1, 2, 3]),
        ],
    },
    {
        "id": "third_normal_form",
        "name": "Third Normal Form (3NF)",
        "concept_type": "method",
        "difficulty": "intermediate",
        "summary": (
            "Third Normal Form (3NF) is a relational database normal form: a relation "
            "is in 3NF if it is in 2NF and no non-prime attribute is transitively "
            "dependent on a candidate key. It reduces update anomalies by eliminating "
            "transitive dependencies (classic DBMS / Silberschatz curriculum)."
        ),
        "requires": ["sql"],
        "unlocks": [],
        "pdfs": [],  # grounded summary; shelf card below
        "shelf": {
            "call_no": "005.74 SIL",
            "title": "Database System Concepts (Silberschatz et al.)",
            "rack": "CS-DBMS / Rack B3",
            "status": "available (pilot shelf seed)",
        },
        "hand_chunks": [
            {
                "page": 1,
                "doc_id": "pilot/silberschatz_3nf_card.txt",
                "title": "Database System Concepts — 3NF pilot card",
                "text": (
                    "A relation schema R is in third normal form (3NF) if for every "
                    "functional dependency X → A that holds over R, either X is a "
                    "superkey of R, or A is a prime attribute of R. 3NF eliminates "
                    "transitive dependencies of non-prime attributes on candidate keys, "
                    "reducing insertion, update, and deletion anomalies while remaining "
                    "dependency-preserving more often than BCNF."
                ),
            }
        ],
    },
]
