"""Request Deduplication for Archipelago Inference."""
from __future__ import annotations

import threading
from typing import Any, Dict, Optional

class RequestDeduplicator:
    """Tracks in-flight requests and shares responses for identical concurrent queries."""
    
    def __init__(self, max_wait_timeout: float = 30.0):
        self._lock = threading.Lock()
        self._in_flight: Dict[str, threading.Event] = {}
        self._results: Dict[str, Any] = {}
        self.max_wait_timeout = max_wait_timeout

    def is_in_flight(self, normalized_query: str) -> bool:
        """Check if a query is currently in-flight."""
        with self._lock:
            return normalized_query in self._in_flight
            
    def mark_in_flight(self, normalized_query: str) -> None:
        """Mark a query as in-flight."""
        with self._lock:
            if normalized_query not in self._in_flight:
                self._in_flight[normalized_query] = threading.Event()
                
    def wait_for_result(self, normalized_query: str) -> Optional[Any]:
        """Wait for an in-flight query to complete and return its result."""
        with self._lock:
            event = self._in_flight.get(normalized_query)
        
        if event:
            # Wait for the event to be set
            if event.wait(timeout=self.max_wait_timeout):
                with self._lock:
                    return self._results.get(normalized_query)
        return None
        
    def complete_request(self, normalized_query: str, result: Any) -> None:
        """Mark a query as complete, store result, and notify waiters."""
        with self._lock:
            self._results[normalized_query] = result
            event = self._in_flight.get(normalized_query)
            if event:
                event.set()
                
    def cleanup(self, normalized_query: str) -> None:
        """Clean up state after result is returned to all waiters."""
        with self._lock:
            self._in_flight.pop(normalized_query, None)
            self._results.pop(normalized_query, None)
