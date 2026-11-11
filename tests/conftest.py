from pathlib import Path
import re
from unittest.mock import MagicMock, patch

import pytest

pytest_plugins = ("tests.graph_fixtures",)

REPO_ROOT = Path(__file__).resolve().parents[1]

# Artifacts written by the ingestion/pipeline code paths. They are gitignored
# and live at the repository root in production, but a test must never write
# them there: doing so overwrites the local concept corpus (okf_graph.json)
# that inference loads, which silently breaks routing.
_GENERATED_ARTIFACTS = (
    "okf_graph.json",
    "okf_graph.db",
    "okf_results.json",
    "graph_audit.json",
    "accuracy.json",
    "pdf_chunks.json",
    "_graph_nodes.json",
    "_graph_edges.json",
    "source_audit.json",
)


def _artifact_state() -> dict:
    """Fingerprint each generated repo-root artifact by existence + size.

    Size (not mtime) is deliberate: closing a Kùzu handle legitimately touches
    ``okf_graph.db``'s mtime without changing its contents, whereas the bug we
    guard against rewrites the corpus and changes its size.
    """
    state: dict = {}
    for name in _GENERATED_ARTIFACTS:
        path = REPO_ROOT / name
        state[name] = path.stat().st_size if path.exists() else None
    return state


@pytest.fixture(autouse=True)
def _guard_repo_artifacts():
    """Fail any test that writes generated artifacts into the repository root."""
    before = _artifact_state()
    yield
    after = _artifact_state()
    changed = sorted(n for n in before if before[n] != after[n])
    assert not changed, (
        "test wrote generated artifacts into the repository root: "
        f"{changed}. Anchor pipeline output to tmp_path / a patched BASE_DIR."
    )


@pytest.fixture
def verified_student_auth(monkeypatch):
    """Install a verified Supabase-style test principal for protected routes."""
    from archipelago import supabase_auth

    principal = supabase_auth.AuthPrincipal(
        user_id="unit-test-user",
        username="unit-test-student",
        role="student",
        access_token="unit-test-session-token",
    )
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "1")
    monkeypatch.setattr(
        supabase_auth,
        "authenticate_request",
        lambda _request: (principal, None),
    )
    return principal


@pytest.fixture(autouse=True)
def _isolate_auth_required_env(monkeypatch):
    """Pin ``ARCHIPELAGO_AUTH_REQUIRED`` to 0 for tests that do not opt in.

    Several services (chat_server, the graph app) read this flag **at import
    time** into a module constant. Without pinning it, the developer ``.env``
    (which sets it to 1) leaks into the suite: any test that merely imports
    ``chat_server`` inherits "auth required", and unrelated tests then fail in a
    file-order-dependent way. Tests that assert the guarded behaviour set the
    variable themselves (see ``verified_student_auth`` and
    ``test_auth.py``), and monkeypatch restores whatever they chose.
    """
    monkeypatch.setenv("ARCHIPELAGO_AUTH_REQUIRED", "0")


@pytest.fixture(autouse=True)
def _isolate_external_services(monkeypatch):
    """Force every optional external service to its offline path.

    A developer ``.env`` points at real Supabase / Hugging Face / LLM
    endpoints. Without clearing those variables a test that intends to exercise
    the in-memory cache or the fake-client path silently uses the live service,
    so results depend on network state and on what earlier tests cached. Each
    test then starts from a known-empty cache.
    """
    for var in (
        "SUPABASE_URL",
        "SUPABASE_SECRET_KEY",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_SERVICE_KEY",
        "SUPABASE_PUBLISHABLE_KEY",
        "HF_TOKEN",
        "XKIRO_API_KEY",
        "GEMINI_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture
def mock_ollama():
    """Patches/mocks ollama.Client calls to avoid connecting to a local Ollama server during tests."""
    mock_client_instance = MagicMock()

    mock_list_response = {"models": [{"name": "qwen3.5:0.8b"}]}
    mock_client_instance.list.return_value = mock_list_response

    mock_chat_response = {
        "message": {
            "role": "assistant",
            "content": "Mocked Ollama response content.",
            "tool_calls": [],
        }
    }
    mock_client_instance.chat.return_value = mock_chat_response

    with patch("ollama.Client", return_value=mock_client_instance):
        yield mock_client_instance


@pytest.fixture
def flask_test_client(tmp_kuzu_db, sample_concepts):
    """Initializes concepts data and returns flask client, overriding the db with the temporary one."""
    from archipelago.inference.bootstrap import app
    import archipelago.inference.state as inference_server

    # Save original values to restore later
    old_db = inference_server.db
    old_concepts = inference_server.CONCEPTS_DATA

    # Point server db to the temporary test db
    inference_server.db = tmp_kuzu_db.db

    # Build CONCEPTS_DATA from sample_concepts
    concepts_dict = {}
    for concept in sample_concepts:
        name = concept["concept_name"]
        cid = "".join(ch if ch.isalnum() else "_" for ch in name.lower())
        cid = re.sub(r"_+", "_", cid).strip("_") or "concept"
        concepts_dict[cid] = {
            "id": cid,
            "label": name,
            "name": name,
            "concept_type": concept.get("concept_type", "definition"),
            "difficulty": concept.get("difficulty", "intermediate"),
            "summary": concept.get("summary", ""),
        }
    inference_server.CONCEPTS_DATA = concepts_dict

    with app.test_client() as client:
        yield client

    # Restore original values
    inference_server.db = old_db
    inference_server.CONCEPTS_DATA = old_concepts
