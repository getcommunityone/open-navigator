#!/usr/bin/env python3
"""
Load a scraped Power BI ballot-measures CSV into ``bronze.bronze_ballot_measures_powerbi``.

Reads the CSV produced by ``download_powerbi_ballot_measures.py``, maps a
best-effort set of columns into the denormalized bronze columns, stores the
full row as JSONB in ``raw_row``, and verifies the post-load count against
``--expected-count`` (default 9670 — the headline KPI on the source
dashboard).

Usage
-----
    python scripts/datasources/powerbi_ballot_measures/load_powerbi_ballot_measures_to_bronze.py
    python scripts/datasources/powerbi_ballot_measures/load_powerbi_ballot_measures_to_bronze.py --truncate
    python scripts/datasources/powerbi_ballot_measures/load_powerbi_ballot_measures_to_bronze.py \
        --file data/cache/powerbi_ballot_measures/ballot_measures_20260524T200000Z.csv \
        --expected-count 9670
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from pathlib import Path
from typing import Any

import pandas as pd
import psycopg2
from dotenv import load_dotenv
from loguru import logger
from psycopg2.extras import Json, execute_batch

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))
load_dotenv(_ROOT / ".env")

CACHE_DIR = _ROOT / "data" / "cache" / "powerbi_ballot_measures"
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "password")
DATABASE_URL = (
    os.getenv("NEON_DATABASE_URL_DEV", "").strip()
    or os.getenv("OPEN_NAVIGATOR_DATABASE_URL", "").strip()
    or f"postgresql://postgres:{POSTGRES_PASSWORD}@localhost:5433/open_navigator"
)

TABLE = "bronze.bronze_ballot_measures_powerbi"

CREATE_TABLE_SQL = """
    CREATE SCHEMA IF NOT EXISTS bronze;
    CREATE TABLE IF NOT EXISTS bronze.bronze_ballot_measures_powerbi (
        id                  BIGSERIAL PRIMARY KEY,
        scrape_batch_id     UUID NOT NULL,
        measure_id          TEXT,
        measure_title       TEXT,
        measure_summary     TEXT,
        measure_type        TEXT,
        state_code          CHAR(2),
        state               TEXT,
        jurisdiction_name   TEXT,
        election_date       DATE,
        election_year       INTEGER,
        outcome             TEXT,
        yes_count           BIGINT,
        no_count            BIGINT,
        yes_percent         DOUBLE PRECISION,
        source_url          TEXT,
        raw_row             JSONB NOT NULL DEFAULT '{}'::JSONB,
        source_csv_path     TEXT,
        scraped_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        loaded_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_bbmp_state    ON bronze.bronze_ballot_measures_powerbi (state_code);
    CREATE INDEX IF NOT EXISTS idx_bbmp_year     ON bronze.bronze_ballot_measures_powerbi (election_year);
    CREATE INDEX IF NOT EXISTS idx_bbmp_date     ON bronze.bronze_ballot_measures_powerbi (election_date);
    CREATE INDEX IF NOT EXISTS idx_bbmp_batch    ON bronze.bronze_ballot_measures_powerbi (scrape_batch_id);
    CREATE INDEX IF NOT EXISTS idx_bbmp_outcome  ON bronze.bronze_ballot_measures_powerbi (outcome);
"""

INSERT_SQL = """
    INSERT INTO bronze.bronze_ballot_measures_powerbi (
        scrape_batch_id, measure_id, measure_title, measure_summary, measure_type,
        state_code, state, jurisdiction_name, election_date, election_year,
        outcome, yes_count, no_count, yes_percent, source_url, raw_row, source_csv_path
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s
    )
"""


# Heuristic column-name → bronze-column mapping. Lowercased & non-alphanumeric
# stripped before matching so "Measure Title", "measure_title", and
# "MeasureTitle" all collapse to the same key.
_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


def _norm(col: str) -> str:
    return _NORMALIZE_RE.sub("", col.lower())


COLUMN_ALIASES: dict[str, list[str]] = {
    "measure_id":        ["measureid", "id", "ballotmeasureid", "ocdid", "g10"],
    "measure_title":     ["measuretitle", "title", "measurename", "name", "ballotmeasure", "measure", "g2"],
    "measure_summary":   ["measuresummary", "summary", "description", "ballotsummary", "g3"],
    "measure_type":      ["measuretype", "type", "classification", "ballottype", "irtypedefinition", "g4", "ballottypecombined", "g9"],
    "state_code":        ["statecode", "stateabbreviation", "stateabbr", "st"],
    "state":             ["state", "statename", "statename1", "g0"],
    "jurisdiction_name": ["jurisdiction", "jurisdictionname", "locality", "city", "county"],
    "election_date":     ["electiondate", "date", "votedate"],
    "election_year":     ["electionyear", "year", "g1"],
    "outcome":           ["outcome", "result", "status", "passfail", "passfailcalculation", "g7"],
    "yes_count":         ["yescount", "yesvotes", "votesyes", "yes"],
    "no_count":          ["nocount", "novotes", "votesno", "no"],
    "yes_percent":       ["yespercent", "yespct", "percentyes", "approval", "percentagevote", "g8"],
    "source_url":        ["sourceurl", "url", "link", "ballotpediaurl"],
}


def _build_column_map(csv_columns: list[str]) -> dict[str, str | None]:
    """Map each bronze column → the matching CSV column header (or None)."""
    norm_to_csv = {_norm(c): c for c in csv_columns}
    mapping: dict[str, str | None] = {}
    for bronze_col, aliases in COLUMN_ALIASES.items():
        match = None
        for alias in aliases:
            if alias in norm_to_csv:
                match = norm_to_csv[alias]
                break
        mapping[bronze_col] = match
    return mapping


def _coerce_int(val: Any) -> int | None:
    if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        s = str(val).replace(",", "").strip()
        return int(float(s)) if s else None
    except (ValueError, TypeError):
        return None


def _coerce_float(val: Any) -> float | None:
    if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        s = str(val).replace(",", "").replace("%", "").strip()
        return float(s) if s else None
    except (ValueError, TypeError):
        return None


def _coerce_str(val: Any, maxlen: int | None = None) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def _coerce_date(val: Any) -> str | None:
    if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return pd.to_datetime(val, errors="raise").date().isoformat()
    except (ValueError, TypeError):
        return None


def find_latest_csv() -> Path:
    csvs = sorted(CACHE_DIR.glob("ballot_measures_*.csv"), reverse=True)
    if not csvs:
        raise FileNotFoundError(
            f"No CSV found in {CACHE_DIR}. Run download_powerbi_ballot_measures.py first."
        )
    return csvs[0]


def parse_csv(csv_path: Path, limit: int | None = None) -> tuple[list[tuple], int]:
    logger.info("Reading {}", csv_path)
    df = pd.read_csv(csv_path, dtype=str, low_memory=False, keep_default_na=False)
    df = df.replace({"": None})
    source_rows = len(df)
    logger.info("CSV: {:,} rows × {} cols. Columns: {}",
                source_rows, len(df.columns), list(df.columns))

    if limit:
        df = df.head(limit)

    col_map = _build_column_map(list(df.columns))
    logger.info("Column mapping → bronze:")
    for bronze_col, csv_col in col_map.items():
        logger.info("  {:<18} ← {}", bronze_col, csv_col or "(no match)")

    batch_id = str(uuid.uuid4())
    logger.info("scrape_batch_id = {}", batch_id)

    records: list[tuple] = []
    for _, row in df.iterrows():
        raw_row = {k: (None if v is None else str(v)) for k, v in row.to_dict().items()}
        records.append((
            batch_id,
            _coerce_str(row.get(col_map["measure_id"])) if col_map["measure_id"] else None,
            _coerce_str(row.get(col_map["measure_title"])) if col_map["measure_title"] else None,
            _coerce_str(row.get(col_map["measure_summary"])) if col_map["measure_summary"] else None,
            _coerce_str(row.get(col_map["measure_type"])) if col_map["measure_type"] else None,
            _coerce_str(row.get(col_map["state_code"]), maxlen=2) if col_map["state_code"] else None,
            _coerce_str(row.get(col_map["state"])) if col_map["state"] else None,
            _coerce_str(row.get(col_map["jurisdiction_name"])) if col_map["jurisdiction_name"] else None,
            _coerce_date(row.get(col_map["election_date"])) if col_map["election_date"] else None,
            _coerce_int(row.get(col_map["election_year"])) if col_map["election_year"] else None,
            _coerce_str(row.get(col_map["outcome"])) if col_map["outcome"] else None,
            _coerce_int(row.get(col_map["yes_count"])) if col_map["yes_count"] else None,
            _coerce_int(row.get(col_map["no_count"])) if col_map["no_count"] else None,
            _coerce_float(row.get(col_map["yes_percent"])) if col_map["yes_percent"] else None,
            _coerce_str(row.get(col_map["source_url"])) if col_map["source_url"] else None,
            Json(raw_row),
            str(csv_path),
        ))
    return records, source_rows


def load(records: list[tuple], *, dry_run: bool, truncate: bool,
         expected_count: int) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()

    cur.execute(CREATE_TABLE_SQL)
    conn.commit()

    if truncate:
        cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
        before = cur.fetchone()[0]
        cur.execute(f"TRUNCATE TABLE {TABLE} RESTART IDENTITY")
        conn.commit()
        logger.info("Truncated {} ({:,} rows removed)", TABLE, before)

    if dry_run:
        logger.warning("DRY RUN — showing first 3 records, not writing:")
        for r in records[:3]:
            logger.info("  {}", r[:8])
        cur.close()
        conn.close()
        return 0

    execute_batch(cur, INSERT_SQL, records, page_size=2_000)
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
    total = cur.fetchone()[0]
    logger.success("Inserted {:,} rows → {} (table total: {:,})",
                   len(records), TABLE, total)

    delta = total - expected_count
    status = "OK" if delta == 0 else ("UNDER" if delta < 0 else "OVER")
    logger.info("Count check [{}]: table={:,}, expected={:,}, Δ={:+}",
                status, total, expected_count, delta)
    if delta != 0:
        logger.error("Row count mismatch. If --truncate was not used, stale rows from "
                     "prior loads may inflate the total. Otherwise the scraper missed "
                     "(or over-collected) rows — re-run the downloader with --headed.")

    cur.execute(f"""
        SELECT state_code, COUNT(*) AS cnt
        FROM {TABLE}
        WHERE state_code IS NOT NULL
        GROUP BY state_code ORDER BY cnt DESC LIMIT 10
    """)
    breakdown = cur.fetchall()
    if breakdown:
        logger.info("Top states by row count:")
        for sc, cnt in breakdown:
            logger.info("  {}: {:,}", sc, cnt)

    cur.close()
    conn.close()
    return total


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", type=Path, help="CSV path (default: latest in data/cache/powerbi_ballot_measures/)")
    parser.add_argument("--limit", type=int, help="Limit rows (testing)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE table before loading")
    parser.add_argument("--expected-count", type=int, default=9670,
                        help="Expected post-load row count (headline KPI on source dashboard).")
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Power BI Ballot Measures → {}", TABLE)
    logger.info("=" * 70)

    csv_path = args.file or find_latest_csv()
    records, source_rows = parse_csv(csv_path, limit=args.limit)
    logger.info("Prepared {:,} records (source had {:,})", len(records), source_rows)

    total = load(records, dry_run=args.dry_run, truncate=args.truncate,
                 expected_count=args.expected_count)

    if args.dry_run:
        return 0
    return 0 if total == args.expected_count else 2


if __name__ == "__main__":
    sys.exit(main())
