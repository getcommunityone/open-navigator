"""
Canonical ``jurisdiction_id`` format: ``{place_slug}_{geoid}`` (e.g. ``andalusia_0101708``, ``mobile_01097``).

Aligns bronze generated columns, ``int_jurisdictions``, scraped-meetings cache folders, and discovery loaders.
States remain 2-letter USPS (``AL``). Legacy typed ids (``municipality_0101852``, ``c-AL-0101852``) are still parsed.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple

from scripts.datasources.youtube.download_audio_to_drive import slug_snake_case

# Legacy: municipality_0101852, county_01097, school_district_0103360
_TYPED_JURISDICTION_ID_RE = re.compile(
    r"^(?P<jtype>county|municipality|state|township|school_district)_(?P<geoid>.+)$",
    re.I,
)
# Migration 013: c-AL-01001, m-AL-0100124
_PREFIXED_USPS_GEOID_RE = re.compile(
    r"^[csmz]-(?P<usps>[A-Za-z]{2})-(?P<geoid>\d+)$",
    re.I,
)
# Canonical: andalusia_0101708, mobile_01097
_SLUG_GEOID_RE = re.compile(r"^(?P<slug>[a-z][a-z0-9_]*)_(?P<geoid>\d+)$", re.I)

_UNICODE_SPACE_RE = re.compile(r"[\u00a0\u2000-\u200a\u202f\u205f\u3000]+")
_PLACE_OF_PREFIX_RE = re.compile(
    r"^(?:city|town|village|borough|township|county)\s+of\s+",
    re.I,
)
_PLACE_LSAD_SUFFIX_RE = re.compile(
    r"\s+(?:city|town|village|county|borough|cdp|municipality|township|parish|ccd)\s*$",
    re.I,
)

_SLUG_MAX_LEN = 56


def normalize_place_label_for_slug(name: str) -> str:
    """Census-style place name with LSAD / ``City of`` prefixes removed."""
    n = _UNICODE_SPACE_RE.sub(" ", (name or "").strip())
    n = _PLACE_OF_PREFIX_RE.sub("", n)
    n = _PLACE_LSAD_SUFFIX_RE.sub("", n).strip()
    return re.sub(r"\s+", " ", n).strip()


def place_slug_for_jurisdiction_id(name: str, *, max_length: int = _SLUG_MAX_LEN) -> str:
    """Lowercase snake_case slug used as the prefix in ``{slug}_{geoid}`` ids."""
    label = normalize_place_label_for_slug(name)
    return slug_snake_case(label, max_length=max_length)


def jurisdiction_id_from_name_geoid(
    name: str,
    geoid: str,
    *,
    jurisdiction_type: Optional[str] = None,
) -> str:
    """
    Build canonical ``jurisdiction_id``.

    ``jurisdiction_type`` is only required for 2-digit state FIPS (``state`` → ``state_01`` style
    is not used; states use USPS). For other types, only ``name`` and ``geoid`` matter.
    """
    g = str(geoid or "").strip().replace("-", "")
    if not g or not g.isdigit():
        return ""
    jt = (jurisdiction_type or "").lower()
    if jt == "state" and len(g) == 2:
        # Bronze states table uses USPS as jurisdiction_id; callers pass geoid FIPS here.
        return ""
    slug = place_slug_for_jurisdiction_id(name or g)
    return f"{slug}_{g}"


def infer_jurisdiction_type_from_geoid(geoid: str) -> Optional[str]:
    """Best-effort type from GEOID length when the id string has no type prefix."""
    g = str(geoid or "").strip()
    n = len(g)
    if n == 2:
        return "state"
    if n == 5:
        return "county"
    if n == 7:
        return "municipality"
    if n == 10:
        return "township"
    return None


def parse_jurisdiction_id(
    jurisdiction_id: str,
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    Parse ``jurisdiction_id`` → ``(jurisdiction_type, geoid, place_slug)``.

    Supports canonical ``slug_geoid``, legacy ``{type}_{geoid}``, and ``c-USPS-geoid`` forms.
    """
    jid = (jurisdiction_id or "").strip()
    if not jid:
        return None, None, None
    if len(jid) == 2 and jid.isalpha():
        return "state", None, jid.lower()

    m = _TYPED_JURISDICTION_ID_RE.match(jid)
    if m:
        jt = m.group("jtype").lower()
        geoid = m.group("geoid").strip()
        slug = place_slug_for_jurisdiction_id(geoid) if jt == "state" else None
        return jt, geoid, slug

    m = _PREFIXED_USPS_GEOID_RE.match(jid)
    if m:
        geoid = m.group("geoid").strip()
        prefix = jid[0].lower()
        jt = {"c": "county", "m": "municipality", "s": "school_district", "z": "zcta"}.get(prefix)
        return jt, geoid, None

    m = _SLUG_GEOID_RE.match(jid)
    if m:
        geoid = m.group("geoid").strip()
        slug = m.group("slug").lower()
        return infer_jurisdiction_type_from_geoid(geoid), geoid, slug

    return None, None, None


def jurisdiction_pk_from_geoid(
    geoid: Optional[str],
    jtype: Optional[str],
    *,
    name: Optional[str] = None,
) -> str:
    """
    Primary key matching bronze / ``int_jurisdictions.jurisdiction_id``.

    When ``name`` is provided (or derivable from bronze), returns ``{slug}_{geoid}``.
    Without ``name``, returns legacy ``{type}_{padded_geoid}`` for backward compatibility.
    """
    raw = str(geoid or "").strip().replace("-", "")
    if not raw or not raw.isdigit():
        return ""
    jt = (jtype or "city").lower()
    if jt in ("city", "town", "village", "borough", "place"):
        jt = "municipality"
    if jt == "school":
        jt = "school_district"

    if name and jt in ("county", "municipality", "school_district", "township"):
        padded = raw
        if jt == "county":
            padded = raw.zfill(5)
        elif jt in ("municipality", "school_district"):
            padded = raw.zfill(7)
        elif jt == "township":
            padded = raw.zfill(10)
        return jurisdiction_id_from_name_geoid(name, padded, jurisdiction_type=jt)

    if jt == "state":
        return f"state_{raw.zfill(2)}"
    if jt == "county":
        return f"county_{raw.zfill(5)}"
    if jt in ("school_district", "school"):
        return f"school_district_{raw.zfill(7)}"
    if jt == "township":
        return f"township_{raw.zfill(10)}"
    return f"municipality_{raw.zfill(7)}"


def resolve_canonical_jurisdiction_id(
    jurisdiction_id: str,
    *,
    name: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
) -> str:
    """Map legacy typed / prefixed ids to canonical ``slug_geoid`` when ``name`` is known."""
    jid = (jurisdiction_id or "").strip()
    if not jid:
        return jid
    if _SLUG_GEOID_RE.match(jid) and not _TYPED_JURISDICTION_ID_RE.match(jid):
        return jid
    jt, geoid, _slug = parse_jurisdiction_id(jid)
    if not geoid:
        return jid
    if name and jt in ("county", "municipality", "school_district", "township"):
        return jurisdiction_id_from_name_geoid(name, geoid, jurisdiction_type=jt)
    if name and jt is None and infer_jurisdiction_type_from_geoid(geoid):
        return jurisdiction_id_from_name_geoid(
            name, geoid, jurisdiction_type=infer_jurisdiction_type_from_geoid(geoid)
        )
    return jid
