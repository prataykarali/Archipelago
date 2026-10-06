"""Vercel's fail-closed WSGI entrypoint for the approved hosted corpus."""

from __future__ import annotations

import os

MINIMUM_LIVE_CONCEPTS = 520
MINIMUM_LIVE_PEARSON_BOOKS = 40


def create_vercel_app(context=None):
    """Load private Supabase artifacts and reject a fixture or partial catalog."""
    os.environ["ARCHIPELAGO_ENV"] = "production"
    from hostapp.factory import build_context, create_app
    from live_wsgi import validate_release_context

    release_floor = {
        "minimum_concepts": MINIMUM_LIVE_CONCEPTS,
        "minimum_pearson_books": MINIMUM_LIVE_PEARSON_BOOKS,
    }
    active_context = context or build_context()
    validate_release_context(active_context, release_floor)
    application = create_app(active_context)

    @application.after_request
    def release_headers(response):
        response.headers["X-Archipelago-Release"] = (
            os.environ.get("VERCEL_GIT_COMMIT_SHA")
            or os.environ.get("ARCHIPELAGO_RELEASE_SHA")
            or "unversioned"
        )
        return response

    return application
