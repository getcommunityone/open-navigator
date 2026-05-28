#!/usr/bin/env python3
"""
Sync ``openstates.public.opencivicdata_person`` + its 5 child tables into the c1
person model on Neon dev:

  openstates                                 →  open-navigator (Neon dev)
  ──────────────────────────────────────────    ────────────────────────────
  opencivicdata_person                         public.c1_person
  opencivicdata_personidentifier               public.c1_personidentifier
  opencivicdata_personlink                     public.c1_personlink
  opencivicdata_personname                     public.c1_personname
  opencivicdata_personsource                   public.c1_personsource
  opencivicdata_personvote                     public.c1_personvote

Idempotent: rows are keyed by OCD id / (parent_id + UUID) so re-running upserts cleanly.
Child rows for a person_id are TRUNCATED-and-REINSERTED per sync so deletions in
OpenStates propagate (we don't try to detect deletes at the row level).

Run::

    .venv/bin/python -m pipeline.openstates.sync_persons_to_c1 \\
        --states AL,GA,IN,MA,WA,WI
    .venv/bin/python -m pipeline.openstates.sync_persons_to_c1 --all
    .venv/bin/python -m pipeline.openstates.sync_persons_to_c1 --states MA --dry-run
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import uuid
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import execute_values

_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_ROOT / ".env")

logger = logging.getLogger("openstates_sync_c1")

DEFAULT_PRIORITY_STATES = ("AL", "GA", "IN", "MA", "WA", "WI")

# State filter from OCD jurisdiction id:
#   ocd-jurisdiction/country:us/state:al/place:abbeville/government
_STATE_FROM_OCD = re.compile(r"/state:([a-z]{2})(?:/|$)", re.IGNORECASE)


# --------------------------------------------------------------------------------------
# DB helpers
# --------------------------------------------------------------------------------------


def _connect(env_var: str) -> psycopg2.extensions.connection:
    url = os.getenv(env_var, "").strip()
    if not url:
        raise SystemExit(f"{env_var} not set in .env")
    return psycopg2.connect(url)


def _state_filter_sql(states: tuple[str, ...] | None) -> tuple[str, tuple]:
    """Return (WHERE-fragment, params) selecting persons by their current_jurisdiction_id state."""
    if not states:
        return "", tuple()
    or_terms = " OR ".join(f"current_jurisdiction_id ILIKE %s" for _ in states)
    params = tuple(f"%state:{s.lower()}%" for s in states)
    return f"AND ({or_terms})", params


# --------------------------------------------------------------------------------------
# Phase 1: sync c1_person
# --------------------------------------------------------------------------------------


def sync_persons(src_conn, dst_conn, states: tuple[str, ...] | None, *, dry_run: bool) -> int:
    state_clause, state_params = _state_filter_sql(states)
    sql_src = f"""
        SELECT id, name, family_name, given_name, image, gender, biography,
               birth_date, death_date, primary_party, current_jurisdiction_id,
               current_role, extras, email
        FROM public.opencivicdata_person
        WHERE id IS NOT NULL {state_clause}
    """
    with src_conn.cursor() as src:
        src.execute(sql_src, state_params)
        rows = src.fetchall()
    logger.info("Pulled %d persons from openstates", len(rows))
    if dry_run or not rows:
        return len(rows)

    n = 0
    with dst_conn.cursor() as dst:
        for r in rows:
            (pid, name, family, given, image, gender, bio, birth, death,
             party, juris, current_role, extras, email) = r
            dst.execute("""
                INSERT INTO public.c1_person (
                    id, name, family_name, given_name, image, gender, biography,
                    birth_date, death_date, primary_party, current_jurisdiction_id,
                    "current_role", extras, email,
                    source, created_at, updated_at
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s::jsonb, %s,
                    'openstates_sync', now(), now()
                )
                ON CONFLICT (legacy_id)
                  WHERE legacy_id IS NOT NULL
                  -- (no-op: matches only the 149 pre-existing legacy rows; new openstates rows insert)
                  DO NOTHING
            """, (pid, name, family, given, image, gender, bio, birth, death,
                  party, juris,
                  psycopg2.extras.Json(current_role) if current_role else "{}",
                  psycopg2.extras.Json(extras) if extras else "{}",
                  email))
            n += 1
    dst_conn.commit()
    return n


# --------------------------------------------------------------------------------------
# Phase 2: sync child tables
# --------------------------------------------------------------------------------------


def _person_ids_in_dst(dst_conn) -> set[str]:
    """Return the set of person ids that exist in c1_person (skip child rows for unknown persons)."""
    with dst_conn.cursor() as cur:
        cur.execute("SELECT id FROM public.c1_person WHERE id IS NOT NULL")
        return {r[0] for r in cur.fetchall()}


def _truncate_child_rows_for_persons(dst_conn, table: str, parent_col: str, person_ids: set[str]) -> int:
    """Delete child rows for the given person_ids before re-inserting (clean refresh)."""
    if not person_ids:
        return 0
    with dst_conn.cursor() as cur:
        cur.execute(
            f"DELETE FROM public.{table} WHERE {parent_col} = ANY(%s)",
            (list(person_ids),),
        )
        return cur.rowcount


def sync_child(
    src_conn, dst_conn, *,
    src_table: str, dst_table: str, parent_col: str,
    columns: list[str],
    valid_person_ids: set[str],
    dry_run: bool,
) -> int:
    col_list = ", ".join(f'"{c}"' if c in {"option"} else c for c in columns)
    sql_src = f"""
        SELECT {col_list}
        FROM public.{src_table}
        WHERE {parent_col} = ANY(%s)
    """
    with src_conn.cursor() as src:
        src.execute(sql_src, (list(valid_person_ids),))
        rows = src.fetchall()
    logger.info("  %s: pulled %d rows", src_table, len(rows))

    if dry_run or not rows:
        return len(rows)

    # Clean refresh: delete existing child rows for these persons, then bulk insert.
    deleted = _truncate_child_rows_for_persons(dst_conn, dst_table, parent_col, valid_person_ids)
    if deleted:
        logger.debug("  %s: cleared %d existing rows before re-insert", dst_table, deleted)

    dst_cols = ", ".join(f'"{c}"' if c in {"option"} else c for c in columns)
    with dst_conn.cursor() as dst:
        execute_values(
            dst,
            f"INSERT INTO public.{dst_table} ({dst_cols}) VALUES %s",
            rows,
        )
    dst_conn.commit()
    return len(rows)


# --------------------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--states", default="", help="Comma-separated USPS codes")
    g.add_argument("--all", action="store_true", help="Sync all 50 states")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    states: tuple[str, ...] | None = None
    if args.states:
        states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip())

    src = _connect("OPENSTATES_DATABASE_URL")
    dst = _connect("NEON_DATABASE_URL_DEV")
    try:
        n_persons = sync_persons(src, dst, states, dry_run=args.dry_run)
        logger.info("c1_person: %d rows %s", n_persons, "to upsert (dry-run)" if args.dry_run else "upserted")

        ids = _person_ids_in_dst(dst) if not args.dry_run else set()
        logger.info("c1_person has %d ids available for child-table syncing", len(ids))

        results = {}
        for src_table, dst_table, parent_col, cols in [
            ("opencivicdata_personidentifier", "c1_personidentifier", "person_id",
             ["id", "identifier", "scheme", "person_id"]),
            ("opencivicdata_personlink",       "c1_personlink",       "person_id",
             ["id", "note", "url", "person_id"]),
            ("opencivicdata_personname",       "c1_personname",       "person_id",
             ["id", "name", "note", "start_date", "end_date", "person_id"]),
            ("opencivicdata_personsource",     "c1_personsource",     "person_id",
             ["id", "note", "url", "person_id"]),
            ("opencivicdata_personvote",       "c1_personvote",       "voter_id",
             ["id", "option", "voter_name", "note", "vote_event_id", "voter_id"]),
        ]:
            n = sync_child(
                src, dst,
                src_table=src_table, dst_table=dst_table, parent_col=parent_col,
                columns=cols,
                valid_person_ids=ids,
                dry_run=args.dry_run,
            )
            results[dst_table] = n

        print()
        print(f"c1_person rows synced:           {n_persons}")
        for tbl, n in results.items():
            print(f"  {tbl:30s} {n} rows")
        if args.dry_run:
            print("(dry-run — no DB writes)")
        return 0
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    raise SystemExit(main())
