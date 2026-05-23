#!/usr/bin/env python3
"""
Concurrent, fault-tolerant, resumable contact + YouTube scraper for priority-state
jurisdictions. Writes to Neon dev (``NEON_DATABASE_URL_DEV``):

- ``bronze.bronze_contacts_scraped``        (existing, migration 035)
- ``bronze.bronze_jurisdiction_youtube``    (new, migration 039 — apply first)

Default scope: cities + counties for AL, GA, IN, MA, WA, WI (~2,300 jurisdictions).
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

Fault tolerance:
  - Each jurisdiction runs in its own try/except. A single failure logs and continues.
  - DB writes happen per-jurisdiction, so a crash mid-run loses at most the in-flight
    one.
  - A local checkpoint file at
    ``data/bronze/jurisdiction_pilot_progress/<batch_id>.jsonl`` records every completed
    jurisdiction (including zero-row outcomes), so ``--batch-id <id>`` resumes cleanly.

Concurrency:
  - Thread pool sized by ``--workers``. Each worker handles one jurisdiction end-to-end
    (probe seeds → fetch HTML → extract contacts → YouTube discovery → persist).
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

import psycopg2
import requests
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

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
from scripts.discovery.bronze_contacts_scraped_persist import (  # noqa: E402
    insert_bronze_contacts_scraped,
)
from scripts.discovery.bronze_jurisdiction_youtube_persist import (  # noqa: E402
    insert_bronze_jurisdiction_youtube,
)
from scripts.discovery.contact_directory_heuristics import (  # noqa: E402
    classify_contact_directory_page,
)
from scripts.discovery.contact_extract_from_html import (  # noqa: E402
    extract_structured_contacts_from_html,
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

DEFAULT_PRIORITY_STATES = ("AL", "GA", "IN", "MA", "WA", "WI")
DEFAULT_INCLUDE_TYPES = ("municipality", "county")

# Default insert-time gate on official_meeting_confidence. The upstream YouTube discovery
# (pattern_match handles + YouTube Data API free-text search) is intentionally permissive;
# this threshold separates plausibly-official jurisdiction channels from squatted handles
# and name-token collisions. 0.5 corresponds roughly to "title contains jurisdiction name
# AND at least one government/meeting keyword OR a website back-link." Lower to 0.4 if you
# want broader recall and higher review burden.
MIN_CHANNEL_CONFIDENCE = float(os.getenv("MIN_CHANNEL_CONFIDENCE", "0.5"))

_USER_AGENT = "OpenNavigatorJurisdictionPilot/1.0"
_REQUEST_TIMEOUT_S = 20
_CHECKPOINT_ROOT = _ROOT / "data" / "bronze" / "jurisdiction_pilot_progress"
_PROGRESS_LOCK = Lock()
_STOP = Event()


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
    youtube_filtered_out: int = 0
    seed_urls_attempted: int = 0
    seed_urls_succeeded: int = 0
    error: str | None = None
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
            SELECT DISTINCT ON (jurisdiction_id)
                jurisdiction_id,
                state_code,
                jurisdiction_category AS jurisdiction_type,
                COALESCE(NULLIF(btrim(organization_name), ''),
                         NULLIF(btrim(city), ''),
                         jurisdiction_id) AS name,
                btrim(website_url) AS website_url
            FROM intermediate.int_jurisdiction_websites
            WHERE state_code IN ({state_placeholders})
              AND jurisdiction_category IN ({type_placeholders})
              AND website_url IS NOT NULL
              AND btrim(website_url) <> ''
            ORDER BY jurisdiction_id, website_record_key
        )
        SELECT jurisdiction_id, state_code, jurisdiction_type, name, website_url
        FROM ranked
        ORDER BY state_code, jurisdiction_id
    """
    out: list[Jurisdiction] = []
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (*states, *include_types))
            for jid, sc, jtype, name, url in cur.fetchall():
                out.append(Jurisdiction(
                    jurisdiction_id=jid, state_code=sc,
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
        "seed_urls_attempted": result.seed_urls_attempted,
        "seed_urls_succeeded": result.seed_urls_succeeded,
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

    for u in merged_contact_seed_urls(j.jurisdiction_id, []):
        if u in seen:
            continue
        seen.add(u)
        kind = "mayor" if is_mayor_seed_url(u) else "council"
        seeds.append((u, kind))

    # If hand-curated covers both kinds, skip the heuristic to save HTTP.
    have_mayor = any(k == "mayor" for _, k in seeds)
    have_council = any(k == "council" for _, k in seeds)
    if have_mayor and have_council:
        return seeds

    discovered = discover_seed_urls(j.website_url)
    if not have_mayor:
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
    try:
        resp = session.get(url, timeout=_REQUEST_TIMEOUT_S, allow_redirects=True)
        return resp.status_code, resp.text or ""
    except requests.RequestException:
        return 0, ""


def _scrape_contacts(
    j: Jurisdiction, seeds: list[tuple[str, str]], session: requests.Session, batch_id: str,
) -> tuple[list[dict[str, Any]], int]:
    """Return (contact rows ready for insert, count of seed URLs that responded 200)."""
    rows_out: list[dict[str, Any]] = []
    ok = 0
    scraped_at = datetime.now(timezone.utc).isoformat()
    for url, seed_kind in seeds:
        if _STOP.is_set():
            break
        status, html = _fetch(url, session)
        if status != 200 or not html:
            continue
        ok += 1
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
                "person_name": r.get("person_name"),
                "title_or_role": r.get("title_or_role"),
                "department": r.get("department"),
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
    return rows_out, ok


def _discover_youtube(j: Jurisdiction, session: requests.Session) -> list[dict[str, Any]]:
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
        logger.debug("Found %d verified YouTube URLs from Civic API for %s", len(civic_urls), j.name)

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
            logger.debug("Found %d YouTube URLs on %s website", len(website_channel_urls), j.name)

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
            session=session,
        )
        rows.append({
            "youtube_channel_url": url,
            "youtube_channel_id": enriched.get("channel_id"),
            "channel_title": enriched.get("channel_title"),
            "subscriber_count": enriched.get("subscriber_count"),
            "video_count": enriched.get("video_count"),
            "view_count": enriched.get("view_count"),
            "latest_upload": str(enriched.get("latest_upload") or ""),
            "discovery_method": enriched.get("discovery_method") or ch.get("discovery_method"),
            "confidence": enriched.get("confidence"),
            "channel_description": enriched.get("channel_description"),
            "back_links_to_jurisdiction_website": enriched.get("back_links_to_jurisdiction_website"),
            "official_meeting_confidence": enriched.get("official_meeting_confidence"),
            "external_links": enriched.get("external_links") or [],
            "raw_row": enriched,
            "scraped_at": scraped_at,
        })
    return rows


def _process_one(
    j: Jurisdiction, batch_id: str, database_url: str, *, skip_youtube: bool,
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
    vendor_type, vendor_info = detect_vendor(j.website_url, session=session)
    logger.debug("Detected vendor: %s for %s", vendor_type, j.name)

    try:
        seeds = _resolve_seed_urls(j)
        result.seeds_used = [u for u, _ in seeds]
        result.seed_urls_attempted = len(seeds)

        # Priority 1: Try Legistar for council members (high-confidence official contacts)
        legistar_contacts = []
        if vendor_type == "legistar" and vendor_info.get("api_endpoint"):
            legistar_contacts = get_legistar_council_members(vendor_info.get("api_endpoint", ""))
            if legistar_contacts:
                logger.debug("Found %d council members via Legistar", len(legistar_contacts))

        # Priority 2: Scrape website contacts
        contact_rows, ok = _scrape_contacts(j, seeds, session, batch_id)
        result.seed_urls_succeeded = ok

        # Merge Legistar + scraped contacts (Legistar has priority)
        all_contacts = legistar_contacts + contact_rows

        result.mayor_rows_inserted = sum(
            1 for r in all_contacts if r.get("raw_row", {}).get("is_mayor")
        )

        if all_contacts:
            result.contacts_inserted = insert_bronze_contacts_scraped(
                database_url,
                scrape_batch_id=batch_id,
                jurisdiction_id=j.jurisdiction_id,
                state_code=j.state_code,
                ocd_id=ocd_id,
                rows=all_contacts,
            )

        if not skip_youtube and not _STOP.is_set():
            yt_rows = _discover_youtube(j, session)
            # Hard filter: only persist channels above the officialness threshold. Upstream
            # discovery is intentionally permissive (pattern_match + free-text API search);
            # without this gate the table fills with squatted handles and random name-token
            # collisions ("Adams" -> civil rights lawyer, etc.).
            keep_rows = [
                r for r in yt_rows
                if (r.get("official_meeting_confidence") or 0.0) >= MIN_CHANNEL_CONFIDENCE
            ]
            result.youtube_filtered_out = len(yt_rows) - len(keep_rows)
            if keep_rows:
                result.youtube_inserted = insert_bronze_jurisdiction_youtube(
                    database_url,
                    scrape_batch_id=batch_id,
                    jurisdiction_id=j.jurisdiction_id,
                    state_code=j.state_code,
                    ocd_id=ocd_id,
                    website_url=j.website_url,
                    rows=keep_rows,
                )
    except Exception as exc:  # fault tolerance: never let one jurisdiction kill the run
        result.error = f"{type(exc).__name__}: {exc}"
        logger.exception("jurisdiction %s failed", j.jurisdiction_id)

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
        "--min-channel-confidence", type=float, default=None,
        help=(
            "Drop YouTube rows with official_meeting_confidence below this threshold "
            f"(default: {MIN_CHANNEL_CONFIDENCE:.2f} or MIN_CHANNEL_CONFIDENCE env var). "
            "Set 0 to persist everything (audit mode); set 0.7+ for high precision."
        ),
    )
    p.add_argument("--dry-run", action="store_true",
                   help="Resolve jurisdictions and print the plan; don't fetch or write.")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # Silence the underlying http client unless verbose; otherwise the log is unreadable.
    if not args.verbose:
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

    states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip())
    include_types = tuple(t.strip().lower() for t in args.include_types.split(",") if t.strip())
    if not states or not include_types:
        logger.error("--states and --include-types must be non-empty")
        return 2

    if args.min_channel_confidence is not None:
        MIN_CHANNEL_CONFIDENCE = args.min_channel_confidence
    logger.info("YouTube hard filter: official_meeting_confidence >= %.2f", MIN_CHANNEL_CONFIDENCE)

    database_url = _resolve_database_url()
    batch_id = args.batch_id or str(uuid.uuid4())
    done_ids = load_completed_ids(batch_id) if args.batch_id else set()

    logger.info("Loading jurisdictions for %s (%s) limit_per_state=%s",
                states, include_types, args.limit_per_state)
    targets = load_jurisdictions(
        database_url, states=states, include_types=include_types,
        limit_per_state=args.limit_per_state,
    )
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

    _install_sigint_handler()
    start = time.monotonic()
    completed = 0
    totals = {"contacts": 0, "mayors": 0, "youtube": 0, "youtube_filtered": 0, "errors": 0}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(_process_one, j, batch_id, database_url, skip_youtube=args.skip_youtube): j
            for j in pending
        }
        for fut in as_completed(futures):
            j = futures[fut]
            try:
                result = fut.result()
            except Exception as exc:  # extra safety net
                logger.exception("worker raised for %s", j.jurisdiction_id)
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
            if result.error:
                totals["errors"] += 1

            if completed % 10 == 0 or completed == len(pending):
                elapsed = time.monotonic() - start
                rate = completed / elapsed if elapsed > 0 else 0
                eta_s = (len(pending) - completed) / rate if rate > 0 else 0
                logger.info(
                    "[%d/%d] %s %s contacts=%d mayors=%d youtube=%d err=%s | "
                    "totals contacts=%d mayors=%d youtube=%d errors=%d | rate=%.2f/s ETA=%.0fs",
                    completed, len(pending), j.state_code, j.jurisdiction_id,
                    result.contacts_inserted, result.mayor_rows_inserted, result.youtube_inserted,
                    "yes" if result.error else "no",
                    totals["contacts"], totals["mayors"], totals["youtube"], totals["errors"],
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
    print(f"Errors:                  {totals['errors']}")
    print(f"Elapsed:                 {elapsed:.0f}s")
    print(f"Checkpoint file:         {_checkpoint_path(batch_id)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
