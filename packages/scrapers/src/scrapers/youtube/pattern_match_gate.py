"""
Strict acceptance rules for ``pattern_match`` YouTube handle probes.

Generic handles like ``@CalhounCounty`` collide across states; we only keep a
pattern-match candidate when enrichment shows all of:

- Government website back-link (About page links or description mentions host)
- Meeting / council signal in channel title or description
- Correct state (USPS code or state name in title or description)
"""

from __future__ import annotations

import re
from typing import Any, Sequence

from scripts.datasources.jurisdiction_pilot.youtube_channel_enrich import (
    _GOV_TITLE_KEYWORDS,
    _MEETING_TITLE_KEYWORDS,
    _jurisdiction_name_tokens,
    back_links_to,
)

# Probe-only score stored on raw discovery rows (not used for primary selection).
PATTERN_MATCH_PROBE_CONFIDENCE = 0.1

# Minimum ``official_meeting_confidence`` to promote pattern_match as primary.
PATTERN_MATCH_PRIMARY_MIN_OFFICIAL_CONFIDENCE = 0.55

_USPS_TO_STATE_NAME: dict[str, str] = {
    "AL": "alabama",
    "AK": "alaska",
    "AZ": "arizona",
    "AR": "arkansas",
    "CA": "california",
    "CO": "colorado",
    "CT": "connecticut",
    "DE": "delaware",
    "FL": "florida",
    "GA": "georgia",
    "HI": "hawaii",
    "ID": "idaho",
    "IL": "illinois",
    "IN": "indiana",
    "IA": "iowa",
    "KS": "kansas",
    "KY": "kentucky",
    "LA": "louisiana",
    "ME": "maine",
    "MD": "maryland",
    "MA": "massachusetts",
    "MI": "michigan",
    "MN": "minnesota",
    "MS": "mississippi",
    "MO": "missouri",
    "MT": "montana",
    "NE": "nebraska",
    "NV": "nevada",
    "NH": "new hampshire",
    "NJ": "new jersey",
    "NM": "new mexico",
    "NY": "new york",
    "NC": "north carolina",
    "ND": "north dakota",
    "OH": "ohio",
    "OK": "oklahoma",
    "OR": "oregon",
    "PA": "pennsylvania",
    "RI": "rhode island",
    "SC": "south carolina",
    "SD": "south dakota",
    "TN": "tennessee",
    "TX": "texas",
    "UT": "utah",
    "VT": "vermont",
    "VA": "virginia",
    "WA": "washington",
    "WV": "west virginia",
    "WI": "wisconsin",
    "WY": "wyoming",
    "DC": "district of columbia",
}

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


def references_state(text: str, state_code: str) -> bool:
    """True when title/description clearly names the jurisdiction's state."""
    state = (state_code or "").strip().upper()
    if not state or len(state) != 2:
        return False
    blob = (text or "").lower()
    if not blob:
        return False
    # USPS in prose: ", TX" / " TX " / "(TX)"
    if re.search(rf",\s*{re.escape(state.lower())}\b", blob):
        return True
    if re.search(rf"\b{re.escape(state.lower())}\b", blob):
        return True
    if re.search(rf"\({re.escape(state)}\)", blob, re.IGNORECASE):
        return True
    full = _USPS_TO_STATE_NAME.get(state)
    if full and full in blob:
        return True
    return False


def has_meeting_signal(channel_title: str, channel_description: str) -> bool:
    """Explicit government/meeting wording in title or About description."""
    title_l = (channel_title or "").strip().lower()
    if title_l in _JUNK_CHANNEL_TITLES:
        title_l = ""
    combined = f"{title_l} {(channel_description or '').lower()}"
    if not combined.strip():
        return False
    keywords = _MEETING_TITLE_KEYWORDS + _GOV_TITLE_KEYWORDS
    return any(kw in combined for kw in keywords)


def jurisdiction_name_plausible(
    channel_title: str,
    channel_description: str,
    jurisdiction_name: str,
) -> bool:
    """Require at least one non-generic jurisdiction name token in title or description."""
    tokens = _jurisdiction_name_tokens(jurisdiction_name)
    if not tokens:
        return True
    title_l = (channel_title or "").strip().lower()
    if title_l in _JUNK_CHANNEL_TITLES:
        title_l = ""
    blob = f"{title_l} {(channel_description or '').lower()}"
    return any(tok in blob for tok in tokens)


def passes_pattern_match_gate(
    *,
    channel_title: str,
    channel_description: str,
    jurisdiction_name: str,
    jurisdiction_state_code: str,
    jurisdiction_homepage: str,
    external_links: Sequence[str] | None = None,
    backlinks_to_jurisdiction: bool | None = None,
) -> bool:
    """
    Return True only when this pattern-matched channel is plausibly the
    jurisdiction's official meeting channel (not a same-name county in another state).
    """
    homepage = (jurisdiction_homepage or "").strip()
    if not homepage:
        return False

    links = list(external_links or [])
    if backlinks_to_jurisdiction is None:
        backlinks = back_links_to(
            links,
            homepage,
            description_text=channel_description or "",
        )
    else:
        backlinks = bool(backlinks_to_jurisdiction)

    if not backlinks:
        return False

    text = f"{channel_title or ''} {channel_description or ''}"
    if not references_state(text, jurisdiction_state_code):
        return False

    if not has_meeting_signal(channel_title, channel_description):
        return False

    if not jurisdiction_name_plausible(
        channel_title, channel_description, jurisdiction_name
    ):
        return False

    return True


def is_pattern_match_discovery(channel: dict[str, Any]) -> bool:
    method = str(
        channel.get("discovery_method")
        or channel.get("youtube_channel_selection_method")
        or ""
    ).strip().lower()
    return method.startswith("pattern_match")
