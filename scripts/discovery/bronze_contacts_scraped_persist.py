"""
Insert rows into ``bronze.bronze_contacts_scraped`` (see Neon migration 035).

Requires ``psycopg2`` and ``DATABASE_URL`` (or ``NEON_DATABASE_URL``) resolvable via
``resolve_database_url`` from ``jurisdiction_discovery_pipeline``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

try:
    import psycopg2
except ModuleNotFoundError:  # pragma: no cover
    psycopg2 = None  # type: ignore[misc, assignment]


def insert_bronze_contacts_scraped(
    database_url: str,
    *,
    scrape_batch_id: str,
    jurisdiction_id: str,
    state_code: str,
    ocd_id: str | None = None,
    rows: List[Dict[str, Any]],
) -> int:
    """
    Bulk-insert structured contact rows. Returns number of rows attempted.

    Each ``row`` may include: ``source_page_url``, ``page_classification``, ``directory_score``,
    ``person_name``, ``title_or_role``, ``department``, ``email``, ``phone``, ``mailing_address``,
    ``profile_url``, ``extraction_method``, ``contact_source``, ``raw_row`` (dict), ``scraped_at`` (ISO str optional).

    Contact details are automatically structured in OCD format (contact_details JSONB array).
    """
    if not rows or not database_url or psycopg2 is None:
        return 0
    scraped_default = datetime.now(timezone.utc)
    n = 0
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            for r in rows:
                raw = r.get("raw_row")
                if raw is None:
                    raw = {k: v for k, v in r.items() if k not in ("scraped_at",)}
                scraped_at = r.get("scraped_at")
                if isinstance(scraped_at, datetime):
                    sa_val = scraped_at
                elif isinstance(scraped_at, str) and scraped_at.strip():
                    try:
                        sa_val = datetime.fromisoformat(scraped_at.strip().replace("Z", "+00:00"))
                    except ValueError:
                        sa_val = scraped_default
                else:
                    sa_val = scraped_default

                # Build OCD-style contact_details array
                contact_details: List[Dict[str, str]] = []
                email = (r.get("email") or "").strip()
                if email:
                    contact_details.append({"type": "email", "value": email})
                phone = (r.get("phone") or "").strip()
                if phone:
                    contact_details.append({"type": "phone", "value": phone})

                cur.execute(
                    """
                    INSERT INTO bronze.bronze_contacts_scraped (
                        scrape_batch_id,
                        jurisdiction_id,
                        state_code,
                        ocd_id,
                        source_page_url,
                        page_classification,
                        directory_score,
                        person_name,
                        title_or_role,
                        department,
                        email,
                        phone,
                        mailing_address,
                        profile_url,
                        extraction_method,
                        contact_details,
                        contact_source,
                        raw_row,
                        scraped_at
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s
                    )
                    """,
                    (
                        scrape_batch_id,
                        jurisdiction_id,
                        (state_code or "").strip().upper()[:2],
                        ocd_id,
                        (r.get("source_page_url") or "")[:4096],
                        (r.get("page_classification") or "unknown")[:128],
                        int(r.get("directory_score") or 0),
                        (r.get("person_name") or "")[:512] or None,
                        (r.get("title_or_role") or "")[:512] or None,
                        (r.get("department") or "")[:512] or None,
                        email[:512] if email else None,
                        phone[:64] if phone else None,
                        (r.get("mailing_address") or "")[:1024] or None,
                        (r.get("profile_url") or "")[:4096] or None,
                        (r.get("extraction_method") or "")[:64] or None,
                        json.dumps(contact_details),
                        (r.get("contact_source") or "").strip()[:128] or None,
                        json.dumps(raw, default=str),
                        sa_val,
                    ),
                )
                n += 1
        conn.commit()
    finally:
        conn.close()
    return n
