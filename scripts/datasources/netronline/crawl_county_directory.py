#!/usr/bin/env python3
"""
Crawl publicrecords.netronline.com and persist per-county public-records office
directories into ``bronze.bronze_jurisdictions_county_directory`` (Neon dev,
``NEON_DATABASE_URL_DEV``).

For each state code (defaults to all 50 + DC):

  1. GET ``/state/<XX>``                 → discover county slugs.
  2. For each county GET ``/state/<XX>/county/<slug>`` → extract office rows
     (Name / Phone / Online-URL / access-type label) from the ``.div-table-row``
     containers.
  3. Best-effort map ``county_name`` to ``int_jurisdictions.jurisdiction_id`` +
     FIPS code by exact normalized-name match within the state.
  4. Insert rows in batches.

Polite by default: 1 worker, ``--sleep 1`` second between requests, custom UA.
robots.txt at the time of writing permits unrestricted crawling
(``User-agent: * / Disallow:``). Re-check before each large run.

Run::

    .venv/bin/python -m scripts.datasources.netronline.crawl_county_directory \\
        --states AL --dry-run                # confirm county-slug discovery
    .venv/bin/python -m scripts.datasources.netronline.crawl_county_directory \\
        --states AL                          # 1 state, polite default
    .venv/bin/python -m scripts.datasources.netronline.crawl_county_directory \\
        --workers 3                          # all 50+DC, 3 workers

Resume::

    .venv/bin/python -m scripts.datasources.netronline.crawl_county_directory \\
        --batch-id <uuid-from-previous-run>

Checkpoints (per-state JSONL) live at ``data/bronze/netronline_progress/<batch>.jsonl``.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
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
from bs4 import BeautifulSoup
from dotenv import load_dotenv

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.discovery.bronze_jurisdictions_county_directory_persist import (  # noqa: E402
    insert_bronze_county_directory_rows,
)

logger = logging.getLogger("netronline_crawl")

BASE_URL = "https://publicrecords.netronline.com"
DEFAULT_UA = (
    "OpenNavigatorJurisdictionPilot/1.0 "
    "(+https://github.com/getcommunityone/open-navigator-for-engagement)"
)
DEFAULT_STATES = (
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY",
)
_CHECKPOINT_ROOT = _ROOT / "data" / "bronze" / "netronline_progress"
_PROGRESS_LOCK = Lock()
_STOP = Event()


# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CountySlug:
    state_code: str
    slug: str
    display_name: str   # as shown on the state index page


@dataclass
class StateResult:
    state_code: str
    counties_seen: int = 0
    counties_persisted: int = 0
    offices_persisted: int = 0
    error: str | None = None
    duration_s: float = 0.0


# --------------------------------------------------------------------------------------
# DB
# --------------------------------------------------------------------------------------


def _resolve_database_url() -> str:
    load_dotenv(_ROOT / ".env")
    url = os.getenv("NEON_DATABASE_URL_DEV", "").strip()
    if not url:
        raise SystemExit("NEON_DATABASE_URL_DEV is not set in .env — refusing to default to prod.")
    return url


def _normalize_county_name(name: str) -> str:
    """``Barbour (Clayton)`` -> ``barbour``; ``Saint Clair`` -> ``st clair``; lowercases."""
    s = (name or "").strip().lower()
    s = re.sub(r"\(.*?\)", "", s)  # drop courthouse suffix in parens
    s = re.sub(r"[^a-z]+", " ", s)
    s = re.sub(r"\bsaint\b", "st", s)
    s = re.sub(r"\bcounty\b|\bparish\b|\bborough\b|\bcensus area\b", "", s)
    return s.strip()


def load_state_county_index(database_url: str, state_code: str) -> dict[str, tuple[str, str]]:
    """
    Return ``{normalized_county_name -> (jurisdiction_id, fips_5)}`` for one state, sourced
    from ``intermediate.int_jurisdiction_websites`` (only includes counties with websites,
    which is the same authority the rest of the pipeline uses).
    """
    out: dict[str, tuple[str, str]] = {}
    sql = """
        SELECT DISTINCT jurisdiction_id, organization_name, city
        FROM intermediate.int_jurisdiction_websites
        WHERE state_code = %s AND jurisdiction_category = 'county'
    """
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (state_code,))
            for jid, org_name, city in cur.fetchall():
                # jurisdiction_id format: "county_<5-digit FIPS>"
                fips = ""
                if jid and jid.startswith("county_"):
                    suffix = jid.split("_", 1)[1]
                    if suffix.isdigit() and len(suffix) == 5:
                        fips = suffix
                for candidate in (org_name, city):
                    norm = _normalize_county_name(candidate or "")
                    if norm:
                        out.setdefault(norm, (jid, fips))
    finally:
        conn.close()
    return out


# --------------------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------------------


def _new_session(user_agent: str) -> requests.Session:
    sess = requests.Session()
    sess.headers["User-Agent"] = user_agent
    sess.headers["Accept-Language"] = "en-US,en;q=0.9"
    return sess


def _fetch(session: requests.Session, url: str, *, timeout: int = 25) -> str:
    resp = session.get(url, timeout=timeout, allow_redirects=True)
    if resp.status_code == 200:
        return resp.text or ""
    raise RuntimeError(f"HTTP {resp.status_code} for {url}")


# --------------------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------------------


_COUNTY_HREF_RE = re.compile(r"/state/([A-Z]{2})/county/([^/?#]+)")


def parse_state_index(html: str, state_code: str) -> list[CountySlug]:
    """From a /state/<XX> page, return [(slug, display_name), ...] for that state."""
    soup = BeautifulSoup(html, "html.parser")
    out: list[CountySlug] = []
    seen: set[str] = set()
    for a in soup.find_all("a", href=_COUNTY_HREF_RE):
        href = a.get("href", "")
        m = _COUNTY_HREF_RE.search(href)
        if not m:
            continue
        st, slug = m.group(1), m.group(2)
        if st != state_code or slug in seen:
            continue
        seen.add(slug)
        name = a.get_text(" ", strip=True) or slug.replace("_", " ").title()
        out.append(CountySlug(state_code=state_code, slug=slug, display_name=name))
    return out


def parse_county_offices(html: str) -> list[dict[str, Any]]:
    """
    Parse a /state/<XX>/county/<slug> page; return office dicts.

    Page layout: each office is a ``<div class="div-table-row">`` with child
    ``<div class="div-table-col" col-name="...">`` cells. Known col-names:
    ``Name``, ``Phone``, ``Online`` (text label + outbound href), ``Report``.
    """
    soup = BeautifulSoup(html, "html.parser")
    out: list[dict[str, Any]] = []
    for row in soup.find_all("div", class_=lambda c: c and "div-table-row" in c):
        cells: dict[str, Any] = {}
        href: str | None = None
        for col in row.find_all("div", class_=lambda c: c and "div-table-col" in c):
            key = (col.get("col-name") or "").strip()
            if not key:
                continue
            text = col.get_text(" ", strip=True)
            a = col.find("a", href=True)
            cells[key] = text
            if a and key.lower() == "online":
                href = a["href"].strip()

        name = (cells.get("Name") or "").strip()
        if not name:
            continue
        if name.lower() in {"name", "report"}:  # header rows
            continue
        out.append({
            "office_name": name,
            "office_phone": cells.get("Phone") or None,
            "office_url": href,
            "access_type": cells.get("Online") or None,
            # data_type isn't a column on the page; downstream can derive from office_name.
            "data_type": None,
            "raw_row": cells,
        })
    return out


# --------------------------------------------------------------------------------------
# Checkpoint
# --------------------------------------------------------------------------------------


def _checkpoint_path(batch_id: str) -> Path:
    return _CHECKPOINT_ROOT / f"{batch_id}.jsonl"


def load_completed_states(batch_id: str) -> set[str]:
    p = _checkpoint_path(batch_id)
    if not p.exists():
        return set()
    done: set[str] = set()
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("state_code"):
                done.add(rec["state_code"])
    return done


def record_state_checkpoint(batch_id: str, result: StateResult) -> None:
    p = _checkpoint_path(batch_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps({
        "state_code": result.state_code,
        "counties_seen": result.counties_seen,
        "counties_persisted": result.counties_persisted,
        "offices_persisted": result.offices_persisted,
        "error": result.error,
        "duration_s": round(result.duration_s, 2),
        "completed_at": datetime.now(timezone.utc).isoformat(),
    })
    with _PROGRESS_LOCK:
        with p.open("a") as f:
            f.write(line + "\n")


# --------------------------------------------------------------------------------------
# Per-state work
# --------------------------------------------------------------------------------------


def _process_state(
    state_code: str,
    *,
    batch_id: str,
    database_url: str,
    user_agent: str,
    sleep_s: float,
    dry_run: bool,
) -> StateResult:
    result = StateResult(state_code=state_code)
    start = time.monotonic()
    try:
        session = _new_session(user_agent)
        index_url = f"{BASE_URL}/state/{state_code}"
        index_html = _fetch(session, index_url)
        counties = parse_state_index(index_html, state_code)
        result.counties_seen = len(counties)
        logger.info("[%s] %d county slugs found", state_code, len(counties))

        if dry_run:
            for c in counties[:8]:
                print(f"  {state_code} /county/{c.slug} \"{c.display_name}\"")
            if len(counties) > 8:
                print(f"  ... and {len(counties) - 8} more")
            result.duration_s = time.monotonic() - start
            return result

        name_to_jid = load_state_county_index(database_url, state_code)
        logger.info("[%s] FIPS map has %d county-name entries", state_code, len(name_to_jid))

        for i, c in enumerate(counties, 1):
            if _STOP.is_set():
                logger.info("[%s] stop requested mid-state at %d/%d", state_code, i, len(counties))
                break
            time.sleep(sleep_s)
            county_url = f"{BASE_URL}/state/{c.state_code}/county/{c.slug}"
            try:
                county_html = _fetch(session, county_url)
            except Exception as exc:
                logger.warning("[%s] %s fetch failed: %s", state_code, c.slug, exc)
                continue
            offices = parse_county_offices(county_html)
            if not offices:
                logger.info("[%s] %s — no office rows parsed", state_code, c.slug)
                continue

            jid_match = name_to_jid.get(_normalize_county_name(c.display_name))
            jurisdiction_id = jid_match[0] if jid_match else None
            fips = jid_match[1] if jid_match else None

            inserted = insert_bronze_county_directory_rows(
                database_url,
                scrape_batch_id=batch_id,
                state_code=state_code,
                county_slug=c.slug,
                county_name=c.display_name,
                source_page_url=county_url,
                jurisdiction_id=jurisdiction_id,
                fips_code=fips,
                offices=offices,
            )
            result.counties_persisted += 1 if inserted else 0
            result.offices_persisted += inserted
            if i % 25 == 0 or i == len(counties):
                logger.info("[%s] %d/%d counties processed (%d offices so far)",
                            state_code, i, len(counties), result.offices_persisted)
    except Exception as exc:
        result.error = f"{type(exc).__name__}: {exc}"
        logger.exception("[%s] state failed", state_code)

    result.duration_s = time.monotonic() - start
    return result


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------


def _install_sigint_handler() -> None:
    def _h(_s, _f):  # type: ignore[no-untyped-def]
        if _STOP.is_set():
            logger.warning("Second Ctrl-C — exiting hard.")
            os._exit(130)
        logger.warning("Ctrl-C: finishing in-flight state then stopping (Ctrl-C again to abort).")
        _STOP.set()
    signal.signal(signal.SIGINT, _h)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--states", default=",".join(DEFAULT_STATES),
                   help="Comma-separated state codes (default: all 50 + DC).")
    p.add_argument("--workers", type=int, default=1,
                   help="Parallel states (default: 1 — be polite). Per-state requests stay serial.")
    p.add_argument("--sleep", type=float, default=1.0,
                   help="Seconds between county fetches within a state (default: 1.0).")
    p.add_argument("--batch-id", default=None,
                   help="Resume an existing batch — already-completed states are skipped.")
    p.add_argument("--user-agent", default=DEFAULT_UA,
                   help="HTTP User-Agent header for outbound requests.")
    p.add_argument("--dry-run", action="store_true",
                   help="List counties per state; do not fetch county pages or write to DB.")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    states = tuple(s.strip().upper() for s in args.states.split(",") if s.strip())
    if not states:
        logger.error("--states must be non-empty")
        return 2

    database_url = _resolve_database_url() if not args.dry_run else ""
    batch_id = args.batch_id or str(uuid.uuid4())
    done = load_completed_states(batch_id) if args.batch_id else set()
    pending = [s for s in states if s not in done]
    logger.info("Batch %s — %d state(s) pending (%d already complete)",
                batch_id, len(pending), len(done))

    if not pending:
        print("Nothing to do (all states complete in this batch).")
        return 0

    _install_sigint_handler()
    totals = {"counties": 0, "offices": 0, "errors": 0}
    start = time.monotonic()

    if args.workers <= 1:
        for st in pending:
            if _STOP.is_set():
                break
            r = _process_state(
                st, batch_id=batch_id, database_url=database_url,
                user_agent=args.user_agent, sleep_s=args.sleep, dry_run=args.dry_run,
            )
            record_state_checkpoint(batch_id, r)
            totals["counties"] += r.counties_persisted
            totals["offices"] += r.offices_persisted
            if r.error:
                totals["errors"] += 1
            logger.info("[%s] done in %.0fs: counties=%d offices=%d err=%s",
                        st, r.duration_s, r.counties_persisted, r.offices_persisted,
                        "yes" if r.error else "no")
    else:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            fut2st = {
                pool.submit(
                    _process_state, st,
                    batch_id=batch_id, database_url=database_url,
                    user_agent=args.user_agent, sleep_s=args.sleep, dry_run=args.dry_run,
                ): st
                for st in pending
            }
            for fut in as_completed(fut2st):
                st = fut2st[fut]
                try:
                    r = fut.result()
                except Exception as exc:
                    logger.exception("worker raised for %s", st)
                    r = StateResult(state_code=st, error=f"{type(exc).__name__}: {exc}")
                record_state_checkpoint(batch_id, r)
                totals["counties"] += r.counties_persisted
                totals["offices"] += r.offices_persisted
                if r.error:
                    totals["errors"] += 1
                logger.info("[%s] done in %.0fs: counties=%d offices=%d err=%s",
                            st, r.duration_s, r.counties_persisted, r.offices_persisted,
                            "yes" if r.error else "no")

    elapsed = time.monotonic() - start
    print()
    print(f"Batch:                  {batch_id}")
    print(f"States processed:       {len(pending)}")
    print(f"Counties with rows:     {totals['counties']}")
    print(f"Offices inserted:       {totals['offices']}")
    print(f"States with error:      {totals['errors']}")
    print(f"Elapsed:                {elapsed:.0f}s")
    print(f"Checkpoint file:        {_checkpoint_path(batch_id)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
