"""Land platform meetings in bronze, idempotently (#536).

Tables (created if missing):

- ``bronze.bronze_platform_meeting`` — one row per meeting, PK ``(platform, meeting_uid)``.
- ``bronze.bronze_platform_meeting_caption`` — caption text a platform serves for a
  meeting's video, PK ``(platform, meeting_uid)``.
- ``bronze.bronze_platform_portal`` — one row per portal read or probed, PK
  ``(platform, portal)``, with its status (``ok``, ``robots_disallowed``,
  ``not_configured``, ...) so blocked portals are on record, not silently missing.

Every write is an ``INSERT ... ON CONFLICT DO UPDATE``: re-running a portal updates
its rows in place and never duplicates them. A meeting row is never deleted because a
later run didn't list it (Legistar drops cancelled meetings from listings).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Iterable, Optional, Sequence

from scrapers.platforms.model import PlatformMeeting, PortalResult

MEETING_TABLE = "bronze.bronze_platform_meeting"
CAPTION_TABLE = "bronze.bronze_platform_meeting_caption"
PORTAL_TABLE = "bronze.bronze_platform_portal"

DDL = f"""
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS {MEETING_TABLE} (
    platform              text        NOT NULL,
    meeting_uid           text        NOT NULL,
    portal                text        NOT NULL,
    jurisdiction_id       text,
    state_code            varchar(2),
    body_name             text,
    title                 text,
    meeting_date          date,
    meeting_time          text,
    location              text,
    agenda_url            text,
    minutes_url           text,
    video_url             text,
    video_url_source      text,
    video_clip_id         text,
    detail_url            text,
    agenda_text           text,
    minutes_text          text,
    votes_json            jsonb,
    has_captions          boolean     NOT NULL DEFAULT false,
    transcription_status  text        NOT NULL,
    source_modified_at    timestamptz,
    raw                   jsonb,
    first_seen_at         timestamptz NOT NULL DEFAULT now(),
    fetched_at            timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT bronze_platform_meeting_pkey PRIMARY KEY (platform, meeting_uid),
    CONSTRAINT bronze_platform_meeting_status_chk CHECK (
        transcription_status IN ('captions', 'queued_whisper', 'video_url_unknown', 'no_video')
    )
);
CREATE INDEX IF NOT EXISTS bronze_platform_meeting_jurisdiction_idx ON {MEETING_TABLE} (jurisdiction_id, meeting_date);
CREATE INDEX IF NOT EXISTS bronze_platform_meeting_status_idx ON {MEETING_TABLE} (transcription_status);

-- Existing warehouses created before #633 lack votes_json.
ALTER TABLE {MEETING_TABLE} ADD COLUMN IF NOT EXISTS votes_json jsonb;

CREATE TABLE IF NOT EXISTS {CAPTION_TABLE} (
    platform        text        NOT NULL,
    meeting_uid     text        NOT NULL,
    caption_source  text        NOT NULL,
    caption_url     text,
    caption_format  text        NOT NULL,
    language        text,
    raw_text        text        NOT NULL,
    segments        jsonb,
    cue_count       integer,
    fetched_at      timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT bronze_platform_meeting_caption_pkey PRIMARY KEY (platform, meeting_uid),
    CONSTRAINT bronze_platform_meeting_caption_meeting_fk FOREIGN KEY (platform, meeting_uid)
        REFERENCES {MEETING_TABLE} (platform, meeting_uid) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS {PORTAL_TABLE} (
    platform             text        NOT NULL,
    portal               text        NOT NULL,
    portal_url           text        NOT NULL,
    jurisdiction_id      text,
    state_code           varchar(2),
    found_via            text        NOT NULL,
    data_center          boolean     NOT NULL DEFAULT false,
    status               text        NOT NULL,
    detail               text,
    meetings_listed      integer     NOT NULL DEFAULT 0,
    newest_meeting_date  date,
    checked_at           timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT bronze_platform_portal_pkey PRIMARY KEY (platform, portal)
);
"""

MEETING_COLS = (
    "platform", "meeting_uid", "portal", "jurisdiction_id", "state_code", "body_name", "title", "meeting_date",
    "meeting_time", "location", "agenda_url", "minutes_url", "video_url", "video_url_source", "video_clip_id",
    "detail_url", "agenda_text", "minutes_text", "votes_json", "has_captions", "transcription_status",
    "source_modified_at", "raw", "fetched_at",
)
CAPTION_COLS = (
    "platform", "meeting_uid", "caption_source", "caption_url", "caption_format", "language", "raw_text",
    "segments", "cue_count", "fetched_at",
)
PORTAL_COLS = (
    "platform", "portal", "portal_url", "jurisdiction_id", "state_code", "found_via", "data_center", "status",
    "detail", "meetings_listed", "newest_meeting_date", "checked_at",
)


def _strip_nul(value: Optional[str]) -> Optional[str]:
    return value.replace("\x00", "") if isinstance(value, str) else value


def meeting_row(m: PlatformMeeting, fetched_at: datetime) -> tuple[Any, ...]:
    return (
        m.platform, m.meeting_uid, m.portal, m.jurisdiction_id, m.state_code, _strip_nul(m.body_name),
        _strip_nul(m.title), m.meeting_date, m.meeting_time, _strip_nul(m.location), m.agenda_url, m.minutes_url,
        m.video_url, m.video_url_source, m.video_clip_id, m.detail_url, _strip_nul(m.agenda_text),
        _strip_nul(m.minutes_text),
        json.dumps(m.votes_json, default=str) if m.votes_json is not None else None,
        m.transcription_status == "captions", m.transcription_status,
        m.source_modified_at, json.dumps(m.raw, default=str), fetched_at,
    )


def caption_row(m: PlatformMeeting, fetched_at: datetime) -> Optional[tuple[Any, ...]]:
    c = m.caption
    if c is None or not c.raw_text.strip():
        return None
    return (
        m.platform, m.meeting_uid, c.caption_source, c.caption_url, c.caption_format, c.language,
        _strip_nul(c.raw_text), json.dumps([cue.as_json() for cue in c.cues]) if c.cues else None,
        len(c.cues), fetched_at,
    )


def portal_row(
    p: PortalResult, checked_at: datetime, meetings_listed: Optional[int] = None, newest: Optional[Any] = None
) -> tuple[Any, ...]:
    """``meetings_listed`` / ``newest`` default to this read's meetings (the store passes the landed totals)."""
    return (
        p.platform, p.portal, p.portal_url, p.jurisdiction_id, p.state_code, p.found_via, p.data_center, p.status,
        p.detail, len(p.meetings) if meetings_listed is None else meetings_listed,
        p.newest_meeting_date if newest is None else newest, checked_at,
    )


def _upsert_sql(table: str, cols: Sequence[str], key: Sequence[str], keep: Iterable[str] = ()) -> str:
    keep = set(keep)
    updates = ", ".join(f"{c} = EXCLUDED.{c}" for c in cols if c not in key and c not in keep)
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES %s ON CONFLICT ({', '.join(key)}) DO UPDATE SET {updates}"


class PlatformStore:
    """psycopg2 writer for the three bronze tables (the local warehouse; never Neon)."""

    def __init__(self, dsn: Optional[str] = None) -> None:
        import psycopg2

        from scrapers.discovery.survey_meeting_sources import warehouse_dsn

        self._conn = psycopg2.connect(dsn or warehouse_dsn())
        self._conn.autocommit = True

    def ensure_tables(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(DDL)

    def known_modified(self, platform: str, portal: str) -> dict[str, Optional[datetime]]:
        """``meeting_uid -> source_modified_at`` already landed for a portal (for incremental reads)."""
        with self._conn.cursor() as cur:
            cur.execute(
                f"SELECT meeting_uid, source_modified_at FROM {MEETING_TABLE} WHERE platform = %s AND portal = %s",
                (platform, portal),
            )
            return {uid: ts for uid, ts in cur.fetchall()}

    def write_portal(self, result: PortalResult) -> int:
        """Upsert one portal read: its meetings, their captions and the portal status, in one transaction."""
        import psycopg2.extras

        now = datetime.now(timezone.utc)
        meetings = result.meetings
        self._conn.autocommit = False
        try:
            with self._conn.cursor() as cur:
                if meetings:
                    psycopg2.extras.execute_values(
                        cur,
                        _upsert_sql(MEETING_TABLE, MEETING_COLS, ("platform", "meeting_uid")),
                        [meeting_row(m, now) for m in meetings],
                        page_size=200,
                    )
                    caps = [r for r in (caption_row(m, now) for m in meetings) if r]
                    if caps:
                        psycopg2.extras.execute_values(
                            cur, _upsert_sql(CAPTION_TABLE, CAPTION_COLS, ("platform", "meeting_uid")), caps
                        )
                cur.execute(
                    f"SELECT count(*), max(meeting_date) FILTER (WHERE meeting_date <= current_date) "
                    f"FROM {MEETING_TABLE} WHERE platform = %s AND portal = %s",
                    (result.platform, result.portal),
                )
                listed, newest = cur.fetchone()
                psycopg2.extras.execute_values(
                    cur,
                    _upsert_sql(PORTAL_TABLE, PORTAL_COLS, ("platform", "portal")),
                    [portal_row(result, now, meetings_listed=int(listed or 0), newest=newest)],
                )
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise
        finally:
            self._conn.autocommit = True
        return len(meetings)

    def close(self) -> None:
        self._conn.close()
