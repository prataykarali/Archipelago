"""Unit tests for Phase 2-9 system-wide relevance, metrics, AnswerThis, and 40-query benchmark."""

from __future__ import annotations

from io import BytesIO
import json

from openpyxl import load_workbook
import pytest

from archipelago.scholarly.contracts.okf_models import (
    PaperAuthor,
    PaperIdentifiers,
    PaperRecord,
    ProvenancePointer,
)
from archipelago.scholarly.discovery.answerthis_adapter import (
    ANSWERTHIS_IMPORTED_VALIDATION,
    ANSWERTHIS_NOT_CONFIGURED,
    AnswerThisProvider,
    compare_against_answerthis,
    import_answerthis_export,
)
from archipelago.scholarly.discovery.provider_selector import classify_domain, select_providers
from archipelago.scholarly.intelligence.graph import build_graph
from archipelago.scholarly.intelligence.relevance_engine import evaluate_relevance, understand_query
from archipelago.scholarly.intelligence.search import discover
from archipelago.scholarly.intelligence.workbook import build_workbook

pytestmark = pytest.mark.unit


def test_answerthis_adapter_unconfigured_and_import_comparison() -> None:
    prov = AnswerThisProvider()
    assert prov.status_snapshot()["status"] == ANSWERTHIS_NOT_CONFIGURED
    res = prov.search("liquid neural networks")
    assert res["status"] == ANSWERTHIS_NOT_CONFIGURED
    assert res["records"] == []

    exported = json.dumps([
        {"title": "Liquid Time-constant Networks", "doi": "10.1609/aaai.v35i9.16936", "year": 2021, "authors": ["Ramin Hasani"]},
        {"title": "Closed-form continuous-time neural networks", "doi": "10.1038/s42256-022-00556-7", "year": 2022, "authors": ["Ramin Hasani"]},
    ])
    imp = import_answerthis_export(exported, fmt="json")
    assert imp["status"] == ANSWERTHIS_IMPORTED_VALIDATION
    assert imp["record_count"] == 2

    comp = compare_against_answerthis(
        [{"title": "Liquid Time-constant Networks", "doi": "10.1609/aaai.v35i9.16936"}],
        imp["records"],
    )
    assert comp["matched_count"] == 1
    assert comp["overlap_rate"] == 0.5


def test_ai_cs_domain_excludes_biomedical_europe_pmc() -> None:
    plan = select_providers("liquid neural networks")
    assert plan["domain"] == "ai_cs"
    assert "europe_pmc" not in plan["selected"]
    assert any(s["source"] == "europe_pmc" for s in plan["skipped"])

    bio = select_providers("clinical protein folding in patients")
    assert bio["domain"] == "biomedical"
    assert "europe_pmc" in bio["selected"]


def test_semantic_relevance_rejects_scattered_false_positives() -> None:
    # True LNN papers
    r1 = evaluate_relevance(
        "Liquid Neural Networks",
        "Liquid Time-constant Networks",
        "We introduce liquid time-constant (LTC) recurrent neural networks with continuous-time ODE dynamics.",
    )
    assert r1["eligible"] is True
    assert r1["label"] in {"HIGHLY_RELEVANT", "RELEVANT"}

    r2 = evaluate_relevance(
        "Liquid Neural Networks",
        "Multi-Rate Mixture of Experts for Accelerating Liquid Neural Network Training",
        "Liquid neural networks achieve strong temporal modeling on sequential control benchmarks.",
    )
    assert r2["eligible"] is True
    assert r2["label"] == "HIGHLY_RELEVANT"

    # Off-topic distractors that previously passed bag-of-words!
    d1 = evaluate_relevance(
        "Liquid Neural Networks",
        "Peri-Infarct Cortical Network Remapping During Stroke Recovery via a Soft Liquid Metal Neural Interface",
        "A soft liquid metal neural interface improves cortical network remapping in mice.",
    )
    assert d1["eligible"] is False
    assert d1["label"] == "IRRELEVANT"

    d2 = evaluate_relevance(
        "Liquid Neural Networks",
        "Clapeyron neural networks for single-species vapor-liquid equilibria",
        "We train physics-informed neural networks to predict vapor-liquid equilibria.",
    )
    assert d2["eligible"] is False
    assert d2["label"] == "IRRELEVANT"


def test_preprint_and_published_versions_collapse_across_years() -> None:
    class VersionedOrch:
        def discover_with_status(self, query: str, limit: int):
            p_pre = PaperRecord(
                paper_id="pre-1",
                title="Liquid Time-constant Networks",
                abstract="We introduce liquid time-constant networks for time-series modeling.",
                identifiers=PaperIdentifiers(arxiv_id="2006.04439"),
                authors=[PaperAuthor(name="Ramin Hasani")],
                venue="arXiv",
                publication_date="2020-06-08",
                publication_type="preprint",
            )
            p_pub = PaperRecord(
                paper_id="pub-1",
                title="Liquid Time-constant Networks",
                abstract="We introduce liquid time-constant networks for time-series modeling.",
                identifiers=PaperIdentifiers(doi="10.1609/aaai.v35i9.16936", openalex_id="https://openalex.org/W31"),
                authors=[PaperAuthor(name="Ramin Hasani")],
                venue="AAAI",
                publication_date="2021-05-18",
                publication_type="proceedings-article",
            )
            prov = ProvenancePointer(source_type="openalex", artifact_sha256="a" * 64, source_url="https://openalex.org/W31")
            return [
                {"paper": p_pre, "source": "arxiv", "provenance": prov, "citation_count": 10, "source_metadata": {}},
                {"paper": p_pub, "source": "openalex", "provenance": prov, "citation_count": 500, "source_metadata": {}},
            ], [{"source": "openalex", "status": "live", "record_count": 2}]

    run = discover({"topic": "liquid neural networks", "top_k": 10, "sort": "foundational"}, VersionedOrch())
    assert len(run["papers"]) == 1
    assert run["papers"][0]["doi"] == "10.1609/aaai.v35i9.16936"
    assert run["papers"][0]["published_vs_preprint"] == "published"


def test_coverage_audit_never_exceeds_100_percent_and_graph_distinguishes_verification() -> None:
    run = {
        "schema": "archipelago.research_intelligence.v2",
        "options": {"topic": "liquid neural networks", "top_k": 20, "sort": "newest"},
        "retrieved_at": "2026-11-16T00:00:00Z",
        "ordering": "publication_date_desc",
        "sources": [{"source": "openalex", "status": "live", "record_count": 1}],
        "papers": [
            {
                "paper_id": "p1",
                "title": "Liquid Time-constant Networks",
                "year": 2021,
                "publication_date": "2021-05-18",
                "doi": "10.1609/aaai.v35i9.16936",
                "url": "https://doi.org/10.1609/aaai.v35i9.16936",
                "identifiers": {"doi": "10.1609/aaai.v35i9.16936"},
                "authors": [{"name": "Ramin Hasani"}],
                "references": ["10.1000/ref1", "10.1000/ref2", "10.1000/ref3", "raw-text-ref"],
                "provenance": [{"source_type": "openalex", "source_url": "https://openalex.org/W1", "fetched_at": "2026-11-16T00:00:00Z"}],
                "evidence_status": "REFERENCE_METADATA_AVAILABLE",
                "identity_review": [],
                "citation_count": 500,
                "citation_provider": "openalex",
                "citation_observations": [{"provider": "openalex", "count": 500}],
                "venue": "AAAI",
            }
        ],
        "author_observations": [],
    }
    graph = build_graph(run)
    cov = graph["coverage_report"]
    assert cov["raw_reference_count"] == 4
    assert cov["identifier_matched_count"] == 3
    assert cov["existence_verified_count"] == 0
    assert cov["unresolved_count"] == 1

    book = load_workbook(BytesIO(build_workbook(run).getvalue()))
    ca = book["Coverage_Audit"]
    for r in range(2, ca.max_row + 1):
        pct = ca.cell(r, 9).value
        assert 0.0 <= pct <= 100.0, f"Invalid coverage % in {ca.cell(r, 1).value}: {pct}"


def test_40_query_multidiscipline_generalization_benchmark() -> None:
    """Evaluate precision >= 0.90 and low false-positive rate across 40 diverse queries + distractors."""
    benchmark_cases = [
        # (query, relevant_title, relevant_abs, distractor_title, distractor_abs)
        ("liquid neural networks", "Liquid Time-constant Networks", "Liquid time-constant neural networks model continuous dynamics.", "Soft Liquid Metal Neural Interface", "Liquid metal interface for cortical neural recording."),
        ("diffusion models", "Denoising Diffusion Probabilistic Models", "Diffusion models learn to reverse a gradual noising process.", "Diffusion of oxygen in metallic models", "Oxygen diffusion and structural models in alloys."),
        ("retrieval augmented generation", "Retrieval-Augmented Generation for Knowledge-Intensive NLP", "RAG combines dense retrieval with sequence generation.", "Generation of augmented power in energy retrieval", "Energy retrieval and power generation grids."),
        ("graph neural networks", "Graph Attention Networks", "Graph neural networks compute node representations via attention.", "Neural network plots and graph visualization", "We plot neural network accuracy graphs."),
        ("attention mechanism", "Attention Is All You Need", "The Transformer relies entirely on self-attention mechanisms.", "Mechanisms of visual attention in infants", "Cognitive attention mechanism in pediatric studies."),
        ("federated learning", "Communication-Efficient Learning of Deep Networks from Decentralized Data", "Federated learning trains models across decentralized clients.", "Learning outcomes in federated school districts", "Educational learning across federated regional boards."),
        ("reinforcement learning", "Proximal Policy Optimization Algorithms", "Reinforcement learning agents optimize policy rewards.", "Concrete reinforcement and machine learning", "Steel reinforcement bars tested with learning curves."),
        ("knowledge distillation", "Distilling the Knowledge in a Neural Network", "Knowledge distillation transfers dark knowledge to a student model.", "Vacuum distillation of chemical knowledge", "Chemical distillation columns and process knowledge."),
        ("quantization aware training", "Quantization and Training of Neural Networks for Efficient Integer-Arithmetic", "Quantization aware training simulates low-bit weights.", "Energy quantization in aware quantum training", "Quantum energy quantization during lab training."),
        ("contrastive learning", "A Simple Framework for Contrastive Learning of Visual Representations", "Contrastive learning maximizes agreement between augmented views.", "Contrastive linguistics in second-language learning", "A contrastive study of grammar learning."),
        ("distributed consensus", "In Search of an Understandable Consensus Algorithm (Raft)", "Distributed consensus protocols ensure replicated state machine safety.", "Consensus on distributed agricultural subsidies", "Policy consensus regarding distributed farm grants."),
        ("columnar database", "C-Store: A Column-Oriented DBMS", "Columnar database engines compress attributes for analytical queries.", "Database of columnar basalt formations", "Geological database of columnar rock."),
        ("query optimization", "Access Path Selection in a Relational Database Management System", "Query optimization selects minimum-cost execution plans.", "Optimization of survey query wording", "Survey optimization for customer query forms."),
        ("memory safety", "RustBelt: Securing the Foundations of the Rust Programming Language", "Memory safety prevents use-after-free and buffer overflows.", "Safety training for memory care facilities", "Clinical memory care safety protocols."),
        ("dense passage retrieval", "Dense Passage Retrieval for Open-Domain Question Answering", "Dense passage retrieval embeds questions and passages in dual encoders.", "Passage of dense smoke in retrieval shafts", "Mine retrieval shaft smoke passage modeling."),
        ("vector database", "Milvus: A Purpose-Built Vector Data Management System", "Vector database indexing accelerates approximate nearest neighbor search.", "Database of mosquito vector habitats", "Entomological vector species database."),
        ("topological data analysis", "Persistent Homology and Topological Data Analysis", "Topological data analysis extracts persistent homology barcodes.", "Data analysis of topological road maps", "Highway map data analysis."),
        ("stochastic differential equations", "Numerical Solution of Stochastic Differential Equations", "Stochastic differential equations model noisy continuous trajectories.", "Differential pricing in stochastic equations", "Market equations with differential fees."),
        ("bayesian inference", "Variational Bayesian Inference for Latent Dirichlet Allocation", "Bayesian inference approximates posterior distributions over parameters.", "Statistical inference of Bayesian island populations", "Demographic inference on island censuses."),
        ("convex optimization", "Interior-Point Methods for Convex Optimization", "Convex optimization guarantees global optima under convexity.", "Optimization of convex glass lenses", "Optical grinding of convex mirrors."),
        ("quantum error correction", "Surface Codes: Towards Practical Large-Scale Quantum Computation", "Quantum error correction encodes logical qubits into stabilizer codes.", "Error correction in quantum accounting software", "Software error correction in accounting."),
        ("superconducting qubits", "Transmon Superconducting Qubits for Quantum Processors", "Superconducting qubits leverage Josephson junctions at millikelvin.", "Cooling pipes for superconducting magnets", "Industrial pipe insulation."),
        ("plasma confinement", "Tokamak Magnetic Confinement of Fusion Plasma", "Magnetic plasma confinement sustains high-temperature fusion.", "Blood plasma storage confinement", "Hospital blood plasma refrigeration."),
        ("density functional theory", "Kohn-Sham Density Functional Theory for Electronic Structure", "Density functional theory computes ground-state electron density.", "Functional theory of urban population density", "Urban planning density theories."),
        ("molecular dynamics", "Fast Parallel Algorithms for Short-Range Molecular Dynamics", "Molecular dynamics integrates Newtonian equations for atomic systems.", "Dynamics of molecular gastronomy", "Culinary texture dynamics."),
        ("metal organic frameworks", "Metal-Organic Frameworks for Gas Storage and Catalysis", "Metal-organic frameworks exhibit high porosity and tunable linkers.", "Organic software frameworks for metal fabrication", "CAD software frameworks for sheet metal."),
        ("perovskite solar cells", "High-Efficiency Perovskite Solar Cells via Interface Engineering", "Perovskite solar cells achieve >25% power conversion efficiency.", "Solar heating in concrete cells", "Thermal mass of concrete."),
        ("battery electrolyte", "Solid-State Electrolyte Design for Lithium-Ion Batteries", "Solid-state battery electrolytes suppress dendrite growth.", "Electrolyte drinks for marathon endurance", "Sports hydration electrolyte balance."),
        ("crispr gene editing", "A Programmable Dual-RNA-Guided DNA Endonuclease in Adaptive Bacterial Immunity", "CRISPR gene editing enables targeted genome modification.", "Editing of gene names in manuscripts", "Copyediting biological manuscripts."),
        ("protein folding", "Highly Accurate Protein Structure Prediction with AlphaFold", "Protein folding predicts 3D atomic coordinates from amino-acid sequences.", "Folding origami structures for packaging", "Cardboard folding patterns."),
        ("single cell rna sequencing", "Integrated Analysis of Single-Cell RNA-seq Data", "Single-cell RNA sequencing profiles transcriptomes at cellular resolution.", "Sequencing of single cell phone towers", "Telecom tower scheduling."),
        ("mrna vaccine delivery", "Lipid Nanoparticles for mRNA Vaccine Delivery", "Lipid nanoparticles encapsulate mRNA for intracellular vaccine delivery.", "Cold-chain truck delivery routes", "Logistics routing for refrigerated trucks."),
        ("climate tipping points", "Tipping Elements in the Earth's Climate System", "Climate tipping points trigger nonlinear shifts in ice sheets.", "Tipping etiquette in service industries", "Restaurant tipping behavior."),
        ("urban heat island", "Surface Urban Heat Island Mitigation Strategies", "Urban heat islands elevate metropolitan temperatures relative to rural areas.", "Heat transfer on tropical island resorts", "Resort HVAC sizing."),
        ("autonomous vehicle perception", "Multi-Sensor Fusion for Autonomous Vehicle Perception", "Autonomous vehicle perception fuses LiDAR and camera streams.", "Driver perception of vehicle color", "Consumer color preferences."),
        ("algorithmic fairness", "Fairness Through Awareness in Machine Learning", "Algorithmic fairness constrains demographic disparity in predictions.", "Fairness in sports refereeing", "Soccer referee consistency."),
        ("neural radiance fields", "NeRF: Representing Scenes as Neural Radiance Fields", "Neural radiance fields synthesize novel views via volumetric rendering.", "Solar radiance measurements in fields", "Pyranometer field calibration."),
        ("zero knowledge proofs", "Succinct Non-Interactive Zero-Knowledge Proofs", "Zero-knowledge proofs verify computation without revealing witness inputs.", "Knowledge tests with zero preparation", "Student quiz scores."),
        ("homomorphic encryption", "Fully Homomorphic Encryption over Ideal Lattices", "Homomorphic encryption permits computation directly on ciphertexts.", "Encryption of home network routers", "Wi-Fi password setup."),
        ("spiking neural networks", "Surrogate Gradient Learning in Spiking Neural Networks", "Spiking neural networks communicate via discrete temporal spikes.", "Voltage spikes in neural recording amplifiers", "Amplifier surge protection."),
    ]
    assert len(benchmark_cases) == 40
    tp = fp = fn = 0
    for q, r_title, r_abs, d_title, d_abs in benchmark_cases:
        rel = evaluate_relevance(q, r_title, r_abs)
        dist = evaluate_relevance(q, d_title, d_abs)
        if rel["eligible"]:
            tp += 1
        else:
            fn += 1
        if dist["eligible"]:
            fp += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    fpr = fp / len(benchmark_cases)
    assert precision >= 0.90, f"Precision {precision:.3f} < 0.90 (tp={tp}, fp={fp}, fn={fn})"
    assert recall >= 0.90, f"Recall {recall:.3f} < 0.90 (tp={tp}, fn={fn})"
    assert fpr <= 0.10, f"FPR {fpr:.3f} > 0.10"
