"""Token / context budget helpers for stream completions."""
from __future__ import annotations

import re

MAX_OUTPUT_TOKENS: int = 1500
MAX_CONTEXT_CHARS: int = 8000
MIN_RESPONSE_TOKENS: int = 50

# Ollama / study-style completion knobs expected by tests & harness.
MAX_NUM_CTX: int = 8192
MIN_NUM_PREDICT: int = 256
CTX_SAFETY_TOKENS: int = 64
STUDY_RESERVE_TOKENS: int = 640
MIN_BOUNDARY_KEEP_CHARS: int = 80


def estimate_prompt_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token)."""
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def stream_token_budget(
    prompt: str,
    *,
    reserve_tokens: int | None = None,
    max_ctx: int | None = None,
) -> tuple[int, int]:
    """Return (num_ctx, num_predict) that never exceeds free KV slots."""
    num_ctx = min(int(max_ctx or MAX_NUM_CTX), MAX_NUM_CTX)
    reserve = int(reserve_tokens if reserve_tokens is not None else STUDY_RESERVE_TOKENS)
    prompt_tokens = estimate_prompt_tokens(prompt)
    free = max(0, num_ctx - prompt_tokens - CTX_SAFETY_TOKENS)
    if free == 0:
        return num_ctx, 1
    num_predict = min(reserve, free)
    num_predict = max(1, min(num_predict, free))
    if free >= MIN_NUM_PREDICT:
        num_predict = max(num_predict, min(MIN_NUM_PREDICT, free))
    return num_ctx, num_predict


def trim_to_completion_boundary(text: str) -> str:
    """Trim a ragged mid-word / mid-sentence tail to the last complete sentence."""
    if not text:
        return text
    s = text.rstrip()
    if re.search(r'[.!?…]["\'”’)]?\s*$', s):
        return s
    # Prefer last sentence terminator.
    for i in range(len(s) - 1, -1, -1):
        if s[i] in ".!?…":
            cut = s[: i + 1]
            if len(cut) >= MIN_BOUNDARY_KEEP_CHARS:
                return cut
            break
    # Fall back to last whitespace (drop partial word).
    m = re.search(r"^(.*\S)\s+\S*$", s, flags=re.DOTALL)
    if m and len(m.group(1)) >= MIN_BOUNDARY_KEEP_CHARS:
        return m.group(1).rstrip()
    return s


def budget_ok(n_tokens: int) -> bool:
    return n_tokens <= MAX_OUTPUT_TOKENS


def trim_to_budget(text: str) -> str:
    return text[:MAX_CONTEXT_CHARS]


def context_chars_remaining(used: int) -> int:
    return max(0, MAX_CONTEXT_CHARS - used)
