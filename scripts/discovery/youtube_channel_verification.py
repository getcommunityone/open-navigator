"""
Decide which discovered YouTube channels belong in ``bronze.bronze_jurisdiction_youtube``
(canonical verified) vs ``bronze_jurisdiction_youtube_candidates`` (audit only).
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from scripts.datasources.youtube.pattern_match_gate import (
    is_pattern_match_discovery,
    passes_pattern_match_gate,
)

# Default bar for canonical table (override via env in pilot runner).
DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE = 0.55

_JUNK_CHANNEL_TITLES = frozenset(
    s.lower()
    for s in (
        "home",
        "videos",
        "shorts",
        "live",
        "playlists",
        "community",
        "channels",
        "about",
    )
)

_TRUSTED_DISCOVERY_PREFIXES = (
    "website_search",
    "website_scrape",
    "civic_api",
    "localview",
    "verified_bronze_events_youtube",
    "events_catalog",
    "manual",
)

_CITY_GOVT_TITLE_RE = re.compile(r"\b(?:city|town|village|borough)\s+of\b", re.I)
_COUNTY_GOV_TITLE_SIGNALS = (
    "county commission",
    "county commissioners",
    "board of commissioners",
    "county board",
    "county government",
    " commissioners",
    "commissioners meeting",
)


def rejection_reason_for_channel(
    row: Mapping[str, Any],
    *,
    jurisdiction_type: str,
    jurisdiction_name: str,
    jurisdiction_state_code: str,
    jurisdiction_homepage: str,
    min_confidence: float = DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE,
) -> Optional[str]:
    """
    Return a short reason string when *row* must not enter the canonical table,
    or ``None`` when it qualifies.
    """
    if qualifies_for_bronze_jurisdiction_youtube(
        row,
        jurisdiction_type=jurisdiction_type,
        jurisdiction_name=jurisdiction_name,
        jurisdiction_state_code=jurisdiction_state_code,
        jurisdiction_homepage=jurisdiction_homepage,
        min_confidence=min_confidence,
    ):
        return None

    conf = float(row.get("official_meeting_confidence") or 0.0)
    method = str(row.get("discovery_method") or "").strip().lower()
    title = str(row.get("channel_title") or "").strip().lower()
    backlink = bool(row.get("back_links_to_jurisdiction_website"))

    if is_pattern_match_discovery(row):
        if not passes_pattern_match_gate(
            channel_title=str(row.get("channel_title") or ""),
            channel_description=str(row.get("channel_description") or ""),
            jurisdiction_name=jurisdiction_name,
            jurisdiction_state_code=jurisdiction_state_code,
            jurisdiction_homepage=jurisdiction_homepage or "",
            external_links=row.get("external_links"),
            backlinks_to_jurisdiction=backlink,
        ):
            return "pattern_match_gate_failed"
        if conf < min_confidence:
            return "pattern_match_low_confidence"

    if title in _JUNK_CHANNEL_TITLES and conf < min_confidence:
        return "junk_channel_title"

    if conf < min_confidence:
        return "low_official_confidence"

    if method.startswith("pattern_match") and not backlink:
        return "pattern_match_no_backlink"

    if jurisdiction_type == "county" and _looks_like_city_channel_for_county(
        row, jurisdiction_name=jurisdiction_name
    ):
        return "county_city_channel_mismatch"

    return "not_verified"


def qualifies_for_bronze_jurisdiction_youtube(
    row: Mapping[str, Any],
    *,
    jurisdiction_type: str,
    jurisdiction_name: str,
    jurisdiction_state_code: str,
    jurisdiction_homepage: str,
    min_confidence: float = DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE,
) -> bool:
    """True when a channel row should upsert into ``bronze.bronze_jurisdiction_youtube``."""
    conf = float(row.get("official_meeting_confidence") or 0.0)
    method = str(row.get("discovery_method") or "").strip().lower()
    title = str(row.get("channel_title") or "").strip().lower()
    backlink = bool(row.get("back_links_to_jurisdiction_website"))

    if conf < min_confidence:
        return False

    if title in _JUNK_CHANNEL_TITLES and not backlink and conf < 0.7:
        return False

    if is_pattern_match_discovery(row):
        if not passes_pattern_match_gate(
            channel_title=str(row.get("channel_title") or ""),
            channel_description=str(row.get("channel_description") or ""),
            jurisdiction_name=jurisdiction_name,
            jurisdiction_state_code=jurisdiction_state_code,
            jurisdiction_homepage=jurisdiction_homepage or "",
            external_links=row.get("external_links"),
            backlinks_to_jurisdiction=backlink,
        ):
            return False
        if not backlink and conf < 0.7:
            return False

    if jurisdiction_type == "county" and _looks_like_city_channel_for_county(
        row, jurisdiction_name=jurisdiction_name
    ):
        return False

    if any(method.startswith(p) for p in _TRUSTED_DISCOVERY_PREFIXES):
        return True

    if backlink:
        return True

    return conf >= 0.7 and not method.startswith("pattern_match")


def _county_name_token(jurisdiction_name: str) -> str:
    return jurisdiction_name.replace("County", "").replace("county", "").strip().lower()


def _has_county_gov_signal(blob: str, county_token: str) -> bool:
    if any(sig in blob for sig in _COUNTY_GOV_TITLE_SIGNALS):
        return True
    if county_token and re.search(rf"\b{re.escape(county_token)}\s+county\b", blob):
        return True
    if "county" in blob and county_token and county_token in blob:
        return True
    return False


def _looks_like_city_channel_for_county(
    row: Mapping[str, Any],
    *,
    jurisdiction_name: str,
) -> bool:
    """
    Reject municipal YouTube channels attached to a county jurisdiction.

    Catches ``City of Dothan AL`` on Houston County (seat city channel), not just
    ``@CityOfBaxley``-style handles.
    """
    title = str(row.get("channel_title") or "")
    desc = str(row.get("channel_description") or "")
    blob = f"{title} {desc}".lower()
    title_l = title.lower()
    county_token = _county_name_token(jurisdiction_name)

    if _CITY_GOVT_TITLE_RE.search(title_l):
        # Explicit municipal title wins; do not let description mention of
        # "Dallas County" / "Cullman County" in a city channel bio override.
        if _has_county_gov_signal(title_l, county_token):
            return False
        return True

    if _has_county_gov_signal(blob, county_token):
        return False

    return _looks_like_city_handle_for_county(row, jurisdiction_name=jurisdiction_name)


def _looks_like_city_handle_for_county(
    row: Mapping[str, Any],
    *,
    jurisdiction_name: str,
) -> bool:
    """Reject @CityOfSeat-style handles for counties when title lacks county signals."""
    url = str(row.get("youtube_channel_url") or row.get("channel_url") or "").lower()
    if "cityof" not in url and not url.rstrip("/").endswith("city"):
        return False

    title = str(row.get("channel_title") or "").lower()
    desc = str(row.get("channel_description") or "").lower()
    blob = f"{title} {desc}"
    county_token = _county_name_token(jurisdiction_name)
    if "county" in blob or "commission" in blob or "commissioners" in blob:
        return False
    if county_token and county_token in blob:
        return False
    return True


def canonical_source_from_row(row: Mapping[str, Any]) -> str:
    method = str(row.get("discovery_method") or row.get("source") or "").strip().lower()
    if method.startswith("civic"):
        return "pilot_civic_api"
    if "website" in method:
        return "pilot_website_search"
    if method.startswith("localview"):
        return "localview"
    if method.startswith("verified_bronze") or method.startswith("events_catalog"):
        return "events_catalog"
    if method.startswith("manual"):
        return "manual"
    if method.startswith("pattern_match"):
        return "pilot_pattern_match_verified"
    return method or "unknown"
