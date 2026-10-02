"""Concept data bootstrap for the inference service."""

from __future__ import annotations

import json

from archipelago.inference import state as st
from archipelago.inference.aliases import generate_aliases


def init_concepts_data():
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
        # Session 2: precompute aliases for acronym/alias-aware ranking
        for cid, concept in st.CONCEPTS_DATA.items():
            if "id" not in concept:
                concept["id"] = cid
            concept["aliases"] = generate_aliases(concept)
        print(f"Synchronously loaded {len(st.CONCEPTS_DATA)} concepts at startup (aliases ready).")
    except Exception as e:
        print(f"Error loading concepts at startup: {e}")
