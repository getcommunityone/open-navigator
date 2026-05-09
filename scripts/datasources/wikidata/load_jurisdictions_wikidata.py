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

    # Load priority development states (AL, GA, IN, MA, WA, WI)
    .venv/bin/python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --priority-states

    # All 50 states + DC + PR (requires rows in bronze base tables per USPS where applicable)
    .venv/bin/python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --all-us-states --types county

    # Explicit list
    .venv/bin/python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --states TX,NY,OH

    # Load all jurisdiction types for one state (defaults include all four types + six priority USPS)
    .venv/bin/python scripts/datasources/wikidata/load_jurisdictions_wikidata.py --states AL
"""
import os
import sys
import argparse
from argparse import BooleanOptionalAction
import asyncio
import json
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple, Any
from datetime import datetime

try:
    import psycopg2
    from psycopg2.extras import execute_batch
except ModuleNotFoundError as exc:
    if exc.name != "psycopg2":
        raise
    _repo_root = Path(__file__).resolve().parents[3]
    _venv_py = _repo_root / ".venv" / "bin" / "python"
    sys.stderr.write(
        "ModuleNotFoundError: psycopg2 — install deps in the project venv or use its interpreter.\n"
        f"  Example: {_venv_py} {_repo_root / 'scripts/datasources/wikidata/load_jurisdictions_wikidata.py'} ...\n"
        "  Or: source .venv/bin/activate   (then run python3 …)\n"
        "  Setup: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt\n"
    )
    sys.exit(1)
from loguru import logger
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from scripts.datasources.wikidata.wikidata_integration import WikidataQuery
from scripts.datasources.wikidata.geography_qid_cache import GeographyQidCache
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
PRIORITY_STATES = ["AL", "GA", "IN", "MA", "WA", "WI"]


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
    Hybrid county id→Q resolution: ``entity_search`` (wbsearchentities + FIPS reconcile, no WDQS map query)
    or ``sparql`` (FILTER IN batch on WDQS). Default: entity_search — avoids giant SPARQL mapping batches.
    """
    raw = (os.getenv("WIKIDATA_HYBRID_COUNTY_MAP_MODE") or "entity_search").strip().lower()
    if raw in ("sparql", "wdqs", "map_sparql"):
        return "sparql"
    return "entity_search"


def _wikidata_state_legacy_sparql() -> bool:
    """When True, use WDQS for ``query_state_info``. Default: Wikibase API (wbgetentities / same JSON as EntityData)."""
    return _env_truthy("WIKIDATA_STATE_LEGACY_SPARQL", default=False)


def _wikidata_incremental_merge() -> bool:
    """
    When True, seeding merges Census base rows into *_wikidata without wiping existing QIDs,
    and WDQS runs only for rows where wikidata_id is still NULL (see WIKIDATA_INCREMENTAL_MERGE).
    """
    return _env_truthy("WIKIDATA_INCREMENTAL_MERGE", default=False)


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


def _sparql_quote_string_literal(s: str) -> str:
    """Escape a string for WDQS FILTER IN (\"…\") literals."""
    esc = str(s).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{esc}"'


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


# Bronze municipality rows join Wikidata largely via P774 (FIPS place code); P590 is GNIS (often = ansicode).
def _municipality_wd_literal_sets(geoid: str, ansicode: Optional[str]) -> tuple[Set[str], Set[str]]:
    fips_lit: Set[str] = set()
    gnis_lit: Set[str] = set()
    g = str(geoid).strip().replace("-", "")
    if not g:
        return fips_lit, gnis_lit
    fips_lit.add(g)
    if g.isdigit():
        if len(g) >= 7:
            p = g[2:7]
            fips_lit.add(p)
            fips_lit.add(p.zfill(5))
            fips_lit.add(g[-5:])
            fips_lit.add(g[-5:].zfill(5))
        elif len(g) == 5:
            fips_lit.add(g.zfill(5))
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
    """Load jurisdiction data from WikiData into PostgreSQL."""
    
    def __init__(self, database_url: str):
        self.conn = psycopg2.connect(database_url)
        self.wikidata = WikidataQuery()
        self._geography_qid_cache: GeographyQidCache | None = None
        
        # Create table
        self._create_table()

    def geography_qid_cache(self) -> GeographyQidCache:
        if self._geography_qid_cache is None:
            self._geography_qid_cache = GeographyQidCache()
        return self._geography_qid_cache

    def warm_geography_qid_cache_from_db(self, state_code: str, warm_task: str) -> None:
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
        Used with WIKIDATA_INCREMENTAL_MERGE to skip WDQS entirely when fully enriched.
        """
        if not _wikidata_incremental_merge():
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
        """Update the appropriate bronze *_wikidata table based on loader task."""
        if not jurisdictions:
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
        state_name: str,
        pairs: List[tuple[str, Optional[str]]],
        ansi_to_geoid: Dict[str, str],
    ) -> List[Dict]:
        """
        Narrow WDQS: only resolve Census literals → Wikidata items; hydrate claims via
        ``wbgetentities`` (or Pywikibot when ``WIKIDATA_ENRICH_USE_PYWIKIBOT=1``).
        Mappings accumulate in ``geography_qid_mapping_v1.json`` for incremental reruns.
        """
        self.warm_geography_qid_cache_from_db(state_code, "city")
        qcache = self.geography_qid_cache()
        chunk_size = _positive_int_env("WIKIDATA_CITY_CHUNK_SIZE", 25, 5, 150)
        chunk_sleep = _chunk_sleep_seconds(1.0)
        aggregated: List[Dict] = []
        n_chunks = (len(pairs) + chunk_size - 1) // chunk_size

        for ix in range(0, len(pairs), chunk_size):
            chunk = pairs[ix : ix + chunk_size]
            chi = ix // chunk_size + 1
            logger.info(f"Hybrid municipalities chunk {chi}/{n_chunks} ({len(chunk)} GEOIDs, {state_name})…")

            geo_to_q: Dict[str, str] = {}

            need_fips: Set[str] = set()
            need_gnis: Set[str] = set()

            for geo, ansi in chunk:
                ff, gg = _municipality_wd_literal_sets(geo, ansi)
                q = qcache.lookup_q_for_municipality(ff, gg)
                if q:
                    geo_to_q[str(geo).strip()] = q
                else:
                    need_fips |= ff
                    need_gnis |= gg

            filt_parts: List[str] = []
            f_list = sorted(_sparql_quote_string_literal(x) for x in need_fips)
            g_list = sorted(_sparql_quote_string_literal(x) for x in need_gnis)
            if need_fips:
                filt_parts.append(
                    '(BOUND(?fips) && REPLACE(STR(?fips), "-", "") IN (' + ", ".join(f_list) + "))"
                )
            if need_gnis:
                filt_parts.append(
                    '(BOUND(?gnis) && REPLACE(STR(?gnis), "-", "") IN (' + ", ".join(g_list) + "))"
                )
            filt = ""
            if len(filt_parts) == 2:
                filt = f"FILTER({' || '.join(filt_parts)})"
            elif len(filt_parts) == 1:
                filt = f"FILTER({filt_parts[0]})"

            mapping_rows: List[Dict] = []
            if filt:
                lim = min(5000, max(400, len(chunk) * 60))
                qtext = _wikidata_hybrid_sql.municipality_mapping_sparql(filt, lim)
                try:
                    mapping_rows = await self.wikidata.execute_sparql(qtext)
                except Exception as e:
                    logger.warning(f"Hybrid city mapping WDQS failed ({chi}/{n_chunks}): {type(e).__name__}: {e}")
                    mapping_rows = []
                mapping_rows = self._dedupe_sparql_bindings_by_item(mapping_rows)
                for mr in mapping_rows:
                    iq = (mr.get("item") or "").rsplit("/", 1)[-1].strip()
                    if not iq.startswith("Q"):
                        continue
                    qcache.remember_muni(iq, mr.get("fips"), mr.get("gnis"))

            for geo, ansi in chunk:
                gid = str(geo).strip()
                if gid in geo_to_q:
                    continue
                ff, gg = _municipality_wd_literal_sets(geo, ansi)
                iq = qcache.lookup_q_for_municipality(ff, gg)
                if iq:
                    geo_to_q[gid] = iq

            chunk_geos = {str(g).strip() for g, _ in chunk}
            q_needed = sorted({geo_to_q[g] for g in chunk_geos if g in geo_to_q})
            if not q_needed:
                qcache.save()
                continue

            enriched: List[Dict] = []
            py_try = try_pywikibot_rows(q_needed)
            if py_try is not None:
                enriched.extend(py_try)
            else:
                api_payload = await self.wikidata.wikibase_get_entities(q_needed)
                enriched.extend(entities_response_to_rows({"entities": api_payload}))

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
            aggregated.extend(chunk_out)
            qcache.save()
            if chunk_sleep > 0 and chi < n_chunks:
                await asyncio.sleep(chunk_sleep)

        logger.info(f"  Found {len(aggregated)} cities (hybrid)")
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

        for ix in range(0, len(geoids), csize):
            chunk = geoids[ix : ix + csize]
            chi = ix // csize + 1
            mlabel = "entity-search" if map_mode == "entity_search" else "WDQS-map"
            logger.info(f"Hybrid counties {mlabel} chunk {chi}/{n_chunks} ({state_name})…")
            geo_to_q: Dict[str, str] = {}

            if map_mode == "entity_search":
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
                    in_list = ", ".join(sorted(_sparql_quote_string_literal(x) for x in literals))
                    lim = min(2500, max(520, len(chunk) * 25))
                    mq = _wikidata_hybrid_sql.county_mapping_sparql(ctype, in_list, lim)
                    try:
                        mapping_rows = await self.wikidata.execute_sparql(mq)
                    except Exception as e:
                        logger.warning(f"Hybrid county mapping failed: {type(e).__name__}: {e}")
                        mapping_rows = []
                    mapping_rows = self._dedupe_sparql_bindings_by_item(mapping_rows)
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

        for ix in range(0, len(geoids), chunk_size):
            chunk = geoids[ix : ix + chunk_size]
            chi = ix // chunk_size + 1
            logger.info(f"Hybrid school districts map chunk {chi}/{n_chunks} ({state_name})…")
            geo_to_q: Dict[str, str] = {}
            literals: Set[str] = set()
            for gid in chunk:
                lits = _school_id_literal_alternatives(gid)
                cq = qcache.lookup_q_for_school(lits)
                if cq:
                    geo_to_q[str(gid).strip()] = cq
                else:
                    literals |= lits

            mapping_rows: List[Dict] = []
            if literals:
                id_in = ", ".join(sorted(_sparql_quote_string_literal(x) for x in literals))
                lim = min(2500, max(520, len(chunk) * 28))
                mq = _wikidata_hybrid_sql.school_mapping_sparql(id_in, lim)
                try:
                    mapping_rows = await self.wikidata.execute_sparql(mq)
                except Exception as e:
                    logger.warning(f"Hybrid school mapping failed: {type(e).__name__}: {e}")
                    mapping_rows = []
                mapping_rows = self._dedupe_sparql_bindings_by_item(mapping_rows)
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
                state_code, state_name, pairs, ansi_to_geoid
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

            f_in = ", ".join(sorted(_sparql_quote_string_literal(x) for x in fips_lit))
            g_in = ", ".join(sorted(_sparql_quote_string_literal(x) for x in gnis_lit))
            filt_parts: List[str] = []
            if f_in.strip():
                filt_parts.append(
                    f'(BOUND(?fips) && REPLACE(STR(?fips), "-", "") IN ({f_in}))'
                )
            if g_in.strip():
                filt_parts.append(
                    f'(BOUND(?gnis) && REPLACE(STR(?gnis), "-", "") IN ({g_in}))'
                )
            filt = ""
            if len(filt_parts) == 2:
                filt = f"FILTER({' || '.join(filt_parts)})"
            elif len(filt_parts) == 1:
                filt = f"FILTER({filt_parts[0]})"
            else:
                logger.warning(f"City batch has no literals (chunk)—skipping WDQS.")
                continue

            limit_rows = min(5000, max(900, chunk_size * 48))
            chi = ix // chunk_size + 1
            logger.info(f"Querying municipalities in {state_name} via identifier batch ({chi}/{n_chunks})…")

            query = f"""
            SELECT DISTINCT
                ?item ?itemLabel
                ?website ?population ?area
                ?facebook ?twitter ?youtube
                ?fips ?gnis
                ?image ?banner ?locatorMap
                ?lat ?lon
            WHERE {{
              VALUES ?placeType {{
                wd:Q515 wd:Q3957 wd:Q15284 wd:Q486972 wd:Q493522 wd:Q1115575
                wd:Q1549591 wd:Q15222645 wd:Q2989398 wd:Q1426695
              }}
              ?item wdt:P31 ?placeType .
              ?item wdt:P17 wd:Q30 .

              OPTIONAL {{ ?item wdt:P856 ?website . }}
              OPTIONAL {{ ?item wdt:P1082 ?population . }}
              OPTIONAL {{ ?item wdt:P2046 ?area . }}
              OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
              OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
              OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
              OPTIONAL {{ ?item wdt:P774 ?fips . }}
              OPTIONAL {{ ?item wdt:P590 ?gnis . }}
              OPTIONAL {{ ?item wdt:P18 ?image . }}
              OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
              OPTIONAL {{ ?item wdt:P948 ?banner . }}
              OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLatitude ?lat . }}
              OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLongitude ?lon . }}

              {filt}

              SERVICE wikibase:label {{ bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en". }}
            }}
            LIMIT {limit_rows}
            """

            try:
                chunk_rows = await self.wikidata.execute_sparql(query)
            except Exception as e:
                logger.warning(f"City batch query failed ({chi}/{n_chunks}): {type(e).__name__}: {e}")
                chunk_rows = []
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
            ?lat ?lon
        WHERE {{
          VALUES ?placeType {{
            wd:Q515 wd:Q3957 wd:Q15284 wd:Q486972 wd:Q493522 wd:Q1115575
            wd:Q1549591 wd:Q15222645 wd:Q2989398 wd:Q1426695
          }}
          ?item wdt:P31 ?placeType .
          ?item wdt:P131+ wd:{state_q_code} .
          ?item wdt:P17 wd:Q30 .

          OPTIONAL {{ ?item wdt:P856 ?website . }}
          OPTIONAL {{ ?item wdt:P1082 ?population . }}
          OPTIONAL {{ ?item wdt:P2046 ?area . }}
          OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
          OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
          OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
          OPTIONAL {{ ?item wdt:P774 ?fips . }}
          OPTIONAL {{ ?item wdt:P590 ?gnis . }}
          OPTIONAL {{ ?item wdt:P18 ?image . }}
          OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
          OPTIONAL {{ ?item wdt:P948 ?banner . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLatitude ?lat . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLongitude ?lon . }}

          FILTER(BOUND(?fips))

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

        seen_ids: Set[str] = set()
        ordered_ids: List[str] = []
        for phrase in phrases:
            try:
                hits = await self.wikidata.wikibase_search_entities(phrase, limit=14)
            except Exception as exc:
                logger.debug(f"wbsearchentities failed for {phrase[:60]!r}: {type(exc).__name__}: {exc}")
                hits = []
            for h in hits:
                qid = h.get("id")
                if isinstance(qid, str) and qid.startswith("Q") and qid not in seen_ids:
                    seen_ids.add(qid)
                    ordered_ids.append(qid)
            if len(ordered_ids) >= 24:
                break

        if not ordered_ids:
            return None

        try:
            ents = await self.wikidata.wikibase_get_entities(
                ordered_ids[:28], wikibase_props="labels|claims"
            )
        except Exception as exc:
            logger.warning(f"wbgetentities (county search reconcile) failed: {type(exc).__name__}: {exc}")
            return None

        for qid in ordered_ids:
            ent = ents.get(qid)
            if not ent:
                continue
            ok, _seen = wes.entity_claim_identifier_literals(ent, lits)
            if ok:
                return (qid, ent)
        return None

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
            in_list = ", ".join(sorted(_sparql_quote_string_literal(x) for x in literals))

            limit_rows = max(550, chunk_size * 25)
            limit_rows = min(limit_rows, 2500)

            query = f"""
            SELECT DISTINCT
                ?item ?itemLabel ?website ?population ?area
                ?facebook ?twitter ?youtube ?fips ?fipsAlt ?gnis ?nces ?image ?banner ?locatorMap
                ?lat ?lon
                ?geonamesId
            WHERE {{
              VALUES ?countyType {{ {county_type_values} }}
              ?item wdt:P31 ?countyType .

              OPTIONAL {{ ?item wdt:P856 ?website . }}
              OPTIONAL {{ ?item wdt:P1082 ?population . }}
              OPTIONAL {{ ?item wdt:P2046 ?area . }}
              OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
              OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
              OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
              OPTIONAL {{ ?item wdt:P882 ?fips . }}
              OPTIONAL {{ ?item wdt:P3006 ?fipsAlt . }}
              OPTIONAL {{ ?item wdt:P590 ?gnis . }}
              OPTIONAL {{ ?item wdt:P6545 ?nces . }}
              OPTIONAL {{ ?item wdt:P18 ?image . }}
              OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
              OPTIONAL {{ ?item wdt:P948 ?banner . }}
              OPTIONAL {{ ?item wdt:P1566 ?geonamesId . }}
              OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLatitude ?lat . }}
              OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLongitude ?lon . }}

              FILTER(
                (BOUND(?fips) && REPLACE(STR(?fips), "-", "") IN ({in_list}))
                || (BOUND(?fipsAlt) && REPLACE(STR(?fipsAlt), "-", "") IN ({in_list}))
              )

              SERVICE wikibase:label {{
                bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en".
              }}
            }}
            LIMIT {limit_rows}
            """

            chi = ix // chunk_size + 1
            logger.info(f"  County WDQS chunk {chi}/{n_chunks} ({len(chunk)} GEOIDs, ~{len(literals)} literals)…")
            try:
                chunk_rows = await self.wikidata.execute_sparql(query)
            except Exception as e:
                logger.warning(f"County batch query failed ({chi}/{n_chunks}): {type(e).__name__}: {e}")
                chunk_rows = []
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
            ?lat ?lon
            ?geonamesId
        WHERE {{
          VALUES ?countyType {{ {county_type_values} }}
          ?item wdt:P31 ?countyType .

          ?item wdt:P131+ wd:{state_q_code} .

          OPTIONAL {{ ?item wdt:P856 ?website . }}
          OPTIONAL {{ ?item wdt:P1082 ?population . }}
          OPTIONAL {{ ?item wdt:P2046 ?area . }}
          OPTIONAL {{ ?item wdt:P2013 ?facebook . }}
          OPTIONAL {{ ?item wdt:P2002 ?twitter . }}
          OPTIONAL {{ ?item wdt:P2397 ?youtube . }}
          OPTIONAL {{ ?item wdt:P882 ?fips . }}
          OPTIONAL {{ ?item wdt:P3006 ?fipsAlt . }}
          OPTIONAL {{ ?item wdt:P590 ?gnis . }}
          OPTIONAL {{ ?item wdt:P6545 ?nces . }}
          OPTIONAL {{ ?item wdt:P18 ?image . }}
          OPTIONAL {{ ?item wdt:P242 ?locatorMap . }}
          OPTIONAL {{ ?item wdt:P948 ?banner . }}
          OPTIONAL {{ ?item wdt:P1566 ?geonamesId . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLatitude ?lat . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLongitude ?lon . }}

          FILTER(BOUND(?fips) || BOUND(?fipsAlt))

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

            id_in = ", ".join(sorted(_sparql_quote_string_literal(x) for x in literals))

            filt = ""
            if id_in.strip():
                filt = f"""FILTER(
                  (BOUND(?nces) && REPLACE(STR(?nces), "-", "") IN ({id_in}))
                  || (BOUND(?fips) && REPLACE(STR(?fips), "-", "") IN ({id_in}))
                )"""
            else:
                continue

            limit_rows = min(2500, max(520, chunk_size * 28))
            chi = ix // chunk_size + 1
            logger.info(f"Querying school districts in {state_name} via NCES/FIPS batch ({chi}/{n_chunks})…")

            query = f"""
            SELECT DISTINCT
                ?item ?itemLabel ?website ?population ?area
                ?facebook ?twitter ?youtube ?fips ?gnis ?nces ?image ?banner ?locatorMap
                ?dialingCode ?googleMapsCustomerId ?households ?medianAge
                ?lat ?lon
                ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
                ?ballotpediaId ?tripadvisorId ?subreddit
                ?geonamesId
            WHERE {{
              ?item wdt:P31 wd:Q1455778 .

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
              OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLatitude ?lat . }}
              OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLongitude ?lon . }}
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

              {filt}

              SERVICE wikibase:label {{
                bd:serviceParam wikibase:language "[AUTO_LANGUAGE],en".
              }}
            }}
            LIMIT {limit_rows}
            """

            try:
                chunk_rows = await self.wikidata.execute_sparql(query)
            except Exception as e:
                logger.warning(
                    f"School district batch query failed ({chi}/{n_chunks}): {type(e).__name__}: {e}"
                )
                chunk_rows = []
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
            ?lat ?lon
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
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLatitude ?lat . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLongitude ?lon . }}
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
                'latitude': float(result.get("lat")) if result.get("lat") else None,
                'longitude': float(result.get("lon")) if result.get("lon") else None,
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
                "latitude": float(result.get("lat")) if result.get("lat") else None,
                "longitude": float(result.get("lon")) if result.get("lon") else None,
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

    async def _query_state_info_via_wikibase(self, state_code: str, state_info: dict) -> List[Dict]:
        state_name = state_info["name"]
        state_q_code = state_info["q_code"]
        logger.info(f"Fetching state Wikidata entity via API ({state_name}, {state_q_code})…")
        ents = await self.wikidata.wikibase_get_entities(
            [state_q_code], wikibase_props="labels|descriptions|aliases|claims"
        )
        entity = ents.get(state_q_code)
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
            ?lat ?lon
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
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLatitude ?lat . }}
          OPTIONAL {{ ?item p:P625/psv:P625/wikibase:geoLongitude ?lon . }}
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
          ?lat ?lon ?postalCode ?perCapitaIncome ?timeZone ?timeZoneLabel
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
                results = await self._query_cities_in_state(state_code, state_q_code, state_name)
            elif task == 'county':
                results = await self._query_counties_in_state(state_code, state_q_code, state_name)
            elif task == 'school_district':
                results = await self._query_schools_in_state(state_code, state_q_code, state_name)
            else:
                continue

            all_jurisdictions.extend(results)
            if results:
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
        """Close database connection."""
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

    args = parser.parse_args()

    if args.incremental_merge is True:
        os.environ["WIKIDATA_INCREMENTAL_MERGE"] = "1"
    elif args.incremental_merge is False:
        os.environ["WIKIDATA_INCREMENTAL_MERGE"] = "0"

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

    # Parse states and types
    if args.retry_county_gap_states:
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
    elif args.all_us_states:
        states = sorted(STATE_MAP.keys())
    elif args.priority_states:
        states = PRIORITY_STATES
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
    loader = JurisdictionsWikiDataLoader(DATABASE_URL)
    
    try:
        for state in states:
            await loader.load_state(state, types, checkpoint)
            # Be kind to WDQS; pause between states as well.
            if args.task_sleep_seconds and args.task_sleep_seconds > 0:
                await asyncio.sleep(args.task_sleep_seconds)
        
        # Final summary (bronze *_wikidata tables)
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
        
        logger.info("")
        logger.info("=" * 80)
        logger.info("FINAL SUMMARY")
        logger.info("=" * 80)
        logger.info(
            "Bronze totals in Postgres across all USPS (not scoped to today's --states / gap list)."
        )

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
