"""Canonical 12-domain source catalog assembly for Archipelago D14 corpus_v3_d14."""

from __future__ import annotations

from archipelago.corpus.catalog_types import (
    CANONICAL_DOMAINS,
    CORPUS_VERSION_V3,
    PARENT_CORPUS_VERSION,
    PARENT_HF_REPO_ID,
    PARENT_HF_REVISION,
    PARENT_MANIFEST_REL_PATH,
    LicenseStatus,
    SourceFormat,
    SourceSpec,
)
from archipelago.corpus.oa_sources import build_d14_new_oa_sources

__all__ = [
    "CANONICAL_DOMAINS",
    "CORPUS_VERSION_V3",
    "PARENT_CORPUS_VERSION",
    "PARENT_HF_REPO_ID",
    "PARENT_HF_REVISION",
    "PARENT_MANIFEST_REL_PATH",
    "LicenseStatus",
    "SourceFormat",
    "SourceSpec",
    "build_default_source_catalog",
]

_OSTEP_CHAPTERS: tuple[tuple[str, str], ...] = (
    ("00_Dialogue.pdf", "Ch. 0: A Dialogue on the Book"),
    ("01_Introduction.pdf", "Ch. 1: Introduction to Operating Systems"),
    ("02_CPU_Virtualization.pdf", "Ch. 2: CPU Virtualization and Processes"),
    ("03_Process_API.pdf", "Ch. 3: Interlude: Process API"),
    ("04_Limited_Direct_Execution.pdf", "Ch. 4: Mechanism: Limited Direct Execution"),
    ("05_CPU_Scheduling.pdf", "Ch. 5: CPU Scheduling"),
    ("06_Address_Spaces.pdf", "Ch. 6: The Abstraction: Address Spaces"),
    ("07_Address_Translation.pdf", "Ch. 7: Mechanism: Address Translation"),
    ("08_Paging.pdf", "Ch. 8: Paging: Introduction"),
    ("09_TLBs.pdf", "Ch. 9: Paging: Faster Translations (TLBs)"),
    ("10_Concurrency_Intro.pdf", "Ch. 10: Concurrency: An Introduction"),
    ("11_Locks.pdf", "Ch. 11: Locks"),
    ("12_Semaphores.pdf", "Ch. 12: Semaphores"),
    ("13_Common_Bugs.pdf", "Ch. 13: Common Concurrency Problems"),
    ("14_IO_Devices.pdf", "Ch. 14: I/O Devices"),
    ("15_RAID.pdf", "Ch. 15: Redundant Arrays of Inexpensive Disks (RAID)"),
    ("16_Log_Structured_FS.pdf", "Ch. 16: Log-Structured File Systems"),
)

_BASELINE_ML_PAPERS: tuple[tuple[str, str, str], ...] = (
    (
        "Bahdanau2014_Attention.pdf",
        "Neural Machine Translation by Jointly Learning to Align and Translate",
        "Bahdanau et al. (2014)",
    ),
    (
        "Bai2022_ConstitutionalAI.pdf",
        "Constitutional AI: Harmlessness from AI Feedback",
        "Bai et al. (2022)",
    ),
    ("Brown2020_GPT3.pdf", "Language Models are Few-Shot Learners", "Brown et al. (2020)"),
    (
        "Dettmers2023_QLoRA.pdf",
        "QLoRA: Efficient Finetuning of Quantized LLMs",
        "Dettmers et al. (2023)",
    ),
    (
        "Devlin2018_BERT.pdf",
        "BERT: Pre-training of Deep Bidirectional Transformers",
        "Devlin et al. (2018)",
    ),
    ("Edge2024_GraphRAG.pdf", "From Local to Global: A Graph RAG Approach", "Edge et al. (2024)"),
    ("Goodfellow2014_GAN.pdf", "Generative Adversarial Nets", "Goodfellow et al. (2014)"),
    ("Ho2020_DDPM.pdf", "Denoising Diffusion Probabilistic Models", "Ho, Jain & Abbeel (2020)"),
    ("Hochreiter1997_LSTM.pdf", "Long Short-Term Memory", "Hochreiter & Schmidhuber (1997)"),
    ("Hu2021_LoRA.pdf", "LoRA: Low-Rank Adaptation of Large Language Models", "Hu et al. (2021)"),
    (
        "Karpukhin2020_DPR.pdf",
        "Dense Passage Retrieval for Open-Domain QA",
        "Karpukhin et al. (2020)",
    ),
    ("Kingma2013_VAE.pdf", "Auto-Encoding Variational Bayes", "Kingma & Welling (2013)"),
    (
        "Kipf2016_GCN.pdf",
        "Semi-Supervised Classification with Graph Convolutional Networks",
        "Kipf & Welling (2016)",
    ),
    (
        "Krizhevsky2012_AlexNet.pdf",
        "ImageNet Classification with Deep Convolutional Neural Networks",
        "Krizhevsky et al. (2012)",
    ),
    (
        "Kwon2023_vLLM.pdf",
        "Efficient Memory Management for LLM Serving with PagedAttention",
        "Kwon et al. (2023)",
    ),
    (
        "LeCun1998_ConvNets.pdf",
        "Gradient-Based Learning Applied to Document Recognition",
        "LeCun et al. (1998)",
    ),
    (
        "Lewis2020_RAG.pdf",
        "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "Lewis et al. (2020)",
    ),
    (
        "Ouyang2022_InstructGPT.pdf",
        "Training Language Models to Follow Instructions with Human Feedback",
        "Ouyang et al. (2022)",
    ),
    ("Rafailov2023_DPO.pdf", "Direct Preference Optimization", "Rafailov et al. (2023)"),
    (
        "Rumelhart1986_Backpropagation.pdf",
        "Learning Representations by Back-Propagating Errors",
        "Rumelhart, Hinton & Williams (1986)",
    ),
    (
        "Vaswani2017_Attention_Is_All_You_Need.pdf",
        "Attention Is All You Need",
        "Vaswani et al. (2017)",
    ),
    ("Velickovic2017_GAT.pdf", "Graph Attention Networks", "Velickovic et al. (2017)"),
    (
        "Wei2022_ChainOfThought.pdf",
        "Chain-of-Thought Prompting Elicits Reasoning in LLMs",
        "Wei et al. (2022)",
    ),
    (
        "Willard2023_Outlines.pdf",
        "Efficient Guided Generation for Large Language Models",
        "Willard & Louf (2023)",
    ),
    (
        "Yao2022_ReAct.pdf",
        "ReAct: Synergizing Reasoning and Acting in Language Models",
        "Yao et al. (2022)",
    ),
)

_EXCLUDED_COMMERCIAL: tuple[tuple[str, str, str, str], ...] = (
    (
        "clrs_algorithms",
        "Introduction to Algorithms (CLRS 4e)",
        "Cormen, Leiserson, Rivest & Stein",
        "Data Structures & Algorithms",
    ),
    (
        "tanenbaum_networks",
        "Computer Networks (6e)",
        "Andrew S. Tanenbaum et al.",
        "Computer Networks",
    ),
    (
        "dragon_book_compilers",
        "Compilers: Principles, Techniques, and Tools (Dragon Book 2e)",
        "Aho, Lam, Sethi & Ullman",
        "Compiler Design",
    ),
    (
        "silberschatz_os",
        "Operating System Concepts (10e)",
        "Silberschatz, Galvin & Gagne",
        "Operating Systems",
    ),
    (
        "silberschatz_db",
        "Database System Concepts (7e)",
        "Silberschatz, Korth & Sudarshan",
        "Database Systems",
    ),
    (
        "hopcroft_automata",
        "Introduction to Automata Theory, Languages, and Computation",
        "Hopcroft, Motwani & Ullman",
        "Automata Theory",
    ),
    (
        "ross_probability",
        "A First Course in Probability (9e)",
        "Sheldon Ross",
        "Probability & Statistics",
    ),
    (
        "stallings_security",
        "Cryptography and Network Security (8e)",
        "William Stallings",
        "Information Security",
    ),
    ("sommerville_se", "Software Engineering (10e)", "Ian Sommerville", "Software Engineering"),
    (
        "mano_architecture",
        "Computer System Architecture (3e)",
        "M. Morris Mano",
        "Computer Architecture",
    ),
    (
        "russell_norvig_ai",
        "Artificial Intelligence: A Modern Approach (4e)",
        "Stuart Russell & Peter Norvig",
        "AI & Machine Learning",
    ),
    (
        "pearson_uem_holdings",
        "UEM Institutional Pearson eLibrary Holdings (40 titles)",
        "Pearson Education (Institutional)",
        "Operating Systems",
    ),
)


def _build_baseline_v2_sources() -> list[SourceSpec]:
    """Return the 43 baseline open-access PDFs carried forward from corpus_v2_d10_3025."""
    specs: list[SourceSpec] = []
    for filename, chapter_title in _OSTEP_CHAPTERS:
        doc_id = f"archipelago-books-cs/ostep_three_easy_pieces/{filename}"
        slug = filename.replace(".pdf", "").lower()
        specs.append(
            SourceSpec(
                source_id=f"ostep_{slug}",
                doc_id=doc_id,
                title=f"Operating Systems: Three Easy Pieces — {chapter_title}",
                authors="Remzi H. Arpaci-Dusseau & Andrea C. Arpaci-Dusseau",
                domain="Operating Systems",
                secondary_domains=(),
                source_format=SourceFormat.PDF,
                license_name="Author Free Open Textbook (OSTEP Online)",
                license_status=LicenseStatus.APPROVED_OA,
                license_url="https://pages.cs.wisc.edu/~remzi/OSTEP/",
                canonical_url="https://pages.cs.wisc.edu/~remzi/OSTEP/",
                origin="baseline_v2_hf_cache",
                independent_group="ostep_arpaci_dusseau",
                notes="Re-extracted from pinned corpus_v2_d10_3025 cache with D14 structural filtering.",
                local_rel_path=doc_id,
            )
        )
    specs.append(
        SourceSpec(
            source_id="deisenroth_math_for_ml",
            doc_id="books/textbooks/Deisenroth_Math_For_ML.pdf",
            title="Mathematics for Machine Learning",
            authors="Marc Peter Deisenroth, A. Aldo Faisal & Cheng Soon Ong",
            domain="Mathematics for ML",
            secondary_domains=("Probability & Statistics", "AI & Machine Learning"),
            source_format=SourceFormat.PDF,
            license_name="Author Free Open PDF (Cambridge Univ. Press / mml-book)",
            license_status=LicenseStatus.APPROVED_OA,
            license_url="https://mml-book.github.io/",
            canonical_url="https://mml-book.github.io/book/mml-book.pdf",
            origin="baseline_v2_hf_cache",
            independent_group="deisenroth_mml",
            notes="Re-extracted from pinned corpus_v2_d10_3025 cache with printed-page mapping.",
            local_rel_path="books/textbooks/Deisenroth_Math_For_ML.pdf",
        )
    )
    for filename, title, authors in _BASELINE_ML_PAPERS:
        doc_id = f"books/papers/{filename}"
        slug = filename.replace(".pdf", "").lower()
        secondary: tuple[str, ...] = ()
        if "vLLM" in filename:
            secondary = ("Operating Systems",)
        elif "VAE" in filename or "DDPM" in filename:
            secondary = ("Probability & Statistics",)
        specs.append(
            SourceSpec(
                source_id=f"paper_{slug}",
                doc_id=doc_id,
                title=title,
                authors=authors,
                domain="AI & Machine Learning",
                secondary_domains=secondary,
                source_format=SourceFormat.PDF,
                license_name="arXiv / Open-Access Research Paper",
                license_status=LicenseStatus.APPROVED_OA,
                license_url="https://arxiv.org/licenses/nonexclusive-distrib/1.0/",
                canonical_url=f"https://huggingface.co/datasets/{PARENT_HF_REPO_ID}",
                origin="baseline_v2_hf_cache",
                independent_group=f"paper_{slug}",
                notes="Re-extracted from pinned corpus_v2_d10_3025 cache with reference/footer filtering.",
                local_rel_path=doc_id,
            )
        )
    return specs


def _build_excluded_commercial_sources() -> list[SourceSpec]:
    """Explicitly register commercial/institutional holdings blocked from OA ingestion."""
    return [
        SourceSpec(
            source_id=f"excluded_{sid}",
            doc_id=f"metadata_only/{sid}",
            title=title,
            authors=authors,
            domain=domain,
            secondary_domains=(),
            source_format=SourceFormat.CATALOG_CARD,
            license_name="All Rights Reserved / Commercial Copyright",
            license_status=LicenseStatus.PROHIBITED_COMMERCIAL,
            license_url="",
            canonical_url="",
            origin="excluded_commercial",
            independent_group=f"excluded_{sid}",
            notes="Blocked by D14 license gate; metadata-only catalogue reference, never ingested as full text.",
        )
        for sid, title, authors, domain in _EXCLUDED_COMMERCIAL
    ]


def build_default_source_catalog() -> list[SourceSpec]:
    """Return the complete D14 source catalog (approved OA + excluded commercial audit rows)."""
    return (
        _build_baseline_v2_sources()
        + build_d14_new_oa_sources()
        + _build_excluded_commercial_sources()
    )
