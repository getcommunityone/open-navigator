#!/usr/bin/env python3
"""
Load Google Civic Elections/Voter Info and Ballotpedia election snapshots into bronze, then promote to c1.

Flow:
  1) elections.electionQuery — global snapshot under data/cache/google_civic/elections/
     plus a per-state copy per jurisdiction (VIP Test id 2000 excluded; no date param on API)
  2) elections.voterInfoQuery — per jurisdiction address + electionId (VIP polling/contests)
  3) divisionsByAddress — resolve OCD division IDs (Representatives API is retired)
  4) Optional Ballotpedia ballot-measure / external-link enrichment for municipalities

Usage:
    .venv/bin/python -m scripts.datasources.google_civic.load_google_civic_officials_to_c1 \\
        --states AL,GA,IN,MA,WA,WI --limit-per-state 20

    .venv/bin/python scripts/datasources/google_civic/load_google_civic_officials_to_c1.py \\
        --states MA --limit-per-state 5 --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

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
from scripts.datasources.google_civic.google_civic_integration import (
    civic_divisions_by_address_url,
    civic_elections_url,
    civic_voterinfo_url,
    elections_for_state,
    filter_civic_elections,
    format_civic_address_query,
    normalize_civic_place_name,
    sanitize_civic_error_message,
)
from scripts.gemini.transcript_cache_paths import (
    cache_type_segment,
    jurisdiction_cache_folder_name,
)

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


def _run_async(coro: Any, description: str):
    """Run async work and exit cleanly when interrupted by Ctrl+C."""
    try:
        return asyncio.run(coro)
    except KeyboardInterrupt:
        logger.warning("Interrupted while %s", description)
        raise SystemExit(130)
    except asyncio.CancelledError:
        logger.warning("Cancelled while %s", description)
        raise SystemExit(130)


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


def _load_targets(
    conn,
    states: tuple[str, ...],
    include_types: tuple[str, ...],
    limit_per_state: int | None,
    jurisdiction_ids: tuple[str, ...] = (),
) -> list[dict[str, Any]]:
    state_placeholders = ",".join(["%s"] * len(states))
    type_placeholders = ",".join(["%s"] * len(include_types))
    jur_filter_sql = ""
    if jurisdiction_ids:
        jur_placeholders = ",".join(["%s"] * len(jurisdiction_ids))
        jur_filter_sql = f"AND j.jurisdiction_id IN ({jur_placeholders})"
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
              {jur_filter_sql}
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
    if jurisdiction_ids:
        params.extend(jurisdiction_ids)
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
    """Strip Census LSAD suffixes; shared logic with Google Civic address normalization."""
    return normalize_civic_place_name(name)


def _jurisdiction_elections_cache_payload(
    *,
    elections_payload: dict[str, Any],
    relevant_elections: list[dict[str, Any]],
    civic_address: str,
    jurisdiction_id: str,
    state_code: str,
    jurisdiction_name: str,
    jurisdiction_type: str,
) -> dict[str, Any]:
    """electionQuery rows scoped to a jurisdiction address (state + national)."""
    return {
        "elections": relevant_elections,
        "kind": elections_payload.get("kind"),
        "source": elections_payload.get("source") or "google_civic_elections",
        "source_url": elections_payload.get("source_url") or civic_elections_url(),
        "fetched_at": elections_payload.get("fetched_at"),
        "address": civic_address,
        "raw_place_name": jurisdiction_name,
        "jurisdiction_id": jurisdiction_id,
        "state_code": state_code,
        "jurisdiction_type": jurisdiction_type,
        "debug_status": "success" if relevant_elections else "empty",
        "debug_reason": (
            "google_elections_ok"
            if relevant_elections
            else "google_elections_none_for_state"
        ),
    }


def _cache_write(base_dir: Path, relative_name: str, payload: dict[str, Any] | list[dict[str, Any]]) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = base_dir / f"{relative_name}_{ts}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def _jurisdiction_cache_folder(jurisdiction_name: str, jurisdiction_id: str) -> str:
    return jurisdiction_cache_folder_name(jurisdiction_id, place_name=jurisdiction_name)


def _source_cache_dir(
    *,
    source: str,
    state_code: str,
    jurisdiction_type: str,
    jurisdiction_name: str,
    jurisdiction_id: str,
) -> Path:
    source_base = GOOGLE_CACHE_DIR if source == "google_civic" else BALLOTPEDIA_CACHE_DIR
    segment = cache_type_segment(jurisdiction_id, jurisdiction_type=jurisdiction_type)
    folder = _jurisdiction_cache_folder(jurisdiction_name, jurisdiction_id)
    return source_base / state_code.upper() / segment / folder


def _standard_jurisdiction_dir(*, state_code: str, jurisdiction_type: str, jurisdiction_name: str, jurisdiction_id: str) -> Path:
    folder_name = _jurisdiction_cache_folder(jurisdiction_name, jurisdiction_id)
    segment = cache_type_segment(jurisdiction_id, jurisdiction_type=jurisdiction_type)
    return SCRAPED_MEETINGS_CACHE_DIR / state_code.upper() / segment / folder_name


def _enrich_source_cache_payload(payload: dict[str, Any] | list[dict[str, Any]]) -> dict[str, Any] | list[dict[str, Any]]:
    """Ensure debug/empty cache JSON always carries when it ran and is self-describing."""
    if not isinstance(payload, dict):
        return payload
    out = dict(payload)
    now = datetime.now(timezone.utc).isoformat()
    out.setdefault("scraped_at", now)
    out.setdefault("cache_written_at", now)
    return out


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
    if isinstance(payload, dict):
        payload = _enrich_source_cache_payload(payload)
    dest_dir = _source_cache_dir(
        source=source,
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        jurisdiction_name=jurisdiction_name,
        jurisdiction_id=jurisdiction_id,
    )
    _cache_write(dest_dir, relative_name, payload)
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
        f"{jurisdiction_id}_*.json",
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


def _legacy_flat_source_cache_dir(
    *,
    source: str,
    state_code: str,
    jurisdiction_type: str,
    jurisdiction_id: str,
) -> Path:
    """Pre-folder layout: ``{state}/{type}/municipality_{geoid}_*.json``."""
    source_base = GOOGLE_CACHE_DIR if source == "google_civic" else BALLOTPEDIA_CACHE_DIR
    segment = cache_type_segment(jurisdiction_id, jurisdiction_type=jurisdiction_type)
    return source_base / state_code.upper() / segment


def prune_legacy_flat_source_cache(*, dry_run: bool = False) -> int:
    """Remove jurisdiction JSON files sitting directly under ``{state}/{type}/``."""
    typed_prefixes = ("municipality_", "county_", "township_", "school_district_")
    deleted = 0
    for source_base in (GOOGLE_CACHE_DIR, BALLOTPEDIA_CACHE_DIR):
        if not source_base.exists():
            continue
        for path in source_base.rglob("*.json"):
            rel = path.relative_to(source_base)
            if len(rel.parts) != 3:
                continue
            state, segment, filename = rel.parts
            if segment in ("state", "elections") or len(state) != 2:
                continue
            if not any(filename.startswith(p) for p in typed_prefixes):
                continue
            if dry_run:
                print(f"would delete {path}")
            else:
                path.unlink(missing_ok=True)
            deleted += 1
    return deleted


def _prune_jurisdiction_artifacts(*, state_code: str, jurisdiction_type: str, jurisdiction_name: str, jurisdiction_id: str) -> int:
    deleted = 0
    for source in ("google_civic", "ballotpedia"):
        deleted += _prune_old_cache_artifacts(
            _source_cache_dir(
                source=source,
                state_code=state_code,
                jurisdiction_type=jurisdiction_type,
                jurisdiction_name=jurisdiction_name,
                jurisdiction_id=jurisdiction_id,
            ),
            jurisdiction_id,
        )
        deleted += _prune_old_cache_artifacts(
            _legacy_flat_source_cache_dir(
                source=source,
                state_code=state_code,
                jurisdiction_type=jurisdiction_type,
                jurisdiction_id=jurisdiction_id,
            ),
            jurisdiction_id,
        )
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


def _insert_bronze_ballot_measure_row(
    cur,
    *,
    scrape_batch_id: uuid.UUID,
    ocd_id: str,
    state_code: str | None,
    jurisdiction_id: str | None,
    ocd_jurisdiction_id: str | None,
    measure_title: str,
    measure_outcome: str | None,
    source_url: str | None,
    source_name: str,
    raw_row: dict[str, Any],
) -> None:
    """Insert a record_type='ballot_measure' row into bronze.bronze_elections_scraped."""
    cur.execute(
        """
        INSERT INTO bronze.bronze_elections_scraped
            (scrape_batch_id, record_type, ocd_id,
             ocd_jurisdiction_id, state_code, jurisdiction_id,
             measure_title, measure_outcome,
             source_url, source_name, raw_row)
        VALUES (%s, 'ballot_measure', %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            str(scrape_batch_id),
            ocd_id,
            ocd_jurisdiction_id,
            state_code,
            jurisdiction_id,
            measure_title,
            measure_outcome,
            source_url,
            source_name,
            Json(raw_row),
        ),
    )


def _insert_bronze_external_links(
    cur,
    *,
    scrape_batch_id: uuid.UUID,
    source_page_url: str,
    source_page_kind: str | None,
    state_code: str | None,
    jurisdiction_id: str | None,
    ocd_id: str | None,
    links: list[dict[str, Any]],
) -> int:
    """Bulk-insert outbound-link rows. Returns count inserted."""
    if not links:
        return 0
    rows = [
        (
            str(scrape_batch_id),
            source_page_url,
            source_page_kind,
            link.get("target_url"),
            link.get("target_host"),
            link.get("target_kind"),
            link.get("anchor_text"),
            link.get("rel"),
            state_code,
            jurisdiction_id,
            ocd_id,
            Json(link),
        )
        for link in links
        if link.get("target_url")
    ]
    if not rows:
        return 0
    cur.executemany(
        """
        INSERT INTO bronze.bronze_websites_ballotpedia
            (scrape_batch_id, source_page_url, source_page_kind,
             target_url, target_host, target_kind, anchor_text, rel,
             state_code, jurisdiction_id, ocd_id, raw_row)
        VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        rows,
    )
    return len(rows)


async def _capture_ballotpedia_extras(
    *,
    conn,
    cursor,
    ballotpedia,
    scrape_batch_id: uuid.UUID,
    state_code: str,
    jurisdiction_id: str,
    division_id: str | None,
    name: str,
    query_name: str,
    officials_page_html: str | None,
) -> tuple[int, int]:
    """
    Capture jurisdiction-level ballot measures + external links from the officials
    page and the ballot-measures page. Returns ``(n_measures, n_links)`` inserted.

    Failures are non-fatal (logged + swallowed) — measures/links are best-effort
    enrichments, not the primary ingest goal.
    """
    n_measures = 0
    n_links = 0
    bp_source = BALLOTPEDIA_SOURCE_NAME

    # 1. External links from the officials page (if we have its HTML)
    officials_url = ballotpedia.build_city_url(query_name, state_code)
    if officials_page_html:
        try:
            links = ballotpedia.extract_external_links(officials_page_html, officials_url)
            n_links += _insert_bronze_external_links(
                cursor,
                scrape_batch_id=scrape_batch_id,
                source_page_url=officials_url,
                source_page_kind="city",
                state_code=state_code,
                jurisdiction_id=jurisdiction_id,
                ocd_id=division_id,
                links=links,
            )
        except Exception as exc:
            logger.warning("external-link extraction failed for %s: %s", officials_url, exc)

    # 2. Jurisdiction-level ballot measures + that page's external links
    measures_url = ballotpedia.build_jurisdiction_ballot_measures_url(query_name, state_code)
    try:
        measures_html, measures_links = await ballotpedia.fetch_and_extract_external_links(measures_url)
    except Exception as exc:
        logger.warning("ballot-measures fetch failed for %s: %s", measures_url, exc)
        measures_html, measures_links = None, []

    if measures_html:
        try:
            measures = await ballotpedia.get_jurisdiction_ballot_measures(query_name, state_code)
        except Exception as exc:
            logger.warning("ballot-measures parse failed for %s: %s", measures_url, exc)
            measures = []
        for m in measures:
            measure_id = _stable_id(
                "ballotmeasure",
                _stable_key(bp_source, state_code, jurisdiction_id, m.get("measure_title") or ""),
            )
            _insert_bronze_ballot_measure_row(
                cursor,
                scrape_batch_id=scrape_batch_id,
                ocd_id=measure_id,
                state_code=state_code,
                jurisdiction_id=jurisdiction_id,
                ocd_jurisdiction_id=division_id,
                measure_title=m.get("measure_title") or "",
                measure_outcome=m.get("measure_outcome"),
                source_url=m.get("source_url") or measures_url,
                source_name=bp_source,
                raw_row={**m, "jurisdiction_id": jurisdiction_id},
            )
            n_measures += 1
        try:
            n_links += _insert_bronze_external_links(
                cursor,
                scrape_batch_id=scrape_batch_id,
                source_page_url=measures_url,
                source_page_kind="ballot_measures",
                state_code=state_code,
                jurisdiction_id=jurisdiction_id,
                ocd_id=division_id,
                links=measures_links,
            )
        except Exception as exc:
            logger.warning("external-link insert failed for %s: %s", measures_url, exc)

    return n_measures, n_links


def _parse_election_day(value: Any) -> date:
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    if not text:
        return date.today()
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return date.today()


def _persist_voterinfo_bronze(
    cur,
    *,
    scrape_batch_id: uuid.UUID,
    voter_info: dict[str, Any],
    state_code: str,
    jurisdiction_id: str,
    division_id: str,
    civic_address: str,
) -> tuple[int, int, int]:
    """Insert bronze rows from a voterInfoQuery payload. Returns (elections, candidacies, measures)."""
    election_meta = voter_info.get("election") or {}
    civic_election_id = str(voter_info.get("election_id") or election_meta.get("id") or "")
    election_name = election_meta.get("name") or f"Google Civic voter info ({civic_election_id or 'unknown'})"
    election_day = _parse_election_day(election_meta.get("electionDay"))
    source_url = voter_info.get("source_url") or civic_voterinfo_url(
        civic_address,
        election_id=civic_election_id or None,
    )
    election_row_id = _stable_id(
        "election",
        _stable_key(GOOGLE_SOURCE_NAME, civic_election_id, jurisdiction_id, civic_address, election_day.isoformat()),
    )
    _insert_bronze_row(
        cur,
        scrape_batch_id=scrape_batch_id,
        record_type="election",
        ocd_id=election_row_id,
        election_name=election_name,
        election_date_value=election_day,
        election_type="civic_voterinfo",
        election_status="confirmed",
        ocd_jurisdiction_id=division_id,
        state_code=state_code,
        jurisdiction_id=jurisdiction_id,
        candidate_name=None,
        candidate_party=None,
        candidate_post=None,
        candidate_status=None,
        source_url=source_url,
        source_name=GOOGLE_SOURCE_NAME,
        raw_row={
            "source": GOOGLE_SOURCE_NAME,
            "address": civic_address,
            "jurisdiction_id": jurisdiction_id,
            "division_id": division_id,
            "election": election_meta,
            "polling_locations": voter_info.get("polling_locations") or [],
            "early_vote_sites": voter_info.get("early_vote_sites") or [],
            "drop_off_locations": voter_info.get("drop_off_locations") or [],
            "state_officials": voter_info.get("state") or [],
            "normalized_input": voter_info.get("normalizedInput"),
        },
    )
    n_elections = 1
    n_candidacies = 0
    n_measures = 0

    for contest in voter_info.get("contests") or []:
        if not isinstance(contest, dict):
            continue
        contest_type = (contest.get("type") or "").strip()
        office_name = contest.get("office") or contest.get("district") or contest.get("level") or "Office"
        if contest_type.lower() == "referendum" or contest.get("referendumTitle"):
            measure_title = (
                contest.get("referendumTitle")
                or contest.get("referendumBrief")
                or contest.get("ballotTitle")
                or "Referendum"
            )
            measure_id = _stable_id(
                "ballotmeasure",
                _stable_key(GOOGLE_SOURCE_NAME, jurisdiction_id, civic_election_id, measure_title),
            )
            _insert_bronze_ballot_measure_row(
                cur,
                scrape_batch_id=scrape_batch_id,
                ocd_id=measure_id,
                state_code=state_code,
                jurisdiction_id=jurisdiction_id,
                ocd_jurisdiction_id=division_id,
                measure_title=measure_title,
                measure_outcome=None,
                source_url=source_url,
                source_name=GOOGLE_SOURCE_NAME,
                raw_row={**contest, "jurisdiction_id": jurisdiction_id, "election_id": civic_election_id},
            )
            n_measures += 1
            continue

        for candidate in contest.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            person_name = candidate.get("name") or "Unknown candidate"
            candidacy_id = _stable_id(
                "candidacy",
                _stable_key(GOOGLE_SOURCE_NAME, election_row_id, office_name, person_name, civic_election_id),
            )
            _insert_bronze_row(
                cur,
                scrape_batch_id=scrape_batch_id,
                record_type="candidacy",
                ocd_id=candidacy_id,
                election_name=election_name,
                election_date_value=election_day,
                election_type="civic_voterinfo",
                election_status="confirmed",
                ocd_jurisdiction_id=division_id,
                state_code=state_code,
                jurisdiction_id=jurisdiction_id,
                candidate_name=person_name,
                candidate_party=candidate.get("party"),
                candidate_post=office_name,
                candidate_status=contest_type or "candidate",
                source_url=(candidate.get("candidateUrl") or candidate.get("url") or source_url),
                source_name=GOOGLE_SOURCE_NAME,
                raw_row={
                    "source": GOOGLE_SOURCE_NAME,
                    "contest": contest,
                    "candidate": candidate,
                    "jurisdiction_id": jurisdiction_id,
                    "division_id": division_id,
                    "election_id": civic_election_id,
                },
            )
            n_candidacies += 1

    return n_elections, n_candidacies, n_measures


async def _ingest_target(
    *,
    conn,
    api,
    ballotpedia,
    find_ocd_match,
    target: dict[str, Any],
    elections: list[dict[str, Any]],
    elections_payload: dict[str, Any],
    scrape_batch_id: uuid.UUID,
    dry_run: bool,
) -> tuple[int, int, int]:
    name = target["name"]
    state_code = target["state_code"]
    jurisdiction_id = target["jurisdiction_id"]
    jurisdiction_type = target["jurisdiction_type"]
    civic_address = format_civic_address_query(name, state_code)
    division_id = find_ocd_match(name, state_code, jurisdiction_type=jurisdiction_type) or jurisdiction_id
    if not division_id:
        logger.warning("Skipping %s (%s): no OCD match", name, jurisdiction_id)
        return 0, 0, 0

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
        divisions_payload = await api.get_divisions_by_address(civic_address)
        divisions = divisions_payload.get("divisions", {})
        place_keys = [k for k in divisions if "/place:" in k]
        county_keys = [k for k in divisions if "/county:" in k]
        if jurisdiction_type == "municipality" and place_keys:
            division_id = sorted(place_keys, key=len)[-1]
        elif jurisdiction_type == "county" and county_keys:
            division_id = sorted(county_keys, key=len)[-1]
        _write_source_cache(
            source="google_civic",
            state_code=state_code,
            jurisdiction_type=jurisdiction_type,
            jurisdiction_name=name,
            jurisdiction_id=jurisdiction_id,
            relative_name=f"{jurisdiction_id}_divisions",
            payload={
                **divisions_payload,
                "source_url": civic_divisions_by_address_url(civic_address),
                "debug_status": "success",
                "debug_reason": "google_divisions_by_address_ok",
                "jurisdiction_id": jurisdiction_id,
                "state_code": state_code,
                "jurisdiction_name": name,
                "resolved_division_id": division_id,
                "address": civic_address,
                "raw_place_name": name,
            },
        )
    except Exception as divisions_exc:
        logger.warning("Divisions-by-address lookup failed for %s: %s", name, divisions_exc)
        _write_source_cache(
            source="google_civic",
            state_code=state_code,
            jurisdiction_type=jurisdiction_type,
            jurisdiction_name=name,
            jurisdiction_id=jurisdiction_id,
            relative_name=f"{jurisdiction_id}_divisions_error",
            payload={
                "error": sanitize_civic_error_message(str(divisions_exc)),
                "source": "google_civic_divisions_by_address",
                "source_url": civic_divisions_by_address_url(civic_address),
                "debug_status": "error",
                "debug_reason": "google_divisions_by_address_failed",
                "address": civic_address,
                "raw_place_name": name,
                "jurisdiction_id": jurisdiction_id,
                "state_code": state_code,
                "jurisdiction_name": name,
            },
        )

    relevant_elections = elections_for_state(elections, state_code)
    _write_source_cache(
        source="google_civic",
        state_code=state_code,
        jurisdiction_type=jurisdiction_type,
        jurisdiction_name=name,
        jurisdiction_id=jurisdiction_id,
        relative_name=f"{jurisdiction_id}_elections",
        payload=_jurisdiction_elections_cache_payload(
            elections_payload=elections_payload,
            relevant_elections=relevant_elections,
            civic_address=civic_address,
            jurisdiction_id=jurisdiction_id,
            state_code=state_code,
            jurisdiction_name=name,
            jurisdiction_type=jurisdiction_type,
        ),
    )
    if not relevant_elections:
        logger.warning("No elections.electionQuery rows for %s; skipping voterInfo for %s", state_code, name)
        return 0, 0, 0

    voterinfo_payloads: list[dict[str, Any]] = []
    for election in relevant_elections:
        civic_election_id = str(election.get("id") or "")
        if not civic_election_id:
            continue
        try:
            voter_info = await api.get_voter_info(civic_address, election_id=civic_election_id)
            voterinfo_payloads.append(voter_info)
            _write_source_cache(
                source="google_civic",
                state_code=state_code,
                jurisdiction_type=jurisdiction_type,
                jurisdiction_name=name,
                jurisdiction_id=jurisdiction_id,
                relative_name=f"{jurisdiction_id}_voterinfo_{civic_election_id}",
                payload={
                    **voter_info,
                    "debug_status": "success",
                    "debug_reason": "google_voterinfo_ok",
                    "jurisdiction_id": jurisdiction_id,
                    "state_code": state_code,
                    "jurisdiction_name": name,
                    "google_election_id": civic_election_id,
                },
            )
        except Exception as voter_exc:
            logger.warning(
                "voterInfoQuery failed for %s election %s: %s",
                name,
                civic_election_id,
                voter_exc,
            )
            _write_source_cache(
                source="google_civic",
                state_code=state_code,
                jurisdiction_type=jurisdiction_type,
                jurisdiction_name=name,
                jurisdiction_id=jurisdiction_id,
                relative_name=f"{jurisdiction_id}_voterinfo_{civic_election_id}_error",
                payload={
                    "error": sanitize_civic_error_message(str(voter_exc)),
                    "source": "google_civic_voterinfo",
                    "source_url": civic_voterinfo_url(civic_address, election_id=civic_election_id),
                    "debug_status": "error",
                    "debug_reason": "google_voterinfo_failed",
                    "address": civic_address,
                    "raw_place_name": name,
                    "google_election_id": civic_election_id,
                    "jurisdiction_id": jurisdiction_id,
                    "state_code": state_code,
                    "jurisdiction_name": name,
                },
            )

    if dry_run:
        logger.info(
            "[dry-run] %s %s %s (%d voterInfo payload(s))",
            state_code,
            jurisdiction_type,
            name,
            len(voterinfo_payloads),
        )
        return 0, 0, 0

    if not voterinfo_payloads:
        return 0, 0, 0

    total_elections = 0
    total_candidacies = 0
    total_measures = 0
    with conn.cursor() as cur:
        for voter_info in voterinfo_payloads:
            e_n, c_n, m_n = _persist_voterinfo_bronze(
                cur,
                scrape_batch_id=scrape_batch_id,
                voter_info=voter_info,
                state_code=state_code,
                jurisdiction_id=jurisdiction_id,
                division_id=division_id,
                civic_address=civic_address,
            )
            total_elections += e_n
            total_candidacies += c_n
            total_measures += m_n

        if jurisdiction_type == "municipality" and ballotpedia is not None:
            query_name = _normalize_ballotpedia_city_name(name)
            measures_n, links_n = await _capture_ballotpedia_extras(
                conn=conn,
                cursor=cur,
                ballotpedia=ballotpedia,
                scrape_batch_id=scrape_batch_id,
                state_code=state_code,
                jurisdiction_id=jurisdiction_id,
                division_id=division_id,
                name=name,
                query_name=query_name,
                officials_page_html=None,
            )
            if measures_n or links_n:
                logger.info(
                    "Ballotpedia extras for %s/%s: %d ballot_measure(s), %d external link(s)",
                    state_code,
                    jurisdiction_id,
                    measures_n,
                    links_n,
                )

    conn.commit()
    return total_elections, total_elections, total_candidacies


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--states", default=",".join(DEFAULT_PRIORITY_STATES), help=f"Comma-separated state codes (default: {','.join(DEFAULT_PRIORITY_STATES)})")
    parser.add_argument("--include-types", default=",".join(DEFAULT_INCLUDE_TYPES), help=f"Comma-separated jurisdiction categories (default: {','.join(DEFAULT_INCLUDE_TYPES)})")
    parser.add_argument("--limit-per-state", type=int, default=20, help="Cap jurisdictions per state (default: 20)")
    parser.add_argument("--jurisdiction-ids", default="",
                        help="Optional comma-separated jurisdiction_id list to filter targets to (e.g. municipality_0177256). "
                             "Useful for targeted re-test of a specific jurisdiction.")
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
        jurisdiction_ids = tuple(j.strip() for j in args.jurisdiction_ids.split(",") if j.strip())
        targets = _load_targets(conn, states, include_types, args.limit_per_state, jurisdiction_ids)
        logger.info("Loaded %d jurisdictions for bronze election ingest", len(targets))

        scrape_batch_id = uuid.uuid4()
        bronze_google_elections = 0
        bronze_snapshot_elections = 0
        bronze_snapshot_candidacies = 0
        bronze_ballotpedia_rows = 0

        elections_payload_raw = _run_async(api.get_elections(), "fetching Google Civic elections")
        elections_payload = (
            elections_payload_raw
            if isinstance(elections_payload_raw, dict)
            else {"elections": [], "payload": elections_payload_raw}
        )
        all_elections = elections_payload.get("elections", [])
        upcoming_elections = filter_civic_elections(all_elections)
        if len(all_elections) != len(upcoming_elections):
            logger.info(
                "Excluded %d VIP/sandbox election(s) from ingest (e.g. id %s)",
                len(all_elections) - len(upcoming_elections),
                "2000",
            )
        if not args.dry_run:
            _cache_write(
                GOOGLE_CACHE_DIR / "elections",
                "upcoming_elections",
                {**elections_payload, "elections": upcoming_elections},
            )
            with conn.cursor() as cur:
                for election in upcoming_elections:
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
                        election_date_value=_parse_election_day(election.get("electionDay")),
                        election_type="civic_calendar",
                        election_status="confirmed",
                        ocd_jurisdiction_id=division_id,
                        state_code=state_code,
                        jurisdiction_id=division_id,
                        candidate_name=None,
                        candidate_party=None,
                        candidate_post=None,
                        candidate_status=None,
                        source_url=civic_elections_url(),
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
                    elections=upcoming_elections,
                    elections_payload=elections_payload,
                    scrape_batch_id=scrape_batch_id,
                    dry_run=args.dry_run,
                )
                total_snapshot_elections += delta_elections
                total_snapshot_candidacies += delta_candidacies
            return total_snapshot_elections, total_snapshot_candidacies

        bronze_snapshot_elections, bronze_snapshot_candidacies = _run_async(
            _run_all_targets(),
            "ingesting Google Civic/Ballotpedia jurisdiction targets",
        )

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
                _run_async(ballotpedia.close(), "closing Ballotpedia resources")
            except Exception:
                pass
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
