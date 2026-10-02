"""Make the sibling ``archipelago`` package importable from a standalone deploy.

``host_inference`` is deployed on its own — AntDeploy runs
``gunicorn --chdir host_inference``, so the repository root is not on
``sys.path`` and ``import archipelago`` fails with the container unable to load
its own factory. Two things used to paper over that: a ``PYTHONPATH`` in the
start command, and the hope that the platform reads ``.antideploy.json``. The
platform detects the entrypoint itself, so the start command is not ours to
control.

This module makes the import work from inside the package instead. It is
imported *before* the first ``archipelago`` import in
:mod:`hostapp.factory`, and it changes nothing when the package is already
importable — a local development run keeps whatever ``sys.path`` it had.

Security note: this does not duplicate
:mod:`archipelago.middleware.log_redaction`. There is exactly one implementation
of the redaction filter, and this only makes it reachable.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

#: ``host_inference`` itself, so the repository root is its parent.
HOST_DIR = Path(__file__).resolve().parent

#: The repository root, i.e. where the ``archipelago`` package lives.
REPO_ROOT = HOST_DIR.parent

#: Guard against repeated sys.path edits on repeated imports.
_MARKER = "archipelago"

__all__ = ["REPO_ROOT", "ensure_repo_root_importable"]


def ensure_repo_root_importable() -> bool:
    """Add the repository root to ``sys.path`` if ``archipelago`` needs it.

    Returns:
        True when the package was already importable (nothing changed), False
        when the root had to be added.  A caller can treat ``False`` as worth
        logging, since it means the deploy layout is not the one expected.
    """
    if importlib.util.find_spec(_MARKER) is not None:
        return True
    root = str(REPO_ROOT)
    if root not in sys.path:
        sys.path.append(root)
    # False when the root still does not help, e.g. a genuinely absent package.
    return importlib.util.find_spec(_MARKER) is not None


ensure_repo_root_importable()
