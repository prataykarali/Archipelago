"""New Chat must also release its server-side semantic context."""

from archipelago.inference.context_tracker import SESSION_CONTEXTS, get_or_create_context
from archipelago.inference.state import app
# Import registers the Flask route when this unit test runs without the normal
# inference bootstrap module.
import archipelago.inference.routes_context  # noqa: F401


def test_context_reset_removes_the_discarded_session():
    session_id = "test-discarded-session"
    get_or_create_context(session_id)
    assert session_id in SESSION_CONTEXTS

    with app.test_client() as client:
        response = client.post(
            "/api/context-status",
            json={"session_id": session_id, "action": "reset"},
        )

    assert response.status_code == 200
    assert response.get_json() == {"session_id": session_id, "reset": True}
    assert session_id not in SESSION_CONTEXTS
