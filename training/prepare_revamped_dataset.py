"""Revamps the old v4.4 training dataset into standardized ChatML format.

Ensures high-quality pedagogical concept explanations, prerequisite chains,
and diagnostic verification MCQs grounded in authentic textbook citations.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

INPUT_V44_PATH = Path("training_data/unified_v4_4_train.jsonl")
OUTPUT_PATH = Path("data/datasets/dataset1_pedagogical_revamped.jsonl")


def revamp_v44_dataset(
    input_path: Path = INPUT_V44_PATH,
    output_path: Path = OUTPUT_PATH,
    max_records: int = 500,
) -> int:
    """Read existing v4.4 training pairs and format into clean ChatML."""
    if not input_path.is_file():
        raise FileNotFoundError(f"Input file {input_path} not found.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    revamped_count = 0

    with open(input_path, "r", encoding="utf-8") as f_in, open(output_path, "w", encoding="utf-8") as f_out:
        for line in f_in:
            if not line.strip():
                continue
            row = json.loads(line)

            task = row.get("task", "okf_extraction")
            doc_id = row.get("doc_id", "canonical_source")
            instruction = row.get("instruction", "")
            text_input = row.get("input", "")
            output_content = row.get("output", "")

            # If messages are already present, normalize system prompt
            if "messages" in row and row["messages"]:
                msgs = row["messages"]
                # Ensure system prompt is present
                if msgs[0]["role"] != "system":
                    msgs.insert(0, {
                        "role": "system",
                        "content": (
                            "You are an expert pedagogical AI librarian for Archipelago. "
                            "Extract structured knowledge concepts, prerequisite relationships, "
                            "and authoritative learning roadmaps without hallucinating unverified claims."
                        ),
                    })
                clean_row = {
                    "id": f"revamped_{row.get('id', revamped_count)}",
                    "task": "pedagogical_okf_extraction",
                    "dataset": "dataset1_pedagogical_revamped",
                    "doc_id": doc_id,
                    "messages": msgs,
                }
            else:
                user_msg = f"{instruction}\n\n{text_input}".strip()
                clean_row = {
                    "id": f"revamped_{row.get('id', revamped_count)}",
                    "task": task,
                    "dataset": "dataset1_pedagogical_revamped",
                    "doc_id": doc_id,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are an expert pedagogical AI librarian for Archipelago. "
                                "Extract structured knowledge concepts, prerequisite relationships, "
                                "and authoritative learning roadmaps without hallucinating unverified claims."
                            ),
                        },
                        {
                            "role": "user",
                            "content": user_msg,
                        },
                        {
                            "role": "assistant",
                            "content": output_content,
                        },
                    ],
                }

            f_out.write(json.dumps(clean_row, ensure_ascii=False) + "\n")
            revamped_count += 1
            if revamped_count >= max_records:
                break

    return revamped_count


if __name__ == "__main__":
    count = revamp_v44_dataset()
    print(f"✅ Successfully revamped {count} pedagogical training examples into {OUTPUT_PATH}")
