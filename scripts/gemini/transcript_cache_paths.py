"""
Local policy cache layout — mirrors scraped meetings geography + Opus basenames.

``data/cache/gemini_transcript_policy/{state}/{type}/{place_slug}_{geoid}/{channel_id}/``

Jurisdiction folders and bronze ``jurisdiction_id`` both use ``{place_slug}_{geoid}`` (e.g. ``anniston_0101852``).
Legacy typed ids (``municipality_0101852``) are still resolved via ``resolve_canonical_jurisdiction_id``.

- ``01_transcripts/`` — YouTube captions (``YYYY-MM-DD_<title>.json``)
- ``02_analysis/`` — Part 1 structured JSON (same basename)
- ``03_reports/`` — Part 2 Smart Brevity markdown (``.md``)
- ``04_runs/`` — run metadata (``.meta.json``), optional diagrams (``.diagrams.md``)
- ``README.md`` — what each folder is

Legacy flat ``<jurisdiction_id>/`` at the cache root is still read. Reorganize with
``migrate_policy_cache_geography.py``; flatten step folders with ``migrate_policy_cache_layout.py``.
"""

from __future__ import annotations

import functools
import json
import os
import re
import shutil
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

DIR_TRANSCRIPTS = "01_transcripts"
DIR_ANALYSIS = "02_analysis"
DIR_REPORTS = "03_reports"
DIR_RUNS = "04_runs"
DIR_EXCEPTIONS = "05_exceptions"
EXCLUDED_MANIFEST = "_excluded_videos.json"
README_NAME = "README.md"

_POLICY_SUBDIRS = (DIR_TRANSCRIPTS, DIR_ANALYSIS, DIR_REPORTS, DIR_RUNS)
_POLICY_PIPELINE_SUBDIRS = _POLICY_SUBDIRS

# Same folder names as ``data/cache/scraped_meetings`` (see CACHE_TYPE_DIRS in load_scraped_meetings_manifests_to_bronze).
_CACHE_TYPE_FROM_TYPED_ID = {
    "county": "county",
    "municipality": "municipality",
    "state": "state",
    "township": "township",
    "school_district": "school",
}

_BRONZE_JURISDICTION_TYPE_TO_CACHE = {
    "county": "county",
    "municipality": "municipality",
    "city": "municipality",
    "town": "municipality",
    "village": "municipality",
    "school_district": "school",
    "school": "school",
    "state": "state",
    "township": "township",
}

from scripts.jurisdictions.jurisdiction_id import (
    _SLUG_GEOID_RE,
    _TYPED_JURISDICTION_ID_RE,
    infer_jurisdiction_type_from_geoid,
    jurisdiction_pk_from_geoid,
    lookup_canonical_jurisdiction_id_from_bronze,
    parse_jurisdiction_id,
    place_slug_for_jurisdiction_id,
    resolve_canonical_jurisdiction_id as _resolve_slug_jurisdiction_id,
)

_GEOID_FOLDER_SUFFIX_RE = re.compile(r"_(\d{5,10})$")

_JID_TYPED_RE = _TYPED_JURISDICTION_ID_RE
_STATE_CODE_RE = re.compile(r"^[A-Za-z]{2}$")
_YOUTUBE_CHANNEL_ID_RE = re.compile(r"^UC[\w-]{11,}$")
_NUMERIC_JID_RE = re.compile(r"^[0-9]+$")
_UNKNOWN_CHANNEL_SEGMENT = "_unknown"


_UNICODE_SPACE_RE = re.compile(r"[\u00a0\u2000-\u200a\u202f\u205f\u3000]+")
_PLACE_OF_PREFIX_RE = re.compile(
    r"^(?:city|town|village|borough|township|county)\s+of\s+",
    re.I,
)
_PLACE_LSAD_SUFFIX_RE = re.compile(
    r"\s+(?:city|town|village|county|borough|cdp|municipality|township|parish|ccd)\s*$",
    re.I,
)


def _collapse_unicode_spaces(text: str) -> str:
    return _UNICODE_SPACE_RE.sub(" ", (text or "").strip())


def _normalize_place_name_for_match(name: str) -> str:
    """Lowercase place label with LSAD / ``City of`` prefixes removed (Census-style names)."""
    n = _collapse_unicode_spaces(name).lower()
    n = _PLACE_OF_PREFIX_RE.sub("", n)
    n = _PLACE_LSAD_SUFFIX_RE.sub("", n).strip()
    return re.sub(r"\s+", " ", n).strip()


def _place_names_compatible(youtube_name: str, search_name: str) -> bool:
    a = _normalize_place_name_for_match(youtube_name)
    b = _normalize_place_name_for_match(search_name)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    return len(a_tokens & b_tokens) >= max(1, min(len(a_tokens), len(b_tokens)) // 2)


def resolve_canonical_jurisdiction_id(jurisdiction_id: str) -> str:
    """
    Map legacy numeric / typed ids to canonical ``{place_slug}_{geoid}``.

    Returns the input unchanged when already canonical or not resolvable.
    """
    jid = (jurisdiction_id or "").strip()
    if not jid:
        return jid
    if _SLUG_GEOID_RE.match(jid) and not _JID_TYPED_RE.match(jid):
        return jid
    jt, geoid, _slug = parse_jurisdiction_id(jid)
    if geoid and jt and _SLUG_GEOID_RE.match(jid):
        return jid
    if geoid and jt and not _NUMERIC_JID_RE.fullmatch(jid):
        name = lookup_jurisdiction_place_name(jid) or ""
        if name:
            return _resolve_slug_jurisdiction_id(jid, name=name, jurisdiction_type=jt) or jid
    if not jid or not _NUMERIC_JID_RE.fullmatch(jid):
        return jid
    url = _database_url()
    if not url:
        return jid
    try:
        import psycopg2
    except ImportError:
        return jid
    try:
        with psycopg2.connect(url) as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM bronze.bronze_events_youtube WHERE jurisdiction_id = %s",
                (jid,),
            )
            legacy_rows = int(cur.fetchone()[0] or 0)
            cur.execute(
                """
                SELECT jurisdiction_name, state_code
                FROM bronze.bronze_events_youtube
                WHERE jurisdiction_id = %s
                  AND jurisdiction_name IS NOT NULL
                LIMIT 1
                """,
                (jid,),
            )
            yt = cur.fetchone()
            cur.execute(
                """
                SELECT geoid, type, name, state
                FROM public.jurisdiction
                WHERE id::text = %s
                  AND geoid IS NOT NULL AND BTRIM(geoid) <> ''
                LIMIT 1
                """,
                (jid,),
            )
            row = cur.fetchone()
    except Exception:
        return jid
    if not row:
        return jid
    geoid, stype, search_name, search_state = (
        str(row[0] or ""),
        str(row[1] or ""),
        str(row[2] or ""),
        str(row[3] or ""),
    )
    yt_name = str(yt[0] or "") if yt else ""
    yt_state = str(yt[1] or "").strip().upper() if yt and yt[1] else ""
    if legacy_rows > 0:
        if not search_name or not yt_name or not _place_names_compatible(yt_name, search_name):
            return jid
        if search_state and yt_state and search_state.strip().upper() != yt_state:
            return jid
    jt = (stype or "city").lower()
    if jt == "school":
        jt = "school_district"
    if "county" in yt_name.lower():
        jt = "county"
    canonical = jurisdiction_pk_from_geoid(geoid, jt, name=search_name or yt_name)
    return canonical or jid


@functools.lru_cache(maxsize=4096)
def lookup_jurisdiction_place_name(jurisdiction_id: str) -> Optional[str]:
    """Display name from ``int_jurisdictions`` (fallback: bronze YouTube label)."""
    jid = resolve_canonical_jurisdiction_id(jurisdiction_id)
    if not jid:
        return None
    url = _database_url()
    if not url:
        return None
    try:
        import psycopg2
    except ImportError:
        return None
    try:
        with psycopg2.connect(url) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT name FROM intermediate.int_jurisdictions
                WHERE jurisdiction_id = %s
                LIMIT 1
                """,
                (jid,),
            )
            row = cur.fetchone()
            if row and row[0]:
                return str(row[0]).strip()
            cur.execute(
                """
                SELECT jurisdiction_name FROM bronze.bronze_events_youtube
                WHERE jurisdiction_id = %s
                  AND jurisdiction_name IS NOT NULL
                  AND BTRIM(jurisdiction_name) <> ''
                LIMIT 1
                """,
                (jid,),
            )
            row = cur.fetchone()
            if row and row[0]:
                return str(row[0]).strip()
    except Exception:
        return None
    return None


def _place_slug_for_folder(name: str) -> str:
    from scripts.datasources.youtube.download_audio_to_drive import slug_snake_case

    label = _normalize_place_name_for_match(name) or _collapse_unicode_spaces(name)
    return slug_snake_case(label, max_length=56)


def _legacy_place_slug_for_folder(name: str) -> str:
    """
    Pre-2026 slug: snake_case the raw label without stripping trailing ``city`` / ``town``.

    Kept only for ``jurisdiction_cache_folder_aliases`` so older cache dirs resolve.
    """
    from scripts.datasources.youtube.download_audio_to_drive import slug_snake_case

    collapsed = _collapse_unicode_spaces(name).lower()
    return slug_snake_case(collapsed, max_length=56)


def geoid_folder_suffix(folder_name: str) -> Optional[str]:
    """Trailing Census GEOID from a cache folder basename (``henry_01067`` → ``01067``)."""
    m = _GEOID_FOLDER_SUFFIX_RE.search((folder_name or "").strip())
    return m.group(1) if m else None


def _canonical_cache_folder_from_bronze_geoid(
    geoid: str,
    jurisdiction_type: str,
) -> str:
    """``{slug}_{geoid}`` from bronze when GEOID + type are known (ignores caller ``place_name``)."""
    jid = lookup_canonical_jurisdiction_id_from_bronze(geoid, jurisdiction_type)
    if jid and _SLUG_GEOID_RE.match(jid) and not _JID_TYPED_RE.match(jid):
        return jid
    return ""


def jurisdiction_cache_folder_name(jurisdiction_id: str, *, place_name: str | None = None) -> str:
    """
    Filesystem folder under ``{state}/{type}/`` — same as canonical ``jurisdiction_id``.

    Legacy ``municipality_{geoid}`` is mapped via ``resolve_canonical_jurisdiction_id``.
    When bronze has a GEOID match, that canonical id wins over a seat-city ``place_name``
    (e.g. Henry County ``01067`` → ``henry_01067``, not ``abbeville_01067``).
    """
    jid = resolve_canonical_jurisdiction_id(jurisdiction_id)
    _jt, geoid, _slug = parse_jurisdiction_id(jid)
    jtype = (_jt or infer_jurisdiction_type_from_geoid(geoid or "") or "").lower()
    if geoid and jtype:
        bronze_folder = _canonical_cache_folder_from_bronze_geoid(geoid, jtype)
        if bronze_folder:
            return bronze_folder
    if _SLUG_GEOID_RE.match(jid) and not _JID_TYPED_RE.match(jid):
        return jid
    if not geoid:
        safe = re.sub(r"[^A-Za-z0-9._-]+", "_", jid).strip("_")
        return safe[:200] or "unknown"
    place = (place_name or "").strip() or lookup_jurisdiction_place_name(jid) or geoid
    return f"{place_slug_for_jurisdiction_id(place)}_{geoid}"


def jurisdiction_cache_folder_aliases(
    jurisdiction_id: str,
    *,
    place_name: str | None = None,
) -> List[str]:
    """On-disk folder basenames that may exist for one logical jurisdiction."""
    jid = resolve_canonical_jurisdiction_id(jurisdiction_id)
    _jt, geoid, _slug = parse_jurisdiction_id(jid)
    place = (place_name or "").strip() or (lookup_jurisdiction_place_name(jid) if geoid else "")
    names: List[str] = []
    for candidate in (
        jurisdiction_cache_folder_name(jid, place_name=place_name),
        jid,
        (jurisdiction_id or "").strip(),
    ):
        if candidate and candidate not in names:
            names.append(candidate)
    if geoid and place:
        legacy_slug = _legacy_place_slug_for_folder(place)
        legacy_folder = f"{legacy_slug}_{geoid}"
        if legacy_folder not in names:
            names.append(legacy_folder)
        typed = _JID_TYPED_RE.match(jid)
        if typed:
            typed_folder = f"{typed.group('jtype').lower()}_{geoid}"
            if typed_folder not in names:
                names.append(typed_folder)
    return names


def scraped_meetings_jurisdiction_dir(
    output_root: Path,
    *,
    state_code: str,
    jurisdiction_id: str,
    place_name: str | None = None,
) -> Path:
    """
    Canonical ``scraped_meetings/{ST}/{type}/{place_slug}_{geoid}/`` path.

    If a legacy folder already exists (e.g. ``abbeville_city_0100124``), return it so
    crawls resume in-place; new jurisdictions use the normalized canonical name.
    """
    st = (state_code or "").strip().upper()
    segment = cache_type_segment(jurisdiction_id)
    canonical = jurisdiction_cache_folder_name(jurisdiction_id, place_name=place_name)
    root = Path(output_root)
    canonical_path = root / st / segment / canonical
    if canonical_path.is_dir():
        return canonical_path
    canon_geoid = geoid_folder_suffix(canonical)
    for alias in jurisdiction_cache_folder_aliases(jurisdiction_id, place_name=place_name):
        if alias == canonical:
            continue
        # Seat-city misnames (``abbeville_01067`` for Henry County) — merge script fixes;
        # new writes use the canonical folder name.
        alias_geoid = geoid_folder_suffix(alias)
        if canon_geoid and alias_geoid == canon_geoid:
            continue
        candidate = root / st / segment / alias
        if candidate.is_dir():
            return candidate
    return canonical_path


def cache_type_segment(
    jurisdiction_id: str,
    *,
    jurisdiction_type: Optional[str] = None,
) -> str:
    """Filesystem segment under ``{state}/`` (e.g. ``municipality``, ``school``)."""
    jid = resolve_canonical_jurisdiction_id((jurisdiction_id or "").strip())
    match = _JID_TYPED_RE.match(jid)
    if match:
        return _CACHE_TYPE_FROM_TYPED_ID.get(match.group("jtype"), match.group("jtype"))
    jt, _geoid, _slug = parse_jurisdiction_id(jid)
    if jt:
        return _CACHE_TYPE_FROM_TYPED_ID.get(jt, jt)
    raw = (jurisdiction_type or "").strip().lower()
    if raw:
        return _BRONZE_JURISDICTION_TYPE_TO_CACHE.get(raw, raw)
    return "municipality"


def _database_url() -> Optional[str]:
    return (
        os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or os.getenv("DATABASE_URL")
    )


@functools.lru_cache(maxsize=2048)
def lookup_jurisdiction_geo_from_db(jurisdiction_id: str) -> Tuple[Optional[str], Optional[str]]:
    """``(state_code, bronze jurisdiction_type)`` from ``bronze.bronze_events_youtube``."""
    jid = (jurisdiction_id or "").strip()
    if not jid:
        return None, None
    url = _database_url()
    if not url:
        return None, None
    try:
        import psycopg2
    except ImportError:
        return None, None
    try:
        with psycopg2.connect(url) as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT state_code, jurisdiction_type
                FROM bronze.bronze_events_youtube
                WHERE jurisdiction_id = %s
                  AND state_code IS NOT NULL
                  AND BTRIM(state_code) <> ''
                LIMIT 1
                """,
                (jid,),
            )
            row = cur.fetchone()
    except Exception:
        return None, None
    if not row:
        return None, None
    state = str(row[0] or "").strip().upper() or None
    jtype = str(row[1] or "").strip().lower() or None
    return state, jtype


def resolve_jurisdiction_geo(
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
) -> Tuple[str, str]:
    """Return ``(state_code, cache_type_segment)`` for policy cache paths."""
    jurisdiction_id = resolve_canonical_jurisdiction_id(jurisdiction_id)
    st = (state_code or "").strip().upper()
    jtype = (jurisdiction_type or "").strip().lower()
    if not st or not jtype:
        db_st, db_type = lookup_jurisdiction_geo_from_db(jurisdiction_id)
        st = st or (db_st or "")
        jtype = jtype or (db_type or "")
    segment = cache_type_segment(jurisdiction_id, jurisdiction_type=jtype or None)
    return st, segment


def normalize_channel_segment(channel_id: Optional[str]) -> str:
    """Filesystem-safe YouTube channel id folder (``UC…`` or ``_unknown``)."""
    cid = (channel_id or "").strip()
    if _YOUTUBE_CHANNEL_ID_RE.fullmatch(cid):
        return cid
    return _UNKNOWN_CHANNEL_SEGMENT


@functools.lru_cache(maxsize=8192)
def lookup_channel_id_from_db(
    jurisdiction_id: str,
    video_id: str = "",
) -> Optional[str]:
    """``channel_id`` from ``bronze.bronze_events_youtube`` for a jurisdiction or video."""
    jid = (jurisdiction_id or "").strip()
    if not jid:
        return None
    url = _database_url()
    if not url:
        return None
    try:
        import psycopg2
    except ImportError:
        return None
    vid = (video_id or "").strip()
    try:
        with psycopg2.connect(url) as conn, conn.cursor() as cur:
            if vid:
                cur.execute(
                    """
                    SELECT channel_id
                    FROM bronze.bronze_events_youtube
                    WHERE jurisdiction_id = %s AND video_id = %s
                      AND channel_id IS NOT NULL AND BTRIM(channel_id) <> ''
                    LIMIT 1
                    """,
                    (jid, vid),
                )
            else:
                cur.execute(
                    """
                    SELECT channel_id
                    FROM bronze.bronze_events_youtube
                    WHERE jurisdiction_id = %s
                      AND channel_id IS NOT NULL AND BTRIM(channel_id) <> ''
                    GROUP BY channel_id
                    ORDER BY COUNT(*) DESC
                    LIMIT 1
                    """,
                    (jid,),
                )
            row = cur.fetchone()
    except Exception:
        return None
    if not row or not row[0]:
        return None
    cid = str(row[0]).strip()
    return cid if _YOUTUBE_CHANNEL_ID_RE.fullmatch(cid) else None


def jurisdiction_geo_dir(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
) -> Path:
    """``{cache_dir}/{ST}/{type}/{place_slug}_{geoid}/`` (no channel segment)."""
    st, segment = resolve_jurisdiction_geo(
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
    )
    folder = jurisdiction_cache_folder_name(jurisdiction_id)
    if not st:
        return cache_dir / folder
    return cache_dir / st / segment / folder


def canonical_jurisdiction_root(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Path:
    """Write path: ``…/{place_slug}_{geoid}/{channel_id}/``."""
    cid = (channel_id or "").strip()
    if not cid and video_id:
        cid = lookup_channel_id_from_db(jurisdiction_id, video_id) or ""
    if not cid:
        cid = lookup_channel_id_from_db(jurisdiction_id) or ""
    segment = normalize_channel_segment(cid)
    return jurisdiction_geo_dir(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
    ) / segment


def _is_state_cache_dir(path: Path) -> bool:
    return path.is_dir() and bool(_STATE_CODE_RE.fullmatch(path.name))


def _is_policy_channel_dir(path: Path) -> bool:
    """Leaf cache folder: holds ``01_transcripts`` / ``02_analysis`` or is a ``UC…`` dir."""
    if not path.is_dir():
        return False
    if (path / DIR_TRANSCRIPTS).is_dir() or (path / DIR_ANALYSIS).is_dir():
        return True
    name = path.name
    return bool(_YOUTUBE_CHANNEL_ID_RE.fullmatch(name)) or name == _UNKNOWN_CHANNEL_SEGMENT


def list_policy_channel_roots(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> List[Path]:
    """All on-disk channel folders for a jurisdiction (or canonical target for writes)."""
    cache_dir = cache_dir.resolve()
    jid = (jurisdiction_id or "").strip()
    cid = (channel_id or "").strip()
    seen: set[Path] = set()
    out: List[Path] = []

    def add(p: Path) -> None:
        key = p.resolve()
        if key not in seen:
            seen.add(key)
            out.append(p)

    if cid:
        add(
            canonical_jurisdiction_root(
                cache_dir,
                jid,
                state_code=state_code,
                jurisdiction_type=jurisdiction_type,
                channel_id=cid,
            )
        )

    for geo in jurisdiction_geo_candidates(
        cache_dir, jid, state_code=state_code, jurisdiction_type=jurisdiction_type
    ):
        if not geo.is_dir():
            continue
        if _is_policy_channel_dir(geo):
            add(geo)
            continue
        for child in sorted(geo.iterdir()):
            if _is_policy_channel_dir(child):
                add(child)

    if not out:
        add(
            canonical_jurisdiction_root(
                cache_dir,
                jid,
                state_code=state_code,
                jurisdiction_type=jurisdiction_type,
                channel_id=cid or None,
            )
        )
    return out


def jurisdiction_geo_candidates(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
) -> List[Path]:
    """Geographic jurisdiction dirs (channel segment not included)."""
    cache_dir = cache_dir.resolve()
    jid = (jurisdiction_id or "").strip()
    st, segment = resolve_jurisdiction_geo(
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
    )
    seen: set[Path] = set()
    out: List[Path] = []

    def add(p: Path) -> None:
        key = p.resolve()
        if key not in seen:
            seen.add(key)
            out.append(p)

    for folder_name in jurisdiction_cache_folder_aliases(jid):
        if st:
            add(cache_dir / st / segment / folder_name)
        if segment:
            for state_dir in sorted(cache_dir.iterdir()):
                if not _is_state_cache_dir(state_dir):
                    continue
                add(state_dir / segment / folder_name)
    add(cache_dir / jid)
    return out


def jurisdiction_root_candidates(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> List[Path]:
    """Search order for channel-level policy folders (newest layout first)."""
    return list_policy_channel_roots(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
    )


def find_jurisdiction_root(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Optional[Path]:
    """First existing channel folder, or canonical write path."""
    for candidate in jurisdiction_root_candidates(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id or lookup_channel_id_from_db(jurisdiction_id, video_id or ""),
    ):
        if candidate.is_dir() and _is_policy_channel_dir(candidate):
            return candidate
    return canonical_jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    )


_JURISDICTION_README = """# Meeting policy cache — {jurisdiction_id}

Files are grouped by pipeline step. Within each folder, names sort **newest-first by date** (`YYYY-MM-DD_<meeting title>.…`).

| Folder | Contents |
|--------|----------|
| **{dir_transcripts}** | YouTube caption JSON (source text + `youtube.segments`) |
| **{dir_analysis}** | Part 1 policy JSON (`decisions[]`, `uncontested_items[]`, `places[]`) |
| **{dir_reports}** | Part 2 resident-facing Markdown summaries |
| **{dir_runs}** | Run metadata (`.meta.json`) and optional Mermaid sidecars (`.diagrams.md`) |
| **{dir_exceptions}** | Non-meeting uploads excluded from the pipeline (see `exclude_policy_video.py`) |

Basenames match Opus audio under `data/cache/youtube_audio/…/city_of_tuscaloosa_…/`.

Regenerate layout from repo root::

    python scripts/gemini/migrate_policy_cache_layout.py --jurisdiction-id {jurisdiction_id}
"""


def _sanitize_audio_title(text: str, *, max_length: int = 80) -> str:
    if not text:
        return "untitled"
    text = text.replace("/", "-")
    text = re.sub(r'[<>:"\\|?*]', "", text)
    text = re.sub(r"\s+", "_", text.strip())
    text = re.sub(r"_+", "_", text).strip("_")
    return (text or "untitled")[:max_length]


def strip_meeting_date_from_title(
    title: str,
    *,
    resolved_date: Optional[str] = None,
) -> str:
    """
    Drop calendar date text from a meeting title when the same date is the filename prefix.

    Handles ``1/11/2024``, ``1-11-2024``, ``September 23, 2024``, and legacy compact
    suffixes like ``1112024`` (slashes removed by older sanitizers).
    """
    t = (title or "").strip()
    if not t:
        return "untitled"

    month_match = _MONTH_DAY_YEAR_RE.search(t)
    if month_match:
        t = (t[: month_match.start()] + t[month_match.end() :]).strip()
    else:
        for pattern in _DATE_IN_TITLE_PATTERNS:
            match = re.search(pattern, t)
            if match:
                t = (t[: match.start()] + t[match.end() :]).strip()
                break
        else:
            for pattern in _DATE_IN_TITLE_PATTERNS_2Y:
                match = re.search(pattern, t)
                if match:
                    t = (t[: match.start()] + t[match.end() :]).strip()
                    break

    if resolved_date:
        try:
            d = datetime.strptime(str(resolved_date)[:10], "%Y-%m-%d")
        except ValueError:
            d = None
        if d is not None:
            yy = d.year % 100
            variants = (
                f"{d.month}/{d.day}/{d.year}",
                f"{d.month}-{d.day}-{d.year}",
                f"{d.month:02d}/{d.day:02d}/{d.year}",
                f"{d.month:02d}-{d.day:02d}-{d.year}",
                f"{d.month}/{d.day}/{yy:02d}",
                f"{d.month}-{d.day}-{yy:02d}",
                f"{d.month:02d}/{d.day:02d}/{yy:02d}",
                f"{d.month:02d}-{d.day:02d}-{yy:02d}",
                f"{d.month}{d.day}{d.year}",
                f"{d.month:02d}{d.day:02d}{d.year}",
            )
            for fragment in variants:
                if t.endswith(fragment):
                    t = t[: -len(fragment)].strip()
                    break
                hyphenated = fragment.replace("/", "-")
                if hyphenated != fragment and t.endswith(hyphenated):
                    t = t[: -len(hyphenated)].strip()
                    break

    t = re.sub(r"[\s\-–—]+$", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t or "untitled"


_POLICY_OUTPUT_RE = re.compile(r"^\d{8}T\d{6}Z_")
_YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_DATE_IN_TITLE_PATTERNS = (
    r"(\d{4})-(\d{1,2})-(\d{1,2})",
    r"(\d{1,2})-(\d{1,2})-(\d{4})",
    r"(\d{1,2})/(\d{1,2})/(\d{4})",
)
# M-D-YY or M/D/YY (e.g. ``1-23-24`` in county board titles); not four-digit years.
_DATE_IN_TITLE_PATTERNS_2Y = (
    r"(\d{1,2})-(\d{1,2})-(\d{2})(?!\d)",
    r"(\d{1,2})/(\d{1,2})/(\d{2})(?!\d)",
)
_MONTH_DAY_YEAR_RE = re.compile(
    r"(January|February|March|April|May|June|July|August|September|October|November|December|"
    r"Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+(\d{1,2}),\s+(\d{4})",
    re.IGNORECASE,
)
_MONTH_DAY_YEAR_FMTS = ("%B %d, %Y", "%b %d, %Y")


def _full_year_from_two_digit(yy: int) -> int:
    """Meeting titles: ``00``–``49`` → 2000–2049; ``50``–``99`` → 1950–1999."""
    yy = int(yy) % 100
    if yy < 50:
        return 2000 + yy
    return 1900 + yy


def _parse_mdy_groups(month: int, day: int, year: int) -> Optional[str]:
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def extract_meeting_date_from_title(title: str) -> Optional[str]:
    """Parse M/D/YYYY, M-D-YY, YYYY-MM-DD, or 'September 23, 2024' from a video title."""
    month_match = _MONTH_DAY_YEAR_RE.search(title or "")
    if month_match:
        fragment = month_match.group(0)
        for fmt in _MONTH_DAY_YEAR_FMTS:
            try:
                return datetime.strptime(fragment, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
    for pattern in _DATE_IN_TITLE_PATTERNS:
        match = re.search(pattern, title or "")
        if not match:
            continue
        groups = match.groups()
        try:
            if len(groups[0]) == 4:
                year, month, day = int(groups[0]), int(groups[1]), int(groups[2])
            else:
                month, day, year = int(groups[0]), int(groups[1]), int(groups[2])
            parsed = _parse_mdy_groups(month, day, year)
            if parsed:
                return parsed
        except (ValueError, IndexError):
            continue
    for pattern in _DATE_IN_TITLE_PATTERNS_2Y:
        match = re.search(pattern, title or "")
        if not match:
            continue
        try:
            month, day, yy = int(match.group(1)), int(match.group(2)), int(match.group(3))
            parsed = _parse_mdy_groups(month, day, _full_year_from_two_digit(yy))
            if parsed:
                return parsed
        except (ValueError, IndexError):
            continue
    return None


_extract_date_from_title = extract_meeting_date_from_title


def _coerce_date_str(value: Optional[Union[str, datetime, date]]) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    raw = str(value).strip()
    if re.match(r"^\d{4}-\d{2}-\d{2}", raw):
        return raw[:10]
    return None


def resolve_meeting_event_date(
    title: str,
    event_date: Optional[Union[str, datetime, date]] = None,
    published_at: Optional[Union[str, datetime]] = None,
) -> Optional[str]:
    """
    Meeting calendar date for filenames and bronze.

    Prefer a date parsed from the title (e.g. ``9/23/2024`` in the council meeting title)
    over catalog ``event_date`` / YouTube ``published_at`` (often the upload day).
    """
    from_title = extract_meeting_date_from_title(title)
    if from_title:
        return from_title
    coerced = _coerce_date_str(event_date)
    if coerced:
        return coerced
    if published_at is not None:
        try:
            if isinstance(published_at, datetime):
                return published_at.date().strftime("%Y-%m-%d")
            return _coerce_date_str(str(published_at))
        except (ValueError, TypeError):
            pass
    return None


def meeting_media_basename(
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
) -> str:
    date_str = resolve_meeting_event_date(title, event_date=event_date)
    if not date_str:
        date_str = "unknown-date"
    title_without_date = strip_meeting_date_from_title(title, resolved_date=date_str)
    safe_title = _sanitize_audio_title(title_without_date)
    return f"{date_str}_{safe_title}"


def media_filename(
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
    *,
    suffix: str = ".json",
) -> str:
    return f"{meeting_media_basename(title, event_date)}{suffix}"


def jurisdiction_root(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Path:
    """Prefer an existing channel folder; else canonical write path."""
    found = find_jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    )
    return found if found is not None else canonical_jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    )


def channel_root_from_policy_path(path: Path) -> Path:
    """Resolve the ``UC…/`` channel folder containing a policy cache file."""
    p = path.expanduser().resolve()
    if p.parent.name in _POLICY_PIPELINE_SUBDIRS:
        return p.parent.parent
    if p.parent.parent.name == DIR_EXCEPTIONS:
        return p.parent.parent.parent
    for parent in p.parents:
        if _is_policy_channel_dir(parent):
            return parent
    raise ValueError(f"Not under a policy channel folder: {path}")


def ensure_jurisdiction_layout(jid_root: Path) -> None:
    for name in _POLICY_SUBDIRS:
        (jid_root / name).mkdir(parents=True, exist_ok=True)
    readme = jid_root / README_NAME
    if not readme.is_file():
        if _is_policy_channel_dir(jid_root) and (
            _YOUTUBE_CHANNEL_ID_RE.fullmatch(jid_root.name)
            or jid_root.name == _UNKNOWN_CHANNEL_SEGMENT
        ):
            jid = jid_root.parent.name
        else:
            jid = jid_root.name
        readme.write_text(
            _JURISDICTION_README.format(
                jurisdiction_id=jid,
                dir_transcripts=DIR_TRANSCRIPTS,
                dir_analysis=DIR_ANALYSIS,
                dir_reports=DIR_REPORTS,
                dir_runs=DIR_RUNS,
                dir_exceptions=DIR_EXCEPTIONS,
            ),
            encoding="utf-8",
        )


def transcripts_dir(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Path:
    return jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    ) / DIR_TRANSCRIPTS


def analysis_dir(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Path:
    return jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    ) / DIR_ANALYSIS


def reports_dir(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Path:
    return jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    ) / DIR_REPORTS


def runs_dir(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Path:
    return jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    ) / DIR_RUNS


def transcript_cache_filename(
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
) -> str:
    return media_filename(title, event_date, suffix=".json")


def transcript_cache_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
    video_id: Optional[str] = None,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> Path:
    vid = (video_id or "").strip()
    root = canonical_jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=vid or None,
    )
    ensure_jurisdiction_layout(root)
    if title:
        return (
            transcripts_dir(
                cache_dir,
                jurisdiction_id,
                state_code=state_code,
                jurisdiction_type=jurisdiction_type,
                channel_id=channel_id,
                video_id=vid or None,
            )
            / transcript_cache_filename(title, event_date)
        )
    if vid:
        return legacy_transcript_cache_path(
            cache_dir,
            jurisdiction_id,
            vid,
            state_code=state_code,
            jurisdiction_type=jurisdiction_type,
            channel_id=channel_id,
        )
    raise ValueError("transcript_cache_path requires title or video_id")


def analysis_cache_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Path:
    root = canonical_jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    )
    ensure_jurisdiction_layout(root)
    return analysis_dir(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    ) / media_filename(title, event_date, suffix=".json")


def report_cache_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Path:
    root = canonical_jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    )
    ensure_jurisdiction_layout(root)
    return reports_dir(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    ) / media_filename(title, event_date, suffix=".md")


def run_meta_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Path:
    root = canonical_jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    )
    ensure_jurisdiction_layout(root)
    return runs_dir(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    ) / media_filename(title, event_date, suffix=".meta.json")


def run_diagrams_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    title: str,
    event_date: Optional[Union[str, datetime]] = None,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
    video_id: Optional[str] = None,
) -> Path:
    root = canonical_jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    )
    ensure_jurisdiction_layout(root)
    return runs_dir(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    ) / media_filename(title, event_date, suffix=".diagrams.md")


def report_path_for_analysis(analysis_path: Path) -> Path:
    """``02_analysis/foo.json`` → ``03_reports/foo.md``."""
    name = analysis_path.name
    if analysis_path.parent.name == DIR_ANALYSIS:
        return analysis_path.parent.parent / DIR_REPORTS / f"{analysis_path.stem}.md"
    if name.endswith("_analysis.json"):
        base = name[: -len("_analysis.json")]
        return analysis_path.parent / DIR_REPORTS / f"{base}.md"
    return analysis_path.with_suffix(".md").parent.parent / DIR_REPORTS / f"{analysis_path.stem}.md"


def meta_path_for_analysis(analysis_path: Path) -> Path:
    """Sibling run metadata for a Part 1 analysis file."""
    if analysis_path.parent.name == DIR_ANALYSIS:
        return analysis_path.parent.parent / DIR_RUNS / f"{analysis_path.stem}.meta.json"
    name = analysis_path.name
    if name.endswith("_analysis.json"):
        return analysis_path.with_name(name.replace("_analysis.json", "_meta.json"))
    return analysis_path.with_suffix(".meta.json")


_LEGACY_RUN_STEM_RE = re.compile(
    r"^\d+_\d{8}T\d{6}Z_+_?(?P<vid>[A-Za-z0-9_-]{11})_(?P<title>.+?)_policy_analysis_part_1",
    re.IGNORECASE,
)
_YOUTUBE_ID_IN_NAME_RE = re.compile(r"_([A-Za-z0-9_-]{11})_")


def _strip_unknown_prefixes(name: str) -> str:
    stem = Path(name).stem
    while stem.startswith("unknown-date_"):
        stem = stem[len("unknown-date_") :]
    return stem + Path(name).suffix


def _parse_dated_basename(filename: str) -> Tuple[Optional[str], str]:
    stem = Path(_strip_unknown_prefixes(filename)).stem
    match = re.match(r"^(\d{4}-\d{2}-\d{2})_(.+)$", stem)
    if match:
        return match.group(1), match.group(2)
    return None, stem


def _title_from_meeting_and_meta(folder: Path, meeting: Dict[str, Any]) -> Tuple[str, Optional[Any], str]:
    body = str(meeting.get("body_name") or "").strip()
    mdate = str(meeting.get("meeting_date") or meeting.get("date") or "").strip()[:10]
    if not body or not mdate:
        return "", None, ""
    body_key = re.sub(r"[^a-z0-9]+", "", body.lower())
    runs = folder / DIR_RUNS
    if not runs.is_dir():
        return "", None, ""
    for meta_path in sorted(runs.glob("*.meta.json"), key=lambda p: p.name, reverse=True):
        if not meta_path.name.startswith(mdate):
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        title = str(meta.get("title") or "").strip()
        if not title:
            continue
        title_key = re.sub(r"[^a-z0-9]+", "", title.lower())
        if body_key in title_key or body_key in re.sub(r"[^a-z0-9]+", "", meta_path.stem.lower()):
            return title, meta.get("event_date") or mdate, str(meta.get("video_id") or "").strip()
    return "", None, ""


def _title_from_legacy_filename(filename: str) -> Tuple[str, str]:
    """Parse legacy run stem; returns ``(title, video_id)``."""
    stem = Path(_strip_unknown_prefixes(filename)).stem
    for suffix in (
        "_analysis",
        "_meta",
        "_report",
        "_transcript",
        ".diagrams.md",
        ".diagrams",
    ):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break
    match = _LEGACY_RUN_STEM_RE.match(stem)
    if not match:
        return "", ""
    title = match.group("title").replace("_", " ")
    title = re.sub(r"_gemini-[\w-]+$", "", title, flags=re.IGNORECASE).strip()
    return title, match.group("vid")


def _read_json_metadata(path: Path) -> Tuple[str, Optional[Any], str]:
    title = ""
    event_date: Optional[Any] = None
    video_id = ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return title, event_date, video_id
    if isinstance(data, dict):
        title = str(data.get("title") or "").strip()
        event_date = data.get("event_date")
        video_id = str(data.get("video_id") or "").strip()
        meeting = data.get("meeting")
        if isinstance(meeting, dict):
            if not title:
                title = str(meeting.get("title") or "").strip()
            if not video_id:
                video_id = str(meeting.get("video_id") or "").strip()
            if not event_date:
                event_date = meeting.get("event_date") or meeting.get("date")
        transcript = data.get("transcript")
        if isinstance(transcript, dict):
            if not title:
                title = str(transcript.get("title") or "").strip()
            if not event_date:
                event_date = transcript.get("event_date")
    return title, event_date, video_id


def _lookup_run_meta(folder: Path, *, video_id: str = "", run_prefix: str = "") -> Tuple[str, Optional[Any], str]:
    """Find title/date from ``04_runs/*.meta.json`` by video id or legacy run id."""
    runs = folder / DIR_RUNS
    if not runs.is_dir():
        return "", None, ""
    candidates = sorted(runs.glob("*.meta.json"), key=lambda p: p.name, reverse=True)
    for meta_path in candidates:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        mid = str(meta.get("video_id") or "").strip()
        if video_id and mid:
            if mid != video_id:
                continue
        elif run_prefix and not meta_path.name.startswith(run_prefix):
            continue
        title = str(meta.get("title") or "").strip()
        event_date = meta.get("event_date")
        if not title:
            transcript = meta.get("transcript")
            if isinstance(transcript, dict):
                title = str(transcript.get("title") or "").strip()
                event_date = event_date or transcript.get("event_date")
        if title:
            return title, event_date, mid or video_id
    return "", None, video_id


def _run_prefix_from_name(name: str) -> str:
    match = re.match(r"^(\d+)_", name)
    return match.group(1) if match else ""


def _video_id_from_name(name: str) -> str:
    match = _YOUTUBE_ID_IN_NAME_RE.search(name)
    return match.group(1) if match else ""


def metadata_for_policy_file(path: Path, *, folder: Optional[Path] = None) -> Tuple[str, Optional[Any], str]:
    """Best-effort ``(title, event_date, video_id)`` for a cache file."""
    jid_root = folder or path.parent
    if jid_root.name in _POLICY_SUBDIRS:
        jid_root = jid_root.parent

    title, event_date, video_id = _read_json_metadata(path)
    if not video_id:
        video_id = _video_id_from_name(path.name)
    if not title:
        parsed_date, parsed_title = _parse_dated_basename(path.name)
        if parsed_date and parsed_title:
            title = parsed_title
            event_date = event_date or parsed_date
    if not title:
        stripped = Path(_strip_unknown_prefixes(path.name)).stem
        inferred = _extract_date_from_title(stripped)
        if inferred:
            title = stripped
            event_date = event_date or inferred
    if not title or not video_id:
        leg_title, leg_vid = _title_from_legacy_filename(path.name)
        title = title or leg_title
        video_id = video_id or leg_vid
    if not title and path.suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            meeting = data.get("meeting") if isinstance(data.get("meeting"), dict) else {}
            if meeting:
                mt, md, mv = _title_from_meeting_and_meta(jid_root, meeting)
                title = mt or title
                event_date = event_date or md
                video_id = video_id or mv
        except (json.JSONDecodeError, OSError):
            pass
    if not title:
        run_prefix = _run_prefix_from_name(_strip_unknown_prefixes(path.name))
        meta_title, meta_date, meta_vid = _lookup_run_meta(
            jid_root,
            video_id=video_id,
            run_prefix=run_prefix,
        )
        title = meta_title or title
        event_date = event_date or meta_date
        video_id = video_id or meta_vid
    return title, event_date, video_id


def classify_policy_cache_file(path: Path) -> Optional[str]:
    """Map a flat jurisdiction-root file to ``01_transcripts`` … ``04_runs``."""
    name = path.name
    if name == README_NAME or not path.is_file():
        return None
    if name.endswith("_analysis.json"):
        return DIR_ANALYSIS
    if name.endswith("_report.md"):
        return DIR_REPORTS
    if name.endswith("_meta.json"):
        return DIR_RUNS
    if name.endswith(".diagrams.md") or "_diagrams.md" in name:
        return DIR_RUNS
    if name.endswith("_transcript.json"):
        return DIR_TRANSCRIPTS
    if path.suffix == ".json" and _is_flat_caption_json(path):
        return DIR_TRANSCRIPTS
    if name.endswith("_report.md"):
        return DIR_REPORTS
    if path.suffix == ".md" and _LEGACY_RUN_STEM_RE.search(
        path.stem.replace("_report", "").replace(".diagrams", "")
    ):
        return DIR_REPORTS
    return None


def destination_for_policy_file(
    folder: Path,
    path: Path,
    *,
    kind: str,
) -> Optional[Path]:
    title, event_date, _vid = metadata_for_policy_file(path, folder=folder)
    if not title:
        return None
    if kind == DIR_TRANSCRIPTS:
        return folder / DIR_TRANSCRIPTS / transcript_cache_filename(title, event_date)
    if kind == DIR_ANALYSIS:
        return folder / DIR_ANALYSIS / media_filename(title, event_date, suffix=".json")
    if kind == DIR_REPORTS:
        return folder / DIR_REPORTS / media_filename(title, event_date, suffix=".md")
    if kind == DIR_RUNS:
        if path.name.endswith(".diagrams.md") or "_diagrams.md" in path.name:
            return folder / DIR_RUNS / media_filename(title, event_date, suffix=".diagrams.md")
        return folder / DIR_RUNS / media_filename(title, event_date, suffix=".meta.json")
    return None


def _safe_move(src: Path, dest: Path, *, dry_run: bool) -> str:
    if dest.resolve() == src.resolve():
        return "same"
    if dest.is_file():
        if src.stat().st_mtime <= dest.stat().st_mtime:
            if dry_run:
                return "would_remove_older_duplicate"
            src.unlink()
            return "removed_older_duplicate"
        if dry_run:
            return "would_replace_newer"
        dest.unlink()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dry_run:
        return "would_move"
    shutil.move(str(src), str(dest))
    return "moved"


def migrate_policy_cache_layout(
    folder: Path,
    *,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Move flat files under a jurisdiction folder into ``01_transcripts`` … ``04_runs``.

    Collapses duplicate legacy runs per meeting basename (keeps newest mtime).
    """
    folder = folder.resolve()
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    ensure_jurisdiction_layout(folder)
    stats: Dict[str, int] = defaultdict(int)

    renamed, skipped, warnings = migrate_transcript_cache_names(folder, dry_run=dry_run)
    stats["transcript_renamed"] = renamed
    stats["transcript_skipped"] = skipped
    stats["warnings"] = len(warnings)

    pending: Dict[Path, List[Path]] = defaultdict(list)
    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        kind = classify_policy_cache_file(path)
        if not kind:
            stats["unclassified"] += 1
            continue
        dest = destination_for_policy_file(folder, path, kind=kind)
        if dest is None:
            stats["skipped_no_title"] += 1
            warnings.append(f"{path.name}: could not derive meeting title")
            continue
        pending[dest].append(path)

    for dest, sources in pending.items():
        sources.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for i, src in enumerate(sources):
            action = _safe_move(src, dest, dry_run=dry_run)
            stats[action] += 1
            if i > 0 and action in ("removed_older_duplicate", "would_remove_older_duplicate"):
                continue
    repair_policy_cache_basenames(folder, dry_run=dry_run)
    return dict(stats)


def _needs_basename_repair(path: Path) -> bool:
    if path.name.startswith("unknown-date_") or bool(_POLICY_OUTPUT_RE.match(path.name)):
        return True
    return not bool(re.match(r"^\d{4}-\d{2}-\d{2}_", path.name))


def _is_junk_policy_artifact(path: Path) -> bool:
    stem = Path(_strip_unknown_prefixes(path.name)).stem
    return stem in ("_manifest",) or stem.startswith("_index")


def repair_policy_cache_basenames(folder: Path, *, dry_run: bool = False) -> Dict[str, int]:
    """Rename ``unknown-date_*`` (or legacy timestamp) files to ``YYYY-MM-DD_<title>.*``."""
    folder = folder.resolve()
    ensure_jurisdiction_layout(folder)
    stats: Dict[str, int] = defaultdict(int)
    pending: Dict[Path, List[Path]] = defaultdict(list)

    for sub in _POLICY_SUBDIRS:
        subdir = folder / sub
        if not subdir.is_dir():
            continue
        for path in subdir.iterdir():
            if not path.is_file():
                continue
            if _is_junk_policy_artifact(path):
                if not dry_run:
                    path.unlink()
                stats["removed_junk"] += 1
                continue
            if not _needs_basename_repair(path):
                continue
            kind = sub
            dest = destination_for_policy_file(folder, path, kind=kind)
            if dest is None:
                stats["skipped"] += 1
                continue
            pending[dest].append(path)

    for dest, sources in pending.items():
        sources.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        for src in sources:
            stats[_safe_move(src, dest, dry_run=dry_run)] += 1
    return dict(stats)


def policy_output_stem(
    *,
    title: str = "",
    event_date: Optional[Union[str, datetime]] = None,
    video_id: str = "",
    prompt_tag: str = "policy",
    model_tag: str = "model",
) -> str:
    """Human basename (no subdir); used for legacy browser stem compatibility."""
    _ = (video_id, prompt_tag, model_tag)
    if (title or "").strip():
        return meeting_media_basename(title, event_date)
    return f"unknown-date_{(video_id or 'unknown').strip()}"


def legacy_transcript_cache_path(
    cache_dir: Path,
    jurisdiction_id: str,
    video_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> Path:
    vid = video_id.strip()
    return jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=vid,
    ) / f"{vid}_transcript.json"


def _is_flat_caption_json(path: Path) -> bool:
    name = path.name
    if not name.endswith(".json") or not path.is_file():
        return False
    if any(x in name for x in ("_analysis", "_meta", ".diagrams", "_transcript")):
        return False
    if _POLICY_OUTPUT_RE.match(name):
        return False
    if name.endswith("_transcript.json"):
        stem = name[: -len("_transcript.json")]
        return bool(_YOUTUBE_ID_RE.fullmatch(stem))
    return bool(re.match(r"^\d{4}-\d{2}-\d{2}_", name))


def is_transcript_cache_file(path: Path) -> bool:
    return _is_flat_caption_json(path)


def _iter_dir_sorted(folder: Path) -> List[Path]:
    if not folder.is_dir():
        return []
    return sorted(
        (p for p in folder.iterdir() if p.is_file()),
        key=lambda p: p.name,
        reverse=True,
    )


def iter_transcript_cache_files(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> List[Path]:
    out: List[Path] = []
    seen: set[str] = set()
    for root in list_policy_channel_roots(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
    ):
        td = root / DIR_TRANSCRIPTS
        if td.is_dir():
            for p in _iter_dir_sorted(td):
                if _is_flat_caption_json(p) and p.name not in seen:
                    seen.add(p.name)
                    out.append(p)
        for p in _iter_dir_sorted(root):
            if _is_flat_caption_json(p) and p.name not in seen:
                seen.add(p.name)
                out.append(p)
    return out


def iter_analysis_files(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> List[Path]:
    out: List[Path] = []
    for root in list_policy_channel_roots(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
    ):
        ad = root / DIR_ANALYSIS
        if ad.is_dir():
            out.extend(
                p for p in _iter_dir_sorted(ad) if p.suffix == ".json" and p.is_file()
            )
        else:
            out.extend(p for p in root.glob("*_analysis.json") if p.is_file())
    return sorted(out, key=lambda p: p.name, reverse=True)


def iter_report_files(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> List[Path]:
    out: List[Path] = []
    for root in list_policy_channel_roots(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
    ):
        rd = root / DIR_REPORTS
        if rd.is_dir():
            out.extend(p for p in _iter_dir_sorted(rd) if p.suffix == ".md" and p.is_file())
        else:
            out.extend(p for p in root.glob("*_report.md") if p.is_file())
    return sorted(out, key=lambda p: p.name, reverse=True)


def resolve_transcript_cache_path(
    folder: Path,
    *,
    video_id: Optional[str] = None,
    title: Optional[str] = None,
    event_date: Optional[Union[str, datetime]] = None,
) -> Optional[Path]:
    """Find caption JSON under ``01_transcripts/`` or legacy flat layout."""
    jid_root = folder
    if title:
        candidate = jid_root / DIR_TRANSCRIPTS / transcript_cache_filename(title, event_date)
        if candidate.is_file():
            return candidate
        flat = jid_root / transcript_cache_filename(title, event_date)
        if flat.is_file():
            return flat
    vid = (video_id or "").strip()
    if vid:
        legacy = jid_root / f"{vid}_transcript.json"
        if legacy.is_file():
            return legacy
        for sub in (jid_root / DIR_TRANSCRIPTS, jid_root):
            for path in _iter_dir_sorted(sub):
                if not _is_flat_caption_json(path):
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if (data.get("video_id") or "").strip() == vid:
                    return path
    return None


def video_id_from_analysis(data: Dict[str, Any]) -> str:
    """YouTube id from Part 1 JSON (top-level, meeting, or first playback_url)."""
    vid = str(data.get("video_id") or "").strip()
    if vid:
        return vid
    meeting = data.get("meeting")
    if isinstance(meeting, dict):
        vid = str(meeting.get("video_id") or "").strip()
        if vid:
            return vid
    for bucket in (data.get("uncontested_items") or [], data.get("decisions") or []):
        if not isinstance(bucket, list):
            continue
        for row in bucket:
            if not isinstance(row, dict):
                continue
            anchor = row.get("media_anchor")
            if not isinstance(anchor, dict):
                continue
            url = str(anchor.get("playback_url") or "")
            match = re.search(r"(?:[?&]v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
            if match:
                return match.group(1)
    return ""


def resolve_analysis_path(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    video_id: str = "",
    title: str = "",
    event_date: Optional[Union[str, datetime]] = None,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> Optional[Path]:
    if title:
        for root in list_policy_channel_roots(
            cache_dir,
            jurisdiction_id,
            state_code=state_code,
            jurisdiction_type=jurisdiction_type,
            channel_id=channel_id,
        ):
            p = root / DIR_ANALYSIS / media_filename(title, event_date, suffix=".json")
            if p.is_file():
                return p
    vid = (video_id or "").strip()
    for path in iter_analysis_files(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
    ):
        if vid:
            if vid in path.name:
                return path
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if video_id_from_analysis(data) != vid:
                continue
        return path
    return None


def _policy_file_dest(
    folder: Path,
    sub: str,
    path: Path,
    title: str,
    event_date: Optional[Union[str, datetime]],
) -> Path:
    """Target path using title-first meeting date (``meeting_media_basename``)."""
    subdir = folder / sub
    if sub == DIR_TRANSCRIPTS:
        return subdir / transcript_cache_filename(title, event_date)
    if sub == DIR_RUNS:
        if path.name.endswith(".diagrams.md"):
            return subdir / media_filename(title, event_date, suffix=".diagrams.md")
        return subdir / media_filename(title, event_date, suffix=".meta.json")
    return subdir / media_filename(title, event_date, suffix=path.suffix)


def _patch_json_event_date_field(
    path: Path,
    title: str,
    *,
    dry_run: bool,
) -> bool:
    """Set ``event_date`` inside a transcript or analysis JSON when title has a clearer date."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(data, dict):
        return False
    resolved = resolve_meeting_event_date(title, event_date=data.get("event_date"))
    if not resolved or str(data.get("event_date") or "")[:10] == resolved:
        return False
    if not dry_run:
        data["event_date"] = resolved
        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return True


def fix_policy_cache_dates_from_title(
    folder: Path,
    *,
    dry_run: bool = False,
) -> Dict[str, int]:
    """
    Rename ``01_transcripts`` … ``04_runs`` files to ``YYYY-MM-DD_<title>.*`` using the
    meeting date parsed from the title (not the upload date prefix).

    Updates ``event_date`` inside transcript/analysis JSON when it disagrees.
    """
    folder = folder.resolve()
    ensure_jurisdiction_layout(folder)
    stats: Dict[str, int] = defaultdict(int)

    for sub in _POLICY_SUBDIRS:
        subdir = folder / sub
        if not subdir.is_dir():
            continue
        for path in sorted(subdir.iterdir()):
            if not path.is_file() or path.name == README_NAME:
                continue
            if _is_junk_policy_artifact(path):
                continue
            title, event_date, _vid = metadata_for_policy_file(path, folder=folder)
            if not (title or "").strip():
                stats["skipped_no_title"] += 1
                continue
            dest = _policy_file_dest(folder, sub, path, title, event_date)
            work_path = path
            if dest.resolve() != path.resolve():
                action = _safe_move(path, dest, dry_run=dry_run)
                stats[action] += 1
                work_path = dest
            else:
                stats["already_named"] += 1
            if sub in (DIR_TRANSCRIPTS, DIR_ANALYSIS) and work_path.suffix == ".json":
                if _patch_json_event_date_field(work_path, title, dry_run=dry_run):
                    stats["json_event_date_patched"] += 1

    for path in sorted(folder.iterdir()):
        if not path.is_file():
            continue
        kind = classify_policy_cache_file(path)
        if not kind or kind not in _POLICY_SUBDIRS:
            continue
        title, event_date, _vid = metadata_for_policy_file(path, folder=folder)
        if not (title or "").strip():
            stats["skipped_no_title"] += 1
            continue
        dest = _policy_file_dest(folder, kind, path, title, event_date)
        if dest.resolve() == path.resolve():
            stats["already_named"] += 1
            continue
        action = _safe_move(path, dest, dry_run=dry_run)
        stats[action] += 1

    return dict(stats)


def migrate_transcript_cache_names(
    folder: Path,
    *,
    dry_run: bool = False,
) -> Tuple[int, int, List[str]]:
    """Rename legacy ``{video_id}_transcript.json`` under transcripts dir or flat root."""
    target = folder / DIR_TRANSCRIPTS if (folder / DIR_TRANSCRIPTS).is_dir() else folder
    target.mkdir(parents=True, exist_ok=True)
    renamed = 0
    skipped = 0
    warnings: List[str] = []
    for path in sorted(folder.glob("*_transcript.json")):
        if not path.is_file():
            continue
        stem = path.stem.replace("_transcript", "")
        if not _YOUTUBE_ID_RE.fullmatch(stem):
            skipped += 1
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            warnings.append(f"{path.name}: unreadable ({exc})")
            skipped += 1
            continue
        title = str(data.get("title") or "").strip()
        if not title:
            warnings.append(f"{path.name}: missing title; not renamed")
            skipped += 1
            continue
        dest = target / transcript_cache_filename(title, data.get("event_date"))
        if dest.resolve() == path.resolve():
            skipped += 1
            continue
        if dest.is_file() and dest.resolve() != path.resolve():
            warnings.append(f"{path.name}: target exists {dest.name}; removing duplicate legacy file")
            if not dry_run:
                path.unlink()
            renamed += 1
            continue
        if dry_run:
            warnings.append(f"would rename: {path.name} -> {dest.relative_to(folder)}")
        else:
            path.rename(dest)
        renamed += 1
    return renamed, skipped, warnings


def load_local_transcript_payload(
    cache_dir: Path,
    jurisdiction_id: str,
    *,
    video_id: str,
    title: Optional[str] = None,
    event_date: Optional[Union[str, datetime]] = None,
    state_code: Optional[str] = None,
    jurisdiction_type: Optional[str] = None,
    channel_id: Optional[str] = None,
) -> Optional[tuple[Path, Dict[str, Any]]]:
    folder = find_jurisdiction_root(
        cache_dir,
        jurisdiction_id,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        channel_id=channel_id,
        video_id=video_id,
    )
    path = resolve_transcript_cache_path(
        folder,
        video_id=video_id,
        title=title,
        event_date=event_date,
    )
    if path is None:
        return None
    return path, json.loads(path.read_text(encoding="utf-8"))


def payload_from_row_or_path(
    row: Optional[Dict[str, Any]] = None,
    *,
    path: Optional[Path] = None,
) -> Tuple[str, Optional[str], str]:
    if row:
        return (
            str(row.get("title") or ""),
            row.get("event_date"),
            str(row.get("video_id") or ""),
        )
    if path and path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        return (
            str(data.get("title") or ""),
            data.get("event_date"),
            str(data.get("video_id") or path.stem.replace("_transcript", "")),
        )
    raise ValueError("payload_from_row_or_path requires row or path")


_POLICY_SKIP_ROOT_DIRS = frozenset({"logs"})


def is_legacy_policy_jurisdiction_dir(path: Path, cache_dir: Path) -> bool:
    """Jurisdiction folder sitting directly under the policy cache root (pre-geography layout)."""
    if not path.is_dir():
        return False
    cache_dir = cache_dir.resolve()
    if path.resolve() == cache_dir or path.name in _POLICY_SKIP_ROOT_DIRS:
        return False
    if _is_state_cache_dir(path):
        return False
    return path.parent.resolve() == cache_dir


def list_legacy_policy_jurisdiction_dirs(cache_dir: Path) -> List[Path]:
    cache_dir = cache_dir.resolve()
    return [
        child
        for child in sorted(cache_dir.iterdir())
        if is_legacy_policy_jurisdiction_dir(child, cache_dir)
    ]


def migrate_policy_cache_geography(
    cache_dir: Path,
    *,
    dry_run: bool = False,
    jurisdiction_id: str = "",
) -> Dict[str, int]:
    """Move flat ``{cache_dir}/{jurisdiction_id}/`` trees into ``{state}/{type}/{jid}/``."""
    cache_dir = cache_dir.resolve()
    stats: Dict[str, int] = defaultdict(int)
    targets = list_legacy_policy_jurisdiction_dirs(cache_dir)
    want = (jurisdiction_id or "").strip()
    if want:
        targets = [p for p in targets if p.name == want]
    for src in targets:
        jid = src.name
        st, jtype = resolve_jurisdiction_geo(jid)
        if not st:
            stats["skipped_no_state"] += 1
            continue
        dest = jurisdiction_geo_dir(
            cache_dir,
            jid,
            state_code=st,
            jurisdiction_type=jtype,
        )
        if dest.resolve() == src.resolve():
            stats["already_placed"] += 1
            continue
        if dest.exists():
            stats["skipped_dest_exists"] += 1
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dry_run:
            stats["would_move"] += 1
        else:
            shutil.move(str(src), str(dest))
            stats["moved"] += 1
    return dict(stats)


def _video_id_from_policy_file(path: Path) -> str:
    if path.suffix == ".json":
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            vid = str(data.get("video_id") or "").strip()
            if vid:
                return vid
        except (json.JSONDecodeError, OSError):
            pass
    vid = _video_id_from_name(path.name)
    return vid or ""


def list_jurisdiction_geo_dirs_needing_channel_split(cache_dir: Path) -> List[Path]:
    """Geographic jurisdiction dirs with step folders directly underneath (no ``UC…`` child)."""
    cache_dir = cache_dir.resolve()
    out: List[Path] = []
    for geo in cache_dir.iterdir():
        if not _is_state_cache_dir(geo):
            continue
        for jtype_dir in geo.iterdir():
            if not jtype_dir.is_dir():
                continue
            for jid_dir in jtype_dir.iterdir():
                if not jid_dir.is_dir():
                    continue
                if (jid_dir / DIR_TRANSCRIPTS).is_dir() or (jid_dir / DIR_ANALYSIS).is_dir():
                    out.append(jid_dir)
    return sorted(out)


def migrate_policy_cache_channels(
    cache_dir: Path,
    *,
    dry_run: bool = False,
    jurisdiction_id: str = "",
) -> Dict[str, int]:
    """
    Move ``{geo}/{jid}/01_transcripts/…`` into ``{geo}/{jid}/{channel_id}/01_transcripts/…``.

    Channel is resolved per file from bronze (by ``video_id`` in JSON).
    """
    cache_dir = cache_dir.resolve()
    stats: Dict[str, int] = defaultdict(int)
    targets = list_jurisdiction_geo_dirs_needing_channel_split(cache_dir)
    want = (jurisdiction_id or "").strip()
    if want:
        targets = [p for p in targets if p.name == want]

    for geo_dir in targets:
        jid = geo_dir.name
        st = geo_dir.parent.parent.name if _is_state_cache_dir(geo_dir.parent.parent) else ""
        jtype = geo_dir.parent.name
        for sub in _POLICY_SUBDIRS:
            subdir = geo_dir / sub
            if not subdir.is_dir():
                continue
            for path in sorted(subdir.iterdir()):
                if not path.is_file():
                    continue
                vid = _video_id_from_policy_file(path)
                channel = (
                    lookup_channel_id_from_db(jid, vid)
                    if vid
                    else lookup_channel_id_from_db(jid)
                )
                dest_root = canonical_jurisdiction_root(
                    cache_dir,
                    jid,
                    state_code=st or None,
                    jurisdiction_type=jtype,
                    channel_id=channel,
                )
                dest = dest_root / sub / path.name
                if dest.resolve() == path.resolve():
                    stats["already_placed"] += 1
                    continue
                if dest.is_file():
                    stats["skipped_dest_exists"] += 1
                    continue
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dry_run:
                    stats["would_move"] += 1
                else:
                    shutil.move(str(path), str(dest))
                    stats["moved"] += 1

        if not dry_run:
            for sub in _POLICY_SUBDIRS:
                leftover = geo_dir / sub
                if leftover.is_dir() and not any(leftover.iterdir()):
                    leftover.rmdir()
            readme = geo_dir / README_NAME
            if readme.is_file() and not any(
                (geo_dir / s).is_dir() for s in _POLICY_SUBDIRS
            ):
                readme.unlink(missing_ok=True)
            if geo_dir.is_dir() and not any(geo_dir.iterdir()):
                geo_dir.rmdir()
                stats["removed_empty_geo"] += 1

    return dict(stats)


def _is_typed_prefix_folder_name(name: str) -> bool:
    return bool(_JID_TYPED_RE.match((name or "").strip()))


def migrate_policy_cache_folder_names(
    cache_dir: Path,
    *,
    dry_run: bool = False,
    jurisdiction_id: str = "",
) -> Dict[str, int]:
    """
    Rename ``municipality_0101852/`` → ``anniston_0101852/`` under each ``{state}/{type}/``.
    """
    cache_dir = cache_dir.resolve()
    stats: Dict[str, int] = defaultdict(int)
    want = (jurisdiction_id or "").strip()
    want_aliases = set(jurisdiction_cache_folder_aliases(want)) if want else set()

    for state_dir in sorted(cache_dir.iterdir()):
        if not _is_state_cache_dir(state_dir):
            continue
        for type_dir in sorted(state_dir.iterdir()):
            if not type_dir.is_dir():
                continue
            for geo_dir in sorted(type_dir.iterdir()):
                if not geo_dir.is_dir():
                    continue
                old_name = geo_dir.name
                if not _is_typed_prefix_folder_name(old_name):
                    continue
                if want_aliases and old_name not in want_aliases:
                    if jurisdiction_cache_folder_name(old_name) not in want_aliases:
                        continue
                new_name = jurisdiction_cache_folder_name(old_name)
                if new_name == old_name:
                    stats["already_named"] += 1
                    continue
                dest = geo_dir.parent / new_name
                if dest.exists():
                    stats["skipped_dest_exists"] += 1
                    continue
                if dry_run:
                    stats["would_rename"] += 1
                else:
                    shutil.move(str(geo_dir), str(dest))
                    stats["renamed"] += 1
    return dict(stats)


_INT_TYPES_FOR_CACHE_SEGMENT = {
    "municipality": frozenset({"municipality", "city", "town", "village"}),
    "county": frozenset({"county"}),
    "school": frozenset({"school_district", "school"}),
    "township": frozenset({"township"}),
    "state": frozenset({"state"}),
}


def geoid_variants_for_numeric(numeric_id: str) -> frozenset[str]:
    """Filesystem legacy ids often drop leading zeros from Census GEOIDs."""
    n = (numeric_id or "").strip()
    if not _NUMERIC_JID_RE.fullmatch(n):
        return frozenset()
    variants = {n, str(int(n)), n.zfill(7), n.zfill(5), n.zfill(10), str(int(n)).zfill(7)}
    return frozenset(v for v in variants if v)


def _int_type_matches_cache_segment(int_type: str, cache_segment: str) -> bool:
    allowed = _INT_TYPES_FOR_CACHE_SEGMENT.get(cache_segment, frozenset({cache_segment}))
    return (int_type or "").strip().lower() in allowed


def resolve_numeric_folder_canonical_id(
    numeric_id: str,
    *,
    state_code: str,
    cache_type_segment: str,
    jurisdictions: Sequence[Dict[str, str]],
) -> Optional[str]:
    """
    Map a bare numeric cache folder (e.g. ``159472``) to ``{place_slug}_{geoid}``.

    Uses ``intermediate.int_jurisdictions`` rows supplied by the caller.
    """
    variants = geoid_variants_for_numeric(numeric_id)
    if not variants:
        return None
    st = (state_code or "").strip().upper()
    hits: List[str] = []
    for row in jurisdictions:
        if (row.get("state_code") or "").strip().upper() != st:
            continue
        geoid = str(row.get("geoid") or "").strip()
        if geoid not in variants:
            continue
        jtype = str(row.get("jurisdiction_type") or row.get("type") or "").strip().lower()
        if not _int_type_matches_cache_segment(jtype, cache_type_segment):
            continue
        jid = str(row.get("jurisdiction_id") or "").strip()
        if jid and jid not in hits:
            hits.append(jid)
    if len(hits) == 1:
        return hits[0]
    return None


def list_numeric_policy_geo_dirs(cache_dir: Path) -> List[Tuple[str, str, str, Path]]:
    """``(state_code, cache_type_segment, numeric_folder_name, path)``."""
    cache_dir = cache_dir.resolve()
    out: List[Tuple[str, str, str, Path]] = []
    for state_dir in sorted(cache_dir.iterdir()):
        if not _is_state_cache_dir(state_dir):
            continue
        for type_dir in sorted(state_dir.iterdir()):
            if not type_dir.is_dir():
                continue
            for geo_dir in sorted(type_dir.iterdir()):
                if geo_dir.is_dir() and _NUMERIC_JID_RE.fullmatch(geo_dir.name):
                    out.append((state_dir.name, type_dir.name, geo_dir.name, geo_dir))
    return out


def load_int_jurisdictions_for_numeric_migration(database_url: str) -> List[Dict[str, str]]:
    """Rows used to resolve numeric policy-cache folders."""
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return []
    if not database_url:
        return []
    try:
        with psycopg2.connect(database_url) as conn, conn.cursor(
            cursor_factory=RealDictCursor
        ) as cur:
            cur.execute(
                """
                SELECT jurisdiction_id, geoid, name, jurisdiction_type, state_code
                FROM intermediate.int_jurisdictions
                WHERE geoid IS NOT NULL AND BTRIM(geoid) <> ''
                """
            )
            rows = cur.fetchall()
    except Exception:
        return []
    out: List[Dict[str, str]] = []
    for row in rows:
        out.append(
            {
                "jurisdiction_id": str(row.get("jurisdiction_id") or "").strip(),
                "geoid": str(row.get("geoid") or "").strip(),
                "name": str(row.get("name") or "").strip(),
                "jurisdiction_type": str(row.get("jurisdiction_type") or "").strip().lower(),
                "state_code": str(row.get("state_code") or "").strip().upper(),
            }
        )
    return out


def build_numeric_policy_folder_mapping(
    cache_dir: Path,
    jurisdictions: Sequence[Dict[str, str]],
    *,
    jurisdiction_id_filter: str = "",
) -> Dict[str, str]:
    """Legacy numeric folder basename → canonical ``jurisdiction_id``."""
    want = (jurisdiction_id_filter or "").strip()
    want_aliases = set(jurisdiction_cache_folder_aliases(want)) if want else set()
    mapping: Dict[str, str] = {}
    ambiguous: Dict[str, List[str]] = {}

    for state_code, cache_segment, numeric_name, _geo in list_numeric_policy_geo_dirs(cache_dir):
        if want_aliases and numeric_name not in want_aliases:
            canonical_hint = resolve_numeric_folder_canonical_id(
                numeric_name,
                state_code=state_code,
                cache_type_segment=cache_segment,
                jurisdictions=jurisdictions,
            )
            if not canonical_hint or canonical_hint not in want_aliases:
                if jurisdiction_cache_folder_name(canonical_hint or "") not in want_aliases:
                    continue
        canonical = resolve_numeric_folder_canonical_id(
            numeric_name,
            state_code=state_code,
            cache_type_segment=cache_segment,
            jurisdictions=jurisdictions,
        )
        if not canonical or canonical == numeric_name:
            continue
        if numeric_name in mapping and mapping[numeric_name] != canonical:
            ambiguous.setdefault(numeric_name, sorted({mapping[numeric_name], canonical}))
            continue
        mapping[numeric_name] = canonical

    for legacy, options in ambiguous.items():
        mapping.pop(legacy, None)
    return mapping


def _merge_policy_dir_contents(src: Path, dest: Path, *, dry_run: bool) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for child in src.iterdir():
        target = dest / child.name
        if child.is_dir():
            if target.exists():
                _merge_policy_dir_contents(child, target, dry_run=dry_run)
                if not dry_run and not any(child.iterdir()):
                    child.rmdir()
            elif dry_run:
                pass
            else:
                shutil.move(str(child), str(target))
        elif target.exists():
            if not dry_run and child.name == README_NAME and target.name == README_NAME:
                child.unlink()
            continue
        elif dry_run:
            pass
        else:
            shutil.move(str(child), str(target))


def _patch_policy_cache_json_jurisdiction_id(
    root: Path,
    canonical: str,
    *,
    dry_run: bool,
) -> None:
    if not root.is_dir():
        return
    for path in root.rglob("*.json"):
        if path.parent.name not in (
            DIR_TRANSCRIPTS,
            DIR_ANALYSIS,
            DIR_RUNS,
        ) and "_transcript" not in path.name:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if str(data.get("jurisdiction_id") or "") == canonical:
            continue
        data["jurisdiction_id"] = canonical
        if not dry_run:
            path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )


def migrate_policy_cache_numeric_folders(
    cache_dir: Path,
    *,
    database_url: Optional[str] = None,
    jurisdictions: Optional[Sequence[Dict[str, str]]] = None,
    dry_run: bool = False,
    jurisdiction_id: str = "",
) -> Dict[str, int]:
    """
    Merge ``{state}/{type}/{numeric}/`` policy-cache folders into ``{place_slug}_{geoid}/``.

    Handles legacy ids that dropped leading zeros (``159472`` → ``phenix_city_0159472``).
    """
    cache_dir = cache_dir.resolve()
    stats: Dict[str, int] = defaultdict(int)
    rows = list(jurisdictions) if jurisdictions is not None else load_int_jurisdictions_for_numeric_migration(
        database_url or _database_url() or ""
    )
    if not rows:
        stats["skipped_no_jurisdictions"] += 1
        return dict(stats)

    mapping = build_numeric_policy_folder_mapping(
        cache_dir,
        rows,
        jurisdiction_id_filter=jurisdiction_id,
    )
    stats["mapped"] = len(mapping)

    for legacy, canonical in sorted(mapping.items()):
        dest_folder = jurisdiction_cache_folder_name(canonical)
        segment = cache_type_segment(canonical)
        dest_paths: List[Path] = []

        for geo in list(cache_dir.glob("*/" + segment + "/" + legacy)):
            if not geo.is_dir():
                continue
            dest_geo = geo.parent / dest_folder
            if dest_geo.resolve() == geo.resolve():
                stats["already_named"] += 1
                dest_paths.append(dest_geo)
                continue
            if dest_geo.exists():
                if dry_run:
                    stats["would_merge"] += 1
                else:
                    _merge_policy_dir_contents(geo, dest_geo, dry_run=False)
                    if not any(geo.iterdir()):
                        geo.rmdir()
                    stats["merged"] += 1
            elif dry_run:
                stats["would_rename"] += 1
            else:
                shutil.move(str(geo), str(dest_geo))
                stats["renamed"] += 1
            dest_paths.append(dest_geo)

        for dest in dest_paths:
            if dest.is_dir():
                _patch_policy_cache_json_jurisdiction_id(dest, canonical, dry_run=dry_run)
                stats["json_patched_roots"] += 1

    return dict(stats)
