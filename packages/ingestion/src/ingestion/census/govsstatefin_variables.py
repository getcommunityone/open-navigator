#!/usr/bin/env python3
"""Census ``timeseries/govsstatefin`` variable codebook ingestion.

The Census Bureau publishes a per-dataset variables.json metadata file that
maps every column in the survey to a human label, concept group, predicate
type, and any enumerated values. For the State and Local Government Finance
time series (govsstatefin) that codebook is the dictionary for the ~300
finance variables TPC re-publishes in ``bronze.bronze_jurisdiction_tpc``
— so once both bronze tables are loaded, dbt can join ``raw_record->>key``
to a human-readable label without a separate vendored lookup.

Endpoint (public, no key required, JSON):
  https://api.census.gov/data/timeseries/govsstatefin/variables.json

Pipeline shape (mirrors ingestion.bls.cpi / ingestion.tpc.finance):
  1. FETCH: hit the URL, write the raw payload to
     ``data/cache/census/govsstatefin_variables/<YYYYMMDD_HHMMSS>.json``.
     Each snapshot is kept — never overwritten — so if Census revises the
     codebook later the audit trail of what was in effect at each load
     survives. ``--no-fetch`` reads the newest existing snapshot;
     ``--snapshot <path>`` pins to a specific file.
  2. LAND: melt the nested ``{"variables": {code: meta, ...}}`` blob into
     one ``CensusFinanceVariableRow`` per variable_code; upsert into bronze.

Usage:
    python -m ingestion.census.govsstatefin_variables              # fetch + load
    python -m ingestion.census.govsstatefin_variables --no-fetch   # newest cache
    python -m ingestion.census.govsstatefin_variables --snapshot data/cache/census/govsstatefin_variables/20260528_120000.json
    python -m ingestion.census.govsstatefin_variables --truncate

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
from pathlib import Path
from typing import Any, AsyncIterator

import httpx
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/census/govsstatefin_variables")
DEFAULT_DATASET = "govsstatefin"
DEFAULT_URL = (
    "https://api.census.gov/data/timeseries/govsstatefin/variables.json"
)


def _snapshot_path(cache_dir: Path, now: dt.datetime | None = None) -> Path:
    """Build a timestamped snapshot filename in ``cache_dir``.

    Format is ``YYYYMMDD_HHMMSS.json`` so files sort lexically in time order.
    Using UTC keeps cross-environment lexical ordering monotonic.
    """
    stamp = (now or dt.datetime.now(dt.timezone.utc)).strftime("%Y%m%d_%H%M%S")
    return cache_dir / f"{stamp}.json"


def latest_snapshot(cache_dir: Path) -> Path | None:
    """Return the most recent ``YYYYMMDD_HHMMSS.json`` snapshot, or ``None``."""
    if not cache_dir.exists():
        return None
    snaps = sorted(cache_dir.glob("*.json"))
    return snaps[-1] if snaps else None


async def fetch_snapshot(
    client: httpx.AsyncClient,
    url: str,
    cache_dir: Path,
    *,
    now: dt.datetime | None = None,
) -> Path:
    """Download the variables.json blob and write a fresh timestamped snapshot.

    Snapshots are append-only — every successful fetch writes a new file so
    operators can ``diff`` codebook versions over time. The pipeline always
    processes the snapshot it just wrote.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Census variables fetch: {}", url)
    r = await client.get(url, timeout=60)
    r.raise_for_status()
    body = r.json()
    # Light shape check — fail loudly if the endpoint shape ever changes,
    # rather than silently writing zero rows downstream.
    if not isinstance(body, dict) or "variables" not in body:
        raise RuntimeError(
            f"Census variables.json response missing 'variables' key. "
            f"Got top-level keys: {list(body) if isinstance(body, dict) else type(body).__name__}"
        )
    out = _snapshot_path(cache_dir, now=now)
    out.write_text(json.dumps(body, indent=2, sort_keys=True))
    logger.success("Census variables snapshot saved -> {}", out)
    return out


def _safe_str(v: Any, maxlen: int | None = None) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    return s[:maxlen] if maxlen else s


def melt_variables(
    body: dict[str, Any],
    *,
    dataset: str,
    source_url: str,
    snapshot_at: dt.datetime,
) -> list[dict[str, Any]]:
    """Flatten ``body['variables']`` into one row dict per variable_code.

    Every variable is included — including the standard Census predicate
    variables ``for`` / ``in`` / ``ucgid`` / ``time`` — because bronze's
    job is "verbatim with hot keys hoisted". Staging models filter as needed.
    """
    out: list[dict[str, Any]] = []
    variables = body.get("variables") or {}
    for code, meta in variables.items():
        # Defensive: a malformed entry where the value isn't a dict shouldn't
        # blow up the whole pipeline. Skip with a warning.
        if not isinstance(meta, dict):
            logger.warning(
                "Skipping non-dict metadata for variable_code={}: {!r}",
                code, type(meta).__name__,
            )
            continue
        attrs_raw = meta.get("attributes")
        attrs_str: str | None
        if isinstance(attrs_raw, list):
            attrs_str = ",".join(str(a) for a in attrs_raw) or None
        else:
            attrs_str = _safe_str(attrs_raw)
        var_limit: int | None
        try:
            var_limit = int(meta["limit"]) if meta.get("limit") is not None else None
        except (TypeError, ValueError):
            var_limit = None

        required_raw = meta.get("required")
        if isinstance(required_raw, bool):
            required_val: bool | None = required_raw
        elif isinstance(required_raw, str):
            required_val = required_raw.strip().lower() in ("true", "yes", "1")
        else:
            required_val = None

        out.append(
            {
                "source": "census_govsstatefin_variables",
                "source_version": snapshot_at.strftime("%Y%m%d_%H%M%S"),
                "natural_key": f"{dataset}:{code}",
                "dataset": dataset,
                "variable_code": str(code)[:64],
                "label": _safe_str(meta.get("label")),
                "concept": _safe_str(meta.get("concept")),
                "predicate_type": _safe_str(meta.get("predicateType"), 32),
                "var_group": _safe_str(meta.get("group"), 64),
                "var_limit": var_limit,
                "attributes": attrs_str,
                "required": required_val,
                "source_url": source_url,
                "snapshot_at": snapshot_at,
                "raw_record": meta,
            }
        )
    return out


class CensusFinanceVariableRow(RawRow):
    """One variable from the Census govsstatefin codebook."""

    dataset: str = Field(min_length=1, max_length=64)
    variable_code: str = Field(min_length=1, max_length=64)
    label: str | None = None
    concept: str | None = None
    predicate_type: str | None = Field(default=None, max_length=32)
    var_group: str | None = Field(default=None, max_length=64)
    var_limit: int | None = None
    attributes: str | None = None
    required: bool | None = None
    source_url: str = Field(min_length=1, max_length=500)
    snapshot_at: dt.datetime
    raw_record: dict


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_census_finance_variables (
        dataset         VARCHAR(64)   NOT NULL,
        variable_code   VARCHAR(64)   NOT NULL,
        label           TEXT,
        concept         TEXT,
        predicate_type  VARCHAR(32),
        var_group       VARCHAR(64),
        var_limit       INTEGER,
        attributes      TEXT,
        required        BOOLEAN,
        source_url      VARCHAR(500)  NOT NULL,
        snapshot_at     TIMESTAMPTZ   NOT NULL,
        raw_record      JSONB         NOT NULL,
        loaded_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
        last_updated    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
        PRIMARY KEY (dataset, variable_code)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        "CREATE INDEX IF NOT EXISTS idx_bcfv_concept "
        "ON bronze.bronze_census_finance_variables (concept) "
        "WHERE concept IS NOT NULL"
    ),
    text(
        "CREATE INDEX IF NOT EXISTS idx_bcfv_group "
        "ON bronze.bronze_census_finance_variables (var_group) "
        "WHERE var_group IS NOT NULL"
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_census_finance_variables")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_census_finance_variables
        (dataset, variable_code, label, concept, predicate_type,
         var_group, var_limit, attributes, required, source_url,
         snapshot_at, raw_record, loaded_at, last_updated)
    VALUES
        (:dataset, :variable_code, :label, :concept, :predicate_type,
         :var_group, :var_limit, :attributes, :required, :source_url,
         :snapshot_at, CAST(:raw_record AS JSONB), NOW(), NOW())
    ON CONFLICT (dataset, variable_code) DO UPDATE SET
        label          = EXCLUDED.label,
        concept        = EXCLUDED.concept,
        predicate_type = EXCLUDED.predicate_type,
        var_group      = EXCLUDED.var_group,
        var_limit      = EXCLUDED.var_limit,
        attributes     = EXCLUDED.attributes,
        required       = EXCLUDED.required,
        source_url     = EXCLUDED.source_url,
        snapshot_at    = EXCLUDED.snapshot_at,
        raw_record     = EXCLUDED.raw_record,
        last_updated   = NOW()
    """
)


class CensusFinanceVariablesPipeline(DataSourcePipeline[CensusFinanceVariableRow]):
    source = "census_govsstatefin_variables"
    batch_size = 500
    row_schema = CensusFinanceVariableRow

    def __init__(
        self,
        *,
        dataset: str = DEFAULT_DATASET,
        url: str = DEFAULT_URL,
        cache_dir: Path = CACHE_DIR,
        fetch: bool = True,
        snapshot: Path | None = None,
        limit: int | None = None,
    ):
        self._dataset = dataset
        self._url = url
        self._cache_dir = cache_dir
        self._fetch = fetch
        self._snapshot = snapshot
        self._limit = limit

    async def _resolve_snapshot(self) -> Path:
        if self._snapshot is not None:
            if not self._snapshot.exists():
                raise FileNotFoundError(
                    f"--snapshot points at {self._snapshot} which does not exist."
                )
            return self._snapshot
        if self._fetch:
            async with httpx.AsyncClient() as client:
                return await fetch_snapshot(client, self._url, self._cache_dir)
        latest = latest_snapshot(self._cache_dir)
        if latest is None:
            raise FileNotFoundError(
                f"--no-fetch set but no snapshots found under {self._cache_dir}. "
                f"Run once without --no-fetch to populate the cache."
            )
        logger.info("Using latest cached snapshot: {}", latest)
        return latest

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        snapshot_path = await self._resolve_snapshot()
        body = json.loads(snapshot_path.read_text())
        # Use the file mtime as snapshot_at when the timestamp isn't encoded
        # in the filename (defensive — operator-supplied snapshots may have
        # arbitrary names).
        try:
            stem = snapshot_path.stem
            snapshot_at = dt.datetime.strptime(stem, "%Y%m%d_%H%M%S").replace(
                tzinfo=dt.timezone.utc
            )
        except ValueError:
            snapshot_at = dt.datetime.fromtimestamp(
                snapshot_path.stat().st_mtime, tz=dt.timezone.utc
            )

        rows = melt_variables(
            body,
            dataset=self._dataset,
            source_url=self._url,
            snapshot_at=snapshot_at,
        )
        logger.info(
            "Melted {} variables from snapshot {}", len(rows), snapshot_path.name
        )
        emitted = 0
        for row in rows:
            if self._limit is not None and emitted >= self._limit:
                return
            yield row
            emitted += 1

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[CensusFinanceVariableRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "dataset": r.dataset,
                "variable_code": r.variable_code,
                "label": r.label,
                "concept": r.concept,
                "predicate_type": r.predicate_type,
                "var_group": r.var_group,
                "var_limit": r.var_limit,
                "attributes": r.attributes,
                "required": r.required,
                "source_url": r.source_url,
                "snapshot_at": r.snapshot_at,
                "raw_record": json.dumps(r.raw_record),
            }
            for r in rows
        ]
        await session.execute(_UPSERT_SQL, params)


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
        description=(
            "Load the Census govsstatefin variables codebook into "
            "bronze.bronze_census_finance_variables."
        )
    )
    parser.add_argument(
        "--dataset",
        default=DEFAULT_DATASET,
        help=(
            "Census dataset id (default: %(default)s). Stored as the first "
            "component of the primary key so multiple variable codebooks can "
            "share the table."
        ),
    )
    parser.add_argument(
        "--url",
        default=DEFAULT_URL,
        help="Override the variables.json URL (default: %(default)s).",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Skip the HTTP fetch; load the newest snapshot in the cache dir.",
    )
    parser.add_argument(
        "--snapshot",
        type=Path,
        help="Pin to a specific snapshot file (overrides --no-fetch logic).",
    )
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="TRUNCATE table before loading (recommended for clean refreshes).",
    )
    parser.add_argument("--limit", type=int, help="Limit records (for testing).")
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = CensusFinanceVariablesPipeline(
        dataset=args.dataset,
        url=args.url,
        fetch=not args.no_fetch,
        snapshot=args.snapshot,
        limit=args.limit,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
