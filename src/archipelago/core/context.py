"""Request context isolation module for Archipelago.

Guarantees thread-safe and async-safe request state tracking, completely
eliminating mutable global request state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .chunk import RetrievedChunk


@dataclass
class RequestContext:
    """Explicit request execution context.
    
    Every request processed by the Archipelago pipeline receives a unique,
    isolated RequestContext instance to prevent cross-request context pollution.
    """

    query: str
    user_id: str = "anonymous"
    request_id: str = field(default_factory=lambda: f"req_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    intent: str | None = None
    retrieved_sources: list[RetrievedChunk] = field(default_factory=list)
    graph_nodes: list[str] = field(default_factory=list)
    model_output: str | None = None
    verification_result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def add_retrieved_source(self, chunk: RetrievedChunk) -> None:
        """Attach a retrieved chunk to this request's isolated context."""
        self.retrieved_sources.append(chunk)

    def set_graph_nodes(self, nodes: list[str]) -> None:
        """Store graph nodes retrieved during topological traversal."""
        self.graph_nodes = list(nodes)

    def to_dict(self) -> dict[str, Any]:
        """Serialize context for audit logging or client response envelopes."""
        return {
            "request_id": self.request_id,
            "user_id": self.user_id,
            "query": self.query,
            "timestamp": self.timestamp.isoformat(),
            "intent": self.intent,
            "graph_nodes": self.graph_nodes,
            "verification_result": self.verification_result,
        }
