"""Pilot corpus selection, prompt, and local model extraction."""

from __future__ import annotations

import json
import re

# Pilot papers (≤15) — full text OK per Jul 21
PILOT_PAPERS = [
    "Lewis2020_RAG.pdf",
    "Hu2021_LoRA.pdf",
    "Dettmers2023_QLoRA.pdf",
    "Kwon2023_vLLM.pdf",
    "Vaswani2017_Attention_Is_All_You_Need.pdf",
    "Devlin2018_BERT.pdf",
    "Karpukhin2020_DPR.pdf",
    "Edge2024_GraphRAG.pdf",
    "Yao2022_ReAct.pdf",
    "Wei2022_ChainOfThought.pdf",
    "Ouyang2022_InstructGPT.pdf",
    "Rafailov2023_DPO.pdf",
    "Rumelhart1986_Backpropagation.pdf",
    "Kipf2016_GCN.pdf",
    "Bahdanau2014_Attention.pdf",
]

# Book dirs (METADATA only — no body PDFs in tree for Silberschatz etc.)
PILOT_BOOK_DIRS = [
    "database_system_concepts_silberschatz",
    "database_management_systems_ramakrishnan",
    "data_structures_algorithm_analysis_weiss",
    "operating_system_concepts_silberschatz",
    "ostep_three_easy_pieces",
    "introduction_to_algorithms_clrs",
]

# OSTEP: chapter *titles* only (filename = TOC line), never chapter body
OSTEP_TOC_ONLY = True

EXTRACT_PROMPT = """You are an OKF extraction engine for Archipelago (pilot, copyright-safe).
From the TEXT (paper abstract/body OR book TOC/index/author metadata only),
extract 1 to 4 teachable CONCEPTS as a JSON array.

Keys per object:
- concept_name (Title Case, max 6 words)
- concept_type: method|metric|technique|theory|tool|dataset|result|definition
- difficulty: foundational|intermediate|advanced|expert
- summary: 1-2 sentences
- prerequisites: [Title Case names]
- unlocks: [Title Case names]
- related_to: [{{"concept":"Name","relation":"uses"}}]
- tags: [lowercase-hyphen]

Rules: only concepts present in the text; CS/AI/OS/DBMS/DSA preferred; JSON array only.

TEXT:
{text}
"""

_TOC_HINT = re.compile(
    r"(?i)\b(contents|table of contents|index|preface|copyright|isbn|"
    r"about the author|list of figures|chapter\s+\d|part\s+[ivx]+)\b"
)


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
    return s[:80] or "concept"


def _parse_json_array(raw: str) -> list:
    s = (raw or "").strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    try:
        data = json.loads(s)
        return data if isinstance(data, list) else [data] if isinstance(data, dict) else []
    except Exception:
        pass
    m = re.search(r"\[.*\]", s, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
            return data if isinstance(data, list) else []
        except Exception:
            return []
    return []


def extract_text_gpu(model: str, text: str, keep_alive: str = "30m") -> list[dict]:
    import ollama

    prompt = EXTRACT_PROMPT.format(text=(text or "")[:1800])
    kwargs = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "keep_alive": keep_alive,
        "options": {"temperature": 0.1, "num_predict": 640, "num_ctx": 4096},
    }
    try:
        res = ollama.chat(**kwargs, think=False)
    except TypeError:
        res = ollama.chat(**kwargs)
    msg = res.get("message") if hasattr(res, "get") else getattr(res, "message", None)
    if isinstance(msg, dict):
        content = msg.get("content") or msg.get("thinking") or ""
    else:
        content = getattr(msg, "content", None) or getattr(msg, "thinking", None) or ""
    return _parse_json_array(str(content))


def _esc(s: str) -> str:
    return (s or "").replace("\\", "\\\\").replace("'", "\\'")
