"""Unit tests for Hugging Face Remote Storage Client."""

import tempfile
from pathlib import Path
import pytest

from archipelago.storage.hf_remote import (
    HFStorageClient,
    compute_sha256,
)


def test_compute_sha256():
    data = b"Archipelago Knowledge Graph Corpus"
    sha = compute_sha256(data)
    assert len(sha) == 64
    assert isinstance(sha, str)

    with tempfile.NamedTemporaryFile("wb", delete=False) as f:
        f.write(data)
        f_path = f.name
    try:
        assert compute_sha256(f_path) == sha
    finally:
        Path(f_path).unlink()


def test_hf_storage_client_initialization(monkeypatch, tmp_path):
    monkeypatch.setenv("HF_DATASET_REPO", "Prataykarali/Library_books")
    monkeypatch.setenv("HF_TOKEN", "mock_token")

    client = HFStorageClient(cache_dir=tmp_path)
    assert client.repo_id == "Prataykarali/Library_books"
    assert client.token == "mock_token"
    assert client.cache_dir == tmp_path


def test_hf_storage_local_fallback(tmp_path):
    # Explicitly test offline fallback mode
    client = HFStorageClient(repo_id="test/repo", token=None, cache_dir=tmp_path, offline=True)
    assert client.is_available is False

    test_file = tmp_path / "sample.txt"
    test_file.write_text("Test content for storage")

    res = client.upload_file(test_file, "textbooks/sample.txt")
    assert res["success"] is True
    assert res["mode"] == "local_fallback"
    assert client.file_exists("textbooks/sample.txt") is True

    downloaded = client.download_file("textbooks/sample.txt")
    assert downloaded.is_file()
    assert downloaded.read_text() == "Test content for storage"


def test_hf_storage_list_files_offline(tmp_path):
    client = HFStorageClient(repo_id="test/repo", token=None, cache_dir=tmp_path, offline=True)
    client.upload_bytes(b"data 1", "books/ai/book1.txt")
    client.upload_bytes(b"data 2", "books/systems/book2.txt")

    files = client.list_files(prefix="books/ai")
    assert len(files) == 1
    assert "books/ai/book1.txt" in files[0]
