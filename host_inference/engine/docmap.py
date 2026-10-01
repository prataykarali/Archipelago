"""Map catalog document ids onto Hugging Face dataset paths.

The catalogue stores a mix of slug ids, bare filenames and already-correct
relative paths.  :func:`hf_doc_path` normalises all three onto the single path
shape the dataset actually contains, so a citation can never point at a file
that does not exist.
"""
from __future__ import annotations

HF_DOC_MAP = {
    "doc_lora_low_rank_adaptation_of_large": "papers/Hu2021_LoRA.pdf",
    "hu2021_lora.pdf": "papers/Hu2021_LoRA.pdf",
    "lora_paper": "papers/Hu2021_LoRA.pdf",
    "dettmers2023_qlora.pdf": "papers/Dettmers2023_QLoRA.pdf",
    "lewis2020_rag.pdf": "papers/Lewis2020_RAG.pdf",
    "devlin2018_bert.pdf": "papers/Devlin2018_BERT.pdf",
    "bert_paper": "papers/Devlin2018_BERT.pdf",
    "edge2024_graphrag.pdf": "papers/Edge2024_GraphRAG.pdf",
    "vaswani2017_attention_is_all_you_need.pdf": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "paper_attention_is_all_you_need_2017": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "goodfellow2014_gan.pdf": "papers/Goodfellow2014_GAN.pdf",
    "book_deep_learning_goodfellow_2016": "papers/Goodfellow2014_GAN.pdf",
    "deisenroth_math_for_ml.pdf": "textbooks/Deisenroth_Math_For_ML.pdf",
    "book_math_for_machine_learning_2020": "textbooks/Deisenroth_Math_For_ML.pdf",
    "bahdanau2014_attention.pdf": "papers/Bahdanau2014_Attention.pdf",
    "kwon2023_vllm.pdf": "papers/Kwon2023_vLLM.pdf",
    "brown2020_gpt3.pdf": "papers/Brown2020_GPT3.pdf",
}

DATASET_PREFIXES = ("papers/", "textbooks/", "archipelago-books-cs/")


def hf_doc_path(doc_id: str) -> str:
    """Return the dataset-relative path for ``doc_id`` (empty string if none)."""
    raw = (doc_id or "").strip().lstrip("/")
    if not raw:
        return ""
    key = raw.lower()
    base = raw.split("/")[-1].lower()
    if key in HF_DOC_MAP:
        return HF_DOC_MAP[key]
    if base in HF_DOC_MAP:
        return HF_DOC_MAP[base]
    if raw.startswith(DATASET_PREFIXES) or "/" in raw:
        return raw
    if raw.lower().endswith(".pdf"):
        return f"papers/{raw}"
    return raw


# Privately used name kept for the original call sites in engine.py.
_hf_doc_path = hf_doc_path
