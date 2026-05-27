#!/usr/bin/env python3
"""Power BI ballot-measures pipeline: load cached CSV into bronze.bronze_ballot_measures_powerbi.

Ported from load_powerbi_ballot_measures_to_bronze.py to the core_lib
DataSourcePipeline contract.

Reads the CSV produced by ``download_powerbi_ballot_measures.py``, maps a
best-effort set of columns into the denormalized bronze columns, resolves
``state_code``, ``jurisdiction_id``, and ``ocd_id`` from
``intermediate.int_jurisdictions`` (state rows), stores the full row as JSONB
in ``raw_row``, and verifies the post-load count against ``--expected-count``
(default 9670 — the headline KPI on the source dashboard).

Usage:
    python -m scripts.datasources.powerbi_ballot_measures.ballot_measures_pipeline
    python scripts/datasources/powerbi_ballot_measures/ballot_measures_pipeline.py --truncate
    python scripts/datasources/powerbi_ballot_measures/ballot_measures_pipeline.py --backfill
    python scripts/datasources/powerbi_ballot_measures/ballot_measures_pipeline.py \\
        --file data/cache/ncls/ballot_measures_20260524T200000Z.csv \\
        --expected-count 9670

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator

import pandas as pd
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

CACHE_DIR = _ROOT / "data" / "cache" / "ncls"

TABLE = "bronze.bronze_ballot_measures_powerbi"

# Heuristic column-name → bronze-column mapping. Lowercased & non-alphanumeric
# stripped before matching so "Measure Title", "measure_title", and
# "MeasureTitle" all collapse to the same key.
_NORMALIZE_RE = re.compile(r"[^a-z0-9]+")


# --- DDL (each statement as a SEPARATE text(); never multiple per text()) ----

_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
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
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bbmp_state        ON bronze.bronze_ballot_measures_powerbi (state_code)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmp_jurisdiction ON bronze.bronze_ballot_measures_powerbi (jurisdiction_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmp_ocd_id       ON bronze.bronze_ballot_measures_powerbi (ocd_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmp_year         ON bronze.bronze_ballot_measures_powerbi (election_year)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmp_date         ON bronze.bronze_ballot_measures_powerbi (election_date)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmp_batch        ON bronze.bronze_ballot_measures_powerbi (scrape_batch_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmp_outcome      ON bronze.bronze_ballot_measures_powerbi (outcome)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_ballot_measures_powerbi RESTART IDENTITY")

# Plain append-insert: the source table has a BIGSERIAL surrogate PK and no
# natural unique key, so there is no ON CONFLICT target (matches the original
# loader's append semantics; use --truncate for full reloads).
_INSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_ballot_measures_powerbi (
        scrape_batch_id, measure_id, measure_title, measure_summary, measure_type,
        state_code, state, jurisdiction_id, ocd_id, jurisdiction_name,
        election_date, election_year,
        outcome, yes_count, no_count, yes_percent, source_url, raw_row, source_csv_path
    ) VALUES (
        :scrape_batch_id, :measure_id, :measure_title, :measure_summary, :measure_type,
        :state_code, :state, :jurisdiction_id, :ocd_id, :jurisdiction_name,
        :election_date, :election_year,
        :outcome, :yes_count, :no_count, :yes_percent, :source_url,
        CAST(:raw_row AS JSONB), :source_csv_path
    )
    """
)

_BACKFILL_SQL = text(
    """
    UPDATE bronze.bronze_ballot_measures_powerbi
    SET state_code = :state_code,
        jurisdiction_id = :jurisdiction_id,
        ocd_id = :ocd_id
    WHERE id = :id
    """
)

_STATE_INDEX_SQL = text(
    """
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
)


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


def _build_state_index(rows: list[tuple]) -> dict[str, StateJurisdiction]:
    """Build the lookup index from raw int_jurisdictions rows.

    Keys: upper state_code and lowercased state / jurisdiction display names.
    """
    by_key: dict[str, StateJurisdiction] = {}
    for state_code, state_name, jurisdiction_name, jurisdiction_id, open_states_id in rows:
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
    return by_key


async def load_state_jurisdiction_index(session: AsyncSession) -> dict[str, StateJurisdiction]:
    """Load the state lookup index from intermediate.int_jurisdictions."""
    result = await session.execute(_STATE_INDEX_SQL)
    by_key = _build_state_index(list(result.fetchall()))
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


class BallotMeasureRow(RawRow):
    """One Power BI ballot-measure row, validated before insert."""

    scrape_batch_id: str
    measure_id: str | None = None
    measure_title: str | None = None
    measure_summary: str | None = None
    measure_type: str | None = None
    state_code: str | None = Field(default=None, max_length=2)
    state: str | None = None
    jurisdiction_id: str | None = None
    ocd_id: str | None = None
    jurisdiction_name: str | None = None
    election_date: str | None = None
    election_year: str | None = Field(default=None, max_length=4)
    outcome: str | None = None
    yes_count: int | None = None
    no_count: int | None = None
    yes_percent: float | None = None
    source_url: str | None = None
    raw_row: dict[str, Any] = Field(default_factory=dict)
    source_csv_path: str | None = None


class PowerbiBallotMeasuresPipeline(DataSourcePipeline[BallotMeasureRow]):
    source = "powerbi_ballot_measures"
    batch_size = 2_000
    row_schema = BallotMeasureRow

    def __init__(self, *, path: Path | None = None, limit: int | None = None):
        self._path = path
        self._limit = limit

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._path or find_latest_csv()
        async with async_session() as session:
            state_index = await load_state_jurisdiction_index(session)

        batch_id = str(uuid.uuid4())
        logger.info("Reading {}", path)
        logger.info("scrape_batch_id = {}", batch_id)

        df = pd.read_csv(path, dtype=str, low_memory=False, keep_default_na=False)
        df = df.replace({"": None})
        source_rows = len(df)
        logger.info("CSV: {:,} rows × {} cols. Columns: {}",
                    source_rows, len(df.columns), list(df.columns))

        if self._limit:
            df = df.head(self._limit)

        col_map = _build_column_map(list(df.columns))
        logger.info("Column mapping → bronze:")
        for bronze_col, csv_col in col_map.items():
            logger.info("  {:<18} ← {}", bronze_col, csv_col or "(no match)")

        unresolved_states = 0
        for idx, row in df.iterrows():
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
                ocd_id = _ocd_id_for_state(state_code, None) if state_code else None
                state_label = state_name

            yield {
                "source": self.source,
                "source_version": batch_id,
                "natural_key": f"{batch_id}:{idx}",
                "scrape_batch_id": batch_id,
                "measure_id": _coerce_str(row.get(col_map["measure_id"])) if col_map["measure_id"] else None,
                "measure_title": _coerce_str(row.get(col_map["measure_title"])) if col_map["measure_title"] else None,
                "measure_summary": _coerce_str(row.get(col_map["measure_summary"])) if col_map["measure_summary"] else None,
                "measure_type": _coerce_str(row.get(col_map["measure_type"])) if col_map["measure_type"] else None,
                "state_code": state_code,
                "state": state_label,
                "jurisdiction_id": jurisdiction_id,
                "ocd_id": ocd_id,
                "jurisdiction_name": _coerce_str(row.get(col_map["jurisdiction_name"])) if col_map["jurisdiction_name"] else None,
                "election_date": _coerce_date(row.get(col_map["election_date"])) if col_map["election_date"] else None,
                "election_year": _coerce_year(row.get(col_map["election_year"])) if col_map["election_year"] else None,
                "outcome": _coerce_str(row.get(col_map["outcome"])) if col_map["outcome"] else None,
                "yes_count": _coerce_int(row.get(col_map["yes_count"])) if col_map["yes_count"] else None,
                "no_count": _coerce_int(row.get(col_map["no_count"])) if col_map["no_count"] else None,
                "yes_percent": _coerce_float(row.get(col_map["yes_percent"])) if col_map["yes_percent"] else None,
                "source_url": _coerce_str(row.get(col_map["source_url"])) if col_map["source_url"] else None,
                "raw_row": raw_row,
                "source_csv_path": str(path),
            }

        if unresolved_states:
            logger.warning(
                "{:,} rows had no int_jurisdictions state match (state_code/jurisdiction_id may be partial)",
                unresolved_states,
            )

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[BallotMeasureRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "scrape_batch_id": r.scrape_batch_id,
                "measure_id": r.measure_id,
                "measure_title": r.measure_title,
                "measure_summary": r.measure_summary,
                "measure_type": r.measure_type,
                "state_code": r.state_code,
                "state": r.state,
                "jurisdiction_id": r.jurisdiction_id,
                "ocd_id": r.ocd_id,
                "jurisdiction_name": r.jurisdiction_name,
                "election_date": r.election_date,
                "election_year": r.election_year,
                "outcome": r.outcome,
                "yes_count": r.yes_count,
                "no_count": r.no_count,
                "yes_percent": r.yes_percent,
                "source_url": r.source_url,
                "raw_row": json.dumps(r.raw_row),
                "source_csv_path": r.source_csv_path,
            }
            for r in rows
        ]
        await session.execute(_INSERT_SQL, params)


async def _prepare_target(truncate: bool) -> None:
    async with async_session() as session:
        await session.execute(_CREATE_SCHEMA_SQL)
        await session.execute(_CREATE_TABLE_SQL)
        for idx in _CREATE_INDEXES_SQL:
            await session.execute(idx)
        if truncate:
            await session.execute(_TRUNCATE_SQL)


async def backfill_jurisdictions() -> int:
    """UPDATE existing rows' state_code/jurisdiction_id/ocd_id from int_jurisdictions."""
    await _prepare_target(truncate=False)
    async with async_session() as session:
        state_index = await load_state_jurisdiction_index(session)
        result = await session.execute(
            text(f"SELECT id, state_code, state FROM {TABLE} ORDER BY id")
        )
        rows = list(result.fetchall())
        if not rows:
            logger.warning("No rows in {} — nothing to backfill", TABLE)
            return 0

        updates: list[dict] = []
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
            updates.append({
                "state_code": resolved.state_code,
                "jurisdiction_id": resolved.jurisdiction_id,
                "ocd_id": resolved.ocd_id,
                "id": row_id,
            })

        logger.info(
            "Backfill: {:,} rows in table, {:,} to update, {:,} unresolved",
            len(rows), len(updates), unchanged,
        )
        if updates:
            await session.execute(_BACKFILL_SQL, updates)

        count_result = await session.execute(text(f"""
            SELECT COUNT(*) FILTER (WHERE jurisdiction_id IS NOT NULL),
                   COUNT(*) FILTER (WHERE ocd_id IS NOT NULL),
                   COUNT(*) FILTER (WHERE state_code IS NOT NULL)
            FROM {TABLE}
        """))
        with_jur, with_ocd, with_sc = count_result.fetchone()
    logger.success(
        "Backfill complete: jurisdiction_id={:,}, ocd_id={:,}, state_code={:,} / {:,} rows",
        with_jur, with_ocd, with_sc, len(rows),
    )
    return len(updates)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load cached Power BI ballot-measures CSV into bronze.bronze_ballot_measures_powerbi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--file", type=Path, help="CSV path (default: latest in data/cache/ncls/)")
    parser.add_argument("--limit", type=int, help="Limit rows (testing)")
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
        help="Exit with error if loaded row count is outside +/-5%% of --expected-count.",
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    logger.info("=" * 70)
    logger.info("Power BI Ballot Measures → {}", TABLE)
    logger.info("Cache directory: {}", CACHE_DIR.resolve())
    logger.info("=" * 70)

    if args.backfill:
        await backfill_jurisdictions()
        return 0

    await _prepare_target(args.truncate)
    pipeline = PowerbiBallotMeasuresPipeline(path=args.file, limit=args.limit)
    run = await pipeline.run()

    delta = run.loaded - args.expected_count
    tolerance = max(50, int(args.expected_count * 0.05))
    kpi_status = "OK" if abs(delta) <= tolerance else ("UNDER" if delta < 0 else "OVER")
    logger.info(
        "KPI check [{}]: loaded={:,}, dashboard KPI={:,}, Δ={:+} (tolerance ±{:,}). "
        "The table visual often has more rows than the KPI card (multiple topics per measure).",
        kpi_status, run.loaded, args.expected_count, delta, tolerance,
    )

    if args.strict_kpi and abs(delta) > tolerance:
        return 2
    return 0


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
