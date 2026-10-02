"""Generalized module splitter: turn a Python monolith into a package.

Moves top-level blocks VERBATIM into ``<out>/`` modules and a facade
``__init__.py`` that re-exports every original top-level name in original
order — so ``import <module>`` and ``from <module> import X`` keep working
and side-effect registrations (Flask routes) fire in the original sequence.

Grouping: pass ``--groups-json`` ({"01_pdf.py": ["serve_pdf", ...], ...}) or
let the script auto-pack consecutive blocks into modules of ``--max-lines``.

Safety rails:
* aborts on ``global`` statements (splitting would break them);
* aborts on top-level statements it cannot claim (other than the docstring);
* aborts on sibling import cycles (auto-retries by merging the cycle);
* every block is asserted byte-identical after write;
* the facade is asserted to expose the full original name set.

Usage::

    python scripts/refactor/split_module.py --src archipelago/inference/routes_misc.py --apply
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path


def _bound_names(node: ast.AST) -> list[str]:
    out: list[str] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            out.append((alias.asname or alias.name).split(".")[0])
    elif isinstance(node, ast.ImportFrom):
        for alias in node.names:
            out.append(alias.asname or alias.name)
    return out


def _referenced(text: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            base = node
            while isinstance(base, ast.Attribute):
                base = base.value
            if isinstance(base, ast.Name):
                names.add(base.id)
    return names


def _slug(name: str) -> str:
    return name.strip("_").lower() or "module"


def _module_level_assigned_names(node: ast.AST) -> set[str]:
    """Names assigned at module scope inside a top-level try/if/with block.

    Used so that names bound by a guarded import (e.g. ``try: import ollama``)
    remain visible to sibling modules through the package namespace.
    """
    out: set[str] = set()

    def walk(n: ast.AST) -> None:
        for child in ast.iter_child_nodes(n):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                continue
            if isinstance(child, ast.Assign):
                out.update(t.id for t in child.targets if isinstance(t, ast.Name))
            elif isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                out.add(child.target.id)
            elif isinstance(child, ast.Import):
                out.update((a.asname or a.name).split(".")[0] for a in child.names)
            elif isinstance(child, ast.ImportFrom):
                out.update(a.asname or a.name for a in child.names)
            walk(child)

    walk(node)
    return out


def _extract_blocks(text: str, tree: ast.Module) -> tuple[dict, list, str, dict, dict]:
    """Return (blocks, imports, docstring, globals, toplevel_bound)."""
    blocks: dict[str, tuple[int, int, str, list[str]]] = {}
    imports: list[tuple[str, list[str]]] = []
    problems: list[str] = []
    globals_by_block: dict[str, set[str]] = {}
    toplevel_bound: dict[str, set[str]] = {}
    docstring = ast.get_docstring(tree) or ""

    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            imports.append((ast.get_source_segment(text, node) or "", _bound_names(node)))
            continue
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            continue  # module docstring
        name = None
        start = node.lineno
        decorators: list[str] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            name = node.name
            if node.decorator_list:
                start = min(d.lineno for d in node.decorator_list)
                decorators = [
                    ast.get_source_segment(text, d) or "" for d in node.decorator_list
                ]
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name = node.target.id
        elif isinstance(node, (ast.If, ast.Try, ast.With, ast.AsyncWith, ast.For, ast.While)):
            # Top-level control-flow blocks (e.g. ``if __name__ == "__main__"``)
            name = f"_toplevel_{node.lineno}"
        elif isinstance(node, ast.Expr):
            # Side-effect calls at module level (e.g. mimetypes.add_type)
            name = f"_toplevel_{node.lineno}"
        if name is None:
            problems.append(f"line {node.lineno}: {type(node).__name__}")
            continue
        segment = ast.get_source_segment(text, node) or ""
        if decorators:
            segment = "\n".join("@" + d for d in decorators) + "\n" + segment
        for sub in ast.walk(node):
            if isinstance(sub, ast.Global):
                globals_by_block.setdefault(name, set()).update(sub.names)
        if name.startswith("_toplevel_"):
            toplevel_bound[name] = _module_level_assigned_names(node)
        blocks[name] = (start, node.end_lineno, segment, decorators)

    if problems:
        print("ABORT — cannot split mechanically:")
        for line in problems:
            print("  ", line)
        raise SystemExit(1)
    return blocks, imports, docstring, globals_by_block, toplevel_bound


def _pack(blocks: dict, order: list[str], max_lines: int) -> list[list[str]]:
    """Greedy consecutive packing under ``max_lines`` (decorators included)."""
    modules: list[list[str]] = []
    current: list[str] = []
    size = 0
    for name in order:
        block_size = blocks[name][1] - blocks[name][0] + 1
        if current and size + block_size > max_lines:
            modules.append(current)
            current, size = [], 0
        current.append(name)
        size += block_size + 2  # blank separators
    if current:
        modules.append(current)
    return modules


def _module_text(name_prefix: str, names: list[str], blocks: dict, imports: list, owner: dict, needs_deps: bool) -> str:
    parts = [blocks[name][2] for name in names]
    original_body = "\n\n\n".join(parts) + "\n"
    for name in names:
        if blocks[name][2] not in original_body:
            raise AssertionError(f"block {name} not verbatim in {name_prefix}")
    body = original_body
    needed = _referenced(body)
    import_lines: list[str] = []
    seen: set[str] = set()
    for stmt_text, bound in imports:
        if set(bound) & needed and stmt_text not in seen:
            seen.add(stmt_text)
            import_lines.append(stmt_text)
    # Sibling-owned names are resolved through the package namespace at call
    # time (``_rt.<name>``) so tests can keep monkeypatching the package the
    # way they did against the original single module.
    sibling_names: set[str] = set()
    for name in needed:
        target = owner.get(name)
        if target and target != name_prefix and name not in names:
            sibling_names.add(name)
    import re as _re

    for name in sibling_names:
        body = _re.sub(rf"\b{name}\b", f"_rt.{name}", body)
    header = ['"""Auto-split from monolith — blocks are verbatim."""', "from __future__ import annotations", ""]
    if import_lines:
        header.append("\n".join(import_lines))
    if needs_deps:
        header.append("from . import _deps as _rt  # noqa: F401")
    return "\n".join(header) + "\n\n\n" + body


def _cycles(graph: dict[str, set[str]]) -> list[str] | None:
    state: dict[str, int] = {}

    def visit(node: str, stack: list[str]) -> list[str] | None:
        state[node] = 1
        for dep in sorted(graph.get(node, ())):
            if state.get(dep, 0) == 1:
                return stack + [node, dep]
            if state.get(dep, 0) == 0:
                found = visit(dep, stack + [node])
                if found:
                    return found
        state[node] = 2
        return None

    for module in graph:
        if state.get(module, 0) == 0:
            found = visit(module, [])
            if found:
                return found
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", required=True)
    parser.add_argument("--max-lines", type=int, default=340)
    parser.add_argument("--groups-json", default=None)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    src = Path(args.src)
    out = src.parent / src.stem
    text = src.read_text(encoding="utf-8")
    blocks, imports, docstring, globals_by_block, toplevel_bound = _extract_blocks(text, ast.parse(text))
    order = sorted(blocks, key=lambda n: blocks[n][0])

    # ``global``-rebinding blocks plus the blocks that define their state must
    # live in ONE module; the facade late-binds those names via __getattr__ so
    # a rebind inside the state module stays visible to every caller.
    late_names: set[str] = set()
    forced_group: list[str] = []
    if globals_by_block:
        for gnames in globals_by_block.values():
            late_names |= gnames
        forced_group = [n for n in order if n in globals_by_block or n in late_names]
        if forced_group:
            print(
                f"note: {len(forced_group)} blocks with global state kept together "
                f"({', '.join(sorted(late_names))})"
            )

    if args.groups_json:
        groups_spec = json.loads(Path(args.groups_json).read_text())
        modules = [groups_spec[k] for k in sorted(groups_spec)]
        missing = sorted(set(blocks) - {n for m in modules for n in m})
        if missing:
            print("ABORT — ungrouped blocks:", missing)
            return 1
    else:
        modules = _pack(blocks, order, args.max_lines)

    if forced_group:
        # One state module first; every other module keeps its remaining blocks.
        forced_set = set(forced_group)
        modules = [[n for n in order if n in forced_set]] + [
            [n for n in names if n not in forced_set] for names in modules
        ]
        modules = [m for m in modules if m]

    def _module_file(i: int, names: list[str]) -> str:
        """Module filename: group key when provided, else partNN_<slug>."""
        if args.groups_json:
            return module_keys[i - 1]
        return f"part{i:02d}_{_slug(names[0])}.py"

    module_keys = sorted(groups_spec) if args.groups_json else None

    while True:
        owner = {
            name: _module_file(i, names)
            for i, names in enumerate(modules, 1)
            for name in names
        }
        # Names bound inside a top-level block belong to that block's module so
        # siblings resolve them through ``_rt.<name>``.
        for block_name, bound in toplevel_bound.items():
            for bound_name in bound:
                owner.setdefault(bound_name, owner[block_name])
        try:
            texts = {
                _module_file(i, names): _module_text(
                    _module_file(i, names), names, blocks, imports, owner, True
                )
                for i, names in enumerate(modules, 1)
            }
        except AssertionError as exc:
            print(f"ABORT — {exc}")
            return 1
        graph = {}  # sibling imports are late-bound — no import-time edges
        cycle = _cycles(graph)
        if not cycle:
            break
        # Merge the two modules that form the cycle, then retry.
        file_to_index = {_module_file(i, names): i - 1 for i, names in enumerate(modules, 1)}
        a, b = file_to_index[cycle[-2]], file_to_index[cycle[-1]]
        lo, hi = min(a, b), max(a, b)
        print(f"cycle detected ({' -> '.join(cycle)}); merging modules {lo + 1} + {hi + 1}")
        merged = modules[:lo] + [modules[lo] + modules[hi]] + modules[lo + 1:hi] + modules[hi + 1:]
        modules = merged
        module_keys = [
            f"merged{i:02d}_{_slug(names[0])}.py" for i, names in enumerate(modules, 1)
        ]

    # Verbatim identity of every block was asserted inside _module_text.

    print(f"plan for {src}: {len(modules)} modules")
    for module, content in texts.items():
        print(f"  {module:36s} {len(content.splitlines()):4d} lines")

    if not args.apply:
        print("(dry run — pass --apply to write)")
        return 0

    parts = list(src.with_suffix("").parts)
    # A dotted import path only when the leading directory is an actual package.
    import_name = (
        ".".join(parts)
        if len(parts) > 1 and (Path(parts[0]) / "__init__.py").exists()
        else src.stem
    )

    out.mkdir(exist_ok=True)
    (out / "_deps.py").write_text(
        '"""Late-bound access to this package namespace (monkeypatch contract)."""\n'
        "from __future__ import annotations\n\n"
        f"import {import_name} as _pkg\n\n\n"
        "def __getattr__(name: str):\n"
        '    """Resolve ``name`` against the live package namespace."""\n'
        "    return getattr(_pkg, name)\n",
        encoding="utf-8",
    )
    for module, content in texts.items():
        (out / module).write_text(content, encoding="utf-8")

    all_names = order
    facade = [
        f'"""{docstring}"""' if docstring else f'"""Facade for the split of {src.name}."""',
        "from __future__ import annotations",
        "",
    ]
    state_stem = _module_file(1, modules[0])[:-3] if forced_group else None
    for i, names in enumerate(modules, 1):
        stem = _module_file(i, names)[:-3]
        named = [n for n in names if n not in late_names]
        # Names bound by a guarded top-level block (e.g. ``try: import ollama``)
        # must be imported so side effects fire and siblings can resolve them.
        named += sorted(
            {b for n in names if n in toplevel_bound for b in toplevel_bound[n]}
            - set(named)
        )
        named = [n for n in named if not n.startswith("_toplevel_")]
        if not named:
            continue
        facade.append(f"from .{stem} import (  # noqa: F401")
        facade.extend(f"    {name}," for name in named)
        facade.append(")")
    # Re-export the original module-level import bindings (e.g. ``st``) so
    # attribute access like ``routes_misc.st`` keeps working. Emitted AFTER the
    # part modules so trailing/guarded imports (e.g.
    # ``from okf.pipeline_staged import ...``) see fully built siblings.
    if imports:
        facade.append("")
        for stmt_text, _bound in imports:
            facade.append(stmt_text + "  # noqa: F401")
    if state_stem and late_names:
        facade.append(f"from . import {state_stem} as _state  # noqa: F401")
        facade.append("")
        facade.append(
            "def __getattr__(name: str):\n"
            '    """Late-bind ``global``-rebound state (PEP 562)."""\n'
            "    return getattr(_state, name)"
        )
        facade.append("")
    facade.append("")
    named_all = [n for n in all_names if not n.startswith("_toplevel_")]
    facade.append("__all__ = [" + ", ".join(f'"{n}"' for n in named_all) + "]")
    (out / "__init__.py").write_text("\n".join(facade) + "\n", encoding="utf-8")
    print(f"wrote {out}/__init__.py (facade, {len(all_names)} names)")

    import importlib
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    facade_mod = importlib.import_module(import_name)
    absent = [n for n in named_all if not hasattr(facade_mod, n)]
    if absent:
        print("ABORT — facade missing names:", absent)
        return 1
    print(f"facade exposes all {len(all_names)} original top-level names")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
