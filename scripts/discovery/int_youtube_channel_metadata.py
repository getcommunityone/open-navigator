"""
Read/write ``intermediate.int_youtube_channel_metadata`` — cached YouTube channel metadata.

Populate from existing warehouse rows first (``bronze_events_channels``,
``int_events_channels``), then optionally scrape About pages for gaps.
"""

from __future__ import annotations

import json
from typing import Any

CREATE_TABLE_SQL = """
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE TABLE IF NOT EXISTS intermediate.int_youtube_channel_metadata (
    channel_id           TEXT PRIMARY KEY,
    channel_url          TEXT,
    channel_title        TEXT,
    channel_description  TEXT,
    subscriber_count     BIGINT,
    video_count          BIGINT,
    view_count           BIGINT,
    latest_upload        VARCHAR(64),
    external_links       JSONB NOT NULL DEFAULT '[]'::JSONB,
    metadata_source      TEXT NOT NULL,
    fetched_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_int_youtube_channel_metadata_fetched_at
    ON intermediate.int_youtube_channel_metadata (fetched_at DESC);
"""


def ensure_table(conn) -> None:
    cur = conn.cursor()
    try:
        cur.execute(CREATE_TABLE_SQL)
        conn.commit()
    finally:
        cur.close()


def _norm_channel_id(value: Any) -> str | None:
    cid = str(value or "").strip()
    return cid if cid.startswith("UC") else None


def upsert_channel_metadata(
    conn,
    *,
    channel_id: str,
    metadata_source: str,
    channel_url: str | None = None,
    channel_title: str | None = None,
    channel_description: str | None = None,
    subscriber_count: int | None = None,
    video_count: int | None = None,
    view_count: int | None = None,
    latest_upload: str | None = None,
    external_links: list | None = None,
) -> None:
    cid = _norm_channel_id(channel_id)
    if not cid:
        return
    links_json = json.dumps(external_links or [])
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO intermediate.int_youtube_channel_metadata (
                channel_id, channel_url, channel_title, channel_description,
                subscriber_count, video_count, view_count, latest_upload,
                external_links, metadata_source, fetched_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, NOW(), NOW()
            )
            ON CONFLICT (channel_id) DO UPDATE SET
                channel_url = COALESCE(
                    NULLIF(EXCLUDED.channel_url, ''),
                    intermediate.int_youtube_channel_metadata.channel_url
                ),
                channel_title = COALESCE(
                    NULLIF(EXCLUDED.channel_title, ''),
                    intermediate.int_youtube_channel_metadata.channel_title
                ),
                channel_description = COALESCE(
                    NULLIF(EXCLUDED.channel_description, ''),
                    intermediate.int_youtube_channel_metadata.channel_description
                ),
                subscriber_count = COALESCE(
                    EXCLUDED.subscriber_count,
                    intermediate.int_youtube_channel_metadata.subscriber_count
                ),
                video_count = COALESCE(
                    EXCLUDED.video_count,
                    intermediate.int_youtube_channel_metadata.video_count
                ),
                view_count = COALESCE(
                    EXCLUDED.view_count,
                    intermediate.int_youtube_channel_metadata.view_count
                ),
                latest_upload = COALESCE(
                    NULLIF(EXCLUDED.latest_upload, ''),
                    intermediate.int_youtube_channel_metadata.latest_upload
                ),
                external_links = CASE
                    WHEN EXCLUDED.external_links IS NOT NULL
                         AND EXCLUDED.external_links <> '[]'::jsonb
                    THEN EXCLUDED.external_links
                    ELSE intermediate.int_youtube_channel_metadata.external_links
                END,
                metadata_source = EXCLUDED.metadata_source,
                updated_at = NOW(),
                fetched_at = CASE
                    WHEN EXCLUDED.channel_title IS NOT NULL
                         OR EXCLUDED.channel_description IS NOT NULL
                         OR EXCLUDED.subscriber_count IS NOT NULL
                    THEN NOW()
                    ELSE intermediate.int_youtube_channel_metadata.fetched_at
                END
            """,
            (
                cid,
                channel_url,
                channel_title,
                channel_description,
                subscriber_count,
                video_count,
                view_count,
                (str(latest_upload)[:64] if latest_upload else None),
                links_json,
                metadata_source,
            ),
        )
        conn.commit()
    finally:
        cur.close()


def sync_from_bronze_events_channels(conn) -> int:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                bc.channel_id,
                bc.channel_url,
                bc.channel_title,
                bc.channel_description,
                bc.subscriber_count,
                bc.video_count,
                bc.view_count,
                bc.channel_external_links
            FROM bronze.bronze_events_channels bc
            WHERE bc.channel_id IS NOT NULL
              AND BTRIM(bc.channel_id) <> ''
              AND (
                  NULLIF(BTRIM(bc.channel_title), '') IS NOT NULL
                  OR NULLIF(BTRIM(bc.channel_description), '') IS NOT NULL
                  OR bc.subscriber_count IS NOT NULL
              )
            """
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    touched = 0
    for row in rows:
        links = row[7]
        if isinstance(links, str):
            try:
                links = json.loads(links)
            except json.JSONDecodeError:
                links = []
        upsert_channel_metadata(
            conn,
            channel_id=row[0],
            metadata_source="bronze_events_channels",
            channel_url=row[1],
            channel_title=row[2],
            channel_description=row[3],
            subscriber_count=row[4],
            video_count=row[5],
            view_count=row[6],
            external_links=links if isinstance(links, list) else [],
        )
        touched += 1
    return touched


def sync_from_int_events_channels(conn) -> int:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT
                ec.channel_id,
                ec.channel_url,
                ec.channel_title,
                ec.channel_description,
                ec.subscriber_count,
                ec.video_count,
                ec.view_count,
                ec.channel_external_links
            FROM intermediate.int_events_channels ec
            WHERE ec.channel_id IS NOT NULL
              AND BTRIM(ec.channel_id) <> ''
              AND (
                  NULLIF(BTRIM(ec.channel_title), '') IS NOT NULL
                  OR NULLIF(BTRIM(ec.channel_description), '') IS NOT NULL
                  OR ec.subscriber_count IS NOT NULL
              )
            """
        )
        rows = cur.fetchall()
    finally:
        cur.close()

    touched = 0
    for row in rows:
        links = row[7]
        if isinstance(links, str):
            try:
                links = json.loads(links)
            except json.JSONDecodeError:
                links = []
        upsert_channel_metadata(
            conn,
            channel_id=row[0],
            metadata_source="int_events_channels",
            channel_url=row[1],
            channel_title=row[2],
            channel_description=row[3],
            subscriber_count=row[4],
            video_count=row[5],
            view_count=row[6],
            external_links=links if isinstance(links, list) else [],
        )
        touched += 1
    return touched


def fetch_row(conn, channel_id: str) -> dict[str, Any] | None:
    cid = _norm_channel_id(channel_id)
    if not cid:
        return None
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT channel_id, channel_url, channel_title, channel_description,
                   subscriber_count, video_count, view_count, latest_upload,
                   external_links, metadata_source, fetched_at
            FROM intermediate.int_youtube_channel_metadata
            WHERE channel_id = %s
            """,
            (cid,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "channel_id": row[0],
            "channel_url": row[1],
            "channel_title": row[2],
            "channel_description": row[3],
            "subscriber_count": row[4],
            "video_count": row[5],
            "view_count": row[6],
            "latest_upload": row[7],
            "external_links": row[8] or [],
            "metadata_source": row[9],
            "fetched_at": row[10],
        }
    finally:
        cur.close()


def metadata_dict_for_channel(conn, channel_id: str) -> dict[str, Any]:
    """Return cached metadata dict suitable for jurisdiction youtube rows."""
    row = fetch_row(conn, channel_id)
    return dict(row) if row else {}


def apply_metadata_to_jurisdiction_tables(
    conn,
    *,
    table: str,
    state_codes: list[str] | None = None,
    only_missing: bool = True,
) -> int:
    """Copy int cache onto bronze_jurisdiction_youtube* rows by youtube_channel_id."""
    where_parts = [
        "m.channel_id = y.youtube_channel_id",
        "y.youtube_channel_id IS NOT NULL",
        "BTRIM(y.youtube_channel_id) <> ''",
    ]
    params: list[Any] = []
    if state_codes:
        where_parts.append("y.state_code = ANY(%s)")
        params.append([s.upper() for s in state_codes])
    if only_missing:
        where_parts.append(
            """(
                y.channel_title IS NULL OR BTRIM(y.channel_title) = ''
                OR y.channel_description IS NULL OR BTRIM(y.channel_description) = ''
                OR y.subscriber_count IS NULL
            )"""
        )

    sql = f"""
        UPDATE {table} AS y
        SET
            channel_title = COALESCE(NULLIF(BTRIM(m.channel_title), ''), y.channel_title),
            channel_description = COALESCE(NULLIF(BTRIM(m.channel_description), ''), y.channel_description),
            subscriber_count = COALESCE(m.subscriber_count, y.subscriber_count),
            video_count = COALESCE(m.video_count, y.video_count),
            view_count = COALESCE(m.view_count, y.view_count),
            latest_upload = COALESCE(NULLIF(BTRIM(m.latest_upload), ''), y.latest_upload),
            external_links = CASE
                WHEN m.external_links IS NOT NULL AND m.external_links <> '[]'::jsonb
                THEN m.external_links
                ELSE y.external_links
            END,
            loaded_at = NOW()
        FROM intermediate.int_youtube_channel_metadata m
        WHERE {' AND '.join(where_parts)}
    """
    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        updated = cur.rowcount
        conn.commit()
        return int(updated)
    finally:
        cur.close()


def cache_from_enriched_row(
    conn,
    *,
    channel_id: str,
    enriched: Mapping[str, Any],
    channel_url: str | None = None,
) -> None:
    upsert_channel_metadata(
        conn,
        channel_id=channel_id,
        metadata_source="about_scrape",
        channel_url=channel_url or enriched.get("youtube_channel_url"),
        channel_title=enriched.get("channel_title"),
        channel_description=enriched.get("channel_description"),
        subscriber_count=enriched.get("subscriber_count"),
        video_count=enriched.get("video_count"),
        view_count=enriched.get("view_count"),
        latest_upload=enriched.get("latest_upload"),
        external_links=enriched.get("external_links")
        if isinstance(enriched.get("external_links"), list)
        else [],
    )
