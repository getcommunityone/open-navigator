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
    "board of commissioners",
    "council meeting",
    "public meeting",
    "public meetings",
    "official meetings",
    "official meeting",
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
    "town meetings",
    "boards and commissions meetings",
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

# Title-only: ``Houston County Commission``, ``Board of Commissioners``, etc.
_COMMISSION_IN_TITLE_RE = re.compile(
    r"\b(?:board\s+of\s+)?commission(?:ers|er)?s?\b",
    re.I,
)


def title_indicates_meeting_channel(channel_title: str) -> bool:
    """True when the channel title names a commission/board body (meeting channel)."""
    title = (channel_title or "").strip()
    if not title:
        return False
    return bool(_COMMISSION_IN_TITLE_RE.search(title))


def _blob(channel_title: str, channel_description: str) -> str:
    return f"{channel_title or ''} {channel_description or ''}".lower()


def has_meeting_purpose_signal(channel_title: str, channel_description: str) -> bool:
    """True when title/description focus on meetings (not generic ``government``)."""
    if title_indicates_meeting_channel(channel_title):
        return True
    text = _blob(channel_title, channel_description)
    if not text.strip():
        return False
    return any(sig in text for sig in _MEETING_PURPOSE_SIGNALS)


_NON_GOV_HOBBY_SIGNALS = (
    "filming trains",
    "if you like trains",
    "railroad",
    "steam engine",
    "big boy",
    "follow me on facebook",
    "follow the link below",
    "my store",
    "etsy.com",
    "my short videos",
    "adventures",
    "subscribers filming",
)

_PERSONAL_SOCIAL_HOSTS = (
    "facebook.com",
    "instagram.com",
    "etsy.com",
    "tiktok.com",
    "twitter.com",
    "x.com",
    "snapchat.com",
)

_COMMUNITY_PROMO_SIGNALS = (
    "get to know",
    "get to know our",
    "discover our county",
    "explore our county",
)

_NON_MEETING_LEISURE_SIGNALS = (
    "parades",
    "concerts",
    "formal balls",
    " pets",
    "pets,",
    " animals",
    "animals,",
    "festivals",
    "fireworks",
    "snapchat",
    "tiktok",
)


def _external_link_urls(external_links: object) -> list[str]:
    links: list[str] = []
    if isinstance(external_links, list):
        for item in external_links:
            if isinstance(item, str):
                links.append(item.lower())
            elif isinstance(item, dict):
                links.append(str(item.get("url") or "").lower())
    return links


def looks_like_community_promo_channel(
    channel_title: str,
    channel_description: str,
    *,
    external_links: object = None,
) -> bool:
    """
    Tourism / chamber-style regional promo channels (``Know Pickens``, etc.) that
    mention some government meetings alongside parades, pets, and social media.
    """
    text = _blob(channel_title, channel_description)
    if any(sig in text for sig in _COMMUNITY_PROMO_SIGNALS):
        return True

    leisure_hits = sum(1 for sig in _NON_MEETING_LEISURE_SIGNALS if sig in text)
    mentions_meetings = "government meeting" in text or "government meetings" in text
    if mentions_meetings and leisure_hits >= 2:
        return True

    title_l = (channel_title or "").strip().lower()
    if title_indicates_meeting_channel(channel_title):
        return False

    links = _external_link_urls(external_links)
    has_gov_link = any(".gov" in url for url in links)
    social_hits = sum(
        1 for url in links if url and any(host in url for host in _PERSONAL_SOCIAL_HOSTS)
    )
    bare_county_title = bool(re.match(r"^[a-z .'-]+county$", title_l))
    if bare_county_title and social_hits >= 2 and not has_gov_link and leisure_hits >= 1:
        return True

    return False


def has_government_channel_signal(
    channel_title: str,
    channel_description: str,
    *,
    jurisdiction_type: str = "",
    jurisdiction_name: str = "",
    external_links: object = None,
) -> bool:
    """True when title/description look like official or meeting-focused government media."""
    if looks_like_community_promo_channel(
        channel_title,
        channel_description,
        external_links=external_links,
    ):
        return False
    title = channel_title or ""
    desc = channel_description or ""
    text = _blob(title, desc)
    if not text.strip():
        return False
    if has_meeting_purpose_signal(title, desc):
        return True
    if any(sig in text for sig in _GENERAL_GOV_SIGNALS):
        return True
    if is_tv_public_channel(title, desc):
        return True

    jt = _norm_jurisdiction_type(jurisdiction_type)
    name_l = (jurisdiction_name or "").lower()
    if jt == "county":
        county_token = name_l.replace(" county", "").strip()
        if "county" in text and (not county_token or county_token in text):
            return True
        if any(
            sig in text
            for sig in (
                "county commission",
                "board of commissioners",
                "county board",
                "county government",
            )
        ):
            return True
    if jt == "municipality":
        if re.search(r"\b(city|town|village|borough)\s+of\b", (title or "").lower()):
            return True
        if any(
            sig in text
            for sig in ("city of ", "town of ", "village of ", "borough of ", "municipal")
        ):
            return True
    return False


def looks_like_non_government_channel(
    channel_title: str,
    channel_description: str,
    *,
    external_links: object = None,
) -> bool:
    """True for hobby/personal channels and regional tourism promo channels."""
    if looks_like_community_promo_channel(
        channel_title,
        channel_description,
        external_links=external_links,
    ):
        return True

    text = _blob(channel_title, channel_description)
    if any(sig in text for sig in _NON_GOV_HOBBY_SIGNALS):
        return True

    links: list[str] = _external_link_urls(external_links)
    has_personal_social = any(
        host in url for url in links for host in _PERSONAL_SOCIAL_HOSTS if url
    )
    has_gov_link = any(".gov" in url for url in links)
    if has_personal_social and not has_gov_link and not has_government_channel_signal(
        channel_title,
        channel_description,
        external_links=external_links,
    ):
        return True
    return False


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
    if jt in ("city", "town", "village", "borough", "place", "municipality", "township"):
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
    title_l = (title or "").lower()

    # Official ``Town/City of …`` channels with meeting wording beat generic TV access.
    if re.search(r"\b(city|town|village|borough)\s+of\b", title_l):
        jt = "municipality"
        if has_meeting_purpose_signal(title, desc):
            return "municipality-meeting"

    if is_tv_public_channel(title, desc):
        return "tv-public"

    if title_indicates_meeting_channel(title):
        if jt == "county":
            return "county-meeting"
        if jt == "municipality":
            return "municipality-meeting"
        if jt != "unknown":
            return f"{jt}-meeting"

    # Title says Town/City of … — classify as local government even when the scrape
    # target jurisdiction was a county (coterminous county/town like Nantucket MA).
    if re.search(r"\b(city|town|village|borough)\s+of\b", title_l):
        jt = "municipality"

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
