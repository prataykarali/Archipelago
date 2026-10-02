"""Auto-split from monolith — blocks are verbatim."""
from __future__ import annotations

import json
import re
import secrets
import time
from pathlib import Path
from flask import jsonify, send_from_directory, request, redirect
from archipelago.inference import state as st


SHARES_DIR = Path(st.BASE_DIR) / "shares"


_SHARE_MAX_BYTES = 512 * 1024


_SHARE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,32}$")


@st.app.route("/api/share", methods=["POST"])
def create_share():
    """Persist a conversation snapshot and return a share id."""
    data = request.get_json(silent=True) or {}
    history = data.get("history")
    if not isinstance(history, list) or not history:
        return jsonify({"error": "history must be a non-empty list"}), 400
    clean = []
    for m in history[:200]:
        if not isinstance(m, dict):
            continue
        role = m.get("role")
        content = m.get("content")
        if role in ("user", "assistant") and isinstance(content, str) and content.strip():
            clean.append({"role": role, "content": content[:20000]})
    if not clean:
        return jsonify({"error": "no valid messages in history"}), 400
    payload = {
        "title": str(data.get("title") or "")[:120],
        "history": clean,
        "created_at": time.time(),
    }
    raw = json.dumps(payload, ensure_ascii=False)
    if len(raw.encode("utf-8")) > _SHARE_MAX_BYTES:
        return jsonify({"error": "conversation too large to share"}), 413
    share_id = secrets.token_urlsafe(9)
    SHARES_DIR.mkdir(exist_ok=True)
    (SHARES_DIR / f"{share_id}.json").write_text(raw, encoding="utf-8")
    return jsonify({"share_id": share_id, "url": f"/?share={share_id}"})


@st.app.route("/api/share/<share_id>", methods=["GET"])
def get_share(share_id):
    """Fetch a shared conversation snapshot by id."""
    if not _SHARE_ID_RE.match(share_id or ""):
        return jsonify({"error": "invalid share id"}), 400
    path = SHARES_DIR / f"{share_id}.json"
    if not path.is_file():
        return jsonify({"error": "share not found"}), 404
    try:
        return jsonify(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return jsonify({"error": "share unreadable"}), 500
