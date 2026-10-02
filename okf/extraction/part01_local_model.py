"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

from okf.config import (
    BASE_DIR,
    EXTRACTION_PROMPT_V15,
    MAX_CHARS_TO_SLM,
    MAX_RETRIES,
    MODEL_NAME,
    VALID_DIFFICULTIES,
    VALID_RELATIONS,
    VALID_TYPES,
    _local_path,
    infer_source_category,
)
from . import _deps as _rt  # noqa: F401


LOCAL_MODEL = None


LOCAL_TOKENIZER = None


LOCAL_MODE = _local_path.exists()


def load_local_model():
    """Load the local model and tokenizer directly from disk."""
    global LOCAL_MODEL, LOCAL_TOKENIZER, LOCAL_MODE
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    # Prefer live config resolution (OKF_LOCAL_MODEL / lib-qwen / aura-qwen).
    try:
        from okf.config import resolve_local_model_path
        local_path = resolve_local_model_path()
    except Exception:
        local_path = _local_path
    if not local_path.exists():
        local_path = BASE_DIR.parent / "lib-qwen"
    if not local_path.exists():
        local_path = BASE_DIR.parent / "aura-qwen"

    print(f"  Loading local model from {local_path}...")
    try:
        # ``local_path`` is a local directory (never a hub id), so there is no
        # revision to pin; remote loading is not attempted here.
        LOCAL_TOKENIZER = AutoTokenizer.from_pretrained(  # nosec B615
            local_path, trust_remote_code=True, fix_mistral_regex=True
        )
        LOCAL_MODEL = AutoModelForCausalLM.from_pretrained(  # nosec B615
            local_path,
            dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        print(f"  ✓ Local model loaded successfully from {local_path}!")
        LOCAL_MODE = True
    except Exception as exc:
        print(f"  Error loading local model: {exc}")
        print("  ⚠️ Falling back to Ollama mode...")
        LOCAL_MODE = False
