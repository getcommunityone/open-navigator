#!/usr/bin/env python3
"""
Load cached League / state municipal league ``cities.json`` files into bronze.

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

Database URL: ``scripts/database/target_database_url.py`` (same as other loaders).

Usage:
    ./.venv/bin/python scripts/datasources/leagueofcities/load_league_city_directories_to_bronze.py
    ./.venv/bin/python scripts/datasources/leagueofcities/load_league_city_directories_to_bronze.py --states AL TX
    ./.venv/bin/python scripts/datasources/leagueofcities/load_league_city_directories_to_bronze.py --truncate --dry-run
    ./.venv/bin/python scripts/datasources/leagueofcities/load_league_city_directories_to_bronze.py --rematch-jurisdictions --states CA
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.datasources.leagueofcities.league_website_sanitize import sanitize_league_website
_VENV_REEXEC = "_OPEN_NAVIGATOR_LEAGUE_LOAD_VENV_REEXEC"


def _in_project_venv() -> bool:
    px = Path(sys.prefix).resolve()
    return px in {
        (_ROOT / ".venv").resolve(),
        (_ROOT / ".venv-dbt").resolve(),
    }


def _maybe_reexec_with_project_venv() -> None:
    if os.environ.get(_VENV_REEXEC) == "1":
        return
    if _in_project_venv():
        return
    for name in (".venv", ".venv-dbt"):
        vpy = _ROOT / name / "bin" / "python"
        if vpy.is_file():
            os.environ[_VENV_REEXEC] = "1"
            os.execv(str(vpy), [str(vpy)] + sys.argv)


try:
    import psycopg2
    from psycopg2.extensions import connection as PGConnection
    from psycopg2.extensions import cursor as PGCursor
    from psycopg2.extras import execute_batch
    from dotenv import load_dotenv
    from loguru import logger
except ImportError:
    _maybe_reexec_with_project_venv()
    print(
        "Need psycopg2-binary, python-dotenv, loguru. "
        "cd repo root && ./.venv/bin/pip install -r requirements.txt",
        file=sys.stderr,
    )
    sys.exit(1)

sys.path.insert(0, str(_ROOT))

load_dotenv(_ROOT / ".env")
load_dotenv()

from scripts.database.target_database_url import resolve_target_database_url

DATABASE_URL = resolve_target_database_url()

CACHE_ROOT = _ROOT / "data" / "cache" / "leagueofcities"

BRONZE_TABLE = "bronze.bronze_jurisdictions_municipalities_league"
CENSUS_TABLE = "bronze.bronze_jurisdictions_municipalities"

CREATE_SQL = f"""
    CREATE SCHEMA IF NOT EXISTS bronze;

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
    );

    CREATE INDEX IF NOT EXISTS idx_bjmleague_state
        ON {BRONZE_TABLE} (state_code);
    CREATE INDEX IF NOT EXISTS idx_bjmleague_jurisdiction_id
        ON {BRONZE_TABLE} (jurisdiction_id)
        WHERE jurisdiction_id IS NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_bjmleague_geoid
        ON {BRONZE_TABLE} (census_geoid)
        WHERE census_geoid IS NOT NULL;
"""

EVOLVE_LEAGUE_SCHEMA_SQL: tuple[str, ...] = (
    r"""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name = 'bronze_jurisdictions_municipalities_league'
          AND column_name = 'state_usps'
    ) THEN
        EXECUTE $rn$
            ALTER TABLE bronze.bronze_jurisdictions_municipalities_league
                RENAME COLUMN state_usps TO state_code
        $rn$;
    END IF;
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name = 'bronze_jurisdictions_municipalities_league'
          AND column_name = 'state_name'
    ) THEN
        EXECUTE $rn2$
            ALTER TABLE bronze.bronze_jurisdictions_municipalities_league
                RENAME COLUMN state_name TO state
        $rn2$;
    END IF;
END$$;
""",
    f"ALTER TABLE {BRONZE_TABLE} ADD COLUMN IF NOT EXISTS municipality_state_usps VARCHAR(2)",
    f"ALTER TABLE {BRONZE_TABLE} ADD COLUMN IF NOT EXISTS raw_row JSONB NOT NULL DEFAULT '[]'::jsonb",
    r"""
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'bronze'
          AND table_name = 'bronze_jurisdictions_municipalities_league'
          AND column_name = 'raw_city_json'
    ) THEN
        EXECUTE $mig$
            UPDATE bronze.bronze_jurisdictions_municipalities_league
            SET
                municipality_state_usps = COALESCE(
                    NULLIF(TRIM(UPPER(raw_city_json->>'state_usps')), ''),
                    municipality_state_usps
                ),
                raw_row = CASE
                    WHEN raw_city_json ? 'raw_row'
                         AND jsonb_typeof(raw_city_json->'raw_row') = 'array'
                    THEN raw_city_json->'raw_row'
                    ELSE raw_row
                END
            WHERE raw_city_json IS NOT NULL
              AND raw_city_json <> '{}'::jsonb
        $mig$;
    END IF;
END$$;
""",
    f"ALTER TABLE {BRONZE_TABLE} DROP COLUMN IF EXISTS raw_city_json",
)


def evolve_league_table_schema(cur: PGCursor) -> None:
    """Rename legacy state columns; upgrade pre-030 tables (raw_city_json) to municipality_state_usps + raw_row."""
    for stmt in EVOLVE_LEAGUE_SCHEMA_SQL:
        cur.execute(stmt)


UPSERT_SQL = f"""
    INSERT INTO {BRONZE_TABLE} (
        row_key, state_code, state, league_organization, league_base_url,
        league_state_extracted_at, state_extraction_status,
        municipality_name, population_raw, county, mayor, website, phone, email, address,
        municipality_type, source_url, source_kind, source_detail, league_profile_url,
        alternate_names, municipality_state_usps, raw_row,
        census_geoid, jurisdiction_id, jurisdiction_match_method
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb,
        %s, %s, %s
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


def _database_url_source_label() -> str:
    if (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip():
        return "OPEN_NAVIGATOR_DATABASE_URL"
    if (os.getenv("NEON_DATABASE_URL_DEV") or "").strip():
        return "NEON_DATABASE_URL_DEV"
    if (os.getenv("NEON_DATABASE_URL") or "").strip():
        return "NEON_DATABASE_URL"
    return "default local (localhost:5433/open_navigator)"


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


def _raw_row_json(city: dict[str, Any]) -> str:
    rr = city.get("raw_row")
    if isinstance(rr, list):
        return json.dumps(rr, default=str)
    return "[]"


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
        url_idx: dict[tuple[str, str], list[tuple[str, str, str]]] | None = None,
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


def load_census_index(conn) -> CensusPlaceIndex:
    idx = CensusPlaceIndex()
    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT usps, name, geoid, jurisdiction_id
            FROM {CENSUS_TABLE}
            WHERE usps IS NOT NULL AND name IS NOT NULL
            """
        )
        for usps, name, geoid, jid in cur.fetchall():
            if not usps or not name or not geoid or not jid:
                continue
            idx.add(str(usps), str(name), str(geoid), str(jid))
    return idx


def load_url_jurisdiction_index(conn) -> dict[tuple[str, str], list[tuple[str, str]]]:
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
    with conn.cursor() as cur:
        for sql in sql_variants:
            try:
                cur.execute(sql)
            except Exception as e:
                logger.debug(f"URL index query skipped: {e}")
                continue
            for state_code, origin, jid, geoid in cur.fetchall():
                if not state_code or not origin or not jid or not geoid:
                    continue
                pair = (str(jid), str(geoid))
                bucket = idx[(str(state_code).upper(), str(origin))]
                if pair not in bucket:
                    bucket.append(pair)
            if idx:
                break
    return idx


def iter_city_files(states: set[str] | None) -> list[Path]:
    if not CACHE_ROOT.is_dir():
        return []
    paths: list[Path] = []
    for p in sorted(CACHE_ROOT.glob("*/cities.json")):
        st = p.parent.name.upper()
        if len(st) != 2:
            continue
        if states is not None and st not in states:
            continue
        paths.append(p)
    return paths


def parse_city_files(
    paths: list[Path],
    idx: CensusPlaceIndex,
    url_idx: dict[tuple[str, str], list[tuple[str, str]]] | None = None,
) -> list[tuple[Any, ...]]:
    rows: list[tuple[Any, ...]] = []
    for path in paths:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"Skip {path}: {e}")
            continue
        if not isinstance(doc, dict):
            continue
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
            continue

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
            if _should_attempt_jurisdiction_match(muni):
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

            alt_json = json.dumps(c.get("alternate_names") if isinstance(c.get("alternate_names"), list) else [])
            rows.append(
                (
                    rk,
                    file_state_code,
                    file_state_name,
                    league_org,
                    league_base,
                    extracted_at,
                    extraction_status,
                    muni,
                    population_raw,
                    _str(c.get("county")),
                    _str(c.get("mayor")),
                    _league_website(c.get("website")),
                    _str(c.get("phone"), 120),
                    _str(c.get("email")),
                    _str(c.get("address")),
                    _str(c.get("municipality_type")),
                    _str(c.get("source_url")),
                    _str(c.get("source_kind")),
                    detail,
                    profile,
                    alt_json,
                    muni_state,
                    _raw_row_json(c),
                    geoid,
                    jid,
                    match_method,
                )
            )
    return rows


def load_to_postgres(
    conn: PGConnection,
    records: list[tuple[Any, ...]],
    *,
    dry_run: bool,
    truncate: bool,
) -> dict[str, Any]:
    cur = conn.cursor()

    if truncate:
        cur.execute(f"SELECT COUNT(*) FROM {BRONZE_TABLE}")
        before = cur.fetchone()[0]
        cur.execute(f"TRUNCATE TABLE {BRONZE_TABLE}")
        conn.commit()
        logger.info(f"Truncated {BRONZE_TABLE} ({before:,} rows prior)")

    if dry_run:
        matched = sum(1 for r in records if r[-2] is not None)
        logger.warning(f"DRY RUN — no data written. Parsed {len(records):,} rows; {matched:,} with jurisdiction_id.")
        for row in records[:3]:
            logger.info(f"  sample: {row[1]} {row[7]!r} jid={row[-2]} method={row[-1]}")
        cur.close()
        return {"parsed": len(records), "loaded": 0, "with_jurisdiction_id": matched}

    if records:
        execute_batch(cur, UPSERT_SQL, records, page_size=2000)
        conn.commit()
        cur.execute(f"SELECT COUNT(*) FROM {BRONZE_TABLE}")
        total = cur.fetchone()[0]
        cur.execute(f"SELECT COUNT(*) FROM {BRONZE_TABLE} WHERE jurisdiction_id IS NOT NULL")
        with_j = cur.fetchone()[0]
        logger.success(
            f"Upserted {len(records):,} rows → {BRONZE_TABLE} "
            f"(table total: {total:,}; with jurisdiction_id: {with_j:,})"
        )
    else:
        logger.warning("No city rows to load.")

    cur.close()
    return {
        "parsed": len(records),
        "loaded": len(records),
        "with_jurisdiction_id": sum(1 for r in records if r[-2] is not None),
    }


def rematch_bronze_jurisdiction_ids(
    conn: PGConnection,
    idx: CensusPlaceIndex,
    url_idx: dict[tuple[str, str], list[tuple[str, str]]],
    *,
    states: set[str] | None,
    dry_run: bool,
) -> dict[str, int]:
    where = ""
    params: list[Any] = []
    if states:
        where = "WHERE state_code = ANY(%s)"
        params.append(list(states))

    with conn.cursor() as cur:
        cur.execute(
            f"""
            SELECT row_key, state_code, municipality_name, website, alternate_names
            FROM {BRONZE_TABLE}
            {where}
            """,
            params or None,
        )
        rows = cur.fetchall()

    updates: list[tuple[str | None, str | None, str | None, str]] = []
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
        updates.append((jid, geoid, method, str(row_key)))

    if dry_run:
        with_j = sum(1 for u in updates if u[0])
        logger.info(f"Rematch dry-run: {len(updates):,} rows; would set jurisdiction_id on {with_j:,}")
        return {"rows": len(updates), "with_jurisdiction_id": with_j}

    with conn.cursor() as cur:
        execute_batch(
            cur,
            f"""
            UPDATE {BRONZE_TABLE}
            SET jurisdiction_id = %s,
                census_geoid = %s,
                jurisdiction_match_method = %s,
                ingestion_date = NOW()
            WHERE row_key = %s
            """,
            updates,
            page_size=2000,
        )
        conn.commit()
    with_j = sum(1 for u in updates if u[0])
    logger.success(f"Rematched {len(updates):,} bronze rows ({with_j:,} with jurisdiction_id)")
    return {"rows": len(updates), "with_jurisdiction_id": with_j}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load League city directory JSON into bronze_jurisdictions_municipalities_league"
    )
    parser.add_argument(
        "--states",
        nargs="*",
        help="Optional USPS state codes (default: all states under cache root)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--truncate", action="store_true")
    parser.add_argument(
        "--rematch-jurisdictions",
        action="store_true",
        help="Re-resolve jurisdiction_id on existing bronze rows (no JSON re-parse)",
    )
    args = parser.parse_args()

    st_filter = None
    if args.states:
        st_filter = {s.strip().upper() for s in args.states if len(s.strip()) == 2}

    paths = iter_city_files(st_filter)
    if not paths and not args.rematch_jurisdictions:
        logger.error(
            f"No cities.json under {CACHE_ROOT} (states={st_filter or 'all'}). "
            "Run download_league_city_directories.py first."
        )
        sys.exit(1)

    logger.info("=" * 70)
    logger.info(f"League city directories → {BRONZE_TABLE}")
    logger.info("=" * 70)
    logger.info(
        f"Database: {_database_url_source_label()} → {DATABASE_URL.split('@')[-1]}"
    )
    if paths:
        logger.info(f"Files: {len(paths)} (sample: {paths[0].relative_to(_ROOT)})")

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    try:
        cur = conn.cursor()
        cur.execute(CREATE_SQL)
        evolve_league_table_schema(cur)
        conn.commit()
        cur.close()

        logger.info(f"Building Census place index from {CENSUS_TABLE} …")
        idx = load_census_index(conn)
        logger.info(
            f"Census index: {len(idx._by_exact):,} exact keys, {len(idx._by_norm):,} normalized keys"
        )
        logger.info("Building URL → jurisdiction index …")
        url_idx = load_url_jurisdiction_index(conn)
        logger.info(f"URL index: {len(url_idx):,} (state, origin) keys")

        if args.rematch_jurisdictions:
            stats = rematch_bronze_jurisdiction_ids(
                conn,
                idx,
                url_idx,
                states=st_filter,
                dry_run=args.dry_run,
            )
            logger.info("SUMMARY")
            for k, v in stats.items():
                logger.info(f"  {k}: {v:,}")
            logger.success("Done.")
            return

        records = parse_city_files(paths, idx, url_idx)
        logger.info(f"Rows parsed for load: {len(records):,}")

        stats = load_to_postgres(
            conn, records, dry_run=args.dry_run, truncate=args.truncate
        )
        logger.info("SUMMARY")
        for k, v in stats.items():
            if isinstance(v, int):
                logger.info(f"  {k}: {v:,}")
            else:
                logger.info(f"  {k}: {v}")
        logger.success("Done.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
