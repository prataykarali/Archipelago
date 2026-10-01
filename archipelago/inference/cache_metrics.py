"""Cache metrics for Archipelago Inference."""
from __future__ import annotations

import threading
from typing import Dict, Any

class CacheMetrics:
    """Thread-safe counters for cache and dedup metrics."""
    
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._total_requests = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._dedup_hits = 0
        self._tokens_saved_estimate = 0
        
    def inc_total_requests(self) -> None:
        with self._lock:
            self._total_requests += 1
            
    def inc_cache_hit(self, tokens_saved: int = 0) -> None:
        with self._lock:
            self._cache_hits += 1
            self._tokens_saved_estimate += tokens_saved
            
    def inc_cache_miss(self) -> None:
        with self._lock:
            self._cache_misses += 1
            
    def inc_dedup_hit(self, tokens_saved: int = 0) -> None:
        with self._lock:
            self._dedup_hits += 1
            self._tokens_saved_estimate += tokens_saved
            
    def get_stats(self) -> Dict[str, Any]:
        """Get current metrics as a dictionary."""
        with self._lock:
            return {
                "total_requests": self._total_requests,
                "cache_hits": self._cache_hits,
                "cache_misses": self._cache_misses,
                "dedup_hits": self._dedup_hits,
                "tokens_saved_estimate": self._tokens_saved_estimate
            }
            
    def reset(self) -> None:
        """Reset all metrics to 0."""
        with self._lock:
            self._total_requests = 0
            self._cache_hits = 0
            self._cache_misses = 0
            self._dedup_hits = 0
            self._tokens_saved_estimate = 0

# Global instance for easy access
metrics = CacheMetrics()
