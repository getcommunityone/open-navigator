#!/usr/bin/env python3
"""
Load cached USCM « Meet the Mayors » scrape JSON into bronze.

Expects output from ``download_uscm_mayors.py`` (``data/cache/uscm/meet_the_mayors_us_*.json``).

Database URL: NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / OPEN_NAVIGATOR_DATABASE_URL —
see ``scripts/database/target_database_url.py``.

Table:
    bronze.bronze_jurisdictions_municipalities_uscm — one row per municipality mayor card from USCM.

Usage:
    ./.venv/bin/python scripts/datasources/uscm/load_uscm_mayors_to_bronze.py
    ./.venv/bin/python scripts/datasources/uscm/load_uscm_mayors_to_bronze.py --file data/cache/uscm/meet_the_mayors_us_20260510.json
    ./.venv/bin/python scripts/datasources/uscm/load_uscm_mayors_to_bronze.py --truncate --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_VENV_REEXEC = "_OPEN_NAVIGATOR_USCM_LOAD_VENV_REEXEC"


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

CACHE_DIR = Path("data/cache/uscm")

BRONZE_TABLE = "bronze.bronze_jurisdictions_municipalities_uscm"

CREATE_SQL = f"""
    CREATE SCHEMA IF NOT EXISTS bronze;

    CREATE TABLE IF NOT EXISTS {BRONZE_TABLE} (
        state_code           VARCHAR(2) NOT NULL,
        municipality_name    VARCHAR(255) NOT NULL,
        mayor_name           VARCHAR(255),
        population           INTEGER,
        mayor_photo_url      TEXT,
        city_website         VARCHAR(500),
        bio_url              VARCHAR(500),
        next_election_raw    VARCHAR(255),
        phone                VARCHAR(80),
        email                VARCHAR(255),
        search_term_used     VARCHAR(120),
        source_url           VARCHAR(500),
        scraped_at           TIMESTAMPTZ,
        raw_json             JSONB,
        ingestion_date       TIMESTAMPTZ DEFAULT NOW(),
        PRIMARY KEY (state_code, municipality_name)
    );

    CREATE INDEX IF NOT EXISTS idx_bjmuscm_state ON {BRONZE_TABLE}(state_code);
"""

UPSERT_SQL = f"""
    INSERT INTO {BRONZE_TABLE}
        (state_code, municipality_name, mayor_name, population, mayor_photo_url,
         city_website, bio_url, next_election_raw, phone, email,
         search_term_used, source_url, scraped_at, raw_json)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
    ON CONFLICT (state_code, municipality_name) DO UPDATE SET
        mayor_name           = EXCLUDED.mayor_name,
        population           = EXCLUDED.population,
        mayor_photo_url      = EXCLUDED.mayor_photo_url,
        city_website         = EXCLUDED.city_website,
        bio_url              = EXCLUDED.bio_url,
        next_election_raw    = EXCLUDED.next_election_raw,
        phone                = EXCLUDED.phone,
        email                = EXCLUDED.email,
        search_term_used     = EXCLUDED.search_term_used,
        source_url           = EXCLUDED.source_url,
        scraped_at           = EXCLUDED.scraped_at,
        raw_json             = EXCLUDED.raw_json,
        ingestion_date       = NOW()
"""


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


def _int(val: Any) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def find_latest_cache() -> Path | None:
    paths = sorted(
        CACHE_DIR.glob("meet_the_mayors_us_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return paths[0] if paths else None


def parse_scrape_payload(raw: dict[str, Any]) -> tuple[list[tuple], dict[str, Any]]:
    """Return (db_rows, meta)."""
    meta = {
        "scraped_at": raw.get("scraped_at"),
        "source_url": raw.get("source_url"),
        "mayor_count": raw.get("mayor_count"),
    }
    mayors = raw.get("mayors")
    if not isinstance(mayors, list):
        return [], meta

    scraped_at = raw.get("scraped_at")
    source_url = _str(raw.get("source_url"), 500)

    rows: list[tuple] = []
    for m in mayors:
        if not isinstance(m, dict):
            continue
        state_code = _str(m.get("state_code"), 2)
        municipality_name = _str(m.get("municipality_name"), 255)
        if not state_code or not municipality_name:
            continue
        slim_raw = {k: v for k, v in m.items() if k != "raw_card_html"}
        rows.append(
            (
                state_code.upper(),
                municipality_name,
                _str(m.get("mayor_name"), 255),
                _int(m.get("population")),
                _str(m.get("mayor_photo_url"), None),
                _str(m.get("city_website"), 500),
                _str(m.get("bio_url"), 500),
                _str(m.get("next_election_raw"), 255),
                _str(m.get("phone"), 80),
                _str(m.get("email"), 255),
                _str(m.get("search_term_used"), 120),
                source_url,
                scraped_at,
                json.dumps(slim_raw),
            )
        )
    return rows, meta


def load_to_postgres(
    records: list[tuple],
    *,
    dry_run: bool,
    truncate: bool,
) -> dict[str, Any]:
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    cur = conn.cursor()

    cur.execute(CREATE_SQL)
    conn.commit()

    if truncate:
        cur.execute(f"SELECT COUNT(*) FROM {BRONZE_TABLE}")
        before = cur.fetchone()[0]
        cur.execute(f"TRUNCATE TABLE {BRONZE_TABLE}")
        conn.commit()
        logger.info(f"Truncated {BRONZE_TABLE} ({before:,} rows prior)")

    if dry_run:
        logger.warning("DRY RUN — no data written. Sample:")
        for row in records[:3]:
            logger.info(f"  {row[:4]}…")
        cur.close()
        conn.close()
        return {"parsed": len(records), "loaded": 0}

    if records:
        execute_batch(cur, UPSERT_SQL, records, page_size=2000)
        conn.commit()
        cur.execute(f"SELECT COUNT(*) FROM {BRONZE_TABLE}")
        total = cur.fetchone()[0]
        logger.success(
            f"Upserted {len(records):,} rows → {BRONZE_TABLE} (table total: {total:,})"
        )
    else:
        logger.warning("No mayor rows to load.")

    cur.close()
    conn.close()
    return {"parsed": len(records), "loaded": len(records)}


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load USCM Meet the Mayors JSON into bronze_jurisdictions_municipalities_uscm"
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Path to meet_the_mayors_us_*.json (default: newest under data/cache/uscm/)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--truncate", action="store_true")
    args = parser.parse_args()

    cache_file = args.file
    if cache_file is None:
        cache_file = find_latest_cache()
    if cache_file is None or not cache_file.is_file():
        logger.error(
            f"No cache file. Run download_uscm_mayors.py first or pass --file. "
            f"Expected under {CACHE_DIR}/meet_the_mayors_us_*.json"
        )
        sys.exit(1)

    logger.info("=" * 70)
    logger.info(f"USCM Meet the Mayors → {BRONZE_TABLE}")
    logger.info("=" * 70)
    logger.info(
        f"Database: {_database_url_source_label()} → {DATABASE_URL.split('@')[-1]}"
    )
    logger.info(f"Cache file: {cache_file}")

    raw = json.loads(cache_file.read_text(encoding="utf-8"))
    rows, meta = parse_scrape_payload(raw)
    logger.info(f"Meta: scraped_at={meta.get('scraped_at')}, mayor_count={meta.get('mayor_count')}")
    logger.info(f"Rows parsed for load: {len(rows):,}")

    stats = load_to_postgres(rows, dry_run=args.dry_run, truncate=args.truncate)
    logger.info("SUMMARY")
    for k, v in stats.items():
        logger.info(f"  {k}: {v:,}")
    logger.success("Done.")


if __name__ == "__main__":
    main()
