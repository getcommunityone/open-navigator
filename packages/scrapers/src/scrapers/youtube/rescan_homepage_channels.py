"""Find the YouTube channels that city websites actually link to.

The first homepage scrape stored no links for any city: every
``payload.social_media`` list is empty, and ``youtube_channel_url`` on
``bronze.bronze_jurisdictions_municipalities_scraped`` mostly holds handle guesses
(``youtube_channel_selection_method = 'pattern_match'``, for example ``@SeligmanAL``)
that the channel verification gate rejects.

This revisits each city's ``homepage_url`` with ``YouTubeChannelDiscovery``: links
and embeds on the homepage, then same-site meeting and video pages, then site
search. Each channel found is added to ``payload.youtube_channels`` with
``discovery_method = 'website_scrape'``. When the row's primary channel is empty or
a pattern guess, the first link found becomes the primary
(``youtube_channel_selection_method = 'website_scrape'``). A channel chosen any
other way is never replaced. No YouTube request is made, so the YouTube Data API
quota and YouTube's bot checks don't apply.

Dry run by default::

    python -m scrapers.youtube.rescan_homepage_channels --states AL --limit 50
    python -m scrapers.youtube.rescan_homepage_channels --states AL --limit 50 --apply
    python -m scrapers.youtube.rescan_homepage_channels --apply --concurrency 8
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Sequence

from loguru import logger

TABLE = "bronze.bronze_jurisdictions_municipalities_scraped"
METHOD = "website_scrape"  # the name youtube_primary_channel ranks highest
CONFIDENCE = 0.9
# A primary chosen by one of these may be replaced by a homepage link: guesses and
# search hits (4 of 4 Alabama search picks were wrong on November 16, 2026).
REPLACEABLE_METHODS = frozenset({"", "pattern_match", "domain_search", "youtube_api"})


@dataclass
class RescanResult:
    geoid: str
    homepage_url: str
    channels: list[str] = field(default_factory=list)
    error: str | None = None


def merge_channels(
    payload: dict[str, Any] | None, channels: Sequence[str], *, now: str
) -> tuple[dict[str, Any], int]:
    """Add each channel URL to ``payload['youtube_channels']`` as a homepage link.

    A URL already listed is relabelled as a homepage link, since the site itself
    links to it. Returns the new payload and how many URLs were new."""
    out = dict(payload or {})
    entries = [
        dict(e) for e in (out.get("youtube_channels") or []) if isinstance(e, dict)
    ]
    by_url = {_key(e.get("channel_url")): e for e in entries if e.get("channel_url")}
    added = 0
    for url in channels:
        key = _key(url)
        if not key:
            continue
        if key in by_url:
            by_url[key]["discovery_method"] = METHOD
            by_url[key]["confidence"] = max(
                float(by_url[key].get("confidence") or 0), CONFIDENCE
            )
            continue
        entry = {
            "channel_url": url,
            "channel_id": _channel_id(url),
            "discovery_method": METHOD,
            "confidence": CONFIDENCE,
            "discovered_at": now,
        }
        entries.append(entry)
        by_url[key] = entry
        added += 1
    out["youtube_channels"] = entries
    social = dict(out.get("social_media") or {})
    social["youtube"] = sorted({*(social.get("youtube") or []), *channels})
    out["social_media"] = social
    return out, added


def choose_primary(
    current_url: str | None, current_method: str | None, channels: Sequence[str]
) -> str | None:
    """The new primary channel URL, or ``None`` to keep the current one."""
    if not channels:
        return None
    if (current_method or "").strip().lower() not in REPLACEABLE_METHODS and (
        current_url or ""
    ).strip():
        return None
    return channels[0]


def _key(url: Any) -> str:
    return str(url or "").strip().rstrip("/").lower()


def _channel_id(url: str) -> str | None:
    marker = "/channel/"
    if marker in url:
        cid = url.split(marker, 1)[1].split("/", 1)[0].split("?", 1)[0]
        return cid if cid.startswith("UC") else None
    return None


def select_sql(
    states: Sequence[str], *, include_rescanned: bool
) -> tuple[str, list[Any]]:
    where = ["homepage_url IS NOT NULL", "BTRIM(homepage_url) <> ''"]
    params: list[Any] = []
    if states:
        where.append("usps = ANY(%s)")
        params.append([s.upper() for s in states])
    if not include_rescanned:
        where.append("NOT (payload ? 'homepage_rescan_at')")
    sql = (
        f"SELECT geoid, usps, COALESCE(homepage_final_url, homepage_url) AS homepage_url, payload, "
        f"youtube_channel_url, youtube_channel_selection_method FROM {TABLE} "
        f"WHERE {' AND '.join(where)} ORDER BY usps, geoid LIMIT %s"
    )
    return sql, params


async def scan_all(
    rows: list[dict[str, Any]], *, concurrency: int, timeout: float
) -> list[RescanResult]:
    from scrapers.youtube.youtube_channel_discovery import YouTubeChannelDiscovery

    sem = asyncio.Semaphore(max(1, concurrency))
    results: list[RescanResult] = []
    async with YouTubeChannelDiscovery(youtube_api_key=None) as discovery:

        async def one(i: int, row: dict[str, Any]) -> None:
            res = RescanResult(geoid=row["geoid"], homepage_url=row["homepage_url"])
            async with sem:
                try:
                    found = await asyncio.wait_for(
                        discovery._scrape_website_for_channels(res.homepage_url),
                        timeout,
                    )
                    res.channels = list(dict.fromkeys(c for c in found if c))
                except Exception as exc:  # noqa: BLE001 - one broken site must not stop the scan
                    res.error = f"{type(exc).__name__}: {exc}"[:200]
            results.append(res)
            if res.channels:
                logger.info(
                    "[{}/{}] {} {} -> {}",
                    i,
                    len(rows),
                    row["usps"],
                    res.homepage_url,
                    res.channels,
                )

        await asyncio.gather(*(one(i, r) for i, r in enumerate(rows, 1)))
    return results


def write_results(
    conn: Any, rows: dict[str, dict[str, Any]], results: list[RescanResult]
) -> dict[str, int]:
    now = datetime.now(UTC).replace(microsecond=0).isoformat()
    counts = {"rows_with_links": 0, "new_links": 0, "primary_set": 0}
    with conn.cursor() as cur:
        for res in results:
            row = rows[res.geoid]
            payload, added = merge_channels(row["payload"], res.channels, now=now)
            payload["homepage_rescan_at"] = now
            if res.error:
                payload["homepage_rescan_error"] = res.error
            else:
                payload.pop("homepage_rescan_error", None)
            primary = choose_primary(
                row["youtube_channel_url"],
                row["youtube_channel_selection_method"],
                res.channels,
            )
            if res.channels:
                counts["rows_with_links"] += 1
                counts["new_links"] += added
            if primary:
                counts["primary_set"] += 1
                cur.execute(
                    f"UPDATE {TABLE} SET payload = %s, youtube_channel_url = %s, youtube_channel_id = %s, "
                    "youtube_channel_selection_method = %s, youtube_channel_selection_confidence = %s "
                    "WHERE geoid = %s",
                    [
                        json.dumps(payload),
                        primary,
                        _channel_id(primary),
                        METHOD,
                        CONFIDENCE,
                        res.geoid,
                    ],
                )
            else:
                cur.execute(
                    f"UPDATE {TABLE} SET payload = %s WHERE geoid = %s",
                    [json.dumps(payload), res.geoid],
                )
    conn.commit()
    return counts


def _database_url(explicit: str) -> str:
    import os

    from dotenv import load_dotenv

    load_dotenv()
    url = (
        explicit
        or os.getenv("OPEN_NAVIGATOR_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    ).strip()
    if url:
        return url
    return f"postgresql://postgres:{os.getenv('POSTGRES_PASSWORD') or 'password'}@localhost:5433/open_navigator"


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Find the YouTube channels that city websites link to."
    )
    p.add_argument(
        "--states", default="", help="Comma-separated USPS codes (default: all)"
    )
    p.add_argument("--limit", type=int, default=100000)
    p.add_argument(
        "--concurrency",
        type=int,
        default=8,
        help="Websites fetched at once (default 8)",
    )
    p.add_argument(
        "--timeout", type=float, default=90.0, help="Seconds per website (default 90)"
    )
    p.add_argument(
        "--rescan", action="store_true", help="Also revisit cities already rescanned"
    )
    p.add_argument(
        "--apply", action="store_true", help="Write results (default: dry run)"
    )
    p.add_argument(
        "--batch", type=int, default=200, help="Cities per saved batch (default 200)"
    )
    p.add_argument("--database-url", default="")
    args = p.parse_args(argv)

    import psycopg2
    from psycopg2.extras import RealDictCursor

    states = [s.strip() for s in args.states.split(",") if s.strip()]
    sql, params = select_sql(states, include_rescanned=args.rescan)
    conn = psycopg2.connect(_database_url(args.database_url))
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, [*params, args.limit])
            rows = {r["geoid"]: dict(r) for r in cur.fetchall()}
        logger.info(
            "{:,} city homepage(s) to scan ({})",
            len(rows),
            "apply" if args.apply else "dry run",
        )
        batch = max(1, args.batch)
        ordered = list(rows.values())
        totals = {
            "scanned": 0,
            "found": 0,
            "errors": 0,
            "rows_with_links": 0,
            "new_links": 0,
            "primary_set": 0,
        }
        for start in range(0, len(ordered), batch):
            chunk = ordered[start : start + batch]
            results = asyncio.run(
                scan_all(chunk, concurrency=args.concurrency, timeout=args.timeout)
            )
            totals["scanned"] += len(results)
            totals["found"] += sum(1 for res in results if res.channels)
            totals["errors"] += sum(1 for res in results if res.error)
            if args.apply:
                for key, value in write_results(conn, rows, results).items():
                    totals[key] += value
            logger.info(
                "Progress {scanned:,}/{total:,}: {found:,} with YouTube links, {errors:,} errors",
                total=len(ordered),
                **totals,
            )
        if args.apply:
            logger.success(
                "Wrote {rows_with_links:,} rows with links ({new_links:,} new links); primary set on {primary_set:,}",
                **totals,
            )
        else:
            logger.success("Dry run: nothing written. Re-run with --apply to save.")
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
