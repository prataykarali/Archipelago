"""Curated invalid edge removal rules for graph_v2_d14 (D14-DEF-010..018 & DAG fixes)."""

from __future__ import annotations

from .d14_schema import REL_ENABLES, REL_REQUIRES

#: Explicit invalid edges removed from graph_v2_d14 (post-canonicalization IDs).
#: Key: (from_id, to_id, normalized_relation_or_wildcard) -> (defect_id, rationale).
INVALID_EDGE_REMOVALS: dict[tuple[str, str, str], tuple[str, str]] = {
    ("probability_distribution", "neural_network", REL_REQUIRES): (
        "D14-DEF-010",
        "Probability distribution is foundational to neural networks, not dependent on them.",
    ),
    ("neural_network", "probability_distribution", REL_ENABLES): (
        "D14-DEF-010",
        "Inverted pedagogical direction; probability distributions precede neural networks.",
    ),
    ("neural_network", "maximum_likelihood_estimation", "*"): (
        "D14-DEF-010",
        "MLE precedes neural networks; neural networks are not a prerequisite for MLE.",
    ),
    ("maximum_likelihood_estimation", "neural_network", REL_REQUIRES): (
        "D14-DEF-010",
        "MLE is a general statistical estimator and does not require neural networks.",
    ),
    ("neural_network", "graph_convolutional_network", REL_REQUIRES): (
        "D14-DEF-010",
        "Inverted dependency: GCN requires Neural Network, not vice versa.",
    ),
    ("graph_convolutional_network", "neural_network", REL_ENABLES): (
        "D14-DEF-010",
        "Inverted dependency: Neural Network enables GCN, not vice versa.",
    ),
    ("direct_preference_optimization", "reinforcement_learning", REL_ENABLES): (
        "D14-DEF-011",
        "DPO does not unlock Reinforcement Learning; DPO contrasts with RLHF/RL.",
    ),
    ("direct_preference_optimization", "reward_function", REL_REQUIRES): (
        "D14-DEF-011",
        "DPO eliminates explicit reward-model training via closed-form reparameterization.",
    ),
    ("direct_preference_optimization", "gpt_4", REL_REQUIRES): (
        "D14-DEF-011",
        "DPO is a general preference optimization objective and does not require GPT-4.",
    ),
    ("gpt_4", "direct_preference_optimization", REL_ENABLES): (
        "D14-DEF-011",
        "GPT-4 is an evaluation judge in the DPO paper, not a prerequisite for DPO.",
    ),
    ("gpt", "direct_preference_optimization", REL_ENABLES): (
        "D14-DEF-011",
        "Specific model family GPT does not define a hard prerequisite for DPO.",
    ),
    ("neural_network", "attention_mechanism", REL_REQUIRES): (
        "D14-DEF-012",
        "Inverted dependency: Attention Mechanism builds on Neural Networks, not vice versa.",
    ),
    ("attention_mechanism", "neural_network", REL_ENABLES): (
        "D14-DEF-012",
        "Inverted dependency: Neural Networks enable Attention Mechanisms, not vice versa.",
    ),
    ("regular_expression", "autonomous_system", "*"): (
        "D14-DEF-013",
        "Spurious lexical-collision edge connecting formal languages to autonomous systems.",
    ),
    ("partial_regular_expression", "autonomous_system", "*"): (
        "D14-DEF-013",
        "Spurious lexical-collision edge connecting formal languages to autonomous systems.",
    ),
    ("deterministic_finite_automaton", "autonomous_system", "*"): (
        "D14-DEF-013",
        "Spurious lexical-collision edge between DFA and Autonomous System.",
    ),
    ("probability", "inheritance_hierarchy", "*"): (
        "D14-DEF-014",
        "Cross-domain co-mention noise between Probability and OOP Inheritance Hierarchy.",
    ),
    ("direct_preference_optimization", "inheritance_hierarchy", "*"): (
        "D14-DEF-014",
        "Cross-domain co-mention noise between DPO and OOP Inheritance Hierarchy.",
    ),
    ("web_traffic", "principal_component_analysis", "*"): (
        "D14-DEF-015",
        "Spurious book-index co-mention noise between Web Traffic and PCA.",
    ),
    ("principal_component_analysis", "web_traffic", "*"): (
        "D14-DEF-015",
        "Spurious book-index co-mention noise between PCA and Web Traffic.",
    ),
    ("bit_transmission", "data_link_layer", REL_REQUIRES): (
        "D14-DEF-016",
        "Inverted OSI dependency: Physical Bit Transmission (L1) precedes Data Link Layer (L2).",
    ),
    ("bit_transmission", "packet_switching", REL_REQUIRES): (
        "D14-DEF-016",
        "Inverted OSI dependency: Physical Bit Transmission (L1) precedes Packet Switching (L3).",
    ),
    ("bit_transmission", "network_layer", REL_REQUIRES): (
        "D14-DEF-016",
        "Inverted OSI dependency: Physical Bit Transmission (L1) precedes Network Layer (L3).",
    ),
    ("data_link_layer", "bit_transmission", REL_ENABLES): (
        "D14-DEF-016",
        "Inverted OSI dependency: Bit Transmission enables Data Link Layer framing.",
    ),
    ("b_plus_tree", "clustered_index", REL_ENABLES): (
        "D14-DEF-017",
        "Re-typed to clustered_index USES b_plus_tree; not a mandatory prerequisite.",
    ),
    ("tcp", "constitutional_principle", "*"): (
        "D14-DEF-018",
        "Cross-domain contamination edge linking TCP to AI Constitutional Principle.",
    ),
    ("constitutional_principle", "tcp", "*"): (
        "D14-DEF-018",
        "Cross-domain contamination edge linking AI Constitutional Principle to TCP.",
    ),
    ("kl_divergence", "direct_preference_optimization", REL_REQUIRES): (
        "D14-DAG-001",
        "Inverted prerequisite: DPO requires KL Divergence, not vice versa.",
    ),
    ("kl_divergence", "direct_preference_optimization", REL_ENABLES): (
        "D14-DAG-001",
        "Normalized to direct_preference_optimization REQUIRES kl_divergence.",
    ),
    ("gae", "direct_preference_optimization", REL_REQUIRES): (
        "D14-DAG-002",
        "Invalid prerequisite: Generalized Advantage Estimation does not require DPO.",
    ),
    ("gae", "direct_preference_optimization", REL_ENABLES): (
        "D14-DAG-002",
        "Invalid unlock: GAE does not unlock DPO.",
    ),
    ("direct_preference_optimization", "bradley_terry_preference_model", REL_ENABLES): (
        "D14-DAG-003",
        "Contradictory unlock: DPO requires Bradley-Terry preference model, not unlocks it.",
    ),
    ("reinforcement_learning", "bradley_terry_preference_model", REL_REQUIRES): (
        "D14-DAG-004",
        "General RL does not require the Bradley-Terry preference model.",
    ),
    ("binary_cross_entropy", "reinforcement_learning", REL_REQUIRES): (
        "D14-DAG-005",
        "Binary cross-entropy is a general loss function and does not require RL.",
    ),
    ("binary_cross_entropy", "reinforcement_learning", REL_ENABLES): (
        "D14-DAG-005",
        "Contradictory unlock between binary cross-entropy and RL.",
    ),
    ("language_model", "summarization", REL_REQUIRES): (
        "D14-DAG-006",
        "Inverted dependency: Summarization uses Language Models, not vice versa.",
    ),
    ("self_attention", "transformer", REL_REQUIRES): (
        "D14-DAG-007",
        "Inverted dependency: Transformer requires Self-Attention, not vice versa.",
    ),
    ("transformer", "self_attention", REL_ENABLES): (
        "D14-DAG-007",
        "Inverted dependency: Self-Attention enables Transformer, not vice versa.",
    ),
    ("long_context_transformer", "self_attention", REL_ENABLES): (
        "D14-DAG-008",
        "Contradictory unlock: Long-Context Transformer requires Self-Attention.",
    ),
    ("token_dropping", "transformer", REL_ENABLES): (
        "D14-DAG-009",
        "Contradictory unlock: Token Dropping requires Transformer.",
    ),
    ("sparse_routing", "sparse_mixture_of_experts", REL_REQUIRES): (
        "D14-DAG-010",
        "Contradictory cycle: Sparse MoE requires Sparse Routing, not vice versa.",
    ),
    ("variational_inference", "diffusion_model", REL_REQUIRES): (
        "D14-DAG-011",
        "Inverted dependency: Diffusion models build on variational inference, not vice versa.",
    ),
    ("bayesian_inference", "variational_inference", REL_REQUIRES): (
        "D14-DAG-012",
        "Inverted dependency: Variational inference approximates Bayesian inference.",
    ),
    ("variational_inference", "bayesian_inference", REL_ENABLES): (
        "D14-DAG-012",
        "Inverted unlock: Bayesian inference precedes variational inference.",
    ),
    ("virtual_memory", "address_translation", REL_REQUIRES): (
        "D14-DAG-013",
        "Address translation is a mechanism within virtual memory (normalized to PART_OF/USES).",
    ),
    ("address_translation", "paging", REL_REQUIRES): (
        "D14-DAG-014",
        "Inverted dependency: Paging is an address-translation scheme, not a prerequisite for it.",
    ),
    ("paged_attention", "paging", REL_REQUIRES): (
        "D14-BRIDGE-001",
        "Re-typed to paged_attention USES paging (interdisciplinary inspiration/mechanism).",
    ),
    ("paging", "paged_attention", REL_ENABLES): (
        "D14-BRIDGE-001",
        "Re-typed to paged_attention USES paging (interdisciplinary link, not hard prerequisite).",
    ),
}

#: Nodes whose incoming/outgoing v1 UNLOCKS/REQUIRES edges are bulk-quarantined due to hub noise.
NOISE_HUB_IDS: frozenset[str] = frozenset({"autonomous_system"})
