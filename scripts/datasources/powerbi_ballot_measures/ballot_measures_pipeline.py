#!/usr/bin/env python3
"""
Load a scraped Power BI ballot-measures CSV into ``bronze.bronze_ballot_measures_powerbi``.

Reads the CSV produced by ``download_powerbi_ballot_measures.py``, maps a
best-effort set of columns into the denormalized bronze columns, resolves
``state_code``, ``jurisdiction_id``, and ``ocd_id`` from
``intermediate.int_jurisdictions`` (state rows), stores the full row as JSONB
in ``raw_row``, and verifies the post-load count against ``--expected-count``
(default 9670 — the headline KPI on the source dashboard).

Usage
-----
    python scripts/datasources/powerbi_ballot_measures/load_powerbi_ballot_measures_to_bronze.py
    python scripts/datasources/powerbi_ballot_measures/load_powerbi_ballot_measures_to_bronze.py --truncate
    python scripts/datasources/powerbi_ballot_measures/load_powerbi_ballot_measures_to_bronze.py --backfill
    python scripts/datasources/powerbi_ballot_measures/load_powerbi_ballot_measures_to_bronze.py \\
        --file data/cache/ncls/ballot_measures_20260524T200000Z.csv \\
        --expected-count 9670
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import uuid
from dataclasses import dataclass
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

CACHE_DIR = _ROOT / "data" / "cache" / "ncls"
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
        jurisdiction_id     TEXT,
        ocd_id              TEXT,
        jurisdiction_name   TEXT,
        election_date       DATE,
        election_year       VARCHAR(4),
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
    CREATE INDEX IF NOT EXISTS idx_bbmp_jurisdiction ON bronze.bronze_ballot_measures_powerbi (jurisdiction_id);
    CREATE INDEX IF NOT EXISTS idx_bbmp_ocd_id   ON bronze.bronze_ballot_measures_powerbi (ocd_id);
    CREATE INDEX IF NOT EXISTS idx_bbmp_year     ON bronze.bronze_ballot_measures_powerbi (election_year);
    CREATE INDEX IF NOT EXISTS idx_bbmp_date     ON bronze.bronze_ballot_measures_powerbi (election_date);
    CREATE INDEX IF NOT EXISTS idx_bbmp_batch    ON bronze.bronze_ballot_measures_powerbi (scrape_batch_id);
    CREATE INDEX IF NOT EXISTS idx_bbmp_outcome  ON bronze.bronze_ballot_measures_powerbi (outcome);
"""

INSERT_SQL = """
    INSERT INTO bronze.bronze_ballot_measures_powerbi (
        scrape_batch_id, measure_id, measure_title, measure_summary, measure_type,
        state_code, state, jurisdiction_id, ocd_id, jurisdiction_name,
        election_date, election_year,
        outcome, yes_count, no_count, yes_percent, source_url, raw_row, source_csv_path
    ) VALUES (
        %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s,
        %s, %s,
        %s, %s, %s, %s, %s, %s, %s
    )
"""

BACKFILL_SQL = """
    UPDATE bronze.bronze_ballot_measures_powerbi
    SET state_code = %s,
        jurisdiction_id = %s,
        ocd_id = %s
    WHERE id = %s
"""

STATE_INDEX_SQL = """
    SELECT
        UPPER(TRIM(state_code)) AS state_code,
        TRIM(state) AS state_name,
        TRIM(name) AS jurisdiction_name,
        jurisdiction_id,
        open_states_jurisdiction_id
    FROM intermediate.int_jurisdictions
    WHERE jurisdiction_type = 'state'
      AND state_code IS NOT NULL
      AND BTRIM(state_code) <> ''
"""

# Heuristic column-name → bronze-column mapping. Lowercased & non-alphanumeric
# stripped before matching so "Measure Title", "measure_title", and
# "MeasureTitle" all collapse to the same key.
_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class StateJurisdiction:
    state_code: str
    state_name: str
    jurisdiction_id: str
    ocd_id: str


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


def _coerce_year(val: Any) -> str | None:
    """Calendar year label as four-digit string."""
    if val is None or val == "" or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    if not s:
        return None
    m = re.search(r"\b(19|20)\d{2}\b", s)
    if m:
        return m.group(0)
    n = _coerce_int(val)
    if n is not None and 1900 <= n <= 2100:
        return str(n)
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


def _state_code_from_name(state: str | None) -> str | None:
    if not state:
        return None
    s = state.strip()
    if len(s) == 2 and s.isalpha():
        return s.upper()
    from scripts.datasources.ballotpedia.ballotpedia_integration import BallotpediaDiscovery
    for code, name in BallotpediaDiscovery.STATE_NAME_BY_CODE.items():
        if name.lower() == s.lower():
            return code
    return None


def _ocd_id_for_state(state_code: str, open_states_jurisdiction_id: str | None) -> str:
    if open_states_jurisdiction_id and open_states_jurisdiction_id.startswith("ocd-division/"):
        return open_states_jurisdiction_id
    return f"ocd-division/country:us/state:{state_code.lower()}"


def load_state_jurisdiction_index(conn) -> dict[str, StateJurisdiction]:
    """Keys: upper state_code and lowercased state / jurisdiction display names."""
    by_key: dict[str, StateJurisdiction] = {}
    cur = conn.cursor()
    cur.execute(STATE_INDEX_SQL)
    for state_code, state_name, jurisdiction_name, jurisdiction_id, open_states_id in cur.fetchall():
        if not state_code or not jurisdiction_id:
            continue
        entry = StateJurisdiction(
            state_code=state_code,
            state_name=state_name or jurisdiction_name or state_code,
            jurisdiction_id=jurisdiction_id,
            ocd_id=_ocd_id_for_state(state_code, open_states_id),
        )
        by_key[state_code.upper()] = entry
        for label in (state_name, jurisdiction_name):
            if label:
                by_key[label.strip().lower()] = entry
    cur.close()
    logger.info("State jurisdiction index: {:,} lookup keys from int_jurisdictions", len(by_key))
    return by_key


def resolve_state_jurisdiction(
    index: dict[str, StateJurisdiction],
    *,
    state_code_hint: str | None,
    state_name_hint: str | None,
) -> StateJurisdiction | None:
    code = None
    if state_code_hint:
        c = state_code_hint.strip().upper()
        if len(c) == 2 and c.isalpha():
            code = c
    if code and code in index:
        return index[code]
    for hint in (state_name_hint, state_code_hint):
        if not hint:
            continue
        hit = index.get(hint.strip().lower())
        if hit:
            return hit
    inferred = _state_code_from_name(state_name_hint) or _state_code_from_name(state_code_hint)
    if inferred:
        return index.get(inferred.upper())
    return None


def find_latest_csv() -> Path:
    csvs = sorted(CACHE_DIR.glob("ballot_measures_*.csv"), reverse=True)
    if not csvs:
        raise FileNotFoundError(
            f"No CSV found in {CACHE_DIR}. Run download_powerbi_ballot_measures.py first."
        )
    return csvs[0]


def parse_csv(
    csv_path: Path,
    limit: int | None,
    state_index: dict[str, StateJurisdiction],
) -> tuple[list[tuple], int]:
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
    unresolved_states = 0
    for _, row in df.iterrows():
        raw_row = {k: (None if v is None else str(v)) for k, v in row.to_dict().items()}
        state_name = _coerce_str(row.get(col_map["state"])) if col_map["state"] else None
        state_code_csv = (
            _coerce_str(row.get(col_map["state_code"]), maxlen=2) if col_map["state_code"] else None
        )
        resolved = resolve_state_jurisdiction(
            state_index,
            state_code_hint=state_code_csv,
            state_name_hint=state_name,
        )
        if resolved:
            state_code = resolved.state_code
            jurisdiction_id = resolved.jurisdiction_id
            ocd_id = resolved.ocd_id
            state_label = state_name or resolved.state_name
        else:
            unresolved_states += 1
            state_code = state_code_csv or _state_code_from_name(state_name)
            jurisdiction_id = None
            ocd_id = (
                _ocd_id_for_state(state_code, None) if state_code else None
            )
            state_label = state_name

        records.append((
            batch_id,
            _coerce_str(row.get(col_map["measure_id"])) if col_map["measure_id"] else None,
            _coerce_str(row.get(col_map["measure_title"])) if col_map["measure_title"] else None,
            _coerce_str(row.get(col_map["measure_summary"])) if col_map["measure_summary"] else None,
            _coerce_str(row.get(col_map["measure_type"])) if col_map["measure_type"] else None,
            state_code,
            state_label,
            jurisdiction_id,
            ocd_id,
            _coerce_str(row.get(col_map["jurisdiction_name"])) if col_map["jurisdiction_name"] else None,
            _coerce_date(row.get(col_map["election_date"])) if col_map["election_date"] else None,
            _coerce_year(row.get(col_map["election_year"])) if col_map["election_year"] else None,
            _coerce_str(row.get(col_map["outcome"])) if col_map["outcome"] else None,
            _coerce_int(row.get(col_map["yes_count"])) if col_map["yes_count"] else None,
            _coerce_int(row.get(col_map["no_count"])) if col_map["no_count"] else None,
            _coerce_float(row.get(col_map["yes_percent"])) if col_map["yes_percent"] else None,
            _coerce_str(row.get(col_map["source_url"])) if col_map["source_url"] else None,
            Json(raw_row),
            str(csv_path),
        ))
    if unresolved_states:
        logger.warning(
            "{:,} rows had no int_jurisdictions state match (state_code/jurisdiction_id may be partial)",
            unresolved_states,
        )
    return records, source_rows


def backfill_jurisdictions(*, dry_run: bool) -> int:
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute(CREATE_TABLE_SQL)
    conn.commit()

    state_index = load_state_jurisdiction_index(conn)
    cur.execute(f"SELECT id, state_code, state FROM {TABLE} ORDER BY id")
    rows = cur.fetchall()
    if not rows:
        logger.warning("No rows in {} — nothing to backfill", TABLE)
        cur.close()
        conn.close()
        return 0

    updates: list[tuple] = []
    unchanged = 0
    for row_id, state_code, state_name in rows:
        resolved = resolve_state_jurisdiction(
            state_index,
            state_code_hint=state_code,
            state_name_hint=state_name,
        )
        if not resolved:
            unchanged += 1
            continue
        updates.append((
            resolved.state_code,
            resolved.jurisdiction_id,
            resolved.ocd_id,
            row_id,
        ))

    logger.info(
        "Backfill: {:,} rows in table, {:,} to update, {:,} unresolved",
        len(rows), len(updates), unchanged,
    )
    if dry_run:
        for u in updates[:5]:
            logger.info("  sample update: state_code={} jurisdiction_id={} id={}", u[0], u[1], u[3])
        cur.close()
        conn.close()
        return len(updates)

    execute_batch(cur, BACKFILL_SQL, updates, page_size=2_000)
    conn.commit()

    cur.execute(f"""
        SELECT COUNT(*) FILTER (WHERE jurisdiction_id IS NOT NULL),
               COUNT(*) FILTER (WHERE ocd_id IS NOT NULL),
               COUNT(*) FILTER (WHERE state_code IS NOT NULL)
        FROM {TABLE}
    """)
    with_jur, with_ocd, with_sc = cur.fetchone()
    logger.success(
        "Backfill complete: jurisdiction_id={:,}, ocd_id={:,}, state_code={:,} / {:,} rows",
        with_jur, with_ocd, with_sc, len(rows),
    )
    cur.close()
    conn.close()
    return len(updates)


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
            logger.info("  {}", r[:10])
        cur.close()
        conn.close()
        return 0

    execute_batch(cur, INSERT_SQL, records, page_size=2_000)
    conn.commit()

    cur.execute(f"SELECT COUNT(*) FROM {TABLE}")
    total = cur.fetchone()[0]
    logger.success("Inserted {:,} rows → {} (table total: {:,})",
                   len(records), TABLE, total)

    if total != len(records):
        logger.error(
            "Insert mismatch: prepared {:,} CSV rows but table has {:,}. "
            "Re-run with --truncate if stale rows are inflating the total.",
            len(records), total,
        )

    delta = total - expected_count
    tolerance = max(50, int(expected_count * 0.05))
    kpi_status = "OK" if abs(delta) <= tolerance else ("UNDER" if delta < 0 else "OVER")
    logger.info(
        "KPI check [{}]: table={:,}, dashboard KPI={:,}, Δ={:+} (tolerance ±{:,}). "
        "The table visual often has more rows than the KPI card (multiple topics per measure).",
        kpi_status, total, expected_count, delta, tolerance,
    )
    if abs(delta) > tolerance:
        logger.warning(
            "Row count differs from dashboard KPI — this is common for the paginated table scrape. "
            "Bronze load is still valid if the insert count matches the CSV."
        )

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
    parser.add_argument("--file", type=Path, help="CSV path (default: latest in data/cache/ncls/)")
    parser.add_argument("--limit", type=int, help="Limit rows (testing)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--truncate", action="store_true", help="TRUNCATE table before loading")
    parser.add_argument(
        "--backfill",
        action="store_true",
        help="UPDATE existing rows: state_code, jurisdiction_id, ocd_id from int_jurisdictions (no CSV load).",
    )
    parser.add_argument("--expected-count", type=int, default=9670,
                        help="Dashboard KPI card count for logging (default 9670).")
    parser.add_argument(
        "--strict-kpi",
        action="store_true",
        help="Exit with error if table row count is outside ±5%% of --expected-count.",
    )
    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info("Power BI Ballot Measures → {}", TABLE)
    logger.info("Cache directory: {}", CACHE_DIR.resolve())
    logger.info("=" * 70)

    if args.backfill:
        updated = backfill_jurisdictions(dry_run=args.dry_run)
        return 0 if updated or args.dry_run else 0

    conn = psycopg2.connect(DATABASE_URL)
    state_index = load_state_jurisdiction_index(conn)
    conn.close()

    csv_path = args.file or find_latest_csv()
    logger.info("Source CSV: {}", csv_path.resolve())
    records, source_rows = parse_csv(csv_path, limit=args.limit, state_index=state_index)
    logger.info("Prepared {:,} records (source had {:,})", len(records), source_rows)

    total = load(records, dry_run=args.dry_run, truncate=args.truncate,
                 expected_count=args.expected_count)

    if args.dry_run:
        return 0
    if total != len(records):
        return 2
    if args.strict_kpi:
        tolerance = max(50, int(args.expected_count * 0.05))
        if abs(total - args.expected_count) > tolerance:
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
