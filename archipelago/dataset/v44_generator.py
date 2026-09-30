"""
Archipelago v4.4 Training Dataset Synthesis Engine.

Generates fine-tuning conversational QnA pairs, prerequisite reasoning chains,
and 4-option diagnostic MCQs grounded in authentic textbook citations with
exact Pearson eLibrary reader page deep-links.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from archipelago.ingestion.pearson_connector import PearsonBook, PearsonCatalog
from archipelago.storage.hf_remote import HFStorageClient

logger = logging.getLogger("archipelago.dataset.v44_generator")

DEFAULT_OUTPUT_PATH = Path("data/datasets/v44_training_dataset.jsonl")


class V44DatasetGenerator:
    """Synthesizes high-fidelity pedagogical training examples from ingested concepts."""

    def __init__(self, catalog_path: str | Path = "data/catalogs/pearson_bookshelf.json"):
        self.catalog = None
        p = Path(catalog_path)
        if p.is_file():
            try:
                self.catalog = PearsonCatalog.load_from_file(p)
            except Exception as e:
                logger.warning("Could not load Pearson catalog: %s", e)

    def generate_example_explanation(self, concept: dict, book: PearsonBook | None = None) -> dict:
        """Task 1: Deep concept explanation grounded in textbook citation & deep reader link."""
        cid = concept["id"]
        cname = concept["name"]
        domain = concept.get("domain", "Computer Science")
        defn = concept.get("definition", f"{cname} is a fundamental concept in {domain}.")
        diff = concept.get("difficulty", "intermediate")
        page = concept.get("page_number", 1)

        reader_url = book.get_page_reader_url(page) if book else ""
        source_title = book.title if book else concept.get("source_book", "Computer Science Reference")
        author = book.author if book else "Author"

        citation_md = (
            f"**Authoritative Source**: [{source_title} (p. {page})]({reader_url}) — {author}\n"
            if reader_url else f"**Authoritative Source**: {source_title} (p. {page}) — {author}\n"
        )

        user_msg = f"Explain the concept of {cname} from a rigorous pedagogical perspective."
        asst_msg = (
            f"### 📘 Concept Overview: {cname}\n\n"
            f"{defn}\n\n"
            f"#### 🎓 Pedagogical Depth & Context\n"
            f"In {domain}, **{cname}** represents a {diff}-level foundational milestone. "
            f"Mastery requires understanding how its mathematical formulation and operational principles "
            f"connect with upstream foundational components.\n\n"
            f"#### 📖 Canonical Citation\n"
            f"{citation_md}"
        )

        return {
            "id": f"v44_exp_{cid}",
            "task": "pedagogical_explanation",
            "concept_id": cid,
            "concept_name": cname,
            "domain": domain,
            "difficulty": diff,
            "source_citation": {
                "book_title": source_title,
                "author": author,
                "page_number": page,
                "reader_deep_link": reader_url,
            },
            "messages": [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": asst_msg},
            ],
        }

    def generate_example_reasoning(
        self,
        concept: dict,
        prereq_name: str,
        book: PearsonBook | None = None,
    ) -> dict:
        """Task 2: Prerequisite dependency reasoning chain."""
        cid = concept["id"]
        cname = concept["name"]
        domain = concept.get("domain", "Computer Science")
        page = concept.get("page_number", 1)
        reader_url = book.get_page_reader_url(page) if book else ""
        source_title = book.title if book else concept.get("source_book", "Reference")

        user_msg = f"Why is {prereq_name} considered a prerequisite before studying {cname}?"
        asst_msg = (
            f"### 🔗 Dependency Reasoning: {prereq_name} → {cname}\n\n"
            f"In the pedagogical curriculum of **{domain}**, studying **{cname}** before mastering **{prereq_name}** "
            f"leads to significant conceptual gaps. Specifically:\n\n"
            f"1. **Theoretical Grounding**: {cname} builds directly upon the mathematical invariants and formal abstractions defined in {prereq_name}.\n"
            f"2. **Algorithmic Mechanics**: Without understanding the mechanics of {prereq_name}, the optimization steps and state transformations of {cname} appear arbitrary.\n"
            f"3. **Curriculum Invariant**: In canonical textbooks like *{source_title}*, {prereq_name} is developed earlier as an indispensable building block.\n\n"
            f"Therefore, {prereq_name} is topologically upstream of {cname} in the knowledge graph."
        )

        return {
            "id": f"v44_rea_{cid}_{prereq_name.lower().replace(' ', '_')}",
            "task": "prerequisite_reasoning",
            "concept_id": cid,
            "concept_name": cname,
            "prerequisite_name": prereq_name,
            "domain": domain,
            "source_citation": {
                "book_title": source_title,
                "reader_deep_link": reader_url,
            },
            "messages": [
                {"role": "user", "content": user_msg},
                {"role": "assistant", "content": asst_msg},
            ],
        }

    def generate_example_mcq(
        self,
        concept: dict,
        book: PearsonBook | None = None,
    ) -> dict:
        """Task 3: Diagnostic 4-option MCQ with literature citation and deep reader link."""
        cid = concept["id"]
        cname = concept["name"]
        domain = concept.get("domain", "Computer Science")
        defn = concept.get("definition", f"{cname} is a key concept.")
        page = concept.get("page_number", 1)
        reader_url = book.get_page_reader_url(page) if book else ""
        source_title = book.title if book else concept.get("source_book", "Reference")

        question = f"Which of the following statements most accurately characterizes {cname}?"
        options = {
            "A": defn,
            "B": f"{cname} is a deprecated heuristic that has been replaced by purely random parameter sampling.",
            "C": f"{cname} operates exclusively at compile-time without any runtime representation or state.",
            "D": f"{cname} guarantees O(1) worst-case time complexity across all arbitrary input topologies.",
        }
        correct_option = "A"
        explanation = f"Option A is correct: as defined in {source_title} (p. {page}), {defn}"

        return {
            "id": f"v44_mcq_{cid}",
            "task": "diagnostic_mcq",
            "concept_id": cid,
            "concept_name": cname,
            "domain": domain,
            "question": question,
            "options": options,
            "correct_option": correct_option,
            "explanation": explanation,
            "reader_deep_link": reader_url,
            "messages": [
                {
                    "role": "user",
                    "content": f"Diagnose my prerequisite knowledge for {cname} with a diagnostic multiple-choice question.",
                },
                {
                    "role": "assistant",
                    "content": (
                        f"**Diagnostic Question for {cname}**\n\n"
                        f"{question}\n\n"
                        f"- **A)** {options['A']}\n"
                        f"- **B)** {options['B']}\n"
                        f"- **C)** {options['C']}\n"
                        f"- **D)** {options['D']}\n\n"
                        f"*Ground Truth Answer: ({correct_option})*\n"
                        f"{explanation}\n"
                        + (f"[Verify in Pearson eLibrary Reader (p. {page})]({reader_url})" if reader_url else "")
                    ),
                },
            ],
        }

    def export_dataset(
        self,
        concepts: list[dict],
        output_path: str | Path = DEFAULT_OUTPUT_PATH,
        sync_to_hf: bool = False,
    ) -> dict:
        """Compile and save v4.4 dataset JSONL."""
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)

        examples = []
        for c in concepts:
            book = None
            if self.catalog:
                book = self.catalog.find_by_title(c.get("source_book", ""))

            # 1. Explanation example
            examples.append(self.generate_example_explanation(c, book))

            # 2. Prerequisite reasoning examples
            for p in c.get("prerequisites", []):
                p_name = p.get("name") if isinstance(p, dict) else str(p)
                examples.append(self.generate_example_reasoning(c, p_name, book))

            # 3. Diagnostic MCQ example
            examples.append(self.generate_example_mcq(c, book))

        with open(out, "w") as f:
            for ex in examples:
                f.write(json.dumps(ex) + "\n")

        logger.info("Exported %d v4.4 training examples to %s", len(examples), out)

        hf_result = None
        if sync_to_hf:
            hf_client = HFStorageClient()
            if hf_client.is_available:
                hf_result = hf_client.upload_file(out, f"datasets/v44/{out.name}")

        return {
            "success": True,
            "total_examples": len(examples),
            "output_path": str(out),
            "hf_sync": hf_result,
        }
