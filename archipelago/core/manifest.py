"""RunManifest module for Archipelago research reproducibility."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


@dataclass(frozen=True)
class RunManifest:
    """Immutable multi-dimensional version manifest for every executed answer.
    
    Guarantees research reproducibility by binding every output to exact versions
    of the graph, corpus, model, prompt, and retrieval configuration.
    """

    run_id: str = field(default_factory=lambda: f"run_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    graph_version: str = "v5.0.0"
    corpus_version: str = "cs_pilot_v1.0"
    model_version: str = "qwen3.5:0.8b"
    prompt_version: str = "synthesis_v2.0"
    retrieval_config_version: str = "arctic_matryoshka_1024_k2"

    def to_dict(self) -> dict[str, Any]:
        """Serialize manifest to dictionary for JSON output."""
        return {
            "run_id": self.run_id,
            "timestamp": self.timestamp.isoformat(),
            "graph_version": self.graph_version,
            "corpus_version": self.corpus_version,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "retrieval_config_version": self.retrieval_config_version,
        }
