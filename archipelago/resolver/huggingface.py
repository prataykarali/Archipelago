"""Hugging Face Link Resolver using huggingface_hub with File Verification & Caching."""
from __future__ import annotations

import datetime
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

try:
    from huggingface_hub import HfApi, hf_hub_url
    try:
        from huggingface_hub import parse_hf_uri
    except ImportError:
        parse_hf_uri = None
    _HAS_HF_HUB = True
except ImportError:
    HfApi = None
    hf_hub_url = None
    parse_hf_uri = None
    _HAS_HF_HUB = False

logger = logging.getLogger("archipelago.resolver.huggingface")

DEFAULT_HF_REPO = os.environ.get("HF_DATASET_REPO", "Prataykarali/Library_books")
DEFAULT_REPO_TYPE = "dataset"
DEFAULT_REVISION = "main"

# Memory cache for repository file listings: repo_key -> (set_of_filenames, timestamp)
_REPO_FILES_CACHE: dict[str, tuple[set[str], float]] = {}
_CACHE_TTL_SEC = 3600.0  # 1 hour
_BUNDLED_MANIFEST = Path(__file__).resolve().parents[2] / "data" / "catalogs" / "hf_dataset_manifest.json"

# Canonical alias mapping for common book IDs to their exact repo file path
HF_CANONICAL_PATHS: dict[str, str] = {
    "deisenroth_math_for_ml.pdf": "textbooks/Deisenroth_Math_For_ML.pdf",
    "deisenroth_math_for_ml": "textbooks/Deisenroth_Math_For_ML.pdf",
    "book_math_for_machine_learning_2020": "textbooks/Deisenroth_Math_For_ML.pdf",
    "math_for_ml": "textbooks/Deisenroth_Math_For_ML.pdf",
    "attention_is_all_you_need": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "vaswani2017_attention_is_all_you_need.pdf": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "paper_attention_is_all_you_need_2017": "papers/Vaswani2017_Attention_Is_All_You_Need.pdf",
    "bert_paper": "papers/Devlin2018_BERT.pdf",
    "devlin2018_bert.pdf": "papers/Devlin2018_BERT.pdf",
    "hu2021_lora.pdf": "papers/Hu2021_LoRA.pdf",
    "lora_paper": "papers/Hu2021_LoRA.pdf",
    "dettmers2023_qlora.pdf": "papers/Dettmers2023_QLoRA.pdf",
    "lewis2020_rag.pdf": "papers/Lewis2020_RAG.pdf",
    "rag_paper": "papers/Lewis2020_RAG.pdf",
    "edge2024_graphrag.pdf": "papers/Edge2024_GraphRAG.pdf",
    "graphrag_ms": "papers/Edge2024_GraphRAG.pdf",
    "goodfellow2014_gan.pdf": "papers/Goodfellow2014_GAN.pdf",
    "deep_learning_goodfellow": "papers/Goodfellow2014_GAN.pdf",
    "book_deep_learning_goodfellow_2016": "papers/Goodfellow2014_GAN.pdf",
    "book_deep_learning_goodfellow_2016.pdf": "papers/Goodfellow2014_GAN.pdf",
    "kwon2023_vllm.pdf": "papers/Kwon2023_vLLM.pdf",
    "brown2020_gpt3.pdf": "papers/Brown2020_GPT3.pdf",
    "bahdanau2014_attention.pdf": "papers/Bahdanau2014_Attention.pdf",
    "hochreiter1997_lstm.pdf": "papers/Hochreiter1997_LSTM.pdf",
}


def _get_hf_token(provided_token: str | None = None) -> str | None:
    if provided_token:
        return provided_token
    token = os.environ.get("HF_TOKEN")
    if token:
        return token
    # Check .env file in repo root
    from pathlib import Path
    for parent in [Path.cwd(), Path(__file__).resolve().parents[2]]:
        env_file = parent / ".env"
        if env_file.is_file():
            try:
                with open(env_file, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("HF_TOKEN="):
                            t = line.split("=", 1)[1].strip().strip('"').strip("'")
                            if t:
                                return t
            except Exception:
                pass
    return None


def _bundled_repo_files(repo_id: str) -> set[str]:
    """Return the last known dataset inventory when Hub access is unavailable."""
    if repo_id != DEFAULT_HF_REPO or not _BUNDLED_MANIFEST.is_file():
        return set()
    try:
        payload = json.loads(_BUNDLED_MANIFEST.read_text(encoding="utf-8"))
        return {str(path) for path in payload.get("files", []) if str(path)}
    except (OSError, ValueError) as exc:
        logger.warning("Unable to read bundled HF dataset manifest: %s", exc)
        return set()


def get_hf_repo_files(
    repo_id: str = DEFAULT_HF_REPO,
    repo_type: str = "dataset",
    hf_token: str | None = None,
    force_refresh: bool = False,
) -> set[str]:
    """Retrieve and cache the full set of files present in the HF repository."""
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    cache_key = f"{repo_type}:{repo_id}"

    if not force_refresh and cache_key in _REPO_FILES_CACHE:
        cached_set, cached_time = _REPO_FILES_CACHE[cache_key]
        if now - cached_time < _CACHE_TTL_SEC:
            return cached_set

    # The bundled manifest is a last-known-good snapshot of the private
    # dataset.  It makes reader links and the showcase available at startup
    # without blocking the UI on a Hub round trip.  Operators can opt into a
    # live refresh for newly ingested files.
    bundled_files = _bundled_repo_files(repo_id)
    if bundled_files and not force_refresh and os.environ.get("ARCHIPELAGO_HF_REFRESH") != "1":
        _REPO_FILES_CACHE[cache_key] = (bundled_files, now)
        return bundled_files

    token = _get_hf_token(hf_token)

    if _HAS_HF_HUB:
        try:
            api = HfApi(token=token)
            file_list = api.list_repo_files(repo_id=repo_id, repo_type=repo_type)
            file_set = set(file_list)
            _REPO_FILES_CACHE[cache_key] = (file_set, now)
            return file_set
        except Exception as exc:
            logger.warning("Failed to list files via HfApi for %s: %s", repo_id, exc)

    # Fallback to direct HTTP request via requests
    try:
        import requests
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        tree_url = f"https://huggingface.co/api/{repo_type}s/{repo_id}/tree/main?recursive=true"
        resp = requests.get(tree_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            items = resp.json()
            file_set = {x["path"] for x in items if "path" in x}
            _REPO_FILES_CACHE[cache_key] = (file_set, now)
            return file_set
    except Exception as exc:
        logger.debug("Failed to list files via HTTP for %s: %s", repo_id, exc)

    if cache_key in _REPO_FILES_CACHE:
        return _REPO_FILES_CACHE[cache_key][0]
    bundled_files = _bundled_repo_files(repo_id)
    if bundled_files:
        _REPO_FILES_CACHE[cache_key] = (bundled_files, now)
    return bundled_files



def verify_hf_repo_file(
    repo_id: str = DEFAULT_HF_REPO,
    filename: str = "README.md",
    repo_type: str = "dataset",
    hf_token: str | None = None,
) -> bool:
    files = get_hf_repo_files(repo_id=repo_id, repo_type=repo_type, hf_token=hf_token)

    clean_name = filename.lstrip("/")
    lower_name = clean_name.lower()
    base_lower = clean_name.split("/")[-1].lower()

    if files:
        if clean_name in files:
            return True
        for f in files:
            f_lower = f.lower()
            if f_lower == lower_name or f_lower.endswith("/" + base_lower) or f_lower == base_lower:
                return True
        return False

    # Offline fallback: check known manifest and local storage
    if base_lower in HF_CANONICAL_PATHS or lower_name in HF_CANONICAL_PATHS:
        return True

    # Check local files under pdfs/ or cache
    from pathlib import Path
    base_dir = Path(__file__).resolve().parents[2]
    candidate = base_dir / "pdfs" / clean_name
    if candidate.is_file():
        return True
    for p in (base_dir / "pdfs").glob(f"**/{base_lower}"):
        if p.is_file():
            return True

    cache_dir = Path.home() / ".cache" / "archipelago" / "library_books" / clean_name
    if cache_dir.is_file():
        return True

    return False



def enumerate_hf_resources(
    repo_id: str = DEFAULT_HF_REPO,
    repo_type: str = "dataset",
    revision: str = "main",
    hf_token: str | None = None,
) -> list[dict[str, Any]]:
    """Enumerate all books and papers present in the Hugging Face repository."""
    files = get_hf_repo_files(repo_id=repo_id, repo_type=repo_type, hf_token=hf_token)
    resources = []
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    for f in sorted(files):
        if not f.endswith(".pdf"):
            continue

        category = "textbook" if f.startswith("textbooks/") else ("paper" if f.startswith("papers/") else "document")
        blob_url = f"https://huggingface.co/{repo_type}s/{repo_id}/blob/{revision}/{f}"
        raw_resolve_url = f"https://huggingface.co/{repo_type}s/{repo_id}/resolve/{revision}/{f}"

        resources.append({
            "filename": f,
            "category": category,
            "repo_id": repo_id,
            "repo_type": repo_type,
            "revision": revision,
            "blob_url": blob_url,
            "resolve_url": raw_resolve_url,
            "canonical_url": blob_url,
            "url": blob_url,
            "status": "resolved",
            "working": True,
            "source": "huggingface",
            "last_verified": now_iso,
            "target_blank": True,
        })

    return resources


def resolve_huggingface_url(
    input_str: str,
    filename: str | None = None,
    repo_id: str | None = None,
    repo_type: str = "dataset",
    revision: str = "main",
    hf_token: str | None = None,
    verify_existence: bool = True,
) -> dict[str, Any]:
    """Resolve a Hugging Face resource URL or URI to canonical blob (browser) and resolve (download) URLs."""
    target_repo = repo_id or DEFAULT_HF_REPO
    target_revision = revision or DEFAULT_REVISION
    token = _get_hf_token(hf_token)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    clean_input_lower = (filename or input_str).lower().strip()
    if clean_input_lower in HF_CANONICAL_PATHS:
        target_file = HF_CANONICAL_PATHS[clean_input_lower]
    else:
        if input_str.startswith("hf://"):
            rem = input_str[5:]
            p_type = repo_type
            if rem.startswith("datasets/"):
                p_type = "dataset"
                rem = rem[len("datasets/"):]
            elif rem.startswith("models/"):
                p_type = "model"
                rem = rem[len("models/"):]
            elif rem.startswith("spaces/"):
                p_type = "space"
                rem = rem[len("spaces/"):]

            parts = rem.split("/", 2)
            if len(parts) >= 2:
                p_repo = f"{parts[0]}/{parts[1]}"
                rel_path = parts[2] if len(parts) > 2 else ""
            else:
                p_repo = target_repo
                rel_path = rem

            p_rev = target_revision
            if "@" in p_repo:
                p_repo, p_rev = p_repo.split("@", 1)

            blob_url = f"https://huggingface.co/{p_type}s/{p_repo}/blob/{p_rev}/{rel_path}"
            raw_resolve_url = f"https://huggingface.co/{p_type}s/{p_repo}/resolve/{p_rev}/{rel_path}"

            exists = True
            if verify_existence:
                exists = verify_hf_repo_file(repo_id=p_repo, filename=rel_path, repo_type=p_type, hf_token=token)

            return {
                "working": exists,
                "status": "resolved" if exists else "missing",
                "url": blob_url,
                "blob_url": blob_url,
                "resolve_url": raw_resolve_url,
                "canonical_url": blob_url,
                "source": "huggingface",
                "repo_id": p_repo,
                "repo_type": p_type,
                "revision": p_rev,
                "filename": rel_path,
                "target_blank": True,
                "last_verified": now_iso,
                "error": None if exists else f"File not found in HF repo {p_repo}: {rel_path}",
            }

        if "huggingface.co" in input_str:
            clean_input = input_str
            blob_url = clean_input.replace("/resolve/", "/blob/")
            raw_resolve_url = clean_input.replace("/blob/", "/resolve/")
            extracted_filename = filename or clean_input.split("/")[-1]

            return {
                "working": True,
                "status": "resolved",
                "url": blob_url,
                "blob_url": blob_url,
                "resolve_url": raw_resolve_url,
                "canonical_url": blob_url,
                "source": "huggingface",
                "repo_id": target_repo,
                "repo_type": repo_type,
                "revision": target_revision,
                "filename": extracted_filename,
                "target_blank": True,
                "last_verified": now_iso,
            }

        target_file = filename or (input_str if not input_str.startswith("http") else input_str.split("/")[-1])

    if "/" not in target_file:
        tf_lower = target_file.lower()
        if "paper" in tf_lower or any(p in tf_lower for p in ["lstm", "bert", "gpt", "rag", "lora", "attention", "vllm", "gan", "dpo", "moe"]):
            target_file = f"papers/{target_file}"
        else:
            target_file = f"textbooks/{target_file}"

    exists = True
    if verify_existence:
        exists = verify_hf_repo_file(repo_id=target_repo, filename=target_file, repo_type=repo_type, hf_token=token)

    if _HAS_HF_HUB:
        try:
            raw_resolve_url = hf_hub_url(
                repo_id=target_repo,
                filename=target_file,
                repo_type=repo_type,
                revision=target_revision,
            )
            blob_url = raw_resolve_url.replace("/resolve/", "/blob/")
            return {
                "working": exists,
                "status": "resolved" if exists else "missing",
                "url": blob_url,
                "blob_url": blob_url,
                "resolve_url": raw_resolve_url,
                "canonical_url": blob_url,
                "reader_url": f"/read/{target_file}",
                "source": "huggingface",
                "repo_id": target_repo,
                "repo_type": repo_type,
                "revision": target_revision,
                "filename": target_file,
                "target_blank": True,
                "last_verified": now_iso,
                "error": None if exists else f"File not found in HF repo {target_repo}: {target_file}",
            }
        except Exception as exc:
            logger.warning("hf_hub_url failed for %s/%s: %s", target_repo, target_file, exc)

    raw_resolve_url = f"https://huggingface.co/{repo_type}s/{target_repo}/resolve/{target_revision}/{target_file}"
    blob_url = f"https://huggingface.co/{repo_type}s/{target_repo}/blob/{target_revision}/{target_file}"
    return {
        "working": exists,
        "status": "resolved" if exists else "missing",
        "url": blob_url,
        "blob_url": blob_url,
        "resolve_url": raw_resolve_url,
        "canonical_url": blob_url,
        "reader_url": f"/read/{target_file}",
        "source": "huggingface",
        "repo_id": target_repo,
        "repo_type": repo_type,
        "revision": target_revision,
        "filename": target_file,
        "target_blank": True,
        "last_verified": now_iso,
        "error": None if exists else f"File not found in HF repo {target_repo}: {target_file}",
    }
