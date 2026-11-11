"""Normalize positional rows returned by Kùzu queries."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any


def query_rows(conn: Any, cypher: str) -> Iterator[list[Any]]:
    """Yield positional rows from a single result or a list of results."""
    yield from rows_from_result(conn.execute(cypher))


def rows_from_result(response: Any) -> Iterator[list[Any]]:
    """Yield positional rows from an already executed Kùzu query."""
    results = response if isinstance(response, list) else [response]
    for result in results:
        while result.has_next():
            row = result.get_next()
            if not isinstance(row, (list, tuple)):
                raise TypeError("Kùzu query returned a non-positional row")
            yield list(row)
