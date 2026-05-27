#!/usr/bin/env python3
"""League / state municipal league directories pipeline: load cached
``cities.json`` files into bronze.bronze_jurisdictions_municipalities_league.

Ported from load_league_city_directories_to_bronze.py to the core_lib
DataSourcePipeline contract.

Reads every ``data/cache/leagueofcities/<USPS>/cities.json`` produced by
``download_league_city_directories.py``.

Table:
    bronze.bronze_jurisdictions_municipalities_league

``jurisdiction_id`` (and ``census_geoid``) are filled when a row matches
``bronze.bronze_jurisdictions_municipalities`` on state + place name (exact,
normalized label, fuzzy prefix/ratio), or by matching the league ``website`` host
to a municipality homepage already known in ``intermediate.int_jurisdiction_websites``
(within the same state).

Each city field from the JSON (name, contact fields, source_*, ``state_usps`` on
the file / row for matching, ``alternate_names``, ``raw_row``, etc.) is stored in
typed columns (directory ``state_usps`` / ``state_name`` map to ``state_code`` /
``state``); there is no ``raw_city_json`` blob.

Usage:
    python -m ingestion.leagueofcities.directories
    python -m ingestion.leagueofcities.directories --states AL TX
    python -m ingestion.leagueofcities.directories --truncate
    python -m ingestion.leagueofcities.directories --rematch-jurisdictions --states CA

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded psycopg2 connection to localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, AsyncIterator
from urllib.parse import urlparse

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/leagueofcities")

BRONZE_TABLE = "bronze.bronze_jurisdictions_municipalities_league"
CENSUS_TABLE = "bronze.bronze_jurisdictions_municipalities"


# --------------------------------------------------------------------------- #
# Pure helpers (preserved verbatim from the original loader)
# --------------------------------------------------------------------------- #
# league_website_sanitize: normalize league municipal ``website`` values.
# Rejects scheme-only URLs (e.g. ``https://`` from empty iMIS website cells),
# broken double schemes, and hosts without a domain label.

# Bare scheme or scheme + slash only (common when directory cell is empty).
_SCHEME_ONLY_RE = re.compile(r"^https?://\s*/?\s*$", re.I)

_JUNK_LITERALS = frozenset(
    {
        "https://",
        "http://",
        "https://)",
        "http://)",
        "https:",
        "http:",
    }
)

_LOOSE_DOMAIN_RE = re.compile(
    r"^[a-z0-9][a-z0-9.-]*\.[a-z]{2,}(/[^\s]*)?$",
    re.I,
)


def fix_double_scheme_url(url: str) -> str:
    """``http://https://example.com`` → ``https://example.com``."""
    u = (url or "").strip()
    if not u:
        return u
    m = re.match(r"^https?://(https?://.+)$", u, re.DOTALL)
    if m:
        return m.group(1).strip()
    return u


def _has_usable_netloc(netloc: str) -> bool:
    host = (netloc or "").strip().lower()
    if not host or host in ("https", "http"):
        return False
    if "." not in host:
        return False
    return True


def sanitize_league_website(url: str | None) -> str | None:
    """
    Return a normalized ``https://host…`` URL, or ``None`` if missing / unusable.
    """
    if url is None:
        return None
    s = fix_double_scheme_url(str(url).strip())
    if not s or s in _JUNK_LITERALS or _SCHEME_ONLY_RE.match(s):
        return None

    if not re.match(r"^https?://", s, re.I):
        if re.match(r"^www\.[a-z0-9.-]+\.[a-z]{2,}(/.*)?$", s, re.I):
            s = "https://" + s
        elif _LOOSE_DOMAIN_RE.match(s):
            s = "https://" + s.lstrip("/")
        else:
            return None

    try:
        p = urlparse(s)
    except Exception:
        return None
    if p.scheme not in ("http", "https"):
        return None
    if not _has_usable_netloc(p.netloc):
        return None

    low = s.lower()
    if low.startswith("http://"):
        s = "https://" + s[7:]
    return s.rstrip("/") if s.count("/") == 2 and s.endswith("/") else s


_WS = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_ST_LEAD_RE = re.compile(r"^\s*st\.\s+", re.IGNORECASE)
_ST_MID_RE = re.compile(r"(^|[^a-z])st\.\s+", re.IGNORECASE)
_SUFFIX_RE = re.compile(
    r"\s+(city|town|township|village|borough|county|parish|municipality|cdp)\s*$",
    re.IGNORECASE,
)
_PREFIX_RE = re.compile(
    r"^(city|town|village|borough|county|township|parish)\s+of\s+",
    re.IGNORECASE,
)
_FUZZY_RATIO_MIN = 0.92
_JUNK_NAME_RE = re.compile(
    r"^\s*\d|^\s*\d+\s*\(|%\)|\d+\s*to\s*\d+\s*$|\(\s*\d+\s*%",
    re.IGNORECASE,
)


def _str(val: Any, maxlen: int | None = None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def _league_website(val: Any) -> str | None:
    """Bronze ``website`` column: null scheme-only / empty hosts."""
    return sanitize_league_website(_str(val))


def _raw_row_json(city: dict[str, Any]) -> list[Any]:
    """``raw_row`` JSONB payload: the original list, or [] when absent/malformed."""
    rr = city.get("raw_row")
    if isinstance(rr, list):
        return rr
    return []


def _norm_placename(name: str) -> str:
    """Align with dbt ``normalize_jurisdiction_label_for_match`` (St./Saint, parish, suffixes)."""
    s = name.strip().lower()
    s = _ST_LEAD_RE.sub("saint ", s)
    s = _ST_MID_RE.sub(r"\1saint ", s)
    s = _PREFIX_RE.sub("", s)
    s = _SUFFIX_RE.sub("", s)
    s = re.sub(r"\s+parish$", " county", s, flags=re.IGNORECASE)
    s = _NON_ALNUM.sub(" ", s)
    s = _WS.sub(" ", s).strip()
    return s


def _website_origin_norm(url: str | None) -> str | None:
    """Canonical https://host for URL ↔ jurisdiction matching (matches int_jurisdiction_websites)."""
    u = sanitize_league_website(url)
    if not u:
        return None
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u.lstrip("/")
    low = re.sub(r"^http:", "https:", u.lower(), count=1)
    low = re.sub(r"^https://www\.", "https://", low, count=1)
    low = low.rstrip("/")
    m = re.match(r"^(https://[^/?#]+)", low)
    return m.group(1) if m else None


def _row_key(
    state_usps: str,
    municipality_name: str,
    league_profile_url: str | None,
    source_detail: str | None,
) -> str:
    payload = "\x1f".join(
        [
            state_usps.upper(),
            municipality_name.strip(),
            (league_profile_url or "").strip(),
            (source_detail or "").strip(),
        ]
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def _should_attempt_jurisdiction_match(name: str) -> bool:
    n = name.strip()
    if len(n) < 2:
        return False
    if _JUNK_NAME_RE.search(n):
        return False
    return True


class CensusPlaceIndex:
    """In-memory index for (usps, name) → Census place rows."""

    def __init__(self) -> None:
        self._by_exact: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
        self._by_norm: dict[tuple[str, str], list[tuple[str, str, str]]] = defaultdict(list)
        self._by_state: dict[str, list[tuple[str, str, str, str]]] = defaultdict(list)

    def add(self, usps: str, place_name: str, geoid: str, jurisdiction_id: str) -> None:
        u = usps.upper()
        key_exact = (u, place_name.strip().lower())
        self._by_exact[key_exact].append((place_name, geoid, jurisdiction_id))
        nn = _norm_placename(place_name)
        if nn:
            self._by_norm[(u, nn)].append((place_name, geoid, jurisdiction_id))
            self._by_state[u].append((nn, place_name, geoid, jurisdiction_id))

    def match(
        self,
        usps: str,
        league_name: str,
        *,
        website: str | None = None,
        url_idx: dict[tuple[str, str], list[tuple[str, str]]] | None = None,
    ) -> tuple[str | None, str | None, str | None]:
        """
        Returns (jurisdiction_id, geoid, method) or (None, None, 'unmatched').
        """
        u = usps.upper()
        raw = league_name.strip()
        if not raw:
            return None, None, None

        # Exact case-insensitive match on full Census place name
        exact_key = (u, raw.lower())
        cands = self._by_exact.get(exact_key, [])
        if len(cands) == 1:
            _pn, geoid, jid = cands[0]
            return jid, geoid, "place_name_exact"
        if len(cands) > 1:
            return None, None, "ambiguous_exact"

        nn = _norm_placename(raw)
        if nn:
            nc = self._by_norm.get((u, nn), [])
            if len(nc) == 1:
                _pn, geoid, jid = nc[0]
                return jid, geoid, "place_name_normalized"
            if len(nc) > 1:
                hits = [t for t in nc if t[0].strip().lower() == raw.lower()]
                if len(hits) == 1:
                    _pn, geoid, jid = hits[0]
                    return jid, geoid, "place_name_normalized_disambiguated"
                return None, None, "ambiguous_normalized"

            prefix_hits: list[tuple[str, str, str]] = []
            for j_norm, place_name, geoid, jid in self._by_state.get(u, []):
                if j_norm == nn:
                    continue
                if j_norm.startswith(nn + " ") or nn.startswith(j_norm + " "):
                    prefix_hits.append((place_name, geoid, jid))
            if len(prefix_hits) == 1:
                _pn, geoid, jid = prefix_hits[0]
                return jid, geoid, "place_name_fuzzy_prefix"
            if len(prefix_hits) > 1:
                dis = [t for t in prefix_hits if t[0].strip().lower() == raw.lower()]
                if len(dis) == 1:
                    _pn, geoid, jid = dis[0]
                    return jid, geoid, "place_name_fuzzy_prefix_disambiguated"
                return None, None, "ambiguous_fuzzy_prefix"

            if len(nn) >= 4:
                scored: list[tuple[float, str, str, str]] = []
                for j_norm, place_name, geoid, jid in self._by_state.get(u, []):
                    ratio = SequenceMatcher(None, nn, j_norm).ratio()
                    if ratio >= _FUZZY_RATIO_MIN:
                        scored.append((ratio, place_name, geoid, jid))
                scored.sort(key=lambda t: (-t[0], t[1]))
                if len(scored) == 1:
                    _r, _pn, geoid, jid = scored[0]
                    return jid, geoid, "place_name_fuzzy_ratio"
                if len(scored) > 1 and scored[0][0] - scored[1][0] >= 0.04:
                    _r, _pn, geoid, jid = scored[0]
                    return jid, geoid, "place_name_fuzzy_ratio"

        origin = _website_origin_norm(website)
        if origin and url_idx is not None:
            url_cands = url_idx.get((u, origin), [])
            if len(url_cands) == 1:
                jid, geoid = url_cands[0]
                return jid, geoid, "website_url_state"
            if len(url_cands) > 1:
                return None, None, "ambiguous_website_url"

        return None, None, "unmatched"


def iter_city_files(states: set[str] | None) -> list[Path]:
    if not CACHE_DIR.is_dir():
        return []
    paths: list[Path] = []
    for p in sorted(CACHE_DIR.glob("*/cities.json")):
        st = p.parent.name.upper()
        if len(st) != 2:
            continue
        if states is not None and st not in states:
            continue
        paths.append(p)
    return paths


def parse_city_file(
    path: Path,
    idx: CensusPlaceIndex | None = None,
    url_idx: dict[tuple[str, str], list[tuple[str, str]]] | None = None,
) -> list[dict[str, Any]]:
    """Parse one ``cities.json`` into normalized field dicts (no envelope)."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(doc, dict):
        return []
    file_state_code = _str(doc.get("state_usps"), 2)
    if not file_state_code:
        file_state_code = path.parent.name.upper()[:2]
    file_state_code = file_state_code.upper()
    file_state_name = _str(doc.get("state_name"))
    league_org = _str(doc.get("league_organization"))
    league_base = _str(doc.get("league_base_url"))
    extracted_at = doc.get("extracted_at")
    extraction_status = _str(doc.get("extraction_status"))
    cities = doc.get("cities")
    if not isinstance(cities, list):
        return []

    rows: list[dict[str, Any]] = []
    for c in cities:
        if not isinstance(c, dict):
            continue
        muni = _str(c.get("name"), 500)
        if not muni:
            continue
        profile = _str(c.get("league_profile_url"))
        detail = _str(c.get("source_detail"))
        muni_state = _str(c.get("state_usps"), 2)
        if muni_state:
            muni_state = muni_state.upper()
        match_usps = muni_state or file_state_code
        rk = _row_key(match_usps, muni, profile, detail)

        pop = c.get("population")
        population_raw = None if pop is None else str(pop)

        jid: str | None = None
        geoid: str | None = None
        match_method: str | None = None
        league_website = _league_website(c.get("website"))
        if idx is not None and _should_attempt_jurisdiction_match(muni):
            jid, geoid, match_method = idx.match(
                match_usps,
                muni,
                website=league_website,
                url_idx=url_idx,
            )
            if jid is None and match_method == "unmatched":
                alts = c.get("alternate_names")
                if isinstance(alts, list):
                    for alt in alts:
                        if not isinstance(alt, str):
                            continue
                        if not _should_attempt_jurisdiction_match(alt):
                            continue
                        jid, geoid, mm = idx.match(
                            match_usps,
                            alt,
                            website=league_website,
                            url_idx=url_idx,
                        )
                        if jid and mm:
                            match_method = f"alternate_{mm}"
                            break

        alt_names = c.get("alternate_names") if isinstance(c.get("alternate_names"), list) else []
        rows.append(
            {
                "row_key": rk,
                "state_code": file_state_code,
                "state": file_state_name,
                "league_organization": league_org,
                "league_base_url": league_base,
                "league_state_extracted_at": extracted_at,
                "state_extraction_status": extraction_status,
                "municipality_name": muni,
                "population_raw": population_raw,
                "county": _str(c.get("county")),
                "mayor": _str(c.get("mayor")),
                "website": _league_website(c.get("website")),
                "phone": _str(c.get("phone"), 120),
                "email": _str(c.get("email")),
                "address": _str(c.get("address")),
                "municipality_type": _str(c.get("municipality_type")),
                "source_url": _str(c.get("source_url")),
                "source_kind": _str(c.get("source_kind")),
                "source_detail": detail,
                "league_profile_url": profile,
                "alternate_names": alt_names,
                "municipality_state_usps": muni_state,
                "raw_row": _raw_row_json(c),
                "census_geoid": geoid,
                "jurisdiction_id": jid,
                "jurisdiction_match_method": match_method,
            }
        )
    return rows


# --------------------------------------------------------------------------- #
# Row schema
# --------------------------------------------------------------------------- #
class LeagueDirectoryRow(RawRow):
    """One League municipal directory row, validated before upsert."""

    row_key: str = Field(min_length=1)
    state_code: str = Field(min_length=1, max_length=2)
    state: str | None = None
    league_organization: str | None = None
    league_base_url: str | None = None
    league_state_extracted_at: str | None = None
    state_extraction_status: str | None = None
    municipality_name: str = Field(min_length=1, max_length=500)
    population_raw: str | None = None
    county: str | None = None
    mayor: str | None = None
    website: str | None = None
    phone: str | None = Field(default=None, max_length=120)
    email: str | None = None
    address: str | None = None
    municipality_type: str | None = None
    source_url: str | None = None
    source_kind: str | None = None
    source_detail: str | None = None
    league_profile_url: str | None = None
    alternate_names: list[Any] = Field(default_factory=list)
    municipality_state_usps: str | None = Field(default=None, max_length=2)
    raw_row: list[Any] = Field(default_factory=list)
    census_geoid: str | None = Field(default=None, max_length=7)
    jurisdiction_id: str | None = None
    jurisdiction_match_method: str | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    f"""
    CREATE TABLE IF NOT EXISTS {BRONZE_TABLE} (
        row_key                      TEXT          PRIMARY KEY,
        state_code                   VARCHAR(2)    NOT NULL,
        state                        TEXT,
        league_organization          TEXT,
        league_base_url              TEXT,
        league_state_extracted_at    TIMESTAMPTZ,
        state_extraction_status      TEXT,
        municipality_name            VARCHAR(500)  NOT NULL,
        population_raw               TEXT,
        county                       TEXT,
        mayor                        TEXT,
        website                      TEXT,
        phone                        VARCHAR(120),
        email                        TEXT,
        address                      TEXT,
        municipality_type            TEXT,
        source_url                   TEXT,
        source_kind                  TEXT,
        source_detail                TEXT,
        league_profile_url           TEXT,
        alternate_names              JSONB         NOT NULL DEFAULT '[]'::jsonb,
        municipality_state_usps      VARCHAR(2),
        raw_row                      JSONB         NOT NULL DEFAULT '[]'::jsonb,
        census_geoid                 VARCHAR(7),
        jurisdiction_id              TEXT,
        jurisdiction_match_method    TEXT,
        ingestion_date               TIMESTAMPTZ   NOT NULL DEFAULT NOW()
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        f"CREATE INDEX IF NOT EXISTS idx_bjmleague_state "
        f"ON {BRONZE_TABLE} (state_code)"
    ),
    text(
        f"CREATE INDEX IF NOT EXISTS idx_bjmleague_jurisdiction_id "
        f"ON {BRONZE_TABLE} (jurisdiction_id) "
        f"WHERE jurisdiction_id IS NOT NULL"
    ),
    text(
        f"CREATE INDEX IF NOT EXISTS idx_bjmleague_geoid "
        f"ON {BRONZE_TABLE} (census_geoid) "
        f"WHERE census_geoid IS NOT NULL"
    ),
)

_TRUNCATE_SQL = text(f"TRUNCATE TABLE {BRONZE_TABLE}")

_UPSERT_SQL = text(
    f"""
    INSERT INTO {BRONZE_TABLE} (
        row_key, state_code, state, league_organization, league_base_url,
        league_state_extracted_at, state_extraction_status,
        municipality_name, population_raw, county, mayor, website, phone, email, address,
        municipality_type, source_url, source_kind, source_detail, league_profile_url,
        alternate_names, municipality_state_usps, raw_row,
        census_geoid, jurisdiction_id, jurisdiction_match_method
    ) VALUES (
        :row_key, :state_code, :state, :league_organization, :league_base_url,
        :league_state_extracted_at, :state_extraction_status,
        :municipality_name, :population_raw, :county, :mayor, :website, :phone, :email, :address,
        :municipality_type, :source_url, :source_kind, :source_detail, :league_profile_url,
        CAST(:alternate_names AS JSONB), :municipality_state_usps, CAST(:raw_row AS JSONB),
        :census_geoid, :jurisdiction_id, :jurisdiction_match_method
    )
    ON CONFLICT (row_key) DO UPDATE SET
        state_code                     = EXCLUDED.state_code,
        state                          = EXCLUDED.state,
        league_organization          = EXCLUDED.league_organization,
        league_base_url              = EXCLUDED.league_base_url,
        league_state_extracted_at    = EXCLUDED.league_state_extracted_at,
        state_extraction_status      = EXCLUDED.state_extraction_status,
        municipality_name            = EXCLUDED.municipality_name,
        population_raw               = EXCLUDED.population_raw,
        county                       = EXCLUDED.county,
        mayor                        = EXCLUDED.mayor,
        website                      = EXCLUDED.website,
        phone                        = EXCLUDED.phone,
        email                        = EXCLUDED.email,
        address                      = EXCLUDED.address,
        municipality_type            = EXCLUDED.municipality_type,
        source_url                   = EXCLUDED.source_url,
        source_kind                  = EXCLUDED.source_kind,
        source_detail                = EXCLUDED.source_detail,
        league_profile_url           = EXCLUDED.league_profile_url,
        alternate_names              = EXCLUDED.alternate_names,
        municipality_state_usps      = EXCLUDED.municipality_state_usps,
        raw_row                      = EXCLUDED.raw_row,
        census_geoid                 = EXCLUDED.census_geoid,
        jurisdiction_id              = EXCLUDED.jurisdiction_id,
        jurisdiction_match_method    = EXCLUDED.jurisdiction_match_method,
        ingestion_date               = NOW()
    """
)

_REMATCH_SQL = text(
    f"""
    UPDATE {BRONZE_TABLE}
    SET jurisdiction_id = :jurisdiction_id,
        census_geoid = :census_geoid,
        jurisdiction_match_method = :jurisdiction_match_method,
        ingestion_date = NOW()
    WHERE row_key = :row_key
    """
)


async def load_census_index(session: AsyncSession) -> CensusPlaceIndex:
    idx = CensusPlaceIndex()
    result = await session.execute(
        text(
            f"""
            SELECT usps, name, geoid, jurisdiction_id
            FROM {CENSUS_TABLE}
            WHERE usps IS NOT NULL AND name IS NOT NULL
            """
        )
    )
    for usps, name, geoid, jid in result.fetchall():
        if not usps or not name or not geoid or not jid:
            continue
        idx.add(str(usps), str(name), str(geoid), str(jid))
    return idx


async def load_url_jurisdiction_index(
    session: AsyncSession,
) -> dict[tuple[str, str], list[tuple[str, str]]]:
    """
    (state_usps, https://host) → [(jurisdiction_id, geoid), …] from known municipality homepages.
    """
    idx: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    sql_variants = (
        """
        SELECT DISTINCT
            UPPER(TRIM(j.state_code)) AS state_code,
            (regexp_match(
                NULLIF(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(
                                LOWER(
                                    CASE
                                        WHEN w.website_url ~* '^https?://' THEN TRIM(w.website_url)
                                        ELSE 'https://' || TRIM(REGEXP_REPLACE(w.website_url, '^/+', ''))
                                    END
                                ),
                                '^http:', 'https:', 'i'
                            ),
                            '^https://www\\.', 'https://', 'i'
                        ),
                        '/+$', '', 'g'
                    ),
                    ''
                ),
                '^(https://[^/?#]+)'
            ))[1] AS origin_norm,
            w.jurisdiction_id,
            j.geoid
        FROM intermediate.int_jurisdiction_websites w
        INNER JOIN intermediate.int_jurisdictions j
            ON j.jurisdiction_id = w.jurisdiction_id
        WHERE j.jurisdiction_type = 'municipality'
          AND w.jurisdiction_id IS NOT NULL
          AND w.website_url IS NOT NULL
          AND TRIM(w.website_url) <> ''
        """,
        """
        SELECT DISTINCT
            UPPER(TRIM(u.state_code)) AS state_code,
            (regexp_match(
                NULLIF(
                    REGEXP_REPLACE(
                        REGEXP_REPLACE(
                            REGEXP_REPLACE(
                                LOWER(
                                    CASE
                                        WHEN u.city_website ~* '^https?://' THEN TRIM(u.city_website)
                                        ELSE 'https://' || TRIM(REGEXP_REPLACE(u.city_website, '^/+', ''))
                                    END
                                ),
                                '^http:', 'https:', 'i'
                            ),
                            '^https://www\\.', 'https://', 'i'
                        ),
                        '/+$', '', 'g'
                    ),
                    ''
                ),
                '^(https://[^/?#]+)'
            ))[1] AS origin_norm,
            m.jurisdiction_id,
            m.geoid
        FROM bronze.bronze_jurisdictions_municipalities_uscm u
        INNER JOIN bronze.bronze_jurisdictions_municipalities m
            ON UPPER(TRIM(m.usps)) = UPPER(TRIM(u.state_code))
           AND LOWER(TRIM(m.name)) = LOWER(TRIM(u.municipality_name))
        WHERE u.city_website IS NOT NULL
          AND TRIM(u.city_website) <> ''
          AND m.jurisdiction_id IS NOT NULL
        """,
    )
    for sql in sql_variants:
        try:
            result = await session.execute(text(sql))
        except Exception:
            continue
        for state_code, origin, jid, geoid in result.fetchall():
            if not state_code or not origin or not jid or not geoid:
                continue
            pair = (str(jid), str(geoid))
            bucket = idx[(str(state_code).upper(), str(origin))]
            if pair not in bucket:
                bucket.append(pair)
        if idx:
            break
    return idx


class LeagueOfCitiesDirectoriesPipeline(DataSourcePipeline[LeagueDirectoryRow]):
    source = "leagueofcities_directories"
    batch_size = 2_000
    row_schema = LeagueDirectoryRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        limit: int | None = None,
        states: set[str] | None = None,
        census_index: CensusPlaceIndex | None = None,
        url_index: dict[tuple[str, str], list[tuple[str, str]]] | None = None,
    ):
        self._cache_root = path
        self._limit = limit
        self._states = states
        self._census_index = census_index
        self._url_index = url_index

    def _discover_paths(self) -> list[Path]:
        root = self._cache_root or CACHE_DIR
        if not root.is_dir():
            return []
        paths: list[Path] = []
        for p in sorted(root.glob("*/cities.json")):
            st = p.parent.name.upper()
            if len(st) != 2:
                continue
            if self._states is not None and st not in self._states:
                continue
            paths.append(p)
        return paths

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        emitted = 0
        for path in self._discover_paths():
            for rec in parse_city_file(path, self._census_index, self._url_index):
                if self._limit is not None and emitted >= self._limit:
                    return
                yield {
                    "source": self.source,
                    "source_version": path.parent.name.upper(),
                    "natural_key": rec["row_key"],
                    **rec,
                }
                emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[LeagueDirectoryRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "row_key": r.row_key,
                "state_code": r.state_code,
                "state": r.state,
                "league_organization": r.league_organization,
                "league_base_url": r.league_base_url,
                "league_state_extracted_at": r.league_state_extracted_at,
                "state_extraction_status": r.state_extraction_status,
                "municipality_name": r.municipality_name,
                "population_raw": r.population_raw,
                "county": r.county,
                "mayor": r.mayor,
                "website": r.website,
                "phone": r.phone,
                "email": r.email,
                "address": r.address,
                "municipality_type": r.municipality_type,
                "source_url": r.source_url,
                "source_kind": r.source_kind,
                "source_detail": r.source_detail,
                "league_profile_url": r.league_profile_url,
                "alternate_names": json.dumps(r.alternate_names),
                "municipality_state_usps": r.municipality_state_usps,
                "raw_row": json.dumps(r.raw_row, default=str),
                "census_geoid": r.census_geoid,
                "jurisdiction_id": r.jurisdiction_id,
                "jurisdiction_match_method": r.jurisdiction_match_method,
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


async def _rematch_bronze_jurisdiction_ids(
    idx: CensusPlaceIndex,
    url_idx: dict[tuple[str, str], list[tuple[str, str]]],
    *,
    states: set[str] | None,
) -> dict[str, int]:
    where = ""
    params: dict[str, Any] = {}
    if states:
        where = "WHERE state_code = ANY(:states)"
        params["states"] = list(states)

    async with async_session() as session:
        result = await session.execute(
            text(
                f"""
                SELECT row_key, state_code, municipality_name, website, alternate_names
                FROM {BRONZE_TABLE}
                {where}
                """
            ),
            params or None,
        )
        rows = result.fetchall()

    updates: list[dict[str, Any]] = []
    for row_key, state_code, muni, website, alts_json in rows:
        match_usps = str(state_code or "").upper()[:2]
        muni_s = str(muni or "").strip()
        website_s = _league_website(website)
        jid: str | None = None
        geoid: str | None = None
        method: str | None = None
        if _should_attempt_jurisdiction_match(muni_s):
            jid, geoid, method = idx.match(
                match_usps,
                muni_s,
                website=website_s,
                url_idx=url_idx,
            )
            if jid is None and method == "unmatched":
                alts = alts_json if isinstance(alts_json, list) else []
                if isinstance(alts_json, str):
                    try:
                        alts = json.loads(alts_json)
                    except json.JSONDecodeError:
                        alts = []
                if isinstance(alts, list):
                    for alt in alts:
                        if not isinstance(alt, str) or not _should_attempt_jurisdiction_match(alt):
                            continue
                        jid, geoid, mm = idx.match(
                            match_usps,
                            alt,
                            website=website_s,
                            url_idx=url_idx,
                        )
                        if jid and mm:
                            method = f"alternate_{mm}"
                            break
        updates.append(
            {
                "jurisdiction_id": jid,
                "census_geoid": geoid,
                "jurisdiction_match_method": method,
                "row_key": str(row_key),
            }
        )

    if updates:
        async with async_session() as session:
            await session.execute(_REMATCH_SQL, updates)
    with_j = sum(1 for u in updates if u["jurisdiction_id"])
    return {"rows": len(updates), "with_jurisdiction_id": with_j}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load League city directory JSON into bronze_jurisdictions_municipalities_league"
    )
    parser.add_argument(
        "--states",
        nargs="*",
        help="Optional USPS state codes (default: all states under cache root)",
    )
    parser.add_argument("--limit", type=int, help="Limit number of rows extracted (for testing)")
    parser.add_argument("--truncate", action="store_true")
    parser.add_argument(
        "--rematch-jurisdictions",
        action="store_true",
        help="Re-resolve jurisdiction_id on existing bronze rows (no JSON re-parse)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    st_filter = None
    if args.states:
        st_filter = {s.strip().upper() for s in args.states if len(s.strip()) == 2}

    await _prepare_target(args.truncate)

    async with async_session() as session:
        idx = await load_census_index(session)
        url_idx = await load_url_jurisdiction_index(session)

    if args.rematch_jurisdictions:
        await _rematch_bronze_jurisdiction_ids(idx, url_idx, states=st_filter)
        return

    pipeline = LeagueOfCitiesDirectoriesPipeline(
        limit=args.limit,
        states=st_filter,
        census_index=idx,
        url_index=url_idx,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
