#!/usr/bin/env python3
"""Council Data Project (CDP) events pipeline: land meeting events into bronze.bronze_events_cdp.

CDP (https://councildataproject.org/) runs per-jurisdiction instances that
index, archive, and transcribe city/county council meetings. Each instance
exposes a GraphQL endpoint; this pipeline queries it directly (no `cdp-data`
package dependency — that package pins pandas in a way that conflicts with the
3.12 workspace and shells out to `pip install` at runtime).

Pipeline shape (mirrors ``ingestion.bls.cpi``): ``data/cache/cdp/{instance}.json``
holds the raw GraphQL response (FETCH); ``extract()`` flattens each event +
its first session into one ``CdpEventRow`` (LAND). Re-runs hit the cache;
``--refresh`` forces a re-fetch and ``--no-fetch`` replays strictly from cache.

The bronze table is a CDP-compatible superset that ``stg_bronze_events_cdp``
reads (id, title, description, event_date/time/datetime, body_*, jurisdiction_*,
agenda/minutes/video URLs, session_content_hash, source tracking). This pipeline
populates the subset the GraphQL API exposes; YouTube-only columns
(channel_id, view_count, …) stay NULL for CDP rows.

Source: CDP GraphQL API — https://councildataproject.org/<instance>/graphql

Usage:
    python -m ingestion.cdp.events --instance seattle
    python -m ingestion.cdp.events --instance seattle --limit 50
    python -m ingestion.cdp.events --instance all --truncate
    python -m ingestion.cdp.events --instance portland --no-fetch   # replay cache only
    python -m ingestion.cdp.events --instance denver --refresh      # force re-fetch

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
from pathlib import Path
from typing import Any, AsyncIterator, Iterable

import httpx
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.db import async_session
from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


CACHE_DIR = Path("data/cache/cdp")

# ⚠️ KNOWN-DEAD ENDPOINTS — CDP upstream appears sunset (verified 2026-05-30).
# These GraphQL URLs were carried over from the legacy scripts/datasources/cdp/
# loader, which never actually pulled data. councildataproject.org is a static
# GitHub Pages site: GET → 404, POST → 405. There is no GraphQL gateway.
#
# CDP's data lived in per-instance Google Firestore databases, but those GCP
# projects are now deactivated: anonymous, ADC, and REST reads all return
# 403 CONSUMER_INVALID on the owning project — confirmed across
# cdp-seattle-21723dcf, cdp-seattle-staging-dbengvtn, and cdp-denver-962aefef.
# Firestore bills the call to the project that OWNS the database, so no external
# credential or quota project can read a dead CDP project. Don't re-attempt the
# Firestore route; it's a confirmed dead end.
#
# The DB target + pipeline plumbing below are verified working; fetch_instance()
# is structural-only until/unless CDP revives or a replacement source appears.
# The instance slugs themselves stay valid as jurisdiction keys.
CDP_API_ENDPOINTS: dict[str, str] = {
    "seattle": "https://councildataproject.org/seattle/graphql",
    "portland": "https://councildataproject.org/portland/graphql",
    "boston": "https://councildataproject.org/boston/graphql",
    "denver": "https://councildataproject.org/denver/graphql",
    "king-county": "https://councildataproject.org/king-county/graphql",
    "alameda": "https://councildataproject.org/alameda/graphql",
    "oakland": "https://councildataproject.org/oakland/graphql",
    "charlotte": "https://councildataproject.org/charlotte/graphql",
    "san-jose": "https://councildataproject.org/san-jose/graphql",
}

# Jurisdiction metadata per instance. `name`/`type` flow straight into the
# bronze jurisdiction_* columns; counties carry a None city so jurisdiction_name
# falls back to the county name.
JURISDICTION_MAPPING: dict[str, dict[str, Any]] = {
    "seattle": {"city": "Seattle", "county": None, "state_code": "WA", "state": "Washington", "type": "city"},
    "portland": {"city": "Portland", "county": None, "state_code": "OR", "state": "Oregon", "type": "city"},
    "boston": {"city": "Boston", "county": None, "state_code": "MA", "state": "Massachusetts", "type": "city"},
    "denver": {"city": "Denver", "county": None, "state_code": "CO", "state": "Colorado", "type": "city"},
    "king-county": {"city": None, "county": "King County", "state_code": "WA", "state": "Washington", "type": "county"},
    "alameda": {"city": None, "county": "Alameda County", "state_code": "CA", "state": "California", "type": "county"},
    "oakland": {"city": "Oakland", "county": None, "state_code": "CA", "state": "California", "type": "city"},
    "charlotte": {"city": "Charlotte", "county": None, "state_code": "NC", "state": "North Carolina", "type": "city"},
    "san-jose": {"city": "San José", "county": None, "state_code": "CA", "state": "California", "type": "city"},
}

_EVENTS_QUERY = """
query GetEvents($limit: Int!) {
  events(first: $limit, orderBy: {field: EVENT_DATETIME, direction: DESC}) {
    edges {
      node {
        id
        eventDatetime
        agendaUri
        minutesUri
        body {
          name
          description
        }
        sessions {
          videoUri
          sessionDatetime
          sessionContentHash
        }
      }
    }
  }
}
"""


def cache_path_for(instance: str, *, cache_dir: Path = CACHE_DIR) -> Path:
    """Deterministic cache filename for one instance's raw GraphQL response."""
    return cache_dir / f"{instance}.json"


async def fetch_instance(
    client: httpx.AsyncClient,
    instance: str,
    limit: int,
    *,
    cache_dir: Path = CACHE_DIR,
    refresh: bool = False,
) -> Path:
    """Fetch one instance's events into the cache, return the cache path.

    Skips the HTTP call when a cache file already exists and ``refresh`` is
    False. Raises ``RuntimeError`` on a GraphQL- or transport-level failure.
    """
    api_url = CDP_API_ENDPOINTS.get(instance)
    if not api_url:
        raise ValueError(f"Unknown CDP instance: {instance}. Available: {sorted(CDP_API_ENDPOINTS)}")

    path = cache_path_for(instance, cache_dir=cache_dir)
    if path.exists() and not refresh:
        logger.info("CDP cache hit: instance={} -> {}", instance, path)
        return path

    logger.info("CDP fetch: instance={} limit={} (cache={}, refresh={})", instance, limit, path.exists(), refresh)
    resp = await client.post(
        api_url,
        json={"query": _EVENTS_QUERY, "variables": {"limit": limit}},
        headers={"Content-Type": "application/json"},
        timeout=60,
    )
    resp.raise_for_status()
    body = resp.json()
    if body.get("errors"):
        raise RuntimeError(f"CDP GraphQL errors for {instance}: {body['errors']}")

    cache_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2, sort_keys=True))
    return path


def _split_datetime(
    raw: str | None,
) -> tuple[dt.datetime | None, dt.date | None, dt.time | None]:
    """Parse a CDP ISO ``eventDatetime`` into (datetime, date, time).

    Returns real Python temporals, not the raw string — asyncpg rejects a str
    bound to the ``TIMESTAMPTZ``/``DATE``/``TIME`` columns. ``stg_bronze_events_cdp``
    also filters on ``event_date IS NOT NULL``, so a row with only a datetime
    would be dropped; splitting here at the LAND boundary fills event_date too.
    """
    if not raw:
        return None, None, None
    try:
        parsed = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        logger.warning("Unparsable CDP eventDatetime: {!r}", raw)
        return None, None, None
    return parsed, parsed.date(), parsed.time()


def flatten_events(body: dict[str, Any], instance: str) -> Iterable[dict[str, Any]]:
    """Flatten one cached GraphQL response into per-event raw row dicts."""
    juris = JURISDICTION_MAPPING[instance]
    edges = (body.get("data", {}) or {}).get("events", {}).get("edges", []) or []
    for edge in edges:
        node = edge.get("node") or {}
        event_id = node.get("id")
        if not event_id:
            continue

        meeting_body = node.get("body") or {}
        body_name = meeting_body.get("name") or "City Council"
        body_desc = meeting_body.get("description")

        sessions = node.get("sessions") or []
        first = sessions[0] if sessions else {}
        video_url = first.get("videoUri")
        session_hash = first.get("sessionContentHash")

        event_dt, event_date, event_time = _split_datetime(node.get("eventDatetime"))

        yield {
            "source": "cdp",
            "source_version": instance,
            "natural_key": f"cdp|{instance}|{event_id}",
            "external_source_id": event_id,
            "datasource_id": instance,
            "title": f"{body_name} Meeting",
            "description": body_desc,
            "event_datetime": event_dt,
            "event_date": event_date,
            "event_time": event_time,
            "body_name": body_name,
            "body_description": body_desc,
            "agenda_url": node.get("agendaUri"),
            "minutes_url": node.get("minutesUri"),
            "video_url": video_url,
            "session_content_hash": session_hash,
            "jurisdiction_name": juris["city"] or juris["county"],
            "jurisdiction_type": juris["type"],
            "city": juris["city"],
            "state_code": juris["state_code"],
            "state": juris["state"],
        }


class CdpEventRow(RawRow):
    """One CDP meeting event, validated before upsert into bronze.bronze_events_cdp."""

    external_source_id: str = Field(min_length=1)
    datasource_id: str
    title: str = Field(min_length=1)
    description: str | None = None
    event_datetime: dt.datetime | None = None
    event_date: dt.date | None = None
    event_time: dt.time | None = None
    body_name: str | None = None
    body_description: str | None = None
    agenda_url: str | None = None
    minutes_url: str | None = None
    video_url: str | None = None
    session_content_hash: str | None = None
    jurisdiction_name: str | None = None
    jurisdiction_type: str | None = None
    city: str | None = None
    state_code: str | None = Field(default=None, max_length=2)
    state: str | None = None


_CREATE_SCHEMA_SQL = text("CREATE SCHEMA IF NOT EXISTS bronze")

# Idempotent twin of migration 086. CDP-compatible superset read by
# stg_bronze_events_cdp; YouTube-only columns are present so the shared staging
# view compiles but stay NULL for CDP-sourced rows.
_CREATE_TABLE_SQL = text(
    """
    CREATE TABLE IF NOT EXISTS bronze.bronze_events_cdp (
        id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
        title                TEXT,
        description          TEXT,
        event_date           DATE,
        event_time           TIME,
        event_datetime       TIMESTAMPTZ,
        body_name            TEXT,
        body_description     TEXT,
        jurisdiction_id      TEXT,
        jurisdiction_name    TEXT,
        jurisdiction_type    TEXT,
        state_code           VARCHAR(2),
        state                TEXT,
        city                 TEXT,
        location             TEXT,
        location_description TEXT,
        meeting_type         TEXT,
        status               TEXT,
        agenda_url           TEXT,
        minutes_url          TEXT,
        video_url            TEXT,
        session_content_hash TEXT,
        channel_id           TEXT,
        channel_url          TEXT,
        channel_type         TEXT,
        view_count           BIGINT,
        duration_minutes     NUMERIC,
        like_count           BIGINT,
        language             TEXT,
        source               TEXT NOT NULL,
        datasource_id        TEXT,
        external_source_id   TEXT,
        loaded_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_updated         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        CONSTRAINT uq_bronze_events_cdp_source_extid UNIQUE (source, external_source_id)
    )
    """
)

_CREATE_INDEXES_SQL = (
    text(
        "CREATE INDEX IF NOT EXISTS idx_bronze_events_cdp_state_source "
        "ON bronze.bronze_events_cdp (state_code, source)"
    ),
)

_TRUNCATE_SQL = text("TRUNCATE TABLE bronze.bronze_events_cdp")

_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_events_cdp (
        title, description, event_date, event_time, event_datetime,
        body_name, body_description, jurisdiction_name, jurisdiction_type,
        city, state_code, state, agenda_url, minutes_url, video_url,
        session_content_hash, source, datasource_id, external_source_id,
        loaded_at, last_updated
    ) VALUES (
        :title, :description, :event_date, :event_time, :event_datetime,
        :body_name, :body_description, :jurisdiction_name, :jurisdiction_type,
        :city, :state_code, :state, :agenda_url, :minutes_url, :video_url,
        :session_content_hash, :source, :datasource_id, :external_source_id,
        NOW(), NOW()
    )
    ON CONFLICT (source, external_source_id) DO UPDATE SET
        title                = EXCLUDED.title,
        description          = EXCLUDED.description,
        event_date           = EXCLUDED.event_date,
        event_time           = EXCLUDED.event_time,
        event_datetime       = EXCLUDED.event_datetime,
        body_name            = EXCLUDED.body_name,
        body_description     = EXCLUDED.body_description,
        jurisdiction_name    = EXCLUDED.jurisdiction_name,
        jurisdiction_type    = EXCLUDED.jurisdiction_type,
        city                 = EXCLUDED.city,
        state_code           = EXCLUDED.state_code,
        state                = EXCLUDED.state,
        agenda_url           = EXCLUDED.agenda_url,
        minutes_url          = EXCLUDED.minutes_url,
        video_url            = EXCLUDED.video_url,
        session_content_hash = EXCLUDED.session_content_hash,
        datasource_id        = EXCLUDED.datasource_id,
        last_updated         = NOW()
    """
)


class CdpEventsPipeline(DataSourcePipeline[CdpEventRow]):
    source = "cdp"
    batch_size = 500
    row_schema = CdpEventRow

    def __init__(
        self,
        *,
        instances: list[str],
        limit: int = 100,
        cache_dir: Path = CACHE_DIR,
        allow_fetch: bool = True,
        refresh: bool = False,
    ):
        self._instances = instances
        self._limit = limit
        self._cache_dir = cache_dir
        self._allow_fetch = allow_fetch
        self._refresh = refresh

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        paths: list[Path] = []
        if self._allow_fetch:
            async with httpx.AsyncClient() as client:
                for instance in self._instances:
                    paths.append(
                        await fetch_instance(
                            client, instance, self._limit,
                            cache_dir=self._cache_dir, refresh=self._refresh,
                        )
                    )
        else:
            # --no-fetch: replay strictly from cache. Missing files are an error.
            for instance in self._instances:
                p = cache_path_for(instance, cache_dir=self._cache_dir)
                if not p.exists():
                    raise FileNotFoundError(
                        f"--no-fetch set but cache missing for instance {instance}: {p}"
                    )
                paths.append(p)

        for instance, path in zip(self._instances, paths):
            body = json.loads(path.read_text())
            for row in flatten_events(body, instance):
                yield row

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[CdpEventRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "title": r.title,
                "description": r.description,
                "event_date": r.event_date,
                "event_time": r.event_time,
                "event_datetime": r.event_datetime,
                "body_name": r.body_name,
                "body_description": r.body_description,
                "jurisdiction_name": r.jurisdiction_name,
                "jurisdiction_type": r.jurisdiction_type,
                "city": r.city,
                "state_code": r.state_code,
                "state": r.state,
                "agenda_url": r.agenda_url,
                "minutes_url": r.minutes_url,
                "video_url": r.video_url,
                "session_content_hash": r.session_content_hash,
                "source": r.source,
                "datasource_id": r.datasource_id,
                "external_source_id": r.external_source_id,
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


def _resolve_instances(selected: str) -> list[str]:
    if selected == "all":
        return list(CDP_API_ENDPOINTS)
    if selected not in CDP_API_ENDPOINTS:
        raise SystemExit(
            f"Unknown CDP instance: {selected}. Available: {', '.join(sorted(CDP_API_ENDPOINTS))}, all"
        )
    return [selected]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load Council Data Project events into bronze.bronze_events_cdp"
    )
    parser.add_argument(
        "--instance",
        required=True,
        help="CDP instance slug, or 'all'. Available: " + ", ".join(sorted(CDP_API_ENDPOINTS)),
    )
    parser.add_argument(
        "--limit", type=int, default=100,
        help="Max events to fetch per instance (default: %(default)s).",
    )
    parser.add_argument(
        "--no-fetch", action="store_true",
        help="Use cache only; raise if an instance is not cached.",
    )
    parser.add_argument(
        "--refresh", action="store_true",
        help="Force re-fetch even when a cache file exists.",
    )
    parser.add_argument(
        "--truncate", action="store_true",
        help="TRUNCATE bronze.bronze_events_cdp before loading.",
    )
    return parser


async def _run(args: argparse.Namespace) -> None:
    await _prepare_target(args.truncate)
    pipeline = CdpEventsPipeline(
        instances=_resolve_instances(args.instance),
        limit=args.limit,
        allow_fetch=not args.no_fetch,
        refresh=args.refresh,
    )
    await pipeline.run()


def main() -> None:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))


if __name__ == "__main__":
    main()
