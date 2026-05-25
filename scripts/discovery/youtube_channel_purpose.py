"""
Classify jurisdiction YouTube channels by meeting focus.

Tags:
- ``county-meeting`` / ``municipality-meeting`` — commission/council meeting channels
- ``county-general`` / ``municipality-general`` — broader government PR/news channels
- ``tv-public`` — government access / cable TV / ``* TV`` channels (mixed content)
- ``unknown`` — insufficient signal
"""

from __future__ import annotations

import re
from typing import Mapping, Optional

# Strong meeting-only signals (stricter than generic ``has_meeting_signal``).
_MEETING_PURPOSE_SIGNALS = (
    "commission meeting",
    "board meeting",
    "council meeting",
    "public meeting",
    "public meetings",
    "meeting recording",
    "meetings streamed",
    "meeting livestream",
    "livestream of",
    "live stream of",
    "board of commissioners meeting",
    "county board meeting",
    "county commission meeting",
    "broadcast public meeting",
    "broadcast public meetings",
    "to broadcast public meetings",
    "host recordings and livestreams",
    "recordings and livestreams of",
    "recordings of local government meetings",
    "county government meetings",
    "government meetings",
    "streamed on this channel are",
    "meetings and events for",
)

_TV_PUBLIC_SIGNALS = (
    "public access",
    "government access",
    "community television",
    "local television",
    "local cable",
    "cable channel",
    "cable tv",
    "access channel",
    "access tv",
    "gov tv",
    "government tv",
    "city tv",
    "county tv",
    "media center",
    "government programming",
    "governement tv",
)

_GENERAL_GOV_SIGNALS = (
    "county government",
    "municipal government",
    "city government",
    "town government",
    "government channel",
    "official youtube channel for the",
    "official youtube page for",
    "services, programs and events",
    "news and events",
    "departments and",
    "community initiatives",
    "stay up-to-date with the latest news",
    "video portal",
)

_TV_TITLE_RE = re.compile(
    r"(?:"
    r"\btv\b|television|access|"
    r"gov(?:ernment)?\s+tv|city\s+tv|county\s+tv"
    r")",
    re.I,
)


def _blob(channel_title: str, channel_description: str) -> str:
    return f"{channel_title or ''} {channel_description or ''}".lower()


def has_meeting_purpose_signal(channel_title: str, channel_description: str) -> bool:
    """True when title/description focus on meetings (not generic ``government``)."""
    text = _blob(channel_title, channel_description)
    if not text.strip():
        return False
    return any(sig in text for sig in _MEETING_PURPOSE_SIGNALS)


def is_tv_public_channel(channel_title: str, channel_description: str) -> bool:
    title = (channel_title or "").strip()
    title_l = title.lower()
    text = _blob(channel_title, channel_description)

    if any(sig in text for sig in _TV_PUBLIC_SIGNALS):
        return True
    if re.search(r"\btv\s*$", title_l):
        return True
    if _TV_TITLE_RE.search(title_l):
        return True
    if re.search(r"\btv\b", title_l) and any(
        w in text for w in ("news", "events", "access", "broadcast", "programming", "cable")
    ):
        return True
    return False


def _norm_jurisdiction_type(jurisdiction_type: str) -> str:
    jt = (jurisdiction_type or "").strip().lower()
    if jt in ("city", "town", "village", "borough", "place", "municipality"):
        return "municipality"
    if jt == "county":
        return "county"
    return jt or "unknown"


def classify_channel_purpose(
    *,
    channel_title: str,
    channel_description: str,
    jurisdiction_type: str,
) -> str:
    """
    Return ``county-meeting``, ``county-general``, ``municipality-meeting``,
    ``municipality-general``, ``tv-public``, or ``unknown``.
    """
    jt = _norm_jurisdiction_type(jurisdiction_type)
    title = channel_title or ""
    desc = channel_description or ""
    text = _blob(title, desc)

    if is_tv_public_channel(title, desc):
        return "tv-public"

    if jt == "county":
        if has_meeting_purpose_signal(title, desc):
            return "county-meeting"
        if "county" in text or any(sig in text for sig in _GENERAL_GOV_SIGNALS):
            return "county-general"
        return "unknown"

    if jt == "municipality":
        if has_meeting_purpose_signal(title, desc):
            return "municipality-meeting"
        if any(
            sig in text
            for sig in (
                "city of ",
                "town of ",
                "village of ",
                "borough of ",
                "municipal government",
                "city government",
            )
        ) or any(sig in text for sig in _GENERAL_GOV_SIGNALS):
            return "municipality-general"
        return "unknown"

    if has_meeting_purpose_signal(title, desc):
        return f"{jt}-meeting" if jt != "unknown" else "unknown"
    return "unknown"


def classify_channel_purpose_from_row(
    row: Mapping[str, object],
    *,
    jurisdiction_type: str,
) -> str:
    existing = str(row.get("channel_purpose") or "").strip()
    if existing:
        return existing
    return classify_channel_purpose(
        channel_title=str(row.get("channel_title") or ""),
        channel_description=str(row.get("channel_description") or ""),
        jurisdiction_type=jurisdiction_type,
    )


# Minimum official_meeting_confidence for canonical table by purpose.
PURPOSE_MIN_OFFICIAL_CONFIDENCE: dict[str, float] = {
    "county-meeting": 0.55,
    "municipality-meeting": 0.55,
    "county-general": 0.75,
    "municipality-general": 0.75,
    "tv-public": 0.85,
    "unknown": 0.70,
}

# Purposes that require explicit meeting wording (not just ``government``).
STRICT_MEETING_PURPOSES = frozenset(
    {
        "county-general",
        "municipality-general",
        "tv-public",
    }
)

# Only these may become primary meeting channels.
MEETING_PRIMARY_PURPOSES = frozenset(
    {
        "county-meeting",
        "municipality-meeting",
    }
)


def min_confidence_for_purpose(channel_purpose: str) -> float:
    return PURPOSE_MIN_OFFICIAL_CONFIDENCE.get(
        (channel_purpose or "").strip().lower(),
        PURPOSE_MIN_OFFICIAL_CONFIDENCE["unknown"],
    )


def purpose_requires_explicit_meeting(channel_purpose: str) -> bool:
    return (channel_purpose or "").strip().lower() in STRICT_MEETING_PURPOSES


def is_meeting_primary_purpose(channel_purpose: str) -> bool:
    return (channel_purpose or "").strip().lower() in MEETING_PRIMARY_PURPOSES
