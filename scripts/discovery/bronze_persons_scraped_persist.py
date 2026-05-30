"""
Insert rows into ``bronze.bronze_persons_scraped`` (Neon migration 035 + 043).

Column names align with OpenCivicData Popolo:
- ``name``         (Popolo Person.name)         — was ``person_name``
- ``role``         (Popolo Membership.role)     — was ``title_or_role``
- ``organization`` (Popolo Membership.organization) — was ``department``

A back-compat thin wrapper ``insert_bronze_contacts_scraped`` is exported under the
old name so callers can migrate gradually; it accepts either the old keys
(``person_name``/``title_or_role``/``department``) or the new keys (``name``/``role``/
``organization``) on incoming row dicts and writes to the renamed table.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List

try:
    import psycopg2
except ModuleNotFoundError:  # pragma: no cover
    psycopg2 = None  # type: ignore[misc, assignment]

from scripts.jurisdictions.jurisdiction_id import ensure_canonical_jurisdiction_id


def insert_bronze_persons_scraped(
    database_url: str,
    *,
    scrape_batch_id: str,
    jurisdiction_id: str,
    state_code: str,
    ocd_id: str | None = None,
    rows: List[Dict[str, Any]],
) -> int:
    """
    Bulk-insert person rows into ``bronze.bronze_persons_scraped``. Returns rows inserted.

    Each ``row`` may include EITHER the OCD-aligned keys (``name``, ``role``,
    ``organization``) OR the legacy keys (``person_name``, ``title_or_role``,
    ``department``). Plus: ``source_page_url``, ``page_classification``,
    ``directory_score``, ``email``, ``phone``, ``mailing_address``, ``profile_url``,
    ``extraction_method``, ``contact_source``, ``raw_row`` (dict), ``scraped_at``
    (ISO str optional).

    ``contact_details`` is auto-built from ``email``/``phone`` in OCD Popolo array form.
    """
    if not rows or not database_url or psycopg2 is None:
        return 0

    # Canonicalize the jurisdiction_id at the write boundary so legacy
    # ``{type}_{geoid}`` ids (e.g. ``county_55091``) are stored as the name-slug
    # form (``pepin_55091``) used by int_jurisdictions. Already-canonical ids pass
    # through without a DB lookup; legacy ids self-heal via a bronze GEOID lookup.
    jurisdiction_id = (
        ensure_canonical_jurisdiction_id(jurisdiction_id, database_url=database_url)
        or jurisdiction_id
    )

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

                # OCD-aligned keys preferred; fall back to the legacy ones.
                name = r.get("name") or r.get("person_name")
                role = r.get("role") or r.get("title_or_role")
                organization = r.get("organization") or r.get("department")

                # Build OCD-style contact_details array.
                contact_details: List[Dict[str, str]] = []
                email = (r.get("email") or "").strip()
                if email:
                    contact_details.append({"type": "email", "value": email})
                phone = (r.get("phone") or "").strip()
                if phone:
                    contact_details.append({"type": "voice", "value": phone})
                mailing = (r.get("mailing_address") or "").strip()
                if mailing:
                    contact_details.append({"type": "address", "value": mailing})

                biography = (r.get("biography") or "").strip()
                image_url = (
                    (r.get("image") or r.get("profile_image_url") or "").strip()
                )[:4096] or None

                cur.execute(
                    """
                    INSERT INTO bronze.bronze_persons_scraped (
                        scrape_batch_id,
                        jurisdiction_id,
                        state_code,
                        ocd_id,
                        source_page_url,
                        page_classification,
                        directory_score,
                        name,
                        role,
                        organization,
                        email,
                        phone,
                        mailing_address,
                        profile_url,
                        extraction_method,
                        contact_details,
                        contact_source,
                        raw_row,
                        scraped_at,
                        biography,
                        image
                    ) VALUES (
                        %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s::jsonb, %s,
                        %s, %s
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
                        (str(name) if name else "")[:512] or None,
                        (str(role) if role else "")[:512] or None,
                        (str(organization) if organization else "")[:512] or None,
                        email[:512] if email else None,
                        phone[:64] if phone else None,
                        mailing[:1024] if mailing else None,
                        (r.get("profile_url") or "")[:4096] or None,
                        (r.get("extraction_method") or "")[:64] or None,
                        json.dumps(contact_details),
                        (r.get("contact_source") or "").strip()[:128] or None,
                        json.dumps(raw, default=str),
                        sa_val,
                        biography or None,
                        image_url,
                    ),
                )
                n += 1
        conn.commit()
    finally:
        conn.close()
    return n


# Back-compat alias so callers that still import the old function name keep working
# during the migration period. New code should call ``insert_bronze_persons_scraped``.
insert_bronze_contacts_scraped = insert_bronze_persons_scraped
