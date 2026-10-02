"""One-shot AST splitter for archipelago/inference/synthesis.py.

Moves top-level blocks VERBATIM into modules under synthesis_pkg/.  For each
new module the script computes the imports it needs by checking, for every
name referenced in its blocks, whether the name came from an original import
statement or from a sibling module.  Cross-sibling references are emitted as
direct ``from .sibling import name`` imports; the script aborts if the
sibling graph contains a cycle (none is expected with the chosen grouping).

Safety rails:
* every top-level def/class/assign must be claimed by exactly one group;
* every block must be copied byte-identically into exactly one module;
* after writing, the facade must expose the full original top-level name set.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

SRC = Path("archipelago/inference/synthesis.py")
OUT = Path("archipelago/inference/synthesis_pkg")
PKG_PATH = "archipelago.inference.synthesis"

GROUPS: dict[str, list[str]] = {
    "constants.py": [
        "OLLAMA_UNAVAILABLE_MSG", "_STREAM_SYSTEM_PROMPT", "stream_system_prompt",
    ],
    "reply_checks.py": [
        "_strip_residual_markers", "_count_words", "_looks_like_citation_spam",
        "_trim_verbose_study_answer", "_model_answer_is_usable", "_finalize_stream_answer",
    ],
    "library_render.py": [
        "render_catalog_stats", "render_library_info",
    ],
    "prose.py": [
        "_strip_latex", "_EMOJI_RE", "_SLANG_LEAK_RE",
        "enforce_sterile_prose", "is_readable_synthesis", "_scrub_slm_artifacts",
    ],
    "streaming.py": [
        "is_ollama_available", "stream_synthesis_with_ollama",
        "synthesize_with_ollama_streaming",
    ],
    "render_path.py": [
        "render_indexed_learning_path",
    ],
    "replies.py": [
        "closed_library_reply", "_extract_missing_topic", "_related_concepts_for_topic",
        "not_indexed_reply", "general_chat_reply", "identity_reply", "onboarding_reply",
    ],
    "graph_notes.py": [
        "_summarize_evidence", "build_graph_notes", "format_natural_fallback",
        "generate_aura_synthesis", "run_ollama_agent",
    ],
    "library_books.py": [
        "DOC_TITLE_MAP", "prettify_doc_title", "render_library_books",
        "render_library_chapters", "render_library_chapter_lookup",
        "_FRONTMATTER_RE", "_TOP_LEVEL_CHAPTER_RE",
    ],
    "core.py": [
        "synthesize_with_ollama",
    ],
}

# Names imported from synthesis_library that the old module re-exported.
REEXPORTS = "synthesis_library"


def _bound_names(node: ast.AST) -> list[str]:
    """Names an import statement binds."""
    out: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            out.append((alias.asname or alias.name).split(".")[0])
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            out.append(alias.asname or alias.name)
    return out


def _referenced(text: str) -> set[str]:
    tree = ast.parse(text)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            base = node
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                names.add(base.id)
    return names


def main() -> int:
    text = SRC.read_text(encoding="utf-8")
    tree = ast.parse(text)

    docstring = ast.get_docstring(tree)
    imports: list[tuple[str, list[str]]] = []   # (source_text, bound_names)
    blocks: dict[str, tuple[int, int, str]] = {}  # name -> (start, end, text)
    uncovered: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.Import) or isinstance(node, ast.ImportFrom):
            imports.append((ast.get_source_segment(text, node) or "", _bound_names(node)))
            continue
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue  # module docstring — kept on the facade
        name = None
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        if name is None:
            uncovered.append(f"line {node.lineno}: {type(node).__name__}")
            continue
        segment = ast.get_source_segment(text, node) or ""
        blocks[name] = (node.lineno, node.end_lineno, segment)

    if uncovered:
        print("ABORT — uncovered top-level statements:")
        for line in uncovered:
            print("  ", line)
        return 1

    claimed = [name for names in GROUPS.values() for name in names]
    dupes = {n for n in claimed if claimed.count(n) > 1}
    missing = sorted(set(blocks) - set(claimed))
    unknown = sorted(set(claimed) - set(blocks))
    if dupes or missing or unknown:
        print("ABORT — grouping mismatch.")
        print("  duplicated:", sorted(dupes))
        print("  not grouped:", missing)
        print("  unknown names:", unknown)
        return 1

    owner = {name: module for module, names in GROUPS.items() for name in names}

    # Emit modules.
    OUT.mkdir(exist_ok=True)
    module_texts: dict[str, str] = {}
    for module, names in GROUPS.items():
        parts: list[str] = []
        for name in names:
            parts.append(blocks[name][2])
        body = "\n\n\n".join(parts) + "\n"

        needed = _referenced(body)
        own = set(names)
        import_lines: list[str] = []
        seen_stmts: set[str] = set()
        for stmt_text, bound in imports:
            hits = set(bound) & needed
            if not hits:
                continue
            if stmt_text not in seen_stmts:
                seen_stmts.add(stmt_text)
                import_lines.append(stmt_text)

        # Sibling references.
        siblings: dict[str, set[str]] = {}
        for name in needed:
            target = owner.get(name)
            if target and target != module and name not in own:
                siblings.setdefault(target, set()).add(name)

        header = [
            '"""Auto-split from synthesis.py — do not edit blocks by hand."""',
            "from __future__ import annotations",
            "",
        ]
        if import_lines:
            header.append("\n".join(import_lines))
        for sibling, names_from in sorted(siblings.items()):
            header.append(
                f"from .{sibling[:-3]} import {', '.join(sorted(names_from))}  # noqa: F401"
            )
        module_texts[module] = "\n".join(header) + "\n\n\n" + body

    # Cycle check on the sibling graph.
    graph = {m: set() for m in GROUPS}
    for module in GROUPS:
        for line in module_texts[module].splitlines():
            if line.startswith("from .") and " import " in line:
                dep = line.split()[1].lstrip(".").rstrip(",")
                graph[module].add(dep + ".py")

    state: dict[str, int] = {}

    def visit(node: str, stack: list[str]) -> None:
        state[node] = 1
        for dep in sorted(graph[node]):
            if state.get(dep, 0) == 1:
                print(f"ABORT — sibling cycle: {' -> '.join(stack + [node, dep])}")
                sys.exit(1)
            if state.get(dep, 0) == 0:
                visit(dep, stack + [node])
        state[node] = 2

    for module in GROUPS:
        if state.get(module, 0) == 0:
            visit(module, [])

    # Byte-identity check before writing.
    for name, (_s, _e, segment) in blocks.items():
        module = owner[name]
        if segment not in module_texts[module]:
            print(f"ABORT — block {name} not copied verbatim into {module}")
            return 1

    for module, content in module_texts.items():
        (OUT / module).write_text(content, encoding="utf-8")
        print(f"wrote {module:22s} {len(content.splitlines()):4d} lines")

    # Facade.
    all_names = sorted(blocks)
    facade = [
        f'"""{docstring}"""' if docstring else '"""Synthesis package facade."""',
        "from __future__ import annotations",
        "",
    ]
    for module, names in GROUPS.items():
        stem = module[:-3]
        facade.append(
            f"from .{stem} import (  # noqa: F401"
        )
        facade.extend(f"    {name}," for name in names)
        facade.append(")")
    facade.append(f"from archipelago.inference.{REEXPORTS} import (  # noqa: F401")
    facade.extend(
        f"    {alias},"
        for alias in (
            "view_page_url", "render_physical_resources", "render_catalog_resources",
            "render_resource_availability", "render_journal_status",
        )
    )
    facade.append(")")
    facade.append("")
    facade.append("__all__ = [" + ", ".join(f'"{n}"' for n in all_names) + "]")
    (OUT / "__init__.py").write_text("\n".join(facade) + "\n", encoding="utf-8")
    print(f"wrote __init__.py (facade, {len(all_names)} names)")

    # Post-write facade completeness check (import the real package).
    sys.path.insert(0, ".")
    import importlib
    facade_mod = importlib.import_module(PKG_PATH)
    absent = [n for n in all_names if not hasattr(facade_mod, n)]
    if absent:
        print("ABORT — facade is missing names:", absent)
        return 1
    print(f"facade exposes all {len(all_names)} original top-level names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
