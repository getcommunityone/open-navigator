#!/usr/bin/env python3
"""
Jurisdiction pilot scraper (``scrape_priority_states``) — contacts, YouTube, elections.

**What “pilot” means:** early end-to-end scrape for priority states (AL, GA, IN, MA, WA, WI),
implemented under ``scripts/datasources/jurisdiction_pilot/``. It is the same run as:

    python -m scripts.datasources.jurisdiction_pilot.scrape_priority_states

It is *not* the homepage deep-discovery pipeline (``jurisdiction_discovery_pipeline``).
This runner writes:

- ``bronze.bronze_persons_scraped`` — contacts (+ profile images under ``data/cache/scraped_meetings/``)
- ``bronze.bronze_jurisdiction_youtube_candidates`` — every probe (audit, including rejected noise)
- ``bronze.bronze_jurisdiction_youtube`` — **verified** channels only (website-linked / high-confidence)
- ``bronze.bronze_jurisdictions_{counties,municipalities}_scraped`` — **one primary** channel URL
  + ``youtube_channel_id`` per jurisdiction (for ``load_youtube_events_to_postgres --channel-source counties-scraped``)
- ``bronze.bronze_elections_scraped`` + c1 election tables (with ``--elections``)

Default scope: **counties then municipalities** for AL, GA, IN, MA, WA, WI (~2,300 jurisdictions).
School districts and state-level rows are skipped (no mayors/councils to scrape).

Run (defaults are safe — start with a small slice to validate):

    .venv/bin/python -m scripts.datasources.jurisdiction_pilot.scrape_priority_states \
        --limit-per-state 5

    # Full run, 8 workers:
    .venv/bin/python -m scripts.datasources.jurisdiction_pilot.scrape_priority_states \
        --workers 8

    # Resume a run that was interrupted:
    .venv/bin/python -m scripts.datasources.jurisdiction_pilot.scrape_priority_states \
        --batch-id <uuid-from-prior-run>

    # One state at a time:
    .venv/bin/python -m scripts.datasources.jurisdiction_pilot.scrape_priority_states \
        --states MA --workers 4

    # Contacts + YouTube + website election crawl → bronze + c1_* election tables:
    .venv/bin/python -m scripts.datasources.jurisdiction_pilot.scrape_priority_states \
        --states AL,GA,IN,MA,WA,WI --elections --workers 6

Fault tolerance:
  - Each jurisdiction runs in its own try/except. A single failure logs and continues.
  - DB writes happen per-jurisdiction, so a crash mid-run loses at most the in-flight
    one.
  - A local checkpoint file at
    ``data/bronze/jurisdiction_pilot_progress/<batch_id>.jsonl`` records every completed
    jurisdiction (including zero-row outcomes), so ``--batch-id <id>`` resumes cleanly.

Concurrency:
  - Thread pool sized by ``--workers``. Each worker handles one jurisdiction end-to-end
    (probe seeds → fetch HTML → extract contacts → YouTube discovery → optional
    website election pages → bronze + c1 election-domain tables).
  - Default 6 workers — gentle enough to avoid getting throttled by common municipal
    CMS providers.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Lock
from typing import Any

import re

import httpx
import psycopg2
import requests
import urllib3
from dotenv import load_dotenv

# Silence the InsecureRequestWarning flood. ``website_youtube_search`` intentionally
# sets ``sess.verify = False`` because a chunk of municipal .gov sites still ship
# broken cert chains (self-signed intermediates, expired roots, mismatched CNs).
# Skipping verification is the deliberate choice there; we just don't want the warning
# emitted on every request.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.jurisdictions.jurisdiction_id import ensure_canonical_jurisdiction_id  # noqa: E402
from scripts.datasources.jurisdiction_pilot.load_ocd_jurisdictions import (  # noqa: E402
    find_ocd_match,
)
from scripts.datasources.jurisdiction_pilot.mayor_url_discovery import (  # noqa: E402
    discover_seed_urls,
)
from scripts.datasources.jurisdiction_pilot.youtube_channel_enrich import (  # noqa: E402
    enrich_channel,
)
from scripts.datasources.jurisdiction_pilot.vendor_detection import (  # noqa: E402
    detect_vendor,
)
from scripts.datasources.jurisdiction_pilot.legistar_scraper import (  # noqa: E402
    get_legistar_council_members,
)
from scripts.datasources.jurisdiction_pilot.google_civic_youtube import (  # noqa: E402
    get_youtube_from_civic_api,
)
from scripts.datasources.jurisdiction_pilot.website_youtube_search import (  # noqa: E402
    search_multiple_queries,
)
from scripts.datasources.youtube.youtube_channel_discovery import (  # noqa: E402
    YouTubeChannelDiscovery,
)
from scripts.discovery.bronze_persons_scraped_persist import (  # noqa: E402
    insert_bronze_persons_scraped,
)
from scripts.discovery.bronze_jurisdiction_youtube_persist import (  # noqa: E402
    insert_bronze_jurisdiction_youtube_candidates,
    upsert_bronze_jurisdiction_youtube_verified,
)
from scripts.discovery.youtube_channel_verification import (  # noqa: E402
    DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE,
    rejection_reason_for_channel,
)
from scripts.discovery.sync_youtube_primary_from_jurisdiction_youtube import (  # noqa: E402
    sync_primary_youtube_to_scraped,
)
from scripts.discovery.youtube_primary_channel import (  # noqa: E402
    _channel_url,
    pick_primary_youtube_channel,
)
from scripts.datasources.youtube.youtube_channel_page import canonical_channel_url  # noqa: E402
from scripts.discovery.contact_directory_heuristics import (  # noqa: E402
    classify_contact_directory_page,
)
from scripts.discovery.contact_extract_from_html import (  # noqa: E402
    extract_civicplus_commission_profile_urls_from_html,
    extract_structured_contacts_from_html,
)
from scripts.datasources.jurisdiction_pilot.website_civicplus_meetings import (  # noqa: E402
    scrape_civicplus_meetings,
    write_meetings_snapshot,
)
from scripts.datasources.jurisdiction_pilot.county_municipality_websites import (  # noqa: E402
    scrape_county_municipality_websites,
)
from scripts.discovery.bronze_websites_ballotpedia_persist import (  # noqa: E402
    insert_bronze_websites_ballotpedia,
)
from scripts.discovery.contact_profile_images import (  # noqa: E402
    contact_profile_image_stem_from_name,
    download_profile_images,
    extract_profile_image_jobs,
)
from scripts.discovery.jurisdiction_contact_seed_urls import (  # noqa: E402
    merged_contact_seed_urls,
)
# Reuse the MA pilot's mayor row tagging — generic, not MA-specific.
from scripts.datasources.ma_pilot.mayor_boost import (  # noqa: E402
    is_mayor_seed_url,
    tag_mayor_rows,
)

logger = logging.getLogger("jurisdiction_pilot")

# Loggers that emit one line per HEAD/GET when left at DEBUG (unreadable with -v).
_QUIET_HTTP_LOGGER_NAMES = (
    "urllib3",
    "urllib3.connectionpool",
    "urllib3.util",
    "urllib3.util.retry",
    "httpx",
    "httpx._client",
    "requests",
)


def _quiet_http_loggers() -> None:
    for name in _QUIET_HTTP_LOGGER_NAMES:
        logging.getLogger(name).setLevel(logging.WARNING)


# Submodule DEBUG (probe errors, Civic/YouTube lookups, OCD misses) drowns progress lines.
_QUIET_HELPER_LOGGER_NAMES = (
    "scripts.datasources.jurisdiction_pilot.mayor_url_discovery",
    "scripts.datasources.jurisdiction_pilot.google_civic_youtube",
    "scripts.datasources.jurisdiction_pilot.website_youtube_search",
    "scripts.datasources.jurisdiction_pilot.youtube_channel_enrich",
    "scripts.datasources.jurisdiction_pilot.website_elections",
    "scripts.datasources.jurisdiction_pilot.load_ocd_jurisdictions",
)


def _quiet_helper_loggers() -> None:
    for name in _QUIET_HELPER_LOGGER_NAMES:
        logging.getLogger(name).setLevel(logging.WARNING)


def _jlabel(j: Jurisdiction) -> str:
    """Compact log prefix: state + jurisdiction name."""
    return f"{j.state_code} {j.name}"

DEFAULT_PRIORITY_STATES = ("AL", "GA", "IN", "MA", "WA", "WI")
# Counties first (feeds counties-scraped for YouTube events loader); municipalities second.
DEFAULT_INCLUDE_TYPES = ("county", "municipality")

# Default bar for canonical ``bronze_jurisdiction_youtube`` (candidates table keeps everything).
MIN_CHANNEL_CONFIDENCE = float(
    os.getenv("MIN_CHANNEL_CONFIDENCE", str(DEFAULT_VERIFIED_MIN_OFFICIAL_CONFIDENCE))
)
# Stricter bar for the single primary on ``*_scraped`` (counties-scraped loader reads this).
SCRAPED_PRIMARY_MIN_CONFIDENCE = float(os.getenv("SCRAPED_PRIMARY_MIN_CONFIDENCE", "0.7"))

from scripts.datasources.jurisdiction_pilot.http_fetch import BROWSER_USER_AGENT

_USER_AGENT = BROWSER_USER_AGENT
_REQUEST_TIMEOUT_S = 20
_CHECKPOINT_ROOT = _ROOT / "data" / "bronze" / "jurisdiction_pilot_progress"
_SCRAPED_MEETINGS_ROOT = _ROOT / "data" / "cache" / "scraped_meetings"
_PROGRESS_LOCK = Lock()
_STOP = Event()


# --------------------------------------------------------------------------------------
# Normalized output paths — must match the existing scheme used by older
# ``jurisdiction_discovery_pipeline.py`` and consumed by downstream tools:
#
#   data/cache/scraped_meetings/{STATE}/{type}/{slug}_{geoid_suffix}/_contact_images/
#
# Where ``type`` ∈ {county, municipality}, slug is a snake-cased place name with the
# LSAD suffix stripped (``Tuscaloosa County`` → ``tuscaloosa``; ``Abbeville city`` →
# ``abbeville``; ``Sweet Grass County`` → ``sweet_grass``), and ``geoid_suffix`` is the
# numeric tail of jurisdiction_id (county: 5 digits, municipality: 7 digits).
# --------------------------------------------------------------------------------------


def jurisdiction_output_dir(j: "Jurisdiction") -> Path:
    """Return the canonical ``scraped_meetings/{STATE}/{type}/{slug}_{geoid}/`` dir."""
    from scripts.gemini.transcript_cache_paths import scraped_meetings_jurisdiction_dir

    return scraped_meetings_jurisdiction_dir(
        _SCRAPED_MEETINGS_ROOT,
        state_code=j.state_code,
        jurisdiction_id=j.jurisdiction_id,
        place_name=j.name,
    )


# --------------------------------------------------------------------------------------
# Models
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Jurisdiction:
    jurisdiction_id: str
    state_code: str
    jurisdiction_type: str       # "municipality" / "county"
    name: str                    # organization_name (preferred) or city
    website_url: str


@dataclass
class JurisdictionResult:
    jurisdiction_id: str
    state_code: str
    name: str
    contacts_inserted: int = 0
    mayor_rows_inserted: int = 0
    youtube_inserted: int = 0
    youtube_candidates_inserted: int = 0
    youtube_filtered_out: int = 0
    contact_images_saved: int = 0
    bronze_election_rows: int = 0
    bronze_candidacy_rows: int = 0
    c1_election_rows: int = 0
    c1_candidacy_rows: int = 0
    youtube_events_count: int = 0
    youtube_events_inserted: int = 0
    meetings_events_captured: int = 0
    meetings_agendas_captured: int = 0
    meetings_minutes_captured: int = 0
    municipality_websites_inserted: int = 0
    seed_urls_attempted: int = 0
    seed_urls_succeeded: int = 0
    error: str | None = None
    election_error: str | None = None
    duration_s: float = 0.0
    seeds_used: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------------------
# DB helpers
# --------------------------------------------------------------------------------------


def _resolve_database_url() -> str:
    load_dotenv(_ROOT / ".env")
    url = os.getenv("NEON_DATABASE_URL_DEV", "").strip()
    if not url:
        raise SystemExit("NEON_DATABASE_URL_DEV is not set in .env — refusing to default to prod.")
    return url


def load_jurisdictions(
    database_url: str,
    *,
    states: tuple[str, ...],
    include_types: tuple[str, ...],
    limit_per_state: int | None,
) -> list[Jurisdiction]:
    """
    Pull jurisdictions for the selected states from ``intermediate.int_jurisdiction_websites``.
    One row per jurisdiction (best-priority website per the existing source ordering).
    """
    state_placeholders = ",".join(["%s"] * len(states))
    type_placeholders = ",".join(["%s"] * len(include_types))
    sql = f"""
        WITH ranked AS (
            SELECT DISTINCT ON (
                COALESCE(j.jurisdiction_id, j_geo.jurisdiction_id, w.jurisdiction_id)
            )
                COALESCE(j.jurisdiction_id, j_geo.jurisdiction_id, w.jurisdiction_id)
                    AS jurisdiction_id,
                w.state_code,
                w.jurisdiction_category AS jurisdiction_type,
                COALESCE(
                    NULLIF(btrim(j.name), ''),
                    NULLIF(btrim(j_geo.name), ''),
                    NULLIF(btrim(w.organization_name), ''),
                    CASE
                        WHEN w.jurisdiction_category = 'county' THEN NULL
                        ELSE NULLIF(btrim(w.city), '')
                    END,
                    w.jurisdiction_id
                ) AS name,
                btrim(w.website_url) AS website_url
            FROM intermediate.int_jurisdiction_websites w
            LEFT JOIN intermediate.int_jurisdictions j
              ON j.jurisdiction_id = w.jurisdiction_id
            LEFT JOIN intermediate.int_jurisdictions j_geo
              ON j.jurisdiction_id IS NULL
             AND j_geo.geoid = CASE
                    WHEN w.jurisdiction_id ~* '^(county|municipality|school_district|township)_'
                        THEN regexp_replace(w.jurisdiction_id, '^(county|municipality|school_district|township)_', '', 'i')
                    WHEN w.jurisdiction_id ~ '_([0-9]+)$'
                        THEN (regexp_match(w.jurisdiction_id, '_([0-9]+)$'))[1]
                    ELSE NULL
                 END
             AND j_geo.jurisdiction_type::text = w.jurisdiction_category
            WHERE w.state_code IN ({state_placeholders})
              AND w.jurisdiction_category IN ({type_placeholders})
              AND w.website_url IS NOT NULL
              AND btrim(w.website_url) <> ''
            ORDER BY COALESCE(j.jurisdiction_id, j_geo.jurisdiction_id, w.jurisdiction_id),
                     w.website_record_key
        )
        SELECT jurisdiction_id, state_code, jurisdiction_type, name, website_url
        FROM ranked
        ORDER BY state_code,
                 CASE jurisdiction_type WHEN 'county' THEN 0 ELSE 1 END,
                 jurisdiction_id
    """
    out: list[Jurisdiction] = []
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (*states, *include_types))
            seen: set[str] = set()
            for jid, sc, jtype, name, url in cur.fetchall():
                canonical_id = ensure_canonical_jurisdiction_id(
                    jid,
                    jurisdiction_type=jtype,
                    name=name,
                    database_url=database_url,
                )
                if canonical_id in seen:
                    continue
                seen.add(canonical_id)
                out.append(Jurisdiction(
                    jurisdiction_id=canonical_id, state_code=sc,
                    jurisdiction_type=jtype, name=name, website_url=url,
                ))
    finally:
        conn.close()

    if limit_per_state is not None and limit_per_state > 0:
        capped: list[Jurisdiction] = []
        seen_per_state: dict[str, int] = {}
        for j in out:
            n = seen_per_state.get(j.state_code, 0)
            if n >= limit_per_state:
                continue
            seen_per_state[j.state_code] = n + 1
            capped.append(j)
        out = capped
    return out


# --------------------------------------------------------------------------------------
# Checkpoint
# --------------------------------------------------------------------------------------


def _checkpoint_path(batch_id: str) -> Path:
    return _CHECKPOINT_ROOT / f"{batch_id}.jsonl"


def load_completed_ids(batch_id: str) -> set[str]:
    path = _checkpoint_path(batch_id)
    if not path.exists():
        return set()
    done: set[str] = set()
    with path.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            jid = rec.get("jurisdiction_id")
            if jid:
                done.add(jid)
    return done


def record_checkpoint(batch_id: str, result: JurisdictionResult) -> None:
    path = _checkpoint_path(batch_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({
        "jurisdiction_id": result.jurisdiction_id,
        "state_code": result.state_code,
        "name": result.name,
        "contacts_inserted": result.contacts_inserted,
        "mayor_rows_inserted": result.mayor_rows_inserted,
        "youtube_inserted": result.youtube_inserted,
        "contact_images_saved": result.contact_images_saved,
        "bronze_election_rows": result.bronze_election_rows,
        "bronze_candidacy_rows": result.bronze_candidacy_rows,
        "c1_election_rows": result.c1_election_rows,
        "c1_candidacy_rows": result.c1_candidacy_rows,
        "election_error": result.election_error,
        "seed_urls_attempted": result.seed_urls_attempted,
        "seed_urls_succeeded": result.seed_urls_succeeded,
        "meetings_events_captured": result.meetings_events_captured,
        "meetings_agendas_captured": result.meetings_agendas_captured,
        "meetings_minutes_captured": result.meetings_minutes_captured,
        "municipality_websites_inserted": result.municipality_websites_inserted,
        "error": result.error,
        "duration_s": round(result.duration_s, 2),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    with _PROGRESS_LOCK:
        with path.open("a") as f:
            f.write(line + "\n")


# --------------------------------------------------------------------------------------
# Per-jurisdiction work
# --------------------------------------------------------------------------------------


def _resolve_seed_urls(j: Jurisdiction) -> list[tuple[str, str]]:
    """
    Return ordered ``(url, seed_kind)`` pairs. Priority:

    1. Hand-curated seeds from ``jurisdiction_contact_seed_urls`` (already includes the
       MA pilot's 10 jurisdictions; gets prepended).
    2. Heuristic mayor probes + homepage anchor crawl (``mayor_url_discovery``).
    """
    seeds: list[tuple[str, str]] = []
    seen: set[str] = set()
    is_county = (j.jurisdiction_type or "").strip().lower() == "county"

    for u in merged_contact_seed_urls(j.jurisdiction_id, []):
        if u in seen:
            continue
        seen.add(u)
        if is_county:
            kind = "council"
        else:
            kind = "mayor" if is_mayor_seed_url(u) else "council"
        seeds.append((u, kind))

    # Counties have commissioners, not mayors — skip mayor heuristic probes entirely.
    have_mayor = (not is_county) and any(k == "mayor" for _, k in seeds)
    have_council = any(k == "council" for _, k in seeds)
    if have_mayor and have_council:
        return seeds

    discovered = discover_seed_urls(j.website_url, jurisdiction_type=j.jurisdiction_type)
    if not have_mayor and not is_county:
        for u in discovered.get("mayor", []):
            if u in seen:
                continue
            seen.add(u)
            seeds.append((u, "mayor"))
    if not have_council:
        for u in discovered.get("council", []):
            if u in seen:
                continue
            seen.add(u)
            seeds.append((u, "council"))

    return seeds


def _fetch(url: str, session: requests.Session) -> tuple[int, str]:
    from scripts.datasources.jurisdiction_pilot.http_fetch import fetch_page_html

    status, html, block = fetch_page_html(
        url, session, timeout_s=_REQUEST_TIMEOUT_S, try_playwright=True
    )
    if block:
        # Guessed / probed seeds often 404 or hit bot walls at scale; not actionable at INFO/WARNING.
        logger.debug("fetch blocked for %s: %s", url, block)
        return status, ""
    return status, html


def _scrape_contacts(
    j: Jurisdiction, seeds: list[tuple[str, str]], session: requests.Session, batch_id: str,
) -> tuple[list[dict[str, Any]], int, dict[str, str]]:
    """Return (contact rows, count of seed URLs that responded 200, html_by_url)."""
    rows_out: list[dict[str, Any]] = []
    ok = 0
    html_by_url: dict[str, str] = {}
    scraped_at = datetime.now(timezone.utc).isoformat()
    for url, seed_kind in seeds:
        if _STOP.is_set():
            break
        status, html = _fetch(url, session)
        if status != 200 or not html:
            logger.debug("[%s] skip seed %s (status=%s)", _jlabel(j), url, status)
            continue
        ok += 1
        html_by_url[url] = html
        classification = classify_contact_directory_page(url, html)
        rows = extract_structured_contacts_from_html(html, url)
        tagged_rows = tag_mayor_rows(rows, source_page_url=url)
        is_mayor_page = is_mayor_seed_url(url) or seed_kind == "mayor"
        for r in tagged_rows:
            if not classification["is_directory"] and not (is_mayor_page and r.get("is_mayor")):
                continue
            rows_out.append({
                "source_page_url": url,
                "page_classification": classification["directory_kind"],
                "directory_score": int(classification["score"]),
                # OCD Popolo-aligned keys (Person.name, Membership.role, Membership.organization).
                # The upstream extractor still returns person_name/title_or_role/department, so we
                # remap once here.
                "name": r.get("person_name"),
                "role": r.get("title_or_role"),
                "organization": r.get("department"),
                "email": (r.get("email") or "").lower() or None,
                "phone": r.get("phone"),
                "mailing_address": r.get("mailing_address"),
                "profile_url": r.get("profile_url"),
                "extraction_method": r.get("extraction_method"),
                "raw_row": {
                    **r,
                    "seed_kind": seed_kind,
                    "is_mayor": bool(r.get("is_mayor")),
                },
                "scraped_at": scraped_at,
            })
    rows_out = _enrich_contact_rows_from_profile_pages(
        j, rows_out, html_by_url, session, batch_id, scraped_at,
    )
    return rows_out, ok, html_by_url


def _contact_identity_key(row: dict[str, Any]) -> str:
    name = (row.get("name") or (row.get("raw_row") or {}).get("person_name") or "").strip().lower()
    return name


def _merge_contact_row(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    """Prefer incoming row when it adds email, phone, biography, or profile image."""
    out = {**existing, "raw_row": {**(existing.get("raw_row") or {}), **(incoming.get("raw_row") or {})}}
    for field in ("email", "phone", "mailing_address", "profile_url", "role", "organization"):
        if not out.get(field) and incoming.get(field):
            out[field] = incoming[field]
    if incoming.get("extraction_method") and incoming.get("extraction_method") != existing.get(
        "extraction_method"
    ):
        out["extraction_method"] = incoming["extraction_method"]
    return out


def _enrich_contact_rows_from_profile_pages(
    j: Jurisdiction,
    rows_out: list[dict[str, Any]],
    html_by_url: dict[str, str],
    session: requests.Session,
    batch_id: str,
    scraped_at: str,
    *,
    max_profiles: int = 16,
) -> list[dict[str, Any]]:
    profile_urls: list[str] = []
    seen_profile: set[str] = set()
    from scripts.discovery.contact_extract_from_html import _COUNTY_COMMISSION_PAGE_RE

    for page_url, html in html_by_url.items():
        if not _COUNTY_COMMISSION_PAGE_RE.search(page_url):
            continue
        for u in extract_civicplus_commission_profile_urls_from_html(html, page_url):
            if u in seen_profile or u in html_by_url:
                continue
            seen_profile.add(u)
            profile_urls.append(u)
            if len(profile_urls) >= max_profiles:
                break
        if len(profile_urls) >= max_profiles:
            break

    by_name: dict[str, dict[str, Any]] = {}
    for row in rows_out:
        key = _contact_identity_key(row)
        if key:
            by_name[key] = row

    for url in profile_urls:
        if _STOP.is_set():
            break
        status, html = _fetch(url, session)
        if status != 200 or not html:
            continue
        html_by_url[url] = html
        classification = classify_contact_directory_page(url, html)
        for r in extract_structured_contacts_from_html(html, url):
            name = (r.get("person_name") or "").strip()
            if not name:
                continue
            incoming = {
                "source_page_url": url,
                "page_classification": classification["directory_kind"],
                "directory_score": int(classification["score"]),
                "name": name,
                "role": r.get("title_or_role"),
                "organization": r.get("department"),
                "email": (r.get("email") or "").lower() or None,
                "phone": r.get("phone"),
                "mailing_address": r.get("mailing_address"),
                "profile_url": r.get("profile_url") or url,
                "extraction_method": r.get("extraction_method"),
                "raw_row": {**r, "seed_kind": "council", "profile_page": True},
                "scraped_at": scraped_at,
            }
            key = name.lower()
            if key in by_name:
                by_name[key] = _merge_contact_row(by_name[key], incoming)

    return list(by_name.values()) if by_name else rows_out


async def _download_jurisdiction_contact_images(
    j: Jurisdiction,
    html_by_url: dict[str, str],
    contact_rows: list[dict[str, Any]],
    *,
    max_images_per_jurisdiction: int = 60,
) -> list[dict[str, Any]]:
    """
    Pull profile-image jobs from every fetched HTML page, then download them under
    ``jurisdiction_output_dir(j) / "_contact_images" / "{stem}.png"``.

    Mutates ``contact_rows`` in place by setting ``raw_row['profile_image_filename']``
    when an image was successfully saved that corresponds (by image_url) to a row.

    Returns the per-job manifest from ``download_profile_images``.
    """
    if not html_by_url:
        return []

    # Collect image-extraction jobs across every fetched page; dedupe by image URL.
    jobs: list[dict[str, Any]] = []
    seen_image_urls: set[str] = set()
    for url, html in html_by_url.items():
        try:
            page_jobs = extract_profile_image_jobs(html, url, max_jobs=80)
        except Exception as exc:
            logger.debug("[%s] image-job extract error on %s: %s", _jlabel(j), url, exc)
            continue
        for pj in page_jobs:
            img_url = (pj.get("image_url") or "").strip()
            if not img_url or img_url in seen_image_urls:
                continue
            seen_image_urls.add(img_url)
            jobs.append({
                "image_url": img_url,
                "person_name": pj.get("person_name") or "",
                "title_or_role": pj.get("title_or_role") or "",
                "source_page_url": pj.get("source_page_url") or url,
            })
            if len(jobs) >= max_images_per_jurisdiction:
                break
        if len(jobs) >= max_images_per_jurisdiction:
            break

    if not jobs:
        return []

    out_dir = jurisdiction_output_dir(j) / "_contact_images"
    referer = j.website_url or jobs[0].get("source_page_url") or ""
    async with httpx.AsyncClient(
        follow_redirects=True, timeout=60.0,
        headers={"User-Agent": _USER_AGENT},
    ) as client:
        manifest = await download_profile_images(
            client, jobs, out_dir,
            referer=referer,
            max_images=max_images_per_jurisdiction,
            save_as_png=True,
        )

    # Index by image_url so we can stamp the filename back onto the matching contact row.
    saved_by_url: dict[str, str] = {}
    for entry in manifest:
        fname = entry.get("saved_filename")
        u = entry.get("image_url")
        if fname and u:
            saved_by_url[u] = fname

    if saved_by_url:
        for row in contact_rows:
            raw = row.get("raw_row") or {}
            img = (raw.get("profile_image_url") or "").strip()
            if img and img in saved_by_url:
                raw["profile_image_filename"] = saved_by_url[img]
                # Also surface the local relative path for downstream queries
                raw["profile_image_local_path"] = str((out_dir / saved_by_url[img]).resolve())
                row["raw_row"] = raw

    return manifest


def _discover_youtube(
    j: Jurisdiction,
    session: requests.Session,
    *,
    cookies_file: str | None = None,
) -> list[dict[str, Any]]:
    """
    Discover channels via verified sources, then enrich each with description +
    back-link + officialness score before returning rows ready for the bronze table.

    Priority order:
    1. Google Civic Information API (verified official handles)
    2. Website search (channels linked from jurisdiction website)
    3. Pattern matching (heuristic handle guessing)
    """
    scraped_at = datetime.now(timezone.utc).isoformat()
    raw_channels: list[dict[str, Any]] = []
    seen: set[str] = set()

    # Priority 1: Google Civic Information API (most reliable — verified official handles).
    civic_urls = get_youtube_from_civic_api(j.name, j.state_code)
    for url in civic_urls:
        if url not in seen:
            seen.add(url)
            raw_channels.append({
                "channel_url": url,
                "discovery_method": "civic_api",
            })
    if civic_urls:
        logger.debug("[%s] YouTube from Civic API=%d", _jlabel(j), len(civic_urls))

    # Priority 2: Search the jurisdiction's website for YouTube links.
    if not raw_channels:
        website_channel_urls = search_multiple_queries(
            j.website_url,
            session=session,
        )
        for url in website_channel_urls:
            if url not in seen:
                seen.add(url)
                raw_channels.append({
                    "channel_url": url,
                    "discovery_method": "website_search",
                })
        if website_channel_urls:
            logger.debug("[%s] YouTube on website=%d", _jlabel(j), len(website_channel_urls))

    # Priority 3: Fall back to pattern matching if other methods found nothing.
    if not raw_channels:
        async def _run() -> list[dict[str, Any]]:
            # Pattern matching only: @CityName, CityOfName, etc. (no API search).
            async with YouTubeChannelDiscovery(youtube_api_key=None) as yt:
                city = j.name if j.jurisdiction_type == "municipality" else None
                county = j.name if j.jurisdiction_type == "county" else None
                # Build handle patterns without calling _search_youtube_api
                patterns = yt._generate_handle_patterns(
                    city or county or j.name,
                    j.state_code,
                    county if j.jurisdiction_type == "county" else None,
                    include_city_patterns=(j.jurisdiction_type != "county"),
                )
                channels = []
                for handle in patterns:
                    url = f"https://www.youtube.com/@{handle}"
                    channel_info = await yt._check_channel_exists(url, "pattern_match")
                    if channel_info:
                        channels.append(channel_info)
            return channels

        fallback_channels = asyncio.run(_run())
        for ch in fallback_channels:
            url = ch.get("channel_url")
            if url and url not in seen:
                seen.add(url)
                raw_channels.append(ch)

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for ch in raw_channels:
        url = ch.get("channel_url")
        if not url or url in seen:
            continue
        seen.add(url)
        enriched = enrich_channel(
            channel=ch,
            jurisdiction_name=j.name,
            jurisdiction_state_code=j.state_code,
            jurisdiction_homepage=j.website_url,
            jurisdiction_type=j.jurisdiction_type,
            session=session,
            cookies_file=cookies_file,
        )
        from scripts.datasources.youtube.pattern_match_gate import (
            is_pattern_match_discovery,
        )

        row = {
            "youtube_channel_url": url,
            "youtube_channel_id": enriched.get("channel_id"),
            "channel_title": enriched.get("channel_title"),
            "subscriber_count": enriched.get("subscriber_count"),
            "video_count": enriched.get("video_count"),
            "view_count": enriched.get("view_count"),
            "latest_upload": str(enriched.get("latest_upload") or ""),
            "discovery_method": enriched.get("discovery_method") or ch.get("discovery_method"),
            "channel_description": enriched.get("channel_description"),
            "back_links_to_jurisdiction_website": enriched.get("back_links_to_jurisdiction_website"),
            "official_meeting_confidence": enriched.get("official_meeting_confidence"),
            "external_links": enriched.get("external_links") or [],
            "jurisdiction_website_back_links": enriched.get("jurisdiction_website_back_links") or [],
            "channel_purpose": enriched.get("channel_purpose"),
            "raw_row": enriched,
            "scraped_at": scraped_at,
        }
        rejection = rejection_reason_for_channel(
            row,
            jurisdiction_type=j.jurisdiction_type,
            jurisdiction_name=j.name,
            jurisdiction_state_code=j.state_code,
            jurisdiction_homepage=j.website_url or "",
            min_confidence=MIN_CHANNEL_CONFIDENCE,
        )
        row["rejection_reason"] = rejection
        row["is_verified"] = rejection is None
        if is_pattern_match_discovery(enriched) and rejection == "pattern_match_gate_failed":
            logger.debug(
                "[%s] pattern_match rejected: %s (%s)",
                _jlabel(j),
                url,
                enriched.get("channel_title"),
            )
        rows.append(row)
    return rows


def _promote_primary_youtube_to_scraped(
    database_url: str,
    *,
    jurisdiction_id: str,
    jurisdiction_type: str,
    channels: list[dict[str, Any]],
) -> None:
    """Write the best high-confidence primary channel (URL + ``UC`` id) onto ``*_scraped``."""
    url, method, conf = pick_primary_youtube_channel(channels)
    if not url or jurisdiction_type not in ("county", "municipality"):
        return
    channel_id = ""
    for ch in channels:
        if _channel_url(ch) == url:
            channel_id = (
                str(ch.get("youtube_channel_id") or ch.get("channel_id") or "").strip()
            )
            break
    promo_url = canonical_channel_url(channel_id) if channel_id.startswith("UC") else url
    tbl = (
        "bronze.bronze_jurisdictions_counties_scraped"
        if jurisdiction_type == "county"
        else "bronze.bronze_jurisdictions_municipalities_scraped"
    )
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE {tbl} s
                SET youtube_channel_url = %s,
                    youtube_channel_id = %s,
                    youtube_channel_selection_method = %s,
                    youtube_channel_selection_confidence = %s,
                    discovered_at = NOW()
                FROM intermediate.int_jurisdictions j
                WHERE j.jurisdiction_id = %s
                  AND j.geoid = s.geoid
                  AND j.jurisdiction_type::text = %s
                """,
                (promo_url, channel_id or None, method, conf, jurisdiction_id, jurisdiction_type),
            )
        conn.commit()
    finally:
        conn.close()


def _count_youtube_events(database_url: str, jurisdiction_id: str) -> int:
    """Rows in ``bronze.bronze_events_youtube`` for this jurisdiction (catalog size)."""
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int
                FROM bronze.bronze_events_youtube
                WHERE jurisdiction_id = %s
                """,
                (jurisdiction_id,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0
    finally:
        conn.close()


def _load_youtube_events_for_primary(
    database_url: str,
    j: Jurisdiction,
    *,
    channel_id: str,
    channel_url: str,
    channel_title: str,
    discovery_method: str,
    confidence: float | None,
    max_videos: int,
    skip_transcripts: bool,
    cookies_file: str | None,
) -> int:
    """Catalog videos/streams for the promoted primary channel; returns rows written."""
    from scripts.datasources.youtube.load_youtube_events_to_postgres import YouTubeEventsLoader

    loader = YouTubeEventsLoader(
        database_url=database_url,
        youtube_api_key=os.getenv("YOUTUBE_API_KEY"),
        max_videos_per_channel=max_videos,
        fetch_transcripts=not skip_transcripts,
        cookies_file=cookies_file,
    )
    try:
        jurisdiction = {
            "jurisdiction_id": j.jurisdiction_id,
            "jurisdiction_name": j.name,
            "state_code": j.state_code,
            "state": j.state_code,
            "jurisdiction_type": j.jurisdiction_type,
            "youtube_channels": [
                {
                    "channel_id": channel_id,
                    "channel_url": channel_url,
                    "channel_title": channel_title or j.name,
                    "channel_type": "municipal",
                    "discovery_method": discovery_method or "website_scrape",
                    "confidence": confidence,
                }
            ],
        }
        return int(loader.process_jurisdiction(jurisdiction) or 0)
    finally:
        loader.conn.close()


def _process_one(
    j: Jurisdiction,
    batch_id: str,
    database_url: str,
    *,
    skip_youtube: bool,
    skip_images: bool = False,
    scrape_elections: bool = False,
    skip_elections_c1_sync: bool = False,
    elections_max_pages: int = 10,
    youtube_cookies_file: str | None = None,
    load_youtube_events: bool = False,
    youtube_events_max_videos: int = 100,
    youtube_events_skip_transcripts: bool = True,
) -> JurisdictionResult:
    """Full pipeline for one jurisdiction. Catches everything; never raises."""
    result = JurisdictionResult(
        jurisdiction_id=j.jurisdiction_id, state_code=j.state_code, name=j.name,
    )
    start = time.monotonic()
    session = requests.Session()
    session.headers["User-Agent"] = _USER_AGENT

    # Find OCD ID for this jurisdiction
    ocd_id = find_ocd_match(j.name, j.state_code, jurisdiction_type=j.jurisdiction_type)

    # Detect vendor platform (Legistar, Granicus, etc.) for vendor-specific optimizations
    vendor_type = "unknown"
    vendor_info: dict[str, Any] = {}
    try:
        resp = session.get(j.website_url, timeout=10, allow_redirects=True)
        if resp.status_code == 200:
            vendor_info = detect_vendor(resp.text, j.website_url)
            vendor_type = vendor_info.get("platform", "unknown")
    except Exception as exc:
        logger.debug("[%s] vendor detection failed: %s", _jlabel(j), exc)
    logger.debug("[%s] vendor=%s", _jlabel(j), vendor_type)

    try:
        seeds = _resolve_seed_urls(j)
        result.seeds_used = [u for u, _ in seeds]
        result.seed_urls_attempted = len(seeds)

        # Priority 1: Try Legistar for council members (high-confidence official contacts)
        legistar_contacts = []
        if vendor_type == "legistar":
            # Extract Legistar instance URL from vendor_info
            legistar_url = vendor_info.get("legistar_url") or j.website_url
            legistar_members = get_legistar_council_members(legistar_url)
            if legistar_members:
                legistar_contacts = legistar_members
                logger.debug("[%s] Legistar council members=%d", _jlabel(j), len(legistar_contacts))

        # Priority 2: Scrape website contacts
        contact_rows, ok, html_by_url = _scrape_contacts(j, seeds, session, batch_id)
        result.seed_urls_succeeded = ok

        # Download contact images BEFORE the DB insert so saved filenames can be stamped
        # onto each row's raw_row payload. Images land at
        # data/cache/scraped_meetings/{STATE}/{type}/{slug}_{geoid}/_contact_images/.
        # Skip on opt-out, on stop signal, or when no HTML pages were fetched.
        if not skip_images and not _STOP.is_set() and html_by_url:
            try:
                manifest = asyncio.run(
                    _download_jurisdiction_contact_images(j, html_by_url, contact_rows)
                )
                saved = sum(1 for m in manifest if m.get("saved_filename"))
                result.contact_images_saved = saved
                if saved:
                    logger.debug("[%s] saved %d contact image(s)", _jlabel(j), saved)
            except Exception as exc:
                logger.debug("[%s] image download failed: %s", _jlabel(j), exc)

        # Merge Legistar + scraped contacts (Legistar has priority)
        all_contacts = legistar_contacts + contact_rows

        result.mayor_rows_inserted = sum(
            1 for r in all_contacts if r.get("raw_row", {}).get("is_mayor")
        )

        if all_contacts:
            result.contacts_inserted = insert_bronze_persons_scraped(
                database_url,
                scrape_batch_id=batch_id,
                jurisdiction_id=j.jurisdiction_id,
                state_code=j.state_code,
                ocd_id=ocd_id,
                rows=all_contacts,
            )

        if not _STOP.is_set() and j.website_url:
            try:
                meeting_capture = scrape_civicplus_meetings(
                    j.website_url,
                    session,
                    html_by_url=html_by_url,
                )
                result.meetings_events_captured = meeting_capture.events_count
                result.meetings_agendas_captured = meeting_capture.agendas
                result.meetings_minutes_captured = meeting_capture.minutes
                write_meetings_snapshot(
                    jurisdiction_output_dir(j) / "_pilot_meetings.json",
                    jurisdiction_id=j.jurisdiction_id,
                    homepage_url=j.website_url,
                    capture=meeting_capture,
                    scrape_batch_id=batch_id,
                )
            except Exception as exc:
                logger.debug("[%s] CivicPlus meetings capture failed: %s", _jlabel(j), exc)

        if not _STOP.is_set() and j.jurisdiction_type == "county" and j.website_url:
            try:
                muni_rows, muni_page = scrape_county_municipality_websites(
                    county_name=j.name,
                    state_code=j.state_code,
                    county_website_url=j.website_url,
                    session=session,
                    html_by_url=html_by_url,
                )
                if muni_rows:
                    for row in muni_rows:
                        row["jurisdiction_id"] = j.jurisdiction_id
                        row["ocd_id"] = ocd_id
                    result.municipality_websites_inserted = insert_bronze_websites_ballotpedia(
                        database_url,
                        scrape_batch_id=batch_id,
                        rows=muni_rows,
                    )
                    if muni_page:
                        logger.debug(
                            "[%s] municipality websites=%d from %s",
                            _jlabel(j),
                            result.municipality_websites_inserted,
                            muni_page,
                        )
            except Exception as exc:
                logger.debug("[%s] county municipality websites failed: %s", _jlabel(j), exc)

        if not skip_youtube and not _STOP.is_set():
            yt_rows = _discover_youtube(j, session, cookies_file=youtube_cookies_file)
            verified_rows = [r for r in yt_rows if r.get("is_verified")]
            result.youtube_filtered_out = len(yt_rows) - len(verified_rows)
            if yt_rows:
                result.youtube_candidates_inserted = insert_bronze_jurisdiction_youtube_candidates(
                    database_url,
                    scrape_batch_id=batch_id,
                    jurisdiction_id=j.jurisdiction_id,
                    state_code=j.state_code,
                    jurisdiction_type=j.jurisdiction_type,
                    jurisdiction_name=j.name,
                    ocd_id=ocd_id,
                    website_url=j.website_url,
                    rows=yt_rows,
                )
            if verified_rows:
                result.youtube_inserted = upsert_bronze_jurisdiction_youtube_verified(
                    database_url,
                    scrape_batch_id=batch_id,
                    jurisdiction_id=j.jurisdiction_id,
                    state_code=j.state_code,
                    jurisdiction_type=j.jurisdiction_type,
                    jurisdiction_name=j.name,
                    ocd_id=ocd_id,
                    website_url=j.website_url,
                    rows=verified_rows,
                )
                # One primary on *_scraped for downstream (counties-scraped channel source).
                primary_candidates = [
                    r
                    for r in verified_rows
                    if (r.get("official_meeting_confidence") or 0.0)
                    >= SCRAPED_PRIMARY_MIN_CONFIDENCE
                ]
                if primary_candidates and j.jurisdiction_type in ("county", "municipality"):
                    _promote_primary_youtube_to_scraped(
                        database_url,
                        jurisdiction_id=j.jurisdiction_id,
                        jurisdiction_type=j.jurisdiction_type,
                        channels=primary_candidates,
                    )
                    if load_youtube_events and not _STOP.is_set():
                        primary = pick_primary_youtube_channel(primary_candidates)
                        promo_url = primary[0] if primary else ""
                        primary_row = next(
                            (
                                r
                                for r in primary_candidates
                                if _channel_url(r) == promo_url
                            ),
                            primary_candidates[0],
                        )
                        channel_id = str(
                            primary_row.get("youtube_channel_id")
                            or primary_row.get("channel_id")
                            or ""
                        ).strip()
                        if channel_id.startswith("UC"):
                            try:
                                result.youtube_events_inserted = _load_youtube_events_for_primary(
                                    database_url,
                                    j,
                                    channel_id=channel_id,
                                    channel_url=promo_url
                                    or canonical_channel_url(channel_id),
                                    channel_title=str(
                                        primary_row.get("channel_title") or j.name
                                    ),
                                    discovery_method=str(
                                        primary_row.get("discovery_method") or ""
                                    ),
                                    confidence=float(
                                        primary_row.get("official_meeting_confidence") or 0
                                    )
                                    or None,
                                    max_videos=youtube_events_max_videos,
                                    skip_transcripts=youtube_events_skip_transcripts,
                                    cookies_file=youtube_cookies_file,
                                )
                            except Exception as exc:
                                logger.warning(
                                    "[%s] YouTube events load failed: %s",
                                    _jlabel(j),
                                    exc,
                                )

        if scrape_elections and not _STOP.is_set():
            from scripts.datasources.jurisdiction_pilot.website_elections import (
                ingest_jurisdiction_elections_from_website,
            )

            election_cache_dir = jurisdiction_output_dir(j) / "_downloads" / "website_elections"
            election_result = ingest_jurisdiction_elections_from_website(
                database_url,
                batch_id,
                jurisdiction_id=j.jurisdiction_id,
                state_code=j.state_code,
                jurisdiction_type=j.jurisdiction_type,
                name=j.name,
                website_url=j.website_url,
                ocd_jurisdiction_id=ocd_id,
                html_by_url=html_by_url,
                session=session,
                cache_dir=election_cache_dir,
                max_extra_pages=elections_max_pages,
                sync_c1=not skip_elections_c1_sync,
            )
            result.bronze_election_rows = election_result.bronze_election_rows
            result.bronze_candidacy_rows = election_result.bronze_candidacy_rows
            result.c1_election_rows = election_result.c1_elections
            result.c1_candidacy_rows = election_result.c1_candidacies
            if election_result.error:
                result.election_error = election_result.error
    except Exception as exc:  # fault tolerance: never let one jurisdiction kill the run
        result.error = f"{type(exc).__name__}: {exc}"
        logger.exception("[%s] %s failed", j.state_code, j.jurisdiction_id)

    try:
        result.youtube_events_count = _count_youtube_events(database_url, j.jurisdiction_id)
    except Exception as exc:
        logger.debug("[%s] youtube events count failed: %s", _jlabel(j), exc)

    result.duration_s = time.monotonic() - start
    return result


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------


def _install_sigint_handler() -> None:
    def _handler(_signum, _frame):  # type: ignore[no-untyped-def]
        if _STOP.is_set():
            logger.warning("Second Ctrl-C — exiting hard.")
            os._exit(130)
        logger.warning("Ctrl-C: finishing in-flight jurisdictions then stopping (Ctrl-C again to abort).")
        _STOP.set()
    signal.signal(signal.SIGINT, _handler)


def main(argv: list[str] | None = None) -> int:
    global MIN_CHANNEL_CONFIDENCE
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--states", default=",".join(DEFAULT_PRIORITY_STATES),
                   help=f"Comma-separated state codes (default: {','.join(DEFAULT_PRIORITY_STATES)})")
    p.add_argument("--include-types", default=",".join(DEFAULT_INCLUDE_TYPES),
                   help=f"Comma-separated jurisdiction categories (default: {','.join(DEFAULT_INCLUDE_TYPES)})")
    p.add_argument("--limit-per-state", type=int, default=None,
                   help="Cap jurisdictions per state (default: no cap).")
    p.add_argument("--workers", type=int, default=6,
                   help="Concurrent jurisdiction workers (default: 6).")
    p.add_argument("--batch-id", default=None,
                   help="Resume an existing batch — already-completed jurisdictions are skipped.")
    p.add_argument("--skip-youtube", action="store_true")
    p.add_argument(
        "--elections",
        action="store_true",
        help=(
            "After contacts/YouTube, crawl the jurisdiction website for election/candidate/ballot "
            "pages (HTML heuristics), write cache under _downloads/website_elections/, load "
            "bronze.bronze_elections_scraped, and promote to c1_* election tables."
        ),
    )
    p.add_argument(
        "--elections-max-pages",
        type=int,
        default=10,
        help="Max additional election-themed pages to fetch per jurisdiction (default: 10).",
    )
    p.add_argument(
        "--elections-skip-c1-sync",
        action="store_true",
        help="With --elections, write bronze only; run sync_elections_to_c1 separately.",
    )
    p.add_argument(
        "--skip-images", action="store_true",
        help="Don't download contact profile images (default: download to "
             "data/cache/scraped_meetings/<STATE>/<type>/<slug>_<geoid>/_contact_images/).",
    )
    p.add_argument(
        "--min-channel-confidence", type=float, default=None,
        help=(
            "Drop YouTube rows with official_meeting_confidence below this threshold "
            f"(default: {MIN_CHANNEL_CONFIDENCE:.2f} or MIN_CHANNEL_CONFIDENCE env var). "
            "Set 0 to persist everything (audit mode); set 0.7+ for high precision."
        ),
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Resolve jurisdictions and print the plan; don't fetch or write.")
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="DEBUG for jurisdiction_pilot only (not urllib3 or URL probe modules).",
    )
    p.add_argument(
        "--http-debug",
        action="store_true",
        help="Log every HTTP request from urllib3/httpx/requests (very noisy).",
    )
    p.add_argument(
        "--cookies",
        type=str,
        default=os.getenv("YOUTUBE_COOKIES_FILE", "youtube_cookies.txt"),
        help=(
            "Netscape cookies.txt for YouTube channel page fetches (resolve @handle → UC). "
            "Default: youtube_cookies.txt or YOUTUBE_COOKIES_FILE env."
        ),
    )
    p.add_argument(
        "--progress-every",
        type=int,
        default=10,
        metavar="N",
        help="Log a progress line every N completed jurisdictions (default: 10; use 1 for live terminal status).",
    )
    p.add_argument(
        "--jurisdiction-id",
        default="",
        help="Comma-separated jurisdiction_id filter (e.g. augusta_..., county_13047).",
    )
    p.add_argument(
        "--youtube-debug",
        action="store_true",
        help="DEBUG logs for website YouTube crawl, enrich, and Civic API helpers.",
    )
    p.add_argument(
        "--youtube-events",
        action="store_true",
        help=(
            "After promoting a primary YouTube channel, catalog videos into "
            "bronze.bronze_events_youtube (slow; uses YOUTUBE_API_KEY)."
        ),
    )
    p.add_argument(
        "--youtube-events-max-videos",
        type=int,
        default=100,
        help="With --youtube-events, max videos per channel (default: 100).",
    )
    p.add_argument(
        "--youtube-events-transcripts",
        action="store_true",
        help="With --youtube-events, fetch captions (default: skip for pilot speed).",
    )
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if not args.http_debug:
        _quiet_http_loggers()
    _quiet_helper_loggers()
    if args.verbose:
        logging.getLogger("jurisdiction_pilot").setLevel(logging.DEBUG)
    if args.youtube_debug or args.verbose:
        for name in _QUIET_HELPER_LOGGER_NAMES:
            logging.getLogger(name).setLevel(logging.DEBUG)

    states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip())
    include_types = tuple(t.strip().lower() for t in args.include_types.split(",") if t.strip())
    if not states or not include_types:
        logger.error("--states and --include-types must be non-empty")
        return 2

    if args.min_channel_confidence is not None:
        MIN_CHANNEL_CONFIDENCE = args.min_channel_confidence
    logger.info("YouTube hard filter: official_meeting_confidence >= %.2f", MIN_CHANNEL_CONFIDENCE)

    cookies_path = (args.cookies or "").strip()
    if cookies_path and not Path(cookies_path).is_file():
        logger.warning("YouTube cookies file not found: %s (@handle resolution may fail)", cookies_path)
        cookies_path = ""

    database_url = _resolve_database_url()
    batch_id = args.batch_id or str(uuid.uuid4())
    done_ids = load_completed_ids(batch_id) if args.batch_id else set()

    logger.info("Loading jurisdictions for %s (%s) limit_per_state=%s",
                states, include_types, args.limit_per_state)
    targets = load_jurisdictions(
        database_url, states=states, include_types=include_types,
        limit_per_state=args.limit_per_state,
    )
    id_filter = {x.strip() for x in (args.jurisdiction_id or "").split(",") if x.strip()}
    if id_filter:
        targets = [j for j in targets if j.jurisdiction_id in id_filter]
        logger.info("Filtered to %d jurisdiction(s) matching --jurisdiction-id", len(targets))
    pending = [j for j in targets if j.jurisdiction_id not in done_ids]
    logger.info("Batch %s — %d jurisdiction(s) pending (%d already completed in prior run)",
                batch_id, len(pending), len(done_ids))

    if args.dry_run:
        for j in pending[:20]:
            print(f"  {j.state_code} {j.jurisdiction_id} {j.name!r} -> {j.website_url}")
        if len(pending) > 20:
            print(f"  ... and {len(pending) - 20} more")
        return 0

    if not pending:
        print("Nothing to do (all jurisdictions complete in this batch).")
        return 0

    if args.elections:
        logger.info(
            "Website election scrape enabled (max %d extra pages per jurisdiction)",
            args.elections_max_pages,
        )
    if args.youtube_events:
        logger.info(
            "YouTube events catalog enabled (max %d videos/channel, transcripts=%s)",
            args.youtube_events_max_videos,
            args.youtube_events_transcripts,
        )

    _install_sigint_handler()
    start = time.monotonic()
    completed = 0
    totals = {
        "contacts": 0, "mayors": 0, "youtube": 0,
        "youtube_filtered": 0, "images": 0, "errors": 0,
        "bronze_elections": 0, "bronze_candidacies": 0, "c1_elections": 0, "c1_candidacies": 0,
        "election_errors": 0, "events": 0, "events_inserted": 0,
    }

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                _process_one,
                j,
                batch_id,
                database_url,
                skip_youtube=args.skip_youtube,
                skip_images=args.skip_images,
                scrape_elections=args.elections,
                skip_elections_c1_sync=args.elections_skip_c1_sync,
                elections_max_pages=args.elections_max_pages,
                youtube_cookies_file=cookies_path or None,
                load_youtube_events=args.youtube_events,
                youtube_events_max_videos=args.youtube_events_max_videos,
                youtube_events_skip_transcripts=not args.youtube_events_transcripts,
            ): j
            for j in pending
        }
        for fut in as_completed(futures):
            j = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:  # extra safety net
                logger.exception("[%s] worker raised for %s", j.state_code, j.jurisdiction_id)
                result = JurisdictionResult(
                    jurisdiction_id=j.jurisdiction_id, state_code=j.state_code,
                    name=j.name, error=f"{type(exc).__name__}: {exc}",
                )

            record_checkpoint(batch_id, result)
            completed += 1
            totals["contacts"] += result.contacts_inserted
            totals["mayors"] += result.mayor_rows_inserted
            totals["youtube"] += result.youtube_inserted
            totals["youtube_filtered"] += result.youtube_filtered_out
            totals["images"] += result.contact_images_saved
            totals["bronze_elections"] += result.bronze_election_rows
            totals["bronze_candidacies"] += result.bronze_candidacy_rows
            totals["c1_elections"] += result.c1_election_rows
            totals["c1_candidacies"] += result.c1_candidacy_rows
            if result.error:
                totals["errors"] += 1
            if result.election_error:
                totals["election_errors"] += 1
            totals["events"] += result.youtube_events_count
            totals["events_inserted"] += result.youtube_events_inserted

            pe = max(1, int(args.progress_every))
            if completed % pe == 0 or completed == len(pending):
                elapsed = time.monotonic() - start
                rate = completed / elapsed if elapsed > 0 else 0
                eta_s = (len(pending) - completed) / rate if rate > 0 else 0
                logger.info(
                    "[%d/%d] [%s] %s url=%s contacts=%d mayors=%d youtube=%d "
                    "meetings=%d agendas=%d minutes=%d muni_links=%d yt_events=%d "
                    "bronze_el=%d c1_el=%d err=%s | "
                    "totals contacts=%d youtube=%d yt_events=%d c1_el=%d errors=%d | "
                    "rate=%.2f/s ETA=%.0fs",
                    completed, len(pending), j.state_code, j.name, j.website_url,
                    result.contacts_inserted, result.mayor_rows_inserted, result.youtube_inserted,
                    result.meetings_events_captured, result.meetings_agendas_captured,
                    result.meetings_minutes_captured, result.municipality_websites_inserted,
                    result.youtube_events_count,
                    result.bronze_election_rows, result.c1_election_rows,
                    "yes" if result.error or result.election_error else "no",
                    totals["contacts"], totals["youtube"], totals["events"],
                    totals["c1_elections"], totals["errors"],
                    rate, eta_s,
                )

            if _STOP.is_set():
                logger.warning("Stop requested; not submitting new work. Draining %d in-flight…",
                               sum(1 for f in futures if not f.done()))
                # We can't cancel already-running futures cleanly; let them finish.

    elapsed = time.monotonic() - start
    print()
    print(f"Batch:        {batch_id}")
    print(f"Jurisdictions completed: {completed}/{len(pending)}")
    print(f"Contacts inserted:       {totals['contacts']}")
    print(f"  of which mayor rows:   {totals['mayors']}")
    print(f"YouTube channels kept:   {totals['youtube']}")
    print(f"YouTube filtered out:    {totals['youtube_filtered']}  (confidence < {MIN_CHANNEL_CONFIDENCE:.2f})")
    print(f"Contact images saved:    {totals['images']}  → data/cache/scraped_meetings/<STATE>/<type>/<slug>_<geoid>/_contact_images/")
    if args.elections:
        print(f"Bronze election rows:    {totals['bronze_elections']}  (per-jurisdiction snapshots)")
        print(f"Bronze candidacy rows:   {totals['bronze_candidacies']}")
        print(f"c1_election rows synced: {totals['c1_elections']}")
        print(f"c1_candidacy rows synced:{totals['c1_candidacies']}")
        print(f"Election step errors:    {totals['election_errors']}")
    print(f"Errors:                  {totals['errors']}")
    print(f"Elapsed:                 {elapsed:.0f}s")
    print(f"Checkpoint file:         {_checkpoint_path(batch_id)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
