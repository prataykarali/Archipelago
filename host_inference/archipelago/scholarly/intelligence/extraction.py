"""Evidence-bound research claim extraction from titles, abstracts, and provider fields.

Every extracted claim must be anchored in a literal sentence from provider text.
Nothing is invented or guessed from the title alone, and nothing is ranked.
"""

from __future__ import annotations

from datetime import UTC, datetime
import re
from typing import Any

METHODS = (
    "graph convolutional network", "graph attention network", "graph neural network",
    "message passing", "transformer", "convolutional neural network", "recurrent neural network",
    "lstm", "liquid neural network", "liquid time-constant", "closed-form continuous",
    "contrastive learning", "self-supervised learning", "semi-supervised learning",
    "supervised learning", "reinforcement learning", "rlhf", "transfer learning", "fine-tuning",
    "instruction tuning", "lora", "qlora", "knowledge distillation", "retrieval-augmented generation",
    "dense retrieval", "reranking", "large language model", "multimodal", "omni-modal",
    "multi-agent", "task planning", "tool use",
    "chain-of-thought", "prompt engineering", "experience replay", "regularization",
    "elastic weight consolidation", "meta-learning", "attention mechanism", "diffusion",
    "connectionist temporal classification", "end-to-end", "data augmentation", "ablation study",
    "zero-shot", "few-shot", "survey", "systematic review", "benchmark",
)
MODELS = (
    "gpt-4", "gpt-3.5", "chatgpt", "llama", "bert", "roberta", "t5", "hugginggpt",
    "clip", "vit", "resnet", "whisper", "wav2vec", "conformer", "layoutlm", "donut",
    "trocr", "gat", "gcn", "graphsage", "gin", "stable diffusion", "qwen", "gemini",
)
DATASETS = (
    "cora", "citeseer", "pubmed", "ogb", "imagenet", "cifar-10", "cifar-100", "mnist",
    "coco", "squad", "ms marco", "natural questions", "hotpotqa", "triviaqa", "gsm8k", "mmlu",
    "mmmu", "longbench", "beir", "omni-bench",
    "humaneval", "glue", "superglue", "librispeech", "common voice", "openslr",
    "ocr-bench", "icdar", "docvqa", "funsd", "sroie", "tudataset", "qm9", "mimic",
    "mathvista", "alpaca", "toolbench",
)
TASKS = (
    "question answering", "text generation", "document understanding", "optical character recognition",
    "speech recognition", "node classification", "link prediction", "graph classification",
    "information retrieval", "code generation", "task planning", "reasoning", "summarization",
    "image classification", "object detection", "named entity recognition",
)
METRICS = (
    "accuracy", "f1", "f1-score", "precision", "recall", "auc", "auroc", "bleu", "rouge",
    "word error rate", "wer", "character error rate", "cer", "mean average precision",
    "perplexity", "exact match", "pass@1", "success rate", "win rate", "latency", "throughput",
    "mse", "rmse", "mae", "ndcg", "mrr",
)
SENTENCE = re.compile(r"(?<=[.!?])\s+")
NUM_RESULT_RE = re.compile(
    r"\b(?:accuracy|f1(?:-score)?|bleu|rouge|wer|cer|auc|pass@1|success rate|precision|recall)"
    r"(?:\s*(?:of|=|:|reaches|achieves|improves to))?\s*\d+(?:\.\d+)?\s*%?",
    re.IGNORECASE,
)
BASELINE_RE = re.compile(r"\b(?:outperforms?|compared (?:to|with)|baseline|state-of-the-art|sota)\b", re.IGNORECASE)
LIMIT_RE = re.compile(r"\b(?:limitation|drawback|challenge|fails? to|bottleneck|struggles? with)\b", re.IGNORECASE)
CONTRIB_RE = re.compile(r"\b(?:we propose|we introduce|we present|our main contribution|in this paper)\b", re.IGNORECASE)
RQ_RE = re.compile(r"\b(?:we investigate|we study|we address|research question|whether|how does|can we)\b", re.IGNORECASE)
ABLATION_RE = re.compile(r"\b(?:ablation|ablations|ablate)\b", re.IGNORECASE)
CODE_URL_RE = re.compile(r"https?://(?:github\.com|gitlab\.com)/[^\s,;)\]]+", re.IGNORECASE)
DATASET_URL_RE = re.compile(r"https?://huggingface\.co/datasets/[^\s,;)\]]+", re.IGNORECASE)


def _find(vocab: tuple[str, ...], sentences: list[tuple[str, str]], claim_type: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    for term in vocab:
        pattern = re.compile(rf"(?<![\w-]){re.escape(term)}s?(?![\w-])", re.IGNORECASE)
        for loc, sentence in sentences:
            if pattern.search(sentence):
                found.append(
                    {
                        "name": term,
                        "claim_type": claim_type,
                        "evidence": sentence.strip()[:300],
                        "location": loc,
                        "extraction_method": "controlled_evidence_match",
                    }
                )
                break
    return found


def extract_evidence(
    title: str,
    abstract: str | None,
    source_url: str | None = None,
) -> dict[str, Any]:
    """Return evidence-anchored claims and backward-compatible methods/datasets/metrics."""
    now = datetime.now(UTC).isoformat()
    sents: list[tuple[str, str]] = [("title", s.strip()) for s in SENTENCE.split(title or "") if s.strip()]
    if abstract:
        sents.extend(("abstract", s.strip()) for s in SENTENCE.split(abstract) if s.strip())

    methods = _find(METHODS, sents, "METHOD")
    models = _find(MODELS, sents, "MODEL")
    datasets = _find(DATASETS, sents, "DATASET")
    tasks = _find(TASKS, sents, "TASK")
    metrics = _find(METRICS, sents, "EVALUATION_METRIC")

    claims: list[dict[str, Any]] = []
    for group in (methods, models, datasets, tasks, metrics):
        for item in group:
            claims.append(
                {
                    "claim_type": item["claim_type"],
                    "normalized_value": item["name"],
                    "exact_evidence": item["evidence"],
                    "source_url": source_url,
                    "location": item["location"],
                    "extraction_method": item["extraction_method"],
                    "status": "AVAILABLE",
                    "reviewed_at": now,
                }
            )
    for loc, sentence in sents:
        if loc != "abstract":
            continue
        if m := NUM_RESULT_RE.search(sentence):
            claims.append(
                {
                    "claim_type": "NUMERICAL_RESULT",
                    "normalized_value": m.group(0).strip(),
                    "exact_evidence": sentence[:300],
                    "source_url": source_url,
                    "location": loc,
                    "extraction_method": "pattern_evidence_match",
                    "status": "AVAILABLE",
                    "reviewed_at": now,
                }
            )
        for ctype, rx in (
            ("BASELINE", BASELINE_RE),
            ("LIMITATION", LIMIT_RE),
            ("CONTRIBUTION", CONTRIB_RE),
            ("RESEARCH_QUESTION", RQ_RE),
            ("ABLATION", ABLATION_RE),
        ):
            if rx.search(sentence):
                claims.append(
                    {
                        "claim_type": ctype,
                        "normalized_value": sentence[:120],
                        "exact_evidence": sentence[:300],
                        "source_url": source_url,
                        "location": loc,
                        "extraction_method": "cue_sentence_match",
                        "status": "AVAILABLE",
                        "reviewed_at": now,
                    }
                )
    code_urls = CODE_URL_RE.findall(abstract or "")
    dataset_urls = DATASET_URL_RE.findall(abstract or "")
    for cu in code_urls[:3]:
        claims.append(
            {
                "claim_type": "CODE_REPO_URL",
                "normalized_value": cu,
                "exact_evidence": cu,
                "source_url": source_url,
                "location": "abstract",
                "extraction_method": "explicit_url_match",
                "status": "AVAILABLE",
                "reviewed_at": now,
            }
        )
    for du in dataset_urls[:3]:
        claims.append(
            {
                "claim_type": "DATASET_REPO_URL",
                "normalized_value": du,
                "exact_evidence": du,
                "source_url": source_url,
                "location": "abstract",
                "extraction_method": "explicit_url_match",
                "status": "AVAILABLE",
                "reviewed_at": now,
            }
        )
    claim_types_present = {c["claim_type"] for c in claims}
    absent_status = "NOT_FOUND_IN_AVAILABLE_EVIDENCE" if abstract else "SOURCE_NOT_ACCESSIBLE"
    field_statuses = {
        "research_question": "PRESENT_WITH_EVIDENCE" if "RESEARCH_QUESTION" in claim_types_present else absent_status,
        "contribution": "PRESENT_WITH_EVIDENCE" if "CONTRIBUTION" in claim_types_present else absent_status,
        "methods": "PRESENT_WITH_EVIDENCE" if methods else absent_status,
        "datasets": "PRESENT_WITH_EVIDENCE" if datasets else absent_status,
        "evaluation_metrics": "PRESENT_WITH_EVIDENCE" if metrics else absent_status,
        "numeric_results": "PRESENT_WITH_EVIDENCE" if "NUMERICAL_RESULT" in claim_types_present else absent_status,
        "baselines": "PRESENT_WITH_EVIDENCE" if "BASELINE" in claim_types_present else absent_status,
        "ablations": "PRESENT_WITH_EVIDENCE" if "ABLATION" in claim_types_present else absent_status,
        "limitations": "PRESENT_WITH_EVIDENCE" if "LIMITATION" in claim_types_present else absent_status,
        "code_repo_url": "PRESENT_WITH_EVIDENCE" if code_urls else absent_status,
        "dataset_repo_url": "PRESENT_WITH_EVIDENCE" if dataset_urls else absent_status,
    }
    claim_status = (
        "AVAILABLE"
        if claims
        else ("NOT_FOUND_IN_AVAILABLE_EVIDENCE" if abstract else "EVIDENCE_INSUFFICIENT")
    )
    return {
        "methods": methods,
        "models": models,
        "datasets": datasets,
        "tasks": tasks,
        "evaluation_metrics": metrics,
        "claims": claims,
        "claim_status": claim_status,
        "field_statuses": field_statuses,
        "code_repo_urls": code_urls[:3],
        "dataset_repo_urls": dataset_urls[:3],
    }
