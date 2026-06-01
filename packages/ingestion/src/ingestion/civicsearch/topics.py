#!/usr/bin/env python3
"""CivicSearch topic-decoder pipeline: land topics.json into
bronze.bronze_events_civicsearch_topic (or its _schools counterpart).

Reads the JSON array emitted by the FETCH scraper ``scrapers.civicsearch.topics``
and upserts one row per ``topic_id`` (CivicSearch's numeric topic id, ``-1`` ==
catch-all bucket). Records are landed VERBATIM — name/keyword shaping is done
downstream in dbt. Requires migration
101_create_bronze_events_civicsearch_topic.sql to have been applied.

Topic ids are PORTAL-SPECIFIC, so the two portals land into separate tables
(mirroring the split events tables): ``--schools`` selects the schools table and
the schools/topics.json source.

Usage:
    python -m scrapers.civicsearch.topics --portal both        (FETCH)
    python -m ingestion.civicsearch.topics                     (LAND cities)
    python -m ingestion.civicsearch.topics --schools           (LAND schools)
    python -m ingestion.civicsearch.topics \\
        --json data/cache/civicsearch/cities/topics.json

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator

from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow
from loguru import logger
from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

CACHE_ROOT = Path("data/cache/civicsearch")

# Two decoder tables share an identical schema (see migration 101). The loader
# targets one or the other; --schools selects SCHOOLS_TABLE. Each portal's
# topics.json sits in its own subdir so the two datasets never mingle:
#   data/cache/civicsearch/cities/topics.json   -> BASE_TABLE
#   data/cache/civicsearch/schools/topics.json  -> SCHOOLS_TABLE
BASE_TABLE = "bronze.bronze_events_civicsearch_topic"
SCHOOLS_TABLE = "bronze.bronze_events_civicsearch_schools_topic"


def _default_json(*, schools: bool) -> Path:
    portal = "schools" if schools else "cities"
    return CACHE_ROOT / portal / "topics.json"


class CivicSearchTopicRow(RawRow):
    """One CivicSearch topic-decoder entry, validated before upsert into bronze."""

    topic_id: int
    name: str = Field(min_length=1)
    query_id: str | None = None
    keyword_stats: list[Any] = Field(default_factory=list)
    raw_record: dict[str, Any] = Field(default_factory=dict)


def _build_upsert_sql(table: str):
    """Build the per-topic_id upsert for a given (identical-schema) decoder table.

    ``table`` is a trusted internal constant (BASE_TABLE / SCHOOLS_TABLE), not
    user input — interpolating it is safe and necessary since a table name can't
    be a bind parameter.
    """
    return text(
        f"""
        INSERT INTO {table} (
            topic_id, name, query_id, keyword_stats, raw_record
        ) VALUES (
            :topic_id, :name, :query_id,
            CAST(:keyword_stats AS jsonb), CAST(:raw_record AS jsonb)
        )
        ON CONFLICT (topic_id) DO UPDATE SET
            name = EXCLUDED.name,
            query_id = EXCLUDED.query_id,
            keyword_stats = EXCLUDED.keyword_stats,
            raw_record = EXCLUDED.raw_record,
            last_updated = CURRENT_TIMESTAMP
        """
    )


class CivicSearchTopicsPipeline(DataSourcePipeline[CivicSearchTopicRow]):
    source = "civicsearch"
    batch_size = 200
    row_schema = CivicSearchTopicRow

    def __init__(
        self,
        *,
        json_path: Path | None = None,
        table: str = BASE_TABLE,
    ):
        self._json_path = json_path or _default_json(schools=table == SCHOOLS_TABLE)
        self._table = table
        self._upsert_sql = _build_upsert_sql(table)

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._json_path
        if not path.is_file():
            raise FileNotFoundError(f"topics.json not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError(f"{path}: expected a JSON array of topics")
        for entry in data:
            tid = entry.get("id")
            if tid is None:
                logger.warning("topic entry missing id, skipping: {}", entry)
                continue
            yield {
                "source": self.source,
                "source_version": "topics.json.v1",
                "natural_key": str(tid),
                "topic_id": int(tid),
                "name": entry.get("name"),
                "query_id": entry.get("query_id"),
                "keyword_stats": entry.get("keyword_stats") or [],
                "raw_record": entry,
            }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[CivicSearchTopicRow],
        ctx: PipelineContext,
    ) -> None:
        params = [
            {
                "topic_id": r.topic_id,
                "name": r.name,
                "query_id": r.query_id,
                "keyword_stats": json.dumps(r.keyword_stats),
                "raw_record": json.dumps(r.raw_record),
            }
            for r in rows
        ]
        await session.execute(self._upsert_sql, params)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Land CivicSearch topics.json into "
        "bronze.bronze_events_civicsearch_topic"
    )
    parser.add_argument("--json", type=Path, default=None,
                        help="topics.json path (default: derived from the target "
                             "portal — schools/ vs cities/ subdir).")
    target = parser.add_mutually_exclusive_group()
    target.add_argument("--schools", action="store_true",
                        help=f"Land into the school-district decoder "
                             f"({SCHOOLS_TABLE}) instead of the general "
                             f"{BASE_TABLE}.")
    target.add_argument("--table", type=str, default=None,
                        help="Explicit target table (advanced; overrides "
                             "--schools). Must be an identical-schema "
                             "CivicSearch decoder table.")
    return parser


async def _run(args: argparse.Namespace) -> None:
    table = args.table or (SCHOOLS_TABLE if args.schools else BASE_TABLE)
    json_path = args.json or _default_json(schools=args.schools)
    logger.info("Landing CivicSearch topics from {} into {}", json_path, table)
    pipeline = CivicSearchTopicsPipeline(json_path=json_path, table=table)
    await pipeline.run()


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
