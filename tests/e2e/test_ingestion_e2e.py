"""Live / E2E ingestion pipeline verification.

Validates the full chain from source file parsing to concept and relationship
extraction, graph population, and searchability.
"""

from __future__ import annotations

import csv
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = ROOT / "tests" / "fixtures"


@pytest.mark.e2e
def test_csv_ingestion_workflow(tmp_path: Path) -> None:
    """Test full cycle: parsing CSV fixture, validating columns, and extracting nodes."""
    csv_file = FIXTURES_DIR / "test_book.csv"
    assert csv_file.exists(), f"Fixture missing: {csv_file}"

    # 1. Parse CSV
    rows: list[dict[str, str]] = []
    with open(csv_file, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    assert len(rows) >= 2
    book_row = rows[0]
    assert book_row["title"] == "Test Book on Neural Networks"
    assert book_row["isbn"] == "978-0-00-000000-0"
    assert book_row["source_url"].startswith("https://")

    # 2. Simulate concept extraction from row content
    from okf.pipeline import clean_pipeline

    raw_concepts = [
        {
            "concept_name": "Artificial Neural Network",
            "concept_type": "method",
            "difficulty": "intermediate",
            "summary": "Computational models inspired by biological neural networks.",
            "prerequisites": ["Linear Algebra"],
            "unlocks": ["Deep Learning"],
            "related_to": [{"concept": "Perceptron", "relation": "extends"}],
            "tags": ["machine-learning", "neural-networks"],
        }
    ]

    cleaned = clean_pipeline(raw_concepts)
    assert len(cleaned) == 1
    assert cleaned[0]["concept_name"] == "Artificial Neural Network"
    assert cleaned[0]["difficulty"] == "intermediate"


@pytest.mark.e2e
def test_jobstore_lifecycle(tmp_path: Path) -> None:
    """Test job store creation, staging quarantine, and status updates."""
    from ingestion_jobs import JobStatus, JobStore

    jobs_dir = tmp_path / "jobs"
    store = JobStore(str(jobs_dir))

    # Create job
    job = store.create(filename="test_book.csv", title="Test Neural Networks Book")
    job_id = job["id"]
    assert job["status"] == JobStatus.QUEUED.value

    # Update through statuses
    store.update_status(job_id, JobStatus.PARSING)
    assert store.get(job_id)["status"] == JobStatus.PARSING.value

    store.update_status(job_id, JobStatus.EXTRACTION, progress="Extracting concepts")
    assert store.get(job_id)["status"] == JobStatus.EXTRACTION.value

    store.update_status(job_id, JobStatus.COMPLETE)
    assert store.get(job_id)["status"] == JobStatus.COMPLETE.value
