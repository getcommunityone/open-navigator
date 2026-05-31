#!/usr/bin/env python3
"""
Sync ``openstates.public.opencivicdata_person`` (plus ``personlink`` + ``personidentifier``)
into ``bronze.bronze_jurisdiction_openstates`` on Neon dev.

Source DB:  ``OPENSTATES_DATABASE_URL`` (read-only OpenStates Postgres)
Target DB:  ``NEON_DATABASE_URL_DEV``

Aggregates the two child tables into JSONB arrays per person so downstream queries
don't need cross-database joins. State filter optional but recommended (the source
table holds 22k+ persons across all 50 states).

Run::

    .venv/bin/python -m ingestion.openstates.sync_persons_to_bronze \\
        --states AL,GA,IN,MA,WA,WI

Or all states::

    .venv/bin/python -m ingestion.openstates.sync_persons_to_bronze --all

Each run inserts a fresh ``sync_batch_id``; old batches stay in place for audit.
Downstream models pick the latest batch via ``ORDER BY synced_at DESC LIMIT 1``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

_ROOT = Path(__file__).resolve().parents[5]
load_dotenv(_ROOT / ".env")

logger = logging.getLogger("openstates_sync")

DEFAULT_PRIORITY_STATES = ("AL", "GA", "IN", "MA", "WA", "WI")

# Regex to pull the 2-letter state code out of an OCD jurisdiction id:
#   ocd-jurisdiction/country:us/state:al/place:abbeville/government
#   ocd-jurisdiction/country:us/state:ma/county:barnstable/government
_STATE_FROM_OCD = re.compile(r"/state:([a-z]{2})(?:/|$)", re.IGNORECASE)


def _state_code_from_juris(juris_id: str | None) -> str | None:
    if not juris_id:
        return None
    m = _STATE_FROM_OCD.search(juris_id)
    return m.group(1).upper() if m else None


def fetch_persons(src_conn, states: tuple[str, ...] | None) -> list[dict[str, Any]]:
    """
    Fetch person rows + aggregated link/identifier arrays from the OpenStates DB.

    Aggregation is done via LEFT JOIN + jsonb_agg in a single query rather than
    fetching child tables separately — gives us one row per person ready to insert.
    """
    where = ""
    params: list[Any] = []
    if states:
        state_clauses = " OR ".join([
            "p.current_jurisdiction_id ILIKE %s" for _ in states
        ])
        where = f"WHERE ({state_clauses})"
        params = [f"%/state:{s.lower()}/%" for s in states]

    sql = f"""
        SELECT
            p.id                              AS openstates_person_id,
            p.name,
            p.given_name,
            p.family_name,
            p.gender,
            p.biography,
            p.birth_date,
            p.death_date,
            p.image,
            p.primary_party,
            p.email,
            p.current_jurisdiction_id,
            p.current_role,
            p.extras,
            p.created_at,
            p.updated_at,
            COALESCE((
                SELECT jsonb_agg(jsonb_build_object('note', l.note, 'url', l.url) ORDER BY l.url)
                FROM public.opencivicdata_personlink l
                WHERE l.person_id = p.id
            ), '[]'::jsonb) AS links,
            COALESCE((
                SELECT jsonb_agg(jsonb_build_object('scheme', i.scheme, 'identifier', i.identifier) ORDER BY i.scheme, i.identifier)
                FROM public.opencivicdata_personidentifier i
                WHERE i.person_id = p.id
            ), '[]'::jsonb) AS identifiers
        FROM public.opencivicdata_person p
        {where}
    """
    rows: list[dict[str, Any]] = []
    with src_conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        for raw in cur.fetchall():
            rec = dict(zip(cols, raw))
            rec["state_code"] = _state_code_from_juris(rec.get("current_jurisdiction_id"))
            rows.append(rec)
    return rows


def insert_into_neon(target_conn, batch_id: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    values = [
        (
            batch_id,
            r["openstates_person_id"],
            r.get("name") or "",
            r.get("given_name") or None,
            r.get("family_name") or None,
            r.get("gender") or None,
            r.get("biography") or None,
            r.get("birth_date") or None,
            r.get("death_date") or None,
            r.get("image") or None,
            r.get("primary_party") or None,
            r.get("email") or None,
            r.get("current_jurisdiction_id") or None,
            r.get("state_code") or None,
            json.dumps(r.get("current_role") or {}, default=str),
            json.dumps(r.get("extras") or {}, default=str),
            json.dumps(r.get("links") or []),
            json.dumps(r.get("identifiers") or []),
            r.get("created_at"),
            r.get("updated_at"),
        )
        for r in rows
    ]
    with target_conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO bronze.bronze_jurisdiction_openstates (
                sync_batch_id, openstates_person_id, name, given_name, family_name,
                gender, biography, birth_date, death_date, image, primary_party, email,
                current_jurisdiction_id, state_code, "current_role", extras,
                links, identifiers, source_created_at, source_updated_at
            ) VALUES %s
            """,
            values,
            template="(%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s, %s)",
            page_size=500,
        )
    target_conn.commit()
    return len(values)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--states", default=",".join(DEFAULT_PRIORITY_STATES),
                   help=f"Comma-separated state codes (default: {','.join(DEFAULT_PRIORITY_STATES)}). Ignored when --all is passed.")
    p.add_argument("--all", action="store_true",
                   help="Sync all states (no filter).")
    p.add_argument("--dry-run", action="store_true",
                   help="Fetch + summarize counts but don't write to Neon.")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    src_url = os.getenv("OPENSTATES_DATABASE_URL", "").strip()
    if not src_url:
        logger.error("OPENSTATES_DATABASE_URL is not set in .env")
        return 2
    target_url = os.getenv("NEON_DATABASE_URL_DEV", "").strip()
    if not target_url:
        logger.error("NEON_DATABASE_URL_DEV is not set in .env")
        return 2

    states: tuple[str, ...] | None
    if args.all:
        states = None
    else:
        states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip())

    batch_id = str(uuid.uuid4())
    logger.info("sync batch %s — states filter: %s", batch_id, states or "ALL")

    start = time.monotonic()
    src_conn = psycopg2.connect(src_url)
    try:
        rows = fetch_persons(src_conn, states)
    finally:
        src_conn.close()
    fetched_in = time.monotonic() - start
    logger.info("fetched %d person rows in %.1fs from OpenStates", len(rows), fetched_in)

    # Quick state breakdown for visibility
    by_state: dict[str, int] = {}
    for r in rows:
        by_state[r.get("state_code") or "?"] = by_state.get(r.get("state_code") or "?", 0) + 1
    logger.info("per-state breakdown: %s", dict(sorted(by_state.items())))

    if args.dry_run:
        sample = rows[:3]
        for s in sample:
            logger.info("sample: %s  links=%d ids=%d  juris=%s",
                        s["name"], len(s.get("links") or []), len(s.get("identifiers") or []),
                        s.get("current_jurisdiction_id"))
        return 0

    write_start = time.monotonic()
    target_conn = psycopg2.connect(target_url)
    try:
        n = insert_into_neon(target_conn, batch_id, rows)
    finally:
        target_conn.close()
    write_in = time.monotonic() - write_start
    logger.info("inserted %d rows into bronze.bronze_jurisdiction_openstates in %.1fs", n, write_in)

    print()
    print(f"Sync batch:        {batch_id}")
    print(f"Persons fetched:   {len(rows)}")
    print(f"Persons written:   {n}")
    print(f"Per-state counts:  {dict(sorted(by_state.items()))}")
    print(f"Elapsed total:     {time.monotonic() - start:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
