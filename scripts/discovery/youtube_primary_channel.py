"""
Pick one primary YouTube channel from discovery ``youtube_channels`` payloads.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def _channel_url(ch: Dict[str, Any]) -> str:
    return (
        str(ch.get("channel_url") or ch.get("youtube_channel_url") or "").strip()
    )


def youtube_channel_selection_confidence(ch: Dict[str, Any]) -> Optional[float]:
    """Prefer ``official_meeting_confidence``, then upstream ``confidence``."""
    for key in ("official_meeting_confidence", "confidence"):
        raw = ch.get(key)
        if raw is None:
            continue
        try:
            val = float(raw)
        except (TypeError, ValueError):
            continue
        if val >= 0.0:
            return val
    return None


def pick_primary_youtube_channel(
    youtube_channels: Optional[List[Dict[str, Any]]],
) -> Tuple[Optional[str], Optional[str], Optional[float]]:
    """
    Return ``(youtube_channel_url, selection_method, selection_confidence)``.

    Ranks by selection confidence, then ``video_count``, then ``subscriber_count``.
    """
    candidates: List[Dict[str, Any]] = []
    for ch in youtube_channels or []:
        if not isinstance(ch, dict):
            continue
        url = _channel_url(ch)
        if not url:
            continue
        candidates.append(ch)
    if not candidates:
        return None, None, None

    def sort_key(ch: Dict[str, Any]) -> Tuple[float, int, int, str]:
        conf = youtube_channel_selection_confidence(ch) or 0.0
        try:
            videos = int(ch.get("video_count") or 0)
        except (TypeError, ValueError):
            videos = 0
        try:
            subs = int(ch.get("subscriber_count") or 0)
        except (TypeError, ValueError):
            subs = 0
        return (conf, videos, subs, _channel_url(ch))

    best = max(candidates, key=sort_key)
    url = _channel_url(best) or None
    method = (
        str(
            best.get("discovery_method")
            or best.get("youtube_channel_selection_method")
            or ""
        ).strip()
        or None
    )
    conf = youtube_channel_selection_confidence(best)
    return url, method, conf
