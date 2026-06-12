#!/usr/bin/env python3
"""
Live MA pilot scraper: contacts + YouTube for the 10 jurisdictions in
``ma_pilot.jurisdictions``.

Run::

    python -m scripts.datasources.ma_pilot.scrape_ma_jurisdictions
    python -m scripts.datasources.ma_pilot.scrape_ma_jurisdictions --only Boston Cambridge
    python -m scripts.datasources.ma_pilot.scrape_ma_jurisdictions --skip-youtube

Writes two parquet files under ``data/bronze/``:

- ``data/bronze/contacts_scraped/ma_pilot_contacts.parquet``
- ``data/bronze/youtube_channels/ma_pilot_youtube_channels.parquet``

Each run overwrites the files in full (deterministic snapshot). Mayor-titled rows are
flagged with ``is_mayor=True`` and persisted even when a page scores below the normal
directory threshold (see ``mayor_boost.py``).

The script is intentionally synchronous for the contact half (one homepage at a time)
and async only inside the YouTube discovery call.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import polars as pl
import requests

# Ensure the project root is importable when invoked as a script.
_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from scripts.datasources.ma_pilot.jurisdictions import (  # noqa: E402
    MA_PILOT_JURISDICTIONS,
    MAJurisdiction,
)
from scripts.datasources.ma_pilot.mayor_boost import is_mayor_seed_url, tag_mayor_rows  # noqa: E402
from scrapers.youtube.youtube_channel_discovery import (  # noqa: E402
    YouTubeChannelDiscovery,
)
from scripts.discovery.contact_directory_heuristics import (  # noqa: E402
    classify_contact_directory_page,
)
from scrapers.discovery.contact_extract_from_html import (  # noqa: E402
    extract_structured_contacts_from_html,
)

logger = logging.getLogger("ma_pilot")

_USER_AGENT = "OpenNavigatorMAPilot/1.0 (+https://github.com/anthropics/claude-code)"
_REQUEST_TIMEOUT_S = 25
_BRONZE_ROOT = _ROOT / "data" / "bronze"
_CONTACTS_OUT = _BRONZE_ROOT / "contacts_scraped" / "ma_pilot_contacts.parquet"
_YOUTUBE_OUT = _BRONZE_ROOT / "youtube_channels" / "ma_pilot_youtube_channels.parquet"


def _fetch(url: str) -> tuple[int, str]:
    """Return ``(status_code, body)``. Network errors map to ``(0, "")``."""
    try:
        resp = requests.get(
            url,
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
            timeout=_REQUEST_TIMEOUT_S,
            allow_redirects=True,
        )
        return resp.status_code, resp.text or ""
    except requests.RequestException as exc:
        logger.warning("fetch error for %s: %s", url, exc)
        return 0, ""


def _scrape_contacts_for(j: MAJurisdiction, batch_id: str) -> list[dict[str, Any]]:
    """
    Visit every seed URL for one jurisdiction, run the structured extractor, and
    return rows ready for the parquet writer. Mayor rows are retained regardless
    of directory score (``is_mayor=True``).
    """
    seed_urls: list[tuple[str, str]] = []
    for url in j["mayor_seed_urls"]:
        seed_urls.append((url, "mayor"))
    for url in j["council_seed_urls"]:
        seed_urls.append((url, "council"))

    all_rows: list[dict[str, Any]] = []
    scraped_at = datetime.now(timezone.utc).isoformat()

    for url, seed_kind in seed_urls:
        status, html = _fetch(url)
        if status != 200 or not html:
            logger.info("[%s] %s -> HTTP %s, skipped", j["name"], url, status)
            continue

        classification = classify_contact_directory_page(url, html)
        rows = extract_structured_contacts_from_html(html, url)
        tagged_rows = tag_mayor_rows(rows, source_page_url=url)

        is_mayor_page = is_mayor_seed_url(url) or seed_kind == "mayor"
        kept = 0
        for r in tagged_rows:
            # Retain row when EITHER the page classified as a directory, OR the row
            # itself is a mayor row from a mayor-style page. This is the boost: a
            # single-bio mayor page that scores below 18 still gets persisted.
            if not classification["is_directory"] and not (is_mayor_page and r.get("is_mayor")):
                continue
            kept += 1
            all_rows.append({
                "scrape_batch_id": batch_id,
                "jurisdiction_id": j["jurisdiction_id"],
                "state_code": j["state_code"],
                "jurisdiction_name": j["name"],
                "jurisdiction_type": j["type"],
                "source_page_url": url,
                "seed_kind": seed_kind,
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
                "is_mayor": bool(r.get("is_mayor")),
                "scraped_at": scraped_at,
            })
        logger.info(
            "[%s] %s -> status=%s rows=%d kept=%d score=%d kind=%s",
            j["name"], url, status, len(rows), kept,
            classification["score"], classification["directory_kind"],
        )

    return all_rows


async def _discover_youtube_for(j: MAJurisdiction, batch_id: str) -> list[dict[str, Any]]:
    """One YouTube discovery pass per jurisdiction; returns rows for parquet."""
    city_name = j["name"] if j["type"] == "city" else None
    county_name = j["name"] if j["type"] == "county" else None

    scraped_at = datetime.now(timezone.utc).isoformat()
    rows: list[dict[str, Any]] = []
    try:
        async with YouTubeChannelDiscovery() as yt:
            channels = await yt.discover_channels(
                city_name=city_name,
                state_code=j["state_code"],
                county_name=county_name,
                homepage_url=j["homepage"],
            )
    except Exception as exc:
        logger.warning("[%s] YouTube discovery error: %s", j["name"], exc)
        return rows

    for ch in channels:
        rows.append({
            "scrape_batch_id": batch_id,
            "jurisdiction_id": j["jurisdiction_id"],
            "state_code": j["state_code"],
            "jurisdiction_name": j["name"],
            "channel_url": ch.get("channel_url"),
            "channel_id": ch.get("channel_id"),
            "channel_title": ch.get("channel_title"),
            "video_count": ch.get("video_count"),
            "subscriber_count": ch.get("subscriber_count"),
            "view_count": ch.get("view_count"),
            "latest_upload": str(ch.get("latest_upload") or ""),
            "discovery_method": ch.get("discovery_method"),
            "confidence": float(ch.get("confidence") or 0.0),
            "scraped_at": scraped_at,
        })
    logger.info("[%s] YouTube channels discovered: %d", j["name"], len(rows))
    return rows


def _write_parquet(rows: list[dict[str, Any]], out_path: Path, *, kind: str) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        logger.warning("no %s rows to write to %s", kind, out_path)
        # Still write an empty file so DuckDB queries don't error on a missing path.
        pl.DataFrame().write_parquet(out_path)
        return
    df = pl.DataFrame(rows)
    df.write_parquet(out_path)
    logger.info("wrote %d %s rows -> %s", len(rows), kind, out_path)


def _print_summary(contacts: list[dict[str, Any]], youtube: list[dict[str, Any]]) -> None:
    by_j: dict[str, dict[str, int]] = {}
    for r in contacts:
        d = by_j.setdefault(r["jurisdiction_name"], {"contacts": 0, "mayors": 0, "youtube": 0})
        d["contacts"] += 1
        if r.get("is_mayor"):
            d["mayors"] += 1
    for r in youtube:
        d = by_j.setdefault(r["jurisdiction_name"], {"contacts": 0, "mayors": 0, "youtube": 0})
        d["youtube"] += 1
    print()
    print(f"{'Jurisdiction':<22} {'contacts':>9} {'mayor_rows':>11} {'yt_channels':>12}")
    print("-" * 60)
    for name in sorted(by_j):
        d = by_j[name]
        print(f"{name:<22} {d['contacts']:>9} {d['mayors']:>11} {d['youtube']:>12}")
    print("-" * 60)
    print(f"{'TOTAL':<22} {sum(d['contacts'] for d in by_j.values()):>9} "
          f"{sum(d['mayors'] for d in by_j.values()):>11} "
          f"{sum(d['youtube'] for d in by_j.values()):>12}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--only",
        nargs="*",
        help="Restrict to a subset of jurisdiction names (e.g. --only Boston Cambridge).",
    )
    p.add_argument("--skip-contacts", action="store_true")
    p.add_argument("--skip-youtube", action="store_true")
    p.add_argument("--verbose", "-v", action="store_true")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    targets: list[MAJurisdiction]
    if args.only:
        wanted = {n.lower() for n in args.only}
        targets = [j for j in MA_PILOT_JURISDICTIONS if j["name"].lower() in wanted]
        missing = wanted - {j["name"].lower() for j in targets}
        if missing:
            logger.error("Unknown jurisdiction names: %s", sorted(missing))
            return 2
    else:
        targets = list(MA_PILOT_JURISDICTIONS)

    batch_id = str(uuid.uuid4())
    logger.info("MA pilot scrape batch=%s jurisdictions=%d", batch_id, len(targets))

    contact_rows: list[dict[str, Any]] = []
    if not args.skip_contacts:
        for j in targets:
            start = time.monotonic()
            contact_rows.extend(_scrape_contacts_for(j, batch_id))
            logger.info("[%s] contacts done in %.1fs", j["name"], time.monotonic() - start)
        _write_parquet(contact_rows, _CONTACTS_OUT, kind="contact")

    youtube_rows: list[dict[str, Any]] = []
    if not args.skip_youtube:
        async def _run_yt() -> None:
            for j in targets:
                start = time.monotonic()
                youtube_rows.extend(await _discover_youtube_for(j, batch_id))
                logger.info("[%s] youtube done in %.1fs", j["name"], time.monotonic() - start)
        asyncio.run(_run_yt())
        _write_parquet(youtube_rows, _YOUTUBE_OUT, kind="youtube channel")

    _print_summary(contact_rows, youtube_rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
