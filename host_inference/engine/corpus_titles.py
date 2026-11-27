"""Clean bibliographic titles for all 43 open-access corpus documents.

One concern: map every open-access PDF path or slug in the Archipelago corpus
(17 OSTEP chapters, 1 open ML mathematics textbook, and 25 foundational AI/ML
research papers, plus FlashAttention) to an accurate, human-readable
bibliographic title so raw filenames never leak into citations or UI cards.
"""

from __future__ import annotations

import re

# Authoritative mapping for all 43 open corpus documents in fixtures/hf_files.json
# (17 OSTEP chapters + 1 Deisenroth textbook + 25 open-access research papers),
# plus FlashAttention from docmap.py.
OPEN_CORPUS_TITLES: dict[str, str] = {
    # ── Operating Systems: Three Easy Pieces (17 chapters) ───────────────────
    "00_dialogue.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 0: A Dialogue on the Book "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "01_introduction.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 1: Introduction to Operating Systems "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "02_cpu_virtualization.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 2: CPU Virtualization and Processes "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "03_process_api.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 3: Interlude: Process API "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "04_limited_direct_execution.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 4: Mechanism: Limited Direct Execution "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "05_cpu_scheduling.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 5: CPU Scheduling "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "06_address_spaces.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 6: The Abstraction: Address Spaces "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "07_address_translation.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 7: Mechanism: Address Translation "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "08_paging.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 8: Paging: Introduction "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "09_tlbs.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 9: Paging: Faster Translations (TLBs) "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "10_concurrency_intro.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 10: Concurrency: An Introduction "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "11_locks.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 11: Locks "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "12_semaphores.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 12: Semaphores "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "13_common_bugs.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 13: Common Concurrency Problems "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "14_io_devices.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 14: I/O Devices "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "15_raid.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 15: Redundant Arrays of Inexpensive Disks (RAID) "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    "16_log_structured_fs.pdf": (
        "Operating Systems: Three Easy Pieces — Ch. 16: Log-Structured File Systems "
        "(Arpaci-Dusseau & Arpaci-Dusseau)"
    ),
    # ── Open-Access Textbooks (1) ────────────────────────────────────────────
    "deisenroth_math_for_ml.pdf": (
        "Mathematics for Machine Learning (Deisenroth, Faisal & Ong, 2020)"
    ),
    # ── Open-Access Research Papers (25 + FlashAttention) ────────────────────
    "bahdanau2014_attention.pdf": (
        "Neural Machine Translation by Jointly Learning to Align and Translate (Bahdanau et al., 2014)"
    ),
    "bai2022_constitutionalai.pdf": (
        "Constitutional AI: Harmlessness from AI Feedback (Bai et al., 2022)"
    ),
    "brown2020_gpt3.pdf": "Language Models are Few-Shot Learners (Brown et al., 2020)",
    "dao2022_flashattention.pdf": (
        "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness (Dao et al., 2022)"
    ),
    "dettmers2023_qlora.pdf": (
        "QLoRA: Efficient Finetuning of Quantized LLMs (Dettmers et al., 2023)"
    ),
    "devlin2018_bert.pdf": (
        "BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding (Devlin et al., 2018)"
    ),
    "edge2024_graphrag.pdf": (
        "From Local to Global: A Graph RAG Approach to Query-Focused Summarization (Edge et al., 2024)"
    ),
    "goodfellow2014_gan.pdf": "Generative Adversarial Nets (Goodfellow et al., 2014)",
    "ho2020_ddpm.pdf": "Denoising Diffusion Probabilistic Models (Ho, Jain & Abbeel, 2020)",
    "hochreiter1997_lstm.pdf": "Long Short-Term Memory (Hochreiter & Schmidhuber, 1997)",
    "hu2021_lora.pdf": "LoRA: Low-Rank Adaptation of Large Language Models (Hu et al., 2021)",
    "karpukhin2020_dpr.pdf": (
        "Dense Passage Retrieval for Open-Domain Question Answering (Karpukhin et al., 2020)"
    ),
    "kingma2013_vae.pdf": "Auto-Encoding Variational Bayes (Kingma & Welling, 2013)",
    "kipf2016_gcn.pdf": (
        "Semi-Supervised Classification with Graph Convolutional Networks (Kipf & Welling, 2016)"
    ),
    "krizhevsky2012_alexnet.pdf": (
        "ImageNet Classification with Deep Convolutional Neural Networks "
        "(Krizhevsky, Sutskever & Hinton, 2012)"
    ),
    "kwon2023_vllm.pdf": (
        "Efficient Memory Management for Large Language Model Serving with PagedAttention "
        "(Kwon et al., 2023)"
    ),
    "lecun1998_convnets.pdf": (
        "Gradient-Based Learning Applied to Document Recognition (LeCun et al., 1998)"
    ),
    "lewis2020_rag.pdf": (
        "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks (Lewis et al., 2020)"
    ),
    "ouyang2022_instructgpt.pdf": (
        "Training Language Models to Follow Instructions with Human Feedback (Ouyang et al., 2022)"
    ),
    "rafailov2023_dpo.pdf": (
        "Direct Preference Optimization: Your Language Model is Secretly a Reward Model "
        "(Rafailov et al., 2023)"
    ),
    "rumelhart1986_backpropagation.pdf": (
        "Learning Representations by Back-Propagating Errors (Rumelhart, Hinton & Williams, 1986)"
    ),
    "vaswani2017_attention_is_all_you_need.pdf": (
        "Attention Is All You Need (Vaswani et al., 2017)"
    ),
    "velickovic2017_gat.pdf": "Graph Attention Networks (Velickovic et al., 2017)",
    "wei2022_chainofthought.pdf": (
        "Chain-of-Thought Prompting Elicits Reasoning in Large Language Models (Wei et al., 2022)"
    ),
    "willard2023_outlines.pdf": (
        "Efficient Guided Generation for Large Language Models (Willard & Louf, 2023)"
    ),
    "yao2022_react.pdf": (
        "ReAct: Synergizing Reasoning and Acting in Language Models (Yao et al., 2022)"
    ),
}

_AUTHOR_YEAR_RE = re.compile(r"^([A-Za-z]+)(\d{4})[_\-\s]+(.+)$")
_OSTEP_CHAPTER_RE = re.compile(r"^(\d{2})[_\-\s]+(.+)$")


def clean_bibliographic_title(doc_id: str, raw_title: str = "") -> str:
    """Resolve a clean human-readable bibliographic title for ``doc_id``."""
    for candidate_id in (doc_id, raw_title):
        base = (candidate_id or "").strip().rsplit("/", 1)[-1].lower()
        if base in OPEN_CORPUS_TITLES:
            return OPEN_CORPUS_TITLES[base]
        if base and not base.endswith(".pdf") and f"{base}.pdf" in OPEN_CORPUS_TITLES:
            return OPEN_CORPUS_TITLES[f"{base}.pdf"]

    candidate = (raw_title or "").strip()
    if candidate and not candidate.lower().endswith(".pdf") and "_" not in candidate:
        return candidate

    stem = re.sub(r"\.pdf$", "", (doc_id or raw_title or "Source").rsplit("/", 1)[-1], flags=re.I)
    m_author = _AUTHOR_YEAR_RE.match(stem)
    if m_author:
        author, year, rest = m_author.group(1), m_author.group(2), m_author.group(3)
        clean_rest = re.sub(r"[_\-]+", " ", rest).strip()
        return f"{clean_rest} ({author} et al., {year})"

    m_ostep = _OSTEP_CHAPTER_RE.match(stem)
    if m_ostep and "ostep" in (doc_id or "").lower():
        chapter_num, rest = int(m_ostep.group(1)), re.sub(r"[_\-]+", " ", m_ostep.group(2)).strip()
        return f"Operating Systems: Three Easy Pieces — Ch. {chapter_num}: {rest}"

    return re.sub(r"[_\-]+", " ", stem).strip() or "Source"


__all__ = ["OPEN_CORPUS_TITLES", "clean_bibliographic_title"]
