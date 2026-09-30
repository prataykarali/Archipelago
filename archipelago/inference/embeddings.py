"""Embedding + optional Aura model loading."""
from __future__ import annotations

import os
import json

import torch
import torch.nn.functional as F

from archipelago.inference import state as st

# Transformers pulls sklearn; import lazily so chat/inference can start
# even when the system sklearn/numpy wheels are ABI-incompatible.
AutoTokenizer = None
AutoModel = None
AutoModelForCausalLM = None


def _load_transformers() -> bool:
    """Import transformers on first embed/Aura load. Returns False if unavailable."""
    global AutoTokenizer, AutoModel, AutoModelForCausalLM
    if AutoTokenizer is not None:
        return True
    try:
        from transformers import (
            AutoTokenizer as _Tok,
            AutoModel as _Mod,
            AutoModelForCausalLM as _Causal,
        )
    except Exception as exc:
        print(f"transformers unavailable ({exc}); embeddings disabled.")
        return False
    AutoTokenizer = _Tok
    AutoModel = _Mod
    AutoModelForCausalLM = _Causal
    return True

def _embed_device_preference() -> str:
    """Pick embedder device. Prefer CPU when CUDA is broken or forced off."""
    force = (os.getenv("ARCHIPELAGO_FORCE_CPU_EMBED") or "").strip().lower()
    if force in ("1", "true", "yes", "cpu"):
        return "cpu"
    pref = (os.getenv("ARCHIPELAGO_EMBED_DEVICE") or "").strip().lower()
    if pref in ("cpu", "cuda"):
        if pref == "cuda" and not torch.cuda.is_available():
            return "cpu"
        return pref
    if not torch.cuda.is_available():
        return "cpu"
    # Probe CUDA — a dead driver can report is_available() True then fail.
    try:
        torch.zeros(1, device="cuda")
        return "cuda"
    except Exception as e:
        print(f"CUDA probe failed ({e}); using CPU for embeddings.")
        return "cpu"


def _disable_embeddings(reason: str) -> None:
    """Stop using the embedder after a runtime CUDA/device failure."""
    if st.use_embeddings:
        print(f"Disabling embeddings after failure: {reason}")
    st.use_embeddings = False
    st.CONCEPT_EMBEDDINGS_TENSOR = None


def load_embedding_model():
    try:
        if AutoTokenizer is None and not _load_transformers():
            st.use_embeddings = False
            build_concept_embeddings()
            return
        if not _load_transformers():
            st.use_embeddings = False
            build_concept_embeddings()
            return
        print(f"Loading embedding model {st.EMBED_MODEL_NAME}...")
        st.embed_tokenizer = AutoTokenizer.from_pretrained(st.EMBED_MODEL_NAME, trust_remote_code=True)
        st.embed_model = AutoModel.from_pretrained(st.EMBED_MODEL_NAME, trust_remote_code=True, add_pooling_layer=False)
        device = _embed_device_preference()
        st.embed_model = st.embed_model.to(device)
        st.embed_model.eval()
        st.use_embeddings = False
        st.CONCEPT_EMBEDDINGS_TENSOR = None
        print(f"✓ Embedding model loaded successfully on {device}!")
        build_concept_embeddings(force=True)
        if st.CONCEPT_EMBEDDINGS_TENSOR is not None:
            st.use_embeddings = True
    except Exception as e:
        print(f"Warning: Failed to load embedding model: {e}. Falling back to fuzzy matching.")
        st.use_embeddings = False
        build_concept_embeddings()


def load_aura_model():
    try:
        if not _load_transformers():
            st.aura_loaded = False
            return
        print(f"Loading generator model from {st.AURA_MODEL_PATH}...")
        st.aura_tokenizer = AutoTokenizer.from_pretrained(st.AURA_MODEL_PATH, trust_remote_code=True, fix_mistral_regex=True)
        st.aura_model = AutoModelForCausalLM.from_pretrained(
            st.AURA_MODEL_PATH,
            dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        st.aura_loaded = True
        print("✓ Generator model loaded successfully!")
    except Exception as e:
        print(f"Error loading generator model: {e}")
        st.aura_loaded = False


def build_concept_embeddings(*, force: bool = False):
    try:
        with open(st.DATA_FILE, encoding="utf-8") as f:
            data = json.load(f)
        nodes = list(data.get("visualization", {}).get("nodes", []) or data.get("nodes", []))
        extra_concepts = data.get("concepts", {})
        existing_ids = {n["id"] for n in nodes if "id" in n}
        for cid, c in extra_concepts.items():
            if cid not in existing_ids:
                c_node = dict(c)
                c_node.setdefault("id", cid)
                c_node.setdefault("label", c_node.get("name", cid))
                nodes.append(c_node)
        st.CONCEPTS_DATA = {n["id"]: n for n in nodes}
        
        if not st.use_embeddings:
            print("Skipping embedding pre-computation.")
            return
            
        print(f"Pre-computing embeddings for {len(nodes)} concepts in batches...")
        device = next(st.embed_model.parameters()).device
        
        texts = []
        cids = []
        for node in nodes:
            cid = node["id"]
            name = node.get("label") or node.get("name") or cid
            summary = node.get("summary", "")
            text = f"{name}: {summary}"
            texts.append(text)
            cids.append(cid)

        batch_size = 32
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_cids = cids[i : i + batch_size]
            inputs = st.embed_tokenizer(batch_texts, padding=True, truncation=True, return_tensors='pt', max_length=512).to(device)
            with torch.no_grad():
                model_output = st.embed_model(**inputs)
                embeddings = model_output[0][:, 0]
                embeddings = F.normalize(embeddings, p=2, dim=1)
                for cid, emb in zip(batch_cids, embeddings):
                    st.CONCEPT_EMBEDDINGS[cid] = emb.cpu()
                    
        st.CONCEPT_IDS = list(st.CONCEPT_EMBEDDINGS.keys())
        if st.CONCEPT_IDS:
            tensors_list = [st.CONCEPT_EMBEDDINGS[cid] for cid in st.CONCEPT_IDS]
            # Keep the lookup tensor on the same device as the embedder.
            st.CONCEPT_EMBEDDINGS_TENSOR = torch.stack(tensors_list).to(device)
            
        print("✓ Pre-computed concept embeddings and built fast lookup tensor!")
    except Exception as e:
        print(f"Error pre-computing concept embeddings: {e}")
        _disable_embeddings(str(e))


from collections import OrderedDict

_EMB_CACHE: OrderedDict[str, torch.Tensor] = OrderedDict()
_EMB_CACHE_MAX = 512


def clear_embedding_cache() -> None:
    _EMB_CACHE.clear()


def get_snowflake_embedding(text: str | list[str]) -> torch.Tensor | None:
    if not st.use_embeddings or st.embed_model is None or st.embed_tokenizer is None:
        return None
    if isinstance(text, (list, tuple)):
        texts = [str(item or "").strip() for item in text]
        if not texts or any(not item for item in texts):
            return None
        missing = [item for item in texts if item.lower() not in _EMB_CACHE]
        if missing:
            try:
                device = next(st.embed_model.parameters()).device
                prefix = "Represent this sentence for searching relevant passages: "
                inputs = st.embed_tokenizer([prefix + item for item in missing], padding=True,
                                            truncation=True, return_tensors="pt", max_length=512).to(device)
                with torch.no_grad():
                    output = st.embed_model(**inputs)
                    vectors = F.normalize(output[0][:, 0], p=2, dim=1).cpu()
                for item, vector in zip(missing, vectors):
                    _EMB_CACHE[item.lower()] = vector
                    while len(_EMB_CACHE) > _EMB_CACHE_MAX:
                        _EMB_CACHE.popitem(last=False)
            except Exception as exc:
                _disable_embeddings(str(exc))
                return None
        return torch.stack([_EMB_CACHE[item.lower()] for item in texts])
    key = (text or "").strip().lower()
    if not key:
        return None
    if key in _EMB_CACHE:
        _EMB_CACHE.move_to_end(key)
        return _EMB_CACHE[key]

    try:
        device = next(st.embed_model.parameters()).device
        prefix = "Represent this sentence for searching relevant passages: "
        full_text = prefix + text
        inputs = st.embed_tokenizer(full_text, padding=True, truncation=True, return_tensors='pt', max_length=512).to(device)
        with torch.no_grad():
            model_output = st.embed_model(**inputs)
            embeddings = model_output[0][:, 0]
            embeddings = F.normalize(embeddings, p=2, dim=1)
        res = embeddings[0].cpu()
        _EMB_CACHE[key] = res
        while len(_EMB_CACHE) > _EMB_CACHE_MAX:
            _EMB_CACHE.popitem(last=False)
        return res
    except Exception as e:
        _disable_embeddings(str(e))
        return None
