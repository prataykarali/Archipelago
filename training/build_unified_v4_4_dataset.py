#!/usr/bin/env python3
"""
Build unified v4.4 training dataset for lib-qwen.
Unifies:
1. OKF Extraction pairs from v4.4 (700 pairs with balanced hard negatives, papers, math).
2. Pearson v4.4 educational pairs (76 pairs: explanations, prerequisite reasoning chains, 4-option MCQs).
3. Pearson seminal concept OKF extraction pairs (synthetic extraction for Pearson textbook chapters).

Produces:
- training_data/unified_v4_4_train.jsonl
- training_data/unified_v4_4_test.jsonl
- training_data/unified_v4_4_manifest.json
"""

import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

DATA_DIR = ROOT / "training_data"
CATALOG_PATH = ROOT / "data" / "catalogs" / "pearson_bookshelf.json"
PEARSON_PAIRS_PATH = ROOT / "data" / "datasets" / "pearson_v44_pairs.jsonl"

TRAIN_IN_V44 = DATA_DIR / "okf_train_pairs_v4_4.jsonl"
TEST_IN_V44 = DATA_DIR / "okf_test_pairs_v4_4.jsonl"

TRAIN_OUT = DATA_DIR / "unified_v4_4_train.jsonl"
TEST_OUT = DATA_DIR / "unified_v4_4_test.jsonl"
MANIFEST_OUT = DATA_DIR / "unified_v4_4_manifest.json"

random.seed(42)

def make_chatml_messages(user_text: str, assistant_text: str):
    return [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": assistant_text}
    ]

def load_jsonl(path: Path):
    rows = []
    if not path.exists():
        return rows
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows

def generate_pearson_extraction_pairs():
    """Create extraction pairs for Pearson seminal concepts to align extraction with textbook bookshelf."""
    from training.build_pearson_v44_dataset import PEARSON_SEMINAL_CONCEPTS
    
    extraction_pairs = []
    instr = (
        "You are an OKF extraction engine for the Archipelago knowledge graph.\n"
        "From the TEXT below, extract 1-5 teachable CONCEPTS as a JSON array.\n\n"
        "Each object MUST have exactly these keys: concept_name, concept_type, difficulty, summary, prerequisites, unlocks, related_to, tags.\n"
        "If the passage has no teachable AIML concept, return [].\n"
        "Do not extract celebrities, authors as concepts, or evaluation boilerplate.\n\n"
        "TEXT:\n"
    )
    
    for item in PEARSON_SEMINAL_CONCEPTS:
        book_title = item["title"]
        concept_name = item["name"]
        defn = item["defn"]
        prereqs = item["prereqs"]
        diff = item["diff"]
        
        # Passage simulating a textbook excerpt
        passage = f"In {book_title}, {concept_name} is formalized as follows. {defn} Fundamental prerequisites include {', '.join(prereqs)}."
        user_prompt = instr + passage
        
        extracted_obj = [{
            "concept_name": concept_name,
            "concept_type": "method" if "Algorithm" in concept_name or "Method" in concept_name or "Exchange" in concept_name else "definition",
            "difficulty": diff,
            "summary": defn,
            "prerequisites": prereqs,
            "unlocks": [],
            "related_to": [{"concept": p, "relation": "builds_on"} for p in prereqs],
            "tags": [t.lower().replace(" ", "-") for t in [concept_name.split()[0], diff]]
        }]
        assistant_output = json.dumps(extracted_obj)
        
        extraction_pairs.append({
            "id": f"pearson_extract_{concept_name.lower().replace(' ', '_').replace('*', '_star')}",
            "task": "okf_extraction",
            "instruction": instr + passage,
            "input": "",
            "output": assistant_output,
            "messages": make_chatml_messages(user_prompt, assistant_output),
            "doc_id": f"pearson/{book_title}",
            "source": "pearson_catalog"
        })
        
    return extraction_pairs

def main():
    print("Loading base datasets...")
    okf_train = load_jsonl(TRAIN_IN_V44)
    okf_test = load_jsonl(TEST_IN_V44)
    pearson_pairs = load_jsonl(PEARSON_PAIRS_PATH)
    
    print(f"Loaded {len(okf_train)} OKF v4.4 train pairs, {len(okf_test)} OKF v4.4 test pairs.")
    print(f"Loaded {len(pearson_pairs)} Pearson v4.4 pairs.")
    
    # 1. Format OKF train rows to unified schema
    unified_train = []
    for row in okf_train:
        user_text = row["instruction"]
        if row.get("input"):
            user_text += "\n\n" + row["input"]
        output_text = str(row.get("output", "[]")).strip()
        
        unified_train.append({
            "id": row.get("chunk_id", f"okf_{len(unified_train)}"),
            "task": "okf_extraction",
            "instruction": row["instruction"],
            "input": row.get("input", ""),
            "output": output_text,
            "messages": make_chatml_messages(user_text, output_text),
            "doc_id": row.get("doc_id", "unknown"),
            "source": "okf_v4_4"
        })

    # 2. Format OKF test rows
    unified_test = []
    for row in okf_test:
        user_text = row["instruction"]
        if row.get("input"):
            user_text += "\n\n" + row["input"]
        output_text = str(row.get("output", "[]")).strip()
        
        unified_test.append({
            "id": row.get("chunk_id", f"okf_test_{len(unified_test)}"),
            "task": "okf_extraction",
            "instruction": row["instruction"],
            "input": row.get("input", ""),
            "output": output_text,
            "messages": make_chatml_messages(user_text, output_text),
            "doc_id": row.get("doc_id", "unknown"),
            "source": "okf_v4_4"
        })

    # 3. Add Pearson extraction pairs
    pearson_extractions = generate_pearson_extraction_pairs()
    print(f"Generated {len(pearson_extractions)} Pearson OKF extraction pairs.")
    
    # Split Pearson pairs into train (80%) and test (20%)
    all_pearson = pearson_pairs + pearson_extractions
    random.shuffle(all_pearson)
    p_split = int(len(all_pearson) * 0.85)
    pearson_train = all_pearson[:p_split]
    pearson_test = all_pearson[p_split:]
    
    for row in pearson_train:
        msgs = row.get("messages", [])
        if not msgs and "instruction" in row:
            msgs = make_chatml_messages(row["instruction"], row.get("output", ""))
        unified_train.append({
            "id": row.get("id", f"p_train_{len(unified_train)}"),
            "task": row.get("task", "educational"),
            "instruction": msgs[0]["content"] if msgs else "",
            "input": "",
            "output": msgs[1]["content"] if len(msgs) > 1 else "",
            "messages": msgs,
            "doc_id": row.get("doc_id", "pearson_catalog"),
            "source": "pearson_v4_4"
        })
        
    for row in pearson_test:
        msgs = row.get("messages", [])
        if not msgs and "instruction" in row:
            msgs = make_chatml_messages(row["instruction"], row.get("output", ""))
        unified_test.append({
            "id": row.get("id", f"p_test_{len(unified_test)}"),
            "task": row.get("task", "educational"),
            "instruction": msgs[0]["content"] if msgs else "",
            "input": "",
            "output": msgs[1]["content"] if len(msgs) > 1 else "",
            "messages": msgs,
            "doc_id": row.get("doc_id", "pearson_catalog"),
            "source": "pearson_v4_4"
        })

    # Shuffle training set
    random.shuffle(unified_train)
    
    # Save files
    with open(TRAIN_OUT, "w", encoding="utf-8") as f:
        for r in unified_train:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            
    with open(TEST_OUT, "w", encoding="utf-8") as f:
        for r in unified_test:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    manifest = {
        "train_count": len(unified_train),
        "test_count": len(unified_test),
        "train_composition": {
            "okf_v4_4": len(okf_train),
            "pearson_v4_4": len(pearson_train)
        },
        "tasks": {
            "okf_extraction": sum(1 for r in unified_train if r["task"] == "okf_extraction"),
            "pedagogical_explanation": sum(1 for r in unified_train if r["task"] == "pedagogical_explanation"),
            "prerequisite_reasoning": sum(1 for r in unified_train if r["task"] == "prerequisite_reasoning"),
            "diagnostic_mcq": sum(1 for r in unified_train if r["task"] == "diagnostic_mcq"),
        }
    }
    
    with open(MANIFEST_OUT, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
        
    print(f"\nUnified Dataset Built Successfully:")
    print(f"  Train: {len(unified_train)} examples -> {TRAIN_OUT}")
    print(f"  Test:  {len(unified_test)} examples -> {TEST_OUT}")
    print(f"  Tasks breakdown: {manifest['tasks']}")

if __name__ == "__main__":
    main()
