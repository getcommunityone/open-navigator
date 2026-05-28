#!/usr/bin/env python3
"""Ballotpedia ballot-measure pipeline: land cached JSON snapshots RAW into bronze.

Ported from load_ballotpedia_measures_to_bronze.py to the core_lib
DataSourcePipeline contract, then dbt-slimmed: this loader lands the RAW
measure JSON object plus the bronze keys (scrape_batch_id + measure_id) ONLY.

The derivation that used to live in Python has been moved OUT of this loader and
into dbt (see dbt_project/CONVENTIONS.md):
  * OCD division id + state-code resolution  -> int_ballotpedia__measure_resolved
  * vote / passed / election-year regex parsing + multi-alias coalescing
                                              -> stg_ballotpedia__measure
  * the 2025/2026 election-year filter        -> WHERE in int/mart

This loader keeps cache discovery, the stable natural key (measure_id), and the
CLI/flags. The target table ``bronze.bronze_ballot_measures_ballotpedia`` is
append-only (BIGSERIAL PK); each run gets a fresh ``scrape_batch_id``.

Usage:
    python -m scrapers.ballotpedia.download_ballotpedia_measures  (FETCH); python -m ingestion.ballotpedia.measures  (LAND)
    python -m ingestion.ballotpedia.measures --truncate
    python -m ingestion.ballotpedia.measures \\
        --cache-dir data/cache/ballotpedia --limit 10

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
from pathlib import Path
from typing import Any, AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/ballotpedia")

_UUID_NS = uuid.UUID("b1ed9a39-f6a5-44f7-8e4b-5e0f58d4c0da")

_CACHE_DEDUPE_RE = re.compile(r"^(?P<prefix>.+_ballot_measures(?:_\d{4})?)_\d{8}T", re.I)


# --------------------------------------------------------------------------- #
# Pure helpers
# --------------------------------------------------------------------------- #
def _cache_dedupe_key(path: Path) -> str:
    """One newest snapshot per state/jurisdiction + election year label."""
    m = _CACHE_DEDUPE_RE.match(path.name)
    prefix = m.group("prefix") if m else path.stem
    return str(path.parent / prefix)


def _stable_id(prefix: str, key: str) -> str:
    return f"ocd-{prefix}/{uuid.uuid5(_UUID_NS, key)}"


def _stable_key(*parts: str | None) -> str:
    return "|".join((p or "").strip().lower() for p in parts)


def _title_of(measure: dict[str, Any]) -> str:
    """Best-effort title, used only to gate empty rows and seed the natural key.

    The canonical title coalescing lives in stg_ballotpedia__measure; here we
    only need *a* title to (a) drop title-less rows the way the legacy loader
    did and (b) feed the stable measure_id, so the natural key stays identical.
    """
    return (
        measure.get("measure_title")
        or measure.get("measure_name")
        or measure.get("title")
        or ""
    ).strip()


def _natural_key_for(
    measure: dict[str, Any],
    *,
    envelope: dict[str, Any],
) -> str | None:
    """Return the stable measure_id (natural key) for a raw measure, or None.

    Mirrors the legacy loader's key derivation: an explicit ``measure_id`` wins;
    otherwise a UUIDv5 over (source, state, jurisdiction, title, year, url,
    outcome). The state value is the RAW alias (no name->code resolution — that
    moved to dbt); this keeps the key deterministic and component-aligned with
    the legacy behavior for rows that already carry a 2-letter code, while
    title-less rows are dropped exactly as before.
    """
    title = _title_of(measure)
    if not title:
        return None
    explicit = measure.get("measure_id")
    if explicit:
        return str(explicit)
    state = (
        envelope.get("state_code")
        or measure.get("state")
        or envelope.get("state")
    )
    jurisdiction_id = envelope.get("jurisdiction_id") or measure.get("jurisdiction_id")
    election_year = envelope.get("election_year") or measure.get("year")
    outcome = measure.get("measure_outcome") or measure.get("status")
    return _stable_id(
        "ballotmeasure",
        _stable_key(
            "ballotpedia",
            str(state) if state is not None else None,
            str(jurisdiction_id) if jurisdiction_id is not None else None,
            title,
            str(election_year) if election_year is not None else None,
            measure.get("measure_url"),
            outcome,
        ),
    )


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
# Row schema (RAW shape)
# --------------------------------------------------------------------------- #
class BallotMeasureRow(RawRow):
    """One RAW Ballotpedia ballot measure, validated before insert.

    Slimmed shape: only the bronze keys (scrape_batch_id + measure_id) plus the
    full raw measure JSON object (merged with the file envelope so state/scope/
    jurisdiction context survives). Everything else — title coalescing, vote /
    passed / election-year parsing, state-code + OCD resolution, and the
    election-year filter — is now derived downstream in dbt from ``raw_row``.
    """

    scrape_batch_id: str
    measure_id: str = Field(min_length=1)
    raw_row: dict[str, Any] = Field(default_factory=dict)
    source_json_path: str | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_ballot_measures_ballotpedia (
        id                  BIGSERIAL PRIMARY KEY,
        scrape_batch_id     UUID NOT NULL,
        measure_id          TEXT NOT NULL,
        raw_row             JSONB NOT NULL DEFAULT '{}'::JSONB,
        source_json_path    TEXT,
        loaded_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_CREATE_INDEXES_SQL = (
    text("CREATE INDEX IF NOT EXISTS idx_bbmb_batch ON bronze.bronze_ballot_measures_ballotpedia (scrape_batch_id)"),
    text("CREATE INDEX IF NOT EXISTS idx_bbmb_mid   ON bronze.bronze_ballot_measures_ballotpedia (measure_id)"),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_ballot_measures_ballotpedia RESTART IDENTITY")

_INSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_ballot_measures_ballotpedia (
        scrape_batch_id, measure_id, raw_row, source_json_path
    ) VALUES (
        :scrape_batch_id, :measure_id, CAST(:raw_row AS JSONB), :source_json_path
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
    ):
        self._cache_dir = path
        self._limit = limit
        self._batch_id = str(uuid.uuid4())

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        cache_dir = self._cache_dir or CACHE_DIR
        files = find_latest_cache_files(cache_dir)
        if self._limit:
            files = files[: self._limit]

        for path in files:
            envelope, measures = _load_json(path)
            for measure in measures:
                measure_id = _natural_key_for(measure, envelope=envelope)
                if not measure_id:
                    # No title -> cannot derive a key; dropped as the legacy
                    # loader's _normalize_measure did.
                    continue
                # Land the full raw measure object verbatim, merged with the
                # file-level envelope (state_code / scope / jurisdiction context)
                # so dbt has every field the Python derivation used to read.
                raw_row = {
                    k: v
                    for k, v in envelope.items()
                    if k not in ("measures", "ballot_measures")
                }
                raw_row.update(measure)
                yield {
                    "source": self.source,
                    "source_version": self._batch_id,
                    "natural_key": measure_id,
                    "scrape_batch_id": self._batch_id,
                    "measure_id": measure_id,
                    "raw_row": raw_row,
                    "source_json_path": str(path),
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
                "raw_row": json.dumps(r.raw_row),
                "source_json_path": r.source_json_path,
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
        description="Land cached Ballotpedia ballot-measure JSON RAW into "
        "bronze.bronze_ballot_measures_ballotpedia",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--cache-dir", type=Path, default=CACHE_DIR,
                        help="Directory of cached ballot-measure JSON")
    parser.add_argument("--limit", type=int, help="Limit number of cache files to read")
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE table before loading (recommended for full reloads)",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = BallotpediaMeasuresPipeline(path=args.cache_dir, limit=args.limit)
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
