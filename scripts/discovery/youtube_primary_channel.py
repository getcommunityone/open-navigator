"""
Pick one primary YouTube channel from discovery ``youtube_channels`` payloads.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from scripts.discovery.youtube_channel_purpose import is_meeting_primary_purpose
from scrapers.youtube.pattern_match_gate import (
    PATTERN_MATCH_PRIMARY_MIN_OFFICIAL_CONFIDENCE,
    is_pattern_match_discovery,
)


def _channel_url(ch: Dict[str, Any]) -> str:
    return (
        str(ch.get("channel_url") or ch.get("youtube_channel_url") or "").strip()
    )


def _discovery_method_priority(method: Optional[str]) -> int:
    """Higher = prefer when picking the primary county/city channel."""
    m = (method or "").strip().lower()
    if "website_scrape" in m:
        return 4
    if m.startswith("pattern_match"):
        return 0
    if "domain_search" in m:
        return 2
    if m == "youtube_api" or m.startswith("youtube_api"):
        return 1
    return 0


def youtube_channel_selection_confidence(ch: Dict[str, Any]) -> Optional[float]:
    """Official-channel score from enrichment (0.0–1.0). Ignores legacy ``confidence`` keys."""
    raw = ch.get("official_meeting_confidence")
    if raw is None:
        return None
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return None
    return val if val >= 0.0 else None


def _promotable_for_primary(ch: Dict[str, Any]) -> bool:
    """Exclude weak ``pattern_match`` rows and non-meeting channel purposes."""
    purpose = str(ch.get("channel_purpose") or "").strip().lower()
    if purpose and not is_meeting_primary_purpose(purpose):
        return False
    if not is_pattern_match_discovery(ch):
        return True
    if not ch.get("back_links_to_jurisdiction_website"):
        return False
    conf = youtube_channel_selection_confidence(ch)
    if conf is None or conf < PATTERN_MATCH_PRIMARY_MIN_OFFICIAL_CONFIDENCE:
        return False
    return True


def pick_primary_youtube_channel(
    youtube_channels: Optional[List[Dict[str, Any]]],
) -> Tuple[Optional[str], Optional[str], Optional[float]]:
    """
    Return ``(youtube_channel_url, selection_method, selection_confidence)``.

    Ranks by ``official_meeting_confidence``, then discovery-method priority,
    then ``video_count`` / ``subscriber_count``.
    """
    candidates: List[Dict[str, Any]] = []
    for ch in youtube_channels or []:
        if not isinstance(ch, dict):
            continue
        url = _channel_url(ch)
        if not url:
            continue
        candidates.append(ch)
    candidates = [ch for ch in candidates if _promotable_for_primary(ch)]
    if not candidates:
        return None, None, None

    def sort_key(ch: Dict[str, Any]) -> Tuple[int, float, int, int, str]:
        method = str(ch.get("discovery_method") or ch.get("youtube_channel_selection_method") or "")
        conf = youtube_channel_selection_confidence(ch) or 0.0
        try:
            videos = int(ch.get("video_count") or 0)
        except (TypeError, ValueError):
            videos = 0
        try:
            subs = int(ch.get("subscriber_count") or 0)
        except (TypeError, ValueError):
            subs = 0
        return (
            _discovery_method_priority(method),
            conf,
            videos,
            subs,
            _channel_url(ch),
        )

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
