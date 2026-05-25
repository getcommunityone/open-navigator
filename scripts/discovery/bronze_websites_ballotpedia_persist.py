"""
Insert outbound link rows into ``bronze.bronze_websites_ballotpedia``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    import psycopg2
    from psycopg2.extras import Json
except ModuleNotFoundError:  # pragma: no cover
    psycopg2 = None  # type: ignore[misc, assignment]
    Json = None  # type: ignore[misc, assignment]


def insert_bronze_websites_ballotpedia(
    database_url: str,
    *,
    scrape_batch_id: str,
    rows: list[dict[str, Any]],
) -> int:
    """Bulk-insert link rows. Returns count inserted."""
    if not rows or not database_url or psycopg2 is None:
        return 0

    scraped_default = datetime.now(timezone.utc).isoformat()
    values: list[tuple[Any, ...]] = []
    for r in rows:
        target_url = (r.get("target_url") or "").strip()
        source_page_url = (r.get("source_page_url") or "").strip()
        if not target_url or not source_page_url:
            continue
        raw = r.get("raw_row")
        if raw is None:
            raw = {k: v for k, v in r.items() if k not in ("scraped_at",)}
        scraped_at = r.get("scraped_at") or scraped_default
        values.append(
            (
                scrape_batch_id,
                source_page_url,
                r.get("source_page_kind"),
                target_url,
                r.get("target_host"),
                r.get("target_kind"),
                r.get("anchor_text"),
                r.get("rel"),
                r.get("state_code"),
                r.get("jurisdiction_id"),
                r.get("ocd_id"),
                Json(raw),
                scraped_at,
            )
        )

    if not values:
        return 0

    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.executemany(
                """
                INSERT INTO bronze.bronze_websites_ballotpedia
                    (scrape_batch_id, source_page_url, source_page_kind,
                     target_url, target_host, target_kind, anchor_text, rel,
                     state_code, jurisdiction_id, ocd_id, raw_row, scraped_at)
                VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                """,
                values,
            )
        conn.commit()
    finally:
        conn.close()
    return len(values)
