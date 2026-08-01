"""Readers-writer lock for safe concurrent graph DB access.

Shared by inference (read path) and ingestion (write/swap path) so inference
never imports the ingestion worker or its heavy OKF/ollama dependencies.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator


class GraphLock:
    """Allow concurrent graph reads; exclusive access for writes/swaps."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._readers = 0
        self._writers_waiting = 0
        self._writer_active = False

    @contextmanager
    def read_lock(self) -> Iterator[None]:
        with self._cond:
            while self._writer_active or self._writers_waiting > 0:
                self._cond.wait()
            self._readers += 1
        try:
            yield
        finally:
            with self._cond:
                self._readers -= 1
                if self._readers == 0:
                    self._cond.notify_all()

    @contextmanager
    def write_lock(self) -> Iterator[None]:
        with self._cond:
            self._writers_waiting += 1
            while self._writer_active or self._readers > 0:
                self._cond.wait()
            self._writers_waiting -= 1
            self._writer_active = True
        try:
            yield
        finally:
            with self._cond:
                self._writer_active = False
                self._cond.notify_all()


# Process-wide singleton — both inference and ingestion must share this object
# when co-located in one process. Multi-process deploys rely on DB read-only
# mode + atomic file swap instead.
graph_lock = GraphLock()
