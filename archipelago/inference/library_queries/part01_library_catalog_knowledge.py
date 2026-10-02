"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import re
from . import _deps as _rt  # noqa: F401


LIBRARY_CATALOG_KNOWLEDGE = {
    "attention_is_all_you_need": {
        "title": "Attention Is All You Need",
        "aliases": ["attention is all you need", "vaswani", "transformer paper", "attention paper", "transformer"],
        "authors": "Ashish Vaswani, Noam Shazeer, Niki Parmar, Jakob Uszkoreit, Llion Jones, Aidan N. Gomez, Łukasz Kaiser, Illia Polosukhin",
        "year": "2017",
        "domain": "Artificial Intelligence / Deep Learning & NLP",
        "format": "Seminal Research Paper (arXiv:1706.03762)",
        "shelf_location": "AIML-NLP-02 (Central Library Pilot Collection)",
        "total_copies": 4,
        "available_copies": 3,
        "pdf_path": "/library?book=paper_vaswani2017_attention#book-reader",
        "summary": "Introduces the Transformer model architecture based entirely on self-attention mechanisms, dispensing with recurrence and convolutions entirely. Achieved state-of-the-art results on English-to-German and English-to-French translation with significantly higher parallelizability and reduced training time.",
        "key_sections": [
            "1. Introduction & Background",
            "2. Model Architecture (Multi-Head Attention, Scaled Dot-Product Attention)",
            "3. Positional Encoding (Sinusoidal frequencies)",
            "4. Why Self-Attention (Computational complexity per layer & maximum path length)",
            "5. Training & Regularization (Dropout, Label Smoothing, Adam with warmup)",
            "6. Results on WMT 2014 Translation Benchmarks"
        ],
        "prerequisites": ["Matrix Multiplication", "Softmax Function", "Linear Projections", "Word Embeddings"],
        "unlocks": ["BERT", "GPT Architecture", "LoRA / PEFT", "Vision Transformers (ViT)"]
    },
    "deep_learning_goodfellow": {
        "title": "Deep Learning (Adaptive Computation and Machine Learning series)",
        "aliases": ["deep learning", "goodfellow", "bengio", "courville", "ian goodfellow deep learning", "deep learning book"],
        "authors": "Ian Goodfellow, Yoshua Bengio, Aaron Courville",
        "year": "2016",
        "domain": "Deep Learning / Machine Learning Theory",
        "format": "Hardcover Textbook & Open Access Edition (MIT Press)",
        "shelf_location": "DL-01 / Shelf B3 (Central Library)",
        "total_copies": 5,
        "available_copies": 5,
        "pdf_path": "/library#shelf",
        "summary": "The canonical comprehensive textbook on deep learning theory, covering linear algebra and probability prerequisites, deep feedforward networks, regularization, optimization, convolutional networks, sequence modeling, autoencoders, and generative models (GANs).",
        "key_sections": [
            "Part I: Applied Math and Machine Learning Basics (Linear Algebra, Probability, Numerical Computation)",
            "Part II: Deep Networks: Modern Practices (Feedforward Nets, Regularization, Optimization)",
            "Part III: Deep Learning Research (Autoencoders, Representation Learning, Generative Models / GANs)"
        ],
        "prerequisites": ["Linear Algebra", "Calculus & Gradients", "Probability Distributions"],
        "unlocks": ["Modern Deep Learning Architecture Research", "Generative Modeling", "Representation Learning"]
    },
    "operating_systems_three_easy_pieces": {
        "title": "Operating Systems: Three Easy Pieces (OSTEP)",
        "aliases": ["operating systems: three easy pieces", "ostep", "remzi", "three easy pieces", "arpaci-dusseau"],
        "authors": "Remzi H. Arpaci-Dusseau, Andrea C. Arpaci-Dusseau",
        "year": "2018",
        "domain": "Operating Systems & Computer Systems",
        "format": "Textbook (Arpaci-Dusseau Books / Open Access)",
        "shelf_location": "OS-01 (Stack Area Floor 2)",
        "total_copies": 7,
        "available_copies": 4,
        "pdf_path": "/library?book=ostep_three_easy_pieces#book-reader",
        "summary": "Comprehensive conceptual and practical textbook on modern operating systems organized around three fundamental pillars: Virtualization (CPU & memory), Concurrency (threads, locks, semaphores), and Persistence (I/O devices, hard drives, file systems, RAID, and crash consistency).",
        "key_sections": [
            "I. Virtualization (Processes, CPU Scheduling, Address Spaces, Paging, TLBs, Multi-level Page Tables)",
            "II. Concurrency (Threads, Locks, Condition Variables, Semaphores, Concurrency Bugs)",
            "III. Persistence (I/O Devices, Hard Disks, Flash SSDs, File System Implementation, FSCK & Journaling, RAID, Distributed Systems)"
        ],
        "prerequisites": ["C Programming", "Computer Organization & Architecture"],
        "unlocks": ["Kernel Development", "Distributed Systems", "Database Storage Engines"]
    },
    "database_system_concepts": {
        "title": "Database System Concepts (7th Edition)",
        "aliases": ["database system concepts", "silberschatz database", "korth", "sudarshan", "silberschatz dbms"],
        "authors": "Abraham Silberschatz, Henry F. Korth, S. Sudarshan",
        "year": "2019",
        "domain": "Database Management Systems",
        "format": "Textbook (McGraw Hill)",
        "shelf_location": "DBMS-01 / Reference Section",
        "total_copies": 4,
        "available_copies": 4,
        "pdf_path": "/library#shelf",
        "summary": "The definitive textbook covering relational model, SQL, index architectures (B+ trees, hash indices), query processing and cost-based optimization, transaction management (ACID, concurrency control, 2PL, ARIES recovery), and distributed data stores.",
        "key_sections": [
            "Part 1: Relational Languages & SQL",
            "Part 2: Storage Management and Indexing (Buffer Pools, B+ Tree Indexing)",
            "Part 3: Query Processing and Optimization",
            "Part 4: Transaction Management (ACID, Concurrency Control, Recovery Systems)",
            "Part 5: Distributed & NoSQL Architecture"
        ],
        "prerequisites": ["Data Structures", "Discrete Mathematics"],
        "unlocks": ["High-Performance Database Internals", "Data Engineering", "Distributed Storage"]
    },
    "lora_paper": {
        "title": "LoRA: Low-Rank Adaptation of Large Language Models",
        "aliases": ["lora", "low-rank adaptation", "hu2021", "edward hu", "peft lora"],
        "authors": "Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, Weizhu Chen",
        "year": "2021",
        "domain": "Artificial Intelligence / Parameter-Efficient Fine-Tuning (PEFT)",
        "format": "Research Paper (arXiv:2106.09685)",
        "shelf_location": "AIML-PEFT-01 (Central Library)",
        "total_copies": 3,
        "available_copies": 2,
        "pdf_path": "/library?book=paper_hu2021_lora#book-reader",
        "summary": "Freezes pre-trained model weights and injects trainable rank decomposition matrices into each Transformer layer, drastically reducing the number of trainable parameters for downstream tasks by up to 10,000x and GPU memory requirements by 3x with no inference latency penalty.",
        "key_sections": [
            "1. Problem Statement & Efficiency Challenges in Full Fine-Tuning",
            "2. Aren't Pre-Trained Models Low-Rank? (Intrinsic Rank Hypothesis)",
            "3. Method: Parameterized Low-Rank Decomposition W = W0 + B*A",
            "4. Empirical Evaluation on GPT-3, RoBERTa, and DeBERTa",
            "5. Subspace Similarity & Rank Analysis"
        ],
        "prerequisites": ["Linear Algebra (Matrix Rank, SVD)", "Transformer Architecture", "Gradient Descent Fine-Tuning"],
        "unlocks": ["QLoRA (4-bit Quantized LoRA)", "PEFT Deployment", "On-Device LLM Fine-Tuning"]
    },
    "bert_paper": {
        "title": "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
        "aliases": ["bert", "devlin", "pre-training of deep bidirectional transformers", "bert paper"],
        "authors": "Jacob Devlin, Ming-Wei Chang, Kenton Lee, Kristina Toutanova",
        "year": "2018",
        "domain": "Natural Language Processing / Foundation Models",
        "format": "Research Paper (NAACL-HLT 2019 / arXiv:1810.04805)",
        "shelf_location": "AIML-NLP-01",
        "total_copies": 5,
        "available_copies": 4,
        "pdf_path": "/library?book=paper_devlin2018_bert#book-reader",
        "summary": "Introduces BERT, a bi-directionally trained language representation model using Masked Language Modeling (MLM) and Next Sentence Prediction (NSP). Established foundational benchmarks across 11 NLP tasks including GLUE, MultiNLI, and SQuAD.",
        "key_sections": [
            "1. Introduction: Feature-based vs Fine-tuning Approaches",
            "2. BERT Model Architecture (Transformer Encoder Stack)",
            "3. Pre-training Tasks: Masked LM (Cloze Task) & Next Sentence Prediction",
            "4. Fine-tuning Procedure for Classification, QA, and Tagging",
            "5. Ablation Studies (Effect of Pre-training Tasks, Model Size, Number of Steps)"
        ],
        "prerequisites": ["Transformer Encoder", "Self-Attention Mechanism", "WordPiece Tokenization"],
        "unlocks": ["RoBERTa", "DeBERTa", "Dense Passage Retrieval (DPR)", "Modern Cross-Encoders"]
    },
    "math_for_ml": {
        "title": "Mathematics for Machine Learning",
        "aliases": ["mathematics for machine learning", "deisenroth", "math for ml", "maths for ml"],
        "authors": "Marc Peter Deisenroth, A. Aldo Faisal, Cheng Soon Ong",
        "year": "2020",
        "domain": "Applied Mathematics & Machine Learning Foundations",
        "format": "Textbook (Cambridge University Press)",
        "shelf_location": "AIML-MATH-01",
        "total_copies": 5,
        "available_copies": 5,
        "pdf_path": "/library#shelf",
        "summary": "Presents foundational mathematical concepts for modern ML: linear algebra, analytic geometry, matrix decompositions, vector calculus, probability, and continuous optimization, bridging theory with practical algorithms like linear regression, PCA, GMMs, and SVMs.",
        "key_sections": [
            "Part I: Mathematical Foundations (Linear Algebra, Analytic Geometry, Matrix Decompositions, Vector Calculus, Probability & Distributions, Continuous Optimization)",
            "Part II: Central Machine Learning Problems (Linear Regression, PCA Dimensionality Reduction, Gaussian Mixture Models, Support Vector Machines)"
        ],
        "prerequisites": ["High School Calculus", "Basic Algebra"],
        "unlocks": ["Advanced Machine Learning", "Deep Learning Theory", "Optimization for Neural Networks"]
    },
    "rag_paper": {
        "title": "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks",
        "aliases": ["rag", "retrieval-augmented generation", "lewis", "patrick lewis", "rag paper"],
        "authors": "Patrick Lewis, Ethan Perez, Aleksandara Piktus, Fabio Petroni, Vladimir Karpukhin, Naman Goyal, Heinrich Küttler, Mike Lewis, Wen-tau Yih, Tim Rocktäschel, Sebastian Riedel, Douwe Kiela",
        "year": "2020",
        "domain": "Natural Language Processing / Information Retrieval",
        "format": "Research Paper (NeurIPS 2020)",
        "shelf_location": "AIML-RAG-01",
        "total_copies": 4,
        "available_copies": 3,
        "pdf_path": "/library?book=paper_lewis2020_rag#book-reader",
        "summary": "Combines pre-trained parametric memory (seq2seq generator) with non-parametric memory (dense vector index of Wikipedia accessed via DPR), demonstrating superior open-domain question answering, fact checking, and abstractive QA with lower hallucination rates.",
        "key_sections": [
            "1. Introduction: Parametric vs Non-Parametric Memory",
            "2. RAG Models: RAG-Sequence vs RAG-Token Architectures",
            "3. Dense Passage Retriever (DPR) Integration & Maximum Inner Product Search (MIPS)",
            "4. Training & Joint End-to-End Fine-Tuning",
            "5. Experiments on Open-domain QA (Natural Questions, CuratedTREC, WebQuestions, MS-MARCO)"
        ],
        "prerequisites": ["Transformer Seq2Seq Architecture", "Dense Embeddings", "Vector Search (MIPS/FAISS)"],
        "unlocks": ["GraphRAG", "Hybrid Dense-Sparse Retrieval", "Enterprise Knowledge Assistants"]
    }
}


def _populate_pearson_knowledge():
    """Ingest all 40 Pearson bookshelf titles into LIBRARY_CATALOG_KNOWLEDGE."""
    import json
    from pathlib import Path
    try:
        repo_root = Path(__file__).resolve().parents[2]
        cat_file = repo_root / "data" / "catalogs" / "pearson_bookshelf.json"
        if not cat_file.is_file():
            return
        with cat_file.open(encoding="utf-8") as f:
            books = json.load(f).get("books", [])
        for b in books:
            book_id = b.get("id", "")
            slug = b.get("slug") or book_id
            title = b.get("title", "")
            author = b.get("author", "Pearson Education")
            isbn = b.get("isbn", "")
            domain = b.get("domain", "Computer Science & Engineering")
            reader_url = b.get("reader_base_url") or f"https://ebooks.elibrary.in.pearson.com/wr/index.html#book/{book_id}"

            aliases = [title.lower(), book_id.lower()]
            if slug:
                aliases.append(slug.lower())
                aliases.append(slug.lower().replace("_", " "))
            if isbn:
                aliases.append(isbn)
            if author:
                aliases.append(author.lower())

            title_clean = re.sub(r"[,/:\d+eE]+", " ", title).strip().lower()
            aliases.append(title_clean)

            entry = {
                "title": title,
                "aliases": list(set(aliases)),
                "authors": author,
                "year": "2024",
                "domain": domain,
                "format": f"Pearson eLibrary {'Reflowable' if b.get('book_type') == 'reflowable' else 'PDF'} Textbook (ISBN: {isbn})",
                "shelf_location": f"PEARSON-ELIB-{(slug or 'BOOK').upper()[:16]}",
                "total_copies": 10,
                "available_copies": 8,
                "pdf_path": reader_url,
                "reader_url": reader_url,
                "is_pearson": True,
                "book_id": book_id,
                "subscription_id": b.get("subscription_id", ""),
                "isbn": isbn,
                "summary": f"Authoritative Pearson eLibrary textbook: '{title}' by {author}. Comprehensive academic textbook within {domain} for engineering and computing curricula.",
                "key_sections": [
                    "1. Foundational Principles & Theoretical Background",
                    "2. Core Architectural & Algorithmic Methods",
                    "3. Practical Systems & Case Studies",
                    "4. Modern Design Considerations & Applications",
                    "5. Review Questions, Exercises & Advanced Topics"
                ],
                "prerequisites": ["Foundations of Computing", "Discrete Mathematics", "Systems Basics"],
                "unlocks": ["Advanced Specialized Electives", "Research & Industry Implementation"]
            }
            LIBRARY_CATALOG_KNOWLEDGE[slug] = entry
            if slug != book_id:
                LIBRARY_CATALOG_KNOWLEDGE[book_id] = entry
            doc_key = f"doc_{re.sub(r'[^a-z0-9]+', '_', title.lower()).strip('_')}"
            LIBRARY_CATALOG_KNOWLEDGE[doc_key] = entry
    except Exception as exc:
        print(f"Notice: Pearson knowledge bootstrap skipped: {exc}")


_populate_pearson_knowledge()


JOURNAL_REGISTRY = [
    {
        "title": "Journal of Human Resource Management",
        "publisher": "Academy Publications",
        "accession": "J297, J621",
        "volume_years": "Vol. 14 - 28 (2010-2024)",
        "total_copies": 2,
        "available_copies": 2,
        "status": "Available in Periodical Section"
    },
    {
        "title": "Academy of Management Journal",
        "publisher": "Academy of Management",
        "accession": "J280, J342, J415, J512, J590, J675",
        "volume_years": "Vol. 45 - 67 (2002-2024)",
        "total_copies": 6,
        "available_copies": 6,
        "status": "Available in Periodical Section"
    },
    {
        "title": "Applied Artificial Intelligence Journal",
        "publisher": "Taylor & Francis",
        "accession": "J501, J502, J503",
        "volume_years": "Vol. 32 - 38 (2018-2024)",
        "total_copies": 3,
        "available_copies": 3,
        "status": "Available in AI Research Archive"
    },
    {
        "title": "IEEE Transactions on Neural Networks and Learning Systems",
        "publisher": "IEEE Computational Intelligence Society",
        "accession": "IEEE-TNN-01..04",
        "volume_years": "Vol. 26 - 35 (2015-2024)",
        "total_copies": 4,
        "available_copies": 4,
        "status": "Available in Digital & Print Archive"
    },
    {
        "title": "ACM Transactions on Database Systems (TODS)",
        "publisher": "ACM Press",
        "accession": "ACM-TODS-01, ACM-TODS-02",
        "volume_years": "Vol. 40 - 49 (2015-2024)",
        "total_copies": 2,
        "available_copies": 2,
        "status": "Available in Reference Stacks"
    }
]


def clean_topic_query(query: str) -> str:
    q = re.sub(r"\b(suggest|recommend|top|best|\d+|books?|papers?|readings?|textbooks?|for|the|topic|about|on|of|me|show|find|list|a|an|some|regarding)\b", " ", query, flags=re.I)
    return re.sub(r"\s+", " ", q).strip(" :\"'?.")


def clean_book_query(query: str) -> str:
    q = re.sub(r"\b(tell|me|about|this|the|book|paper|what|is|are|details|of|in|show|table|contents|journal|inventory|holdings|copies)\b", " ", query, flags=re.I)
    return re.sub(r"\s+", " ", q).strip(" :\"'?.")


def parse_chapter_lookup_query(query: str) -> tuple[str, str]:
    query_lower = query.lower()
    splitters = ["discusses", "discussed", "discuss", "mentioning", "mentions", "mentioned", "mention", "containing", "contains", "contained", "contain", "covering", "covers", "covered", "cover", "is in", "about", "has"]
    for splitter in splitters:
        if splitter in query_lower:
            idx = query_lower.find(splitter)
            book_part = query[:idx]
            concept_part = query[idx + len(splitter):]
            book = re.sub(r"\b(which|chapter|section|of|book|paper|where|in)\b", "", book_part, flags=re.I).strip(" :\"'?.")
            concept = concept_part.strip(" :\"'?.")
            return book, concept
    return query, query
