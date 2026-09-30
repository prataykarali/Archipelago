from __future__ import annotations

import re
from typing import Any


def strip_think_tags(text: str) -> str:
    """Remove private reasoning blocks from model output."""
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.DOTALL | re.IGNORECASE).strip()


def cleanse_llm_output(text: str) -> str:
    """Apply conservative, deterministic cleanup to user-facing model text."""
    from archipelago.inference.synthesis_cleaner import enforce_sterile_prose

    cleaned = enforce_sterile_prose(strip_think_tags(text), fallback="")
    cleaned = re.sub(r"(?i)^\s*(?:hello[!,]?\s*)?(?:as an ai(?: study assistant)?[, ]*)", "", cleaned)
    cleaned = re.sub(r"(?i)\bBased on (?:the )?provided context(?: block)?[,]?\s*", "", cleaned)
    # Remove corrupted summary labels while retaining any useful prose after them.
    cleaned = re.sub(r"(?i)\b\d+(?:\.\d+)*\s+Experimental setup\b", "", cleaned)
    cleaned = re.sub(r"(?i)\bAppendix\s+[A-Z]\b", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*(?:Common confusion\.|Trace the path\s*->\s*tutorial\.?|Clean model\.)\s*", "", cleaned)
    cleaned = re.sub(r"(?im)^\s*Library pin\s*", "", cleaned)
    # Drop a parenthesized header that is only a sequence of page-link chips.
    cleaned = re.sub(r"(?m)^\s*\(\s*[^\n)]*\bp\.\d+\s*↗[^\n)]*\)\s*\n?", "", cleaned)
    cleaned = re.sub(r"\\\((.*?)\\\)", r"$ \1 $", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\\\[(.*?)\\\]", r"$$ \1 $$", cleaned, flags=re.DOTALL)
    cleaned = re.sub(r"\$\s{2,}(.*?)\s{2,}\$", lambda m: "$ " + m.group(1).strip() + " $", cleaned)
    cleaned = re.sub(r"\$\$\s{2,}(.*?)\s{2,}\$\$", lambda m: "$$ " + m.group(1).strip() + " $$", cleaned)
    def legacy_cite(match: re.Match[str]) -> str:
        import urllib.parse

        doc_id = re.sub(r"\s+", "", match.group(1).strip())
        page = int(match.group(2))
        url = f"/api/page-view?doc_id={urllib.parse.quote(doc_id, safe='')}&page={page}"
        return f"[1: {doc_id}, p.{page} ↗]({url})"
    cleaned = re.sub(r"\[CITE:\s*([^]|]+?)\s*\|\s*(\d+)\]", legacy_cite, cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    # Remove duplicate adjacent Markdown blocks without changing distinct content.
    blocks = re.split(r"\n\s*\n", cleaned)
    deduped: list[str] = []
    for block in blocks:
        if block.strip() and (not deduped or block.strip() != deduped[-1].strip()):
            deduped.append(block.strip())
    return "\n\n".join(deduped)


class ArchipelagoResponseSanitizer:
    """Stateless sanitizer for Archipelago LLM responses."""

    def sanitize(
        self,
        text: str,
        retrieved_concepts: dict[str, Any] | None = None,
        citation_payloads: list[dict[str, Any]] | None = None,
    ) -> str:
        cleaned = cleanse_llm_output(text)
        if citation_payloads:
            from archipelago.inference.citations import cleanse_model_citations

            cleaned = cleanse_model_citations(cleaned, citation_payloads)
        if retrieved_concepts:
            prerequisites = retrieved_concepts.get("prerequisites") or []
            unlocks = retrieved_concepts.get("unlocks") or []
            target = retrieved_concepts.get("target") or "(unknown)"
            def names(values: list[Any]) -> list[str]:
                return [str(v.get("name") or v.get("label") or v) if isinstance(v, dict) else str(v) for v in values]
            path = " → ".join(names(prerequisites) + [str(target)] + names(unlocks))
            cleaned += f"\n\n### Learning Path\n🧠 {path}"
        if citation_payloads:
            from archipelago.inference.citations import render_citation_from_payload

            evidence = ["### Evidence"]
            for payload in citation_payloads[:8]:
                evidence.append(f"- {render_citation_from_payload(payload)}")
            cleaned += "\n\n" + "\n".join(evidence)
        return cleaned
