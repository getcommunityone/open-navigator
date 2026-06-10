"""
Decide which discovered YouTube channels belong in ``intermediate.int_events_channels``
(golden verified county/municipality) vs ``int_events_channels_candidates`` (audit only).
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from scrapers.youtube.pattern_match_gate import (
    has_meeting_signal,
    is_pattern_match_discovery,
    passes_pattern_match_gate,
)

# NOTE: ``scripts.discovery.youtube_channel_purpose`` is a KEEP-in-scripts discovery
# util (not part of this port round). It is import-clean (depends only on
# ``scrapers.*``), but a packages/ module must not carry a top-level ``import
# scripts.*``, so the symbols below are imported lazily inside each consuming
# function. FOLLOW-UP: port ``youtube_channel_purpose`` into ``scrapers.discovery``
# and replace these function-local imports with a single relative import.

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
    "manual",
)

# Channel URL extracted from the jurisdiction's own website (footer, /youtube, BOC page, etc.).
_OFFICIAL_WEBSITE_DISCOVERY_PREFIXES = (
    "website_search",
    "website_scrape",
)


def is_official_website_discovery(method: str) -> bool:
    """True when the channel link was found on the jurisdiction website crawl."""
    m = (method or "").strip().lower()
    return any(m.startswith(p) for p in _OFFICIAL_WEBSITE_DISCOVERY_PREFIXES)

_CITY_GOVT_TITLE_RE = re.compile(r"\b(?:city|town|village|borough)\s+of\b", re.I)
_CITY_SUFFIX_TITLE_RE = re.compile(r"\b[a-z0-9][\w.'-]*\s+city\b", re.I)
_TOWN_OF_TITLE_RE = re.compile(r"\btown\s+of\b", re.I)
_COMPACT_CITYOF_TITLE_RE = re.compile(r"^cityof[a-z0-9_]+$", re.I)
_LOCAL_PLACE_KIND_RE = re.compile(r"\b(?:township|borough|village)\b", re.I)


def is_localview_discovery(method: str) -> bool:
    return "localview" in (method or "").strip().lower()


def is_events_catalog_auto_discovery(method: str) -> bool:
    """Auto-picked from bronze_event_youtube / repair script — not human-verified."""
    m = (method or "").strip().lower()
    return "verified_bronze" in m or m.startswith("events_catalog")


_STRONG_GOV_CHANNEL_SIGNALS = (
    "commission",
    "council",
    "board of",
    "select board",
    "selectmen",
    "supervisors",
    "government",
    "official channel",
    "official youtube",
    "gov tv",
    "government tv",
    "public access",
    "public meeting",
    "meetings",
    "granicus",
    "legistar",
)


def _has_strong_gov_channel_signal(
    channel_title: str,
    channel_description: str,
    *,
    jurisdiction_type: str = "",
    jurisdiction_name: str = "",
) -> bool:
    """Stricter than ``has_government_channel_signal`` — bare ``Franklin County`` is not enough."""
    from scripts.discovery.youtube_channel_purpose import (  # noqa: E402
        has_meeting_purpose_signal,
        title_indicates_meeting_channel,
    )

    title = channel_title or ""
    desc = channel_description or ""
    if title_indicates_meeting_channel(title):
        return True
    text = f"{title} {desc}".lower()
    if has_meeting_purpose_signal(title, desc):
        return True
    if any(sig in text for sig in _STRONG_GOV_CHANNEL_SIGNALS):
        return True
    return False


def events_catalog_auto_confidence_cap(method: str, requested: float) -> float:
    """Do not treat video-count auto-picks as high-confidence official channels."""
    if is_events_catalog_auto_discovery(method):
        return min(requested, 0.55)
    return requested


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
    from scripts.discovery.youtube_channel_purpose import (  # noqa: E402
        classify_channel_purpose_from_row,
        has_government_channel_signal,
        has_meeting_purpose_signal,
        looks_like_non_government_channel,
        min_confidence_for_purpose,
        purpose_requires_explicit_meeting,
    )

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

    if looks_like_non_government_channel(
        str(row.get("channel_title") or ""),
        str(row.get("channel_description") or ""),
        external_links=row.get("external_links"),
    ):
        return "non_government_channel"

    purpose = classify_channel_purpose_from_row(row, jurisdiction_type=jurisdiction_type)
    purpose_min = min_confidence_for_purpose(purpose)
    website_linked = is_official_website_discovery(method)
    # Channel About → .gov, or .gov → channel: trust enrichment floors (≥0.85).
    effective_min = (
        min_confidence
        if (website_linked or backlink)
        else max(min_confidence, purpose_min)
    )
    if conf < effective_min:
        return "channel_purpose_low_confidence"

    if purpose_requires_explicit_meeting(purpose) and not website_linked and not backlink:
        if not has_meeting_purpose_signal(
            str(row.get("channel_title") or ""),
            str(row.get("channel_description") or ""),
        ):
            return "channel_purpose_not_meeting_focused"

    if is_localview_discovery(method) and purpose == "unknown" and not backlink:
        if not has_government_channel_signal(
            str(row.get("channel_title") or ""),
            str(row.get("channel_description") or ""),
            jurisdiction_type=jurisdiction_type,
            jurisdiction_name=jurisdiction_name,
            external_links=row.get("external_links"),
        ):
            return "localview_unknown_no_government_signal"

    if is_events_catalog_auto_discovery(method):
        if not (
            backlink
            or _has_strong_gov_channel_signal(
                str(row.get("channel_title") or ""),
                str(row.get("channel_description") or ""),
                jurisdiction_type=jurisdiction_type,
                jurisdiction_name=jurisdiction_name,
            )
        ):
            return "events_catalog_weak_signal"

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
    """True when a channel row should upsert into ``intermediate.int_events_channels``."""
    from scripts.discovery.youtube_channel_purpose import (  # noqa: E402
        classify_channel_purpose_from_row,
        has_government_channel_signal,
        has_meeting_purpose_signal,
        looks_like_non_government_channel,
        min_confidence_for_purpose,
        purpose_requires_explicit_meeting,
    )

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

    if looks_like_non_government_channel(
        str(row.get("channel_title") or ""),
        str(row.get("channel_description") or ""),
        external_links=row.get("external_links"),
    ):
        return False

    purpose = classify_channel_purpose_from_row(row, jurisdiction_type=jurisdiction_type)
    purpose_min = min_confidence_for_purpose(purpose)
    website_linked = is_official_website_discovery(method)
    effective_min = (
        min_confidence
        if (website_linked or backlink)
        else max(min_confidence, purpose_min)
    )
    if conf < effective_min:
        return False

    if purpose_requires_explicit_meeting(purpose) and not website_linked and not backlink:
        if not has_meeting_purpose_signal(
            str(row.get("channel_title") or ""),
            str(row.get("channel_description") or ""),
        ):
            return False
        if purpose == "tv-public" and not backlink:
            return False

    if is_localview_discovery(method) and purpose == "unknown" and not backlink:
        if not has_government_channel_signal(
            str(row.get("channel_title") or ""),
            str(row.get("channel_description") or ""),
            jurisdiction_type=jurisdiction_type,
            jurisdiction_name=jurisdiction_name,
            external_links=row.get("external_links"),
        ):
            return False

    if is_events_catalog_auto_discovery(method):
        if not (
            backlink
            or _has_strong_gov_channel_signal(
                str(row.get("channel_title") or ""),
                str(row.get("channel_description") or ""),
                jurisdiction_type=jurisdiction_type,
                jurisdiction_name=jurisdiction_name,
            )
        ):
            return False

    if is_localview_discovery(method):
        return True

    if any(method.startswith(p) for p in _TRUSTED_DISCOVERY_PREFIXES):
        return True

    if backlink:
        return True

    return conf >= 0.7 and not method.startswith("pattern_match")


def _county_name_token(jurisdiction_name: str) -> str:
    return jurisdiction_name.replace("County", "").replace("county", "").strip().lower()


def _county_name_appears_as_county_reference(text: str, county_token: str) -> bool:
    """
    True when ``county_token`` is a county reference, not merely a substring of
    ``cityofcovington``-style municipal handles.
    """
    if not county_token:
        return False
    t = (text or "").lower()
    if re.search(rf"\b{re.escape(county_token)}\s+county\b", t):
        return True
    if re.search(rf"\bcounty\s+of\s+{re.escape(county_token)}\b", t):
        return True
    if "county" not in t:
        return False
    compact = re.sub(r"[^a-z0-9]+", "", t)
    if county_token in compact and re.search(rf"cityof{re.escape(county_token)}", compact):
        remainder = compact.replace(f"cityof{county_token}", "", 1)
        if county_token not in remainder:
            return False
    return bool(re.search(rf"\b{re.escape(county_token)}\b", t))


def _title_is_compact_cityof_handle(title: str) -> bool:
    compact = re.sub(r"[^a-z0-9_]+", "", (title or "").strip().lower())
    return bool(_COMPACT_CITYOF_TITLE_RE.match(compact))


def _has_county_gov_signal(blob: str, county_token: str) -> bool:
    if any(sig in blob for sig in _COUNTY_GOV_TITLE_SIGNALS):
        return True
    return _county_name_appears_as_county_reference(blob, county_token)


def _title_indicates_local_place_government(title: str) -> bool:
    """True for ``AbingtonTownship``, ``Town of …``, ``Foo borough``, etc."""
    title_l = (title or "").strip().lower()
    if not title_l:
        return False
    compact = re.sub(r"[^a-z0-9]+", "", title_l)
    if "township" in compact:
        return True
    if _LOCAL_PLACE_KIND_RE.search(title_l):
        return True
    if _CITY_SUFFIX_TITLE_RE.search(title_l):
        return True
    if _CITY_GOVT_TITLE_RE.search(title_l):
        return True
    return False


def _title_indicates_township_or_borough(title: str) -> bool:
    """``AbingtonTownship``, ``Foo Township``, ``X borough`` — not county bodies."""
    title_l = (title or "").lower()
    compact = re.sub(r"[^a-z0-9]+", "", title_l)
    return "township" in compact or bool(re.search(r"\bborough\b", title_l))


def _looks_like_city_channel_for_county(
    row: Mapping[str, Any],
    *,
    jurisdiction_name: str,
) -> bool:
    """
    Reject municipal/township YouTube channels attached to a county jurisdiction.

    Catches ``City of Dothan AL`` on Houston County (seat city channel), not just
    ``@CityOfBaxley``-style handles. PA townships often say ``Board of Commissioners``
    in the description — title-level township/borough signals win over that.
    """
    from scripts.discovery.youtube_channel_purpose import (  # noqa: E402
        is_tv_public_channel,
    )

    title = str(row.get("channel_title") or "")
    desc = str(row.get("channel_description") or "")
    blob = f"{title} {desc}".lower()
    title_l = title.lower()
    county_token = _county_name_token(jurisdiction_name)

    if is_tv_public_channel(title, desc):
        return False

    if _title_is_compact_cityof_handle(title):
        if _has_county_gov_signal(title_l, county_token):
            return False
        return True

    if _CITY_GOVT_TITLE_RE.search(title_l):
        # Explicit municipal title wins; do not let description mention of
        # "Dallas County" / "Cullman County" in a city channel bio override.
        if _has_county_gov_signal(title_l, county_token):
            return False
        return True

    if _CITY_SUFFIX_TITLE_RE.search(title_l):
        if _has_county_gov_signal(title_l, county_token):
            return False
        return True

    if re.search(r"\bcity council\b", blob):
        if _has_county_gov_signal(title_l, county_token):
            return False
        return True

    if _title_indicates_township_or_borough(title):
        if _has_county_gov_signal(title_l, county_token):
            return False
        return True

    if _TOWN_OF_TITLE_RE.search(title_l):
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
    if _title_is_compact_cityof_handle(title):
        return not _has_county_gov_signal(title, county_token)
    if "county" in blob or "commission" in blob or "commissioners" in blob:
        return False
    if _county_name_appears_as_county_reference(blob, county_token):
        return False
    return True


def canonical_source_from_row(row: Mapping[str, Any]) -> str:
    method = str(row.get("discovery_method") or row.get("source") or "").strip().lower()
    if method.startswith("civic"):
        return "pilot_civic_api"
    if "website" in method:
        return "pilot_website_search"
    if method.startswith("localview") or "localview" in method:
        return "localview"
    if method.startswith("verified_bronze") or method.startswith("events_catalog"):
        return "events_catalog"
    if method.startswith("manual"):
        return "manual"
    if method.startswith("pattern_match"):
        return "pilot_pattern_match_verified"
    return method or "unknown"
