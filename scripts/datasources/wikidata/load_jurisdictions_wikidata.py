#!/usr/bin/env python3
"""
Load Jurisdictions from WikiData

Queries WikiData for all cities, counties, school districts, and states,
and writes Wikidata metadata into these bronze tables:
- bronze.bronze_jurisdictions_states_wikidata
- bronze.bronze_jurisdictions_counties_wikidata
- bronze.bronze_jurisdictions_municipalities_wikidata
- bronze.bronze_jurisdictions_school_districts_wikidata

The legacy `public.jurisdictions_wikidata` table is deprecated and is no longer
created/used by this script.

Wikidata metadata includes:
- Official websites
- YouTube channels
- Social media (Facebook, Twitter)
- Population
- Geographic coordinates

This serves as a validation source for channel quality and provides
authoritative jurisdiction metadata.

Usage:
    From the repo root, use the project virtualenv (see README Quick Start: python3 -m venv .venv && pip install -r requirements.txt):

    # Load priority development states (AL, GA, IN, MA, MT, WA, WI)
    .venv/bin/python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --priority-states

    # All 50 states + DC + PR (requires rows in bronze base tables per USPS where applicable)
    .venv/bin/python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --all-us-states --types county

    # Explicit list
    .venv/bin/python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --states TX,NY,OH

    # Load all jurisdiction types for one state (defaults include all four types + priority dev USPS)
    .venv/bin/python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --states AL
"""
import os
import sys
import argparse
from argparse import BooleanOptionalAction
import asyncio
import json
import time
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Any
from datetime import datetime

_PSYCOPG2_AVAILABLE = True
try:
    import psycopg2
    from psycopg2.extras import execute_batch
except ModuleNotFoundError as exc:
    if exc.name != "psycopg2":
        raise
    _PSYCOPG2_AVAILABLE = False
    psycopg2 = None  # type: ignore[assignment]
    execute_batch = None  # type: ignore[assignment]
from loguru import logger
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from scripts.datasources.wikidata.wikidata_integration import WikidataQuery
from scripts.datasources.wikidata.geography_qid_cache import GeographyQidCache, norm_lit
from scripts.datasources.wikidata import wikidata_hybrid_sql as _wikidata_hybrid_sql
from scripts.datasources.wikidata.wikidata_wbget_claims import (
    collect_state_related_qids,
    entities_response_to_rows,
    entity_en_label,
    entity_to_wdqs_like_row,
    state_entity_to_sparql_shaped_row,
    try_pywikibot_rows,
)

load_dotenv()

DATABASE_URL = (
    os.getenv("NEON_DATABASE_URL_DEV")
    or os.getenv("NEON_DATABASE_URL")
    or "postgresql://postgres:password@localhost:5433/open_navigator"
)

# State mapping: USPS → display name, Wikidata state item, 2-digit state FIPS.
# county_type is optional: state-specific subtype of US county on Wikidata. When omitted,
# the SPARQL query uses only wd:Q47168 ("county of the United States"), which covers most cases.
# county_instance_types: optional explicit list when county-equivalents are not all Q47168
# (e.g. Alaska boroughs/census areas: Q13410522, Q56064719 — see Wikidata).
STATE_MAP = {
    "AL": {"name": "Alabama", "q_code": "Q173", "fips": "01", "county_type": "Q13410400"},
    "AK": {
        "name": "Alaska",
        "q_code": "Q797",
        "fips": "02",
        "county_instance_types": ["Q47168", "Q13410522", "Q56064719"],
    },
    "AZ": {"name": "Arizona", "q_code": "Q816", "fips": "04"},
    "AR": {"name": "Arkansas", "q_code": "Q1612", "fips": "05"},
    "CA": {"name": "California", "q_code": "Q99", "fips": "06"},
    "CO": {"name": "Colorado", "q_code": "Q1261", "fips": "08"},
    "CT": {"name": "Connecticut", "q_code": "Q779", "fips": "09"},
    "DE": {"name": "Delaware", "q_code": "Q1393", "fips": "10"},
    "DC": {"name": "District of Columbia", "q_code": "Q61", "fips": "11"},
    "FL": {"name": "Florida", "q_code": "Q812", "fips": "12"},
    "GA": {"name": "Georgia", "q_code": "Q1428", "fips": "13", "county_type": "Q13410428"},
    "HI": {"name": "Hawaii", "q_code": "Q782", "fips": "15"},
    "ID": {"name": "Idaho", "q_code": "Q1221", "fips": "16"},
    "IL": {"name": "Illinois", "q_code": "Q1204", "fips": "17"},
    "IN": {"name": "Indiana", "q_code": "Q1415", "fips": "18", "county_type": "Q13414760"},
    "IA": {"name": "Iowa", "q_code": "Q1546", "fips": "19"},
    "KS": {"name": "Kansas", "q_code": "Q1558", "fips": "20"},
    "KY": {"name": "Kentucky", "q_code": "Q1603", "fips": "21"},
    "LA": {"name": "Louisiana", "q_code": "Q1588", "fips": "22"},
    "ME": {"name": "Maine", "q_code": "Q724", "fips": "23"},
    "MD": {"name": "Maryland", "q_code": "Q1391", "fips": "24"},
    "MA": {"name": "Massachusetts", "q_code": "Q771", "fips": "25", "county_type": "Q13410485"},
    "MI": {"name": "Michigan", "q_code": "Q1166", "fips": "26"},
    "MN": {"name": "Minnesota", "q_code": "Q1527", "fips": "27"},
    "MS": {"name": "Mississippi", "q_code": "Q1494", "fips": "28"},
    "MO": {"name": "Missouri", "q_code": "Q1581", "fips": "29"},
    "MT": {"name": "Montana", "q_code": "Q1212", "fips": "30"},
    "NE": {"name": "Nebraska", "q_code": "Q1553", "fips": "31"},
    "NV": {"name": "Nevada", "q_code": "Q1227", "fips": "32"},
    "NH": {"name": "New Hampshire", "q_code": "Q759", "fips": "33"},
    "NJ": {"name": "New Jersey", "q_code": "Q1408", "fips": "34"},
    "NM": {"name": "New Mexico", "q_code": "Q1522", "fips": "35"},
    "NY": {"name": "New York", "q_code": "Q1384", "fips": "36"},
    "NC": {"name": "North Carolina", "q_code": "Q1454", "fips": "37"},
    "ND": {"name": "North Dakota", "q_code": "Q1207", "fips": "38"},
    "OH": {"name": "Ohio", "q_code": "Q1397", "fips": "39"},
    "OK": {"name": "Oklahoma", "q_code": "Q1649", "fips": "40"},
    "OR": {"name": "Oregon", "q_code": "Q824", "fips": "41"},
    "PA": {"name": "Pennsylvania", "q_code": "Q1400", "fips": "42"},
    "PR": {
        "name": "Puerto Rico",
        "q_code": "Q1183",
        "fips": "72",
        # Census county-equivalents are municipios; WDQS typing is rarely plain Q47168 only.
        "county_instance_types": ["Q47168", "Q263639"],
    },
    "RI": {"name": "Rhode Island", "q_code": "Q1387", "fips": "44"},
    "SC": {"name": "South Carolina", "q_code": "Q1456", "fips": "45"},
    "SD": {"name": "South Dakota", "q_code": "Q1211", "fips": "46"},
    "TN": {"name": "Tennessee", "q_code": "Q1509", "fips": "47"},
    "TX": {"name": "Texas", "q_code": "Q1439", "fips": "48"},
    "UT": {"name": "Utah", "q_code": "Q829", "fips": "49"},
    "VT": {"name": "Vermont", "q_code": "Q16551", "fips": "50"},
    "VA": {"name": "Virginia", "q_code": "Q1370", "fips": "51"},
    "WA": {"name": "Washington", "q_code": "Q1223", "fips": "53", "county_type": "Q13415369"},
    "WV": {"name": "West Virginia", "q_code": "Q1371", "fips": "54"},
    "WI": {"name": "Wisconsin", "q_code": "Q1537", "fips": "55", "county_type": "Q13414761"},
    "WY": {"name": "Wyoming", "q_code": "Q1214", "fips": "56"},
}

# Priority development states (subset of STATE_MAP).
PRIORITY_STATES = ["AL", "GA", "IN", "MA", "MT", "WA", "WI"]


def _env_truthy(key: str, default: bool = False) -> bool:
    raw = (os.getenv(key) or "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _wikidata_mapping_cache_warm_db() -> bool:
    """Rebuild literal→Q mappings from Postgres when hybrid mode runs (unset env → on)."""
    raw = (os.getenv("WIKIDATA_QID_CACHE_WARM_DB") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _wikidata_hybrid_enrich_enabled() -> bool:
    """Light WDQS map (id→Q) + Wikibase wbgetentities / optional Pywikibot for claims."""
    return _env_truthy("WIKIDATA_HYBRID_ENRICH", default=False)


def _wikidata_hybrid_county_map_mode() -> str:
    """
    Hybrid county id→Q resolution:

    * ``bulk_state`` — **one** WDQS query: counties with P131 = state (+ types), match FIPS/GNIS in-process (default).
    * ``entity_search`` — wbsearchentities + wbgetentities per county (slow).
    * ``sparql`` — legacy batched FILTER IN mapping on WDQS.

    Env: ``WIKIDATA_HYBRID_COUNTY_MAP_MODE``.
    """
    raw = (os.getenv("WIKIDATA_HYBRID_COUNTY_MAP_MODE") or "bulk_state").strip().lower()
    if raw in ("sparql", "wdqs", "map_sparql"):
        return "sparql"
    if raw in ("entity_search", "search", "wbsearch"):
        return "entity_search"
    return "bulk_state"


def _wikidata_hybrid_municipality_map_mode() -> str:
    """
    Hybrid municipality id→Q resolution (hybrid enrich path):

    * ``bulk_state`` — **one** WDQS query per state: P131+ to state, US place types; match P774/P590 in memory (default).
    * ``sparql`` — FILTER IN batches on literals per chunk (legacy hybrid map).

    Env: ``WIKIDATA_HYBRID_MUNICIPALITY_MAP_MODE``.
    """
    raw = (os.getenv("WIKIDATA_HYBRID_MUNICIPALITY_MAP_MODE") or "bulk_state").strip().lower()
    if raw in ("sparql", "wdqs", "map_sparql"):
        return "sparql"
    return "bulk_state"


def _wikidata_school_bulk_supplement_sparql() -> bool:
    """
    After bulk school-district WDQS + in-memory match, optionally run FILTER IN for misses.

    Env: ``WIKIDATA_SCHOOL_BULK_SUPPLEMENT_SPARQL`` (default False).
    """
    return _env_truthy("WIKIDATA_SCHOOL_BULK_SUPPLEMENT_SPARQL", default=False)


def _wikidata_municipality_bulk_supplement_sparql() -> bool:
    """
    After bulk P131+ WDQS + in-memory match, optionally run a second FILTER IN WDQS query for misses.

    Uses **only** the bulk rows by default (one WDQS query per state). Set
    ``WIKIDATA_MUNICIPALITY_BULK_SUPPLEMENT_SPARQL=1`` as a dedicated backfill pass when WDQS is quiet.

    Env: ``WIKIDATA_MUNICIPALITY_BULK_SUPPLEMENT_SPARQL`` (default False).
    """
    return _env_truthy("WIKIDATA_MUNICIPALITY_BULK_SUPPLEMENT_SPARQL", default=False)


def _municipality_pre_bulk_wdqs_pause_seconds() -> float:
    """Sleep before the **one** state bulk municipality WDQS query (first heavy hit; eases cold 429)."""
    try:
        return max(0.0, float(os.getenv("WIKIDATA_MUNICIPALITY_PRE_BULK_WDQS_PAUSE_SECONDS", "0") or "0"))
    except ValueError:
        return 0.0


def _wikidata_municipality_sparql_when_bulk_empty() -> bool:
    """
    If the one **bulk_state** WDQS query returns **0 rows** (or throws), optionally fall back to the
    **heavy** per-chunk ``municipality_mapping_sparql`` FILTER queries. That fallback often triggers 429/500.

    Env: ``WIKIDATA_MUNICIPALITY_SPARQL_WHEN_BULK_EMPTY`` — default **on** (``1``); happy path fills **0**
    so a failed/empty bulk **stops** instead of spamming WDQS.
    """
    raw = (os.getenv("WIKIDATA_MUNICIPALITY_SPARQL_WHEN_BULK_EMPTY") or "1").strip().lower()
    if not raw:
        return True
    return raw not in ("0", "false", "no", "off")


def _apply_wikidata_happy_path_env_defaults() -> None:
    """
    ``WIKIDATA_HAPPY_PATH=1`` (or ``--happy-path``): set **only unset** env keys to reduce
    429s — slower pacing, no extra FILTER supplements after bulk, no county wbsearchentities
    fallback, skip priority USPS that are already enriched. Run a second pass later with
    supplements / gap retry / entity-search when WDQS is quiet.
    """
    if not _env_truthy("WIKIDATA_HAPPY_PATH"):
        return
    # Only fill keys that the user has not already set (explicit empty string counts as set for dotenv).
    defaults = {
        "WIKIDATA_RETRY_AFTER_MAX_SECONDS": "120",
        "WIKIDATA_THROTTLE_SECONDS": "12",
        "WIKIDATA_TASK_SLEEP_SECONDS": "8",
        # Without hybrid, municipalities fall back to legacy huge FILTER-IN WDQS per chunk — not what
        # operators expect from ``--happy-path`` (bulk map + wbgetentities). Explicit ``WIKIDATA_HYBRID_ENRICH=0`` still wins.
        "WIKIDATA_HYBRID_ENRICH": "1",
        "WIKIDATA_INCREMENTAL_MERGE": "1",
        "WIKIDATA_PRIORITY_STATES_SKIP_COMPLETE": "1",
        "WIKIDATA_LOAD_RETRY_COUNTY_GAPS": "0",
        "WIKIDATA_MUNICIPALITY_BULK_SUPPLEMENT_SPARQL": "0",
        "WIKIDATA_MUNICIPALITY_SPARQL_WHEN_BULK_EMPTY": "0",
        "WIKIDATA_SCHOOL_BULK_SUPPLEMENT_SPARQL": "0",
        "WIKIDATA_COUNTY_BULK_FALLBACK_ENTITY_SEARCH": "0",
        "WIKIDATA_COUNTY_CHUNK_SLEEP_SECONDS": "3",
        "WIKIDATA_MUNICIPALITY_PRE_BULK_WDQS_PAUSE_SECONDS": "30",
        "WIKIDATA_MUNICIPALITY_POST_BULK_WDQS_GAP_SECONDS": "12",
        "WIKIDATA_MUNICIPALITY_FILTER_WDQS_GAP_SECONDS": "8",
        "WIKIDATA_SCHOOL_POST_BULK_WDQS_GAP_SECONDS": "12",
        "WIKIDATA_SCHOOL_FILTER_WDQS_GAP_SECONDS": "8",
    }
    applied = []
    for key, val in defaults.items():
        raw = (os.getenv(key) or "").strip()
        if raw == "":
            os.environ[key] = val
            applied.append(key)
    if applied:
        logger.info(
            "WIKIDATA_HAPPY_PATH active — filled unset keys: "
            + ", ".join(applied)
            + " (see module doc / run_wikidata_happy_path.sh)."
        )


def _wikidata_hybrid_school_map_mode() -> str:
    """
    Hybrid school-district id→Q resolution:

    * ``bulk_state`` — **one** WDQS query per state: P131+ to state, Q1455778; match NCES/FIPS in memory (default).
    * ``sparql`` — FILTER IN batches per chunk.

    Env: ``WIKIDATA_HYBRID_SCHOOL_MAP_MODE``.
    """
    raw = (os.getenv("WIKIDATA_HYBRID_SCHOOL_MAP_MODE") or "bulk_state").strip().lower()
    if raw in ("sparql", "wdqs", "map_sparql"):
        return "sparql"
    return "bulk_state"


def _wikidata_state_bulk_wbgetentities() -> bool:
    """When True, first state task prefetches all ``STATE_MAP`` q_codes in one batched ``wbgetentities``."""
    return _env_truthy("WIKIDATA_STATE_BULK_WBGETENTITIES", default=False)


def _wikidata_state_legacy_sparql() -> bool:
    """When True, use WDQS for ``query_state_info``. Default: Wikibase API (wbgetentities / same JSON as EntityData)."""
    return _env_truthy("WIKIDATA_STATE_LEGACY_SPARQL", default=False)


def _wikidata_incremental_merge() -> bool:
    """
    When True, seeding merges Census base rows into *_wikidata without wiping existing QIDs,
    and WDQS runs only for rows where wikidata_id is still NULL (see WIKIDATA_INCREMENTAL_MERGE).

    Default **True**: without merge, each run DELETE+re-seeds rows and clears enrichment, so
    ``--priority-states`` would refetch Wikidata even when coverage is already 100%.
    """
    return _env_truthy("WIKIDATA_INCREMENTAL_MERGE", default=True)


def fetch_usps_county_wikidata_gaps(database_url: str) -> List[str]:
    """
    USPS codes where bronze county rows exist but Wikidata enrichment is incomplete:
    fewer *_wikidata rows than base counties, or not every row has wikidata_id.
    """
    sql = """
    WITH base AS (
      SELECT usps, COUNT(*)::bigint AS n_base
      FROM bronze.bronze_jurisdictions_counties
      GROUP BY usps
    ),
    enr AS (
      SELECT
        usps,
        COUNT(*)::bigint AS n_rows,
        COUNT(*) FILTER (WHERE wikidata_id IS NOT NULL)::bigint AS n_with_wikidata
      FROM bronze.bronze_jurisdictions_counties_wikidata
      GROUP BY usps
    )
    SELECT b.usps
    FROM base b
    LEFT JOIN enr e ON e.usps = b.usps
    WHERE COALESCE(e.n_rows, 0) < b.n_base
       OR COALESCE(e.n_with_wikidata, 0) < b.n_base
    ORDER BY b.usps
    """
    conn = psycopg2.connect(database_url)
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = [r[0] for r in cur.fetchall() if r and r[0]]
        cur.close()
    finally:
        conn.close()

    unknown = sorted({s.upper() for s in rows if s.upper() not in STATE_MAP})
    if unknown:
        logger.warning(f"Ignoring {len(unknown)} USPS code(s) not in STATE_MAP (sample): {unknown[:10]}")
    return [s.upper() for s in rows if s.upper() in STATE_MAP]


def _loader_query_tasks_from_types(types: List[str]) -> List[str]:
    """Same task ordering as ``load_state`` (city/town → single city task)."""
    query_tasks: List[str] = []
    if "state" in types:
        query_tasks.append("state")
    if "city" in types or "town" in types:
        query_tasks.append("city")
    if "county" in types:
        query_tasks.append("county")
    if "school_district" in types:
        query_tasks.append("school_district")
    return query_tasks


def filter_states_with_pending_wikidata_for_types(
    database_url: str, state_codes: List[str], types: List[str]
) -> List[str]:
    """
    USPS codes that still need Wikidata joins: at least one row in a selected *_wikidata
    table has NULL/empty ``wikidata_id`` for that USPS.
    """
    tasks = _loader_query_tasks_from_types(types)
    if not tasks:
        return [s.upper() for s in state_codes if s.strip()]
    tbl_map = {
        "state": "bronze.bronze_jurisdictions_states_wikidata",
        "county": "bronze.bronze_jurisdictions_counties_wikidata",
        "city": "bronze.bronze_jurisdictions_municipalities_wikidata",
        "school_district": "bronze.bronze_jurisdictions_school_districts_wikidata",
    }
    conn = psycopg2.connect(database_url)
    try:
        out: List[str] = []
        for us in state_codes:
            usup = str(us).strip().upper()
            if not usup:
                continue
            needs_work = False
            for task in tasks:
                tbl = tbl_map[task]
                cur = conn.cursor()
                try:
                    cur.execute(
                        f"""
                        SELECT 1
                        FROM {tbl}
                        WHERE usps = %s
                          AND (wikidata_id IS NULL OR BTRIM(wikidata_id::text) = '')
                        LIMIT 1
                        """,
                        (usup,),
                    )
                    if cur.fetchone() is not None:
                        needs_work = True
                        break
                finally:
                    cur.close()
            if needs_work:
                out.append(usup)
        return out
    finally:
        conn.close()


def _sparql_quote_string_literal(s: str) -> str:
    """Escape a string for WDQS FILTER IN (\"…\") literals."""
    esc = str(s).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{esc}"'


def _lat_lon_from_wikidata_coord_binding(coord_val: Any) -> Tuple[Optional[float], Optional[float]]:
    """
    Parse WDQS binding for ``wdt:P625`` (GeoShape / WKT) into ``(latitude, longitude)``.
    Wikidata commonly returns ``Point(lon lat)`` as a literal string.
    """
    import re

    if coord_val is None:
        return None, None
    if isinstance(coord_val, dict):
        coord_val = coord_val.get("value")
    s = str(coord_val).strip()
    if not s:
        return None, None
    if "^^" in s:
        s = s.split("^^", 1)[0].strip().strip('"').strip()
    m = re.search(
        r"Point\s*\(\s*([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s+"
        r"([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)\s*\)",
        s,
        re.I,
    )
    if not m:
        return None, None
    lon = float(m.group(1))
    lat = float(m.group(2))
    return lat, lon


def _county_fips_literal_alternatives(geoid: str, state_fips: Optional[str]) -> Set[str]:
    """
    Alternate string forms WD may expose for P882 (county/admin FIPS) or P3006
    versus bronze 5-character county GEOIDs.
    Mirrors len-based branches in `_parse_jurisdiction_results` only as string targets.
    """
    g = str(geoid).strip().replace("-", "")
    out: Set[str] = {g}
    if not g.isdigit():
        return out
    sf = state_fips or ""
    sf = sf.strip().replace("-", "")
    if len(g) == 5:
        out.add(g[2:])
        out.add(g[1:])
        if sf and sf.isdigit() and g.startswith(sf):
            out.add(g[len(sf) :])  # county-only digits as stored with state prefix stripped
            out.add(g[len(sf) :].zfill(3))
    elif len(g) <= 4 and sf and sf.isdigit():
        padded = g.zfill(5) if len(g) <= 3 else g
        if len(padded) == 5 and padded.startswith(sf):
            out.add(padded)
    return {x.replace("-", "") for x in out if x}


def _positive_int_env(name: str, default: int, lo: int = 1, hi: int = 10_000) -> int:
    try:
        raw = (os.getenv(name) or "").strip()
        v = int(raw or str(default))
        return max(lo, min(hi, v))
    except ValueError:
        return default


def _chunk_sleep_seconds(default: float = 1.0) -> float:
    try:
        return max(
            0.0,
            float(os.getenv("WIKIDATA_COUNTY_CHUNK_SLEEP_SECONDS", str(default)) or str(default)),
        )
    except ValueError:
        return default


def _municipality_post_bulk_wdqs_gap_seconds() -> float:
    """
    Sleep after the one state-wide bulk WDQS query before the first per-chunk FILTER IN
    (``WIKIDATA_MUNICIPALITY_BULK_SUPPLEMENT_SPARQL=1``). Reduces back-to-back WDQS bursts → 429.
    """
    try:
        return max(0.0, float(os.getenv("WIKIDATA_MUNICIPALITY_POST_BULK_WDQS_GAP_SECONDS", "10") or "10"))
    except ValueError:
        return 10.0


def _municipality_filter_wdqs_gap_seconds() -> float:
    """Sleep immediately before each municipality FILTER IN WDQS request (same env family as POST_BULK)."""
    try:
        return max(0.0, float(os.getenv("WIKIDATA_MUNICIPALITY_FILTER_WDQS_GAP_SECONDS", "6") or "6"))
    except ValueError:
        return 6.0


def _school_post_bulk_wdqs_gap_seconds() -> float:
    """After bulk school WDQS, pause before first FILTER supplement (when supplement=1)."""
    try:
        return max(0.0, float(os.getenv("WIKIDATA_SCHOOL_POST_BULK_WDQS_GAP_SECONDS", "10") or "10"))
    except ValueError:
        return 10.0


def _school_filter_wdqs_gap_seconds() -> float:
    """Sleep before each school FILTER IN WDQS request."""
    try:
        return max(0.0, float(os.getenv("WIKIDATA_SCHOOL_FILTER_WDQS_GAP_SECONDS", "6") or "6"))
    except ValueError:
        return 6.0


def _wikidata_filter_in_literal_chunk_size() -> int:
    """Max literals per ``FILTER … IN (...)`` WDQS sub-query (mapping batches)."""
    try:
        v = int(os.getenv("WIKIDATA_FILTER_IN_LITERAL_CHUNK_SIZE", "12") or "12")
        return max(5, min(50, v))
    except ValueError:
        return 12


def _wikidata_filter_in_subquery_gap_seconds() -> float:
    """Pause between FILTER IN sub-queries when literals are split (reduces WDQS timeouts)."""
    try:
        return max(0.0, float(os.getenv("WIKIDATA_FILTER_IN_SUBQUERY_GAP_SECONDS", "1") or "1"))
    except ValueError:
        return 1.0


def _batched_sorted_literals(literals: Set[str], chunk_sz: int) -> List[List[str]]:
    xs = sorted(x for x in literals if str(x).strip())
    if chunk_sz <= 0:
        chunk_sz = 12
    return [xs[i : i + chunk_sz] for i in range(0, len(xs), chunk_sz)]


def _wikidata_municipality_flush_db_each_chunk() -> bool:
    """
    After each hybrid municipality chunk with ≥1 enriched row, ``UPDATE`` Postgres immediately so
    dashboards can show progress before the full state task finishes.

    Env: ``WIKIDATA_MUNICIPALITY_FLUSH_DB_EACH_CHUNK`` — default **on** (``1``); set ``0`` to only
    commit once at end of the city task (legacy behavior).
    """
    raw = (os.getenv("WIKIDATA_MUNICIPALITY_FLUSH_DB_EACH_CHUNK") or "1").strip().lower()
    if not raw:
        return True
    return raw not in ("0", "false", "no", "off")


def _wikidata_municipality_supplement_split_wdqs() -> bool:
    """
    Hybrid municipality **supplement** step: run two WDQS queries (FIPS literals only, then GNIS only)
    instead of one ``FILTER(fips IN (...) || gnis IN (...))``. Combined OR + large IN lists often triggers
    WDQS HTTP 500 (timeout / SystemOverloadFilter).

    Env: ``WIKIDATA_MUNICIPALITY_SUPPLEMENT_SPLIT_WDQS`` — default **on** (``1``); set ``0`` for legacy single query.
    """
    raw = (os.getenv("WIKIDATA_MUNICIPALITY_SUPPLEMENT_SPLIT_WDQS") or "1").strip().lower()
    if not raw:
        return True
    return raw not in ("0", "false", "no", "off")


# Bronze municipality rows join Wikidata largely via P774 (FIPS place code); P590 is GNIS (often = ansicode).
def _municipality_wd_literal_sets(geoid: str, ansicode: Optional[str]) -> tuple[Set[str], Set[str]]:
    """
    Literals for WDQS ``FILTER(REPLACE(STR(?fips), "-", "") IN (...))`` and cache lookup.

    Wikidata ``P774`` uses hyphenated ``SS-CCCPP`` or compact 7-digit strings; we emit **digits-only**
    variants so one IN-list entry matches both (REPLACE strips hyphens server-side). Avoid ad hoc 5-digit
    slices that inflated the batch without matching WD storage.
    """
    fips_lit: Set[str] = set()
    gnis_lit: Set[str] = set()
    raw_geo = str(geoid).strip()
    if not raw_geo:
        return fips_lit, gnis_lit
    d = norm_lit(raw_geo)
    if d.isdigit():
        fips_lit.add(d)
        if len(d) < 7:
            fips_lit.add(d.zfill(7))
        if len(d) >= 7:
            fips_lit.add(d[:7])
    elif d:
        fips_lit.add(d)
    if ansicode is not None and str(ansicode).strip():
        raw = str(ansicode).strip().replace("-", "")
        gnis_lit.add(raw)
        if raw.isdigit():
            stripped = raw.lstrip("0") or "0"
            gnis_lit.add(stripped)
            gnis_lit.add(raw.zfill(len(raw)))
    return {x.replace("-", "") for x in fips_lit if x}, {y.replace("-", "") for y in gnis_lit if y}


def _school_id_literal_alternatives(geoid_or_nces: str) -> Set[str]:
    s = str(geoid_or_nces).strip().replace("-", "")
    if not s:
        return set()
    out: Set[str] = {s}
    if s.isdigit():
        t = s.lstrip("0") or "0"
        out.update({t, s.zfill(7), t.zfill(7)})
    return {x.replace("-", "") for x in out if x}


def _county_type_values_clause(state_code: str) -> str:
    """Build WDQS VALUES clause for county/county-equivalent instance-of types."""
    info = STATE_MAP.get(state_code) or {}
    instances = info.get("county_instance_types")
    if instances:
        return " ".join(f"wd:{q}" for q in instances)
    county_type_q = info.get("county_type")
    if county_type_q:
        return f"wd:{county_type_q} wd:Q47168"
    return "wd:Q47168"


def _wikidata_task_has_join_keys(task: str, rows: List[Dict]) -> bool:
    """True if parsed rows can run UPDATE ... WHERE geoid = ... (or state equivalent)."""
    if not rows:
        return False
    if task == "state":
        return bool(rows[0].get("geoid"))
    if task in ("county", "city", "school_district"):
        return any(r.get("geoid") for r in rows)
    return False


# WikiData Q-codes for jurisdiction types
JURISDICTION_TYPES = {
    "city": "Q515",  # City
    "town": "Q3957",  # Town/Municipality
    "county": "Q47168",  # County of the United States
    "school_district": "Q1455778",  # School district
    "state": "Q35657"  # State of the United States
}


class CheckpointManager:
    """Persist completed (state, type) pairs so interrupted runs can resume."""

    def __init__(self, checkpoint_file: str):
        self.path = Path(checkpoint_file)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._completed: set = set()
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text())
                self._completed = {tuple(x) for x in data.get("completed", [])}
                logger.info(f"Resuming from checkpoint: {len(self._completed)} tasks already done")
            except Exception:
                self._completed = set()

    def is_done(self, state: str, jtype: str) -> bool:
        return (state, jtype) in self._completed

    def mark_done(self, state: str, jtype: str):
        self._completed.add((state, jtype))
        self._save()

    def unmark(self, state: str, jtype: str) -> bool:
        """Remove a task from the checkpoint so it will run again."""
        key = (state, jtype)
        if key not in self._completed:
            return False
        self._completed.discard(key)
        self._save()
        return True

    def _save(self):
        self.path.write_text(json.dumps({
            "completed": [list(x) for x in self._completed],
            "last_updated": datetime.utcnow().isoformat(),
        }, indent=2))


class JurisdictionsWikiDataLoader:
    """Load jurisdiction data from WikiData into PostgreSQL (or JSON cache when --json-cache-dir is used)."""

    def __init__(self, database_url: str, json_cache_dir: Optional[str] = None):
        self._json_cache_dir: Optional[Path] = Path(json_cache_dir) if json_cache_dir else None
        self._json_bronze: Optional[Dict[str, Any]] = None
        # Accumulated enrichment rows keyed by task → list[dict], written to JSON on close.
        self._json_results: Dict[str, List[Dict]] = {}

        if self._json_cache_dir:
            self.conn = None
            self._load_json_cache()
        else:
            if not _PSYCOPG2_AVAILABLE:
                _repo_root = Path(__file__).resolve().parents[3]
                _venv_py = _repo_root / ".venv" / "bin" / "python"
                sys.stderr.write(
                    "ModuleNotFoundError: psycopg2 — install deps in the project venv or use its interpreter.\n"
                    f"  Example: {_venv_py} {_repo_root / 'scripts/datasources/wikidata/load_jurisdictions_wikidata.py'} ...\n"
                    "  Or: source .venv/bin/activate   (then run python3 …)\n"
                    "  Setup: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt\n"
                    "  Alternatively, run offline with --json-cache-dir (no Postgres required).\n"
                )
                sys.exit(1)
            self.conn = psycopg2.connect(database_url)

        self.wikidata = WikidataQuery()
        self._geography_qid_cache: GeographyQidCache | None = None
        self._state_entities_bulk: Dict[str, Dict[str, Any]] = {}
        self._state_bulk_prefetch_attempted = False
        self._municipality_chunk_db_flush_used = False

        if not self._json_cache_dir:
            self._create_table()

    # ------------------------------------------------------------------
    # JSON cache helpers
    # ------------------------------------------------------------------

    def _load_json_cache(self) -> None:
        """Load the bronze JSON cache produced by export_bronze_to_json.py."""
        cache_file = self._json_cache_dir / "bronze_jurisdictions.json"  # type: ignore[operator]
        if not cache_file.exists():
            raise FileNotFoundError(
                f"Bronze JSON cache not found: {cache_file}\n"
                "  Run export_bronze_to_json.py first:\n"
                "    .venv/bin/python scripts/datasources/wikidata/export_bronze_to_json.py"
            )
        logger.info(f"Loading bronze JSON cache from {cache_file}…")
        with open(cache_file, "r", encoding="utf-8") as f:
            self._json_bronze = json.load(f)
        exported_at = self._json_bronze.get("exported_at", "unknown")
        cached_states = self._json_bronze.get("states", [])
        logger.info(
            f"JSON cache loaded: {len(cached_states)} state(s), exported {exported_at}"
        )

    def _json_save_results(self) -> None:
        """Write accumulated enrichment results to JSON in the cache dir."""
        if not self._json_cache_dir or not self._json_results:
            return
        ts = datetime.now().strftime("%Y%m%dT%H%M%S")
        out = self._json_cache_dir / f"wikidata_enrichment_{ts}.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump(self._json_results, f, indent=2, default=str)
        total = sum(len(v) for v in self._json_results.values())
        logger.success(f"Enrichment results saved → {out} ({total} rows)")

    def geography_qid_cache(self) -> GeographyQidCache:
        if self._geography_qid_cache is None:
            self._geography_qid_cache = GeographyQidCache()
        return self._geography_qid_cache

    def warm_geography_qid_cache_from_db(self, state_code: str, warm_task: str) -> None:
        if self._json_cache_dir:
            return  # no Postgres in JSON mode
        if not _wikidata_mapping_cache_warm_db():
            return
        us = state_code.upper()
        qcache = self.geography_qid_cache()
        cur = self.conn.cursor()
        try:
            if warm_task == "city":
                cur.execute(
                    """
                    SELECT geoid::text, ansicode::text, wikidata_id::text
                    FROM bronze.bronze_jurisdictions_municipalities_wikidata
                    WHERE usps = %s AND BTRIM(COALESCE(wikidata_id::text, '')) <> ''
                      AND wikidata_id::text LIKE 'Q%%'
                    """,
                    (us,),
                )
                rows = [(r[0], r[1], r[2]) for r in cur.fetchall()]
            elif warm_task == "county":
                cur.execute(
                    """
                    SELECT geoid::text, wikidata_id::text
                    FROM bronze.bronze_jurisdictions_counties_wikidata
                    WHERE usps = %s AND BTRIM(COALESCE(wikidata_id::text, '')) <> ''
                      AND wikidata_id::text LIKE 'Q%%'
                    """,
                    (us,),
                )
                rows = [(r[0], None, r[1]) for r in cur.fetchall()]
            elif warm_task == "school_district":
                cur.execute(
                    """
                    SELECT geoid::text, wikidata_id::text
                    FROM bronze.bronze_jurisdictions_school_districts_wikidata
                    WHERE usps = %s AND BTRIM(COALESCE(wikidata_id::text, '')) <> ''
                      AND wikidata_id::text LIKE 'Q%%'
                    """,
                    (us,),
                )
                rows = [(r[0], None, r[1]) for r in cur.fetchall()]
            else:
                return
            if rows:
                qcache.warm_from_enriched_rows(warm_task, state_code, rows)
                qcache.save()
                logger.info(
                    f"Warmed geography→Q mapping cache ({warm_task}) with {len(rows)} "
                    f"Postgres rows for USPS {state_code.upper()}"
                )
        finally:
            cur.close()
    
    def _create_table(self):
        """Deprecated: we no longer create/use `public.jurisdictions_wikidata`."""
        return

    def _seed_wikidata_table(self, state_code: str, task: str) -> None:
        """Rebuild the per-type bronze *_wikidata table rows for one state from its base table."""
        if self._json_cache_dir:
            return  # seeding is a no-op in JSON mode; source data comes from the cache file
        mapping: dict[str, tuple[str, str, str]] = {
            "state": (
                "bronze.bronze_jurisdictions_states",
                "bronze.bronze_jurisdictions_states_wikidata",
                "geoid, usps, ansicode, name, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date",
            ),
            "county": (
                "bronze.bronze_jurisdictions_counties",
                "bronze.bronze_jurisdictions_counties_wikidata",
                "geoid, usps, ansicode, name, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date",
            ),
            # city task enriches municipalities
            "city": (
                "bronze.bronze_jurisdictions_municipalities",
                "bronze.bronze_jurisdictions_municipalities_wikidata",
                "geoid, usps, ansicode, name, lsad, funcstat, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date",
            ),
            "school_district": (
                "bronze.bronze_jurisdictions_school_districts",
                "bronze.bronze_jurisdictions_school_districts_wikidata",
                "geoid, usps, name, lograde, higrade, aland, awater, aland_sqmi, awater_sqmi, intptlat, intptlong, ingestion_date",
            ),
        }
        if task not in mapping:
            raise ValueError(f"Unknown seed task: {task}")

        base_table, wikidata_table, cols = mapping[task]
        cur = self.conn.cursor()
        try:
            us = state_code.upper()
            if _wikidata_incremental_merge():
                # Drop wikidata rows no longer present in Census base for this USPS (orphans).
                cur.execute(
                    f"""
                    DELETE FROM {wikidata_table} w
                    WHERE w.usps = %s
                      AND NOT EXISTS (
                        SELECT 1
                        FROM {base_table} b
                        WHERE b.usps = w.usps
                          AND b.geoid::text = w.geoid::text
                      )
                    """,
                    (us,),
                )
                # Insert new base rows not yet present (preserve existing enriched rows / QIDs).
                cur.execute(
                    f"""
                    INSERT INTO {wikidata_table} ({cols})
                    SELECT {cols}
                    FROM {base_table} b
                    WHERE b.usps = %s
                      AND NOT EXISTS (
                        SELECT 1
                        FROM {wikidata_table} w
                        WHERE w.usps = b.usps
                          AND w.geoid::text = b.geoid::text
                      )
                    """,
                    (us,),
                )
                logger.info(
                    f"Incremental merge seed for {wikidata_table} ({us}): "
                    f"orphan cleanup + insert missing base rows (existing wikidata_id preserved)."
                )
            else:
                cur.execute(f"DELETE FROM {wikidata_table} WHERE usps = %s", (us,))
                cur.execute(
                    f"""
                    INSERT INTO {wikidata_table} ({cols})
                    SELECT {cols}
                    FROM {base_table}
                    WHERE usps = %s
                    """,
                    (us,),
                )
            self.conn.commit()
        finally:
            cur.close()

    def _any_missing_wikidata_id_for_task(self, state_code: str, task: str) -> bool:
        """
        True if this USPS still has at least one row in the *_wikidata table with NULL wikidata_id.

        With ``WIKIDATA_INCREMENTAL_MERGE=1`` (default), if this returns False after seeding,
        WDQS is skipped for that task. With merge off, the table is re-seeded empty of Q IDs,
        so this is typically True until Wikidata is fetched again.
        """
        if self._json_cache_dir:
            # In JSON mode, always proceed — no enrichment has been applied yet.
            return True
        tbl = {
            "state": "bronze.bronze_jurisdictions_states_wikidata",
            "county": "bronze.bronze_jurisdictions_counties_wikidata",
            "city": "bronze.bronze_jurisdictions_municipalities_wikidata",
            "school_district": "bronze.bronze_jurisdictions_school_districts_wikidata",
        }.get(task)
        if not tbl:
            return True
        us = state_code.upper()
        cur = self.conn.cursor()
        try:
            cur.execute(
                f"""
                SELECT 1
                FROM {tbl}
                WHERE usps = %s
                  AND (wikidata_id IS NULL OR BTRIM(wikidata_id::text) = '')
                LIMIT 1
                """,
                (us,),
            )
            return cur.fetchone() is not None
        except Exception as exc:
            logger.warning(
                f"Could not check NULL wikidata_id on {tbl} for {us}: {exc}; assuming work remains."
            )
            return True
        finally:
            cur.close()

    def _fetch_geoids_missing_wikidata_qid(self, state_code: str, wikidata_table: str) -> Set[str]:
        """GEOIDs (digits-only) for this USPS that still need a Wikidata QID."""
        if self._json_cache_dir:
            # In JSON mode, all GEOIDs are un-enriched; determine task from table name.
            us = state_code.upper()
            assert self._json_bronze is not None
            if "municipalities" in wikidata_table:
                return {r["geoid"] for r in self._json_bronze.get("municipalities", {}).get(us, [])}
            if "counties" in wikidata_table:
                return {r["geoid"] for r in self._json_bronze.get("counties", {}).get(us, [])}
            if "school_districts" in wikidata_table:
                return {r["geoid"] for r in self._json_bronze.get("school_districts", {}).get(us, [])}
            if "states" in wikidata_table:
                return {r["geoid"] for r in self._json_bronze.get("states_data", {}).get(us, [])}
            return set()
        cur = self.conn.cursor()
        try:
            cur.execute(
                f"""
                SELECT geoid::text
                FROM {wikidata_table}
                WHERE usps = %s
                  AND (wikidata_id IS NULL OR BTRIM(wikidata_id::text) = '')
                """,
                (state_code.upper(),),
            )
            return {str(r[0]).strip().replace("-", "") for r in cur.fetchall() if r and r[0]}
        except Exception as exc:
            logger.warning(f"Could not list missing wikidata_id GEOIDs on {wikidata_table}: {exc}")
            return set()
        finally:
            cur.close()

    def _apply_wikidata_updates(self, task: str, jurisdictions: List[Dict]) -> None:
        """Update the appropriate bronze *_wikidata table (or JSON cache) based on loader task."""
        if not jurisdictions:
            return

        if self._json_cache_dir:
            bucket = self._json_results.setdefault(task, [])
            bucket.extend(jurisdictions)
            logger.info(f"  JSON mode: accumulated {len(jurisdictions)} {task} row(s)")
            return

        if task == "county":
            table = "bronze.bronze_jurisdictions_counties_wikidata"
            key_field = "geoid"
            extra_cols = {
                "wikidata_fips_code": "fips_code",
                "wikidata_geoid": "geoid",
            }
        elif task == "city":
            table = "bronze.bronze_jurisdictions_municipalities_wikidata"
            key_field = "geoid"
            extra_cols = {
                "wikidata_fips_code": "fips_code",
                "wikidata_gnis_id": "gnis_id",
                "wikidata_geoid": "geoid",
            }
        elif task == "school_district":
            table = "bronze.bronze_jurisdictions_school_districts_wikidata"
            key_field = "geoid"
            extra_cols = {
                "wikidata_nces_id": "nces_id",
                "wikidata_geoid": "geoid",
            }
        elif task == "state":
            table = "bronze.bronze_jurisdictions_states_wikidata"
            key_field = "geoid"
            extra_cols = {
                "wikidata_fips_code": "fips_code",
                "wikidata_geoid": "geoid",
            }
        else:
            raise ValueError(f"Unknown update task: {task}")

        before_ct = len(jurisdictions)
        jurisdictions = [j for j in jurisdictions if j.get(key_field)]
        if before_ct and not jurisdictions:
            logger.warning(
                f"No {task} rows with {key_field=}; skipping bronze UPDATE ({before_ct} raw rows lacked join key)"
            )
            return
        if len(jurisdictions) < before_ct:
            logger.warning(
                f"Dropped {before_ct - len(jurisdictions)} {task} rows missing {key_field} "
                f"(bulk UPDATE targets {len(jurisdictions)})"
            )

        set_parts = [
            "wikidata_id = %(wikidata_id)s",
            "official_website = %(official_website)s",
            "official_image_url = %(official_image_url)s",
            "page_banner_image = %(page_banner_image)s",
            "locator_map_image = %(locator_map_image)s",
            "youtube_channel_id = %(youtube_channel_id)s",
            "youtube_channel_url = %(youtube_channel_url)s",
            "facebook_username = %(facebook_username)s",
            "facebook_url = %(facebook_url)s",
            "twitter_username = %(twitter_username)s",
            "twitter_url = %(twitter_url)s",
            "population = %(population)s",
            "area_sq_km = %(area_sq_km)s",
            "per_capita_income = %(per_capita_income)s",
            "number_of_households = %(number_of_households)s",
            "median_age = %(median_age)s",
            "time_zone = %(time_zone)s",
            "local_dialing_code = %(local_dialing_code)s",
            "google_maps_customer_id = %(google_maps_customer_id)s",
            "language_of_work_or_name = %(language_of_work_or_name)s",
            "head_of_government = %(head_of_government)s",
            "head_of_government_position = %(head_of_government_position)s",
            "head_of_government_start_time = %(head_of_government_start_time)s",
            "postal_codes = %(postal_codes)s::jsonb",
            "latitude = %(latitude)s",
            "longitude = %(longitude)s",
            "wikidata_fetched_at = CURRENT_TIMESTAMP",
            "wikidata_last_updated = CURRENT_TIMESTAMP",
        ]

        # State table has additional descriptive metadata columns
        if task == "state":
            set_parts.extend(
                [
                    "jurisdiction_label = %(jurisdiction_label)s",
                    "jurisdiction_description = %(jurisdiction_description)s",
                    "jurisdiction_aliases = %(jurisdiction_aliases)s::jsonb",
                    "native_label = %(native_label)s",
                    "nickname = %(nickname)s::jsonb",
                    "short_name = %(short_name)s::jsonb",
                    "demonym = %(demonym)s::jsonb",
                    "official_language = %(official_language)s::jsonb",
                    "motto = %(motto)s",
                    "anthem = %(anthem)s::jsonb",
                    "inception_date = %(inception_date)s",
                    "capital = %(capital)s::jsonb",
                    "iso_3166_2 = %(iso_3166_2)s",
                    "pronunciation_audio = %(pronunciation_audio)s",
                    "geoshape = %(geoshape)s",
                ]
            )

        for col, src in extra_cols.items():
            set_parts.append(f"{col} = %({src})s")

        update_sql = f"""
            UPDATE {table}
            SET {", ".join(set_parts)}
            WHERE geoid = %({key_field})s
        """

        required = {
            "wikidata_id",
            "official_website",
            "official_image_url",
            "page_banner_image",
            "locator_map_image",
            "youtube_channel_id",
            "youtube_channel_url",
            "facebook_username",
            "facebook_url",
            "twitter_username",
            "twitter_url",
            "population",
            "area_sq_km",
            "per_capita_income",
            "number_of_households",
            "median_age",
            "time_zone",
            "local_dialing_code",
            "google_maps_customer_id",
            "language_of_work_or_name",
            "head_of_government",
            "head_of_government_position",
            "head_of_government_start_time",
            "postal_codes",
            "latitude",
            "longitude",
            "fips_code",
            "gnis_id",
            "nces_id",
            "geoid",
            "jurisdiction_label",
            "jurisdiction_description",
            "jurisdiction_aliases",
            "native_label",
            "nickname",
            "short_name",
            "demonym",
            "official_language",
            "motto",
            "anthem",
            "inception_date",
            "capital",
            "iso_3166_2",
            "pronunciation_audio",
            "geoshape",
        }
        for j in jurisdictions:
            for k in required:
                j.setdefault(k, None)

        cur = self.conn.cursor()
        try:
            execute_batch(cur, update_sql, jurisdictions, page_size=200)
            self.conn.commit()
        finally:
            cur.close()
    
    async def query_all_jurisdictions_in_state(self, state_code: str, types: List[str]) -> List[Dict]:
        """Query WikiData for all jurisdiction types in a state using optimized two-pronged approach."""
        state_info = STATE_MAP.get(state_code)
        if not state_info:
            logger.error(f"Unknown state code: {state_code}")
            return []
        
        state_name = state_info["name"]
        state_q_code = state_info["q_code"]
        
        # Build type filters
        city_types = []
        county_types = []
        school_types = []
        
        if 'city' in types or 'town' in types:
            city_types = [JURISDICTION_TYPES['city'], JURISDICTION_TYPES['town']]
        
        if 'county' in types:
            county_types = [JURISDICTION_TYPES['county']]
        
        if 'school_district' in types:
            school_types = [JURISDICTION_TYPES['school_district']]
        
        all_jurisdictions = []
        
        # Query cities/towns separately with optimized approach
        if city_types:
            city_jurisdictions = await self._query_cities_in_state(state_code, state_q_code, state_name)
            all_jurisdictions.extend(city_jurisdictions)
        
        # Query counties separately
        if county_types:
            county_jurisdictions = await self._query_counties_in_state(state_code, state_q_code, state_name)
            all_jurisdictions.extend(county_jurisdictions)
        
        # Query school districts separately
        if school_types:
            school_jurisdictions = await self._query_schools_in_state(state_code, state_q_code, state_name)
            all_jurisdictions.extend(school_jurisdictions)
        
        logger.success(f"✓ Found {len(all_jurisdictions)} jurisdictions in {state_name}")
        return all_jurisdictions
    
    def _fetch_bronze_municipality_geoid_ansi_pairs(self, state_code: str) -> List[tuple[str, Optional[str]]]:
        if self._json_cache_dir:
            assert self._json_bronze is not None
            rows = self._json_bronze.get("municipalities", {}).get(state_code.upper(), [])
            pairs: List[tuple[str, Optional[str]]] = []
            for r in rows:
                geo = str(r.get("geoid") or "").strip().replace("-", "")
                if not geo:
                    continue
                ansi = r.get("ansicode")
                pairs.append((geo, str(ansi).strip() if ansi else None))
            return pairs
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                SELECT geoid, ansicode
                FROM bronze.bronze_jurisdictions_municipalities
                WHERE usps = %s
                ORDER BY geoid
                """,
                (state_code.upper(),),
            )
            pairs: List[tuple[str, Optional[str]]] = []
            for r in cur.fetchall():
                if not r or not r[0]:
                    continue
                geo = str(r[0]).strip().replace("-", "")
                a = r[1]
                ansi = str(a).strip() if a is not None else None
                pairs.append((geo, ansi if ansi else None))
            return pairs
        finally:
            cur.close()

    def _fetch_bronze_school_geoids(self, state_code: str) -> List[str]:
        if self._json_cache_dir:
            assert self._json_bronze is not None
            rows = self._json_bronze.get("school_districts", {}).get(state_code.upper(), [])
            return [str(r.get("geoid") or "").strip().replace("-", "") for r in rows if r.get("geoid")]
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                SELECT geoid
                FROM bronze.bronze_jurisdictions_school_districts
                WHERE usps = %s
                ORDER BY geoid
                """,
                (state_code.upper(),),
            )
            return [str(r[0]).strip().replace("-", "") for r in cur.fetchall() if r and r[0]]
        finally:
            cur.close()

    @staticmethod
    def _repair_city_geoids_from_ansi_map(jurisdictions: List[Dict], ansi_to_geoid: Dict[str, str]) -> None:
        if not ansi_to_geoid:
            return
        for j in jurisdictions:
            if j.get("jurisdiction_type") != "city":
                continue
            if j.get("geoid"):
                continue
            gid = j.get("gnis_id")
            if gid is None:
                continue
            ks = str(gid).strip()
            geo = ansi_to_geoid.get(ks)
            if geo is None and ks.isdigit():
                geo = ansi_to_geoid.get(ks.lstrip("0") or "0")
            if geo:
                j["geoid"] = geo
                if not j.get("jurisdiction_id"):
                    j["jurisdiction_id"] = ks
                    j["jurisdiction_id_type"] = "gnis_id"

    async def _query_cities_in_state_via_hybrid(
        self,
        state_code: str,
        state_q_code: str,
        state_name: str,
        pairs: List[tuple[str, Optional[str]]],
        ansi_to_geoid: Dict[str, str],
    ) -> List[Dict]:
        """
        Narrow WDQS: only resolve Census literals → Wikidata items; hydrate claims via
        ``wbgetentities`` (or Pywikibot when ``WIKIDATA_ENRICH_USE_PYWIKIBOT=1``).
        Default: **one** bulk WDQS query per state (P131+ / place types) + in-memory match;
        ``WIKIDATA_HYBRID_MUNICIPALITY_MAP_MODE=sparql`` keeps FILTER-batched maps per chunk.
        Mappings accumulate in ``geography_qid_mapping_v1.json`` for incremental reruns.
        """
        self.warm_geography_qid_cache_from_db(state_code, "city")
        qcache = self.geography_qid_cache()
        chunk_size = _positive_int_env("WIKIDATA_CITY_CHUNK_SIZE", 25, 5, 150)
        chunk_sleep = _chunk_sleep_seconds(1.0)
        aggregated: List[Dict] = []
        n_chunks = (len(pairs) + chunk_size - 1) // chunk_size

        map_mode = _wikidata_hybrid_municipality_map_mode()
        bulk_rows: Optional[List[Dict]] = None
        use_bulk = False
        sq = (state_q_code or "").strip()
        if map_mode == "bulk_state" and sq:
            blim = _positive_int_env("WIKIDATA_MUNICIPALITY_BULK_STATE_LIMIT", 8000, 200, 12000)
            mq = _wikidata_hybrid_sql.municipality_bulk_by_state_sparql(state_q_code, blim)
            try:
                pre_b = _municipality_pre_bulk_wdqs_pause_seconds()
                if pre_b > 0:
                    logger.info(
                        f"Waiting {pre_b:.0f}s before municipality bulk WDQS "
                        f"(WIKIDATA_MUNICIPALITY_PRE_BULK_WDQS_PAUSE_SECONDS — reduces immediate 429 on cold start)…"
                    )
                    await asyncio.sleep(pre_b)
                logger.info(
                    f"Hybrid municipalities: one WDQS query (P131+ state, US place types) for {state_name}…"
                )
                raw_b = await self.wikidata.execute_sparql(mq)
                bulk_rows = self._dedupe_sparql_bindings_by_item(raw_b or [])
                use_bulk = len(bulk_rows) > 0
                for mr in bulk_rows or []:
                    iq = (mr.get("item") or "").rsplit("/", 1)[-1].strip()
                    if iq.startswith("Q"):
                        qcache.remember_muni(iq, mr.get("fips"), mr.get("gnis"))
                logger.info(
                    f"  Bulk WDQS: {len(bulk_rows or [])} distinct place item(s) under this state "
                    f"(P131+/types). Next chunks: for each bronze GEOID, resolve Q via "
                    f"literal cache → scan bulk bindings (P774/P590) → optional FILTER IN → wbgetentities."
                )
                if use_bulk and not _wikidata_municipality_bulk_supplement_sparql():
                    logger.info(
                        "  WIKIDATA_MUNICIPALITY_BULK_SUPPLEMENT_SPARQL=0 — "
                        "no supplemental FILTER IN per chunk; bulk + cache matches only."
                    )
            except Exception as e:
                logger.warning(f"Bulk state municipality WDQS failed: {type(e).__name__}: {e}")
                bulk_rows = None

        inner_mode = map_mode
        if map_mode == "bulk_state" and not use_bulk:
            if not _wikidata_municipality_sparql_when_bulk_empty():
                logger.error(
                    "Hybrid municipalities: bulk WDQS returned **no rows** or **failed** for this state. "
                    "Not falling back to per-chunk FILTER IN queries "
                    "(WIKIDATA_MUNICIPALITY_SPARQL_WHEN_BULK_EMPTY=0 — default under --happy-path). "
                    "Otherwise WDQS spams the same heavy query and 429s. Fix: delete stale JSON under "
                    "WIKIDATA_CACHE_DIR for empty bulk responses, retry when WDQS is quiet, or set "
                    "WIKIDATA_MUNICIPALITY_SPARQL_WHEN_BULK_EMPTY=1 to allow the heavy fallback."
                )
                return []
            inner_mode = "sparql"
            logger.warning(
                "bulk_state returned no data — municipality mapping uses FILTER batches per chunk"
            )

        if (
            use_bulk
            and map_mode == "bulk_state"
            and _wikidata_municipality_bulk_supplement_sparql()
        ):
            gap_pb = _municipality_post_bulk_wdqs_gap_seconds()
            if gap_pb > 0:
                logger.info(
                    f"  Waiting {gap_pb:.0f}s after bulk WDQS before FILTER supplements "
                    f"(WIKIDATA_MUNICIPALITY_POST_BULK_WDQS_GAP_SECONDS; eases WDQS 429)…"
                )
                await asyncio.sleep(gap_pb)

        for ix in range(0, len(pairs), chunk_size):
            chunk = pairs[ix : ix + chunk_size]
            chi = ix // chunk_size + 1
            mlabel = "bulk-state" if use_bulk else "WDQS-map"
            logger.info(
                f"Hybrid municipalities {mlabel} chunk {chi}/{n_chunks} "
                f"({len(chunk)} bronze places, {state_name})…"
            )

            geo_to_q: Dict[str, str] = {}
            n_map_cache = 0
            n_map_bulk = 0

            need_fips: Set[str] = set()
            need_gnis: Set[str] = set()

            for geo, ansi in chunk:
                gid = str(geo).strip()
                ff, gg = _municipality_wd_literal_sets(geo, ansi)
                cq = qcache.lookup_q_for_municipality(ff, gg)
                if cq:
                    geo_to_q[gid] = cq
                    n_map_cache += 1
                    continue
                if use_bulk:
                    matched_q: Optional[str] = None
                    for mr in bulk_rows or []:
                        if self._municipality_mapping_row_matches_literals(mr, ff, gg):
                            iq = (mr.get("item") or "").rsplit("/", 1)[-1].strip()
                            if iq.startswith("Q"):
                                matched_q = iq
                                break
                    if matched_q:
                        geo_to_q[gid] = matched_q
                        n_map_bulk += 1
                        continue
                # Pure sparql mode (no bulk rows): every miss needs a FILTER batch.
                if inner_mode == "sparql" and not use_bulk:
                    need_fips |= ff
                    need_gnis |= gg
                # Bulk mode: optional second WDQS query (FILTER IN) for rows bulk did not match.
                elif use_bulk and _wikidata_municipality_bulk_supplement_sparql():
                    need_fips |= ff
                    need_gnis |= gg

            n_after_pass1 = len(geo_to_q)

            mapping_rows: List[Dict] = []
            supplement_wdqs_ran = False
            if need_fips or need_gnis:
                lim = min(5000, max(400, len(chunk) * 60))
                n_lit_f = len(need_fips)
                n_lit_g = len(need_gnis)
                n_miss_p1 = len(chunk) - n_after_pass1
                gapf = _municipality_filter_wdqs_gap_seconds()
                logger.info(
                    f"  chunk {chi}/{n_chunks}: pass-1 done — cache={n_map_cache}, bulk_match={n_map_bulk}, "
                    f"unmapped={n_miss_p1}/{len(chunk)} → UNION WDQS (FIPS {n_lit_f} lits, GNIS {n_lit_g} lits)…"
                )
                if gapf > 0:
                    await asyncio.sleep(gapf)
                try:
                    mapping_rows = await self._wdqs_municipality_mapping_chunked(
                        need_fips, need_gnis, lim, chi, n_chunks
                    )
                    mapping_rows = self._dedupe_sparql_bindings_by_item(mapping_rows or [])
                except Exception as e:
                    logger.warning(f"Hybrid city mapping WDQS failed ({chi}/{n_chunks}): {type(e).__name__}: {e}")
                    mapping_rows = []
                supplement_wdqs_ran = True
                mapping_rows = self._dedupe_sparql_bindings_by_item(mapping_rows)
                for mr in mapping_rows:
                    iq = (mr.get("item") or "").rsplit("/", 1)[-1].strip()
                    if not iq.startswith("Q"):
                        continue
                    qcache.remember_muni(iq, mr.get("fips"), mr.get("gnis"))
                logger.info(
                    f"  chunk {chi}/{n_chunks}: FILTER supplement WDQS → {len(mapping_rows)} distinct item(s); "
                    f"reconciling GEOID→Q via cache…"
                )
            else:
                n_miss = len(chunk) - n_after_pass1
                sup = _wikidata_municipality_bulk_supplement_sparql()
                hint = ""
                if n_miss:
                    hint = (
                        " — set WIKIDATA_MUNICIPALITY_BULK_SUPPLEMENT_SPARQL=1 for FILTER WDQS on misses"
                        if use_bulk and not sup
                        else " (run backfill / wider matching later)"
                    )
                logger.info(
                    f"  chunk {chi}/{n_chunks}: id→Q pass-1 — geography cache={n_map_cache}, "
                    f"bulk WDQS row match={n_map_bulk}, GEOIDs_with_Q={n_after_pass1}/{len(chunk)}"
                    f"{hint}"
                )

            for geo, ansi in chunk:
                gid = str(geo).strip()
                if gid in geo_to_q:
                    continue
                ff, gg = _municipality_wd_literal_sets(geo, ansi)
                iq = qcache.lookup_q_for_municipality(ff, gg)
                if iq:
                    geo_to_q[gid] = iq

            n_map_supplement = len(geo_to_q) - n_after_pass1
            n_mapped_geo = sum(1 for g, _ in chunk if str(g).strip() in geo_to_q)
            n_unmapped = len(chunk) - n_mapped_geo

            chunk_geos = {str(g).strip() for g, _ in chunk}
            q_needed = sorted({geo_to_q[g] for g in chunk_geos if g in geo_to_q})
            if not q_needed:
                qcache.save()
                if supplement_wdqs_ran:
                    logger.info(
                        f"  chunk {chi}/{n_chunks}: done — no wbgetentities (no GEOID resolved to a Q-id in this chunk)."
                    )
                else:
                    logger.info(
                        f"  chunk {chi}/{n_chunks}: done — mapped GEOIDs={n_mapped_geo}/{len(chunk)}; "
                        f"no hydrate step (all unmapped or no Q-ids)."
                    )
                continue

            enriched: List[Dict] = []
            py_try = try_pywikibot_rows(q_needed)
            if py_try is not None:
                enriched.extend(py_try)
            else:
                api_payload = await self.wikidata.wikibase_get_entities(q_needed)
                enriched.extend(entities_response_to_rows({"entities": api_payload}))
            logger.info(
                f"  chunk {chi}/{n_chunks}: hydrate — wbgetentities(Pywikibot) for {len(q_needed)} Q-id(s) "
                f"(labels/claims); GEOIDs with Q this chunk={n_mapped_geo}/{len(chunk)}"
                + (f", +{n_map_supplement} from FILTER+relookup" if n_map_supplement > 0 else "")
                + (f"; {n_unmapped} GEOID(s) still without Q — backfill later" if n_unmapped else "")
            )

            by_q: Dict[str, Dict] = {}
            for row in enriched:
                u = row.get("item") or ""
                iq = str(u).rsplit("/", 1)[-1]
                if iq.startswith("Q"):
                    by_q[iq] = row

            chunk_out: List[Dict] = []
            for geo, ansi in chunk:
                gid = str(geo).strip()
                qid = geo_to_q.get(gid)
                if not qid:
                    continue
                raw = by_q.get(qid)
                if not raw:
                    continue
                pj = self._parse_jurisdiction_results([raw], state_code, state_name, "city")
                if pj:
                    j0 = pj[0]
                    j0["geoid"] = gid
                    chunk_out.append(j0)

            self._repair_city_geoids_from_ansi_map(chunk_out, ansi_to_geoid)
            if chunk_out and _wikidata_municipality_flush_db_each_chunk():
                self.insert_jurisdictions(chunk_out)
                self._municipality_chunk_db_flush_used = True
                logger.info(
                    f"  chunk {chi}/{n_chunks}: committed {len(chunk_out)} row(s) to "
                    f"bronze.bronze_jurisdictions_municipalities_wikidata (per-chunk flush)"
                )
            aggregated.extend(chunk_out)
            qcache.save()
            if chunk_sleep > 0 and chi < n_chunks:
                await asyncio.sleep(chunk_sleep)

        n_pairs = len(pairs)
        logger.info(f"  Found {len(aggregated)} cities (hybrid)")
        if n_pairs and len(aggregated) == 0:
            logger.error(
                f"Hybrid municipalities for {state_code}: 0 Postgres-ready rows despite {n_pairs} bronze "
                f"places — no GEOID→Q resolution + hydrate (no rows for insert_jurisdictions). "
                f"Common: WIKIDATA_MUNICIPALITY_BULK_SUPPLEMENT_SPARQL=0 (happy path) while bulk P131+ did not "
                f"match Census literals — set supplement=1; or WDQS 429/throttle. "
                f"Verify NULLs: SELECT COUNT(*) FROM bronze.bronze_jurisdictions_municipalities_wikidata "
                f"WHERE usps = '{state_code.upper()}' AND (wikidata_id IS NULL OR BTRIM(wikidata_id::text) = '');"
            )
        elif n_pairs and len(aggregated) < n_pairs:
            logger.warning(
                f"Hybrid municipalities for {state_code}: enriched {len(aggregated)}/{n_pairs} places this run — "
                f"remaining bronze rows still have NULL wikidata_id until supplement/backfill."
            )
        return aggregated

    async def _query_counties_in_state_via_hybrid(self, state_code: str, state_q_code: str, state_name: str) -> List[Dict]:
        self.warm_geography_qid_cache_from_db(state_code, "county")
        qcache = self.geography_qid_cache()

        legacy_wide = False
        _legacy_env = (os.getenv("WIKIDATA_COUNTY_LEGACY_STATE_QUERY") or "").strip()
        if _legacy_env:
            legacy_wide = _env_truthy("WIKIDATA_COUNTY_LEGACY_STATE_QUERY", default=False)
        else:
            legacy_wide = not _env_truthy("WIKIDATA_COUNTY_FIPS_BATCH", default=True)
        if legacy_wide:
            return await self._query_counties_in_state_wide(
                _county_type_values_clause(state_code), state_q_code, state_name, state_code
            )

        geoids = self._fetch_bronze_county_geoids(state_code)
        if not geoids:
            return await self._query_counties_in_state_wide(
                _county_type_values_clause(state_code), state_q_code, state_name, state_code
            )

        if _wikidata_incremental_merge():
            miss = self._fetch_geoids_missing_wikidata_qid(
                state_code, "bronze.bronze_jurisdictions_counties_wikidata"
            )
            geoids = [g for g in geoids if g in miss]
            if not geoids:
                logger.info(f"Hybrid county incremental: nothing pending for USPS {state_code}")
                return []

        sf = STATE_MAP.get(state_code, {}).get("fips")
        try:
            raw_chunk_sz = os.getenv("WIKIDATA_COUNTY_CHUNK_SIZE", "35") or "35"
            csize = max(5, min(120, int(str(raw_chunk_sz).strip())))
        except ValueError:
            csize = 35
        chunk_sleep = _chunk_sleep_seconds(1.0)
        ctype = _county_type_values_clause(state_code)
        map_mode = _wikidata_hybrid_county_map_mode()
        pair_by_g = dict(self._fetch_bronze_county_geoid_name_pairs(state_code))
        agg: List[Dict] = []
        n_chunks = (len(geoids) + csize - 1) // csize

        bulk_rows: Optional[List[Dict]] = None
        use_bulk = False
        if map_mode == "bulk_state":
            blim = _positive_int_env("WIKIDATA_COUNTY_BULK_STATE_LIMIT", 600, 50, 2000)
            mq = _wikidata_hybrid_sql.county_bulk_by_state_sparql(ctype, state_q_code, blim)
            try:
                logger.info(
                    f"Hybrid counties: one WDQS query (P131 = state, US county types) for {state_name}…"
                )
                raw_b = await self.wikidata.execute_sparql(mq)
                bulk_rows = self._dedupe_sparql_bindings_by_item(raw_b or [])
                use_bulk = len(bulk_rows) > 0
                for mr in bulk_rows:
                    iq = (mr.get("item") or "").rsplit("/", 1)[-1].strip()
                    if iq.startswith("Q"):
                        qcache.remember_county(iq, mr.get("fips"), mr.get("fipsAlt"), mr.get("gnis"))
                logger.info(
                    f"  Bulk WDQS returned {len(bulk_rows)} row(s); matching {len(geoids)} bronze GEOIDs in memory"
                )
            except Exception as e:
                logger.warning(f"Bulk state county WDQS failed: {type(e).__name__}: {e}")
                bulk_rows = None

        inner_mode = map_mode
        if map_mode == "bulk_state" and not use_bulk:
            inner_mode = (
                "entity_search" if _env_truthy("WIKIDATA_COUNTY_BULK_FALLBACK_ENTITY_SEARCH", True) else "sparql"
            )
            logger.warning(
                f"bulk_state returned no data — inner mapping for this state uses {inner_mode!r}"
            )

        for ix in range(0, len(geoids), csize):
            chunk = geoids[ix : ix + csize]
            chi = ix // csize + 1
            if use_bulk:
                mlabel = "bulk-state"
            elif inner_mode == "entity_search":
                mlabel = "entity-search"
            else:
                mlabel = "WDQS-map"
            logger.info(f"Hybrid counties {mlabel} chunk {chi}/{n_chunks} ({state_name})…")
            geo_to_q: Dict[str, str] = {}

            if use_bulk:
                fb_ent = _env_truthy("WIKIDATA_COUNTY_BULK_FALLBACK_ENTITY_SEARCH", True)
                n_in_chunk = len(chunk)
                for j, gid in enumerate(chunk, start=1):
                    g = str(gid).strip()
                    lits = _county_fips_literal_alternatives(gid, sf)
                    cq = qcache.lookup_q_for_county(lits)
                    if cq:
                        geo_to_q[g] = cq
                        logger.info(f"  [{j}/{n_in_chunk}] GEOID {g}: literal cache hit → {cq}")
                        continue
                    matched_q: Optional[str] = None
                    for mr in bulk_rows or []:
                        if self._county_mapping_row_matches_geoid_literals(mr, lits):
                            iq = (mr.get("item") or "").rsplit("/", 1)[-1].strip()
                            if iq.startswith("Q"):
                                matched_q = iq
                                break
                    if matched_q:
                        geo_to_q[g] = matched_q
                        logger.info(f"  [{j}/{n_in_chunk}] GEOID {g} → {matched_q} (bulk match)")
                    elif fb_ent:
                        display_name = pair_by_g.get(g, "")
                        nm = (display_name or "").strip() or "(no gazetteer name in bronze)"
                        logger.info(f"  [{j}/{n_in_chunk}] GEOID {g} — {nm[:56]} — bulk miss, entity-search fallback…")
                        res = await self._county_resolve_via_entity_search(
                            display_name, state_name, state_q_code, lits
                        )
                        if res:
                            qid, ent = res
                            geo_to_q[g] = qid
                            row_mini = entity_to_wdqs_like_row(ent, qid)
                            qcache.remember_county(
                                qid,
                                row_mini.get("fips"),
                                row_mini.get("fipsAlt"),
                                row_mini.get("gnis"),
                            )
                            logger.info(f"  [{j}/{n_in_chunk}] GEOID {g} → {qid} (fallback)")
                        else:
                            logger.warning(
                                f"  [{j}/{n_in_chunk}] entity-search fallback miss GEOID={g} "
                                f"name={nm[:40]!r}"
                            )
                    else:
                        logger.warning(
                            f"  [{j}/{n_in_chunk}] bulk miss, no fallback GEOID={g} lits={sorted(lits)[:8]}"
                        )

            elif inner_mode == "entity_search":
                n_in_chunk = len(chunk)
                for j, gid in enumerate(chunk, start=1):
                    g = str(gid).strip()
                    lits = _county_fips_literal_alternatives(gid, sf)
                    cq = qcache.lookup_q_for_county(lits)
                    if cq:
                        geo_to_q[g] = cq
                        logger.info(f"  [{j}/{n_in_chunk}] GEOID {g}: literal cache hit → {cq}")
                        continue
                    display_name = pair_by_g.get(g, "")
                    nm = (display_name or "").strip() or "(no gazetteer name in bronze)"
                    logger.info(
                        f"  [{j}/{n_in_chunk}] GEOID {g} — {nm[:72]} — "
                        f"wbsearchentities + wbgetentities (may take seconds per county; respects throttle)…"
                    )
                    res = await self._county_resolve_via_entity_search(
                        display_name, state_name, state_q_code, lits
                    )
                    if res:
                        qid, ent = res
                        geo_to_q[g] = qid
                        row_mini = entity_to_wdqs_like_row(ent, qid)
                        qcache.remember_county(
                            qid,
                            row_mini.get("fips"),
                            row_mini.get("fipsAlt"),
                            row_mini.get("gnis"),
                        )
                        logger.info(f"  [{j}/{n_in_chunk}] GEOID {g} → {qid} (identifiers matched)")
                    else:
                        logger.warning(
                            f"  [{j}/{n_in_chunk}] entity-search miss GEOID={g} name={nm[:48]!r} "
                            f"lits={sorted(lits)[:8]}…"
                        )
            else:
                literals: Set[str] = set()
                for gid in chunk:
                    lits = _county_fips_literal_alternatives(gid, sf)
                    cq = qcache.lookup_q_for_county(lits)
                    if cq:
                        geo_to_q[str(gid).strip()] = cq
                    else:
                        literals |= lits

                mapping_rows: List[Dict] = []
                if literals:
                    cz = _wikidata_filter_in_literal_chunk_size()
                    gap_sub = _wikidata_filter_in_subquery_gap_seconds()
                    lim = min(2500, max(520, len(chunk) * 25))
                    batches = _batched_sorted_literals(literals, cz)
                    if len(batches) > 1:
                        logger.info(
                            f"  county FILTER IN → {len(batches)} WDQS sub-queries "
                            f"(≤{cz} literals; gap={gap_sub:.1f}s)"
                        )
                    acc_co: List[Dict] = []
                    for bi, batch in enumerate(batches):
                        if gap_sub > 0 and bi > 0:
                            await asyncio.sleep(gap_sub)
                        in_list = ", ".join(_sparql_quote_string_literal(x) for x in batch)
                        mq = _wikidata_hybrid_sql.county_mapping_sparql(ctype, in_list, lim)
                        try:
                            acc_co.extend(await self.wikidata.execute_sparql(mq) or [])
                        except Exception as e:
                            logger.warning(f"Hybrid county mapping failed: {type(e).__name__}: {e}")
                    mapping_rows = self._dedupe_sparql_bindings_by_item(acc_co)
                    for mr in mapping_rows:
                        iq = (mr.get("item") or "").rsplit("/", 1)[-1].strip()
                        if iq.startswith("Q"):
                            qcache.remember_county(iq, mr.get("fips"), mr.get("fipsAlt"), mr.get("gnis"))

                    for gid in chunk:
                        g = str(gid).strip()
                        if g in geo_to_q:
                            continue
                        lits2 = _county_fips_literal_alternatives(gid, sf)
                        cq2 = qcache.lookup_q_for_county(lits2)
                        if cq2:
                            geo_to_q[g] = cq2

            chunk_geoids = {str(g).strip() for g in chunk}
            q_needed = sorted({geo_to_q[g] for g in chunk_geoids if g in geo_to_q})
            if not q_needed:
                qcache.save()
                continue

            logger.info(
                f"  Hydrating {len(q_needed)} distinct county Q-id(s) via wbgetentities / Pywikibot "
                f"(chunk {chi}/{n_chunks})…"
            )

            enriched: List[Dict] = []
            py_try = try_pywikibot_rows(q_needed)
            if py_try is not None:
                enriched.extend(py_try)
            else:
                enriched.extend(
                    entities_response_to_rows({"entities": await self.wikidata.wikibase_get_entities(q_needed)})
                )

            by_q: Dict[str, Dict] = {}
            for row in enriched:
                u = row.get("item") or ""
                iq = str(u).rsplit("/", 1)[-1]
                if iq.startswith("Q"):
                    by_q[iq] = row

            for gid in chunk:
                g = str(gid).strip()
                qid = geo_to_q.get(g)
                if not qid:
                    continue
                raw = by_q.get(qid)
                if not raw:
                    continue
                pj = self._parse_jurisdiction_results([raw], state_code, state_name, "county")
                if pj:
                    j0 = pj[0]
                    j0["geoid"] = g
                    agg.append(j0)
            qcache.save()
            if chunk_sleep > 0 and chi < n_chunks:
                await asyncio.sleep(chunk_sleep)

        logger.info(f"  Found {len(agg)} counties (hybrid)")
        return agg

    async def _query_schools_in_state_via_hybrid(self, state_code: str, state_q_code: str, state_name: str) -> List[Dict]:
        self.warm_geography_qid_cache_from_db(state_code, "school_district")
        qcache = self.geography_qid_cache()

        _legacy_s = (os.getenv("WIKIDATA_SCHOOL_LEGACY_STATE_QUERY") or "").strip()
        if _legacy_s:
            legacy_wide = _env_truthy("WIKIDATA_SCHOOL_LEGACY_STATE_QUERY", default=False)
        else:
            legacy_wide = not _env_truthy("WIKIDATA_SCHOOL_IDENTIFIER_BATCH", default=True)
        if legacy_wide:
            return await self._query_schools_in_state_wide(state_code, state_q_code, state_name)

        geoids = self._fetch_bronze_school_geoids(state_code)
        if not geoids:
            return await self._query_schools_in_state_wide(state_code, state_q_code, state_name)

        if _wikidata_incremental_merge():
            miss = self._fetch_geoids_missing_wikidata_qid(
                state_code, "bronze.bronze_jurisdictions_school_districts_wikidata"
            )
            geoids = [g for g in geoids if g in miss]
            if not geoids:
                logger.info(f"Hybrid school incremental: nothing pending for USPS {state_code}")
                return []

        chunk_size = _positive_int_env("WIKIDATA_SCHOOL_CHUNK_SIZE", 35, 5, 200)
        chunk_sleep = _chunk_sleep_seconds(1.0)
        agg: List[Dict] = []
        n_chunks = (len(geoids) + chunk_size - 1) // chunk_size

        map_mode = _wikidata_hybrid_school_map_mode()
        bulk_rows: Optional[List[Dict]] = None
        use_bulk = False
        sq = (state_q_code or "").strip()
        if map_mode == "bulk_state" and sq:
            blim = _positive_int_env("WIKIDATA_SCHOOL_BULK_STATE_LIMIT", 2500, 100, 5000)
            mq = _wikidata_hybrid_sql.school_bulk_by_state_sparql(state_q_code, blim)
            try:
                logger.info(
                    f"Hybrid school districts: one WDQS query (P131+ state, Q1455778) for {state_name}…"
                )
                raw_b = await self.wikidata.execute_sparql(mq)
                bulk_rows = self._dedupe_sparql_bindings_by_item(raw_b or [])
                use_bulk = len(bulk_rows) > 0
                for mr in bulk_rows or []:
                    iq = (mr.get("item") or "").rsplit("/", 1)[-1].strip()
                    if iq.startswith("Q"):
                        qcache.remember_school(iq, mr.get("fips"), mr.get("gnis"), mr.get("nces"))
                logger.info(
                    f"  Bulk WDQS returned {len(bulk_rows or [])} row(s); "
                    f"matching {len(geoids)} bronze district GEOIDs in memory"
                )
                if use_bulk and not _wikidata_school_bulk_supplement_sparql():
                    logger.info(
                        "  WIKIDATA_SCHOOL_BULK_SUPPLEMENT_SPARQL=0 — "
                        "no supplemental FILTER IN per chunk; bulk + cache matches only."
                    )
            except Exception as e:
                logger.warning(f"Bulk state school-district WDQS failed: {type(e).__name__}: {e}")
                bulk_rows = None

        inner_mode = map_mode
        if map_mode == "bulk_state" and not use_bulk:
            inner_mode = "sparql"
            logger.warning(
                "bulk_state returned no data — school id→Q mapping uses FILTER batches per chunk"
            )

        if use_bulk and map_mode == "bulk_state" and _wikidata_school_bulk_supplement_sparql():
            gap_pb = _school_post_bulk_wdqs_gap_seconds()
            if gap_pb > 0:
                logger.info(
                    f"  Waiting {gap_pb:.0f}s after bulk WDQS before FILTER supplements "
                    f"(WIKIDATA_SCHOOL_POST_BULK_WDQS_GAP_SECONDS; eases WDQS 429)…"
                )
                await asyncio.sleep(gap_pb)

        for ix in range(0, len(geoids), chunk_size):
            chunk = geoids[ix : ix + chunk_size]
            chi = ix // chunk_size + 1
            mlabel = "bulk-state" if use_bulk else "WDQS-map"
            logger.info(f"Hybrid school districts {mlabel} chunk {chi}/{n_chunks} ({state_name})…")
            geo_to_q: Dict[str, str] = {}
            literals: Set[str] = set()
            for gid in chunk:
                g = str(gid).strip()
                lits = _school_id_literal_alternatives(gid)
                cq = qcache.lookup_q_for_school(lits)
                if cq:
                    geo_to_q[g] = cq
                    continue
                if use_bulk:
                    matched_q: Optional[str] = None
                    for mr in bulk_rows or []:
                        if self._school_mapping_row_matches_literals(mr, lits):
                            iq = (mr.get("item") or "").rsplit("/", 1)[-1].strip()
                            if iq.startswith("Q"):
                                matched_q = iq
                                break
                    if matched_q:
                        geo_to_q[g] = matched_q
                        continue
                if inner_mode == "sparql" and not use_bulk:
                    literals |= lits
                elif use_bulk and _wikidata_school_bulk_supplement_sparql():
                    literals |= lits

            mapping_rows: List[Dict] = []
            if literals:
                cz = _wikidata_filter_in_literal_chunk_size()
                gap_sub = _wikidata_filter_in_subquery_gap_seconds()
                lim = min(2500, max(520, len(chunk) * 28))
                batches = _batched_sorted_literals(literals, cz)
                if len(batches) > 1:
                    logger.info(
                        f"  school FILTER IN → {len(batches)} WDQS sub-queries "
                        f"(≤{cz} literals; gap={gap_sub:.1f}s)"
                    )
                gapf = _school_filter_wdqs_gap_seconds()
                if gapf > 0:
                    await asyncio.sleep(gapf)
                acc_sd: List[Dict] = []
                for bi, batch in enumerate(batches):
                    if gap_sub > 0 and bi > 0:
                        await asyncio.sleep(gap_sub)
                    id_in = ", ".join(_sparql_quote_string_literal(x) for x in batch)
                    mq = _wikidata_hybrid_sql.school_mapping_sparql(id_in, lim)
                    try:
                        acc_sd.extend(await self.wikidata.execute_sparql(mq) or [])
                    except Exception as e:
                        logger.warning(f"Hybrid school mapping failed: {type(e).__name__}: {e}")
                mapping_rows = self._dedupe_sparql_bindings_by_item(acc_sd)
                for mr in mapping_rows:
                    iq = (mr.get("item") or "").rsplit("/", 1)[-1].strip()
                    if iq.startswith("Q"):
                        qcache.remember_school(iq, mr.get("fips"), mr.get("gnis"), mr.get("nces"))

                for gid in chunk:
                    g = str(gid).strip()
                    if g in geo_to_q:
                        continue
                    lits = _school_id_literal_alternatives(gid)
                    cq = qcache.lookup_q_for_school(lits)
                    if cq:
                        geo_to_q[g] = cq

            chunk_geoids = {str(g).strip() for g in chunk}
            q_needed = sorted({geo_to_q[g] for g in chunk_geoids if g in geo_to_q})
            if not q_needed:
                qcache.save()
                continue

            py_rows = try_pywikibot_rows(q_needed)
            if py_rows is not None:
                enriched = py_rows
            else:
                enriched = entities_response_to_rows(
                    {"entities": await self.wikidata.wikibase_get_entities(q_needed)}
                )

            by_q: Dict[str, Dict] = {}
            for row in enriched:
                u = row.get("item") or ""
                iq = str(u).rsplit("/", 1)[-1]
                if iq.startswith("Q"):
                    by_q[iq] = row

            for gid in chunk:
                g = str(gid).strip()
                qid = geo_to_q.get(g)
                if not qid:
                    continue
                raw = by_q.get(qid)
                if not raw:
                    continue
                pj = self._parse_jurisdiction_results([raw], state_code, state_name, "school_district")
                if pj:
                    j0 = pj[0]
                    j0["geoid"] = g
                    agg.append(j0)
            qcache.save()
            if chunk_sleep > 0 and chi < n_chunks:
                await asyncio.sleep(chunk_sleep)

        logger.info(f"  Found {len(agg)} school districts (hybrid)")
        return agg

    async def _query_cities_in_state(self, state_code: str, state_q_code: str, state_name: str) -> List[Dict]:
        """Places: default batch by bronze GEOID / GNIS (+P774/+P590) to avoid flaky P131+ on WDQS."""

        _legacy_city = (os.getenv("WIKIDATA_CITY_LEGACY_STATE_QUERY") or "").strip()
        if _legacy_city:
            legacy_wide = _env_truthy("WIKIDATA_CITY_LEGACY_STATE_QUERY", default=False)
        else:
            legacy_wide = not _env_truthy("WIKIDATA_CITY_IDENTIFIER_BATCH", default=True)

        if legacy_wide:
            return await self._query_cities_in_state_wide(state_code, state_q_code, state_name)

        pairs = self._fetch_bronze_municipality_geoid_ansi_pairs(state_code)
        if not pairs:
            logger.warning(
                f"No bronze municipality rows for {state_code}; falling back to P131+ Wikidata crawl."
            )
            return await self._query_cities_in_state_wide(state_code, state_q_code, state_name)

        if _wikidata_incremental_merge():
            miss = self._fetch_geoids_missing_wikidata_qid(
                state_code, "bronze.bronze_jurisdictions_municipalities_wikidata"
            )
            pairs = [p for p in pairs if p[0] in miss]
            if not pairs:
                logger.info(
                    f"Incremental merge: no municipalities with NULL wikidata_id for {state_name} — skipping WDQS"
                )
                return []

        ansi_to_geoid: Dict[str, str] = {}
        for geo, ansi in pairs:
            if ansi:
                ansi_to_geoid[str(ansi).strip()] = geo

        if _wikidata_hybrid_enrich_enabled():
            return await self._query_cities_in_state_via_hybrid(
                state_code, state_q_code, state_name, pairs, ansi_to_geoid
            )

        chunk_size = _positive_int_env("WIKIDATA_CITY_CHUNK_SIZE", 25, 5, 150)
        chunk_sleep = _chunk_sleep_seconds(1.0)

        aggregated: List[Dict] = []
        n_chunks = (len(pairs) + chunk_size - 1) // chunk_size
        for ix in range(0, len(pairs), chunk_size):
            chunk = pairs[ix : ix + chunk_size]
            fips_lit: Set[str] = set()
            gnis_lit: Set[str] = set()
            for geo, ansi in chunk:
                ff, gg = _municipality_wd_literal_sets(geo, ansi)
                fips_lit |= ff
                gnis_lit |= gg

            if not fips_lit and not gnis_lit:
                logger.warning(f"City batch has no literals (chunk)—skipping WDQS.")
                continue

            limit_rows = min(5000, max(400, chunk_size * 60))
            chi = ix // chunk_size + 1
            logger.info(f"Querying municipalities in {state_name} via identifier batch ({chi}/{n_chunks})…")

            cz = _wikidata_filter_in_literal_chunk_size()
            gap_sub = _wikidata_filter_in_subquery_gap_seconds()
            f_batches = _batched_sorted_literals(fips_lit, cz)
            g_batches = _batched_sorted_literals(gnis_lit, cz)
            sub_seq: List[Tuple[str, List[str]]] = [("fips", b) for b in f_batches] + [
                ("gnis", b) for b in g_batches
            ]
            if len(sub_seq) > 1:
                logger.info(
                    f"  chunk {chi}/{n_chunks}: FILTER IN → {len(sub_seq)} WDQS sub-queries "
                    f"(≤{cz} literals; gap={gap_sub:.1f}s)"
                )

            chunk_rows: List[Dict] = []
            for si, (branch, batch) in enumerate(sub_seq):
                if gap_sub > 0 and si > 0:
                    await asyncio.sleep(gap_sub)
                branches_sparql: List[str] = []
                if branch == "fips":
                    f_in = ", ".join(_sparql_quote_string_literal(x) for x in batch)
                    branches_sparql.append(
                        f"{{ ?item wdt:P774 ?fips . FILTER(REPLACE(STR(?fips), \"-\", \"\") IN ({f_in})) }}"
                    )
                else:
                    g_in = ", ".join(_sparql_quote_string_literal(x) for x in batch)
                    branches_sparql.append(f"{{ ?item wdt:P590 ?gnis . FILTER(?gnis IN ({g_in})) }}")
                union_block = "\n              UNION\n              ".join(branches_sparql)
                query = f"""
            SELECT DISTINCT
                ?item ?itemLabel
                ?website ?population ?area
                ?facebook ?twitter ?youtube
                ?fips ?gnis
                ?image ?banner ?locatorMap
                ?coord
            WHERE {{
              {union_block}
              OPTIONAL {{ ?item wdt:P856 ?website . }}
              OPTIONAL {{ ?item wdt:P1082 ?population . }}
              OPTIONAL {{ ?item wdt:P2046 ?area . }}
              OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
              OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
              OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
              OPTIONAL {{ ?item wdt:P18 ?image . }}
              OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
              OPTIONAL {{ ?item wdt:P948 ?banner . }}
              OPTIONAL {{ ?item wdt:P625 ?coord . }}
              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
            }}
            LIMIT {limit_rows}
            """
                try:
                    chunk_rows.extend(await self.wikidata.execute_sparql(query) or [])
                except Exception as e:
                    logger.warning(f"City batch query failed ({chi}/{n_chunks}): {type(e).__name__}: {e}")
            aggregated.extend(chunk_rows)

            if chunk_sleep > 0 and ix + chunk_size < len(pairs):
                await asyncio.sleep(chunk_sleep)

        results = self._dedupe_sparql_bindings_by_item(aggregated)
        jurisdictions = self._parse_jurisdiction_results(results, state_code, state_name, "city")
        self._repair_city_geoids_from_ansi_map(jurisdictions, ansi_to_geoid)
        logger.info(f"  Found {len(jurisdictions)} cities")
        return jurisdictions

    async def _query_cities_in_state_wide(
        self, state_code: str, state_q_code: str, state_name: str
    ) -> List[Dict]:
        """Legacy: transitive P131+ on the state — can time out under WDQS load."""
        query = f"""
        SELECT DISTINCT
            ?item ?itemLabel
            ?website ?population ?area
            ?facebook ?twitter ?youtube
            ?fips ?gnis
            ?image ?banner ?locatorMap
            ?coord
        WHERE {{
          ?item wdt:P131+ wd:{state_q_code} .

          OPTIONAL {{ ?item wdt:P856 ?website . }}
          OPTIONAL {{ ?item wdt:P1082 ?population . }}
          OPTIONAL {{ ?item wdt:P2046 ?area . }}
          OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
          OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
          OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
          ?item wdt:P774 ?fips .
          OPTIONAL {{ ?item wdt:P590 ?gnis . }}
          OPTIONAL {{ ?item wdt:P18 ?image . }}
          OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
          OPTIONAL {{ ?item wdt:P948 ?banner . }}
          OPTIONAL {{ ?item wdt:P625 ?coord . }}

          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
        }}
        LIMIT 2000
        """

        logger.info(f"Querying municipalities in {state_name} (legacy P131+ Wikidata crawl)…")
        try:
            raw = await self.wikidata.execute_sparql(query)
        except Exception as e:
            logger.warning(f"City query failed: {type(e).__name__}: {e}")
            raw = []

        jurisdictions = self._parse_jurisdiction_results(raw, state_code, state_name, "city")
        logger.info(f"  Found {len(jurisdictions)} cities")
        return jurisdictions

    def _fetch_bronze_county_geoids(self, state_code: str) -> List[str]:
        """County GEOIDs in bronze for this USPS (digits only in practice)."""
        if self._json_cache_dir:
            assert self._json_bronze is not None
            rows = self._json_bronze.get("counties", {}).get(state_code.upper(), [])
            seen: Set[str] = set()
            out: List[str] = []
            for r in rows:
                g = str(r.get("geoid") or "").strip().replace("-", "")
                if g and g not in seen:
                    seen.add(g)
                    out.append(g)
            return out
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                SELECT geoid
                FROM bronze.bronze_jurisdictions_counties
                WHERE usps = %s
                ORDER BY geoid
                """,
                (state_code.upper(),),
            )
            out = [str(r[0]).strip().replace("-", "") for r in cur.fetchall() if r and r[0]]
            return list(dict.fromkeys(out))
        finally:
            cur.close()

    def _fetch_bronze_county_geoid_name_pairs(self, state_code: str) -> List[Tuple[str, str]]:
        """County GEOIDs with Census gazetteer display names (for entity-search mapping)."""
        if self._json_cache_dir:
            assert self._json_bronze is not None
            rows = self._json_bronze.get("counties", {}).get(state_code.upper(), [])
            seen_g: Set[str] = set()
            out_pairs: List[Tuple[str, str]] = []
            for r in rows:
                g = str(r.get("geoid") or "").strip().replace("-", "")
                if not g or g in seen_g:
                    continue
                seen_g.add(g)
                out_pairs.append((g, str(r.get("name") or "").strip()))
            return out_pairs
        cur = self.conn.cursor()
        try:
            cur.execute(
                """
                SELECT geoid, COALESCE(name, '')
                FROM bronze.bronze_jurisdictions_counties
                WHERE usps = %s
                ORDER BY geoid
                """,
                (state_code.upper(),),
            )
            seen: Set[str] = set()
            out: List[Tuple[str, str]] = []
            for r in cur.fetchall():
                if not r or not r[0]:
                    continue
                g = str(r[0]).strip().replace("-", "")
                if g in seen:
                    continue
                seen.add(g)
                out.append((g, str(r[1] or "").strip()))
            return out
        finally:
            cur.close()

    async def _county_resolve_via_entity_search(
        self,
        display_name: str,
        state_name: str,
        state_q_code: str,
        lits: Set[str],
    ) -> Optional[Tuple[str, Dict[str, Any]]]:
        """
        Resolve county GEOID via wbsearchentities + wbgetentities, matching P882 / P3006 / P590 to ``lits``.
        ``state_q_code`` reserved for future P131 tightening.
        """
        _ = state_q_code
        from scripts.datasources.wikidata import wikidata_entity_search as wes

        if not (display_name or "").strip():
            return None

        phrases = wes.county_search_strings(display_name, state_name)
        if not phrases:
            return None

        t0 = time.monotonic()
        seen_ids: Set[str] = set()
        ordered_ids: List[str] = []
        search_calls = 0
        for pi, phrase in enumerate(phrases, start=1):
            logger.info(f"    phrase {pi}/{len(phrases)} wbsearchentities: {phrase[:80]!r}…")
            t_ph = time.monotonic()
            try:
                hits = await self.wikidata.wikibase_search_entities(phrase, limit=14)
                search_calls += 1
            except Exception as exc:
                logger.warning(
                    f"wbsearchentities failed for {phrase[:60]!r}: {type(exc).__name__}: {exc}"
                )
                hits = []
            dt = time.monotonic() - t_ph
            logger.info(
                f"    → {len(hits)} search hit(s) in {dt:.1f}s "
                f"(each w/api.php call waits WIKIDATA_THROTTLE_SECONDS after the previous one)"
            )
            for h in hits:
                qid = h.get("id")
                if isinstance(qid, str) and qid.startswith("Q") and qid not in seen_ids:
                    seen_ids.add(qid)
                    ordered_ids.append(qid)
            if len(ordered_ids) >= 24:
                break

        if not ordered_ids:
            logger.info(
                f"    county entity-search gave up after {time.monotonic() - t0:.1f}s "
                f"({search_calls} wbsearchentities, 0 candidates)"
            )
            return None

        logger.info(f"    wbgetentities reconcile: {len(ordered_ids[:28])} candidate Q-id(s)…")
        t_get = time.monotonic()
        try:
            ents = await self.wikidata.wikibase_get_entities(
                ordered_ids[:28], wikibase_props="labels|claims"
            )
        except Exception as exc:
            logger.warning(f"wbgetentities (county search reconcile) failed: {type(exc).__name__}: {exc}")
            return None
        get_dt = time.monotonic() - t_get
        logger.info(f"    wbgetentities reconcile done in {get_dt:.1f}s")

        for qid in ordered_ids:
            ent = ents.get(qid)
            if not ent:
                continue
            ok, _seen = wes.entity_claim_identifier_literals(ent, lits)
            if ok:
                total = time.monotonic() - t0
                logger.info(
                    f"    county resolve total {total:.1f}s — "
                    f"{search_calls}× wbsearchentities + 1× wbgetentities (not one FIPS query; "
                    f"Wikidata has no bulk FIPS API, so we search labels then match claims)"
                )
                return (qid, ent)
        logger.info(
            f"    no identifier match after {time.monotonic() - t0:.1f}s "
            f"({search_calls} search + reconcile get)"
        )
        return None

    @staticmethod
    def _county_mapping_row_matches_geoid_literals(mr: Dict, lits: Set[str]) -> bool:
        """True if SPARQL binding ?fips/?fipsAlt/?gnis overlaps GEOID literal alternates."""
        from scripts.datasources.wikidata.geography_qid_cache import norm_lit

        got: Set[str] = set()
        for k in ("fips", "fipsAlt", "gnis"):
            v = mr.get(k)
            if v is None or str(v).strip() == "":
                continue
            s = str(v).strip().replace("-", "")
            got.add(norm_lit(s))
            if s.isdigit():
                got.add(norm_lit(s.lstrip("0") or "0"))
        targets = {norm_lit(x) for x in lits if str(x).strip()}
        return bool(got & targets)

    @staticmethod
    def _municipality_mapping_row_matches_literals(
        mr: Dict, fips_lits: Set[str], gnis_lits: Set[str]
    ) -> bool:
        """True if SPARQL binding ?fips/?gnis overlaps municipality literal sets."""
        from scripts.datasources.wikidata.geography_qid_cache import norm_lit

        got: Set[str] = set()
        for k in ("fips", "gnis"):
            v = mr.get(k)
            if v is None or str(v).strip() == "":
                continue
            s = str(v).strip().replace("-", "")
            got.add(norm_lit(s))
            if s.isdigit():
                got.add(norm_lit(s.lstrip("0") or "0"))
        targets = {norm_lit(x) for x in (fips_lits | gnis_lits) if str(x).strip()}
        for x in list(targets):
            xs = str(x).replace("-", "")
            if xs.isdigit():
                targets.add(norm_lit(xs.lstrip("0") or "0"))
        return bool(got & targets)

    @staticmethod
    def _school_mapping_row_matches_literals(mr: Dict, lits: Set[str]) -> bool:
        """True if binding ?nces/?fips/?gnis overlaps school GEOID/NCES literal alternates."""
        from scripts.datasources.wikidata.geography_qid_cache import norm_lit

        got: Set[str] = set()
        for k in ("nces", "fips", "gnis"):
            v = mr.get(k)
            if v is None or str(v).strip() == "":
                continue
            s = str(v).strip().replace("-", "")
            got.add(norm_lit(s))
            if s.isdigit():
                got.add(norm_lit(s.lstrip("0") or "0"))
                if k == "nces" or len(s) >= 5:
                    got.add(norm_lit(s.zfill(7)))
        targets = {norm_lit(x) for x in lits if str(x).strip()}
        for x in list(targets):
            xs = str(x).replace("-", "")
            if xs.isdigit():
                targets.add(norm_lit(xs.lstrip("0") or "0"))
                targets.add(norm_lit(xs.zfill(7)))
        return bool(got & targets)

    @staticmethod
    def _dedupe_sparql_bindings_by_item(results: List[Dict]) -> List[Dict]:
        by_id: Dict[str, Dict] = {}
        for row in results:
            iurl = row.get("item") or ""
            iid = iurl.rsplit("/", 1)[-1]
            if not iid:
                continue
            if iid not in by_id:
                by_id[iid] = row
        return list(by_id.values())

    async def _wdqs_municipality_mapping_chunked(
        self,
        need_fips: Set[str],
        need_gnis: Set[str],
        lim: int,
        chunk_i: int,
        chunk_n: int,
    ) -> List[Dict]:
        """Thin P774/P590 mapping — small FILTER IN lists to reduce WDQS timeouts."""
        cz = _wikidata_filter_in_literal_chunk_size()
        gap = _wikidata_filter_in_subquery_gap_seconds()
        f_batches = _batched_sorted_literals(need_fips, cz)
        g_batches = _batched_sorted_literals(need_gnis, cz)
        seq: List[Tuple[str, List[str]]] = [("FIPS", b) for b in f_batches] + [("GNIS", b) for b in g_batches]
        if len(seq) > 1:
            logger.info(
                f"  chunk {chunk_i}/{chunk_n}: FILTER IN → {len(seq)} WDQS sub-queries "
                f"(≤{cz} literals each; inter-batch gap={gap:.1f}s)"
            )
        out: List[Dict] = []
        for i, (kind, batch) in enumerate(seq):
            if gap > 0 and i > 0:
                await asyncio.sleep(gap)
            if kind == "FIPS":
                part = ", ".join(_sparql_quote_string_literal(x) for x in batch)
                q = _wikidata_hybrid_sql.municipality_mapping_sparql(part, "", lim)
            else:
                part = ", ".join(_sparql_quote_string_literal(x) for x in batch)
                q = _wikidata_hybrid_sql.municipality_mapping_sparql("", part, lim)
            rows = await self.wikidata.execute_sparql(q)
            out.extend(rows or [])
        return out

    async def _query_counties_in_state(
        self, state_code: str, state_q_code: str, state_name: str
    ) -> List[Dict]:
        """Counties: WDQS is sensitive to transitive P131 + DISTINCT + many OPTIONALS."""

        _legacy_env = (os.getenv("WIKIDATA_COUNTY_LEGACY_STATE_QUERY") or "").strip()
        if _legacy_env:
            legacy_wide = _env_truthy("WIKIDATA_COUNTY_LEGACY_STATE_QUERY", default=False)
        else:
            legacy_wide = not _env_truthy("WIKIDATA_COUNTY_FIPS_BATCH", default=True)
        county_type_values = _county_type_values_clause(state_code)
        sf = STATE_MAP.get(state_code, {}).get("fips")

        if legacy_wide:
            return await self._query_counties_in_state_wide(
                county_type_values, state_q_code, state_name, state_code
            )

        geoids = self._fetch_bronze_county_geoids(state_code)
        if not geoids:
            logger.warning(
                f"No bronze county GEOIDs for {state_code}; falling back to P131+ state-wide query."
            )
            return await self._query_counties_in_state_wide(
                county_type_values, state_q_code, state_name, state_code
            )

        if _wikidata_incremental_merge():
            miss = self._fetch_geoids_missing_wikidata_qid(
                state_code, "bronze.bronze_jurisdictions_counties_wikidata"
            )
            geoids = [g for g in geoids if g in miss]
            if not geoids:
                logger.info(
                    f"Incremental merge: no counties with NULL wikidata_id for {state_name} — skipping WDQS"
                )
                return []

        if _wikidata_hybrid_enrich_enabled():
            return await self._query_counties_in_state_via_hybrid(
                state_code, state_q_code, state_name
            )

        try:
            raw_chunk = os.getenv("WIKIDATA_COUNTY_CHUNK_SIZE", "35") or "35"
            chunk_size = max(5, min(120, int(str(raw_chunk).strip())))
        except ValueError:
            chunk_size = 35

        try:
            chunk_sleep = float(os.getenv("WIKIDATA_COUNTY_CHUNK_SLEEP_SECONDS", "1") or "1")
        except ValueError:
            chunk_sleep = 1.0
        chunk_sleep = max(0.0, chunk_sleep)

        logger.info(
            f"Querying WikiData counties in {state_name} via "
            f"FIPS-batched WDQS (~{chunk_size} GEOIDs/request, "
            "no transitive P131+ — avoids common WDQS timeouts)."
        )

        aggregated: List[Dict] = []
        n_chunks = (len(geoids) + chunk_size - 1) // chunk_size
        for ix in range(0, len(geoids), chunk_size):
            chunk = geoids[ix : ix + chunk_size]
            literals: Set[str] = set()
            for gid in chunk:
                literals.update(_county_fips_literal_alternatives(gid, sf))

            limit_rows = max(550, chunk_size * 25)
            limit_rows = min(limit_rows, 2500)

            cz = _wikidata_filter_in_literal_chunk_size()
            gap_sub = _wikidata_filter_in_subquery_gap_seconds()
            batches = _batched_sorted_literals(literals, cz)

            chi = ix // chunk_size + 1
            logger.info(f"  County WDQS chunk {chi}/{n_chunks} ({len(chunk)} GEOIDs, ~{len(literals)} literals)…")
            if len(batches) > 1:
                logger.info(
                    f"    → {len(batches)} FILTER IN sub-queries (≤{cz} literals; gap={gap_sub:.1f}s)"
                )

            chunk_rows: List[Dict] = []
            for bi, batch in enumerate(batches):
                if gap_sub > 0 and bi > 0:
                    await asyncio.sleep(gap_sub)
                in_list = ", ".join(_sparql_quote_string_literal(x) for x in batch)
                query = f"""
            SELECT DISTINCT
                ?item ?itemLabel ?website ?population ?area
                ?facebook ?twitter ?youtube ?fips ?fipsAlt ?gnis ?nces ?image ?banner ?locatorMap
                ?coord
                ?geonamesId
            WHERE {{
              {{
                VALUES ?countyType {{ {county_type_values} }}
                ?item wdt:P31 ?countyType .
                ?item wdt:P882 ?fips .
                FILTER(?fips IN ({in_list}))
              }}
              UNION
              {{
                VALUES ?countyType {{ {county_type_values} }}
                ?item wdt:P31 ?countyType .
                ?item wdt:P3006 ?fipsAlt .
                FILTER(?fipsAlt IN ({in_list}))
              }}

              OPTIONAL {{ ?item wdt:P856 ?website . }}
              OPTIONAL {{ ?item wdt:P1082 ?population . }}
              OPTIONAL {{ ?item wdt:P2046 ?area . }}
              OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
              OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
              OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
              OPTIONAL {{ ?item wdt:P590 ?gnis . }}
              OPTIONAL {{ ?item wdt:P6545 ?nces . }}
              OPTIONAL {{ ?item wdt:P18 ?image . }}
              OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
              OPTIONAL {{ ?item wdt:P948 ?banner . }}
              OPTIONAL {{ ?item wdt:P1566 ?geonamesId . }}
              OPTIONAL {{ ?item wdt:P625 ?coord . }}

              SERVICE wikibase:label {{
                bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en".
              }}
            }}
            LIMIT {limit_rows}
            """
                try:
                    chunk_rows.extend(await self.wikidata.execute_sparql(query) or [])
                except Exception as e:
                    logger.warning(f"County batch query failed ({chi}/{n_chunks}): {type(e).__name__}: {e}")
            aggregated.extend(chunk_rows)

            if chunk_sleep > 0 and ix + chunk_size < len(geoids):
                await asyncio.sleep(chunk_sleep)

        results = self._dedupe_sparql_bindings_by_item(aggregated)
        jurisdictions = self._parse_jurisdiction_results(results, state_code, state_name, "county")
        logger.info(f"  Found {len(jurisdictions)} counties")
        return jurisdictions

    async def _query_counties_in_state_wide(
        self,
        county_type_values: str,
        state_q_code: str,
        state_name: str,
        state_code: str,
    ) -> List[Dict]:
        """
        Original state-wide pattern: P131+ on the state item. Can time out on WDQS
        under load; prefer FIPS batches (default).
        """
        query = f"""
        SELECT DISTINCT
            ?item ?itemLabel ?website ?population ?area
            ?facebook ?twitter ?youtube ?fips ?fipsAlt ?gnis ?nces ?image ?banner ?locatorMap
            ?coord
            ?geonamesId
        WHERE {{
          VALUES ?countyType {{ {county_type_values} }}
          ?item wdt:P31 ?countyType .
          ?item wdt:P131+ wd:{state_q_code} .

          {{
            ?item wdt:P882 ?fips .
          }}
          UNION
          {{
            ?item wdt:P3006 ?fipsAlt .
          }}

          OPTIONAL {{ ?item wdt:P856 ?website . }}
          OPTIONAL {{ ?item wdt:P1082 ?population . }}
          OPTIONAL {{ ?item wdt:P2046 ?area . }}
          OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
          OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
          OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
          OPTIONAL {{ ?item wdt:P590 ?gnis . }}
          OPTIONAL {{ ?item wdt:P6545 ?nces . }}
          OPTIONAL {{ ?item wdt:P18 ?image . }}
          OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
          OPTIONAL {{ ?item wdt:P948 ?banner . }}
          OPTIONAL {{ ?item wdt:P1566 ?geonamesId . }}
          OPTIONAL {{ ?item wdt:P625 ?coord . }}

          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
        }}
        LIMIT 500
        """

        logger.info(f"Querying WikiData for counties in {state_name} (legacy P131+ query)…")
        try:
            results = await self.wikidata.execute_sparql(query)
        except Exception as e:
            logger.warning(f"County query failed: {type(e).__name__}: {e}")
            results = []

        jurisdictions = self._parse_jurisdiction_results(results, state_code, state_name, "county")
        logger.info(f"  Found {len(jurisdictions)} counties")
        return jurisdictions
    
    async def _query_schools_in_state(self, state_code: str, state_q_code: str, state_name: str) -> List[Dict]:
        """
        Schools: batch by bronze NCES/GEOID (+P6545 / P882) by default — avoids P131+ and avoids
        the expensive correlated OPTIONAL sub-select for superintendent (bulk loads rarely need it).
        """

        _legacy_s = (os.getenv("WIKIDATA_SCHOOL_LEGACY_STATE_QUERY") or "").strip()
        if _legacy_s:
            legacy_wide = _env_truthy("WIKIDATA_SCHOOL_LEGACY_STATE_QUERY", default=False)
        else:
            legacy_wide = not _env_truthy("WIKIDATA_SCHOOL_IDENTIFIER_BATCH", default=True)

        if legacy_wide:
            return await self._query_schools_in_state_wide(state_code, state_q_code, state_name)

        geoids = self._fetch_bronze_school_geoids(state_code)
        if not geoids:
            logger.warning(
                f"No bronze school-district GEOIDs for {state_code}; falling back to legacy P131+ query."
            )
            return await self._query_schools_in_state_wide(state_code, state_q_code, state_name)

        if _wikidata_incremental_merge():
            miss = self._fetch_geoids_missing_wikidata_qid(
                state_code, "bronze.bronze_jurisdictions_school_districts_wikidata"
            )
            geoids = [g for g in geoids if g in miss]
            if not geoids:
                logger.info(
                    f"Incremental merge: no school districts with NULL wikidata_id for {state_name} — skipping WDQS"
                )
                return []

        if _wikidata_hybrid_enrich_enabled():
            return await self._query_schools_in_state_via_hybrid(
                state_code, state_q_code, state_name
            )

        chunk_size = _positive_int_env("WIKIDATA_SCHOOL_CHUNK_SIZE", 35, 5, 200)
        chunk_sleep = _chunk_sleep_seconds(1.0)
        aggregated: List[Dict] = []
        n_chunks = (len(geoids) + chunk_size - 1) // chunk_size

        for ix in range(0, len(geoids), chunk_size):
            chunk = geoids[ix : ix + chunk_size]
            literals: Set[str] = set()
            for gid in chunk:
                literals |= _school_id_literal_alternatives(gid)

            if not literals:
                continue

            limit_rows = min(2500, max(520, chunk_size * 28))
            chi = ix // chunk_size + 1
            logger.info(f"Querying school districts in {state_name} via NCES/FIPS batch ({chi}/{n_chunks})…")

            cz = _wikidata_filter_in_literal_chunk_size()
            gap_sub = _wikidata_filter_in_subquery_gap_seconds()
            batches = _batched_sorted_literals(literals, cz)
            if len(batches) > 1:
                logger.info(
                    f"  chunk {chi}/{n_chunks}: FILTER IN → {len(batches)} WDQS sub-queries "
                    f"(≤{cz} literals; gap={gap_sub:.1f}s)"
                )

            chunk_rows: List[Dict] = []
            for bi, batch in enumerate(batches):
                if gap_sub > 0 and bi > 0:
                    await asyncio.sleep(gap_sub)
                id_in = ", ".join(_sparql_quote_string_literal(x) for x in batch)
                query = f"""
            SELECT DISTINCT
                ?item ?itemLabel ?website ?population ?area
                ?facebook ?twitter ?youtube ?fips ?gnis ?nces ?image ?banner ?locatorMap
                ?dialingCode ?googleMapsCustomerId ?households ?medianAge
                ?coord
                ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
                ?ballotpediaId ?tripadvisorId ?subreddit
                ?geonamesId
            WHERE {{
              {{
                ?item wdt:P31 wd:Q1455778 .
                ?item wdt:P6545 ?nces .
                FILTER(?nces IN ({id_in}))
              }}
              UNION
              {{
                ?item wdt:P31 wd:Q1455778 .
                ?item wdt:P882 ?fips .
                FILTER(?fips IN ({id_in}))
              }}

              OPTIONAL {{ ?item wdt:P856 ?website . }}
              OPTIONAL {{ ?item wdt:P1082 ?population . }}
              OPTIONAL {{ ?item wdt:P2046 ?area . }}
              OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
              OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
              OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
              OPTIONAL {{ ?item wdt:P590 ?gnis . }}
              OPTIONAL {{ ?item wdt:P18 ?image . }}
              OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
              OPTIONAL {{ ?item wdt:P948 ?banner . }}
              OPTIONAL {{ ?item wdt:P1566 ?geonamesId . }}
              OPTIONAL {{ ?item wdt:P625 ?coord . }}
              OPTIONAL {{ ?item wdt:P473 ?dialingCode . }}
              OPTIONAL {{ ?item wdt:P3749 ?googleMapsCustomerId . }}
              OPTIONAL {{ ?item wdt:P1538 ?households . }}
              OPTIONAL {{ ?item wdt:P1310 ?medianAge . }}
              OPTIONAL {{ ?item wdt:P281 ?postalCode . }}
              OPTIONAL {{ ?item wdt:P3529 ?perCapitaIncome . }}
              OPTIONAL {{ ?item wdt:P421 ?timeZone . }}
              OPTIONAL {{ ?item wdt:P2390 ?ballotpediaId . }}
              OPTIONAL {{ ?item wdt:P3134 ?tripadvisorId . }}
              OPTIONAL {{ ?item wdt:P3984 ?subreddit . }}

              SERVICE wikibase:label {{
                bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en".
              }}
            }}
            LIMIT {limit_rows}
            """
                try:
                    chunk_rows.extend(await self.wikidata.execute_sparql(query) or [])
                except Exception as e:
                    logger.warning(
                        f"School district batch query failed ({chi}/{n_chunks}): {type(e).__name__}: {e}"
                    )
            aggregated.extend(chunk_rows)

            if chunk_sleep > 0 and ix + chunk_size < len(geoids):
                await asyncio.sleep(chunk_sleep)

        results = self._dedupe_sparql_bindings_by_item(aggregated)
        jurisdictions = self._parse_jurisdiction_results(results, state_code, state_name, "school_district")
        logger.info(f"  Found {len(jurisdictions)} school districts")
        return jurisdictions

    async def _query_schools_in_state_wide(self, state_code: str, state_q_code: str, state_name: str) -> List[Dict]:
        """Heavy legacy query: transitive P131+ plus superintendent sub-select."""

        query = f"""
        SELECT DISTINCT
            ?item ?itemLabel ?website ?population ?area
            ?facebook ?twitter ?youtube ?fips ?gnis ?nces ?image ?banner ?locatorMap
            ?dialingCode ?googleMapsCustomerId ?households ?medianAge ?languageLabel
            ?coord
            ?headOfGov ?headOfGovLabel
            ?headStart ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
            ?ballotpediaId ?tripadvisorId ?subreddit
            ?geonamesId
        WHERE {{
          ?item wdt:P31 wd:Q1455778 .
          ?item wdt:P131+ wd:{state_q_code} .

          OPTIONAL {{ ?item wdt:P856 ?website . }}
          OPTIONAL {{ ?item wdt:P1082 ?population . }}
          OPTIONAL {{ ?item wdt:P2046 ?area . }}
          OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
          OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
          OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
          OPTIONAL {{ ?item wdt:P882 ?fips . }}
          OPTIONAL {{ ?item wdt:P590 ?gnis . }}
          OPTIONAL {{ ?item wdt:P6545 ?nces . }}
          OPTIONAL {{ ?item wdt:P18 ?image . }}
          OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
          OPTIONAL {{ ?item wdt:P948 ?banner . }}
          OPTIONAL {{ ?item wdt:P1566 ?geonamesId . }}
          OPTIONAL {{ ?item wdt:P625 ?coord . }}
          OPTIONAL {{ ?item wdt:P473 ?dialingCode . }}
          OPTIONAL {{ ?item wdt:P3749 ?googleMapsCustomerId . }}
          OPTIONAL {{ ?item wdt:P1538 ?households . }}
          OPTIONAL {{ ?item wdt:P1310 ?medianAge . }}
          OPTIONAL {{ ?item wdt:P407 ?language . }}

          OPTIONAL {{
            {{
              SELECT ?headOfGov ?headStart WHERE {{
                ?item p:P6 ?headStmt .
                ?headStmt ps:P6 ?headOfGov .
                OPTIONAL {{ ?headStmt pq:P580 ?headStart . }}
                FILTER(BOUND(?headStart))
              }}
              ORDER BY DESC(?headStart)
              LIMIT 1
            }}
            OPTIONAL {{ ?headOfGov wdt:P39 ?position . }}
          }}

          OPTIONAL {{ ?item wdt:P281 ?postalCode . }}
          OPTIONAL {{ ?item wdt:P3529 ?perCapitaIncome . }}
          OPTIONAL {{ ?item wdt:P421 ?timeZone . }}
          OPTIONAL {{ ?item wdt:P2390 ?ballotpediaId . }}
          OPTIONAL {{ ?item wdt:P3134 ?tripadvisorId . }}
          OPTIONAL {{ ?item wdt:P3984 ?subreddit . }}

          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
        }}
        LIMIT 500
        """

        logger.info(f"Querying school districts in {state_name} (legacy P131+ / superintendent query)…")
        try:
            results = await self.wikidata.execute_sparql(query)
        except Exception as e:
            logger.warning(f"School district query failed: {type(e).__name__}: {e}")
            results = []

        jurisdictions = self._parse_jurisdiction_results(results, state_code, state_name, "school_district")
        logger.info(f"  Found {len(jurisdictions)} school districts")
        return jurisdictions

    def _parse_jurisdiction_results(self, results: List[Dict], state_code: str, state_name: str, jurisdiction_type: str) -> List[Dict]:
        """Parse SPARQL results into jurisdiction records."""
        def _safe_float(v: Optional[str]) -> Optional[float]:
            if v is None:
                return None
            try:
                return float(v)
            except Exception:
                return None

        jurisdictions = []
        for result in results:
            wikidata_id = result.get("item", "").split("/")[-1]
            youtube_channel_id = result.get("youtube")
            
            # Extract US government IDs (P882 preferred; P3006 is common fallback on WD)
            fips_code = result.get("fips") or result.get("fipsAlt")
            if isinstance(fips_code, str):
                fips_code = fips_code.replace("-", "")
            gnis_id = result.get("gnis")
            nces_id = result.get("nces")
            geonames_id = result.get("geonamesId")
            
            # Extract official image URL
            image_url = result.get("image")
            locator_map_url = result.get("locatorMap")
            banner_url = result.get("banner")
            
            # Build jurisdiction_id and jurisdiction_id_type to match our database format
            jurisdiction_id = None
            jurisdiction_id_type = None
            geoid = None
            
            if jurisdiction_type == 'county' and fips_code:
                # Census / bronze use 5-digit county GEOID (state FIPS + county FIPS).
                # Wikidata P882 is sometimes the full 5-digit code, sometimes county-only (e.g. "001").
                fc = str(fips_code).strip().replace("-", "")
                state_fips = STATE_MAP.get(state_code, {}).get("fips")
                geoid = None
                if fc.isdigit():
                    if len(fc) == 5:
                        geoid = fc
                    elif (
                        state_fips
                        and len(fc) == 4
                        and fc.startswith(state_fips)
                    ):
                        # e.g. 05001 as "5001" (leading state digit clipped in export)
                        geoid = f"{state_fips}{fc[len(state_fips) :].zfill(3)}"
                    elif state_fips and len(fc) <= 3:
                        geoid = f"{state_fips}{fc.zfill(3)}"
                    else:
                        geoid = fc
                else:
                    geoid = fc
                # Wikidata often exports a 4-digit value that is the full state+county FIPS missing one
                # leading zero vs Census 5-char GEOID (e.g. "5001" → "05001"). Bronze stores 5-digit text.
                if geoid:
                    g = str(geoid).strip().replace("-", "")
                    if g.isdigit() and len(g) == 4:
                        geoid = g.zfill(5)
                fips_code = geoid
                jurisdiction_id = f"county_{geoid}" if geoid else None
                jurisdiction_id_type = 'county_fips' if geoid else None
            elif jurisdiction_type == 'school_district' and nces_id:
                # Format: school_{NCES} (e.g., school_0100001)
                jurisdiction_id = f"school_{nces_id}"
                jurisdiction_id_type = 'nces_id'
                # GEOID for school districts is the NCES ID
                geoid = nces_id
            elif fips_code:
                # City/municipality with FIPS place code.
                # Wikidata P882 for places is often a 5-digit *place* FIPS; our bronze GEOID
                # is 7 digits (state_fips + place_fips). Normalize so updates can join.
                state_fips = STATE_MAP.get(state_code, {}).get("fips")
                if state_fips and len(fips_code) == 5:
                    geoid = f"{state_fips}{fips_code}"
                else:
                    geoid = fips_code
            
            if gnis_id and not jurisdiction_id:
                # Format: {GNIS_ID} (e.g., 173056)
                jurisdiction_id = gnis_id
                jurisdiction_id_type = 'gnis_id'
            
            # Extract head of government info
            head_of_gov = result.get("headOfGovLabel")
            head_of_gov_position = result.get("positionLabel")
            head_start = result.get("headStart")
            
            # Extract postal codes (can be multiple in WikiData)
            postal_code = result.get("postalCode")
            postal_codes = json.dumps([postal_code]) if postal_code else None
            
            # Extract additional metadata
            per_capita_income = int(result.get("perCapitaIncome")) if result.get("perCapitaIncome") else None
            time_zone = result.get("timeZoneLabel") or result.get("timeZone")
            ballotpedia_id = result.get("ballotpediaId")
            tripadvisor_id = result.get("tripadvisorId")
            subreddit = result.get("subreddit")
            dialing_code = result.get("dialingCode")
            google_maps_customer_id = result.get("googleMapsCustomerId")
            number_of_households = _safe_float(result.get("households"))
            median_age = _safe_float(result.get("medianAge"))
            language_of_work_or_name = result.get("languageLabel")

            lat_v = _safe_float(result.get("lat"))
            lon_v = _safe_float(result.get("lon"))
            if lat_v is None or lon_v is None:
                clat, clon = _lat_lon_from_wikidata_coord_binding(result.get("coord"))
                if lat_v is None:
                    lat_v = clat
                if lon_v is None:
                    lon_v = clon
            
            jurisdictions.append({
                'wikidata_id': wikidata_id,
                'jurisdiction_id': jurisdiction_id,
                'jurisdiction_id_type': jurisdiction_id_type,
                'jurisdiction_name': result.get("itemLabel", ""),
                'state_code': state_code,
                'state': state_name,
                'jurisdiction_type': jurisdiction_type,
                'official_website': result.get("website"),
                'official_image_url': image_url,
                'page_banner_image': banner_url,
                'youtube_channel_id': youtube_channel_id,
                'youtube_channel_url': f"https://www.youtube.com/channel/{youtube_channel_id}" if youtube_channel_id else None,
                'facebook_username': result.get("facebook"),
                'facebook_url': f"https://www.facebook.com/{result.get('facebook')}" if result.get('facebook') else None,
                'twitter_username': result.get("twitter"),
                'twitter_url': f"https://twitter.com/{result.get('twitter')}" if result.get('twitter') else None,
                'population': int(result.get("population")) if result.get("population") else None,
                'area_sq_km': float(result.get("area")) if result.get("area") else None,
                'number_of_households': number_of_households,
                'median_age': median_age,
                'latitude': lat_v,
                'longitude': lon_v,
                'fips_code': fips_code,
                'gnis_id': gnis_id,
                'nces_id': nces_id,
                'geonames_id': geonames_id,
                'geoid': geoid,
                'locator_map_image': locator_map_url,
                'head_of_government': head_of_gov,
                'head_of_government_position': head_of_gov_position,
                'head_of_government_start_time': head_start,
                'postal_codes': postal_codes,
                'per_capita_income': per_capita_income,
                'local_dialing_code': dialing_code,
                'google_maps_customer_id': google_maps_customer_id,
                'language_of_work_or_name': language_of_work_or_name,
                'time_zone': time_zone,
                'ballotpedia_id': ballotpedia_id,
                'tripadvisor_id': tripadvisor_id,
                'subreddit': subreddit,
            })
        
        return jurisdictions
    
    def _state_jurisdiction_rows_from_ws_result(
        self,
        state_code: str,
        state_info: dict,
        result: Dict,
        hog_row: Optional[Dict],
    ) -> List[Dict]:
        """Turn a WDQS-shaped ``result`` dict + optional governor row into bronze state payload(s)."""
        state_name = state_info["name"]
        state_q_code = state_info["q_code"]

        jurisdiction_label = result.get("itemLabel") or state_name
        jurisdiction_description = result.get("itemDescription")
        aliases_en = [a for a in result.get("altLabels", "").split("||") if a] if result.get("altLabels") else None
        native_label = result.get("nativeLabel")
        nicknames = [a for a in result.get("nicknames", "").split("||") if a] if result.get("nicknames") else None
        short_names = [a for a in result.get("shortNames", "").split("||") if a] if result.get("shortNames") else None
        demonyms = [a for a in result.get("demonyms", "").split("||") if a] if result.get("demonyms") else None
        official_languages = (
            [a for a in result.get("officialLanguages", "").split("||") if a] if result.get("officialLanguages") else None
        )
        motto = result.get("motto")
        anthems = [a for a in result.get("anthems", "").split("||") if a] if result.get("anthems") else None
        capitals = [a for a in result.get("capitals", "").split("||") if a] if result.get("capitals") else None
        iso_3166_2 = result.get("iso31662")
        pronunciation_audio = result.get("pronunciationAudio")
        geoshape = result.get("geoshape")

        inception_date = None
        inception_raw = result.get("inception")
        if inception_raw:
            try:
                inception_date = str(inception_raw).lstrip("+")[:10]
            except Exception:
                inception_date = None

        youtube_channel_id = result.get("youtube")
        image_url = result.get("image")
        locator_map_url = result.get("locatorMap")
        banner_url = result.get("banner")
        geonames_id = result.get("geonamesId")

        fips_code = state_info["fips"]
        jurisdiction_id = f"state_{fips_code}"
        jurisdiction_id_type = "state_fips"

        head_of_gov = None
        head_of_gov_position = result.get("hogOfficeLabel") or f"Governor of {state_name}"
        head_start = None
        if hog_row:
            head_of_gov = hog_row.get("headOfGovLabel")
            head_of_gov_position = f"Governor of {state_name}"
            head_start_raw = hog_row.get("headStart")
            if head_start_raw:
                try:
                    head_start = datetime.fromisoformat(str(head_start_raw)[:10])
                except Exception:
                    head_start = head_start_raw

        postal_code = result.get("postalCode")
        postal_codes = json.dumps([postal_code]) if postal_code else None

        per_capita_income = int(result.get("perCapitaIncome")) if result.get("perCapitaIncome") else None
        time_zone = result.get("timeZoneLabel") or result.get("timeZone")
        ballotpedia_id = result.get("ballotpediaId")
        tripadvisor_id = result.get("tripadvisorId")
        subreddit = result.get("subreddit")
        dialing_code = result.get("dialingCode")
        google_maps_customer_id = result.get("googleMapsCustomerId")
        try:
            number_of_households = float(result.get("households")) if result.get("households") else None
        except Exception:
            number_of_households = None
        try:
            median_age = float(result.get("medianAge")) if result.get("medianAge") else None
        except Exception:
            median_age = None
        language_of_work_or_name = result.get("languageLabel")

        lat_sv = None
        lon_sv = None
        try:
            if result.get("lat") not in (None, ""):
                lat_sv = float(result.get("lat"))
        except (TypeError, ValueError):
            lat_sv = None
        try:
            if result.get("lon") not in (None, ""):
                lon_sv = float(result.get("lon"))
        except (TypeError, ValueError):
            lon_sv = None
        if lat_sv is None or lon_sv is None:
            clat, clon = _lat_lon_from_wikidata_coord_binding(result.get("coord"))
            if lat_sv is None:
                lat_sv = clat
            if lon_sv is None:
                lon_sv = clon

        return [
            {
                "wikidata_id": state_q_code,
                "jurisdiction_id": jurisdiction_id,
                "jurisdiction_id_type": jurisdiction_id_type,
                "jurisdiction_name": state_name,
                "state_code": state_code,
                "state": state_name,
                "jurisdiction_type": "state",
                "jurisdiction_label": jurisdiction_label,
                "jurisdiction_description": jurisdiction_description,
                "jurisdiction_aliases": json.dumps(aliases_en) if aliases_en else None,
                "native_label": native_label,
                "nickname": json.dumps(nicknames) if nicknames else None,
                "short_name": json.dumps(short_names) if short_names else None,
                "demonym": json.dumps(demonyms) if demonyms else None,
                "official_language": json.dumps(official_languages) if official_languages else None,
                "motto": motto,
                "anthem": json.dumps(anthems) if anthems else None,
                "inception_date": inception_date,
                "capital": json.dumps(capitals) if capitals else None,
                "iso_3166_2": iso_3166_2,
                "pronunciation_audio": pronunciation_audio,
                "geoshape": geoshape,
                "official_website": result.get("website"),
                "official_image_url": image_url,
                "page_banner_image": banner_url,
                "youtube_channel_id": youtube_channel_id,
                "youtube_channel_url": f"https://www.youtube.com/channel/{youtube_channel_id}"
                if youtube_channel_id
                else None,
                "facebook_username": result.get("facebook"),
                "facebook_url": f"https://www.facebook.com/{result.get('facebook')}"
                if result.get("facebook")
                else None,
                "twitter_username": result.get("twitter"),
                "twitter_url": f"https://twitter.com/{result.get('twitter')}" if result.get("twitter") else None,
                "population": int(result.get("population")) if result.get("population") else None,
                "area_sq_km": float(result.get("area")) if result.get("area") else None,
                "latitude": lat_sv,
                "longitude": lon_sv,
                "fips_code": fips_code,
                "gnis_id": None,
                "nces_id": None,
                "geonames_id": geonames_id,
                "geoid": fips_code,
                "locator_map_image": locator_map_url,
                "head_of_government": head_of_gov,
                "head_of_government_position": head_of_gov_position,
                "head_of_government_start_time": head_start,
                "postal_codes": postal_codes,
                "per_capita_income": per_capita_income,
                "number_of_households": number_of_households,
                "median_age": median_age,
                "local_dialing_code": dialing_code,
                "google_maps_customer_id": google_maps_customer_id,
                "language_of_work_or_name": language_of_work_or_name,
                "time_zone": time_zone,
                "ballotpedia_id": ballotpedia_id,
                "tripadvisor_id": tripadvisor_id,
                "subreddit": subreddit,
            }
        ]

    async def query_state_info(self, state_code: str) -> List[Dict]:
        """US state row: default Wikibase API (same JSON as Special:EntityData); optional legacy WDQS."""
        state_info = STATE_MAP.get(state_code)
        if not state_info:
            return []

        state_name = state_info["name"]
        state_q_code = state_info["q_code"]

        if _wikidata_state_legacy_sparql():
            return await self._query_state_info_via_sparql(state_code, state_info)
        return await self._query_state_info_via_wikibase(state_code, state_info)

    async def _ensure_state_entities_bulk_prefetch(self) -> None:
        """Optional: one batched ``wbgetentities`` for every ``STATE_MAP`` q_code (full-US runs)."""
        if self._state_bulk_prefetch_attempted:
            return
        self._state_bulk_prefetch_attempted = True
        if not _wikidata_state_bulk_wbgetentities():
            return
        ids = sorted(
            {
                str(inf["q_code"]).strip()
                for inf in STATE_MAP.values()
                if inf.get("q_code") and str(inf["q_code"]).strip().startswith("Q")
            }
        )
        if not ids:
            return
        try:
            logger.info(
                f"Bulk US jurisdiction prefetch: wbgetentities for {len(ids)} "
                "state/territory Q-ids (WIKIDATA_STATE_BULK_WBGETENTITIES=1)…"
            )
            merged = await self.wikidata.wikibase_get_entities(
                ids, wikibase_props="labels|descriptions|aliases|claims"
            )
            for qid, ent in merged.items():
                if isinstance(ent, dict) and not ent.get("missing"):
                    self._state_entities_bulk[str(qid)] = ent
            logger.info(f"  Cached {len(self._state_entities_bulk)} state Wikidata entities in memory.")
        except Exception as e:
            logger.warning(f"State bulk wbgetentities prefetch failed ({type(e).__name__}): {e}")

    async def _query_state_info_via_wikibase(self, state_code: str, state_info: dict) -> List[Dict]:
        state_name = state_info["name"]
        state_q_code = state_info["q_code"]
        await self._ensure_state_entities_bulk_prefetch()

        entity: Optional[Dict[str, Any]] = self._state_entities_bulk.get(state_q_code)
        if entity is None:
            logger.info(f"Fetching state Wikidata entity via API ({state_name}, {state_q_code})…")
            ents = await self.wikidata.wikibase_get_entities(
                [state_q_code], wikibase_props="labels|descriptions|aliases|claims"
            )
            entity = ents.get(state_q_code)
        else:
            logger.info(f"Using bulk-prefetched Wikidata entity ({state_name}, {state_q_code})…")
        if not isinstance(entity, dict) or entity.get("missing"):
            logger.warning(f"No Wikibase entity for {state_name} ({state_q_code})")
            return []

        related = collect_state_related_qids(entity)
        related_labels: Dict[str, str] = {}
        if related:
            ref_ents = await self.wikidata.wikibase_get_entities(related, wikibase_props="labels")
            for qid, ent in ref_ents.items():
                if not str(qid).startswith("Q"):
                    continue
                lb = entity_en_label(ent)
                if lb:
                    related_labels[str(qid)] = lb

        shaped, hog_row = state_entity_to_sparql_shaped_row(entity, state_q_code, related_labels)
        return self._state_jurisdiction_rows_from_ws_result(state_code, state_info, shaped, hog_row)

    async def _query_state_info_via_sparql(self, state_code: str, state_info: dict) -> List[Dict]:
        state_name = state_info["name"]
        state_q_code = state_info["q_code"]

        query = f"""
        SELECT DISTINCT 
            ?item ?itemLabel ?itemDescription ?nativeLabel
            (GROUP_CONCAT(DISTINCT ?altLabel; separator="||") AS ?altLabels)
            (GROUP_CONCAT(DISTINCT STR(?nickname); separator="||") AS ?nicknames)
            (GROUP_CONCAT(DISTINCT STR(?shortName); separator="||") AS ?shortNames)
            (GROUP_CONCAT(DISTINCT STR(?demonym); separator="||") AS ?demonyms)
            (GROUP_CONCAT(DISTINCT ?officialLanguageLabel; separator="||") AS ?officialLanguages)
            ?motto
            (GROUP_CONCAT(DISTINCT ?anthemLabel; separator="||") AS ?anthems)
            (GROUP_CONCAT(DISTINCT ?capitalLabel; separator="||") AS ?capitals)
            ?inception ?iso31662 ?pronunciationAudio ?geoshape
            ?website ?population ?area
            ?facebook ?twitter ?youtube ?fips ?image ?banner ?locatorMap
            ?dialingCode ?googleMapsCustomerId ?households ?medianAge ?languageLabel
            ?coord
            ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
            ?ballotpediaId ?tripadvisorId ?subreddit
            ?geonamesId
        WHERE {{
          BIND(wd:{state_q_code} AS ?item)

          OPTIONAL {{
            ?item schema:description ?itemDescription .
            FILTER(LANG(?itemDescription) = "en")
          }}
          OPTIONAL {{
            ?item skos:altLabel ?altLabel .
            FILTER(LANG(?altLabel) = "en")
          }}
          OPTIONAL {{
            ?item wdt:P1705 ?nativeLabel .
            FILTER(LANG(?nativeLabel) = "en")
          }}
          OPTIONAL {{ ?item wdt:P1448 ?nickname . }}
          OPTIONAL {{ ?item wdt:P2561 ?nickname . }}
          OPTIONAL {{ ?item wdt:P1813 ?shortName . }}
          OPTIONAL {{ ?item wdt:P1549 ?demonym . }}
          OPTIONAL {{
            ?item wdt:P37 ?officialLanguage .
            OPTIONAL {{
              ?officialLanguage rdfs:label ?officialLanguageLabel .
              FILTER(LANG(?officialLanguageLabel) = "en")
            }}
          }}
          OPTIONAL {{ ?item wdt:P1906 ?hogOffice . }}
          OPTIONAL {{ ?item wdt:P1451 ?motto . }}
          OPTIONAL {{
            ?item wdt:P85 ?anthem .
            OPTIONAL {{
              ?anthem rdfs:label ?anthemLabel .
              FILTER(LANG(?anthemLabel) = "en")
            }}
          }}
          OPTIONAL {{
            ?item wdt:P36 ?capital .
            OPTIONAL {{
              ?capital rdfs:label ?capitalLabel .
              FILTER(LANG(?capitalLabel) = "en")
            }}
          }}
          OPTIONAL {{ ?item wdt:P571 ?inception . }}
          OPTIONAL {{ ?item wdt:P300 ?iso31662 . }}
          OPTIONAL {{ ?item wdt:P443 ?pronunciationAudio . }}
          OPTIONAL {{ ?item wdt:P3896 ?geoshape . }}

          OPTIONAL {{ ?item wdt:P856 ?website . }}
          OPTIONAL {{ ?item wdt:P1082 ?population . }}
          OPTIONAL {{ ?item wdt:P2046 ?area . }}
          OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
          OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
          OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
          OPTIONAL {{ ?item wdt:P882 ?fips . }}
          OPTIONAL {{ ?item wdt:P18 ?image . }}
          OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
          OPTIONAL {{ ?item wdt:P948 ?banner . }}
          OPTIONAL {{ ?item wdt:P1566 ?geonamesId . }}
          OPTIONAL {{ ?item wdt:P625 ?coord . }}
          OPTIONAL {{ ?item wdt:P473 ?dialingCode . }}
          OPTIONAL {{ ?item wdt:P3749 ?googleMapsCustomerId . }}
          OPTIONAL {{ ?item wdt:P1538 ?households . }}
          OPTIONAL {{ ?item wdt:P1310 ?medianAge . }}
          OPTIONAL {{ ?item wdt:P407 ?language . }}

          OPTIONAL {{ ?item wdt:P281 ?postalCode . }}
          OPTIONAL {{ ?item wdt:P3529 ?perCapitaIncome . }}
          OPTIONAL {{ ?item wdt:P421 ?timeZone . }}
          OPTIONAL {{ ?item wdt:P2390 ?ballotpediaId . }}
          OPTIONAL {{ ?item wdt:P3134 ?tripadvisorId . }}
          OPTIONAL {{ ?item wdt:P3984 ?subreddit . }}

          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
        }}
        GROUP BY
          ?item ?itemLabel ?itemDescription ?nativeLabel
          ?motto ?inception ?iso31662 ?pronunciationAudio ?geoshape
          ?website ?population ?area ?facebook ?twitter ?youtube ?fips ?image ?banner ?locatorMap
          ?dialingCode ?googleMapsCustomerId ?households ?medianAge ?languageLabel
          ?coord ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
          ?ballotpediaId ?tripadvisorId ?subreddit ?geonamesId ?hogOffice
        LIMIT 1
        """

        logger.info(f"Querying WikiData for state (legacy WDQS): {state_name}…")
        results = await self.wikidata.execute_sparql(query)
        if not results:
            logger.warning(f"No WikiData entry found for {state_name}")
            return []

        result = results[0]
        hog_row: Optional[Dict] = None
        hog_query = f"""
        SELECT ?headOfGovLabel ?headStart
        WHERE {{
          wd:{state_q_code} p:P6 ?stmt .
          ?stmt ps:P6 ?headOfGov .
          OPTIONAL {{ ?stmt pq:P580 ?headStart . }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        ORDER BY DESC(?headStart)
        LIMIT 1
        """
        try:
            hog_rows = await self.wikidata.execute_sparql(hog_query)
            if hog_rows:
                hog_row = hog_rows[0]
        except Exception:
            pass

        return self._state_jurisdiction_rows_from_ws_result(state_code, state_info, result, hog_row)
    
    def insert_jurisdictions(self, jurisdictions: List[Dict]):
        """Apply Wikidata enrichment into bronze *_wikidata tables (no public table)."""
        if not jurisdictions:
            return

        # All rows in this batch correspond to the same task (state/county/city/school_district)
        # by construction.
        jtype = jurisdictions[0].get("jurisdiction_type")
        if jtype == "county":
            task = "county"
        elif jtype == "school_district":
            task = "school_district"
        elif jtype == "state":
            task = "state"
        else:
            # city/town are stored as municipalities in bronze
            task = "city"

        self._apply_wikidata_updates(task, jurisdictions)
    
    async def load_state(self, state_code: str, types: List[str], checkpoint: Optional['CheckpointManager'] = None):
        """Load all jurisdiction types for a state."""
        state_info = STATE_MAP.get(state_code, {})
        state_name = state_info.get('name', state_code)
        state_q_code = state_info.get('q_code', '')

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"LOADING WIKIDATA FOR {state_name}")
        logger.info("=" * 80)

        all_jurisdictions: List[Dict] = []
        skipped_tasks = 0
        incremental_tasks_skipped_entirely = 0

        # Determine ordered sub-queries, merging city/town into one task
        query_tasks = []
        if 'state' in types:
            query_tasks.append('state')
        if 'city' in types or 'town' in types:
            query_tasks.append('city')
        if 'county' in types:
            query_tasks.append('county')
        if 'school_district' in types:
            query_tasks.append('school_district')

        for task in query_tasks:
            if checkpoint and checkpoint.is_done(state_code, task):
                logger.info(f"  Skipping {task} for {state_code} (already completed)")
                skipped_tasks += 1
                continue

            # Rebuild the bronze *_wikidata base rows for this state+type, then apply updates.
            # With WIKIDATA_INCREMENTAL_MERGE, seed merges new Census rows without deleting QIDs.
            self._seed_wikidata_table(state_code, task)

            if _wikidata_incremental_merge() and not self._any_missing_wikidata_id_for_task(
                state_code, task
            ):
                incremental_tasks_skipped_entirely += 1
                logger.success(
                    f"  Incremental merge: all {task} rows for {state_code} already have wikidata_id — skipping WDQS"
                )
                if checkpoint:
                    checkpoint.mark_done(state_code, task)
                task_sleep_s = float(os.getenv("WIKIDATA_TASK_SLEEP_SECONDS", "2") or "2")
                if task_sleep_s > 0:
                    await asyncio.sleep(task_sleep_s)
                continue

            if task == 'state':
                results = await self.query_state_info(state_code)
            elif task == 'city':
                self._municipality_chunk_db_flush_used = False
                results = await self._query_cities_in_state(state_code, state_q_code, state_name)
            elif task == 'county':
                results = await self._query_counties_in_state(state_code, state_q_code, state_name)
            elif task == 'school_district':
                results = await self._query_schools_in_state(state_code, state_q_code, state_name)
            else:
                continue

            all_jurisdictions.extend(results)
            if results:
                skip_dup_insert = task == "city" and self._municipality_chunk_db_flush_used
                if skip_dup_insert:
                    logger.info(
                        "  city task: bronze municipalities already updated per hybrid chunk — "
                        "skipping duplicate end-of-task batch UPDATE"
                    )
                else:
                    self.insert_jurisdictions(results)
            if checkpoint:
                # Do not checkpoint empty WDQS *or* rows that never produced a joinable geoid/nces:
                # otherwise resume skips while wikidata_id stays NULL.
                if not results:
                    cache_dir = Path(os.getenv("WIKIDATA_CACHE_DIR", "data/cache/wikidata")).resolve()
                    logger.warning(
                        f"  No Wikidata rows for {state_code} task={task}; not checkpointing — resume will retry. "
                        f"If WDQS usually returns data here, delete `{cache_dir}` (empty responses were previously cached)."
                    )
                elif not _wikidata_task_has_join_keys(task, results):
                    logger.warning(
                        f"  Wikidata returned {len(results)} row(s) for {state_code} task={task} but none "
                        f"had a usable join key (GEOID/FIPS/etc.); not checkpointing — resume will retry"
                    )
                else:
                    checkpoint.mark_done(state_code, task)
            # Avoid tripping WDQS overload protections; distinct from per-request throttling
            # because some tasks run large SPARQL queries back-to-back.
            task_sleep_s = float(os.getenv("WIKIDATA_TASK_SLEEP_SECONDS", "2") or "2")
            if task_sleep_s > 0:
                await asyncio.sleep(task_sleep_s)

        with_youtube = sum(1 for j in all_jurisdictions if j.get('youtube_channel_id'))
        with_website = sum(1 for j in all_jurisdictions if j.get('official_website'))

        logger.info("")
        if query_tasks and skipped_tasks == len(query_tasks) and not all_jurisdictions:
            logger.success(
                f"✓ Processed 0 rows for {state_code} this run — all {len(query_tasks)} task(s) "
                f"skipped (checkpoint). Existing bronze *_wikidata rows are unchanged."
            )
        elif (
            incremental_tasks_skipped_entirely == len(query_tasks)
            and incremental_tasks_skipped_entirely > 0
            and not all_jurisdictions
        ):
            logger.success(
                f"✓ Applied 0 new Wikidata updates for {state_code} — incremental merge: "
                f"every {state_code} row for the requested task(s) already had wikidata_id, "
                "so WDQS/API was not needed. Bronze *_wikidata is already filled for those rows."
            )
        else:
            logger.success(
                f"✓ Processed {len(all_jurisdictions)} jurisdiction row(s) for {state_code} this run "
                f"(from Wikidata fetches merged into Postgres this pass; does not subtract prior runs)"
            )
        logger.info(f"  With YouTube channels: {with_youtube}")
        logger.info(f"  With official websites: {with_website}")
    
    def close(self):
        """Close database connection and flush any pending JSON results."""
        self._json_save_results()
        if self.conn:
            self.conn.close()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Load jurisdictions from WikiData')
    
    parser.add_argument(
        '--states',
        type=str,
        default=(
            os.getenv("WIKIDATA_LOAD_STATES", "").strip() or ",".join(PRIORITY_STATES)
        ),
        help=(
            'Comma-separated list of state codes (default: '
            f'env WIKIDATA_LOAD_STATES or {",".join(PRIORITY_STATES)})'
        ),
    )

    parser.add_argument(
        '--priority-states',
        action=BooleanOptionalAction,
        default=_env_truthy("WIKIDATA_LOAD_PRIORITY_STATES"),
        help=(
            'Load priority development states '
            f'({", ".join(PRIORITY_STATES)}); '
            'default from WIKIDATA_LOAD_PRIORITY_STATES (1/true/yes/on)'
        ),
    )

    parser.add_argument(
        '--all-us-states',
        action=BooleanOptionalAction,
        default=_env_truthy("WIKIDATA_LOAD_ALL_US_STATES"),
        help=(
            'Load every USPS code in STATE_MAP (50 states, DC, PR); '
            'default from WIKIDATA_LOAD_ALL_US_STATES (1/true/yes/on). '
            'Takes precedence over --priority-states when both are enabled.'
        ),
    )

    parser.add_argument(
        '--types',
        type=str,
        default=(
            os.getenv(
                "WIKIDATA_LOAD_TYPES",
                "city,county,state,school_district",
            ).strip()
            or 'city,county,state,school_district'
        ),
        help='Comma-separated jurisdiction types (default: env WIKIDATA_LOAD_TYPES)',
    )

    parser.add_argument(
        '--json-cache-dir',
        type=str,
        default=(os.getenv("WIKIDATA_JSON_CACHE_DIR") or "").strip() or None,
        help=(
            "Directory containing bronze_jurisdictions.json (produced by export_bronze_to_json.py). "
            "When set, no Postgres connection is made: GEOIDs are read from JSON and enrichment "
            "results are written to wikidata_enrichment_<ts>.json in the same dir. "
            "Default: env WIKIDATA_JSON_CACHE_DIR."
        ),
    )

    parser.add_argument(
        '--task-sleep-seconds',
        type=float,
        default=float(os.getenv("WIKIDATA_TASK_SLEEP_SECONDS", "2") or "2"),
        help='Sleep between jurisdiction-type queries within a state (default: env WIKIDATA_TASK_SLEEP_SECONDS or 2.0)'
    )

    parser.add_argument(
        '--checkpoint-file',
        type=str,
        default=(
            (os.getenv("WIKIDATA_LOAD_CHECKPOINT_FILE") or "").strip()
            or str(
                Path(
                    (
                        os.getenv("WIKIDATA_CACHE_DIR", "data/cache/wikidata").strip()
                        or "data/cache/wikidata"
                    )
                ).joinpath("wikidata_jurisdictions_checkpoint.json")
            )
        ),
        help=(
            "Checkpoint JSON for resume (default: beside WDQS cache dir under "
            "WIKIDATA_CACHE_DIR …/wikidata_jurisdictions_checkpoint.json)."
        ),
    )

    parser.add_argument(
        '--force',
        action=BooleanOptionalAction,
        default=_env_truthy("WIKIDATA_LOAD_FORCE"),
        help='Ignore existing checkpoint and re-fetch (default: env WIKIDATA_LOAD_FORCE)',
    )

    parser.add_argument(
        '--incremental-merge',
        action=BooleanOptionalAction,
        default=None,
        help=(
            'Preserve existing QIDs in bronze *_wikidata; only WDQS rows with NULL wikidata_id. '
            'Unset = use env WIKIDATA_INCREMENTAL_MERGE only.'
        ),
    )

    parser.add_argument(
        '--retry-county-gap-states',
        action=BooleanOptionalAction,
        default=_env_truthy("WIKIDATA_LOAD_RETRY_COUNTY_GAPS"),
        help=(
            "Query Postgres for USPS where county *_wikidata rows or wikidata_id coverage lags bronze; "
            "clear checkpoint for county on those USPS and rerun only those states (env "
            "WIKIDATA_LOAD_RETRY_COUNTY_GAPS)"
        ),
    )

    parser.add_argument(
        '--happy-path',
        action=BooleanOptionalAction,
        default=None,
        help=(
            "Apply WIKIDATA_HAPPY_PATH=1 and conservative defaults for unset env (slow WDQS cadence, "
            "bulk-only muni/school mapping, no county entity-search fallback, skip enriched priority USPS). "
            "Backfill stragglers later with supplements / --retry-county-gap-states."
        ),
    )

    args = parser.parse_args()

    if args.incremental_merge is True:
        os.environ["WIKIDATA_INCREMENTAL_MERGE"] = "1"
    elif args.incremental_merge is False:
        os.environ["WIKIDATA_INCREMENTAL_MERGE"] = "0"

    if args.happy_path is True:
        os.environ["WIKIDATA_HAPPY_PATH"] = "1"
    elif args.happy_path is False:
        os.environ["WIKIDATA_HAPPY_PATH"] = "0"
    _apply_wikidata_happy_path_env_defaults()

    types = [t.strip().lower() for t in args.types.split(',') if t.strip()]

    checkpoint = None if args.force else CheckpointManager(args.checkpoint_file)

    if args.retry_county_gap_states and "county" not in types:
        logger.warning(
            "County-gap mode (--retry-county-gap-states / WIKIDATA_LOAD_RETRY_COUNTY_GAPS) is on but "
            f"'county' is not in --types / WIKIDATA_LOAD_TYPES (got {types!r}). Ignoring county-gap discovery "
            "for this run. To scan Postgres for county gaps, include county in --types; to silence this, set "
            "WIKIDATA_LOAD_RETRY_COUNTY_GAPS=0 or pass --no-retry-county-gap-states."
        )
        args.retry_county_gap_states = False

    # Parse states and types.
    # Precedence: --all-us-states > --priority-states > county-gap discovery > explicit --states.
    # (County-gap env WIKIDATA_LOAD_RETRY_COUNTY_GAPS must not override an explicit --priority-states run.)
    if args.all_us_states:
        states = sorted(STATE_MAP.keys())
    elif args.priority_states:
        states = PRIORITY_STATES
        if not args.json_cache_dir and _env_truthy("WIKIDATA_PRIORITY_STATES_SKIP_COMPLETE", default=True):
            before = len(states)
            states = filter_states_with_pending_wikidata_for_types(DATABASE_URL, states, types)
            logger.info(
                f"Priority USPS with pending Wikidata (NULL wikidata_id) for types {types!r}: "
                f"{len(states)}/{before} — {','.join(states) if states else '(none)'}"
            )
            if not states:
                logger.success(
                    "All priority states already have wikidata_id for every row in the selected types — nothing to do."
                )
                return
    elif args.retry_county_gap_states:
        if args.json_cache_dir:
            logger.warning(
                "--retry-county-gap-states requires Postgres and is not supported in JSON cache mode; ignoring."
            )
            states = [s.strip().upper() for s in args.states.split(',') if s.strip()]
        else:
            logger.info("Discovering USPS with incomplete county Wikidata enrichment (bronze vs *_wikidata)...")
            states = fetch_usps_county_wikidata_gaps(DATABASE_URL)
            if not states:
                logger.success("No county Wikidata gaps found — all states match base row counts and wikidata_id coverage.")
                return
            logger.info(f"County gap rerun for {len(states)} USPS: {','.join(states)}")
            if checkpoint:
                cleared = sum(1 for s in states if checkpoint.unmark(s, "county"))
                logger.info(f"Cleared checkpoint for county on {cleared} USPS so those tasks rerun.")
            elif args.force:
                logger.info("FORCE=1 — checkpoint ignored; querying WDQS again for gap states.")
    else:
        states = [s.strip().upper() for s in args.states.split(',') if s.strip()]

    # Validate early so we don't partially write tables.
    unknown_states = [s for s in states if s not in STATE_MAP]
    if unknown_states:
        known_sample = ",".join(sorted(STATE_MAP.keys())[:12]) + ",…"
        raise SystemExit(
            f"Unknown state code(s): {', '.join(unknown_states)}. Known codes (sample): {known_sample}"
        )

    # Load data
    loader = JurisdictionsWikiDataLoader(DATABASE_URL, json_cache_dir=args.json_cache_dir)

    try:
        for state in states:
            await loader.load_state(state, types, checkpoint)
            # Be kind to WDQS; pause between states as well.
            if args.task_sleep_seconds and args.task_sleep_seconds > 0:
                await asyncio.sleep(args.task_sleep_seconds)

        logger.info("")
        logger.info("=" * 80)
        logger.info("FINAL SUMMARY")
        logger.info("=" * 80)

        if args.json_cache_dir:
            # Summarise from accumulated in-memory results (no Postgres).
            for task, rows in loader._json_results.items():
                youtube = sum(1 for r in rows if r.get("youtube_channel_id"))
                website = sum(1 for r in rows if r.get("official_website"))
                logger.info(f"{task:15s}: {len(rows):4d} rows fetched, {youtube:3d} with YouTube, {website:3d} with website")
            logger.info("Results will be saved to wikidata_enrichment_<ts>.json in the cache dir on close.")
        else:
            # Final summary (bronze *_wikidata tables)
            logger.info(
                "Bronze totals in Postgres across all USPS (not scoped to today's --states / gap list)."
            )
            cursor = loader.conn.cursor()
            cursor.execute("""
                SELECT 'state'::text AS jurisdiction_type,
                       COUNT(*)::int AS count,
                       COUNT(*) FILTER (WHERE youtube_channel_id IS NOT NULL)::int AS with_youtube,
                       COUNT(*) FILTER (WHERE official_website IS NOT NULL)::int AS with_website
                FROM bronze.bronze_jurisdictions_states_wikidata
                UNION ALL
                SELECT 'county'::text,
                       COUNT(*)::int,
                       COUNT(*) FILTER (WHERE youtube_channel_id IS NOT NULL)::int,
                       COUNT(*) FILTER (WHERE official_website IS NOT NULL)::int
                FROM bronze.bronze_jurisdictions_counties_wikidata
                UNION ALL
                SELECT 'municipality'::text,
                       COUNT(*)::int,
                       COUNT(*) FILTER (WHERE youtube_channel_id IS NOT NULL)::int,
                       COUNT(*) FILTER (WHERE official_website IS NOT NULL)::int
                FROM bronze.bronze_jurisdictions_municipalities_wikidata
                UNION ALL
                SELECT 'school_district'::text,
                       COUNT(*)::int,
                       COUNT(*) FILTER (WHERE youtube_channel_id IS NOT NULL)::int,
                       COUNT(*) FILTER (WHERE official_website IS NOT NULL)::int
                FROM bronze.bronze_jurisdictions_school_districts_wikidata
                ORDER BY count DESC
            """)
            for row in cursor.fetchall():
                jtype, count, youtube, website = row
                logger.info(f"{jtype:15s}: {count:4d} total, {youtube:3d} with YouTube, {website:3d} with website")
            cursor.close()

    finally:
        loader.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Graceful stop on Ctrl-C (avoid noisy asyncio/httpx traceback).
        logger.warning("Interrupted by user (Ctrl-C). Exiting.")
