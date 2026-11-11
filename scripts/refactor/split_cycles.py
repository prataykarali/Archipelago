"""Cycle detection for the source module splitter."""

from __future__ import annotations


def _cycles(graph: dict[str, set[str]]) -> list[str] | None:
    state: dict[str, int] = {}

    def visit(node: str, stack: list[str]) -> list[str] | None:
        state[node] = 1
        for dep in sorted(graph.get(node, ())):
            if state.get(dep, 0) == 1:
                return [*stack, node, dep]
            if state.get(dep, 0) == 0:
                found = visit(dep, [*stack, node])
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
