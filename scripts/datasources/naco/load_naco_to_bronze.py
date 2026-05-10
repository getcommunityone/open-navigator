#!/usr/bin/env python3
"""
Load cached NACo county data into bronze.bronze_naco_* tables.

Run scrape_naco_counties.py first to populate the cache.

Database URL resolution matches the rest of the repo: NEON_DATABASE_URL_DEV,
NEON_DATABASE_URL, OPEN_NAVIGATOR_DATABASE_URL — see scripts/database/target_database_url.py.

Tables created:
    bronze.bronze_naco_counties   — one row per county
    bronze.bronze_naco_officials  — one row per county official

Usage:
    ./.venv/bin/python scripts/datasources/naco/load_naco_to_bronze.py
    python3 scripts/datasources/naco/load_naco_to_bronze.py --states AL,GA
    python3 scripts/datasources/naco/load_naco_to_bronze.py --date 20260510
    python3 scripts/datasources/naco/load_naco_to_bronze.py --truncate
    python3 scripts/datasources/naco/load_naco_to_bronze.py --dry-run
"""
import sys
import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_VENV_REEXEC = "_OPEN_NAVIGATOR_NACO_VENV_REEXEC"


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
    from psycopg2.extras import execute_batch
    from dotenv import load_dotenv
    from loguru import logger
except ImportError:
    _maybe_reexec_with_project_venv()
    hints = [
        "NACo loader needs psycopg2-binary, python-dotenv, loguru (see requirements.txt).",
        "Install dependencies, then retry:",
        f"  cd {_ROOT}",
        "  ./.venv/bin/pip install -r requirements.txt",
        "  ./.venv/bin/python scripts/datasources/naco/load_naco_to_bronze.py   # add your flags, e.g. --states AL,GA,MA",
    ]
    print("\n".join(hints), file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(_ROOT))

# Load repo .env from project root first (works even when cwd is elsewhere)
load_dotenv(_ROOT / ".env")
load_dotenv()

from scripts.database.target_database_url import resolve_target_database_url

DATABASE_URL = resolve_target_database_url()


def _database_url_source_label() -> str:
    """Which env input won (same order as target_database_url.resolve_target_database_url)."""
    if (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip():
        return "OPEN_NAVIGATOR_DATABASE_URL"
    if (os.getenv("NEON_DATABASE_URL_DEV") or "").strip():
        return "NEON_DATABASE_URL_DEV"
    if (os.getenv("NEON_DATABASE_URL") or "").strip():
        return "NEON_DATABASE_URL"
    return "default local (localhost:5433/open_navigator)"

CACHE_DIR = Path("data/cache/naco")

CREATE_COUNTIES_SQL = """
    CREATE SCHEMA IF NOT EXISTS bronze;

    CREATE TABLE IF NOT EXISTS bronze.bronze_naco_counties (
        naco_id             VARCHAR(50),
        county_name         VARCHAR(255),
        state_code          VARCHAR(2),
        fips_code           VARCHAR(5),
        website             VARCHAR(500),
        phone               VARCHAR(50),
        email               VARCHAR(255),
        population          INTEGER,
        area_sq_miles       NUMERIC(12, 2),
        county_seat         VARCHAR(255),
        raw_json            JSONB,
        ingestion_date      TIMESTAMP DEFAULT NOW(),
        PRIMARY KEY (state_code, county_name)
    );

    CREATE INDEX IF NOT EXISTS idx_bnc_state      ON bronze.bronze_naco_counties(state_code);
    CREATE INDEX IF NOT EXISTS idx_bnc_fips       ON bronze.bronze_naco_counties(fips_code);
"""

CREATE_OFFICIALS_SQL = """
    CREATE TABLE IF NOT EXISTS bronze.bronze_naco_officials (
        id                  SERIAL PRIMARY KEY,
        state_code          VARCHAR(2),
        county_name         VARCHAR(255),
        fips_code           VARCHAR(5),
        official_name       VARCHAR(255),
        title               VARCHAR(255),
        email               VARCHAR(255),
        phone               VARCHAR(50),
        raw_json            JSONB,
        ingestion_date      TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_bno_state      ON bronze.bronze_naco_officials(state_code);
    CREATE INDEX IF NOT EXISTS idx_bno_fips       ON bronze.bronze_naco_officials(fips_code);
    CREATE INDEX IF NOT EXISTS idx_bno_county     ON bronze.bronze_naco_officials(state_code, county_name);
"""

UPSERT_COUNTY_SQL = """
    INSERT INTO bronze.bronze_naco_counties
        (naco_id, county_name, state_code, fips_code, website, phone, email,
         population, area_sq_miles, county_seat, raw_json)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (state_code, county_name) DO UPDATE SET
        naco_id        = EXCLUDED.naco_id,
        fips_code      = EXCLUDED.fips_code,
        website        = EXCLUDED.website,
        phone          = EXCLUDED.phone,
        email          = EXCLUDED.email,
        population     = EXCLUDED.population,
        area_sq_miles  = EXCLUDED.area_sq_miles,
        county_seat    = EXCLUDED.county_seat,
        raw_json       = EXCLUDED.raw_json,
        ingestion_date = NOW()
"""

INSERT_OFFICIAL_SQL = """
    INSERT INTO bronze.bronze_naco_officials
        (state_code, county_name, fips_code, official_name, title, email, phone, raw_json)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""


def _str(val: Any, maxlen: int | None = None) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def _int(val: Any) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _float(val: Any) -> float | None:
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _naco_profile_county_block(raw: dict[str, Any]) -> dict[str, Any]:
    """``county`` object inside cached ``naco_get_county`` from ce.naco.org ``/get/county``."""
    pkg = raw.get("naco_get_county")
    if not isinstance(pkg, dict) or not pkg.get("found"):
        return {}
    inner = pkg.get("county")
    return inner if isinstance(inner, dict) else {}


def _population_from_naco_display(val: Any) -> int | None:
    if val is None:
        return None
    pl = str(val).strip().replace(",", "")
    digits = "".join(c for c in pl if c.isdigit())
    return _int(digits) if digits else None


def parse_county(raw: dict[str, Any]) -> tuple | None:
    """Convert a raw NACo county JSON dict into a DB row tuple."""
    inner = _naco_profile_county_block(raw)

    county_name = _str(
        raw.get("name") or raw.get("county_name") or raw.get("countyName"), 255
    )
    state_code = _str(
        raw.get("state") or raw.get("state_code") or raw.get("stateCode"), 2
    )
    if not county_name or not state_code:
        return None

    population = raw.get("population")
    if population is None:
        population = _population_from_naco_display(inner.get("Population_Level"))
    if population is None:
        population = raw.get("pop")

    area = raw.get("area_sq_miles") or raw.get("area") or raw.get("areaSqMiles")
    if area is None and inner.get("Land_Area") is not None:
        land = str(inner.get("Land_Area")).strip().replace(",", "")
        land_num = "".join(c for c in land if c in ".0123456789")
        area = _float(land_num) if land_num else None

    website = raw.get("website") or raw.get("url") or raw.get("countyWebsite")
    if website is None:
        website = inner.get("County_Website")

    county_seat = raw.get("county_seat") or raw.get("countySeat") or raw.get("seat")
    if county_seat is None:
        county_seat = inner.get("County_Seat")

    return (
        _str(raw.get("id") or raw.get("naco_id"), 50),
        county_name,
        state_code.upper(),
        _str(raw.get("fips") or raw.get("fips_code") or raw.get("geoid"), 5),
        _str(website, 500),
        _str(raw.get("phone") or raw.get("phoneNumber"), 50),
        _str(raw.get("email") or raw.get("contactEmail"), 255),
        _int(population),
        _float(area),
        _str(county_seat, 255),
        json.dumps(raw),
    )


def parse_officials(raw: dict[str, Any]) -> list[tuple]:
    """Extract official rows from a county detail JSON dict."""
    county_name = _str(
        raw.get("name") or raw.get("county_name") or raw.get("countyName"), 255
    )
    state_code = _str(
        raw.get("state") or raw.get("state_code") or raw.get("stateCode"), 2
    )
    fips_code = _str(raw.get("fips") or raw.get("fips_code") or raw.get("geoid"), 5)

    officials_raw = (
        raw.get("officials")
        or raw.get("contacts")
        or raw.get("staff")
        or []
    )
    rows = []
    for off in officials_raw:
        name = _str(off.get("name") or off.get("officialName") or off.get("fullName"), 255)
        title = _str(off.get("title") or off.get("position") or off.get("role"), 255)
        if not name:
            continue
        rows.append((
            state_code.upper() if state_code else None,
            county_name,
            fips_code,
            name,
            title,
            _str(off.get("email"), 255),
            _str(off.get("phone") or off.get("phoneNumber"), 50),
            json.dumps(off),
        ))
    return rows


def find_cache_files(date_str: str | None, states: list[str] | None) -> list[Path]:
    """Locate county JSON cache files matching date + state filters."""
    pattern = f"naco_counties_*.json"
    all_files = sorted(CACHE_DIR.glob(pattern))

    if date_str:
        all_files = [f for f in all_files if date_str in f.name]

    if states:
        all_files = [
            f for f in all_files
            if any(f.name.startswith(f"naco_counties_{s}_") for s in states)
        ]

    return all_files


def find_officials_cache_files(date_str: str | None) -> list[Path]:
    officials_dir = CACHE_DIR / "officials"
    if not officials_dir.exists():
        return []
    pattern = f"naco_officials_*.json"
    files = sorted(officials_dir.glob(pattern))
    if date_str:
        files = [f for f in files if date_str in f.name]
    return files


def _connect_postgres():
    try:
        return psycopg2.connect(DATABASE_URL)
    except psycopg2.OperationalError as e:
        tail = DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else DATABASE_URL
        logger.error(f"PostgreSQL connection failed ({tail}): {e}")
        if ":5432/" in DATABASE_URL or ":5432" in tail:
            logger.error(
                "Connection URL uses port 5432. For local Docker, open_navigator is often on 5433; "
                "NEON_DATABASE_URL_DEV in .env should match your actual server. "
                "See scripts/database/target_database_url.py for resolution order."
            )
        else:
            logger.error(
                "Check POSTGRES_PASSWORD and that the server is listening on the host:port above."
            )
        raise


def load_to_postgres(
    county_records: list[tuple],
    official_records: list[tuple],
    dry_run: bool = False,
    truncate: bool = False,
) -> dict[str, int]:
    conn = _connect_postgres()
    cur = conn.cursor()

    cur.execute(CREATE_COUNTIES_SQL)
    cur.execute(CREATE_OFFICIALS_SQL)
    conn.commit()

    if truncate:
        cur.execute("SELECT COUNT(*) FROM bronze.bronze_naco_counties")
        before_c = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM bronze.bronze_naco_officials")
        before_o = cur.fetchone()[0]
        cur.execute("TRUNCATE TABLE bronze.bronze_naco_counties, bronze.bronze_naco_officials")
        conn.commit()
        logger.info(f"Truncated bronze_naco_counties ({before_c:,} rows) and bronze_naco_officials ({before_o:,} rows)")

    stats = {"counties_parsed": len(county_records), "officials_parsed": len(official_records)}

    if dry_run:
        logger.warning("DRY RUN — no data written. First 3 county records:")
        for row in county_records[:3]:
            logger.info(f"  {row[:5]}…")
        cur.close()
        conn.close()
        stats.update({"counties_loaded": 0, "officials_loaded": 0})
        return stats

    if county_records:
        execute_batch(cur, UPSERT_COUNTY_SQL, county_records, page_size=2000)
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM bronze.bronze_naco_counties")
        total_c = cur.fetchone()[0]
        logger.success(f"Upserted {len(county_records):,} counties → bronze.bronze_naco_counties (table total: {total_c:,})")
    else:
        logger.warning("No county records to load.")
        total_c = 0

    if official_records:
        execute_batch(cur, INSERT_OFFICIAL_SQL, official_records, page_size=2000)
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM bronze.bronze_naco_officials")
        total_o = cur.fetchone()[0]
        logger.success(f"Inserted {len(official_records):,} officials → bronze.bronze_naco_officials (table total: {total_o:,})")
    else:
        logger.info("No official records found (run scrape with --details to collect them).")
        total_o = 0

    cur.close()
    conn.close()
    stats.update({"counties_loaded": len(county_records), "officials_loaded": len(official_records)})
    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Load cached NACo county data into bronze.bronze_naco_* tables"
    )
    parser.add_argument("--states", type=str, help="Comma-separated state codes to load (e.g., AL,GA,MA)")
    parser.add_argument("--date", type=str, help="Cache date to load (YYYYMMDD). Default: today.")
    parser.add_argument("--dry-run", action="store_true", help="Parse only, do not write to database")
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE tables before loading")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("NACo cache → bronze.bronze_naco_counties / bronze_naco_officials")
    logger.info("=" * 70)
    logger.info(
        f"Database: {_database_url_source_label()} → {DATABASE_URL.split('@')[-1]}"
    )

    date_str = args.date or datetime.now().strftime("%Y%m%d")
    state_filter = [s.strip().upper() for s in args.states.split(",")] if args.states else None

    county_files = find_cache_files(date_str, state_filter)
    if not county_files:
        logger.error(
            f"No cache files found in {CACHE_DIR} for date={date_str}, states={state_filter}. "
            "Run scrape_naco_counties.py first."
        )
        sys.exit(1)

    logger.info(f"Found {len(county_files)} county cache file(s)")

    county_records: list[tuple] = []
    for cache_file in county_files:
        raw_list = json.loads(cache_file.read_text())
        for raw in raw_list:
            if raw.get("_fallback"):
                # Raw HTML fallback — skip, no structured data to parse yet
                logger.warning(f"Skipping fallback HTML entry in {cache_file.name}")
                continue
            row = parse_county(raw)
            if row:
                county_records.append(row)

    officials_files = find_officials_cache_files(date_str)
    official_records: list[tuple] = []
    for off_file in officials_files:
        raw = json.loads(off_file.read_text())
        official_records.extend(parse_officials(raw))

    logger.info(f"County records parsed  : {len(county_records):,}")
    logger.info(f"Official records parsed: {len(official_records):,}")

    stats = load_to_postgres(
        county_records,
        official_records,
        dry_run=args.dry_run,
        truncate=args.truncate,
    )

    logger.info("=" * 70)
    logger.info("SUMMARY")
    logger.info("=" * 70)
    for k, v in stats.items():
        logger.info(f"  {k}: {v:,}")
    logger.success("Done.")


if __name__ == "__main__":
    main()
