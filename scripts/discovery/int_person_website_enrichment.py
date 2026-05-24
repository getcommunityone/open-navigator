#!/usr/bin/env python3
"""
Intermediate enrichment: extend ``bronze.bronze_persons_scraped`` rows with the URLs
known to OpenStates for the same person.

For every scraped person row that doesn't already have an ``openstates_person_id``,
try to match against the latest sync of ``bronze.bronze_jurisdiction_openstates``
(loaded by ``scripts/datasources/openstates/sync_persons_to_bronze``). When a match
is found, stamp:

- ``openstates_person_id`` (the ocd-person/<UUID> join key)
- ``biography``, ``given_name``, ``family_name``, ``gender``, ``image``,
  ``primary_party`` (only when the scraped row's value is null — never overwrite)
- ``links`` — full deduped JSONB array of {note, url} from OpenStates personlink
- ``identifiers`` — full deduped JSONB array of {scheme, identifier}

Matching strategy (in order of trust):

1. **Email**: exact case-insensitive email match within the same state.
2. **Name + state**: case-insensitive full-name match (normalized, honorifics
   stripped) when the scraped row has both a name and a state_code AND there's
   exactly one OpenStates match in that state.

Run::

    .venv/bin/python -m scripts.discovery.int_person_website_enrichment
    .venv/bin/python -m scripts.discovery.int_person_website_enrichment --states MA
    .venv/bin/python -m scripts.discovery.int_person_website_enrichment --dry-run

Idempotent — re-running only touches rows still missing ``openstates_person_id``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_ROOT / ".env")

logger = logging.getLogger("int_person_enrich")

DEFAULT_PRIORITY_STATES = ("AL", "GA", "IN", "MA", "WA", "WI")

_HONORIFIC_RE = re.compile(
    r"\b(?:mr|mrs|ms|miss|dr|rev|hon|sen|rep|councilor|councilman|councilwoman|"
    r"commissioner|mayor|sheriff|attorney|esq|jr|sr|ii|iii|iv)\.?\b",
    re.IGNORECASE,
)


def _normalize_name(name: str | None) -> str:
    if not name:
        return ""
    s = name.lower().strip()
    s = re.sub(r"[.,'’]", "", s)            # punctuation
    s = _HONORIFIC_RE.sub("", s)                  # mr / dr / commissioner / jr / iii / …
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _latest_sync_batch(conn) -> str | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT sync_batch_id FROM bronze.bronze_jurisdiction_openstates "
            "ORDER BY synced_at DESC LIMIT 1"
        )
        row = cur.fetchone()
    return row[0] if row else None


def load_openstates_lookup(
    conn, batch_id: str, states: tuple[str, ...] | None
) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[tuple[str, str], list[dict[str, Any]]]]:
    """
    Return two indexes for matching:

    - ``by_email``:    {(state_code, email_lower): row}  — 1:1 (collisions kept as last-win, logged)
    - ``by_name_state``: {(state_code, normalized_name): [row, ...]} — many possible, used when there's exactly one
    """
    where = "WHERE sync_batch_id = %s::uuid"
    params: list[Any] = [batch_id]
    if states:
        ph = ",".join(["%s"] * len(states))
        where += f" AND state_code IN ({ph})"
        params.extend(states)
    sql = f"""
        SELECT openstates_person_id, name, given_name, family_name, gender, biography,
               birth_date, death_date, image, primary_party, email, state_code,
               links, identifiers
        FROM bronze.bronze_jurisdiction_openstates
        {where}
    """
    by_email: dict[tuple[str, str], dict[str, Any]] = {}
    by_name_state: dict[tuple[str, str], list[dict[str, Any]]] = {}
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        for raw in cur.fetchall():
            rec = dict(zip(cols, raw))
            state = (rec.get("state_code") or "").upper()
            if not state:
                continue
            email = (rec.get("email") or "").strip().lower()
            if email:
                by_email[(state, email)] = rec
            norm_name = _normalize_name(rec.get("name"))
            if norm_name:
                by_name_state.setdefault((state, norm_name), []).append(rec)
    return by_email, by_name_state


def fetch_scraped_persons_needing_enrichment(
    conn, states: tuple[str, ...] | None, limit: int | None
) -> list[dict[str, Any]]:
    where = "WHERE openstates_person_id IS NULL AND name IS NOT NULL AND btrim(name) <> ''"
    params: list[Any] = []
    if states:
        ph = ",".join(["%s"] * len(states))
        where += f" AND state_code IN ({ph})"
        params.extend(states)
    lim = f"LIMIT {int(limit)}" if limit else ""
    sql = f"""
        SELECT id, jurisdiction_id, state_code, name, email
        FROM bronze.bronze_persons_scraped
        {where}
        ORDER BY id
        {lim}
    """
    with conn.cursor() as cur:
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        return [dict(zip(cols, r)) for r in cur.fetchall()]


def apply_enrichment(conn, row_id: int, ocd: dict[str, Any]) -> None:
    """
    Update one scraped person row with OCD-sourced fields. COALESCE preserves any
    pre-existing scraped values; only nulls get filled.
    """
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE bronze.bronze_persons_scraped
            SET
                openstates_person_id = %s,
                biography     = COALESCE(biography,    %s),
                given_name    = COALESCE(given_name,   %s),
                family_name   = COALESCE(family_name,  %s),
                gender        = COALESCE(gender,       %s),
                image         = COALESCE(image,        %s),
                primary_party = COALESCE(primary_party,%s),
                links         = (
                    CASE WHEN links IS NULL OR links = '[]'::jsonb
                         THEN %s::jsonb ELSE links END
                ),
                identifiers   = (
                    CASE WHEN identifiers IS NULL OR identifiers = '[]'::jsonb
                         THEN %s::jsonb ELSE identifiers END
                )
            WHERE id = %s
            """,
            (
                ocd["openstates_person_id"],
                ocd.get("biography"),
                ocd.get("given_name"),
                ocd.get("family_name"),
                ocd.get("gender"),
                ocd.get("image"),
                ocd.get("primary_party"),
                json.dumps(ocd.get("links") or []),
                json.dumps(ocd.get("identifiers") or []),
                row_id,
            ),
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--states", default=",".join(DEFAULT_PRIORITY_STATES))
    p.add_argument("--limit", type=int, default=None,
                   help="Cap the number of scraped persons to attempt enrichment on (for testing).")
    p.add_argument("--dry-run", action="store_true",
                   help="Report what would match; don't UPDATE.")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    target_url = os.getenv("NEON_DATABASE_URL_DEV", "").strip()
    if not target_url:
        logger.error("NEON_DATABASE_URL_DEV is not set")
        return 2

    states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip())

    conn = psycopg2.connect(target_url)
    try:
        batch_id = _latest_sync_batch(conn)
        if not batch_id:
            logger.error("No bronze.bronze_jurisdiction_openstates batch found — run sync_persons_to_bronze first.")
            return 1
        logger.info("using openstates sync batch %s", batch_id)

        by_email, by_name_state = load_openstates_lookup(conn, batch_id, states)
        logger.info("openstates lookup: %d email entries, %d name+state buckets",
                    len(by_email), len(by_name_state))

        candidates = fetch_scraped_persons_needing_enrichment(conn, states, args.limit)
        logger.info("scraped persons needing enrichment: %d", len(candidates))

        matched_email = matched_name = ambiguous_name = no_match = 0
        for row in candidates:
            state = (row.get("state_code") or "").upper()
            email = (row.get("email") or "").strip().lower()
            ocd = None
            method = ""

            if email:
                ocd = by_email.get((state, email))
                if ocd:
                    method = "email"

            if ocd is None:
                norm = _normalize_name(row.get("name"))
                if state and norm:
                    bucket = by_name_state.get((state, norm), [])
                    if len(bucket) == 1:
                        ocd = bucket[0]
                        method = "name+state"
                    elif len(bucket) > 1:
                        ambiguous_name += 1

            if ocd is None:
                no_match += 1
                continue

            if method == "email":
                matched_email += 1
            else:
                matched_name += 1

            if args.dry_run:
                logger.debug("[%s] %s match for row %s: %s (%d links)",
                             method, row.get("name"), row["id"],
                             ocd.get("openstates_person_id"), len(ocd.get("links") or []))
            else:
                apply_enrichment(conn, row["id"], ocd)
        if not args.dry_run:
            conn.commit()
    finally:
        conn.close()

    print()
    print(f"Scraped persons examined:  {len(candidates)}")
    print(f"Matched by email:          {matched_email}")
    print(f"Matched by name+state:     {matched_name}")
    print(f"Ambiguous name+state:      {ambiguous_name}  (skipped — multiple candidates)")
    print(f"No match:                  {no_match}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
