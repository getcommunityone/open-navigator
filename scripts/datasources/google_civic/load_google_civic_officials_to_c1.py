#!/usr/bin/env python3
"""
Load Google Civic and Ballotpedia election snapshots into bronze first, then promote to c1.

Flow:
  1) Fetch source payloads and save raw cache files under:
     - data/cache/google_civic
     - data/cache/ballotpedia
  2) Insert normalized rows into bronze.bronze_elections_scraped with source tracking:
     - source_name = bronze_election_google
     - source_name = bronze_election_ballotpedia
  3) Promote only the current scrape batch into c1_* tables via sync_elections_to_c1.

Usage:
    .venv/bin/python -m scripts.datasources.google_civic.load_google_civic_officials_to_c1 \
        --states AL,GA,IN,MA,WA,WI --limit-per-state 20

    .venv/bin/python -m scripts.datasources.google_civic.load_google_civic_officials_to_c1 \
        --states MA --limit-per-state 5 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import Json

from scripts.datasources.openstates.sync_elections_to_c1 import (
    load_bronze_rows,
    upsert_ballot_measures,
    upsert_candidacies,
    upsert_candidate_contests,
    upsert_divisions,
    upsert_elections,
)

_ROOT = Path(__file__).resolve().parents[3]
load_dotenv(_ROOT / ".env")

logger = logging.getLogger("google_civic_bronze_loader")

DEFAULT_PRIORITY_STATES = ("AL", "GA", "IN", "MA", "WA", "WI")
DEFAULT_INCLUDE_TYPES = ("municipality", "county")
_UUID_NS = uuid.UUID("b1ed9a39-f6a5-44f7-8e4b-5e0f58d4c0da")
GOOGLE_SOURCE_NAME = "bronze_election_google"
BALLOTPEDIA_SOURCE_NAME = "bronze_election_ballotpedia"
GOOGLE_CACHE_DIR = _ROOT / "data" / "cache" / "google_civic"
BALLOTPEDIA_CACHE_DIR = _ROOT / "data" / "cache" / "ballotpedia"
SCRAPED_MEETINGS_CACHE_DIR = _ROOT / "data" / "cache" / "scraped_meetings"


def _connect() -> psycopg2.extensions.connection:
    url = os.getenv("NEON_DATABASE_URL_DEV", "").strip()
    if not url:
        raise SystemExit("NEON_DATABASE_URL_DEV not set in .env")
    return psycopg2.connect(url)


def _stable_id(prefix: str, key: str) -> str:
    return f"ocd-{prefix}/{uuid.uuid5(_UUID_NS, key)}"


def _stable_key(*parts: str | None) -> str:
    return "|".join((p or "").strip().lower() for p in parts)


def _state_code_from_ocd_id(ocd_id: str | None) -> str | None:
    if not ocd_id:
        return None
    for part in ocd_id.split("/"):
        if part.startswith("state:") and len(part) == len("state:xx"):
            return part.split(":", 1)[1].upper()
    return None


def _load_targets(conn, states: tuple[str, ...], include_types: tuple[str, ...], limit_per_state: int | None) -> list[dict[str, Any]]:
    state_placeholders = ",".join(["%s"] * len(states))
    type_placeholders = ",".join(["%s"] * len(include_types))
    sql = f"""
        WITH ranked AS (
            SELECT
                j.jurisdiction_id,
                j.state_code,
                j.jurisdiction_type,
                COALESCE(NULLIF(BTRIM(j.name), ''), j.jurisdiction_id) AS name
            FROM intermediate.int_jurisdictions j
            WHERE j.state_code IN ({state_placeholders})
              AND j.jurisdiction_type IN ({type_placeholders})
              AND EXISTS (
                  SELECT 1
                  FROM intermediate.int_jurisdiction_websites w
                  WHERE w.jurisdiction_id = j.jurisdiction_id
                    AND w.website_url IS NOT NULL
                    AND BTRIM(w.website_url) <> ''
              )
        ),
        numbered AS (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY state_code
                ORDER BY CASE jurisdiction_type WHEN 'municipality' THEN 0 WHEN 'county' THEN 1 ELSE 2 END,
                         jurisdiction_id
            ) AS rn
            FROM ranked
        )
        SELECT jurisdiction_id, state_code, jurisdiction_type, name
        FROM numbered
        WHERE (%s IS NULL OR rn <= %s)
        ORDER BY state_code,
                 CASE jurisdiction_type WHEN 'municipality' THEN 0 WHEN 'county' THEN 1 ELSE 2 END,
                 jurisdiction_id
    """
    params: list[Any] = list(states) + list(include_types)
    params.extend([limit_per_state, limit_per_state])
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return [
            {
                "jurisdiction_id": row[0],
                "state_code": row[1],
                "jurisdiction_type": row[2],
                "name": row[3],
            }
            for row in cur.fetchall()
        ]


def _normalize_ballotpedia_city_name(name: str) -> str:
    cleaned = re.sub(r"\s+", " ", (name or "").strip())
    cleaned = re.sub(r"\b(city|town|village|borough|township|cdp|municipality)\b\s*$", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" ,") or name


def _cache_write(base_dir: Path, relative_name: str, payload: dict[str, Any] | list[dict[str, Any]]) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = base_dir / f"{relative_name}_{ts}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def _slugify_name(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower())
    return slug.strip("_") or "jurisdiction"


def _jurisdiction_suffix(jurisdiction_id: str) -> str:
    parts = (jurisdiction_id or "").split("_")
    return parts[-1] if parts else "unknown"


def _standard_jurisdiction_dir(*, state_code: str, jurisdiction_type: str, jurisdiction_name: str, jurisdiction_id: str) -> Path:
    folder_name = f"{_slugify_name(jurisdiction_name)}_{_jurisdiction_suffix(jurisdiction_id)}"
    return SCRAPED_MEETINGS_CACHE_DIR / state_code.upper() / jurisdiction_type.lower() / folder_name


def _write_source_cache(
    *,
    source: str,
    state_code: str,
    jurisdiction_type: str,
    jurisdiction_name: str,
    jurisdiction_id: str,
    relative_name: str,
    payload: dict[str, Any] | list[dict[str, Any]],
) -> None:
    source_base = GOOGLE_CACHE_DIR if source == "google_civic" else BALLOTPEDIA_CACHE_DIR
    _cache_write(source_base / state_code / jurisdiction_type, relative_name, payload)
    standard_dir = _standard_jurisdiction_dir(
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        jurisdiction_name=jurisdiction_name,
        jurisdiction_id=jurisdiction_id,
    )
    _cache_write(standard_dir / "_downloads" / source, relative_name, payload)


def _prune_old_cache_artifacts(base_dir: Path, jurisdiction_id: str) -> int:
    if not base_dir.exists():
        return 0
    patterns = (
        f"{jurisdiction_id}_officials_empty_*.json",
        f"{jurisdiction_id}_officials_error_*.json",
        f"{jurisdiction_id}_division_error_*.json",
        f"{jurisdiction_id}_address_error_*.json",
    )
    deleted = 0
    for pattern in patterns:
        for path in base_dir.glob(pattern):
            try:
                path.unlink(missing_ok=True)
                deleted += 1
            except OSError:
                continue
    return deleted


def _prune_jurisdiction_artifacts(*, state_code: str, jurisdiction_type: str, jurisdiction_name: str, jurisdiction_id: str) -> int:
    deleted = 0
    deleted += _prune_old_cache_artifacts(GOOGLE_CACHE_DIR / state_code / jurisdiction_type, jurisdiction_id)
    deleted += _prune_old_cache_artifacts(BALLOTPEDIA_CACHE_DIR / state_code / jurisdiction_type, jurisdiction_id)
    standard_dir = _standard_jurisdiction_dir(
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        jurisdiction_name=jurisdiction_name,
        jurisdiction_id=jurisdiction_id,
    )
    deleted += _prune_old_cache_artifacts(standard_dir / "_downloads" / "google_civic", jurisdiction_id)
    deleted += _prune_old_cache_artifacts(standard_dir / "_downloads" / "ballotpedia", jurisdiction_id)
    return deleted


def _insert_bronze_row(
    cur,
    *,
    scrape_batch_id: uuid.UUID,
    record_type: str,
    ocd_id: str,
    election_name: str | None,
    election_date_value: date | None,
    election_type: str | None,
    election_status: str | None,
    ocd_jurisdiction_id: str | None,
    state_code: str | None,
    jurisdiction_id: str | None,
    candidate_name: str | None,
    candidate_party: str | None,
    candidate_post: str | None,
    candidate_status: str | None,
    source_url: str | None,
    source_name: str,
    raw_row: dict[str, Any],
) -> None:
    cur.execute(
        """
        INSERT INTO bronze.bronze_elections_scraped
            (scrape_batch_id, record_type, ocd_id,
             election_name, election_date, election_type, election_status,
             ocd_jurisdiction_id, state_code, jurisdiction_id,
             candidate_name, candidate_party, candidate_post, candidate_status,
             source_url, source_name, raw_row)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            str(scrape_batch_id),
            record_type,
            ocd_id,
            election_name,
            election_date_value,
            election_type,
            election_status,
            ocd_jurisdiction_id,
            state_code,
            jurisdiction_id,
            candidate_name,
            candidate_party,
            candidate_post,
            candidate_status,
            source_url,
            source_name,
            Json(raw_row),
        ),
    )


async def _ingest_target(
    *,
    conn,
    api,
    ballotpedia,
    find_ocd_match,
    target: dict[str, Any],
    scrape_batch_id: uuid.UUID,
    dry_run: bool,
) -> tuple[int, int, int]:
    name = target["name"]
    state_code = target["state_code"]
    jurisdiction_id = target["jurisdiction_id"]
    jurisdiction_type = target["jurisdiction_type"]
    division_id = find_ocd_match(name, state_code, jurisdiction_type=jurisdiction_type) or jurisdiction_id
    if not division_id:
        logger.warning("Skipping %s (%s): no OCD match", name, jurisdiction_id)
        return 0, 0, 0

    source_url = f"https://www.googleapis.com/civicinfo/v2/representatives/{division_id}"
    source_name = GOOGLE_SOURCE_NAME
    offices: list[dict[str, Any]] = []
    officials: list[dict[str, Any]] = []
    payload: dict[str, Any] = {}
    _standard_jurisdiction_dir(
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        jurisdiction_name=name,
        jurisdiction_id=jurisdiction_id,
    ).mkdir(parents=True, exist_ok=True)
    _prune_jurisdiction_artifacts(
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        jurisdiction_name=name,
        jurisdiction_id=jurisdiction_id,
    )

    try:
        if not str(division_id).startswith("ocd-division/"):
            raise ValueError(f"Non-OCD division id: {division_id}")
        payload = await api.get_representatives_by_division(division_id)
        offices = payload.get("offices", []) if isinstance(payload, dict) else []
        officials = payload.get("officials", []) if isinstance(payload, dict) else []
        _write_source_cache(
            source="google_civic",
            state_code=state_code,
            jurisdiction_type=jurisdiction_type,
            jurisdiction_name=name,
            jurisdiction_id=jurisdiction_id,
            relative_name=f"{jurisdiction_id}_division",
            payload=(
                {
                    **payload,
                    "debug_status": "success",
                    "debug_reason": "google_division_lookup_ok",
                    "jurisdiction_id": jurisdiction_id,
                    "state_code": state_code,
                }
                if isinstance(payload, dict)
                else {
                    "payload": payload,
                    "debug_status": "success",
                    "debug_reason": "google_division_lookup_ok",
                    "jurisdiction_id": jurisdiction_id,
                    "state_code": state_code,
                }
            ),
        )
    except Exception as exc:
        logger.warning("Division lookup failed for %s (%s): %s", name, division_id, exc)
        _write_source_cache(
            source="google_civic",
            state_code=state_code,
            jurisdiction_type=jurisdiction_type,
            jurisdiction_name=name,
            jurisdiction_id=jurisdiction_id,
            relative_name=f"{jurisdiction_id}_division_error",
            payload={
                "error": str(exc),
                "source": "google_civic_division",
                "debug_status": "error",
                "debug_reason": "google_division_lookup_failed",
                "division_id": division_id,
                "jurisdiction_id": jurisdiction_id,
                "state_code": state_code,
            },
        )
        try:
            payload = await api.get_representatives(f"{name}, {state_code}")
            officials = payload.get("officials", []) if isinstance(payload, dict) else []
            grouped: dict[str, list[int]] = {}
            for idx, official in enumerate(officials):
                office_name = official.get("office") or "Office"
                grouped.setdefault(office_name, []).append(idx)
            offices = [{"name": office_name, "officialIndices": indices} for office_name, indices in grouped.items()]
            source_url = f"https://www.googleapis.com/civicinfo/v2/representatives?address={name}, {state_code}"
            _write_source_cache(
                source="google_civic",
                state_code=state_code,
                jurisdiction_type=jurisdiction_type,
                jurisdiction_name=name,
                jurisdiction_id=jurisdiction_id,
                relative_name=f"{jurisdiction_id}_address",
                payload=(
                    {
                        **payload,
                        "debug_status": "success",
                        "debug_reason": "google_address_lookup_ok",
                        "jurisdiction_id": jurisdiction_id,
                        "state_code": state_code,
                    }
                    if isinstance(payload, dict)
                    else {
                        "payload": payload,
                        "debug_status": "success",
                        "debug_reason": "google_address_lookup_ok",
                        "jurisdiction_id": jurisdiction_id,
                        "state_code": state_code,
                    }
                ),
            )
        except Exception as fallback_exc:
            logger.warning("Address lookup failed for %s: %s", name, fallback_exc)
            _write_source_cache(
                source="google_civic",
                state_code=state_code,
                jurisdiction_type=jurisdiction_type,
                jurisdiction_name=name,
                jurisdiction_id=jurisdiction_id,
                relative_name=f"{jurisdiction_id}_address_error",
                payload={
                    "error": str(fallback_exc),
                    "source": "google_civic_address",
                    "debug_status": "error",
                    "debug_reason": "google_address_lookup_failed",
                    "address": f"{name}, {state_code}",
                    "jurisdiction_id": jurisdiction_id,
                    "state_code": state_code,
                },
            )
            if jurisdiction_type != "municipality":
                return 0, 0, 0
            query_name = _normalize_ballotpedia_city_name(name)
            try:
                bp_officials = await ballotpedia.get_city_officials(query_name, state_code)
            except Exception as bp_exc:
                logger.warning("Ballotpedia fallback failed for %s: %s", name, bp_exc)
                _write_source_cache(
                    source="ballotpedia",
                    state_code=state_code,
                    jurisdiction_type=jurisdiction_type,
                    jurisdiction_name=name,
                    jurisdiction_id=jurisdiction_id,
                    relative_name=f"{jurisdiction_id}_officials_error",
                    payload={
                        "error": str(bp_exc),
                        "source": "ballotpedia",
                        "debug_status": "error",
                        "debug_reason": "ballotpedia_exception",
                        "query_name": query_name,
                        "jurisdiction_id": jurisdiction_id,
                        "state_code": state_code,
                    },
                )
                return 0, 0, 0
            if not bp_officials:
                _write_source_cache(
                    source="ballotpedia",
                    state_code=state_code,
                    jurisdiction_type=jurisdiction_type,
                    jurisdiction_name=name,
                    jurisdiction_id=jurisdiction_id,
                    relative_name=f"{jurisdiction_id}_officials_empty",
                    payload={
                        "error": "No officials returned",
                        "source": "ballotpedia",
                        "debug_status": "empty",
                        "debug_reason": "ballotpedia_no_officials",
                        "query_name": query_name,
                        "jurisdiction_id": jurisdiction_id,
                        "state_code": state_code,
                    },
                )
                return 0, 0, 0

            source_name = BALLOTPEDIA_SOURCE_NAME
            source_url = f"https://ballotpedia.org/{query_name.replace(' ', '_')},{state_code}"
            officials = [
                {
                    "name": item.get("name"),
                    "party": item.get("party"),
                    "position": item.get("position"),
                    "office": item.get("position") or "Office",
                    "source": item.get("source", "ballotpedia"),
                    "source_url": item.get("source_url"),
                    "scraped_at": item.get("scraped_at"),
                }
                for item in bp_officials
            ]
            grouped = {}
            for idx, official in enumerate(officials):
                office_name = official.get("office") or "Office"
                grouped.setdefault(office_name, []).append(idx)
            offices = [{"name": office_name, "officialIndices": indices} for office_name, indices in grouped.items()]
            payload = {"officials": officials, "offices": offices, "source": "ballotpedia"}
            _write_source_cache(
                source="ballotpedia",
                state_code=state_code,
                jurisdiction_type=jurisdiction_type,
                jurisdiction_name=name,
                jurisdiction_id=jurisdiction_id,
                relative_name=f"{jurisdiction_id}_officials",
                payload={
                    **payload,
                    "debug_status": "success",
                    "debug_reason": "ballotpedia_lookup_ok",
                    "query_name": query_name,
                    "jurisdiction_id": jurisdiction_id,
                    "state_code": state_code,
                },
            )

    election_name = f"Officials snapshot: {name}"
    election_id = _stable_id("election", _stable_key(source_name, division_id, state_code, name, str(date.today())))

    if dry_run:
        logger.info("[dry-run] %s %s %s (%s)", state_code, jurisdiction_type, name, source_name)
        return 0, 0, 0

    with conn.cursor() as cur:
        _insert_bronze_row(
            cur,
            scrape_batch_id=scrape_batch_id,
            record_type="election",
            ocd_id=election_id,
            election_name=election_name,
            election_date_value=date.today(),
            election_type="officials_snapshot",
            election_status="confirmed",
            ocd_jurisdiction_id=division_id,
            state_code=state_code,
            jurisdiction_id=jurisdiction_id,
            candidate_name=None,
            candidate_party=None,
            candidate_post=None,
            candidate_status=None,
            source_url=source_url,
            source_name=source_name,
            raw_row={
                "source": source_name,
                "state_code": state_code,
                "jurisdiction_id": jurisdiction_id,
                "jurisdiction_name": name,
                "jurisdiction_type": jurisdiction_type,
                "division_id": division_id,
                "offices": offices,
                "officials": officials,
            },
        )

        candidacy_count = 0
        for office in offices:
            office_name = office.get("name") or "Office"
            for idx in office.get("officialIndices", []) or []:
                if not isinstance(idx, int) or idx >= len(officials):
                    continue
                official = officials[idx] or {}
                person_name = official.get("name") or "Unknown official"
                candidacy_id = _stable_id("candidacy", _stable_key(source_name, election_id, office_name, person_name))
                _insert_bronze_row(
                    cur,
                    scrape_batch_id=scrape_batch_id,
                    record_type="candidacy",
                    ocd_id=candidacy_id,
                    election_name=election_name,
                    election_date_value=date.today(),
                    election_type="officials_snapshot",
                    election_status="confirmed",
                    ocd_jurisdiction_id=division_id,
                    state_code=state_code,
                    jurisdiction_id=jurisdiction_id,
                    candidate_name=person_name,
                    candidate_party=official.get("party"),
                    candidate_post=office_name,
                    candidate_status=official.get("position") or "current",
                    source_url=official.get("source_url") or source_url,
                    source_name=source_name,
                    raw_row={
                        "source": source_name,
                        "office": office_name,
                        "official": official,
                        "jurisdiction_id": jurisdiction_id,
                        "division_id": division_id,
                    },
                )
                candidacy_count += 1

    conn.commit()
    return 1, 1, candidacy_count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--states", default=",".join(DEFAULT_PRIORITY_STATES), help=f"Comma-separated state codes (default: {','.join(DEFAULT_PRIORITY_STATES)})")
    parser.add_argument("--include-types", default=",".join(DEFAULT_INCLUDE_TYPES), help=f"Comma-separated jurisdiction categories (default: {','.join(DEFAULT_INCLUDE_TYPES)})")
    parser.add_argument("--limit-per-state", type=int, default=20, help="Cap jurisdictions per state (default: 20)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip())
    include_types = tuple(t.strip().lower() for t in args.include_types.split(",") if t.strip())
    if not states or not include_types:
        parser.error("--states and --include-types must be non-empty")

    from scripts.datasources.ballotpedia.ballotpedia_integration import BallotpediaDiscovery
    from scripts.datasources.google_civic.google_civic_integration import GoogleCivicAPI
    from scripts.datasources.jurisdiction_pilot.load_ocd_jurisdictions import find_ocd_match

    api = GoogleCivicAPI()
    ballotpedia = None
    if not api.api_key:
        raise SystemExit("GOOGLE_CIVIC_API_KEY is required")

    conn = _connect()
    try:
        ballotpedia = BallotpediaDiscovery()
        targets = _load_targets(conn, states, include_types, args.limit_per_state)
        logger.info("Loaded %d jurisdictions for bronze election ingest", len(targets))

        scrape_batch_id = uuid.uuid4()
        bronze_google_elections = 0
        bronze_snapshot_elections = 0
        bronze_snapshot_candidacies = 0
        bronze_ballotpedia_rows = 0

        if not args.dry_run:
            elections_payload = asyncio.run(api.get_elections())
            _cache_write(
                GOOGLE_CACHE_DIR / "elections",
                "upcoming_elections",
                elections_payload if isinstance(elections_payload, dict) else {"payload": elections_payload},
            )
            with conn.cursor() as cur:
                for election in elections_payload.get("elections", []) if isinstance(elections_payload, dict) else []:
                    civic_id = str(election.get("id") or "")
                    division_id = election.get("ocdDivisionId") or "ocd-division/country:us"
                    state_code = _state_code_from_ocd_id(division_id)
                    election_id = _stable_id(
                        "election",
                        _stable_key("google_civic", civic_id, election.get("name"), election.get("electionDay")),
                    )
                    _insert_bronze_row(
                        cur,
                        scrape_batch_id=scrape_batch_id,
                        record_type="election",
                        ocd_id=election_id,
                        election_name=election.get("name") or "Google Civic election",
                        election_date_value=election.get("electionDay") or date.today(),
                        election_type="civic_calendar",
                        election_status="confirmed",
                        ocd_jurisdiction_id=division_id,
                        state_code=state_code,
                        jurisdiction_id=division_id,
                        candidate_name=None,
                        candidate_party=None,
                        candidate_post=None,
                        candidate_status=None,
                        source_url="https://www.googleapis.com/civicinfo/v2/elections",
                        source_name=GOOGLE_SOURCE_NAME,
                        raw_row=election if isinstance(election, dict) else {"payload": election},
                    )
                    bronze_google_elections += 1
            conn.commit()

        async def _run_all_targets() -> tuple[int, int]:
            total_snapshot_elections = 0
            total_snapshot_candidacies = 0
            for target in targets:
                delta_elections, _delta_snapshot, delta_candidacies = await _ingest_target(
                    conn=conn,
                    api=api,
                    ballotpedia=ballotpedia,
                    find_ocd_match=find_ocd_match,
                    target=target,
                    scrape_batch_id=scrape_batch_id,
                    dry_run=args.dry_run,
                )
                total_snapshot_elections += delta_elections
                total_snapshot_candidacies += delta_candidacies
            return total_snapshot_elections, total_snapshot_candidacies

        bronze_snapshot_elections, bronze_snapshot_candidacies = asyncio.run(_run_all_targets())

        if not args.dry_run:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT count(*)
                    FROM bronze.bronze_elections_scraped
                    WHERE scrape_batch_id::text = %s
                      AND source_name = %s
                    """,
                    (str(scrape_batch_id), BALLOTPEDIA_SOURCE_NAME),
                )
                bronze_ballotpedia_rows = int(cur.fetchone()[0])

            rows = load_bronze_rows(
                conn,
                states=None,
                record_types=("election", "candidacy", "ballot_measure"),
                limit=None,
                scrape_batch_id=str(scrape_batch_id),
            )
            n_divisions = upsert_divisions(conn, rows, dry_run=False)
            n_elections = upsert_elections(conn, rows, dry_run=False)
            contest_ids = upsert_candidate_contests(conn, rows, dry_run=False)
            n_candidacies = upsert_candidacies(conn, rows, contest_ids, dry_run=False)
            n_measures = upsert_ballot_measures(conn, rows, dry_run=False)
        else:
            n_divisions = 0
            n_elections = 0
            n_candidacies = 0
            n_measures = 0
            contest_ids = {}

        print()
        print(f"scrape_batch_id:                {scrape_batch_id}")
        print(f"bronze google election rows:    {bronze_google_elections}")
        print(f"bronze snapshot election rows:  {bronze_snapshot_elections}")
        print(f"bronze snapshot candidacy rows: {bronze_snapshot_candidacies}")
        print(f"bronze ballotpedia rows:        {bronze_ballotpedia_rows}")
        print(f"c1_division rows synced:        {n_divisions}")
        print(f"c1_election rows synced:        {n_elections}")
        print(f"c1_candidatecontest rows synced:{len(contest_ids)}")
        print(f"c1_candidacy rows synced:       {n_candidacies}")
        print(f"c1_ballotmeasure rows synced:   {n_measures}")
        print(f"google civic cache dir:         {GOOGLE_CACHE_DIR}")
        print(f"ballotpedia cache dir:          {BALLOTPEDIA_CACHE_DIR}")
        if args.dry_run:
            print("(dry-run — no DB writes)")
        return 0
    finally:
        if ballotpedia is not None:
            try:
                asyncio.run(ballotpedia.close())
            except Exception:
                pass
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
