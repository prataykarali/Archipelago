"""Flask application detected by Vercel's Python runtime."""

from __future__ import annotations

from vercel_wsgi import create_vercel_app

app = create_vercel_app()
