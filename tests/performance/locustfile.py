"""Locust load testing scenario for Archipelago API.

Simulates concurrent student queries, catalog lookups, and graph explorations.
Usage:
    locust -f tests/performance/locustfile.py --host http://localhost:5151
"""

from __future__ import annotations

import os
from locust import HttpUser, between, task


class ArchipelagoStudentUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        """Setup user auth token if configured."""
        self.auth_token = os.environ.get("TEST_AUTH_TOKEN", "mock-student-token")
        self.headers = {
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }

    @task(3)
    def test_health_check(self):
        """Basic liveness check."""
        self.client.get("/api/health")

    @task(2)
    def test_library_catalog(self):
        """Student browsing library holdings."""
        self.client.get("/api/library/data", headers=self.headers)

    @task(2)
    def test_subgraph_lookup(self):
        """Student viewing neighborhood concept graph."""
        self.client.get("/api/graph/subgraph?concept=Transformers&depth=2", headers=self.headers)

    @task(1)
    def test_chat_query(self):
        """Student asking question via Chat API."""
        payload = {
            "query": "What are the prerequisites for Transformers?",
            "stream": False,
        }
        self.client.post("/api/chat", json=payload, headers=self.headers)
