"""
Resolve municipal YouTube channels incorrectly attached to county jurisdictions.

Used by ``remap_county_city_youtube_channels.py`` to move rows to the correct
``municipality`` or drop county duplicates when the city already has the channel.
"""

from __future__ import annotations

import json
import re
from typing import Any, Mapping, Optional

from scripts.discovery.youtube_channel_verification import (
    _looks_like_city_channel_for_county,
)
from scripts.jurisdictions.jurisdiction_id import normalize_place_label_for_slug

_CITY_OF_TITLE_RE = re.compile(
    r"\b(?:city|town|village|borough)\s+of\s+(.+)",
    re.I,
)
_TITLE_SUFFIX_RE = re.compile(
    r",?\s*(?:"
    r"al|ga|in|ma|wa|wi|"
    r"alabama|georgia|indiana|massachusetts|washington|wisconsin|"
    r"government|gov|official|usa|united states"
    r").*$",
    re.I,
)
_HANDLE_CITYOF_RE = re.compile(
    r"(?:@|/user/|/)cityof([a-z0-9_]+)",
    re.I,
)


def _handle_to_place_name(handle: str) -> str:
    h = (handle or "").strip().strip("/")
    if not h:
        return ""
    if h.lower().startswith("cityof"):
        h = h[6:]
    elif h.lower().startswith("city"):
        h = h[4:]
    if not h:
        return ""
    if h.islower() or h.isupper():
        return h.title()
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", h)
    return " ".join(part.capitalize() for part in spaced.split())


def parse_municipality_name_from_channel(row: Mapping[str, Any]) -> Optional[str]:
    """Best-effort place name from channel title or ``@CityOf…`` / ``/user/cityof…`` URL."""
    title = str(row.get("channel_title") or "").strip()
    if title:
        match = _CITY_OF_TITLE_RE.search(title)
        if match:
            name = _TITLE_SUFFIX_RE.sub("", match.group(1)).strip(" ,.-")
            if name:
                return name

    url = str(row.get("youtube_channel_url") or row.get("channel_url") or "").lower()
    handle_match = _HANDLE_CITYOF_RE.search(url)
    if handle_match:
        name = _handle_to_place_name(handle_match.group(1))
        if name:
            return name
    return None


def _normalize_municipality_lookup_name(name: str) -> str:
    return normalize_place_label_for_slug(name).replace("_", " ").lower()


def lookup_municipality_jurisdiction(
    cur,
    *,
    state_code: str,
    municipality_name: str,
) -> Optional[dict[str, str]]:
    """
    Return ``{jurisdiction_id, name, website_url}`` for a municipality in *state_code*.

    Matches Census-style ``{Place} city`` labels and slug-normalized names.
    """
    want = _normalize_municipality_lookup_name(municipality_name)
    if not want:
        return None

    cur.execute(
        """
        SELECT
            j.jurisdiction_id,
            j.name,
            (
                SELECT BTRIM(w.website_url)
                FROM intermediate.int_jurisdiction_websites w
                WHERE w.jurisdiction_id = j.jurisdiction_id
                  AND w.website_url IS NOT NULL
                  AND BTRIM(w.website_url) <> ''
                ORDER BY w.website_record_key
                LIMIT 1
            ) AS website_url
        FROM intermediate.int_jurisdictions j
        WHERE j.state_code = %s
          AND j.jurisdiction_type = 'municipality'
        """,
        (state_code.upper()[:2],),
    )
    hits: list[dict[str, str]] = []
    for row in cur.fetchall():
        jname = str(row["name"] or "")
        norm = _normalize_municipality_lookup_name(jname)
        if norm == want:
            hits.append(
                {
                    "jurisdiction_id": str(row["jurisdiction_id"]),
                    "name": jname,
                    "website_url": str(row.get("website_url") or ""),
                }
            )
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        # Prefer exact title-case match on slug prefix.
        slug = want.replace(" ", "_")
        for hit in hits:
            if hit["jurisdiction_id"].startswith(slug + "_"):
                return hit
    return None


def is_misassigned_city_channel_on_county(
    row: Mapping[str, Any],
    *,
    county_name: str,
) -> bool:
    return _looks_like_city_channel_for_county(row, jurisdiction_name=county_name)


def channel_url_key(url: str) -> str:
    return (url or "").strip().lower().rstrip("/")
