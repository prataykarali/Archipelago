"""Supabase Cache Service for Archipelago Inference."""
from __future__ import annotations

import os
import re
import time
import hashlib
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

try:
    from supabase import create_client, Client
    HAS_SUPABASE = True
except ImportError:
    HAS_SUPABASE = False

# Setup logging
logger = logging.getLogger(__name__)

class CacheService:
    """Thread-safe Supabase cache service."""
    
    def __init__(
        self, 
        model_version: str = "1.0",
        graph_version: str = "1.0",
        prompt_version: str = "1.0",
        library_version: str = "1.0"
    ):
        self._lock = threading.Lock()
        self.model_version = model_version
        self.graph_version = graph_version
        self.prompt_version = prompt_version
        self.library_version = library_version
        self.supabase: Optional[Client] = None
        
        self.response_ttl = 3600  # 1 hour
        self.retrieval_ttl = 1800  # 30 minutes
        self.graph_ttl = 7200  # 2 hours
        
        self._init_supabase()
        
    def _init_supabase(self) -> None:
        if not HAS_SUPABASE:
            logger.warning("Supabase python client not installed. Caching disabled.")
            return
            
        url = os.environ.get("SUPABASE_URL")
        key = (
            os.environ.get("SUPABASE_SERVICE_KEY")
            or os.environ.get("SUPABASE_SECRET_KEY")
            or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        )
        
        if not url or not key:
            logger.warning("SUPABASE_URL or SUPABASE_SECRET_KEY not set. Caching disabled.")
            return
            
        try:
            self.supabase = create_client(url, key)
        except Exception as e:
            logger.warning(f"Failed to initialize Supabase client: {e}. Caching disabled.")
            
    def _normalize_query(self, query: str) -> str:
        """Normalize query text: lowercase, strip punctuation, collapse whitespace."""
        if not query:
            return ""
        q = query.lower().strip()
        # Strip common filler phrases (can be extended)
        fillers = ["tell me about", "what is", "how do i", "can you explain"]
        for f in fillers:
            if q.startswith(f):
                q = q[len(f):].strip()
                
        q = re.sub(r"[\?\!\.,;:\-_/\\]+", " ", q)
        q = re.sub(r"\s+", " ", q).strip()
        return q
        
    def _hash(self, text: str) -> str:
        return hashlib.sha256(text.encode('utf-8')).hexdigest()
        
    def _generate_cache_key(self, normalized_query: str) -> str:
        key_base = f"{normalized_query}:{self.graph_version}:{self.model_version}:{self.prompt_version}"
        return self._hash(key_base)
        
    def get_cached_response(self, query: str) -> Optional[Dict[str, Any]]:
        """Get cached response if it exists and hasn't expired."""
        if not self.supabase:
            return None
            
        norm_query = self._normalize_query(query)
        if not norm_query:
            return None
            
        cache_key = self._generate_cache_key(norm_query)
        
        with self._lock:
            try:
                response = self.supabase.table("ai_response_cache") \
                    .select("*") \
                    .eq("cache_key", cache_key) \
                    .execute()
                    
                if response.data and len(response.data) > 0:
                    data = response.data[0]
                    # Check expiration
                    expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
                    if datetime.now().astimezone() > expires_at:
                        return None
                        
                    # Update hit count async ideally, but sync here for simplicity
                    self.supabase.table("ai_response_cache") \
                        .update({
                            "hit_count": data.get("hit_count", 0) + 1,
                            "last_hit_at": datetime.now().astimezone().isoformat()
                        }) \
                        .eq("id", data["id"]) \
                        .execute()
                        
                    return data
            except Exception as e:
                logger.warning(f"Error fetching cached response: {e}")
                
        return None
        
    def cache_response(self, query: str, response: Any, sources: Any, graph_data: Any, roadmap_data: Any) -> None:
        """Cache a generated response."""
        if not self.supabase:
            return
            
        norm_query = self._normalize_query(query)
        if not norm_query:
            return
            
        query_hash = self._hash(norm_query)
        cache_key = self._generate_cache_key(norm_query)
        expires_at = (datetime.now().astimezone() + timedelta(seconds=self.response_ttl)).isoformat()
        
        data = {
            "cache_key": cache_key,
            "normalized_query": norm_query,
            "query_hash": query_hash,
            "response": response,
            "sources": sources,
            "graph_data": graph_data,
            "roadmap_data": roadmap_data,
            "model_version": self.model_version,
            "graph_version": self.graph_version,
            "prompt_version": self.prompt_version,
            "library_version": self.library_version,
            "expires_at": expires_at
        }
        
        with self._lock:
            try:
                self.supabase.table("ai_response_cache").upsert(data, on_conflict="cache_key").execute()
            except Exception as e:
                logger.warning(f"Error caching response: {e}")

    def get_cached_retrieval(self, query_hash: str) -> Optional[Dict[str, Any]]:
        """Get cached retrieval data."""
        if not self.supabase:
            return None
            
        with self._lock:
            try:
                response = self.supabase.table("retrieval_cache") \
                    .select("*") \
                    .eq("query_hash", query_hash) \
                    .execute()
                    
                if response.data and len(response.data) > 0:
                    data = response.data[0]
                    expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
                    if datetime.now().astimezone() <= expires_at:
                        return data
            except Exception as e:
                logger.warning(f"Error fetching cached retrieval: {e}")
                
        return None
        
    def cache_retrieval(self, query_hash: str, data: Dict[str, Any]) -> None:
        """Cache retrieval data."""
        if not self.supabase:
            return
            
        expires_at = (datetime.now().astimezone() + timedelta(seconds=self.retrieval_ttl)).isoformat()
        cache_data = {
            "query_hash": query_hash,
            "concept_ids": data.get("concept_ids", []),
            "document_ids": data.get("document_ids", []),
            "graph_nodes": data.get("graph_nodes", []),
            "graph_edges": data.get("graph_edges", []),
            "retrieval_version": data.get("retrieval_version", "1.0"),
            "graph_version": self.graph_version,
            "expires_at": expires_at
        }
        
        with self._lock:
            try:
                self.supabase.table("retrieval_cache").upsert(cache_data, on_conflict="query_hash").execute()
            except Exception as e:
                logger.warning(f"Error caching retrieval: {e}")

    def get_cached_graph(self, concept_id: str) -> Optional[Dict[str, Any]]:
        """Get cached graph data for a concept."""
        if not self.supabase:
            return None
            
        with self._lock:
            try:
                response = self.supabase.table("graph_cache") \
                    .select("*") \
                    .eq("concept_id", concept_id) \
                    .eq("graph_version", self.graph_version) \
                    .execute()
                    
                if response.data and len(response.data) > 0:
                    data = response.data[0]
                    expires_at = datetime.fromisoformat(data["expires_at"].replace('Z', '+00:00'))
                    if datetime.now().astimezone() <= expires_at:
                        return data
            except Exception as e:
                logger.warning(f"Error fetching cached graph: {e}")
                
        return None
        
    def cache_graph(self, concept_id: str, data: Dict[str, Any]) -> None:
        """Cache graph data for a concept."""
        if not self.supabase:
            return
            
        expires_at = (datetime.now().astimezone() + timedelta(seconds=self.graph_ttl)).isoformat()
        cache_data = {
            "concept_id": concept_id,
            "graph_version": self.graph_version,
            "nodes": data.get("nodes", []),
            "edges": data.get("edges", []),
            "roadmap": data.get("roadmap", {}),
            "expires_at": expires_at
        }
        
        with self._lock:
            try:
                self.supabase.table("graph_cache").upsert(
                    cache_data, 
                    on_conflict="concept_id,graph_version"
                ).execute()
            except Exception as e:
                logger.warning(f"Error caching graph: {e}")
