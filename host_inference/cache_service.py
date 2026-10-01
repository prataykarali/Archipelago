"""AI Call Minimization & Supabase Caching for Archipelago Host Inference.

Implements doc 03_ai_call_minimization_caching.md:
- Supabase response cache (ai_response_cache) with automatic local in-memory fallback
- Retrieval cache (retrieval_cache)
- Graph cache (graph_cache)
- Semantic query normalization
- Versioned cache keys: hash(normalized_query + graph_version + library_version + model_version + prompt_version)
- Request deduplication for concurrent in-flight queries
- AI budget protection & telemetry metrics
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import requests

logger = logging.getLogger("archipelago.cache")

DEFAULT_MODEL_VERSION = "qwen3.8-max"
DEFAULT_GRAPH_VERSION = "okf-5151-v3"
DEFAULT_PROMPT_VERSION = "v2.1"
DEFAULT_LIBRARY_VERSION = "2026.09"

RESPONSE_TTL_SEC = 3600      # 1 hour
RETRIEVAL_TTL_SEC = 1800     # 30 minutes
GRAPH_TTL_SEC = 7200         # 2 hours


class CacheMetrics:
    """Thread-safe counters for AI call minimization & cache efficiency."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.dedup_hits = 0
        self.tokens_saved = 0
        self.ai_calls_avoided = 0

    def record_request(self) -> None:
        with self._lock:
            self.total_requests += 1

    def record_hit(self, tokens_saved: int = 350) -> None:
        with self._lock:
            self.cache_hits += 1
            self.ai_calls_avoided += 1
            self.tokens_saved += tokens_saved

    def record_miss(self) -> None:
        with self._lock:
            self.cache_misses += 1

    def record_dedup(self, tokens_saved: int = 350) -> None:
        with self._lock:
            self.dedup_hits += 1
            self.ai_calls_avoided += 1
            self.tokens_saved += tokens_saved

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            ratio = (self.cache_hits + self.dedup_hits) / max(1, self.total_requests)
            return {
                "ai_requests_total": self.total_requests,
                "ai_cache_hits": self.cache_hits,
                "ai_cache_misses": self.cache_misses,
                "ai_dedup_hits": self.dedup_hits,
                "ai_requests_saved": self.ai_calls_avoided,
                "tokens_saved": self.tokens_saved,
                "cache_hit_ratio": round(ratio, 4),
                "cache_hit_percentage": f"{round(ratio * 100, 1)}%",
            }


class RequestDeduplicator:
    """In-flight request coalescing to prevent stampedes on identical concurrent queries."""

    def __init__(self, wait_timeout: float = 25.0) -> None:
        self._lock = threading.Lock()
        self._in_flight: Dict[str, threading.Event] = {}
        self._results: Dict[str, Any] = {}
        self.wait_timeout = wait_timeout

    def is_in_flight(self, key: str) -> bool:
        with self._lock:
            return key in self._in_flight

    def start_flight(self, key: str) -> bool:
        """Atomically register as the primary flight leader. Returns True if leader, False if already in-flight."""
        with self._lock:
            if key in self._in_flight:
                return False
            self._in_flight[key] = threading.Event()
            return True

    def wait(self, key: str) -> Optional[Any]:
        """Followers wait for the leader to complete and return the result."""
        with self._lock:
            evt = self._in_flight.get(key)
        if not evt:
            return None
        if evt.wait(timeout=self.wait_timeout):
            with self._lock:
                return self._results.get(key)
        return None

    def complete(self, key: str, result: Any) -> None:
        """Leader sets result and unblocks all waiting followers."""
        with self._lock:
            self._results[key] = result
            evt = self._in_flight.get(key)
            if evt:
                evt.set()

    def cleanup(self, key: str) -> None:
        with self._lock:
            self._in_flight.pop(key, None)
            self._results.pop(key, None)


class CacheService:
    """Thread-safe Supabase & in-memory cache manager implementing doc 03 specifications."""

    def __init__(
        self,
        model_version: str = DEFAULT_MODEL_VERSION,
        graph_version: str = DEFAULT_GRAPH_VERSION,
        prompt_version: str = DEFAULT_PROMPT_VERSION,
        library_version: str = DEFAULT_LIBRARY_VERSION,
    ) -> None:
        self._lock = threading.Lock()
        self.model_version = model_version
        self.graph_version = graph_version
        self.prompt_version = prompt_version
        self.library_version = library_version

        # In-memory storage for high-speed cache & offline fallback
        self._mem_response: Dict[str, Dict[str, Any]] = {}
        self._mem_retrieval: Dict[str, Dict[str, Any]] = {}
        self._mem_graph: Dict[str, Dict[str, Any]] = {}

        self.supabase_url = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.supabase_key = (
            os.environ.get("SUPABASE_SECRET_KEY")
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
            or os.environ.get("SUPABASE_SERVICE_KEY")
            or os.environ.get("SUPABASE_PUBLISHABLE_KEY", "")
        ).strip()
        self.has_supabase = bool(self.supabase_url and self.supabase_key)
        self.supabase_table_available = True

    # ─── Query Normalization (Doc 03 Section 5) ──────────────────────────

    @staticmethod
    def normalize_query(query: str) -> str:
        """Strip filler prefixes, punctuation, and normalize whitespace for semantic equivalence."""
        if not query:
            return ""
        q = query.lower().strip()
        # Strip common student question filler prefixes
        fillers = [
            "can you please explain to me",
            "can you explain to me",
            "can you tell me about",
            "can you explain",
            "could you explain",
            "could you tell me",
            "tell me about",
            "what do you know about",
            "what is the meaning of",
            "what is meant by",
            "what is",
            "what are",
            "explain",
            "describe",
            "give me an overview of",
            "give me a summary of",
            "i want to learn about",
            "i want to know about",
            "i want to understand",
            "teach me",
        ]
        for f in fillers:
            if q.startswith(f + " "):
                q = q[len(f) + 1:].strip()
                break

        # Remove punctuation, symbols, redundant spaces
        q = re.sub(r"[?!.,;:_\-—/\\\"'()\[\]{}]+", " ", q)
        q = re.sub(r"\s+", " ", q).strip()
        return q

    @staticmethod
    def hash_str(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def generate_cache_key(self, norm_query: str) -> str:
        """Versioned cache key incorporating graph, library, model, and prompt versions."""
        raw = f"{norm_query}:{self.graph_version}:{self.library_version}:{self.model_version}:{self.prompt_version}"
        return self.hash_str(raw)

    # ─── Supabase REST Helper ────────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates",
        }

    # ─── Response Cache (Doc 03 Section 2, 3, 4) ─────────────────────────

    def get_cached_response(self, query: str) -> Optional[Dict[str, Any]]:
        """Lookup cached response. Checks in-memory cache first, then Supabase."""
        norm_query = self.normalize_query(query)
        if not norm_query:
            return None
        cache_key = self.generate_cache_key(norm_query)
        now = time.time()

        # 1. Fast in-memory lookup
        with self._lock:
            entry = self._mem_response.get(cache_key)
            if entry and entry.get("expires_at_epoch", 0) > now:
                entry["hit_count"] = entry.get("hit_count", 0) + 1
                entry["last_hit_at"] = datetime.now(timezone.utc).isoformat()
                return entry

        # 2. Supabase REST lookup if configured
        if self.has_supabase and self.supabase_table_available:
            try:
                url = f"{self.supabase_url}/rest/v1/ai_response_cache"
                params = {"cache_key": f"eq.{cache_key}", "select": "*"}
                resp = requests.get(url, headers=self._headers(), params=params, timeout=3.0)
                if resp.status_code == 200:
                    rows = resp.json()
                    if isinstance(rows, list) and rows:
                        row = rows[0]
                        expires_str = row.get("expires_at", "")
                        # Verify not expired
                        try:
                            exp_dt = datetime.fromisoformat(expires_str.replace("Z", "+00:00"))
                            if datetime.now(timezone.utc) <= exp_dt:
                                # Populate local memory cache
                                row["expires_at_epoch"] = exp_dt.timestamp()
                                with self._lock:
                                    self._mem_response[cache_key] = row
                                return row
                        except Exception:
                            return row
                elif resp.status_code in {404, 400}:
                    # Table may not be created in Supabase schema yet; avoid repeated failing HTTP calls
                    self.supabase_table_available = False
            except Exception as e:
                logger.debug("Supabase cache read exception: %s", e)

        return None

    def cache_response(
        self,
        query: str,
        response_text: str,
        sources: Optional[List[Any]] = None,
        graph_data: Optional[Dict[str, Any]] = None,
        roadmap_data: Optional[List[Any]] = None,
        ttl_seconds: int = RESPONSE_TTL_SEC,
    ) -> None:
        """Cache a newly synthesized AI response."""
        norm_query = self.normalize_query(query)
        if not norm_query or not response_text:
            return
        query_hash = self.hash_str(norm_query)
        cache_key = self.generate_cache_key(norm_query)
        now_dt = datetime.now(timezone.utc)
        exp_dt = datetime.fromtimestamp(now_dt.timestamp() + ttl_seconds, tz=timezone.utc)

        data = {
            "cache_key": cache_key,
            "normalized_query": norm_query,
            "query_hash": query_hash,
            "response": response_text,
            "sources": sources or [],
            "graph_data": graph_data or {},
            "roadmap_data": roadmap_data or [],
            "model_version": self.model_version,
            "graph_version": self.graph_version,
            "prompt_version": self.prompt_version,
            "library_version": self.library_version,
            "created_at": now_dt.isoformat(),
            "expires_at": exp_dt.isoformat(),
            "expires_at_epoch": exp_dt.timestamp(),
            "hit_count": 0,
        }

        # 1. Update in-memory cache
        with self._lock:
            self._mem_response[cache_key] = data

        # 2. Persist to Supabase REST asynchronously / best-effort
        if self.has_supabase and self.supabase_table_available:
            def _push():
                try:
                    payload = dict(data)
                    payload.pop("expires_at_epoch", None)
                    url = f"{self.supabase_url}/rest/v1/ai_response_cache"
                    requests.post(url, headers=self._headers(), json=payload, timeout=4.0)
                except Exception:
                    pass

            threading.Thread(target=_push, daemon=True).start()

    # ─── Retrieval Cache (Doc 03 Section 6) ───────────────────────────────

    def get_cached_retrieval(self, query: str) -> Optional[Dict[str, Any]]:
        query_hash = self.hash_str(self.normalize_query(query))
        now = time.time()
        with self._lock:
            entry = self._mem_retrieval.get(query_hash)
            if entry and entry.get("expires_at_epoch", 0) > now:
                return entry
        return None

    def cache_retrieval(self, query: str, data: Dict[str, Any], ttl_seconds: int = RETRIEVAL_TTL_SEC) -> None:
        query_hash = self.hash_str(self.normalize_query(query))
        exp_epoch = time.time() + ttl_seconds
        payload = dict(data)
        payload["query_hash"] = query_hash
        payload["expires_at_epoch"] = exp_epoch
        with self._lock:
            self._mem_retrieval[query_hash] = payload

    # ─── Graph Cache (Doc 03 Section 7) ───────────────────────────────────

    def get_cached_graph(self, concept_id: str) -> Optional[Dict[str, Any]]:
        key = f"{concept_id}:{self.graph_version}"
        now = time.time()
        with self._lock:
            entry = self._mem_graph.get(key)
            if entry and entry.get("expires_at_epoch", 0) > now:
                return entry
        return None

    def cache_graph(self, concept_id: str, data: Dict[str, Any], ttl_seconds: int = GRAPH_TTL_SEC) -> None:
        key = f"{concept_id}:{self.graph_version}"
        exp_epoch = time.time() + ttl_seconds
        payload = dict(data)
        payload["concept_id"] = concept_id
        payload["graph_version"] = self.graph_version
        payload["expires_at_epoch"] = exp_epoch
        with self._lock:
            self._mem_graph[key] = payload


# Global shared singletons
cache_service = CacheService()
request_dedup = RequestDeduplicator()
cache_metrics = CacheMetrics()
