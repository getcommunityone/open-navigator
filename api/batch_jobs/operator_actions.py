"""Open human-required pipeline actions for the admin UI (#712).

Reads ``data/cache/batch_jobs/action_required.json`` (written by Discover) and
``action_dismissals.json`` (manual Mark resolved). Template catalog matches
``web_docs/docs/development/operator-action-templates.md``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from core_lib.paths import repo_root

_REPO = repo_root(__file__)
BATCH_JOBS_DIR = _REPO / "data" / "cache" / "batch_jobs"
ACTION_REQUIRED_JSON = BATCH_JOBS_DIR / "action_required.json"
ACTION_REQUIRED_MD = BATCH_JOBS_DIR / "ACTION_REQUIRED.md"
DISMISSALS_JSON = BATCH_JOBS_DIR / "action_dismissals.json"

TEMPLATES: list[dict[str, Any]] = [
    {
        "id": "youtube_api_quota",
        "title": "YouTube Data API quota",
        "summary": "Wait for daily reset or switch YOUTUBE_API_KEY.",
        "docs_path": "/docs/development/operator-action-templates#youtube-api-quota",
        "steps": [
            "Open GCP Quotas for YouTube Data API v3 for the project that owns YOUTUBE_API_KEY.",
            "Confirm the daily quota is at the cap (often 10,000 units).",
            "Wait for ~midnight Pacific reset, or put a key with remaining quota in .env, or request an increase.",
            "Re-run Discover for states that rejected with uploads 403.",
        ],
    },
    {
        "id": "vpn_down",
        "title": "Surfshark / VPN down",
        "summary": "Connect Surfshark full tunnel, then resume YouTube stages.",
        "docs_path": "/docs/development/operator-action-templates#vpn-down",
        "steps": [
            "On the Windows host, connect Surfshark (full tunnel).",
            "Confirm: .venv/bin/python -m scrapers.youtube.vpn_guard shows vpn_up.",
            "Let Discover wait/resume, or re-kick the stage from Batch Jobs.",
        ],
    },
    {
        "id": "missing_youtube_api_key",
        "title": "Missing YOUTUBE_API_KEY",
        "summary": "Set YOUTUBE_API_KEY in .env and restart.",
        "docs_path": "/docs/development/operator-action-templates#missing-youtube-api-key",
        "steps": [
            "Set a non-empty YOUTUBE_API_KEY in .env (YouTube Data API v3 enabled).",
            "Restart the API and any long-running Discover process.",
            "Re-run Discover for affected states.",
        ],
    },
]


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_dismissals(path: Path = DISMISSALS_JSON) -> dict[str, dict[str, Any]]:
    raw = _read_json(path)
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for code, meta in raw.items():
        if isinstance(meta, dict) and meta.get("fingerprint"):
            out[str(code)] = meta
    return out


def load_action_required(path: Path = ACTION_REQUIRED_JSON) -> dict[str, Any]:
    raw = _read_json(path)
    if isinstance(raw, dict) and isinstance(raw.get("actions"), list):
        return raw
    return {
        "generated_at": None,
        "stamp": None,
        "states": [],
        "actions": [],
        "source": "missing",
    }


def list_open_actions(
    *,
    action_path: Path = ACTION_REQUIRED_JSON,
    dismissals_path: Path = DISMISSALS_JSON,
) -> dict[str, Any]:
    """Open actions minus dismissals whose fingerprint still matches."""
    payload = load_action_required(action_path)
    dismissals = load_dismissals(dismissals_path)
    open_rows: list[dict[str, Any]] = []
    for row in payload.get("actions") or []:
        if not isinstance(row, dict):
            continue
        code = str(row.get("code") or "").strip()
        if not code:
            continue
        fp = str(row.get("fingerprint") or "").strip()
        dismissed = dismissals.get(code) or {}
        if fp and str(dismissed.get("fingerprint") or "") == fp:
            continue
        open_rows.append(
            {
                "code": code,
                "title": row.get("title") or code,
                "count": int(row.get("count") or 0),
                "examples": list(row.get("examples") or [])[:12],
                "states": list(row.get("states") or payload.get("states") or []),
                "fingerprint": fp,
                "template_id": row.get("template_id") or code,
                "first_seen_at": row.get("first_seen_at"),
                "detail": row.get("detail") or "",
            }
        )
    source = "action_required.json" if action_path.is_file() else "missing"
    return {
        "generated_at": payload.get("generated_at"),
        "source": source,
        "stamp": payload.get("stamp"),
        "open": open_rows,
        "templates": list(TEMPLATES),
    }


def dismiss_action(
    code: str,
    *,
    fingerprint: Optional[str] = None,
    action_path: Path = ACTION_REQUIRED_JSON,
    dismissals_path: Path = DISMISSALS_JSON,
) -> dict[str, Any]:
    """Record a manual dismiss for ``code`` at the given (or current) fingerprint."""
    code_n = (code or "").strip()
    if not code_n:
        raise ValueError("code is required")
    payload = load_action_required(action_path)
    current_fp = ""
    for row in payload.get("actions") or []:
        if isinstance(row, dict) and str(row.get("code") or "") == code_n:
            current_fp = str(row.get("fingerprint") or "")
            break
    fp = (fingerprint or current_fp or "").strip()
    if not fp:
        raise ValueError(f"no open fingerprint for code={code_n}")
    dismissals = load_dismissals(dismissals_path)
    dismissals[code_n] = {
        "fingerprint": fp,
        "dismissed_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_json(dismissals_path, dismissals)
    return {"dismissed": True, "code": code_n, "fingerprint": fp}
