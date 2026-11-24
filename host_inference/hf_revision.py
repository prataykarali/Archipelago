"""Resolve immutable Hugging Face dataset revisions for the research release."""

from __future__ import annotations

import os

GRAPH_REPO = "Prataykarali/graphier"
LIBRARY_REPO = "Prataykarali/Library_books"
GRAPH_REVISION = "86e29828c38dbf0f8cea5d50ed6a341ccde3a8f3"
LIBRARY_REVISION = "b0561c76a4c5a7a8cb1fe3bd91b389280d504cbd"


def dataset_revision(repo: str) -> str:
    """Return the reviewed commit and reject alternate hosted repositories."""
    if repo == GRAPH_REPO:
        return GRAPH_REVISION
    if repo == LIBRARY_REPO:
        return LIBRARY_REVISION
    if os.getenv("VERCEL"):
        raise ValueError("unapproved_hf_dataset_repo")
    return "main"
