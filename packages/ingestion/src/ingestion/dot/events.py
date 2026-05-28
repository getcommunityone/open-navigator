#!/usr/bin/env python3
"""DOT public events pipeline: load unified_events.jsonl into bronze.

Ported from load_dot_unified_events_to_postgres.py to the core_lib
DataSourcePipeline contract.

Reads the JSONL emitted by build_dot_unified_events.py and upserts each
event into bronze.bronze_dot_public_events. Requires migration
021_create_bronze_dot_public_events.sql to have been applied.

Usage:
    python -m scrapers.dot.build_dot_unified_events  (FETCH); python -m ingestion.dot.events  (LAND)
    python -m ingestion.dot.events \\
        --jsonl data/cache/dot_public_involvement/unified_events.jsonl

Configuration:
    NEON_DATABASE_URL_DEV / NEON_DATABASE_URL / DATABASE_URL via core_lib.db.
"""
from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, AsyncIterator

from pydantic import Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core_lib.logging import setup_logging
from core_lib.pipeline import DataSourcePipeline, PipelineContext, RawRow


DEFAULT_JSONL = (
    Path(__file__).resolve().parents[3]
    / "data" / "cache" / "dot_public_involvement" / "unified_events.jsonl"
)


def _parse_date_iso(s: str | None) -> date | None:
    if not s or not str(s).strip():
        return None
    raw = str(s).strip()
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        return None


def _parse_scraped_at(raw: Any) -> datetime:
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    s = (raw or "").strip() if isinstance(raw, str) else ""
    if not s:
        return datetime.now(timezone.utc)
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return datetime.now(timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


class DotEventRow(RawRow):
    """One DOT public event, validated before upsert into bronze."""

    state_usps: str = Field(min_length=2, max_length=2)
    event_fingerprint: str = Field(min_length=1)
    adapter: str = ""
    title: str = ""
    summary_text: str | None = None
    list_page_url: str = ""
    detail_url: str | None = None
    meeting_date: date | None = None
    meeting_date_raw: str | None = None
    collateral: list[Any] = Field(default_factory=list)
    raw_record: dict[str, Any] = Field(default_factory=dict)
    scraped_at: datetime


_UPSERT_SQL = text(
    """
    INSERT INTO bronze.bronze_dot_public_events (
        state_usps, event_fingerprint, adapter, title, summary_text,
        list_page_url, detail_url, meeting_date, meeting_date_raw,
        collateral, raw_record, scraped_at
    ) VALUES (
        :state_usps, :event_fingerprint, :adapter, :title, :summary_text,
        :list_page_url, :detail_url, :meeting_date, :meeting_date_raw,
        CAST(:collateral AS jsonb), CAST(:raw_record AS jsonb), :scraped_at
    )
    ON CONFLICT (event_fingerprint) DO UPDATE SET
        adapter = EXCLUDED.adapter,
        title = EXCLUDED.title,
        summary_text = EXCLUDED.summary_text,
        list_page_url = EXCLUDED.list_page_url,
        detail_url = EXCLUDED.detail_url,
        meeting_date = EXCLUDED.meeting_date,
        meeting_date_raw = EXCLUDED.meeting_date_raw,
        collateral = EXCLUDED.collateral,
        raw_record = EXCLUDED.raw_record,
        scraped_at = EXCLUDED.scraped_at
    """
)


class DotEventsPipeline(DataSourcePipeline[DotEventRow]):
    source = "dot_public_events"
    batch_size = 500
    row_schema = DotEventRow

    def __init__(self, *, jsonl_path: Path | None = None):
        self._jsonl_path = jsonl_path or DEFAULT_JSONL

    async def extract(self, ctx: PipelineContext) -> AsyncIterator[dict]:
        path = self._jsonl_path
        if not path.is_file():
            raise FileNotFoundError(f"JSONL not found: {path}")
        with path.open(encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"Line {line_no}: {exc}") from exc
                fp = (obj.get("event_fingerprint") or "").strip()
                if not fp:
                    # match legacy: surface as error to caller, not silent skip
                    raise ValueError(f"Line {line_no}: missing event_fingerprint")
                state = (obj.get("state_usps") or "").strip().upper()
                if len(state) != 2:
                    raise ValueError(f"Line {line_no}: bad state_usps")
                yield {
                    "source": self.source,
                    "source_version": "unified_events.jsonl",
                    "natural_key": fp,
                    "state_usps": state,
                    "event_fingerprint": fp,
                    "adapter": (obj.get("adapter") or "").strip(),
                    "title": (obj.get("title") or "").strip(),
                    "summary_text": obj.get("summary_text"),
                    "list_page_url": (obj.get("list_page_url") or "").strip(),
                    "detail_url": (obj.get("detail_url") or "").strip() or None,
                    "meeting_date": _parse_date_iso(obj.get("meeting_date")),
                    "meeting_date_raw": obj.get("meeting_date_raw"),
                    "collateral": obj.get("collateral") or [],
                    "raw_record": obj,
                    "scraped_at": _parse_scraped_at(obj.get("scraped_at")),
                }

    async def load_batch(
        self,
        session: AsyncSession,
        rows: list[DotEventRow],
        ctx: PipelineContext,
    ) -> None:
        params = []
        for r in rows:
            params.append({
                "state_usps": r.state_usps,
                "event_fingerprint": r.event_fingerprint,
                "adapter": r.adapter,
                "title": r.title,
                "summary_text": r.summary_text,
                "list_page_url": r.list_page_url,
                "detail_url": r.detail_url,
                "meeting_date": r.meeting_date,
                "meeting_date_raw": r.meeting_date_raw,
                "collateral": json.dumps(r.collateral),
                "raw_record": json.dumps(r.raw_record),
                "scraped_at": r.scraped_at,
            })
        await session.execute(_UPSERT_SQL, params)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Load DOT unified events JSONL into bronze.bronze_dot_public_events"
    )
    parser.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL,
                        help=f"JSONL path (default: {DEFAULT_JSONL})")
    return parser


async def _run(args: argparse.Namespace) -> None:
    pipeline = DotEventsPipeline(jsonl_path=args.jsonl)
    await pipeline.run()


def main() -> int:
    setup_logging()
    args = build_parser().parse_args()
    asyncio.run(_run(args))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
