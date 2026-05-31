#!/usr/bin/env python3
"""
Sync bronze election-domain rows into c1 election tables.

Source:
  bronze.bronze_elections_scraped

Destination:
  public.c1_division
  public.c1_election
  public.c1_electionsource
  public.c1_candidatecontest
  public.c1_candidacy
  public.c1_ballotmeasure
  public.c1_ballotmeasuresource

Usage:
    .venv/bin/python -m ingestion.openstates.sync_elections_to_c1 --states AL,GA,IN,MA,WA,WI
    .venv/bin/python -m ingestion.openstates.sync_elections_to_c1 --all
    .venv/bin/python -m ingestion.openstates.sync_elections_to_c1 --states MA --dry-run
"""

from __future__ import annotations

import argparse
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json

_ROOT = Path(__file__).resolve().parents[5]
load_dotenv(_ROOT / ".env")

logger = logging.getLogger("openstates_sync_elections_c1")

_UUID_NS = uuid.UUID("6f33a6d3-6f5c-4d74-8f12-33eb1cdb8f26")

# c1_* ``id`` columns are VARCHAR(50); long prefixes like ``ocd-candidatecontest/`` overflow.
_OCD_PREFIX_SHORT: dict[str, str] = {
    "election": "el",
    "candidatecontest": "cc",
    "candidacy": "cy",
    "ballotmeasure": "bm",
}

# Partial unique indexes (migration 055): ON CONFLICT must include the same predicate.
_ON_CONFLICT_DEDUPE_KEY = "ON CONFLICT (dedupe_key) WHERE dedupe_key IS NOT NULL"

_C1_LIMITS = {
    "id": 50,
    "dedupe_key": 500,
    "division_id": 300,
    "jurisdiction_id": 300,
    "source": 100,
    "electionsource_note": 300,
    "electionsource_url": 2000,
}


@dataclass(frozen=True)
class BronzeElectionRow:
    id: int
    scrape_batch_id: str
    record_type: str
    ocd_id: str | None
    election_name: str | None
    election_date: date | None
    election_type: str | None
    election_status: str | None
    ocd_jurisdiction_id: str | None
    state_code: str | None
    jurisdiction_id: str | None
    candidate_name: str | None
    candidate_party: str | None
    candidate_post: str | None
    candidate_status: str | None
    candidate_vote_count: int | None
    candidate_vote_percent: float | None
    measure_title: str | None
    measure_summary: str | None
    measure_classification: str | None
    measure_yes_count: int | None
    measure_no_count: int | None
    measure_outcome: str | None
    source_url: str | None
    source_name: str | None
    raw_row: dict[str, Any]


def _connect(env_var: str) -> psycopg2.extensions.connection:
    url = os.getenv(env_var, "").strip()
    if not url:
        raise SystemExit(f"{env_var} not set in .env")
    return psycopg2.connect(url)


def make_ocd_id(prefix: str, key: str) -> str:
    """Stable id that fits ``c1_*``.``id`` VARCHAR(50) (``ocd-el/<uuid>`` ≈ 43 chars)."""
    short = _OCD_PREFIX_SHORT.get(prefix, prefix[:8])
    return f"ocd-{short}/{uuid.uuid5(_UUID_NS, key)}"


def _make_id(prefix: str, key: str) -> str:
    return make_ocd_id(prefix, key)


def _truncate(value: str | None, max_len: int) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    return text if len(text) <= max_len else text[:max_len]


def fit_c1_id(value: str | None, *, prefix: str, fallback_key: str) -> str:
    """Use ``value`` when it fits VARCHAR(50); otherwise hash to a short stable id."""
    text = (value or "").strip()
    if text and len(text) <= _C1_LIMITS["id"]:
        return text
    if text:
        return make_ocd_id(prefix, text)
    return make_ocd_id(prefix, fallback_key)


def _stable_key(*parts: str | None) -> str:
    return "|".join((p or "").strip().lower() for p in parts)


def _dedupe_key(*parts: str | None) -> str | None:
    key = _stable_key(*parts)
    if not key:
        return None
    return _truncate(key, _C1_LIMITS["dedupe_key"])


def _fit_division_id(value: str | None) -> str | None:
    return _truncate(value, _C1_LIMITS["division_id"])


def _fit_jurisdiction_id(value: str | None) -> str | None:
    return _truncate(value, _C1_LIMITS["jurisdiction_id"])


def _state_filter_sql(states: tuple[str, ...] | None) -> tuple[str, tuple[Any, ...]]:
    if not states:
        return "", tuple()
    clauses = " OR ".join("state_code = %s" for _ in states)
    return f"AND ({clauses})", tuple(states)


def load_bronze_rows(
    conn,
    states: tuple[str, ...] | None,
    record_types: tuple[str, ...] | None,
    limit: int | None,
    scrape_batch_id: str | None = None,
    jurisdiction_id: str | None = None,
) -> list[BronzeElectionRow]:
    state_clause, state_params = _state_filter_sql(states)
    type_clause = ""
    type_params: tuple[Any, ...] = tuple()
    batch_clause = ""
    batch_params: tuple[Any, ...] = tuple()
    jurisdiction_clause = ""
    jurisdiction_params: tuple[Any, ...] = tuple()
    if record_types:
        placeholders = ", ".join(["%s"] * len(record_types))
        type_clause = f"AND record_type IN ({placeholders})"
        type_params = record_types
    if scrape_batch_id:
        batch_clause = "AND scrape_batch_id::text = %s"
        batch_params = (scrape_batch_id,)
    if jurisdiction_id:
        jurisdiction_clause = "AND jurisdiction_id = %s"
        jurisdiction_params = (jurisdiction_id,)
    limit_clause = f"LIMIT {int(limit)}" if limit else ""
    sql = f"""
        SELECT id, scrape_batch_id::text, record_type, ocd_id,
               election_name, election_date, election_type, election_status,
               ocd_jurisdiction_id, state_code, jurisdiction_id,
               candidate_name, candidate_party, candidate_post, candidate_status,
               candidate_vote_count, candidate_vote_percent,
               measure_title, measure_summary, measure_classification,
               measure_yes_count, measure_no_count, measure_outcome,
               source_url, source_name, raw_row
        FROM bronze.bronze_elections_scraped
        WHERE TRUE {state_clause} {type_clause} {batch_clause} {jurisdiction_clause}
        ORDER BY state_code NULLS LAST, election_date NULLS LAST, id
        {limit_clause}
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            state_params + type_params + batch_params + jurisdiction_params,
        )
        return [BronzeElectionRow(*r) for r in cur.fetchall()]


def sync_jurisdiction_elections_to_c1(
    conn,
    scrape_batch_id: str,
    jurisdiction_id: str,
    *,
    dry_run: bool = False,
) -> dict[str, int]:
    """Promote bronze rows for one jurisdiction in a batch into c1 election tables."""
    rows = load_bronze_rows(
        conn,
        states=None,
        record_types=("election", "candidacy", "ballot_measure"),
        limit=None,
        scrape_batch_id=scrape_batch_id,
        jurisdiction_id=jurisdiction_id,
    )
    if not rows:
        return {"elections": 0, "contests": 0, "candidacies": 0, "measures": 0, "divisions": 0}
    n_divisions = upsert_divisions(conn, rows, dry_run=dry_run)
    n_elections = upsert_elections(conn, rows, dry_run=dry_run)
    contest_ids = upsert_candidate_contests(conn, rows, dry_run=dry_run)
    n_candidacies = upsert_candidacies(conn, rows, contest_ids, dry_run=dry_run)
    n_measures = upsert_ballot_measures(conn, rows, dry_run=dry_run)
    return {
        "divisions": n_divisions,
        "elections": n_elections,
        "contests": len(contest_ids),
        "candidacies": n_candidacies,
        "measures": n_measures,
    }


def _source_rows(raw_row: dict[str, Any], source_url: str | None) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    if source_url:
        rows.append(("source", source_url))
    for item in raw_row.get("sources") or []:
        if isinstance(item, dict):
            url = (item.get("url") or item.get("source_url") or "").strip()
            if url:
                note = _truncate(
                    str(item.get("note") or item.get("classification") or item.get("kind") or "source"),
                    _C1_LIMITS["electionsource_note"],
                ) or "source"
                rows.append((note, url))
    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        if row not in seen:
            seen.add(row)
            deduped.append(row)
    return deduped


def _election_id(row: BronzeElectionRow) -> tuple[str, str | None]:
    """Resolve c1 election id + dedupe_key (dedupe may be None)."""
    raw = row.raw_row or {}
    parent_election_id = (raw.get("election_id") or "").strip()
    jurisdiction = row.jurisdiction_id or row.ocd_jurisdiction_id

    if row.record_type == "election":
        dedupe_key = _dedupe_key(
            jurisdiction,
            str(row.election_date or ""),
            row.election_name,
            row.election_type,
        )
        fallback = dedupe_key or str(row.id)
        election_id = fit_c1_id(row.ocd_id, prefix="election", fallback_key=fallback)
        return election_id, dedupe_key

    if parent_election_id:
        election_id = fit_c1_id(
            parent_election_id, prefix="election", fallback_key=parent_election_id
        )
        dedupe_key = _dedupe_key(
            jurisdiction,
            str(row.election_date or ""),
            row.election_name,
            row.election_type,
        )
        if not (row.election_name or row.election_date or row.election_type):
            dedupe_key = _dedupe_key("election", election_id)
        return election_id, dedupe_key

    dedupe_key = _dedupe_key(
        jurisdiction,
        str(row.election_date or ""),
        row.election_name,
        row.election_type,
        str(row.id),
    )
    fallback = dedupe_key or str(row.id)
    election_id = fit_c1_id(row.ocd_id, prefix="election", fallback_key=fallback)
    return election_id, dedupe_key


def _contest_id(row: BronzeElectionRow, election_id: str) -> tuple[str, str | None]:
    key = _dedupe_key(election_id, row.candidate_post, row.candidate_party)
    contest_id = make_ocd_id("candidatecontest", key or f"{election_id}|{row.id}")
    return contest_id, key


def _candidacy_id(row: BronzeElectionRow, election_id: str, contest_id: str) -> tuple[str, str | None]:
    key = _dedupe_key(election_id, contest_id, row.candidate_name, row.candidate_party)
    fallback = key or str(row.id)
    candidacy_id = fit_c1_id(row.ocd_id, prefix="candidacy", fallback_key=fallback)
    return candidacy_id, key


def _ballotmeasure_id(row: BronzeElectionRow, election_id: str) -> tuple[str, str | None]:
    key = _dedupe_key(
        election_id, row.measure_title, row.measure_classification, row.measure_outcome
    )
    fallback = key or str(row.id)
    measure_id = fit_c1_id(row.ocd_id, prefix="ballotmeasure", fallback_key=fallback)
    return measure_id, key


def _election_group_key(row: BronzeElectionRow) -> str:
    """Stable c1 election id for grouping (not dedupe_key — candidacies use election|{id})."""
    election_id, _ = _election_id(row)
    return fit_c1_id(election_id, prefix="election", fallback_key=str(row.id))


def _election_rows_for_upsert(rows: list[BronzeElectionRow]) -> list[BronzeElectionRow]:
    """One bronze row per election group; candidacies inherit parent election from raw_row."""
    grouped: dict[str, BronzeElectionRow] = {}
    for row in rows:
        if row.record_type != "election":
            continue
        grouped[_election_group_key(row)] = row
    for row in rows:
        if row.record_type == "election":
            continue
        key = _election_group_key(row)
        if key not in grouped:
            grouped[key] = row
    return list(grouped.values())


def _execute_election_upsert(cur, payload: tuple) -> None:
    """Upsert by dedupe_key when set (avoids ux_c1_election_dedupe_key violations)."""
    dedupe_key = payload[9]
    if dedupe_key:
        cur.execute(
            f"""
            INSERT INTO public.c1_election
                (id, legacy_id, name, election_date, election_type, election_status,
                 jurisdiction_id, division_id, state_code, dedupe_key, source, source_url,
                 links, sources, extras)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            {_ON_CONFLICT_DEDUPE_KEY} DO UPDATE SET
                name = EXCLUDED.name,
                election_date = EXCLUDED.election_date,
                election_type = EXCLUDED.election_type,
                election_status = EXCLUDED.election_status,
                jurisdiction_id = EXCLUDED.jurisdiction_id,
                division_id = EXCLUDED.division_id,
                state_code = EXCLUDED.state_code,
                source = EXCLUDED.source,
                source_url = EXCLUDED.source_url,
                links = EXCLUDED.links,
                sources = EXCLUDED.sources,
                extras = EXCLUDED.extras,
                updated_at = now()
            """,
            payload,
        )
        return
    cur.execute(
        """
        INSERT INTO public.c1_election
            (id, legacy_id, name, election_date, election_type, election_status,
             jurisdiction_id, division_id, state_code, dedupe_key, source, source_url,
             links, sources, extras)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (id) DO UPDATE SET
            name = EXCLUDED.name,
            election_date = EXCLUDED.election_date,
            election_type = EXCLUDED.election_type,
            election_status = EXCLUDED.election_status,
            jurisdiction_id = EXCLUDED.jurisdiction_id,
            division_id = EXCLUDED.division_id,
            state_code = EXCLUDED.state_code,
            dedupe_key = EXCLUDED.dedupe_key,
            source = EXCLUDED.source,
            source_url = EXCLUDED.source_url,
            links = EXCLUDED.links,
            sources = EXCLUDED.sources,
            extras = EXCLUDED.extras,
            updated_at = now()
        """,
        payload,
    )


def _execute_dedupe_upsert(
    cur,
    *,
    table: str,
    columns: str,
    placeholders: str,
    update_set: str,
    payload: tuple,
    dedupe_index: int,
) -> None:
    dedupe_key = payload[dedupe_index]
    if dedupe_key:
        cur.execute(
            f"""
            INSERT INTO public.{table} ({columns})
            VALUES ({placeholders})
            {_ON_CONFLICT_DEDUPE_KEY} DO UPDATE SET {update_set}
            """,
            payload,
        )
    else:
        cur.execute(
            f"""
            INSERT INTO public.{table} ({columns})
            VALUES ({placeholders})
            ON CONFLICT (id) DO UPDATE SET {update_set}
            """,
            payload,
        )


def upsert_divisions(dst_conn, rows: list[BronzeElectionRow], *, dry_run: bool) -> int:
    payloads: dict[str, tuple] = {}
    for row in rows:
        division_id = _fit_division_id(row.ocd_jurisdiction_id or row.jurisdiction_id)
        if not division_id:
            continue
        payloads[division_id] = (
            division_id,
            _truncate(row.jurisdiction_id or row.election_name or division_id, 500)
            or division_id,
            "jurisdiction",
            None,
            _fit_jurisdiction_id(row.jurisdiction_id),
            row.state_code,
            Json({"source": row.source_name or "bronze_elections_scraped"}),
        )
    if dry_run:
        return len(payloads)
    with dst_conn.cursor() as cur:
        for payload in payloads.values():
            cur.execute(
                """
                INSERT INTO public.c1_division
                    (id, name, classification, parent_id, jurisdiction_id, state_code, extras)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    classification = EXCLUDED.classification,
                    jurisdiction_id = EXCLUDED.jurisdiction_id,
                    state_code = EXCLUDED.state_code,
                    extras = EXCLUDED.extras,
                    updated_at = now()
                """,
                payload,
            )
    dst_conn.commit()
    return len(payloads)


def upsert_elections(dst_conn, rows: list[BronzeElectionRow], *, dry_run: bool) -> int:
    election_rows = _election_rows_for_upsert(rows)
    if dry_run:
        return len({_election_id(r)[0] for r in election_rows})
    count = 0
    seen_election_ids: set[str] = set()
    with dst_conn.cursor() as cur:
        for row in election_rows:
            election_id, dedupe_key = _election_id(row)
            election_id = fit_c1_id(election_id, prefix="election", fallback_key=str(row.id))
            if election_id in seen_election_ids:
                continue
            seen_election_ids.add(election_id)
            division_id = _fit_division_id(row.ocd_jurisdiction_id or row.jurisdiction_id)
            payload = (
                election_id,
                row.id,
                row.election_name or row.source_name or "Election",
                row.election_date,
                row.election_type,
                row.election_status,
                _fit_jurisdiction_id(row.jurisdiction_id),
                division_id,
                row.state_code,
                dedupe_key,
                _truncate(row.source_name or "bronze_elections_scraped", _C1_LIMITS["source"])
                or "bronze_elections_scraped",
                row.source_url,
                Json((row.raw_row or {}).get("links") or []),
                Json((row.raw_row or {}).get("sources") or []),
                Json(row.raw_row or {}),
            )
            _execute_election_upsert(cur, payload)
            count += 1
            resolved_election_id = election_id
            if dedupe_key:
                cur.execute(
                    "SELECT id FROM public.c1_election WHERE dedupe_key = %s",
                    (dedupe_key,),
                )
                found = cur.fetchone()
                if found:
                    resolved_election_id = found[0]
            for note, url in _source_rows(row.raw_row or {}, row.source_url):
                cur.execute(
                    """
                    INSERT INTO public.c1_electionsource (election_id, note, url)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        resolved_election_id,
                        note,
                        _truncate(url, _C1_LIMITS["electionsource_url"]),
                    ),
                )
    dst_conn.commit()
    return count


def upsert_candidate_contests(dst_conn, rows: list[BronzeElectionRow], *, dry_run: bool) -> dict[str, str]:
    grouped: dict[str, tuple[str, tuple]] = {}
    for row in rows:
        if row.record_type != "candidacy":
            continue
        election_id, _ = _election_id(row)
        contest_id, contest_key = _contest_id(row, election_id)
        group_key = contest_key or contest_id
        if group_key not in grouped:
            grouped[group_key] = (
                contest_id,
                (
                    contest_id,
                    row.id,
                    fit_c1_id(election_id, prefix="election", fallback_key=str(row.id)),
                    row.candidate_post or row.candidate_name or row.election_name or "Contest",
                    row.candidate_post,
                    row.candidate_status,
                    _fit_jurisdiction_id(row.jurisdiction_id),
                    row.state_code,
                    contest_key,
                    _truncate(row.source_name or "bronze_elections_scraped", _C1_LIMITS["source"])
                    or "bronze_elections_scraped",
                    row.source_url,
                    Json(row.raw_row or {}),
                ),
            )
    if dry_run:
        return {key: cid for key, (cid, _) in grouped.items()}
    with dst_conn.cursor() as cur:
        for contest_id, payload in grouped.values():
            _execute_dedupe_upsert(
                cur,
                table="c1_candidatecontest",
                columns=(
                    "id, legacy_id, election_id, name, office, status, "
                    "jurisdiction_id, state_code, dedupe_key, source, source_url, extras"
                ),
                placeholders="%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s",
                update_set=(
                    "election_id = EXCLUDED.election_id, "
                    "name = EXCLUDED.name, office = EXCLUDED.office, status = EXCLUDED.status, "
                    "jurisdiction_id = EXCLUDED.jurisdiction_id, state_code = EXCLUDED.state_code, "
                    "source = EXCLUDED.source, source_url = EXCLUDED.source_url, "
                    "extras = EXCLUDED.extras, updated_at = now()"
                ),
                payload=payload,
                dedupe_index=8,
            )
    dst_conn.commit()
    return {key: cid for key, (cid, _) in grouped.items()}


def upsert_candidacies(dst_conn, rows: list[BronzeElectionRow], contest_ids: dict[str, str], *, dry_run: bool) -> int:
    if dry_run:
        return sum(1 for row in rows if row.record_type == "candidacy")
    count = 0
    with dst_conn.cursor() as cur:
        for row in rows:
            if row.record_type != "candidacy":
                continue
            election_id, _ = _election_id(row)
            contest_id, contest_key = _contest_id(row, election_id)
            resolved_contest_id = contest_ids.get(contest_key or contest_id, contest_id)
            candidacy_id, dedupe_key = _candidacy_id(row, election_id, resolved_contest_id)
            payload = (
                candidacy_id,
                row.id,
                fit_c1_id(election_id, prefix="election", fallback_key=str(row.id)),
                fit_c1_id(resolved_contest_id, prefix="candidatecontest", fallback_key=str(row.id)),
                row.candidate_post or row.candidate_name or row.election_name or "Contest",
                row.candidate_name,
                None,
                row.candidate_party,
                row.candidate_status,
                row.candidate_vote_count,
                row.candidate_vote_percent,
                _fit_jurisdiction_id(row.jurisdiction_id),
                row.state_code,
                dedupe_key,
                _truncate(row.source_name or "bronze_elections_scraped", _C1_LIMITS["source"])
                or "bronze_elections_scraped",
                row.source_url,
                Json(row.raw_row or {}),
                Json(row.raw_row or {}),
            )
            _execute_dedupe_upsert(
                cur,
                table="c1_candidacy",
                columns=(
                    "id, legacy_id, election_id, contest_id, contest_name, person_name, "
                    "person_id, party, status, vote_count, vote_percent, jurisdiction_id, "
                    "state_code, dedupe_key, source, source_url, extras, raw_row"
                ),
                placeholders="%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s",
                update_set=(
                    "election_id = EXCLUDED.election_id, contest_id = EXCLUDED.contest_id, "
                    "contest_name = EXCLUDED.contest_name, person_name = EXCLUDED.person_name, "
                    "party = EXCLUDED.party, status = EXCLUDED.status, "
                    "vote_count = EXCLUDED.vote_count, vote_percent = EXCLUDED.vote_percent, "
                    "jurisdiction_id = EXCLUDED.jurisdiction_id, state_code = EXCLUDED.state_code, "
                    "source = EXCLUDED.source, source_url = EXCLUDED.source_url, "
                    "extras = EXCLUDED.extras, raw_row = EXCLUDED.raw_row, updated_at = now()"
                ),
                payload=payload,
                dedupe_index=13,
            )
            count += 1
    dst_conn.commit()
    return count


def upsert_ballot_measures(dst_conn, rows: list[BronzeElectionRow], *, dry_run: bool) -> int:
    if dry_run:
        return sum(1 for row in rows if row.record_type == "ballot_measure")
    count = 0
    with dst_conn.cursor() as cur:
        for row in rows:
            if row.record_type != "ballot_measure":
                continue
            election_id, _ = _election_id(row)
            measure_id, dedupe_key = _ballotmeasure_id(row, election_id)
            payload = (
                measure_id,
                row.id,
                fit_c1_id(election_id, prefix="election", fallback_key=str(row.id)),
                row.measure_title or row.election_name or "Ballot measure",
                row.measure_title,
                row.measure_summary,
                row.measure_classification,
                row.measure_outcome,
                row.measure_outcome,
                row.measure_yes_count,
                row.measure_no_count,
                None,
                _fit_jurisdiction_id(row.jurisdiction_id),
                row.state_code,
                dedupe_key,
                _truncate(row.source_name or "bronze_elections_scraped", _C1_LIMITS["source"])
                or "bronze_elections_scraped",
                row.source_url,
                Json(row.raw_row or {}),
                Json(row.raw_row or {}),
            )
            _execute_dedupe_upsert(
                cur,
                table="c1_ballotmeasure",
                columns=(
                    "id, legacy_id, election_id, name, title, summary, classification, "
                    "status, result, yes_votes, no_votes, yes_percentage, jurisdiction_id, "
                    "state_code, dedupe_key, source, source_url, extras, raw_row"
                ),
                placeholders="%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s",
                update_set=(
                    "election_id = EXCLUDED.election_id, name = EXCLUDED.name, "
                    "title = EXCLUDED.title, summary = EXCLUDED.summary, "
                    "classification = EXCLUDED.classification, status = EXCLUDED.status, "
                    "result = EXCLUDED.result, yes_votes = EXCLUDED.yes_votes, "
                    "no_votes = EXCLUDED.no_votes, yes_percentage = EXCLUDED.yes_percentage, "
                    "jurisdiction_id = EXCLUDED.jurisdiction_id, state_code = EXCLUDED.state_code, "
                    "source = EXCLUDED.source, source_url = EXCLUDED.source_url, "
                    "extras = EXCLUDED.extras, raw_row = EXCLUDED.raw_row, updated_at = now()"
                ),
                payload=payload,
                dedupe_index=14,
            )
            for note, url in _source_rows(row.raw_row or {}, row.source_url):
                cur.execute(
                    """
                    INSERT INTO public.c1_ballotmeasuresource (ballotmeasure_id, note, url)
                    VALUES (%s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (measure_id, note, url),
                )
            count += 1
    dst_conn.commit()
    return count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--states", default="", help="Comma-separated USPS state codes")
    group.add_argument("--all", action="store_true", help="Sync all states present in bronze")
    parser.add_argument("--record-types", default="election,candidacy,ballot_measure", help="Comma-separated record types to sync")
    parser.add_argument("--limit", type=int, default=None, help="Cap bronze rows processed (useful for testing)")
    parser.add_argument("--scrape-batch-id", default="", help="Only sync rows from a specific bronze scrape_batch_id")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    conn = _connect("NEON_DATABASE_URL_DEV")
    try:
        states: tuple[str, ...] | None = None
        if args.states:
            states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip())
        record_types = tuple(s.strip() for s in args.record_types.split(",") if s.strip()) if args.record_types else None
        rows = load_bronze_rows(conn, states, record_types, args.limit, args.scrape_batch_id.strip() or None)
        if not rows:
            logger.info("No bronze election rows matched the requested filters")
            return 0

        n_divisions = upsert_divisions(conn, rows, dry_run=args.dry_run)
        n_elections = upsert_elections(conn, rows, dry_run=args.dry_run)
        contest_ids = upsert_candidate_contests(conn, rows, dry_run=args.dry_run)
        n_candidacies = upsert_candidacies(conn, rows, contest_ids, dry_run=args.dry_run)
        n_measures = upsert_ballot_measures(conn, rows, dry_run=args.dry_run)

        print()
        print(f"c1_division rows synced:        {n_divisions}")
        print(f"c1_election rows synced:        {n_elections}")
        print(f"c1_candidatecontest rows synced: {len(contest_ids)}")
        print(f"c1_candidacy rows synced:       {n_candidacies}")
        print(f"c1_ballotmeasure rows synced:   {n_measures}")
        if args.dry_run:
            print("(dry-run — no DB writes)")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())