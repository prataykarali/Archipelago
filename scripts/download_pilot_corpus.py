#!/usr/bin/env python3
"""
download_pilot_corpus.py — Download papers & create book directories for
the Archipelago pilot project, then upload to HuggingFace.

Papers: 25 total (5 existing + 20 new) in 5 conceptual clusters
Books:  6 CS textbooks (DBMS ×2, DSA ×2, OS ×2)

Usage:
    python scripts/download_pilot_corpus.py                     # download only
    python scripts/download_pilot_corpus.py --upload-hf         # download + upload to HF
    python scripts/download_pilot_corpus.py --skip-download     # upload existing files only
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
PAPERS_DIR = BASE / "pdfs" / "papers"
BOOKS_BASE = BASE / "pdfs" / "archipelago-books-cs"

HF_TOKEN = os.environ.get("HF_TOKEN")
HF_REPO = "Prataykarali/archipelago-books-cs"

# ═══════════════════════════════════════════════════════════════════════
# PAPER CATALOG — 25 papers in 5 conceptual clusters
# ═══════════════════════════════════════════════════════════════════════

PAPERS = [
    # ── Cluster 1: Foundations & Classical Neural Architectures ──
    {
        "filename": "Rumelhart1986_Backpropagation.pdf",
        "urls": [
            "https://www.cs.toronto.edu/~hinton/absps/naturebp.pdf",
        ],
        "cluster": "01_foundations",
        "title": "Learning Representations by Back-Propagating Errors",
        "authors": "Rumelhart, Hinton, Williams",
        "year": 1986,
        "requires": ["Calculus", "Matrix Multiplication"],
        "unlocks": ["Multilayer Perceptrons", "Backpropagation"],
    },
    {
        "filename": "LeCun1998_ConvNets.pdf",
        "urls": [
            "http://yann.lecun.com/exdb/publis/pdf/lecun-01a.pdf",
        ],
        "cluster": "01_foundations",
        "title": "Gradient-Based Learning Applied to Document Recognition",
        "authors": "LeCun, Bottou, Bengio, Haffner",
        "year": 1998,
        "requires": ["Backpropagation", "Convolution Operations"],
        "unlocks": ["CNNs", "Spatial Feature Extraction"],
    },
    {
        "filename": "Hochreiter1997_LSTM.pdf",
        "urls": [
            "https://www.bioinf.jku.at/publications/older/2604.pdf",
        ],
        "cluster": "01_foundations",
        "title": "Long Short-Term Memory",
        "authors": "Hochreiter, Schmidhuber",
        "year": 1997,
        "requires": ["Recurrent Neural Networks", "Vanishing Gradients"],
        "unlocks": ["Gated Memory Cells", "Sequence Modeling"],
    },
    {
        "filename": "Krizhevsky2012_AlexNet.pdf",
        "urls": [
            "https://proceedings.neurips.cc/paper_files/paper/2012/file/c399862d3b9d6b76c8436e924a68c45b-Paper.pdf",
        ],
        "cluster": "01_foundations",
        "title": "ImageNet Classification with Deep Convolutional Neural Networks",
        "authors": "Krizhevsky, Sutskever, Hinton",
        "year": 2012,
        "requires": ["CNNs", "GPU Acceleration", "Dropout"],
        "unlocks": ["Modern Deep Learning", "Computer Vision Benchmarks"],
    },

    # ── Cluster 2: Transformers, LLMs & Reasoning ──
    {
        "filename": "Bahdanau2014_Attention.pdf",
        "urls": ["https://arxiv.org/pdf/1409.0473"],
        "cluster": "02_transformers_llms",
        "title": "Neural Machine Translation by Jointly Learning to Align and Translate",
        "authors": "Bahdanau, Cho, Bengio",
        "year": 2014,
        "requires": ["Sequence-to-Sequence", "LSTMs"],
        "unlocks": ["Soft Attention Mechanisms"],
    },
    {
        "filename": "Vaswani2017_Attention_Is_All_You_Need.pdf",
        "urls": ["https://arxiv.org/pdf/1706.03762"],
        "cluster": "02_transformers_llms",
        "title": "Attention Is All You Need",
        "authors": "Vaswani et al.",
        "year": 2017,
        "requires": ["Attention Mechanism", "Matrix Projection"],
        "unlocks": ["Self-Attention", "Multi-Head Attention", "Transformer Architecture"],
        "exists": True,
    },
    {
        "filename": "Devlin2018_BERT.pdf",
        "urls": ["https://arxiv.org/pdf/1810.04805"],
        "cluster": "02_transformers_llms",
        "title": "BERT: Pre-training of Deep Bidirectional Transformers",
        "authors": "Devlin, Chang, Lee, Toutanova",
        "year": 2018,
        "requires": ["Transformer Encoders", "Masked Language Modeling"],
        "unlocks": ["Bidirectional Contextual Embeddings"],
        "exists": True,
    },
    {
        "filename": "Brown2020_GPT3.pdf",
        "urls": ["https://arxiv.org/pdf/2005.14165"],
        "cluster": "02_transformers_llms",
        "title": "Language Models are Few-Shot Learners",
        "authors": "Brown et al.",
        "year": 2020,
        "requires": ["Autoregressive Transformers", "Scaling Laws"],
        "unlocks": ["In-Context Learning", "Few-Shot Prompting"],
    },
    {
        "filename": "Wei2022_ChainOfThought.pdf",
        "urls": ["https://arxiv.org/pdf/2201.11903"],
        "cluster": "02_transformers_llms",
        "title": "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models",
        "authors": "Wei et al.",
        "year": 2022,
        "requires": ["Few-Shot Prompting", "Autoregressive LLMs"],
        "unlocks": ["Intermediate Step Decomposition", "Multi-Hop Reasoning"],
    },
    {
        "filename": "Yao2022_ReAct.pdf",
        "urls": ["https://arxiv.org/pdf/2210.03629"],
        "cluster": "02_transformers_llms",
        "title": "ReAct: Synergizing Reasoning and Acting in Language Models",
        "authors": "Yao et al.",
        "year": 2022,
        "requires": ["Chain-of-Thought", "Tool Calling"],
        "unlocks": ["Agentic Workflows", "Dynamic Environment Interaction"],
    },

    # ── Cluster 3: PEFT & Systems ──
    {
        "filename": "Hu2021_LoRA.pdf",
        "urls": ["https://arxiv.org/pdf/2106.09685"],
        "cluster": "03_peft_systems",
        "title": "LoRA: Low-Rank Adaptation of Large Language Models",
        "authors": "Hu et al.",
        "year": 2021,
        "requires": ["Matrix Decomposition", "Singular Value Decomposition"],
        "unlocks": ["Low-Rank Adapter Weights", "Parameter-Efficient Tuning"],
        "exists": True,
    },
    {
        "filename": "Dettmers2023_QLoRA.pdf",
        "urls": ["https://arxiv.org/pdf/2305.14314"],
        "cluster": "03_peft_systems",
        "title": "QLoRA: Efficient Finetuning of Quantized LLMs",
        "authors": "Dettmers et al.",
        "year": 2023,
        "requires": ["LoRA", "NormalFloat4 Quantization"],
        "unlocks": ["Double Quantization", "Low-VRAM Fine-Tuning"],
    },
    {
        "filename": "Willard2023_Outlines.pdf",
        "urls": ["https://arxiv.org/pdf/2307.09702"],
        "cluster": "03_peft_systems",
        "title": "Efficient Guided Generation for Large Language Models",
        "authors": "Willard, Louf",
        "year": 2023,
        "requires": ["Context-Free Grammars", "Regular Expressions"],
        "unlocks": ["Finite State Machine Masking", "Structured JSON Generation"],
    },
    {
        "filename": "Kwon2023_vLLM.pdf",
        "urls": ["https://arxiv.org/pdf/2309.06180"],
        "cluster": "03_peft_systems",
        "title": "Efficient Memory Management for LLM Serving with PagedAttention",
        "authors": "Kwon et al.",
        "year": 2023,
        "requires": ["Virtual Memory Paging", "KV Caching"],
        "unlocks": ["Non-Contiguous Memory Allocation", "High-Throughput Serving"],
    },

    # ── Cluster 4: RAG, Vector & Graph Intelligence ──
    {
        "filename": "Lewis2020_RAG.pdf",
        "urls": ["https://arxiv.org/pdf/2005.11401"],
        "cluster": "04_rag_graph",
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive Tasks",
        "authors": "Lewis et al.",
        "year": 2020,
        "requires": ["Dense Vector Indexing", "Pre-trained Seq2Seq"],
        "unlocks": ["Non-Parametric Memory", "Grounded Text Generation"],
        "exists": True,
    },
    {
        "filename": "Karpukhin2020_DPR.pdf",
        "urls": ["https://arxiv.org/pdf/2004.04906"],
        "cluster": "04_rag_graph",
        "title": "Dense Passage Retrieval for Open-Domain Question Answering",
        "authors": "Karpukhin et al.",
        "year": 2020,
        "requires": ["Dual-Encoder Models", "Cosine Similarity"],
        "unlocks": ["Bi-Encoder Vector Embeddings"],
    },
    {
        "filename": "Kipf2016_GCN.pdf",
        "urls": ["https://arxiv.org/pdf/1609.02907"],
        "cluster": "04_rag_graph",
        "title": "Semi-Supervised Classification with Graph Convolutional Networks",
        "authors": "Kipf, Welling",
        "year": 2016,
        "requires": ["Graph Theory", "Adjacency Matrices", "Spectral Convolutions"],
        "unlocks": ["Graph Neural Networks (GCN)"],
    },
    {
        "filename": "Velickovic2017_GAT.pdf",
        "urls": ["https://arxiv.org/pdf/1710.10903"],
        "cluster": "04_rag_graph",
        "title": "Graph Attention Networks",
        "authors": "Veličković et al.",
        "year": 2017,
        "requires": ["Graph Convolution", "Self-Attention"],
        "unlocks": ["Edge Weighting", "Dynamic Graph Representation"],
    },
    {
        "filename": "Edge2024_GraphRAG.pdf",
        "urls": ["https://arxiv.org/pdf/2404.16130"],
        "cluster": "04_rag_graph",
        "title": "From Local to Global: A Graph RAG Approach to Query-Focused Summarization",
        "authors": "Edge et al.",
        "year": 2024,
        "requires": ["Graph Extraction", "Community Detection", "Text Summarization"],
        "unlocks": ["Hierarchical Graph RAG", "Global Dataset Queries"],
        "exists": True,
    },

    # ── Cluster 5: Generative Modeling & Alignment ──
    {
        "filename": "Goodfellow2014_GAN.pdf",
        "urls": ["https://arxiv.org/pdf/1406.2661"],
        "cluster": "05_generative_alignment",
        "title": "Generative Adversarial Nets",
        "authors": "Goodfellow et al.",
        "year": 2014,
        "requires": ["Minimax Game Theory", "Cross-Entropy Loss"],
        "unlocks": ["Generator-Discriminator Training"],
    },
    {
        "filename": "Kingma2013_VAE.pdf",
        "urls": ["https://arxiv.org/pdf/1312.6114"],
        "cluster": "05_generative_alignment",
        "title": "Auto-Encoding Variational Bayes",
        "authors": "Kingma, Welling",
        "year": 2013,
        "requires": ["Variational Inference", "KL Divergence"],
        "unlocks": ["Reparameterization Trick", "Latent Space Generation"],
    },
    {
        "filename": "Ho2020_DDPM.pdf",
        "urls": ["https://arxiv.org/pdf/2006.11239"],
        "cluster": "05_generative_alignment",
        "title": "Denoising Diffusion Probabilistic Models",
        "authors": "Ho, Jain, Abbeel",
        "year": 2020,
        "requires": ["Markov Chains", "Gaussian Noise Addition"],
        "unlocks": ["Reverse Denoising Dynamics", "Image Generation"],
    },
    {
        "filename": "Ouyang2022_InstructGPT.pdf",
        "urls": ["https://arxiv.org/pdf/2203.02155"],
        "cluster": "05_generative_alignment",
        "title": "Training Language Models to Follow Instructions with Human Feedback",
        "authors": "Ouyang et al.",
        "year": 2022,
        "requires": ["Reward Modeling", "Proximal Policy Optimization"],
        "unlocks": ["Human Preference Alignment (RLHF)"],
    },
    {
        "filename": "Rafailov2023_DPO.pdf",
        "urls": ["https://arxiv.org/pdf/2305.18290"],
        "cluster": "05_generative_alignment",
        "title": "Direct Preference Optimization",
        "authors": "Rafailov et al.",
        "year": 2023,
        "requires": ["RLHF", "Implicit Reward Formulations"],
        "unlocks": ["Closed-Form Preference Loss", "Stable Direct Fine-Tuning"],
    },
    {
        "filename": "Bai2022_ConstitutionalAI.pdf",
        "urls": ["https://arxiv.org/pdf/2212.08073"],
        "cluster": "05_generative_alignment",
        "title": "Constitutional AI: Harmlessness from AI Feedback",
        "authors": "Bai et al.",
        "year": 2022,
        "requires": ["RLHF", "Rule-Based Critiques"],
        "unlocks": ["Self-Critique Alignment", "RLAIF"],
    },
]

# ═══════════════════════════════════════════════════════════════════════
# BOOK CATALOG — 6 CS textbooks across 3 subjects
# ═══════════════════════════════════════════════════════════════════════

BOOKS = [
    # ── DBMS ──
    {
        "dirname": "database_system_concepts_silberschatz",
        "title": "Database System Concepts",
        "authors": "Abraham Silberschatz, Henry F. Korth, S. Sudarshan",
        "publisher": "McGraw Hill",
        "subject": "Database Management Systems",
        "requires": ["Relational Algebra", "B+ Trees", "Disk Storage Architectures"],
        "unlocks": ["Transaction Processing (ACID)", "Concurrency Control (2PL)",
                     "Write-Ahead Logging (WAL)", "Query Optimization"],
        "open_access": False,
    },
    {
        "dirname": "database_management_systems_ramakrishnan",
        "title": "Database Management Systems",
        "authors": "Raghu Ramakrishnan, Johannes Gehrke",
        "publisher": "McGraw Hill",
        "subject": "Database Management Systems",
        "requires": ["Functional Dependencies", "Set Theory"],
        "unlocks": ["Schema Normalization (3NF, BCNF)", "Buffer Pool Management",
                     "External Sorting", "Hash-based Indexing"],
        "open_access": False,
    },
    # ── DSA ──
    {
        "dirname": "introduction_to_algorithms_clrs",
        "title": "Introduction to Algorithms (CLRS)",
        "authors": "Thomas H. Cormen, Charles E. Leiserson, Ronald L. Rivest, Clifford Stein",
        "publisher": "MIT Press / McGraw Hill",
        "subject": "Data Structures and Algorithms",
        "requires": ["Discrete Math", "Proof Techniques", "Recurrence Relations"],
        "unlocks": ["Asymptotic Analysis", "Dynamic Programming", "Red-Black Trees",
                     "Amortized Analysis", "Graph Search (BFS, DFS, Dijkstra)"],
        "open_access": False,
    },
    {
        "dirname": "data_structures_algorithm_analysis_weiss",
        "title": "Data Structures and Algorithm Analysis in C++/Java",
        "authors": "Mark Allen Weiss",
        "publisher": "Pearson",
        "subject": "Data Structures and Algorithms",
        "requires": ["Arrays", "Pointers/References", "Recursion"],
        "unlocks": ["Priority Queues (Binary Heaps)", "Disjoint Set Union-Find",
                     "Splay Trees", "Hashing (Collision Resolution)"],
        "open_access": False,
    },
    # ── OS ──
    {
        "dirname": "operating_system_concepts_silberschatz",
        "title": "Operating System Concepts (The Dinosaur Book)",
        "authors": "Abraham Silberschatz, Peter B. Galvin, Greg Gagne",
        "publisher": "Wiley",
        "subject": "Operating Systems",
        "requires": ["Assembly/Machine Instructions", "Memory Addressing"],
        "unlocks": ["Process Scheduling", "Thread Concurrency & Synchronization",
                     "Virtual Memory (Paging, TLB)", "Deadlock Allocation Graphs"],
        "open_access": False,
    },
    {
        "dirname": "ostep_three_easy_pieces",
        "title": "Operating Systems: Three Easy Pieces (OSTEP)",
        "authors": "Remzi H. Arpaci-Dusseau, Andrea C. Arpaci-Dusseau",
        "publisher": "Arpaci-Dusseau Books (Open Access)",
        "subject": "Operating Systems",
        "requires": ["System Calls", "C Memory Layout (Stack vs Heap)"],
        "unlocks": ["Virtualization (CPU & Address Spaces)", "Concurrency Primitives",
                     "Log-structured File Systems (LFS)", "RAID Storage"],
        "open_access": True,
        "ostep_chapters": [
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/dialogue-threeeasy.pdf", "00_Dialogue.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/intro.pdf", "01_Introduction.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-intro.pdf", "02_CPU_Virtualization.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-api.pdf", "03_Process_API.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-mechanisms.pdf", "04_Limited_Direct_Execution.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/cpu-sched.pdf", "05_CPU_Scheduling.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/vm-intro.pdf", "06_Address_Spaces.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/vm-mechanism.pdf", "07_Address_Translation.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/vm-paging.pdf", "08_Paging.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/vm-tlbs.pdf", "09_TLBs.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/threads-intro.pdf", "10_Concurrency_Intro.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/threads-locks.pdf", "11_Locks.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/threads-sema.pdf", "12_Semaphores.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/threads-bugs.pdf", "13_Common_Bugs.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/file-devices.pdf", "14_IO_Devices.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/file-raid.pdf", "15_RAID.pdf"),
            ("https://pages.cs.wisc.edu/~remzi/OSTEP/file-lfs.pdf", "16_Log_Structured_FS.pdf"),
        ],
    },
]

# ═══════════════════════════════════════════════════════════════════════
# Download helpers
# ═══════════════════════════════════════════════════════════════════════

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) ArchipelagoBot/1.0 (research; pratay.karali@uem.edu.in)",
    "Accept": "application/pdf,*/*",
}


def _download_file(url: str, dest: Path, retries: int = 3) -> bool:
    """Download a file from url to dest with retries. Returns True on success."""
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"  ✓ Already exists: {dest.name} ({dest.stat().st_size:,} bytes)")
        return True

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
                data = resp.read()

            if len(data) < 1000:
                print(f"  ⚠ Too small ({len(data)} bytes) from {url}")
                return False

            if dest.name.endswith(".pdf") and not data.startswith(b"%PDF-"):
                print(f"  ⚠ Invalid PDF header (received HTML/error response) from {url}")
                return False

            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            print(f"  ✓ Downloaded: {dest.name} ({len(data):,} bytes)")
            return True

        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            print(f"  ⚠ Attempt {attempt}/{retries} failed for {dest.name}: {e}")
            if attempt < retries:
                time.sleep(2 * attempt)  # backoff

    return False


# ═══════════════════════════════════════════════════════════════════════
# Phase 1: Download papers
# ═══════════════════════════════════════════════════════════════════════

def download_papers() -> dict:
    """Download all papers to pdfs/papers/. Returns stats."""
    PAPERS_DIR.mkdir(parents=True, exist_ok=True)
    ok, skip, fail = 0, 0, 0

    print("\n" + "=" * 70)
    print("  📄 Downloading Research Papers")
    print("=" * 70)

    for paper in PAPERS:
        name = paper["filename"]
        dest = PAPERS_DIR / name

        if paper.get("exists") and dest.exists() and dest.stat().st_size > 1000:
            print(f"  ✓ Exists: {name}")
            skip += 1
            continue

        success = False
        for url in paper["urls"]:
            if _download_file(url, dest):
                success = True
                break
            time.sleep(1)  # be polite between URL attempts

        if success:
            ok += 1
        else:
            fail += 1
            print(f"  ✗ FAILED: {name}")

        time.sleep(1.5)  # rate limiting between papers

    stats = {"downloaded": ok, "skipped": skip, "failed": fail}
    print(f"\n  Papers: {ok} downloaded, {skip} skipped, {fail} failed")
    return stats


# ═══════════════════════════════════════════════════════════════════════
# Phase 2: Create book directories with metadata
# ═══════════════════════════════════════════════════════════════════════

def prepare_books() -> dict:
    """Create book directories with metadata JSON files.

    For open-access books (OSTEP), also downloads chapters.
    For copyrighted books, creates placeholder metadata.
    """
    print("\n" + "=" * 70)
    print("  📚 Preparing Book Directories")
    print("=" * 70)

    ok, chapters_dl = 0, 0
    need_user_pdfs = []

    for book in BOOKS:
        book_dir = BOOKS_BASE / book["dirname"]
        book_dir.mkdir(parents=True, exist_ok=True)

        # Write metadata JSON
        meta = {
            "title": book["title"],
            "authors": book["authors"],
            "publisher": book["publisher"],
            "subject": book["subject"],
            "requires": book["requires"],
            "unlocks": book["unlocks"],
            "open_access": book["open_access"],
            "compliance_note": "Per Jul 21 meeting: only index, TOC, content pages, "
                               "subheadings, and author info will be extracted — NO body text.",
        }
        meta_path = book_dir / "METADATA.json"
        json.dump(meta, open(meta_path, "w"), indent=2)
        print(f"\n  📁 {book['dirname']}/")
        print(f"     Title: {book['title']}")
        print(f"     Authors: {book['authors']}")
        print(f"     Subject: {book['subject']}")

        # Download OSTEP chapters (open-access)
        if book.get("ostep_chapters"):
            print(f"     Downloading {len(book['ostep_chapters'])} OSTEP chapters...")
            for url, chap_name in book["ostep_chapters"]:
                dest = book_dir / chap_name
                if _download_file(url, dest):
                    chapters_dl += 1
                time.sleep(0.5)

        elif not book["open_access"]:
            # Create README for user to add PDFs
            readme = (
                f"# {book['title']}\n\n"
                f"**Authors:** {book['authors']}\n"
                f"**Publisher:** {book['publisher']}\n"
                f"**Subject:** {book['subject']}\n\n"
                f"## 📥 Action Required\n\n"
                f"This is a copyrighted textbook. Please add the PDF file(s) to this directory.\n"
                f"Per the Jul 21 meeting rules, only **index, TOC, content pages, subheadings,\n"
                f"and author info** will be extracted — no body text.\n\n"
                f"## Graph Concepts\n"
                f"- REQUIRES: {', '.join(book['requires'])}\n"
                f"- UNLOCKS: {', '.join(book['unlocks'])}\n"
            )
            (book_dir / "README.md").write_text(readme)
            need_user_pdfs.append(book["title"])

        ok += 1

    if need_user_pdfs:
        print(f"\n  ⚠ {len(need_user_pdfs)} books need PDFs from you:")
        for t in need_user_pdfs:
            print(f"    • {t}")

    stats = {"books_prepared": ok, "chapters_downloaded": chapters_dl,
             "need_user_pdfs": len(need_user_pdfs)}
    return stats


# ═══════════════════════════════════════════════════════════════════════
# Phase 3: Build categorization manifest
# ═══════════════════════════════════════════════════════════════════════

def build_manifest() -> dict:
    """Build a comprehensive CORPUS_MANIFEST.json for the pilot."""
    manifest = {
        "project": "Archipelago Pilot — Jul 21 2026",
        "hf_dataset": HF_REPO,
        "compliance": {
            "books": "Index, TOC, content pages, subheadings, author info ONLY. No body text.",
            "papers": "Full text allowed (priority content).",
            "scope": "3 subjects (DBMS, DSA, OS) + AI/ML pilot, 6 new books, 25 papers.",
        },
        "paper_clusters": {},
        "books_by_subject": {},
        "papers_total": 0,
        "books_total": 0,
    }

    # Papers
    clusters: dict[str, list] = {}
    for p in PAPERS:
        cl = p["cluster"]
        clusters.setdefault(cl, []).append({
            "filename": p["filename"],
            "title": p["title"],
            "authors": p["authors"],
            "year": p["year"],
            "requires": p["requires"],
            "unlocks": p["unlocks"],
            "exists_locally": (PAPERS_DIR / p["filename"]).exists(),
        })
    manifest["paper_clusters"] = clusters
    manifest["papers_total"] = len(PAPERS)

    # Books
    by_subject: dict[str, list] = {}
    for b in BOOKS:
        subj = b["subject"]
        book_dir = BOOKS_BASE / b["dirname"]
        pdf_count = len(list(book_dir.glob("*.pdf"))) if book_dir.exists() else 0
        by_subject.setdefault(subj, []).append({
            "dirname": b["dirname"],
            "title": b["title"],
            "authors": b["authors"],
            "publisher": b["publisher"],
            "open_access": b["open_access"],
            "pdfs_present": pdf_count,
            "requires": b["requires"],
            "unlocks": b["unlocks"],
        })
    manifest["books_by_subject"] = by_subject
    manifest["books_total"] = len(BOOKS)

    # Domain bridges
    manifest["domain_bridges"] = [
        {
            "bridge": "B+ Trees & Disk Indexing",
            "path": "Weiss (DSA) → Silberschatz (DBMS) → OSTEP (OS Storage)",
        },
        {
            "bridge": "Concurrency & Deadlocks",
            "path": "Silberschatz (OS) → Ramakrishnan (DBMS Concurrency Control)",
        },
        {
            "bridge": "Graph Traversals",
            "path": "CLRS (DSA) → KùzuDB / Network Science / AI Graph RAG",
        },
    ]

    manifest_path = BOOKS_BASE / "CORPUS_MANIFEST.json"
    json.dump(manifest, open(manifest_path, "w"), indent=2)
    print(f"\n  📋 Manifest saved: {manifest_path}")
    return manifest


# ═══════════════════════════════════════════════════════════════════════
# Phase 4: Upload to HuggingFace
# ═══════════════════════════════════════════════════════════════════════

def upload_to_huggingface():
    """Upload new papers, book directories, and manifest to HF dataset."""
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("  ✗ huggingface_hub not installed. Install: pip install huggingface_hub")
        return

    print("\n" + "=" * 70)
    print("  ☁️  Uploading to HuggingFace")
    print(f"  Repo: {HF_REPO}")
    print("=" * 70)

    api = HfApi(token=HF_TOKEN)
    uploaded, failed = 0, 0

    # Upload papers
    for paper in PAPERS:
        local = PAPERS_DIR / paper["filename"]
        if not local.exists():
            continue
        hf_path = f"papers/{paper['filename']}"
        try:
            api.upload_file(
                path_or_fileobj=str(local),
                path_in_repo=hf_path,
                repo_id=HF_REPO,
                repo_type="dataset",
            )
            print(f"  ✓ Uploaded paper: {paper['filename']}")
            uploaded += 1
        except Exception as e:
            print(f"  ✗ Failed paper {paper['filename']}: {e}")
            failed += 1

    # Upload book directories (metadata + any PDFs)
    for book in BOOKS:
        book_dir = BOOKS_BASE / book["dirname"]
        if not book_dir.exists():
            continue
        for f in book_dir.iterdir():
            if f.is_file():
                hf_path = f"{book['dirname']}/{f.name}"
                try:
                    api.upload_file(
                        path_or_fileobj=str(f),
                        path_in_repo=hf_path,
                        repo_id=HF_REPO,
                        repo_type="dataset",
                    )
                    uploaded += 1
                except Exception as e:
                    print(f"  ✗ Failed {f.name}: {e}")
                    failed += 1

    # Upload manifest
    manifest_path = BOOKS_BASE / "CORPUS_MANIFEST.json"
    if manifest_path.exists():
        try:
            api.upload_file(
                path_or_fileobj=str(manifest_path),
                path_in_repo="CORPUS_MANIFEST.json",
                repo_id=HF_REPO,
                repo_type="dataset",
            )
            print(f"  ✓ Uploaded CORPUS_MANIFEST.json")
            uploaded += 1
        except Exception as e:
            print(f"  ✗ Manifest upload failed: {e}")
            failed += 1

    # Update INVENTORY.json
    inv = {
        "hf_dataset": HF_REPO,
        "books_count": 5 + len(BOOKS),  # 5 existing + 6 new
        "paper_count": len(PAPERS),
        "books_existing": [
            "artificial_intelligence_a_new_synthesis_1998 (36)",
            "data_science_2019 (25)",
            "knowledge_representation_and_reasoning_2004 (21)",
            "pattern_recognition_2009 (23)",
            "predictive_analytics_and_data_mining_2015 (22)",
        ],
        "books_new": [b["dirname"] for b in BOOKS],
        "paper_clusters": {
            "01_foundations": 4,
            "02_transformers_llms": 6,
            "03_peft_systems": 4,
            "04_rag_graph": 5,
            "05_generative_alignment": 6,
        },
        "subjects": [
            "Database Management Systems",
            "Data Structures and Algorithms",
            "Operating Systems",
            "AI/ML (pilot corpus)",
        ],
        "updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    inv_path = BOOKS_BASE / "INVENTORY.json"
    json.dump(inv, open(inv_path, "w"), indent=2)
    try:
        api.upload_file(
            path_or_fileobj=str(inv_path),
            path_in_repo="INVENTORY.json",
            repo_id=HF_REPO,
            repo_type="dataset",
        )
        uploaded += 1
    except Exception:
        pass

    print(f"\n  Upload complete: {uploaded} uploaded, {failed} failed")
    print(f"  👉 https://huggingface.co/datasets/{HF_REPO}")


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser(description="Download pilot corpus & upload to HuggingFace")
    ap.add_argument("--upload-hf", action="store_true", help="Upload to HuggingFace after download")
    ap.add_argument("--skip-download", action="store_true", help="Skip downloads, upload existing only")
    args = ap.parse_args()

    print("=" * 70)
    print("  🏝️  Archipelago Pilot Corpus Builder")
    print("  Jul 21 2026 — Compliant with meeting rules")
    print("=" * 70)
    print(f"  Papers dir : {PAPERS_DIR}")
    print(f"  Books base : {BOOKS_BASE}")
    print(f"  HF repo    : {HF_REPO}")

    if not args.skip_download:
        paper_stats = download_papers()
        book_stats = prepare_books()
    else:
        paper_stats = {"downloaded": 0, "skipped": 0, "failed": 0}
        book_stats = {"books_prepared": 0, "chapters_downloaded": 0}

    manifest = build_manifest()

    if args.upload_hf:
        upload_to_huggingface()

    # Final summary
    print("\n" + "=" * 70)
    print("  📊 Summary")
    print("=" * 70)
    existing = sum(1 for p in PAPERS if (PAPERS_DIR / p["filename"]).exists())
    print(f"  Papers ready: {existing}/{len(PAPERS)}")
    for cl_name in sorted(set(p["cluster"] for p in PAPERS)):
        cl_papers = [p for p in PAPERS if p["cluster"] == cl_name]
        ready = sum(1 for p in cl_papers if (PAPERS_DIR / p["filename"]).exists())
        print(f"    {cl_name}: {ready}/{len(cl_papers)}")

    books_with_pdfs = 0
    for b in BOOKS:
        d = BOOKS_BASE / b["dirname"]
        if d.exists() and list(d.glob("*.pdf")):
            books_with_pdfs += 1
    print(f"\n  Books with PDFs: {books_with_pdfs}/{len(BOOKS)}")
    for b in BOOKS:
        d = BOOKS_BASE / b["dirname"]
        n = len(list(d.glob("*.pdf"))) if d.exists() else 0
        icon = "✓" if n > 0 else "⚠"
        note = f"({n} PDFs)" if n > 0 else "(needs PDFs from you)"
        oa = " [Open Access]" if b["open_access"] else ""
        print(f"    {icon} {b['title']}{oa} {note}")

    if not args.upload_hf:
        print(f"\n  💡 Run with --upload-hf to push to HuggingFace")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
