#!/usr/bin/env python3
"""
Sync ``openstates.public.opencivicdata_bill`` (plus its session, sponsorships,
abstracts, titles, and identifier child tables) into
``bronze.bronze_bills_openstates`` on the dev warehouse.

Source DB:  ``OPENSTATES_DATABASE_URL`` (read-only OpenStates Postgres)
Target DB:  ``NEON_DATABASE_URL_DEV`` (dev only — never prod)

Mirrors :mod:`ingestion.openstates.sync_persons_to_bronze`: a direct psycopg2
read from the OpenStates source, child tables aggregated into JSONB arrays on the
parent bill row, batched upsert into the warehouse, loguru logging, argparse CLI.

The bill table is large (~1.55M bills, ~7.3M sponsorships), so reads stream
through a server-side cursor and writes go out in ``--batch-size`` chunks.

Run a single small state first to validate::

    .venv/bin/python -m ingestion.openstates.bills --state al --limit 500 --dry-run
    .venv/bin/python -m ingestion.openstates.bills --state al

Each run inserts a fresh ``sync_batch_id``; rows upsert ON CONFLICT (ocd_bill_id)
so re-running refreshes in place while bumping ``synced_at``.
"""

from __future__ import annotations

import argparse
import json
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

# Resolve the dev warehouse DSN the same way the persons loader's environment
# does, walking the documented precedence. Dev only — never prod.
_TARGET_ENV_CHAIN = (
    "NEON_DATABASE_URL_DEV",
    "NEON_DATABASE_URL",
    "OPEN_NAVIGATOR_DATABASE_URL",
    "DATABASE_URL",
)

_DEFAULT_SOURCE_DSN = "postgresql://postgres:password@localhost:5433/openstates"

# Pull the 2-letter state code out of an OCD jurisdiction id:
#   ocd-jurisdiction/country:us/state:al/government
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
    OCD slug (``ocd-jurisdiction/country:us/state:al/government``). Returns the
    lower-cased 2-letter code, or ``None`` when no state could be parsed.
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


def shape_bill_row(rec: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a raw joined source record into the canonical bill row shape.

    Pure: takes the dict produced by the SELECT (bill columns + session columns +
    the aggregated JSONB child arrays) and returns the cleaned dict whose keys map
    1:1 onto ``bronze_bills_openstates`` columns. Safe to unit-test with fixtures.
    """
    juris = rec.get("ocd_jurisdiction_id")
    return {
        "ocd_bill_id": rec["ocd_bill_id"],
        "identifier": rec.get("identifier") or None,
        "title": rec.get("title") or None,
        "classification": list(rec.get("classification") or []),
        "subject": list(rec.get("subject") or []),
        "from_organization_id": rec.get("from_organization_id") or None,
        "legislative_session_id": rec.get("legislative_session_id") or None,
        "session_identifier": rec.get("session_identifier") or None,
        "session_name": rec.get("session_name") or None,
        "ocd_jurisdiction_id": juris or None,
        "state_code": state_code_from_juris(juris),
        "first_action_date": rec.get("first_action_date") or None,
        "latest_action_date": rec.get("latest_action_date") or None,
        "latest_action_description": rec.get("latest_action_description") or None,
        "latest_passage_date": rec.get("latest_passage_date") or None,
        "citations": rec.get("citations") or [],
        "extras": rec.get("extras") or {},
        "sponsorships": rec.get("sponsorships") or [],
        "abstracts": rec.get("abstracts") or [],
        "titles": rec.get("titles") or [],
        "identifiers": rec.get("identifiers") or [],
        "source_created_at": rec.get("source_created_at"),
        "source_updated_at": rec.get("source_updated_at"),
    }


def build_values_tuple(batch_id: str, row: dict[str, Any]) -> tuple[Any, ...]:
    """
    Turn a shaped bill row + batch id into the positional tuple matching the
    INSERT column order. JSONB columns are pre-serialized to text here so the
    same logic is exercised by unit tests.
    """
    return (
        batch_id,
        row["ocd_bill_id"],
        row.get("identifier"),
        row.get("title"),
        json.dumps(row.get("classification") or [], default=str),
        json.dumps(row.get("subject") or [], default=str),
        row.get("from_organization_id"),
        row.get("legislative_session_id"),
        row.get("session_identifier"),
        row.get("session_name"),
        row.get("ocd_jurisdiction_id"),
        row.get("state_code"),
        row.get("first_action_date"),
        row.get("latest_action_date"),
        row.get("latest_action_description"),
        row.get("latest_passage_date"),
        json.dumps(row.get("citations") or [], default=str),
        json.dumps(row.get("extras") or {}, default=str),
        json.dumps(row.get("sponsorships") or [], default=str),
        json.dumps(row.get("abstracts") or [], default=str),
        json.dumps(row.get("titles") or [], default=str),
        json.dumps(row.get("identifiers") or [], default=str),
        row.get("source_created_at"),
        row.get("source_updated_at"),
    )


# INSERT column order — kept next to build_values_tuple so they stay in lockstep.
_INSERT_COLUMNS = (
    "sync_batch_id",
    "ocd_bill_id",
    "identifier",
    "title",
    "classification",
    "subject",
    "from_organization_id",
    "legislative_session_id",
    "session_identifier",
    "session_name",
    "ocd_jurisdiction_id",
    "state_code",
    "first_action_date",
    "latest_action_date",
    "latest_action_description",
    "latest_passage_date",
    "citations",
    "extras",
    "sponsorships",
    "abstracts",
    "titles",
    "identifiers",
    "source_created_at",
    "source_updated_at",
)

_INSERT_TEMPLATE = (
    "(%s::uuid, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s, %s, %s, "
    "%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, %s::jsonb, "
    "%s::jsonb, %s, %s)"
)


# ---------------------------------------------------------------------------
# Schema / table management
# ---------------------------------------------------------------------------
CREATE_TABLE_SQL = """
CREATE SCHEMA IF NOT EXISTS bronze;

CREATE TABLE IF NOT EXISTS bronze.bronze_bills_openstates (
    id                          BIGSERIAL PRIMARY KEY,
    sync_batch_id               UUID NOT NULL,
    ocd_bill_id                 TEXT NOT NULL,
    identifier                  TEXT,
    title                       TEXT,
    classification              JSONB NOT NULL DEFAULT '[]'::JSONB,
    subject                     JSONB NOT NULL DEFAULT '[]'::JSONB,
    from_organization_id        TEXT,
    legislative_session_id      TEXT,
    session_identifier          TEXT,
    session_name                TEXT,
    ocd_jurisdiction_id         TEXT,
    state_code                  CHAR(2),
    first_action_date           TEXT,
    latest_action_date          TEXT,
    latest_action_description   TEXT,
    latest_passage_date         TEXT,
    citations                   JSONB NOT NULL DEFAULT '[]'::JSONB,
    extras                      JSONB NOT NULL DEFAULT '{}'::JSONB,
    sponsorships                JSONB NOT NULL DEFAULT '[]'::JSONB,
    abstracts                   JSONB NOT NULL DEFAULT '[]'::JSONB,
    titles                      JSONB NOT NULL DEFAULT '[]'::JSONB,
    identifiers                 JSONB NOT NULL DEFAULT '[]'::JSONB,
    source_created_at           TIMESTAMPTZ,
    source_updated_at           TIMESTAMPTZ,
    synced_at                   TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_bronze_bills_openstates_ocd_bill_id
    ON bronze.bronze_bills_openstates (ocd_bill_id);
CREATE INDEX IF NOT EXISTS idx_bronze_bills_openstates_juris
    ON bronze.bronze_bills_openstates (ocd_jurisdiction_id);
CREATE INDEX IF NOT EXISTS idx_bronze_bills_openstates_session
    ON bronze.bronze_bills_openstates (legislative_session_id);
CREATE INDEX IF NOT EXISTS idx_bronze_bills_openstates_state
    ON bronze.bronze_bills_openstates (state_code);
CREATE INDEX IF NOT EXISTS idx_bronze_bills_openstates_batch
    ON bronze.bronze_bills_openstates (sync_batch_id);
"""


def ensure_target_table(target_conn) -> None:
    with target_conn.cursor() as cur:
        cur.execute(CREATE_TABLE_SQL)
    target_conn.commit()


def _table_columns(conn, table: str) -> set[str]:
    """Return the set of column names for ``public.<table>``, empty if absent."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            (table,),
        )
        return {r[0] for r in cur.fetchall()}


# ---------------------------------------------------------------------------
# Source query construction
# ---------------------------------------------------------------------------
def _child_agg_subquery(present_cols: set[str], table: str, fields: list[str]) -> str:
    """
    Build a correlated ``jsonb_agg`` subquery for a child table, but only over
    the fields that actually exist. Returns ``'[]'::jsonb AS <alias>`` when the
    table/fields are missing so the column is always present and safe.
    """
    alias = {
        "opencivicdata_billabstract": "abstracts",
        "opencivicdata_billtitle": "titles",
        "opencivicdata_billidentifier": "identifiers",
    }[table]
    usable = [f for f in fields if f in present_cols]
    if not usable:
        logger.warning(
            "child table public.{} missing or has no expected columns; "
            "emitting empty {} array",
            table,
            alias,
        )
        return f"'[]'::jsonb AS {alias}"
    pairs = ", ".join(f"'{f}', c.{f}" for f in usable)
    return f"""COALESCE((
            SELECT jsonb_agg(jsonb_build_object({pairs}))
            FROM public.{table} c
            WHERE c.bill_id = b.id
        ), '[]'::jsonb) AS {alias}"""


def build_fetch_sql(src_conn, state: str | None, session: str | None) -> tuple[str, list[Any]]:
    """
    Assemble the streaming SELECT over bills + session + child aggregates,
    adapting to whichever child tables exist. Returns (sql, params).
    """
    where: list[str] = []
    params: list[Any] = []
    state_token = normalize_state_arg(state)
    if state_token:
        where.append("ls.jurisdiction_id ILIKE %s")
        params.append(f"%/state:{state_token}/%")
    if session:
        where.append("ls.identifier = %s")
        params.append(session)
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""

    abstract_cols = _table_columns(src_conn, "opencivicdata_billabstract")
    title_cols = _table_columns(src_conn, "opencivicdata_billtitle")
    identifier_cols = _table_columns(src_conn, "opencivicdata_billidentifier")

    abstracts_sq = _child_agg_subquery(
        abstract_cols, "opencivicdata_billabstract", ["abstract", "note"]
    )
    titles_sq = _child_agg_subquery(
        title_cols, "opencivicdata_billtitle", ["title", "note"]
    )
    identifiers_sq = _child_agg_subquery(
        identifier_cols, "opencivicdata_billidentifier", ["identifier"]
    )

    sql = f"""
        SELECT
            b.id                              AS ocd_bill_id,
            b.identifier                      AS identifier,
            b.title                           AS title,
            b.classification                  AS classification,
            b.subject                         AS subject,
            b.from_organization_id            AS from_organization_id,
            b.legislative_session_id          AS legislative_session_id,
            ls.identifier                     AS session_identifier,
            ls.name                           AS session_name,
            ls.jurisdiction_id                AS ocd_jurisdiction_id,
            b.first_action_date               AS first_action_date,
            b.latest_action_date              AS latest_action_date,
            b.latest_action_description       AS latest_action_description,
            b.latest_passage_date             AS latest_passage_date,
            b.citations                       AS citations,
            b.extras                          AS extras,
            b.created_at                      AS source_created_at,
            b.updated_at                      AS source_updated_at,
            COALESCE((
                SELECT jsonb_agg(jsonb_build_object(
                    'id', s.id,
                    'name', s.name,
                    'entity_type', s.entity_type,
                    'primary', s."primary",
                    'classification', s.classification,
                    'person_id', s.person_id,
                    'organization_id', s.organization_id
                ))
                FROM public.opencivicdata_billsponsorship s
                WHERE s.bill_id = b.id
            ), '[]'::jsonb) AS sponsorships,
            {abstracts_sq},
            {titles_sq},
            {identifiers_sq}
        FROM public.opencivicdata_bill b
        LEFT JOIN public.opencivicdata_legislativesession ls
            ON ls.id = b.legislative_session_id
        {where_sql}
        ORDER BY b.id
    """
    return sql, params


def iter_source_bills(
    src_conn,
    state: str | None,
    session: str | None,
    limit: int | None,
    fetch_size: int = 2000,
) -> Iterator[dict[str, Any]]:
    """
    Stream shaped bill rows from the source through a server-side cursor so we
    never materialize 1.5M rows in memory at once.
    """
    sql, params = build_fetch_sql(src_conn, state, session)
    if limit:
        sql = sql + "\n        LIMIT %s"
        params = [*params, limit]

    # Named cursor => server-side; itersize controls round-trip batching.
    # A RealDictCursor yields each row as a dict keyed by column name, so we
    # never touch ``cur.description`` — which a server-side named cursor leaves
    # as ``None`` until the first row is fetched (the statement isn't actually
    # executed server-side until then).
    cur = src_conn.cursor(name="openstates_bills_stream", cursor_factory=RealDictCursor)
    cur.itersize = fetch_size
    try:
        cur.execute(sql, params)
        for raw in cur:
            yield shape_bill_row(dict(raw))
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
            INSERT INTO bronze.bronze_bills_openstates ({cols_sql})
            VALUES %s
            ON CONFLICT (ocd_bill_id) DO UPDATE SET
                sync_batch_id             = EXCLUDED.sync_batch_id,
                identifier                = EXCLUDED.identifier,
                title                     = EXCLUDED.title,
                classification            = EXCLUDED.classification,
                subject                   = EXCLUDED.subject,
                from_organization_id      = EXCLUDED.from_organization_id,
                legislative_session_id    = EXCLUDED.legislative_session_id,
                session_identifier        = EXCLUDED.session_identifier,
                session_name              = EXCLUDED.session_name,
                ocd_jurisdiction_id       = EXCLUDED.ocd_jurisdiction_id,
                state_code                = EXCLUDED.state_code,
                first_action_date         = EXCLUDED.first_action_date,
                latest_action_date        = EXCLUDED.latest_action_date,
                latest_action_description = EXCLUDED.latest_action_description,
                latest_passage_date       = EXCLUDED.latest_passage_date,
                citations                 = EXCLUDED.citations,
                extras                    = EXCLUDED.extras,
                sponsorships              = EXCLUDED.sponsorships,
                abstracts                 = EXCLUDED.abstracts,
                titles                    = EXCLUDED.titles,
                identifiers               = EXCLUDED.identifiers,
                source_created_at         = EXCLUDED.source_created_at,
                source_updated_at         = EXCLUDED.source_updated_at,
                synced_at                 = CURRENT_TIMESTAMP
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
        "filters bills by their session's OCD jurisdiction id.",
    )
    p.add_argument(
        "--session",
        default=None,
        help="Filter to a single legislative session identifier (e.g. '2023rs').",
    )
    p.add_argument("--limit", type=int, default=None, help="Cap number of bills.")
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
        "sync batch {} — state={} session={} limit={} batch_size={}",
        batch_id,
        normalize_state_arg(args.state) or "ALL",
        args.session or "ALL",
        args.limit or "ALL",
        args.batch_size,
    )

    start = time.monotonic()
    src_conn = psycopg2.connect(src_url)
    target_conn = None
    fetched = 0
    written = 0
    by_state: dict[str, int] = {}
    sample: list[dict[str, Any]] = []
    try:
        if not args.dry_run:
            target_conn = psycopg2.connect(target_url)
            ensure_target_table(target_conn)

        batch: list[dict[str, Any]] = []
        for row in iter_source_bills(src_conn, args.state, args.session, args.limit):
            fetched += 1
            sc = row.get("state_code") or "?"
            by_state[sc] = by_state.get(sc, 0) + 1
            if len(sample) < 3:
                sample.append(row)
            batch.append(row)
            if len(batch) >= args.batch_size:
                if not args.dry_run:
                    written += upsert_batch(target_conn, batch_id, batch)
                batch = []
                if fetched % (args.batch_size * 10) == 0:
                    logger.info("…streamed {:,} bills (written {:,})", fetched, written)
        if batch and not args.dry_run:
            written += upsert_batch(target_conn, batch_id, batch)
    finally:
        src_conn.close()
        if target_conn is not None:
            target_conn.close()

    elapsed = time.monotonic() - start
    for s in sample:
        logger.info(
            "sample: {} '{}'  sponsors={} abstracts={} titles={} ids={} juris={}",
            s.get("identifier"),
            (s.get("title") or "")[:60],
            len(s.get("sponsorships") or []),
            len(s.get("abstracts") or []),
            len(s.get("titles") or []),
            len(s.get("identifiers") or []),
            s.get("ocd_jurisdiction_id"),
        )

    if args.dry_run:
        logger.success(
            "DRY RUN: would write {:,} bills (per-state: {}) in {:.1f}s",
            fetched,
            dict(sorted(by_state.items())),
            elapsed,
        )
    else:
        logger.success(
            "upserted {:,} bills (fetched {:,}, per-state: {}) into "
            "bronze.bronze_bills_openstates in {:.1f}s",
            written,
            fetched,
            dict(sorted(by_state.items())),
            elapsed,
        )

    print()
    print(f"Sync batch:       {batch_id}")
    print(f"Bills fetched:    {fetched:,}")
    print(f"Bills written:    {written:,}")
    print(f"Per-state counts: {dict(sorted(by_state.items()))}")
    print(f"Elapsed total:    {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
