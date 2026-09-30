"""Top-level firewall module implementing Stage1Firewall as specified in Archipelago technical spec."""
from __future__ import annotations

import re
from typing import Optional, Tuple
import numpy as np

from src.core.router import QueryRouter, RoutingTier, SECURITY_BOUNDARY_MESSAGE, OUT_OF_SCOPE_MESSAGE, MAX_QUERY_LENGTH


class Stage1Firewall:
    """Enforces query validation, conversational normalization, and domain gating."""

    MAX_QUERY_LEN: int = MAX_QUERY_LENGTH
    CONVERSATIONAL_PREFIXES: Tuple[str, ...] = (
        "can you tell me about", "what is", "explain", "how does", "could you explain",
        "tell me about", "show me", "define", "give an overview of"
    )

    def __init__(self, kill_switch_threshold: float = 0.75) -> None:
        self.theta_kill = kill_switch_threshold
        self._router = QueryRouter(tier1_threshold=kill_switch_threshold)

    def validate_and_normalize(self, raw_query: str) -> Tuple[bool, str, Optional[str]]:
        """Validate query length, malicious injections, and strip non-semantic conversational framing."""
        return self._router.validate_and_normalize(raw_query)

    def evaluate_cosine_kill_switch(self, query_vec: np.ndarray, index_matrix: np.ndarray) -> Tuple[bool, float]:
        """Calculates dot product similarity and enforces theta_kill abort."""
        if index_matrix.size == 0 or query_vec.size == 0:
            return False, 0.0
        q_norm = query_vec / (np.linalg.norm(query_vec) + 1e-9)
        sims = np.dot(index_matrix, q_norm)
        max_sim = float(np.max(sims)) if sims.size > 0 else 0.0
        passed = max_sim >= self.theta_kill
        return passed, max_sim


__all__ = ["Stage1Firewall", "SECURITY_BOUNDARY_MESSAGE", "OUT_OF_SCOPE_MESSAGE"]
