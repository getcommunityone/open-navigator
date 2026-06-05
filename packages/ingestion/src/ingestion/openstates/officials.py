#!/usr/bin/env python3
"""
Sync current government officials from the OpenStates ``opencivicdata_*`` tables
into ``bronze.bronze_officials_openstates`` on the dev warehouse.

Source DB:  ``OPENSTATES_DATABASE_URL`` (read-only OpenStates Postgres)
Target DB:  ``NEON_DATABASE_URL_DEV`` (dev only — never prod)

Mirrors :mod:`ingestion.openstates.bills`: a direct psycopg2 read from the
OpenStates source, one row per person×membership, batched upsert into the
warehouse, loguru logging, argparse CLI, ON CONFLICT upsert keyed on the OCD
membership id.

GRAIN: one row per current membership (person holding a role in an organization).
Unlike the legacy parquet export (export_legislators_to_gold.py) this does NOT
filter org.classification to legislative chambers — that wrongly excludes mayors
and other local officials. We keep ALL current memberships so the downstream
``public.contact_official`` mart includes mayors, council members, etc.

Current-term filter: ``rm.end_date IS NULL OR rm.end_date = '' OR
rm.end_date >= '2024-01-01'`` (OpenStates stores dates as text, so an empty
string is treated as open-ended like NULL).

Run a single small state first to validate::

    .venv/bin/python -m ingestion.openstates.officials --state al --limit 200 --dry-run
    .venv/bin/python -m ingestion.openstates.officials --state al
    .venv/bin/python -m ingestion.openstates.officials            # all states

Each run inserts a fresh ``sync_batch_id``; rows upsert ON CONFLICT
(ocd_membership_id) so re-running refreshes in place while bumping ``synced_at``.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any, Iterator

import psycopg2
from dotenv import load_dotenv
from loguru import logger
from psycopg2.extras import RealDictCursor, execute_values

_ROOT = Path(__file__).resolve().parents[5]
load_dotenv(_ROOT / ".env")

DEFAULT_BATCH_SIZE = 1000

# Current-term cutoff: a membership is "current" if it is open-ended (NULL/empty
# end_date) or ends on/after this date. OpenStates stores dates as text.
CURRENT_TERM_CUTOFF = "2024-01-01"

# Resolve the dev warehouse DSN the same way the bills loader does, walking the
# documented precedence. Dev only — never prod.
_TARGET_ENV_CHAIN = (
    "NEON_DATABASE_URL_DEV",
    "NEON_DATABASE_URL",
    "OPEN_NAVIGATOR_DATABASE_URL",
    "DATABASE_URL",
)

_DEFAULT_SOURCE_DSN = "postgresql://postgres:password@localhost:5433/openstates"

# Pull the 2-letter state code out of an OCD jurisdiction id:
#   ocd-jurisdiction/country:us/state:al/place:tuscaloosa/government
_STATE_FROM_OCD = re.compile(r"/state:([a-z]{2})(?:/|$)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Env resolution
# ---------------------------------------------------------------------------
def resolve_source_dsn() -> str:
    """OpenStates source DSN, defaulting to the documented local instance."""
    return os.getenv("OPENSTATES_DATABASE_URL", "").strip() or _DEFAULT_SOURCE_DSN


def resolve_target_dsn() -> str | None:
    """First non-empty dev warehouse DSN from the documented precedence chain."""
    for var in _TARGET_ENV_CHAIN:
        val = os.getenv(var, "").strip()
        if val:
            return val
    return None


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested without a DB)
# ---------------------------------------------------------------------------
def state_code_from_juris(juris_id: str | None) -> str | None:
    """Extract the upper-case 2-letter state code from an OCD jurisdiction id."""
    if not juris_id:
        return None
    m = _STATE_FROM_OCD.search(juris_id)
    return m.group(1).upper() if m else None


def normalize_state_arg(state: str | None) -> str | None:
    """
    Normalize a ``--state`` value to the OCD ``state:<xx>`` token fragment used
    to ILIKE-match against the jurisdiction id.

    Accepts a bare 2-letter code (``al``/``AL``), a ``state:al`` token, or a full
    OCD slug (``ocd-jurisdiction/country:us/state:al/place:.../government``).
    Returns the lower-cased 2-letter code, or ``None`` when no state could be
    parsed.
    """
    if not state:
        return None
    s = state.strip()
    if not s:
        return None
    m = _STATE_FROM_OCD.search(s)
    if m:
        return m.group(1).lower()
    s = s.lstrip("/").removeprefix("state:")
    if re.fullmatch(r"[A-Za-z]{2}", s):
        return s.lower()
    return None


def synthesize_membership_id(rec: dict[str, Any]) -> str:
    """
    Deterministic fallback membership id when the source row has none.

    OpenStates memberships always carry a stable ``ocd-membership/<uuid>`` id, but
    we guard against a null/blank id by hashing the natural key
    (person|organization|role|post) so the PK / conflict key is never NULL.
    """
    key = "|".join(
        str(rec.get(k) or "")
        for k in ("ocd_person_id", "ocd_organization_id", "role", "post_id")
    )
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return f"ocd-membership/synth-{digest}"


def shape_official_row(rec: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a raw joined source record into the canonical official row shape.

    Pure: takes the dict produced by the SELECT (person ⋈ membership ⋈
    organization LEFT JOIN post) and returns the cleaned dict whose keys map 1:1
    onto ``bronze_officials_openstates`` columns. One row per person×membership.
    Safe to unit-test with fixtures.
    """
    juris = rec.get("ocd_jurisdiction_id")
    membership_id = (rec.get("ocd_membership_id") or "").strip()
    if not membership_id:
        membership_id = synthesize_membership_id(rec)
    return {
        "ocd_membership_id": membership_id,
        "ocd_person_id": (rec.get("ocd_person_id") or None),
        "full_name": (rec.get("full_name") or None),
        "party": (rec.get("party") or None),
        "role": (rec.get("role") or None),
        "district": (rec.get("district") or None),
        "ocd_organization_id": (rec.get("ocd_organization_id") or None),
        "organization_name": (rec.get("organization_name") or None),
        "organization_classification": (rec.get("organization_classification") or None),
        "ocd_jurisdiction_id": juris or None,
        "state_code": state_code_from_juris(juris),
        "email": (rec.get("email") or None),
        "image": (rec.get("image") or None),
        "start_date": (rec.get("start_date") or None),
        "end_date": (rec.get("end_date") or None),
        "source_created_at": rec.get("source_created_at"),
        "source_updated_at": rec.get("source_updated_at"),
    }


def build_values_tuple(batch_id: str, row: dict[str, Any]) -> tuple[Any, ...]:
    """
    Turn a shaped official row + batch id into the positional tuple matching the
    INSERT column order. Kept next to ``_INSERT_COLUMNS`` so they stay in lockstep
    and the same logic is exercised by unit tests.
    """
    return (
        batch_id,
        row["ocd_membership_id"],
        row.get("ocd_person_id"),
        row.get("full_name"),
        row.get("party"),
        row.get("role"),
        row.get("district"),
        row.get("ocd_organization_id"),
        row.get("organization_name"),
        row.get("organization_classification"),
        row.get("ocd_jurisdiction_id"),
        row.get("state_code"),
        row.get("email"),
        row.get("image"),
        row.get("start_date"),
        row.get("end_date"),
        row.get("source_created_at"),
        row.get("source_updated_at"),
    )


# INSERT column order — kept next to build_values_tuple so they stay in lockstep.
_INSERT_COLUMNS = (
    "sync_batch_id",
    "ocd_membership_id",
    "ocd_person_id",
    "full_name",
    "party",
    "role",
    "district",
    "ocd_organization_id",
    "organization_name",
    "organization_classification",
    "ocd_jurisdiction_id",
    "state_code",
    "email",
    "image",
    "start_date",
    "end_date",
    "source_created_at",
    "source_updated_at",
)

_INSERT_TEMPLATE = (
    "(%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


# ---------------------------------------------------------------------------
# Schema / table management
# ---------------------------------------------------------------------------
CREATE_TABLE_SQL = """
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_officials_openstates (
    id                           BIGSERIAL PRIMARY KEY,
    sync_batch_id                UUID NOT NULL,
    ocd_membership_id            TEXT NOT NULL,
    ocd_person_id                TEXT,
    full_name                    TEXT,
    party                        TEXT,
    role                         TEXT,
    district                     TEXT,
    ocd_organization_id          TEXT,
    organization_name            TEXT,
    organization_classification  TEXT,
    ocd_jurisdiction_id          TEXT,
    state_code                   CHAR(2),
    email                        TEXT,
    image                        TEXT,
    start_date                   TEXT,
    end_date                     TEXT,
    source_created_at            TIMESTAMPTZ,
    source_updated_at            TIMESTAMPTZ,
    synced_at                    TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_bronze_officials_openstates_membership
    ON bronze.bronze_officials_openstates (ocd_membership_id);
CREATE INDEX IF NOT EXISTS idx_bronze_officials_openstates_person
    ON bronze.bronze_officials_openstates (ocd_person_id);
CREATE INDEX IF NOT EXISTS idx_bronze_officials_openstates_juris
    ON bronze.bronze_officials_openstates (ocd_jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bronze_officials_openstates_state
    ON bronze.bronze_officials_openstates (state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_officials_openstates_role
    ON bronze.bronze_officials_openstates (role);
CREATE INDEX IF NOT EXISTS idx_bronze_officials_openstates_batch
    ON bronze.bronze_officials_openstates (sync_batch_id);
"""


def ensure_target_table(target_conn) -> None:
    with target_conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    target_conn.commit()


# ---------------------------------------------------------------------------
# Source query construction
# ---------------------------------------------------------------------------
def build_fetch_sql(state: str | None) -> tuple[str, list[Any]]:
    """
    Assemble the streaming SELECT over person ⋈ membership ⋈ organization LEFT
    JOIN post, filtered to CURRENT memberships across ALL organization
    classifications (mayors/council included). Returns (sql, params).
    """
    where: list[str] = [
        "(rm.end_date IS NULL OR rm.end_date = '' OR rm.end_date >= %s)"
    ]
    params: list[Any] = [CURRENT_TERM_CUTOFF]

    state_token = normalize_state_arg(state)
    if state_token:
        where.append("org.jurisdiction_id ILIKE %s")
        params.append(f"%/state:{state_token}/%")

    where_sql = "WHERE " + " AND ".join(where)

    sql = f"""
        SELECT
            rm.id                       AS ocd_membership_id,
            p.id                        AS ocd_person_id,
            p.name                      AS full_name,
            p.primary_party             AS party,
            rm.role                     AS role,
            post.label                  AS district,
            org.id                      AS ocd_organization_id,
            org.name                    AS organization_name,
            org.classification          AS organization_classification,
            org.jurisdiction_id         AS ocd_jurisdiction_id,
            p.email                     AS email,
            p.image                     AS image,
            rm.start_date               AS start_date,
            rm.end_date                 AS end_date,
            rm.created_at               AS source_created_at,
            rm.updated_at               AS source_updated_at
        FROM public.opencivicdata_membership rm
        JOIN public.opencivicdata_person p
            ON p.id = rm.person_id
        JOIN public.opencivicdata_organization org
            ON org.id = rm.organization_id
        LEFT JOIN public.opencivicdata_post post
            ON post.id = rm.post_id
        {where_sql}
        ORDER BY rm.id
    """
    return sql, params


def iter_source_officials(
    src_conn,
    state: str | None,
    limit: int | None,
    fetch_size: int = 2000,
) -> Iterator[dict[str, Any]]:
    """
    Stream shaped official rows from the source through a server-side cursor.
    A RealDictCursor yields each row as a dict keyed by column name so we never
    touch ``cur.description`` (a server-side named cursor leaves it ``None`` until
    the first fetch).
    """
    sql, params = build_fetch_sql(state)
    if limit:
        sql = sql + "\n        LIMIT %s"
        params = [*params, limit]

    cur = src_conn.cursor(
        name="openstates_officials_stream", cursor_factory=RealDictCursor
    )
    cur.itersize = fetch_size
    try:
        cur.execute(sql, params)
        for raw in cur:
            yield shape_official_row(dict(raw))
    finally:
        cur.close()


# ---------------------------------------------------------------------------
# Target write
# ---------------------------------------------------------------------------
def upsert_batch(target_conn, batch_id: str, rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    values = [build_values_tuple(batch_id, r) for r in rows]
    cols_sql = ", ".join(_INSERT_COLUMNS)
    with target_conn.cursor() as cur:
        execute_values(
            cur,
            f"""
            INSERT INTO bronze.bronze_officials_openstates ({cols_sql})
            VALUES %s
            ON CONFLICT (ocd_membership_id) DO UPDATE SET
                sync_batch_id               = EXCLUDED.sync_batch_id,
                ocd_person_id               = EXCLUDED.ocd_person_id,
                full_name                   = EXCLUDED.full_name,
                party                       = EXCLUDED.party,
                role                        = EXCLUDED.role,
                district                    = EXCLUDED.district,
                ocd_organization_id         = EXCLUDED.ocd_organization_id,
                organization_name           = EXCLUDED.organization_name,
                organization_classification = EXCLUDED.organization_classification,
                ocd_jurisdiction_id         = EXCLUDED.ocd_jurisdiction_id,
                state_code                  = EXCLUDED.state_code,
                email                       = EXCLUDED.email,
                image                       = EXCLUDED.image,
                start_date                  = EXCLUDED.start_date,
                end_date                    = EXCLUDED.end_date,
                source_created_at           = EXCLUDED.source_created_at,
                source_updated_at           = EXCLUDED.source_updated_at,
                synced_at                   = CURRENT_TIMESTAMP
            """,
            values,
            template=_INSERT_TEMPLATE,
            page_size=500,
        )
    target_conn.commit()
    return len(values)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument(
        "--state",
        default=None,
        help="2-letter state code or OCD state slug (e.g. 'al' or 'state:al'); "
        "filters officials by their organization's OCD jurisdiction id.",
    )
    p.add_argument("--limit", type=int, default=None, help="Cap number of rows.")
    p.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"Rows per upsert batch (default {DEFAULT_BATCH_SIZE}).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Stream + summarize counts but don't write to the warehouse.",
    )
    args = p.parse_args(argv)

    if args.state and normalize_state_arg(args.state) is None:
        logger.error("could not parse a 2-letter state from --state {!r}", args.state)
        return 2

    src_url = resolve_source_dsn()
    target_url = resolve_target_dsn()
    if not args.dry_run and not target_url:
        logger.error(
            "no dev warehouse DSN set (tried {})", ", ".join(_TARGET_ENV_CHAIN)
        )
        return 2

    batch_id = str(uuid.uuid4())
    logger.info(
        "sync batch {} — state={} limit={} batch_size={}",
        batch_id,
        normalize_state_arg(args.state) or "ALL",
        args.limit or "ALL",
        args.batch_size,
    )

    start = time.monotonic()
    src_conn = psycopg2.connect(src_url)
    target_conn = None
    fetched = 0
    written = 0
    mayors = 0
    by_state: dict[str, int] = {}
    sample_mayors: list[dict[str, Any]] = []
    try:
        if not args.dry_run:
            target_conn = psycopg2.connect(target_url)
            ensure_target_table(target_conn)

        batch: list[dict[str, Any]] = []
        for row in iter_source_officials(src_conn, args.state, args.limit):
            fetched += 1
            sc = row.get("state_code") or "?"
            by_state[sc] = by_state.get(sc, 0) + 1
            if (row.get("role") or "").lower() == "mayor":
                mayors += 1
                if len(sample_mayors) < 5:
                    sample_mayors.append(row)
            batch.append(row)
            if len(batch) >= args.batch_size:
                if not args.dry_run:
                    written += upsert_batch(target_conn, batch_id, batch)
                batch = []
                if fetched % (args.batch_size * 10) == 0:
                    logger.info(
                        "…streamed {:,} officials (written {:,})", fetched, written
                    )
        if batch and not args.dry_run:
            written += upsert_batch(target_conn, batch_id, batch)
    finally:
        src_conn.close()
        if target_conn is not None:
            target_conn.close()

    elapsed = time.monotonic() - start
    for s in sample_mayors:
        logger.info(
            "mayor sample: {} — {} ({}) juris={}",
            s.get("full_name"),
            s.get("organization_name"),
            s.get("state_code"),
            s.get("ocd_jurisdiction_id"),
        )

    if args.dry_run:
        logger.success(
            "DRY RUN: would write {:,} officials ({:,} mayors; per-state: {}) "
            "in {:.1f}s",
            fetched,
            mayors,
            dict(sorted(by_state.items())),
            elapsed,
        )
    else:
        logger.success(
            "upserted {:,} officials (fetched {:,}, {:,} mayors, per-state: {}) "
            "into bronze.bronze_officials_openstates in {:.1f}s",
            written,
            fetched,
            mayors,
            dict(sorted(by_state.items())),
            elapsed,
        )

    print()
    print(f"Sync batch:        {batch_id}")
    print(f"Officials fetched: {fetched:,}")
    print(f"Officials written: {written:,}")
    print(f"Mayors:            {mayors:,}")
    print(f"Per-state counts:  {dict(sorted(by_state.items()))}")
    print(f"Elapsed total:     {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
