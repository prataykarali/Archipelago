"""Source-backed typed edges added in graph_v2_d14 (all marked PENDING_REVIEW)."""

from __future__ import annotations

from dataclasses import dataclass

from .d14_schema import (
    REL_CONTRASTS_WITH,
    REL_ENABLES,
    REL_PART_OF,
    REL_RELATED_TO,
    REL_REQUIRES,
    REL_USES,
    REVIEW_PENDING,
)


@dataclass(frozen=True)
class CuratedEdgeSpec:
    """Source-backed typed relationship added or corrected in graph_v2_d14."""

    from_id: str
    to_id: str
    relation: str
    source_justification: str
    defect_ref: str
    review_status: str = REVIEW_PENDING


def _build_edges(
    rows: tuple[tuple[str, str, str, str, str], ...],
) -> tuple[CuratedEdgeSpec, ...]:
    return tuple(CuratedEdgeSpec(s, d, r, j, ref) for s, d, r, j, ref in rows)


#: Verified, source-backed typed edges added in graph_v2_d14 (never auto-promoted to HUMAN_VERIFIED).
CURATED_EDGES: tuple[CuratedEdgeSpec, ...] = _build_edges(
    (
        ("singular_value_decomposition", "linear_algebra", REL_REQUIRES, "Deisenroth et al. (2020) Ch. 4.5: SVD builds on linear algebra.", "D14-DEF-003"),
        ("singular_value_decomposition", "eigenvalues_and_eigenvectors", REL_REQUIRES, "Deisenroth et al. (2020) Ch. 4.5: singular values derive from A^T A.", "D14-DEF-003"),
        ("eigendecomposition", "eigenvalues_and_eigenvectors", REL_REQUIRES, "Deisenroth et al. (2020) Ch. 4.4.", "D14-DEF-003"),
        ("principal_component_analysis", "singular_value_decomposition", REL_USES, "Deisenroth et al. (2020) Ch. 10: PCA computed via SVD.", "D14-DEF-003"),
        ("principal_component_analysis", "eigendecomposition", REL_USES, "Deisenroth et al. (2020) Ch. 10: PCA diagonalizes covariance.", "D14-DEF-015"),
        ("attention_mechanism", "neural_network", REL_REQUIRES, "Bahdanau (2014); Vaswani (2017): attention over neural hidden states.", "D14-DEF-012"),
        ("neural_network", "attention_mechanism", REL_ENABLES, "Neural representations enable parameterized attention mechanisms.", "D14-DEF-012"),
        ("transformer", "self_attention", REL_REQUIRES, "Vaswani et al. (2017): Transformer built from multi-head self-attention.", "D14-DAG-007"),
        ("graph_attention_network", "attention_mechanism", REL_REQUIRES, "Velickovic et al. (2018) GAT Sec. 2.1: masked self-attention on graphs.", "D14-DEF-004"),
        ("graph_attention_network", "graph_convolutional_network", REL_CONTRASTS_WITH, "Velickovic et al. (2018): learned attention vs. fixed GCN normalization.", "D14-DEF-004"),
        ("graph_convolutional_network", "neural_network", REL_REQUIRES, "Kipf & Welling (2017): GCN extends neural layers to graph data.", "D14-DEF-010"),
        ("direct_preference_optimization", "kl_divergence", REL_REQUIRES, "Rafailov et al. (2023) Eq. 4-7: KL-constrained closed-form policy.", "D14-DEF-011"),
        ("direct_preference_optimization", "reinforcement_learning", REL_CONTRASTS_WITH, "Rafailov et al. (2023): DPO avoids explicit RL/PPO optimization loops.", "D14-DEF-011"),
        ("direct_preference_optimization", "rlhf", REL_CONTRASTS_WITH, "Rafailov et al. (2023): reward-model-free alternative to RLHF.", "D14-DEF-011"),
        ("denoising_diffusion_probabilistic_models", "variational_inference", REL_REQUIRES, "Ho et al. (2020) Sec. 2: objective derives from variational bound.", "D14-DEF-007"),
        ("denoising_diffusion_probabilistic_models", "diffusion_model", REL_PART_OF, "Ho et al. (2020): discrete-time diffusion probabilistic model.", "D14-DEF-007"),
        ("denoising_diffusion_probabilistic_models", "variational_autoencoder", REL_CONTRASTS_WITH, "Ho et al. (2020): fixed Markov forward process vs. learned VAE encoders.", "D14-DEF-007"),
        ("kl_divergence", "probability_distribution", REL_REQUIRES, "Cover & Thomas Ch. 2: directed divergence between two distributions.", "D14-DEF-005"),
        ("variational_inference", "kl_divergence", REL_USES, "Blei et al. (2017): minimizes KL(q || p) via the ELBO.", "D14-DEF-005"),
        ("variational_inference", "bayes_theorem", REL_REQUIRES, "Blei et al. (2017): approximates intractable Bayesian posteriors.", "D14-DEF-005"),
        ("maximum_likelihood_estimation", "probability_distribution", REL_REQUIRES, "Deisenroth et al. (2020) Ch. 9: maximizes likelihood under distribution.", "D14-DEF-010"),
        ("lalr", "bottom_up_parsing", REL_PART_OF, "Dragon Book Ch. 4.7: LALR(1) is a bottom-up shift-reduce parser.", "D14-DEF-006"),
        ("bottom_up_parsing", "syntax_analysis", REL_PART_OF, "Dragon Book Ch. 4: primary syntax-analysis strategy.", "D14-DEF-006"),
        ("lalr", "context_free_grammar", REL_REQUIRES, "Dragon Book Ch. 4.7: LALR tables constructed from LR items of a CFG.", "D14-DEF-006"),
        ("syntax_analysis", "lexical_analysis", REL_REQUIRES, "Dragon Book Ch. 1.2: parser consumes lexer token stream.", "D14-DEF-006"),
        ("semantic_analysis", "syntax_analysis", REL_REQUIRES, "Dragon Book Ch. 1.2: validates types/scopes over parsed AST.", "D14-DEF-006"),
        ("intermediate_code_generation", "semantic_analysis", REL_REQUIRES, "Dragon Book Ch. 1.2: IR generation follows semantic validation.", "D14-DEF-006"),
        ("deterministic_finite_automaton", "finite_automata", REL_PART_OF, "Sipser Ch. 1.1: deterministic finite-state automaton.", "D14-DEF-009"),
        ("nondeterministic_finite_automaton", "finite_automata", REL_PART_OF, "Sipser Ch. 1.2: nondeterministic finite-state automaton.", "D14-DEF-009"),
        ("pumping_lemma", "regular_languages", REL_REQUIRES, "Sipser Ch. 1.4: necessary property of regular languages.", "D14-DEF-009"),
        ("regular_languages", "chomsky_hierarchy", REL_PART_OF, "Sipser: Type-3 of Chomsky hierarchy.", "D14-DEF-009"),
        ("context_free_languages", "chomsky_hierarchy", REL_PART_OF, "Sipser: Type-2 of Chomsky hierarchy.", "D14-DEF-009"),
        ("context_free_languages", "context_free_grammar", REL_REQUIRES, "Sipser Ch. 2.1: CFLs generated by context-free grammars.", "D14-DEF-009"),
        ("data_link_layer", "bit_transmission", REL_REQUIRES, "Tanenbaum / Kurose-Ross: L2 Data Link builds on L1 bit transmission.", "D14-DEF-016"),
        ("bit_transmission", "data_link_layer", REL_ENABLES, "L1 Physical bit transmission enables L2 Data Link framing.", "D14-DEF-016"),
        ("network_layer", "data_link_layer", REL_REQUIRES, "OSI/TCP-IP: L3 Network routing relies on L2 frame delivery.", "D14-DEF-016"),
        ("packet_switching", "network_layer", REL_PART_OF, "Kurose & Ross Ch. 4: core forwarding paradigm at network layer.", "D14-DEF-016"),
        ("tcp", "network_layer", REL_REQUIRES, "RFC 9293: TCP transport operates over IP network-layer datagrams.", "D14-DEF-018"),
        ("clustered_index", "b_plus_tree", REL_USES, "Ramakrishnan & Gehrke Ch. 10: clustered indexes commonly use B+ trees.", "D14-DEF-017"),
        ("paging", "address_translation", REL_PART_OF, "OSTEP Ch. 18: fixed-size address-translation mechanism.", "D14-BRIDGE-001"),
        ("paging", "virtual_memory", REL_PART_OF, "OSTEP Ch. 18: implements virtual memory without external fragmentation.", "D14-BRIDGE-001"),
        ("page_table", "paging", REL_USES, "OSTEP Ch. 18: stores VPN-to-PFN translations for paging.", "D14-DEF-008"),
        ("translation_lookaside_buffer", "page_table", REL_USES, "OSTEP Ch. 19: hardware cache for page-table translations.", "D14-DEF-008"),
        ("base_and_bounds", "address_translation", REL_PART_OF, "OSTEP Ch. 15: dynamic hardware address-translation scheme.", "D14-DEF-008"),
        ("paged_attention", "paging", REL_USES, "Kwon et al. (2023) vLLM: adapts OS paging to KV-cache blocks.", "D14-BRIDGE-001"),
        ("paged_attention", "virtual_memory", REL_RELATED_TO, "Kwon et al. (2023) vLLM: inspired by OS virtual memory.", "D14-BRIDGE-001"),
        ("dijkstras_algorithm", "priority_queue_mechanics", REL_REQUIRES, "CLRS Ch. 24.3: min-priority queue for O((V+E) log V) relaxation.", "D14-DEF-009"),
        ("rsa_cryptosystem", "modular_arithmetic", REL_REQUIRES, "RFC 8017: modular exponentiation and Euler's theorem.", "D14-DEF-009"),
        ("rsa_cryptosystem", "public_key_cryptography", REL_PART_OF, "Katz & Lindell: canonical public-key cryptosystem.", "D14-DEF-009"),
        ("tls_protocol", "public_key_cryptography", REL_USES, "RFC 8446: authentication and key establishment.", "D14-DEF-009"),
        ("tls_protocol", "symmetric_key_cryptography", REL_USES, "RFC 8446: AEAD symmetric ciphers for bulk confidentiality.", "D14-DEF-009"),
        ("tls_protocol", "cryptographic_hash_function", REL_USES, "RFC 8446: SHA-256/SHA-384 transcript hashing and HKDF.", "D14-DEF-009"),
        ("tls_protocol", "tcp", REL_REQUIRES, "RFC 8446: TLS operates over reliable ordered transport stream.", "D14-DEF-009"),
        ("software_development_lifecycle", "software_engineering", REL_PART_OF, "IEEE SWEBOK v4: SDLC structures software engineering execution.", "D14-DEF-009"),
        ("solid_principles", "software_engineering", REL_PART_OF, "Martin (2000): modular object-oriented software design principles.", "D14-DEF-009"),
        ("unit_testing", "software_engineering", REL_PART_OF, "IEEE SWEBOK v4: verifies individual software modules.", "D14-DEF-009"),
        ("design_patterns", "software_engineering", REL_PART_OF, "Gamma et al. (1994): reusable design patterns in software engineering.", "D14-DEF-009"),
        ("continuous_integration", "unit_testing", REL_REQUIRES, "Fowler (2006): CI relies on automated unit tests.", "D14-DEF-009"),
        ("continuous_integration", "version_control", REL_REQUIRES, "Fowler (2006): CI requires a shared version control repository.", "D14-DEF-009"),
        ("instruction_set_architecture", "cpu_architecture", REL_PART_OF, "Patterson & Hennessy Ch. 2: programmer-visible CPU interface.", "D14-DEF-009"),
        ("instruction_pipelining", "instruction_cycle", REL_REQUIRES, "Patterson & Hennessy Ch. 4: overlaps stages of instruction cycle.", "D14-DEF-009"),
        ("instruction_pipelining", "cpu_architecture", REL_PART_OF, "Patterson & Hennessy Ch. 4: core CPU microarchitecture technique.", "D14-DEF-009"),
        ("pipeline_hazards", "instruction_pipelining", REL_REQUIRES, "Patterson & Hennessy Ch. 4.5: hazards arise in pipelined execution.", "D14-DEF-009"),
        ("branch_prediction", "pipeline_hazards", REL_USES, "Patterson & Hennessy Ch. 4.8: mitigates control hazards in pipelines.", "D14-DEF-009"),
        ("cache_memory", "memory_hierarchy", REL_PART_OF, "Patterson & Hennessy Ch. 5: SRAM caches between registers and DRAM.", "D14-DEF-009"),
        ("cache_coherence", "cache_memory", REL_REQUIRES, "Hennessy & Patterson Ch. 5: consistency across private CPU caches.", "D14-DEF-009"),
    )
)
