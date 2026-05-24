"""
Insert rows into ``bronze.bronze_jurisdictions_county_directory`` (Neon migration 041).

Source: scrape of publicrecords.netronline.com. One row per (county × office).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

try:
    import psycopg2
except ModuleNotFoundError:  # pragma: no cover
    psycopg2 = None  # type: ignore[misc, assignment]


def insert_bronze_county_directory_rows(
    database_url: str,
    *,
    scrape_batch_id: str,
    state_code: str,
    county_slug: str,
    county_name: str,
    source_page_url: str,
    jurisdiction_id: str | None,
    fips_code: str | None,
    offices: list[dict[str, Any]],
) -> int:
    """
    Bulk-insert offices for one county. Returns number of rows inserted.

    Each ``office`` dict may include: ``office_name`` (required), ``office_url``,
    ``office_phone``, ``data_type``, ``access_type``, plus any extra fields which get
    captured into ``raw_row``.
    """
    if not offices or not database_url or psycopg2 is None:
        return 0
    scraped_at = datetime.now(timezone.utc)
    state_norm = (state_code or "").strip().upper()[:2]
    fips_norm = (fips_code or "").strip()[:5] or None
    inserted = 0
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            for office in offices:
                name = (office.get("office_name") or "").strip()
                if not name:
                    continue
                cur.execute(
                    """
                    INSERT INTO bronze.bronze_jurisdictions_county_directory (
                        scrape_batch_id,
                        state_code,
                        county_slug,
                        county_name,
                        jurisdiction_id,
                        fips_code,
                        source_page_url,
                        office_name,
                        office_url,
                        office_phone,
                        data_type,
                        access_type,
                        raw_row,
                        scraped_at
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
                    )
                    """,
                    (
                        scrape_batch_id,
                        state_norm,
                        county_slug[:256],
                        county_name[:256],
                        jurisdiction_id,
                        fips_norm,
                        source_page_url[:4096],
                        name[:256],
                        (office.get("office_url") or "")[:4096] or None,
                        (office.get("office_phone") or "")[:64] or None,
                        (office.get("data_type") or "")[:256] or None,
                        (office.get("access_type") or "")[:128] or None,
                        json.dumps(office, default=str),
                        scraped_at,
                    ),
                )
                inserted += 1
        conn.commit()
    finally:
        conn.close()
    return inserted
