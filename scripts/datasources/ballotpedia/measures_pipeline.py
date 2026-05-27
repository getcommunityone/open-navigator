#!/usr/bin/env python3
"""Ballotpedia ballot-measure pipeline: load cached JSON snapshots into bronze.

Ported from load_ballotpedia_measures_to_bronze.py to the core_lib
DataSourcePipeline contract.

Reads timestamped JSON files produced by ``download_ballotpedia_measures.py``
(and compatible snapshots written by the Google Civic loader path), maps fields
into the NIST-aligned bronze columns, resolves ``ocd_division_id`` via the OCD
crosswalk, and stores the full measure dict in ``raw_row``. The target table
``bronze.bronze_ballot_measures_ballotpedia`` is append-only (BIGSERIAL PK); each
run gets a fresh ``scrape_batch_id``.

By default only measures with ``election_year`` in **2025** or **2026** are loaded.

Usage:
    python -m scripts.datasources.ballotpedia.measures_pipeline
    python scripts/datasources/ballotpedia/measures_pipeline.py --truncate
    python scripts/datasources/ballotpedia/measures_pipeline.py \\
        --years 2025,2026 --cache-dir data/cache/ballotpedia --limit 10

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db
    (replaces hardcoded postgresql://postgres:password@localhost:5433).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/ballotpedia")
DEFAULT_ELECTION_YEARS = ("2025", "2026")

_UUID_NS = uuid.UUID("b1ed9a39-f6a5-44f7-8e4b-5e0f58d4c0da")

_PASSED_RE = re.compile(r"\b(?:pass(?:ed|es|ing)?|approv(?:ed|es|al)|adopt(?:ed|s)?|yes)\b", re.I)
_FAILED_RE = re.compile(r"\b(?:fail(?:ed|s|ure)?|defeat(?:ed|s)?|reject(?:ed|s)?|no)\b", re.I)
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_VOTE_PAIR_RE = re.compile(
    r"(?P<yes>\d[\d,]*)\s*(?:yes|for|in favor)[^\d]{0,40}(?P<no>\d[\d,]*)\s*(?:no|against)",
    re.I,
)
_CACHE_DEDUPE_RE = re.compile(r"^(?P<prefix>.+_ballot_measures(?:_\d{4})?)_\d{8}T", re.I)


# --------------------------------------------------------------------------- #
# Pure helpers (preserved verbatim from the original loader)
# --------------------------------------------------------------------------- #
def _parse_years(raw: str | None) -> frozenset[str]:
    if not raw or not raw.strip():
        return frozenset(DEFAULT_ELECTION_YEARS)
    years = frozenset(y.strip() for y in raw.split(",") if y.strip())
    return years or frozenset(DEFAULT_ELECTION_YEARS)


def _cache_dedupe_key(path: Path) -> str:
    """One newest snapshot per state/jurisdiction + election year label."""
    m = _CACHE_DEDUPE_RE.match(path.name)
    prefix = m.group("prefix") if m else path.stem
    return str(path.parent / prefix)


def _stable_id(prefix: str, key: str) -> str:
    return f"ocd-{prefix}/{uuid.uuid5(_UUID_NS, key)}"


def _stable_key(*parts: str | None) -> str:
    return "|".join((p or "").strip().lower() for p in parts)


def _parse_int(val: Any) -> int | None:
    if val is None:
        return None
    try:
        s = str(val).replace(",", "").strip()
        return int(float(s)) if s else None
    except (ValueError, TypeError):
        return None


def _parse_passed(outcome: str | None) -> bool | None:
    if not outcome:
        return None
    if _PASSED_RE.search(outcome) and not _FAILED_RE.search(outcome):
        return True
    if _FAILED_RE.search(outcome) and not _PASSED_RE.search(outcome):
        return False
    return None


def _extract_year(text: str | None, explicit: Any = None) -> str | None:
    if explicit is not None and str(explicit).strip():
        m = _YEAR_RE.search(str(explicit))
        if m:
            return m.group(0)
    if text:
        m = _YEAR_RE.search(text)
        if m:
            return m.group(0)
    return None


def _extract_votes(outcome: str | None) -> tuple[int | None, int | None]:
    if not outcome:
        return None, None
    m = _VOTE_PAIR_RE.search(outcome)
    if not m:
        return None, None
    return _parse_int(m.group("yes")), _parse_int(m.group("no"))


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


def _resolve_ocd_division_id(
    *,
    state_code: str | None,
    jurisdiction_name: str | None,
    jurisdiction_type: str | None,
    scope: str | None,
) -> str | None:
    if scope == "state" and state_code:
        return f"ocd-division/country:us/state:{state_code.lower()}"
    if jurisdiction_name and state_code:
        from scripts.datasources.jurisdiction_pilot.load_ocd_jurisdictions import find_ocd_match
        return find_ocd_match(jurisdiction_name, state_code, jurisdiction_type=jurisdiction_type)
    if state_code:
        return f"ocd-division/country:us/state:{state_code.lower()}"
    return None


def _normalize_measure(
    measure: dict[str, Any],
    *,
    envelope: dict[str, Any],
    source_path: Path,
) -> dict[str, Any] | None:
    title = (
        measure.get("measure_title")
        or measure.get("measure_name")
        or measure.get("title")
        or ""
    ).strip()
    if not title:
        return None

    state_code = (
        envelope.get("state_code")
        or _state_code_from_name(measure.get("state"))
        or _state_code_from_name(envelope.get("state"))
    )
    jurisdiction_id = envelope.get("jurisdiction_id") or measure.get("jurisdiction_id")
    jurisdiction_name = measure.get("jurisdiction") or envelope.get("jurisdiction_name")
    jurisdiction_type = envelope.get("jurisdiction_type") or measure.get("jurisdiction_type")
    scope = envelope.get("scope") or measure.get("scope")

    outcome = measure.get("measure_outcome") or measure.get("status")
    yes_votes = _parse_int(measure.get("yes_votes"))
    no_votes = _parse_int(measure.get("no_votes"))
    if yes_votes is None and no_votes is None:
        yes_votes, no_votes = _extract_votes(outcome)

    election_year = _extract_year(title, envelope.get("election_year") or measure.get("year"))

    ocd_division_id = measure.get("ocd_division_id") or _resolve_ocd_division_id(
        state_code=state_code,
        jurisdiction_name=jurisdiction_name if scope != "state" else None,
        jurisdiction_type=jurisdiction_type,
        scope=scope,
    )

    measure_id = measure.get("measure_id") or _stable_id(
        "ballotmeasure",
        _stable_key(
            "ballotpedia",
            state_code,
            jurisdiction_id,
            title,
            election_year,
            measure.get("measure_url"),
            outcome,
        ),
    )

    scraped_raw = measure.get("scraped_at") or envelope.get("scraped_at")
    scraped_at = None
    if scraped_raw:
        try:
            scraped_at = datetime.fromisoformat(str(scraped_raw).replace("Z", "+00:00"))
        except ValueError:
            scraped_at = None

    return {
        "measure_id": measure_id,
        "ocd_division_id": ocd_division_id,
        "state_code": state_code,
        "jurisdiction_id": jurisdiction_id,
        "jurisdiction_name": jurisdiction_name,
        "jurisdiction_type": jurisdiction_type,
        "election_date": measure.get("election_date"),
        "election_year": election_year,
        "measure_number": measure.get("measure_number") or measure.get("number"),
        "measure_title": title,
        "full_text": measure.get("full_text"),
        "summary_text": measure.get("summary_text") or measure.get("measure_summary"),
        "measure_type": measure.get("measure_type") or measure.get("type"),
        "subject_areas": measure.get("subject_areas"),
        "yes_votes": yes_votes,
        "no_votes": no_votes,
        "passed": measure.get("passed") if measure.get("passed") is not None else _parse_passed(outcome),
        "source_url": measure.get("source_url") or envelope.get("source_url"),
        "measure_page_url": measure.get("measure_url") or measure.get("measure_page_url"),
        "raw_row": measure,
        "source_json_path": str(source_path),
        "scraped_at": scraped_at,
    }


def _load_json(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return {}, data
    measures = data.get("measures") or data.get("ballot_measures") or []
    if not measures and isinstance(data.get("measure_title"), str):
        measures = [data]
    return data if isinstance(data, dict) else {}, measures


def find_latest_cache_files(cache_dir: Path) -> list[Path]:
    """Discover newest ballot-measure JSON snapshots, de-duped per prefix.

    Raises FileNotFoundError when no matching snapshots exist (mirrors the
    original loader's parse_cache guard).
    """
    patterns = ("*_ballot_measures_*.json", "*_ballot_measures.json")
    skip_dirs = {"fetch_debug", "playwright_debug"}
    files: list[Path] = []
    for pat in patterns:
        for path in cache_dir.rglob(pat):
            if any(part in skip_dirs for part in path.parts):
                continue
            files.append(path)
    # De-dupe and prefer newest per directory prefix
    seen: set[str] = set()
    ordered: list[Path] = []
    for path in sorted(files, key=lambda p: p.stat().st_mtime, reverse=True):
        key = _cache_dedupe_key(path)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(path)
    if not ordered:
        raise FileNotFoundError(
            f"No ballot-measures JSON under {cache_dir}. "
            "Run download_ballotpedia_measures.py first."
        )
    return sorted(ordered, key=lambda p: p.stat().st_mtime)


# --------------------------------------------------------------------------- #
# Row schema
# --------------------------------------------------------------------------- #
class BallotMeasureRow(RawRow):
    """One Ballotpedia ballot measure, validated before insert."""

    scrape_batch_id: str
    measure_id: str = Field(min_length=1)
    ocd_division_id: str | None = None
    state_code: str | None = Field(default=None, max_length=2)
    jurisdiction_id: str | None = None
    jurisdiction_name: str | None = None
    jurisdiction_type: str | None = None
    election_date: str | None = None
    election_year: str | None = Field(default=None, max_length=4)
    measure_number: str | None = None
    measure_title: str = Field(min_length=1)
    full_text: str | None = None
    summary_text: str | None = None
    measure_type: str | None = None
    subject_areas: str | None = None
    yes_votes: int | None = None
    no_votes: int | None = None
    passed: bool | None = None
    source_url: str | None = None
    measure_page_url: str | None = None
    raw_row: dict[str, Any] = Field(default_factory=dict)
    source_json_path: str | None = None
    scraped_at: datetime | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_ballot_measures_ballotpedia (
        id                  BIGSERIAL PRIMARY KEY,
        scrape_batch_id     UUID NOT NULL,
        measure_id          TEXT NOT NULL,
        ocd_division_id     TEXT,
        state_code          CHAR(2),
        jurisdiction_id     TEXT,
        jurisdiction_name   TEXT,
        jurisdiction_type   TEXT,
        election_date       DATE,
        election_year       VARCHAR(4),
        measure_number      TEXT,
        measure_title       TEXT NOT NULL,
        full_text           TEXT,
        summary_text        TEXT,
        measure_type        TEXT,
        subject_areas       TEXT,
        yes_votes           BIGINT,
        no_votes            BIGINT,
        passed              BOOLEAN,
        source_url          TEXT,
        measure_page_url    TEXT,
        raw_row             JSONB NOT NULL DEFAULT '{}'::JSONB,
        source_json_path    TEXT,
        scraped_at          TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
        loaded_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bbmb_ocd   ON bronze.bronze_ballot_measures_ballotpedia (ocd_division_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmb_state ON bronze.bronze_ballot_measures_ballotpedia (state_code)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmb_jur   ON bronze.bronze_ballot_measures_ballotpedia (jurisdiction_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmb_date  ON bronze.bronze_ballot_measures_ballotpedia (election_date)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmb_year  ON bronze.bronze_ballot_measures_ballotpedia (election_year)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmb_batch ON bronze.bronze_ballot_measures_ballotpedia (scrape_batch_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmb_mid   ON bronze.bronze_ballot_measures_ballotpedia (measure_id)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_ballot_measures_ballotpedia RESTART IDENTITY")

_INSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_ballot_measures_ballotpedia (
        scrape_batch_id, measure_id, ocd_division_id,
        state_code, jurisdiction_id, jurisdiction_name, jurisdiction_type,
        election_date, election_year, measure_number,
        measure_title, full_text, summary_text, measure_type, subject_areas,
        yes_votes, no_votes, passed,
        source_url, measure_page_url, raw_row, source_json_path, scraped_at
    ) VALUES (
        :scrape_batch_id, :measure_id, :ocd_division_id,
        :state_code, :jurisdiction_id, :jurisdiction_name, :jurisdiction_type,
        :election_date, :election_year, :measure_number,
        :measure_title, :full_text, :summary_text, :measure_type, :subject_areas,
        :yes_votes, :no_votes, :passed,
        :source_url, :measure_page_url, CAST(:raw_row AS JSONB), :source_json_path, :scraped_at
    )
    """
)


class BallotpediaMeasuresPipeline(DataSourcePipeline[BallotMeasureRow]):
    source = "ballotpedia_measures"
    batch_size = 500
    row_schema = BallotMeasureRow

    def __init__(
        self,
        *,
        path: Path | None = None,
        limit: int | None = None,
        years: frozenset[str] | None = None,
    ):
        self._cache_dir = path
        self._limit = limit
        self._years = years if years is not None else frozenset(DEFAULT_ELECTION_YEARS)
        self._batch_id = str(uuid.uuid4())

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        cache_dir = self._cache_dir or CACHE_DIR
        files = find_latest_cache_files(cache_dir)
        if self._limit:
            files = files[: self._limit]

        for path in files:
            envelope, measures = _load_json(path)
            for measure in measures:
                row = _normalize_measure(measure, envelope=envelope, source_path=path)
                if not row:
                    continue
                if row.get("election_year") not in self._years:
                    continue
                yield {
                    "source": self.source,
                    "source_version": self._batch_id,
                    "natural_key": row["measure_id"],
                    "scrape_batch_id": self._batch_id,
                    **row,
                }

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
                "ocd_division_id": r.ocd_division_id,
                "state_code": r.state_code,
                "jurisdiction_id": r.jurisdiction_id,
                "jurisdiction_name": r.jurisdiction_name,
                "jurisdiction_type": r.jurisdiction_type,
                "election_date": r.election_date,
                "election_year": r.election_year,
                "measure_number": r.measure_number,
                "measure_title": r.measure_title,
                "full_text": r.full_text,
                "summary_text": r.summary_text,
                "measure_type": r.measure_type,
                "subject_areas": r.subject_areas,
                "yes_votes": r.yes_votes,
                "no_votes": r.no_votes,
                "passed": r.passed,
                "source_url": r.source_url,
                "measure_page_url": r.measure_page_url,
                "raw_row": json.dumps(r.raw_row),
                "source_json_path": r.source_json_path,
                "scraped_at": r.scraped_at,
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load cached Ballotpedia ballot-measure JSON into "
        "bronze.bronze_ballot_measures_ballotpedia",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR,
                        help="Directory of cached ballot-measure JSON")
    parser.add_argument(
        "--years",
        default=",".join(DEFAULT_ELECTION_YEARS),
        help=f"Comma-separated election years to load (default: {','.join(DEFAULT_ELECTION_YEARS)})",
    )
    parser.add_argument("--limit", type=int, help="Limit number of cache files to read")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    years = _parse_years(args.years)
    await _prepare_target(args.truncate)
    pipeline = BallotpediaMeasuresPipeline(
        path=args.cache_dir, limit=args.limit, years=years,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
