"""
Scrape election information from jurisdiction websites (no Google Civic API).

Writes JSON cache under the scraped-meetings jurisdiction folder, bronze rows to
``bronze.bronze_elections_scraped``, and promotes into c1 election-domain tables.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
import requests
from psycopg2.extras import Json

from scripts.discovery.election_extract_from_html import (
    discover_election_page_urls,
    extract_election_bundle_from_html,
    merge_election_bundles,
    probe_election_path_urls,
)
from scripts.datasources.openstates.sync_elections_to_c1 import sync_jurisdiction_elections_to_c1

logger = logging.getLogger(__name__)

WEBSITE_SOURCE_NAME = "bronze_election_website_scrape"
_UUID_NS = uuid.UUID("c4e8f1a2-9b3d-4e6f-a1c2-8d7e6f5a4b3c")


@dataclass
class JurisdictionElectionResult:
    bronze_election_rows: int = 0
    bronze_candidacy_rows: int = 0
    bronze_measure_rows: int = 0
    c1_elections: int = 0
    c1_contests: int = 0
    c1_candidacies: int = 0
    c1_measures: int = 0
    pages_scraped: int = 0
    error: str | None = None


def _stable_key(*parts: str | None) -> str:
    return "|".join((p or "").strip().lower() for p in parts)


def _stable_id(prefix: str, key: str) -> str:
    from scripts.datasources.openstates.sync_elections_to_c1 import make_ocd_id

    return make_ocd_id(prefix, key)


def _json_safe(value: Any) -> Any:
    """Coerce ``date`` / ``datetime`` in nested dicts for ``psycopg2.extras.Json``."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def _insert_bronze_row(cur, *, scrape_batch_id: uuid.UUID, record_type: str, ocd_id: str, **fields: Any) -> None:
    cur.execute(
        """
        INSERT INTO bronze.bronze_elections_scraped
            (scrape_batch_id, record_type, ocd_id,
             election_name, election_date, election_type, election_status,
             ocd_jurisdiction_id, state_code, jurisdiction_id,
             candidate_name, candidate_party, candidate_post, candidate_status,
             measure_title, measure_summary, measure_classification, measure_outcome,
             source_url, source_name, raw_row)
        VALUES (
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s
        )
        """,
        (
            str(scrape_batch_id),
            record_type,
            ocd_id,
            fields.get("election_name"),
            fields.get("election_date"),
            fields.get("election_type"),
            fields.get("election_status"),
            fields.get("ocd_jurisdiction_id"),
            fields.get("state_code"),
            fields.get("jurisdiction_id"),
            fields.get("candidate_name"),
            fields.get("candidate_party"),
            fields.get("candidate_post"),
            fields.get("candidate_status"),
            fields.get("measure_title"),
            fields.get("measure_summary"),
            fields.get("measure_classification"),
            fields.get("measure_outcome"),
            fields.get("source_url"),
            WEBSITE_SOURCE_NAME,
            Json(_json_safe(fields.get("raw_row") or {})),
        ),
    )


def _write_election_cache(
    cache_dir: Path,
    jurisdiction_id: str,
    payload: dict[str, Any],
) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = cache_dir / f"{jurisdiction_id}_elections_website_{ts}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return path


def _collect_page_html(
    *,
    website_url: str,
    html_by_url: dict[str, str],
    session: requests.Session,
    max_extra_pages: int,
) -> dict[str, str]:
    """Merge contact-scrape HTML with election-specific discovered URLs."""
    pages: dict[str, str] = dict(html_by_url)

    homepage_html = pages.get(website_url) or ""
    if not homepage_html and website_url:
        try:
            resp = session.get(website_url, timeout=12, allow_redirects=True)
            if resp.status_code == 200 and resp.text:
                homepage_html = resp.text
                pages[website_url] = homepage_html
        except requests.RequestException:
            pass

    to_fetch: list[str] = []
    seen = set(pages.keys())
    for url in probe_election_path_urls(website_url, session):
        if url not in seen:
            seen.add(url)
            to_fetch.append(url)
    if homepage_html:
        for url in discover_election_page_urls(website_url, homepage_html):
            if url not in seen:
                seen.add(url)
                to_fetch.append(url)

    for url in to_fetch[:max_extra_pages]:
        try:
            resp = session.get(url, timeout=12, allow_redirects=True)
            if resp.status_code == 200 and resp.text:
                pages[url] = resp.text
        except requests.RequestException as exc:
            logger.debug("election page fetch failed %s: %s", url, exc)
    return pages


def ingest_jurisdiction_elections_from_website(
    database_url: str,
    scrape_batch_id: str,
    *,
    jurisdiction_id: str,
    state_code: str,
    jurisdiction_type: str,
    name: str,
    website_url: str,
    ocd_jurisdiction_id: str | None,
    html_by_url: dict[str, str] | None,
    session: requests.Session,
    cache_dir: Path,
    max_extra_pages: int = 10,
    sync_c1: bool = True,
) -> JurisdictionElectionResult:
    """Crawl election-related pages and persist bronze + c1 rows."""
    result = JurisdictionElectionResult()
    division_id = ocd_jurisdiction_id or jurisdiction_id
    batch_uuid = uuid.UUID(scrape_batch_id)

    try:
        pages = _collect_page_html(
            website_url=website_url,
            html_by_url=html_by_url or {},
            session=session,
            max_extra_pages=max_extra_pages,
        )
        bundles = [
            extract_election_bundle_from_html(html, url)
            for url, html in pages.items()
            if html
        ]
        merged = merge_election_bundles(bundles)
        merged["jurisdiction_id"] = jurisdiction_id
        merged["state_code"] = state_code
        merged["jurisdiction_name"] = name
        merged["source"] = WEBSITE_SOURCE_NAME
        merged["scraped_at"] = datetime.now(timezone.utc).isoformat()
        result.pages_scraped = len(pages)

        _write_election_cache(cache_dir, jurisdiction_id, merged)

        conn = psycopg2.connect(database_url)
        try:
            election_ids: dict[str, str] = {}
            with conn.cursor() as cur:
                for election in merged.get("elections") or []:
                    ename = election.get("name") or "Election"
                    eday = election.get("election_date")
                    ekey = _stable_key(ename, str(eday or ""), jurisdiction_id)
                    election_row_id = _stable_id("election", ekey)
                    election_ids[ekey] = election_row_id
                    _insert_bronze_row(
                        cur,
                        scrape_batch_id=batch_uuid,
                        record_type="election",
                        ocd_id=election_row_id,
                        election_name=ename,
                        election_date=eday,
                        election_type=election.get("election_type") or "unknown",
                        election_status="scraped",
                        ocd_jurisdiction_id=division_id,
                        state_code=state_code,
                        jurisdiction_id=jurisdiction_id,
                        source_url=election.get("source_url"),
                        raw_row={**election, "jurisdiction_id": jurisdiction_id},
                    )
                    result.bronze_election_rows += 1

                default_election_id = next(iter(election_ids.values()), None)
                if not default_election_id and merged.get("candidacies"):
                    fallback_key = _stable_key(jurisdiction_id, "website_election_placeholder")
                    default_election_id = _stable_id("election", fallback_key)
                    _insert_bronze_row(
                        cur,
                        scrape_batch_id=batch_uuid,
                        record_type="election",
                        ocd_id=default_election_id,
                        election_name=f"{name} elections (website scrape)",
                        election_date=None,
                        election_type="unknown",
                        election_status="scraped",
                        ocd_jurisdiction_id=division_id,
                        state_code=state_code,
                        jurisdiction_id=jurisdiction_id,
                        source_url=website_url,
                        raw_row={"placeholder": True, "jurisdiction_id": jurisdiction_id},
                    )
                    result.bronze_election_rows += 1

                for candidacy in merged.get("candidacies") or []:
                    office = candidacy.get("office") or "Office"
                    person = candidacy.get("person_name") or "Unknown"
                    parent_id = default_election_id or _stable_id(
                        "election",
                        _stable_key(jurisdiction_id, "orphan"),
                    )
                    candidacy_id = _stable_id(
                        "candidacy",
                        _stable_key(parent_id, office, person, candidacy.get("source_url")),
                    )
                    _insert_bronze_row(
                        cur,
                        scrape_batch_id=batch_uuid,
                        record_type="candidacy",
                        ocd_id=candidacy_id,
                        election_name=None,
                        election_date=None,
                        election_type=None,
                        election_status=None,
                        ocd_jurisdiction_id=division_id,
                        state_code=state_code,
                        jurisdiction_id=jurisdiction_id,
                        candidate_name=person,
                        candidate_party=candidacy.get("party"),
                        candidate_post=office,
                        candidate_status=candidacy.get("status") or "candidate",
                        source_url=candidacy.get("source_url"),
                        raw_row={**candidacy, "election_id": parent_id, "jurisdiction_id": jurisdiction_id},
                    )
                    result.bronze_candidacy_rows += 1

                for measure in merged.get("ballot_measures") or []:
                    title = measure.get("title") or "Ballot measure"
                    parent_id = default_election_id
                    measure_id = _stable_id(
                        "ballotmeasure",
                        _stable_key(parent_id or jurisdiction_id, title),
                    )
                    _insert_bronze_row(
                        cur,
                        scrape_batch_id=batch_uuid,
                        record_type="ballot_measure",
                        ocd_id=measure_id,
                        election_name=None,
                        election_date=None,
                        election_type=None,
                        election_status=None,
                        ocd_jurisdiction_id=division_id,
                        state_code=state_code,
                        jurisdiction_id=jurisdiction_id,
                        measure_title=title,
                        measure_summary=measure.get("summary"),
                        measure_classification=measure.get("classification"),
                        measure_outcome=None,
                        source_url=measure.get("source_url"),
                        raw_row={**measure, "jurisdiction_id": jurisdiction_id},
                    )
                    result.bronze_measure_rows += 1

            conn.commit()

            if sync_c1:
                counts = sync_jurisdiction_elections_to_c1(
                    conn, scrape_batch_id, jurisdiction_id,
                )
                result.c1_elections = counts.get("elections", 0)
                result.c1_contests = counts.get("contests", 0)
                result.c1_candidacies = counts.get("candidacies", 0)
                result.c1_measures = counts.get("measures", 0)
        finally:
            conn.close()

    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        logger.exception("website election scrape failed for %s", jurisdiction_id)

    return result
