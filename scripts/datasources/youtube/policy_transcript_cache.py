"""
Write YouTube captions under ``data/cache/gemini_transcript_policy`` (standard layout).

See ``scripts/gemini/transcript_cache_paths.py`` for
``{state}/{type}/{place_slug}_{geoid}/{channel_id}/01_transcripts/YYYY-MM-DD_<title>.json``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union

from scripts.gemini.transcript_cache_paths import (
    resolve_meeting_event_date,
    transcript_cache_path,
    transcripts_dir,
)


def apply_resolved_event_date(row: Dict[str, Any]) -> Dict[str, Any]:
    resolved = resolve_meeting_event_date(
        str(row.get("title") or ""),
        event_date=row.get("event_date"),
        published_at=row.get("published_at"),
    )
    if resolved:
        row["event_date"] = resolved
    return row

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_POLICY_CACHE_DIR = _REPO_ROOT / "data" / "cache" / "gemini_transcript_policy"


def policy_transcript_sidecar_path(main_path: Path) -> Path:
    """Sibling path for ``.caption_raw_data.json`` (``preserve_formatting`` export)."""
    stem = main_path.name
    if stem.endswith(".json"):
        stem = stem[: -len(".json")]
    return main_path.parent / f"{stem}.caption_raw_data.json"


def policy_transcript_sidecar_paths(main_path: Path) -> tuple[Path, Path]:
    """Backward-compatible alias: returns ``(raw_data sidecar, same path)``."""
    sidecar = policy_transcript_sidecar_path(main_path)
    return sidecar, sidecar


def write_policy_transcript_cache(
    cache_dir: Path,
    *,
    jurisdiction_id: str,
    state_code: str,
    row: Mapping[str, Any],
    yt: Mapping[str, Any],
    caption_raw_data: Optional[list] = None,
    jurisdiction_type: Optional[str] = None,
) -> Path:
    """
    Write main transcript JSON plus optional ``.caption_raw_data.json`` sidecar.

    ``row`` should include ``video_id``, ``title``, ``event_date``, ``channel_id``,
    ``video_url``, and ``jurisdiction_id``.
    """
    row_dict = apply_resolved_event_date(dict(row))
    st = (state_code or row_dict.get("state_code") or "").strip().upper()
    jtype = (jurisdiction_type or row_dict.get("jurisdiction_type") or "").strip() or None

    main_path = transcript_cache_path(
        cache_dir,
        jurisdiction_id,
        title=str(row_dict.get("title") or ""),
        event_date=row_dict.get("event_date"),
        state_code=st,
        jurisdiction_type=jtype,
        channel_id=str(row_dict.get("channel_id") or "").strip() or None,
        video_id=str(row_dict.get("video_id") or "").strip() or None,
    )
    main_path.parent.mkdir(parents=True, exist_ok=True)

    youtube_block = dict(yt)
    payload: Dict[str, Any] = {
        "video_id": row_dict.get("video_id"),
        "video_url": row_dict.get("video_url"),
        "title": row_dict.get("title"),
        "event_date": row_dict.get("event_date"),
        "jurisdiction_id": row_dict.get("jurisdiction_id") or jurisdiction_id,
        "state_code": st,
        "youtube": youtube_block,
        "segment_count": len(youtube_block.get("segments") or []),
        "transcript_chars": len(youtube_block.get("raw_text") or ""),
        "transcript_source": youtube_block.get("transcript_source"),
    }
    if caption_raw_data is not None:
        payload["caption_raw_data"] = caption_raw_data
        payload["caption_preserve_formatting"] = True

    main_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    # Raw caption snippets live only in the main JSON (`caption_raw_data` key).
    # Do not write a duplicate `.caption_raw_data.json` sidecar.

    return main_path


def resolve_policy_transcripts_dir(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
    create: bool = True,
) -> Path:
    """Absolute ``…/{channel_id}/01_transcripts`` (standard policy layout)."""
    folder = transcripts_dir(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
    )
    if create:
        folder.mkdir(parents=True, exist_ok=True)
    return folder.resolve()


__all__ = [
    "DEFAULT_POLICY_CACHE_DIR",
    "policy_transcript_sidecar_path",
    "policy_transcript_sidecar_paths",
    "resolve_policy_transcripts_dir",
    "write_policy_transcript_cache",
]
