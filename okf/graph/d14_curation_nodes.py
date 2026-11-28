"""Node curation data: artifact removals, duplicate merges, and canonical alias enrichments."""

from __future__ import annotations

from dataclasses import dataclass

from .d14_curriculum_concepts import NEW_CURRICULUM_CONCEPTS, NewConceptSpec

#: Non-concept extraction artifacts removed in graph_v2_d14 (D14-DEF-020).
REMOVED_ARTIFACT_IDS: dict[str, str] = {
    "equation_only": "Malformed prompt-ablation label ('Equation Only'), not a curriculum concept.",
    "variable_compute_only": "Malformed ablation label ('Variable Compute Only'), not a concept.",
    "flow_feature_name_description": "Table column header artifact from network security PDF.",
    "fast": "Adjective extracted from FlashAttention paper title, not a standalone concept.",
    "memory_efficient": "Adjective extracted from FlashAttention paper title, not a standalone concept.",
}

#: Duplicate v1 node IDs merged into canonical v2 IDs (preserving aliases & sources).
DUPLICATE_MERGES: dict[str, str] = {
    "dpo": "direct_preference_optimization",
    "rag": "retrieval_augmented_generation",
    "maximum_likelihood": "maximum_likelihood_estimation",
    "score_matching_methods": "score_matching",
    "adversarial_generative_adversarial_net": "generative_adversarial_network",
}


@dataclass(frozen=True)
class NodeEnrichment:
    """Canonical label, domain, and alias metadata for an existing v1 concept."""

    label: str
    domain: str
    aliases: tuple[str, ...]


#: Canonical metadata & alias enrichments for existing v1 concepts (D14-DEF-004..006, 008).
NODE_ENRICHMENTS: dict[str, NodeEnrichment] = {
    "graph_attention_network": NodeEnrichment(
        "Graph Attention Network (GAT)",
        "AI & Machine Learning",
        ("gat", "gats", "graph attention network", "graph attention networks", "graph attention"),
    ),
    "kl_divergence": NodeEnrichment(
        "Kullback-Leibler Divergence",
        "Probability & Statistics",
        (
            "kl divergence",
            "kl-divergence",
            "kullback leibler divergence",
            "kullback-leibler divergence",
            "relative entropy",
        ),
    ),
    "variational_inference": NodeEnrichment(
        "Variational Inference",
        "Probability & Statistics",
        ("variational inference", "vi", "variational bayes", "elbo optimization"),
    ),
    "lalr": NodeEnrichment(
        "LALR Parsing",
        "Compilers & Languages",
        ("lalr", "lalr parsing", "lalr parser", "lalr(1)", "look-ahead lr"),
    ),
    "direct_preference_optimization": NodeEnrichment(
        "Direct Preference Optimization (DPO)",
        "AI & Machine Learning",
        ("dpo", "direct preference optimization"),
    ),
    "retrieval_augmented_generation": NodeEnrichment(
        "Retrieval-Augmented Generation (RAG)",
        "AI & Machine Learning",
        ("rag", "retrieval augmented generation", "retrieval-augmented generation"),
    ),
    "maximum_likelihood_estimation": NodeEnrichment(
        "Maximum Likelihood Estimation (MLE)",
        "Probability & Statistics",
        ("mle", "maximum likelihood", "maximum likelihood estimation", "gaussian mle"),
    ),
    "principal_component_analysis": NodeEnrichment(
        "Principal Component Analysis (PCA)",
        "Mathematics for Computing",
        ("pca", "principal component analysis", "principal components"),
    ),
    "deterministic_finite_automaton": NodeEnrichment(
        "Deterministic Finite Automaton (DFA)",
        "Automata & Computation",
        ("dfa", "deterministic finite automaton", "deterministic finite automata"),
    ),
    "nondeterministic_finite_automaton": NodeEnrichment(
        "Nondeterministic Finite Automaton (NFA)",
        "Automata & Computation",
        ("nfa", "nondeterministic finite automaton", "nondeterministic finite automata"),
    ),
    "context_free_grammar": NodeEnrichment(
        "Context-Free Grammar (CFG)",
        "Automata & Computation",
        ("cfg", "context free grammar", "context-free grammar", "context free grammars"),
    ),
    "b_plus_tree": NodeEnrichment(
        "B+ Tree",
        "Database Systems",
        ("b+ tree", "b plus tree", "b+tree", "b-plus tree"),
    ),
    "acid_properties": NodeEnrichment(
        "ACID Properties",
        "Database Systems",
        ("acid", "acid properties", "acid transactions"),
    ),
    "tcp": NodeEnrichment(
        "Transmission Control Protocol (TCP)",
        "Computer Networks",
        ("tcp", "transmission control protocol"),
    ),
    "paging": NodeEnrichment(
        "Paging",
        "Operating Systems",
        ("paging", "memory paging", "virtual memory paging"),
    ),
    "paged_attention": NodeEnrichment(
        "PagedAttention",
        "AI & Machine Learning",
        ("pagedattention", "paged attention"),
    ),
}

__all__ = [
    "DUPLICATE_MERGES",
    "NEW_CURRICULUM_CONCEPTS",
    "NODE_ENRICHMENTS",
    "REMOVED_ARTIFACT_IDS",
    "NewConceptSpec",
    "NodeEnrichment",
]
