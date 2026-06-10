"""
Resolve local-place YouTube channels incorrectly attached to county (or CDP) jurisdictions.

Handles ``City of …``, ``Town of …``, ``Village of …``, and ``@CityOf…`` handles.
New England **towns** live in ``int_jurisdictions`` as ``township`` (e.g. Nantucket town),
not always as ``municipality``.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Optional

from scripts.discovery.youtube_channel_verification import (
    _looks_like_city_channel_for_county,
)
from core_lib.jurisdictions.jurisdiction_id import normalize_place_label_for_slug

_LOCAL_PLACE_TYPES = ("municipality", "township")

_PLACE_OF_TITLE_RE = re.compile(
    r"\b(?:city|town|village|borough)\s*of\s+(.+)",
    re.I,
)
_PLACE_KIND_FROM_TITLE_RE = re.compile(
    r"\b(city|town|village|borough)\s+of\b",
    re.I,
)
_TRAILING_JUNK_RE = re.compile(
    r"(?:"
    r"\s+(?:government|gov|official|usa(?:\s+.*)?|united states(?:\s+.*)?)"
    r"|,\s*(?:alabama|georgia|indiana|massachusetts|washington|wisconsin)(?:\s+.*)?"
    r"|\s+(?:al|ga|in|ma|wa|wi)(?:\s+.*)?"
    r")$",
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


def parse_place_kind_from_channel(row: Mapping[str, Any]) -> Optional[str]:
    """Return ``city``, ``town``, ``village``, or ``borough`` when explicit in title."""
    title = str(row.get("channel_title") or "")
    desc = str(row.get("channel_description") or "")
    for blob in (title, desc):
        match = _PLACE_KIND_FROM_TITLE_RE.search(blob)
        if match:
            return match.group(1).lower()
    return None


def parse_municipality_name_from_channel(row: Mapping[str, Any]) -> Optional[str]:
    """Best-effort place name from channel title or ``@CityOf…`` / ``/user/cityof…`` URL."""
    title = str(row.get("channel_title") or "").strip()
    if title:
        match = _PLACE_OF_TITLE_RE.search(title)
        if match:
            name = match.group(1).split(",")[0].strip()
            name = _TRAILING_JUNK_RE.sub("", name).strip(" ,.-")
            if name:
                return name
        compact = re.match(r"^cityof(.+)$", title.replace(" ", ""), re.I)
        if compact:
            name = _handle_to_place_name(compact.group(1))
            if name:
                return name

    url = str(row.get("youtube_channel_url") or row.get("channel_url") or "").lower()
    handle_match = _HANDLE_CITYOF_RE.search(url)
    if handle_match:
        name = _handle_to_place_name(handle_match.group(1))
        if name:
            return name
    return None


def _normalize_place_lookup_name(name: str) -> str:
    return normalize_place_label_for_slug(name).replace("_", " ").lower()


def _pick_best_place_match(
    hits: list[dict[str, str]],
    *,
    place_kind: Optional[str],
    channel_title: str,
) -> Optional[dict[str, str]]:
    if not hits:
        return None
    if len(hits) == 1:
        return hits[0]

    title_l = (channel_title or "").lower()
    kind = (place_kind or "").lower()
    if kind == "town" or "town of" in title_l:
        for hit in hits:
            jtype = hit.get("jurisdiction_type", "")
            name_l = hit.get("name", "").lower()
            if jtype == "township" or name_l.endswith(" town"):
                return hit
    if kind == "city" or "city of" in title_l:
        for hit in hits:
            if hit.get("name", "").lower().endswith(" city"):
                return hit
    if kind == "village" or "village of" in title_l:
        for hit in hits:
            if hit.get("name", "").lower().endswith(" village"):
                return hit
    if kind == "borough" or "borough of" in title_l:
        for hit in hits:
            if hit.get("name", "").lower().endswith(" borough"):
                return hit

    non_cdp = [h for h in hits if " cdp" not in h.get("name", "").lower()]
    if len(non_cdp) == 1:
        return non_cdp[0]
    if non_cdp:
        for hit in non_cdp:
            if hit.get("jurisdiction_type") == "township":
                return hit

    slug = _normalize_place_lookup_name(channel_title).replace(" ", "_")
    for hit in hits:
        if hit.get("jurisdiction_id", "").startswith(slug + "_"):
            return hit
    return hits[0]


def build_local_place_index(cur, *, state_code: str) -> dict[str, list[dict[str, str]]]:
    """Index ``municipality`` and ``township`` rows by normalized place name."""
    cur.execute(
        """
        SELECT
            j.jurisdiction_id,
            j.name,
            j.jurisdiction_type::text AS jurisdiction_type,
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
          AND j.jurisdiction_type::text = ANY(%s)
        """,
        (state_code.upper()[:2], list(_LOCAL_PLACE_TYPES)),
    )
    index: dict[str, list[dict[str, str]]] = {}
    for row in cur.fetchall():
        entry = {
            "jurisdiction_id": str(row["jurisdiction_id"]),
            "name": str(row["name"] or ""),
            "jurisdiction_type": str(row["jurisdiction_type"] or ""),
            "website_url": str(row.get("website_url") or ""),
        }
        norm = _normalize_place_lookup_name(entry["name"])
        index.setdefault(norm, []).append(entry)
    return index


def build_municipality_index(cur, *, state_code: str) -> dict[str, list[dict[str, str]]]:
    """Backward-compatible alias — includes townships."""
    return build_local_place_index(cur, state_code=state_code)


def lookup_local_place_jurisdiction(
    cur,
    *,
    state_code: str,
    place_name: str,
    channel_title: str = "",
    place_kind: Optional[str] = None,
    local_place_index: dict[str, list[dict[str, str]]] | None = None,
) -> Optional[dict[str, str]]:
    """
    Return ``{jurisdiction_id, name, jurisdiction_type, website_url}`` for a local place.

    Prefers ``township`` / ``{Name} town`` when the channel title says ``Town of {Name}``.
    """
    want = _normalize_place_lookup_name(place_name)
    if not want:
        return None

    if local_place_index is None:
        local_place_index = build_local_place_index(cur, state_code=state_code)

    hits = local_place_index.get(want, [])
    return _pick_best_place_match(
        hits,
        place_kind=place_kind,
        channel_title=channel_title or place_name,
    )


def lookup_municipality_jurisdiction(
    cur,
    *,
    state_code: str,
    municipality_name: str,
    municipality_index: dict[str, list[dict[str, str]]] | None = None,
    **kwargs: Any,
) -> Optional[dict[str, str]]:
    return lookup_local_place_jurisdiction(
        cur,
        state_code=state_code,
        place_name=municipality_name,
        local_place_index=municipality_index,
        **kwargs,
    )


def is_misassigned_city_channel_on_county(
    row: Mapping[str, Any],
    *,
    county_name: str,
) -> bool:
    return _looks_like_city_channel_for_county(row, jurisdiction_name=county_name)


def is_misassigned_local_place_channel(
    row: Mapping[str, Any],
    *,
    jurisdiction_type: str,
    jurisdiction_name: str,
) -> bool:
    """True when a city/town channel is on the wrong jurisdiction row."""
    jtype = (jurisdiction_type or "").strip().lower()
    if jtype == "county":
        return is_misassigned_city_channel_on_county(row, county_name=jurisdiction_name)

    place_name = parse_municipality_name_from_channel(row)
    place_kind = parse_place_kind_from_channel(row)
    if not place_name or jtype not in ("municipality", "township"):
        return False

    name_l = (jurisdiction_name or "").lower()
    if place_kind == "town" and name_l.endswith(" cdp"):
        return True
    if place_kind == "city" and name_l.endswith(" town"):
        return True
    return False


def channel_url_key(url: str) -> str:
    return (url or "").strip().lower().rstrip("/")
