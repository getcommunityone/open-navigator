#!/usr/bin/env python3
"""
Promote scraped YouTube meeting videos from ``bronze.bronze_events_youtube`` into
the OCD-aligned ``public.civic_event`` table, attaching each video as a
``civic_eventmedia`` recording.

Why this exists
---------------
``bronze.bronze_events_analysis_ai`` carries a foreign key
``event_id -> public.civic_event(legacy_id)``. The live analyze step
(``llm.enrichment.load_meeting_transcripts``) and the cache backfill
(``llm.enrichment.load_analysis_cache_to_bronze``) both need a ``civic_event`` row
to attach an analysis to. But the YouTube meeting videos those analyses describe
were never promoted into ``civic_event`` — that table only held ``openstates`` and
``bronze_meetings_promotion`` events — so every analysis insert failed the FK and
the table stayed empty. This loader fills that gap, mirroring
``scripts/discovery/promote_bronze_meetings_to_c1_event.py`` for the YouTube source.

The civic_event identity / bridge
------------------------------
``civic_event`` has two keys:
  * ``id``        — varchar ``ocd-event/<uuid5>``; referenced by child tables
                    (``civic_eventmedia.event_id``, ``civic_eventdocument.event_id``).
  * ``legacy_id`` — integer sequence PK; the target of the analysis FK.

One YouTube video == one event (1:1), so we key the event on the video:
  * ``dedupe_key = 'youtube|<video_id>'``  (UPSERT conflict target — the partial
    unique index ``ix_c1_event_dedupe_key_unique`` enforces it)
  * ``id        = ocd-event/<uuid5(dedupe_key)>``  (deterministic, safe re-run)

Keying on ``dedupe_key`` gives the analysis loader an exact, parse-free
``video_id -> legacy_id`` lookup::

    SELECT legacy_id FROM public.civic_event WHERE dedupe_key = 'youtube|' || %s

Scope
-----
By default only videos that passed the Gemini policy gate
(``policy_analysis_at IS NOT NULL``) are promoted — the curated meeting set whose
analyses are cached. Raw scrapes (which include non-government noise) are skipped.
Pass ``--all-dated`` to promote every video that has an ``event_date`` instead.

Idempotent: re-running upserts the same ``dedupe_key`` and uses deterministic
child UUIDs, so no duplicate rows.

Usage::

    python -m ingestion.youtube.promote_to_c1_event --dry-run
    python -m ingestion.youtube.promote_to_c1_event
    python -m ingestion.youtube.promote_to_c1_event --states AL,GA
    python -m ingestion.youtube.promote_to_c1_event --all-dated
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from dataclasses import dataclass

import psycopg2
from loguru import logger
from psycopg2.extras import RealDictCursor

from core_lib.db import resolve_target_database_url

# Same namespace the meetings promotion uses, so deterministic ids are consistent
# across both promotion paths.
_UUID_NS_EVENT_RESOURCE = uuid.UUID("9c8a5d2b-1f4e-4a6b-a8c1-3e7f9b2c4d5a")

# Default classification when the scraped meeting_type is empty.
_DEFAULT_CLASSIFICATION = "committee-meeting"
_SOURCE = "bronze_youtube_promotion"


@dataclass
class YouTubeEvent:
    """A single bronze_events_youtube row eligible for promotion."""

    video_id: str
    event_date: str | None          # ISO YYYY-MM-DD (text) or None
    event_time: str | None
    title: str | None
    description: str | None
    jurisdiction_id: str | None
    jurisdiction_name: str | None
    jurisdiction_type: str | None
    city: str | None
    state_code: str | None
    meeting_type: str | None
    location: str | None
    location_description: str | None
    channel_id: str | None
    channel_url: str | None
    channel_type: str | None
    video_url: str | None
    view_count: int | None
    duration_minutes: int | None
    like_count: int | None
    language: str | None

    @property
    def dedupe_key(self) -> str:
        return f"youtube|{self.video_id}"

    @property
    def event_id(self) -> str:
        """Deterministic civic_event.id (the ocd-event string child rows reference)."""
        return f"ocd-event/{uuid.uuid5(_UUID_NS_EVENT_RESOURCE, self.dedupe_key)}"

    @property
    def name(self) -> str:
        title = (self.title or "").strip()
        if title:
            return title[:200]
        if self.event_date:
            return f"Meeting {self.event_date}"
        return self.video_id

    @property
    def classification(self) -> str:
        mt = (self.meeting_type or "").strip()
        return (mt or _DEFAULT_CLASSIFICATION)[:100]


def load_youtube_rows(conn, states: tuple[str, ...] | None,
                      all_dated: bool) -> list[YouTubeEvent]:
    """Load promotable bronze_events_youtube rows.

    Default scope: policy-analyzed videos (the curated meeting set whose Gemini
    analyses are cached). ``all_dated`` widens to every video carrying a date.
    """
    where = ["video_id IS NOT NULL"]
    args: list = []
    if all_dated:
        where.append("event_date IS NOT NULL")
    else:
        where.append("policy_analysis_at IS NOT NULL")
    if states:
        where.append("state_code = ANY(%s)")
        args.append(list(states))

    sql = f"""
        SELECT video_id, event_date::text AS event_date, event_time::text AS event_time,
               title, description, jurisdiction_id, jurisdiction_name, jurisdiction_type,
               city, state_code, meeting_type, location, location_description,
               channel_id, channel_url, channel_type, video_url,
               view_count, duration_minutes, like_count, language
        FROM bronze.bronze_events_youtube
        WHERE {' AND '.join(where)}
        ORDER BY video_id
    """
    rows: list[YouTubeEvent] = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, args)
        for r in cur.fetchall():
            rows.append(YouTubeEvent(**r))
    return rows


def upsert_events(conn, events: list[YouTubeEvent], *, dry_run: bool) -> int:
    """UPSERT civic_event rows keyed on dedupe_key; preserve id/legacy_id on conflict."""
    if dry_run:
        return len(events)
    n = 0
    insert_sql = """
        INSERT INTO public.civic_event (
            id, name, description, start_date, event_time,
            jurisdiction_id, jurisdiction_name, jurisdiction_type, city, state,
            location, location_description, classification, status, source,
            channel_id, channel_url, channel_type, video_url,
            view_count, duration_minutes, like_count, language,
            dedupe_key, created_at, updated_at, extras, links, sources
        ) VALUES (
            %(id)s, %(name)s, %(description)s, %(start_date)s::date, %(event_time)s::time,
            %(jurisdiction_id)s, %(jurisdiction_name)s, %(jurisdiction_type)s, %(city)s, %(state)s,
            %(location)s, %(location_description)s, %(classification)s, 'confirmed', %(source)s,
            %(channel_id)s, %(channel_url)s, %(channel_type)s, %(video_url)s,
            %(view_count)s, %(duration_minutes)s, %(like_count)s, %(language)s,
            %(dedupe_key)s, now(), now(), '{}'::jsonb, '[]'::jsonb, '[]'::jsonb
        )
        ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL
        DO UPDATE SET
            -- preserve existing id / legacy_id; refresh mutable metadata
            name = EXCLUDED.name,
            description = EXCLUDED.description,
            start_date = EXCLUDED.start_date,
            event_time = EXCLUDED.event_time,
            jurisdiction_id = EXCLUDED.jurisdiction_id,
            video_url = EXCLUDED.video_url,
            view_count = EXCLUDED.view_count,
            like_count = EXCLUDED.like_count,
            updated_at = now()
    """
    with conn.cursor() as cur:
        for e in events:
            cur.execute(insert_sql, {
                "id": e.event_id, "name": e.name, "description": e.description,
                "start_date": e.event_date, "event_time": e.event_time,
                "jurisdiction_id": e.jurisdiction_id, "jurisdiction_name": e.jurisdiction_name,
                "jurisdiction_type": e.jurisdiction_type, "city": e.city, "state": e.state_code,
                "location": e.location, "location_description": e.location_description,
                "classification": e.classification, "source": _SOURCE,
                "channel_id": e.channel_id, "channel_url": e.channel_url,
                "channel_type": e.channel_type, "video_url": e.video_url,
                "view_count": e.view_count, "duration_minutes": e.duration_minutes,
                "like_count": e.like_count, "language": e.language,
                "dedupe_key": e.dedupe_key,
            })
            n += 1
    conn.commit()
    return n


def _det_uuid(event_id: str, url: str | None, kind: str) -> str:
    return str(uuid.uuid5(_UUID_NS_EVENT_RESOURCE, f"{kind}|{event_id}|{url or ''}"))


def insert_media(conn, events: list[YouTubeEvent], *, dry_run: bool) -> int:
    """Attach each video as a civic_eventmedia 'recording' row (idempotent)."""
    eligible = [e for e in events if e.video_url]
    if dry_run:
        return len(eligible)
    n = 0
    with conn.cursor() as cur:
        for e in eligible:
            media_id = _det_uuid(e.event_id, e.video_url, "media_youtube")
            links = json.dumps([{"url": e.video_url, "media_type": "video/youtube"}])
            cur.execute(
                """
                INSERT INTO public.civic_eventmedia
                    (id, note, date, event_id, classification, links)
                VALUES (%s::uuid, %s, %s, %s, 'recording', %s::jsonb)
                ON CONFLICT (id) DO NOTHING
                """,
                (media_id, (e.title or "YouTube recording")[:300],
                 e.event_date or "", e.event_id, links),
            )
            n += cur.rowcount
    conn.commit()
    return n


def run(*, states: tuple[str, ...] | None = None, all_dated: bool = False,
        dry_run: bool = False, limit: int | None = None) -> dict[str, int]:
    db_url = resolve_target_database_url()
    logger.info("=" * 70)
    logger.info("bronze_events_youtube -> public.civic_event promotion")
    logger.info("  scope   : {}", "all dated videos" if all_dated else "policy-analyzed only")
    logger.info("  states  : {}", ",".join(states) if states else "ALL")
    logger.info("  dry-run : {}", dry_run)
    logger.info("=" * 70)

    conn = psycopg2.connect(db_url)
    try:
        events = load_youtube_rows(conn, states, all_dated)
        if limit:
            events = events[:limit]
        logger.info("Eligible YouTube events: {:,}", len(events))

        upserted = upsert_events(conn, events, dry_run=dry_run)
        media = insert_media(conn, events, dry_run=dry_run)
    finally:
        conn.close()

    stats = {"eligible": len(events), "events_upserted": upserted, "media_attached": media}
    logger.success(
        "Promotion {}: {events_upserted:,} civic_event upserted, {media_attached:,} recordings attached",
        "(dry-run)" if dry_run else "done", **stats,
    )
    return stats


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Promote bronze_events_youtube meeting videos into public.civic_event",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--states", default="", help="Comma-separated state codes; empty = all")
    p.add_argument("--all-dated", action="store_true",
                   help="Promote every video with an event_date (default: policy-analyzed only)")
    p.add_argument("--dry-run", action="store_true", help="Resolve & count, but no DB writes")
    p.add_argument("--limit", type=int, default=None, help="Cap rows processed (debug)")
    args = p.parse_args(argv)

    states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip()) or None
    run(states=states, all_dated=args.all_dated, dry_run=args.dry_run, limit=args.limit)
    return 0


if __name__ == "__main__":
    sys.exit(main())
