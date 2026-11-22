#!/usr/bin/env python3
"""Discover candidate YouTube channels for county jurisdictions missing channel mappings.

Writes each hit into ``bronze.bronze_jurisdictions_counties_scraped`` as it is
found (same write-through pattern as catalog/captions), and still emits a CSV
audit file. Rows are flagged ``discover_unreviewed`` so a later review pass can
filter them (#695).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import sys
from pathlib import Path
from typing import Any, Callable, Optional

import psycopg2
from dotenv import load_dotenv
from loguru import logger

from core_lib.paths import repo_root
_REPO_ROOT = repo_root(__file__)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scrapers.youtube.youtube_channel_discovery import YouTubeChannelDiscovery

# Review flag on scraped bronze — catalog still uses these channels (unlike
# pattern_match_unverified). Filter WHERE method = this for a review queue.
DISCOVER_UNREVIEWED_METHOD = "discover_unreviewed"


def resolve_database_url(explicit: str | None) -> str:
    load_dotenv(_REPO_ROOT / ".env")
    return (
        (explicit or "").strip()
        or (os.getenv("OPEN_NAVIGATOR_DATABASE_URL") or "").strip()
        or (os.getenv("NEON_DATABASE_URL_DEV") or "").strip()
        or (os.getenv("NEON_DATABASE_URL") or "").strip()
        or (os.getenv("DATABASE_URL") or "").strip()
        or "postgresql://postgres:password@localhost:5433/open_navigator"
    )


def fetch_missing_counties(
    database_url: str,
    state_code: str,
    *,
    data_center_jids: frozenset[str] | None = None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            j.jurisdiction_id,
            j.geoid,
            j.name AS county_name,
            COALESCE(w.website_url, '') AS website_url,
            COALESCE(s.payload->'youtube_channels', '[]'::jsonb) AS scraped_youtube_channels,
            s.homepage_url AS scraped_homepage_url,
            s.discovered_at
        FROM intermediate.int_jurisdictions j
        LEFT JOIN LATERAL (
            SELECT iw.website_url
            FROM intermediate.int_jurisdiction_websites iw
            WHERE iw.jurisdiction_id = j.jurisdiction_id
              AND iw.website_url IS NOT NULL
              AND BTRIM(iw.website_url) <> ''
            ORDER BY iw.website_source NULLS LAST, iw.website_url
            LIMIT 1
        ) w ON true
                LEFT JOIN bronze.bronze_jurisdictions_counties_scraped s
                    ON s.usps = j.state_code
                 AND s.geoid = j.geoid
        WHERE j.state_code = %s
          AND j.jurisdiction_type = 'county'
          AND j.jurisdiction_id NOT IN (
              SELECT DISTINCT jurisdiction_id
              FROM intermediate.int_events_channels
              WHERE state_code = %s
                AND jurisdiction_id LIKE 'county_%%'
          )
    """
    params: list[Any] = [state_code, state_code]
    if data_center_jids is not None:
        sql += " AND j.jurisdiction_id = ANY(%s)"
        params.append(list(data_center_jids))
    sql += " ORDER BY j.name"

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    return [
        {
            "jurisdiction_id": r[0],
            "geoid": r[1],
            "county_name": r[2],
            "website_url": r[3] or "",
            "scraped_youtube_channels": r[4] or [],
            "scraped_homepage_url": r[5] or "",
            "scraped_discovered_at": r[6].isoformat() if r[6] else "",
        }
        for r in rows
    ]


def _confidence_from_row(row: dict[str, Any]) -> Optional[float]:
    raw = row.get("policy_score")
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def persist_discovered_channel_to_bronze(
    conn: Any,
    row: dict[str, Any],
    *,
    state_code: str,
    method: str = DISCOVER_UNREVIEWED_METHOD,
) -> bool:
    """Write one discover hit onto ``bronze_jurisdictions_counties_scraped``.

    Only fills empty ``youtube_channel_id`` rows. Sets ``discovered_at = now()``
    so the Discover stage clock moves. Returns True when a row was updated.
    """
    geoid = str(row.get("geoid") or "").strip()
    channel_id = str(row.get("channel_id") or "").strip()
    channel_url = str(row.get("channel_url") or "").strip()
    usps = (state_code or "").strip().upper()
    if not geoid or not usps or not channel_id:
        return False
    if not channel_url.startswith("http"):
        channel_url = f"https://www.youtube.com/channel/{channel_id}"
    confidence = _confidence_from_row(row)
    jid = str(row.get("jurisdiction_id") or "").strip() or None
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE bronze.bronze_jurisdictions_counties_scraped
               SET youtube_channel_id = %s,
                   youtube_channel_url = %s,
                   youtube_channel_selection_method = %s,
                   youtube_channel_selection_confidence = COALESCE(%s, youtube_channel_selection_confidence),
                   discovered_at = NOW(),
                   jurisdiction_id = COALESCE(jurisdiction_id, %s)
             WHERE geoid = %s
               AND usps = %s
               AND (
                     youtube_channel_id IS NULL
                     OR BTRIM(youtube_channel_id) = ''
               )
            """,
            (channel_id, channel_url, method, confidence, jid, geoid, usps),
        )
        updated = cur.rowcount > 0
    conn.commit()
    if updated:
        logger.info(
            "Bronze write-through: {} {} → {} ({})",
            usps,
            geoid,
            channel_id,
            method,
        )
    return updated


def choose_scraped_channel(channels: Any) -> dict[str, Any]:
    """Pick the best website-scraped candidate when available."""
    if not isinstance(channels, list):
        return {}

    def score(channel: dict[str, Any]) -> tuple[int, int, int]:
        method = str(channel.get("discovery_method") or "")
        confidence = float(channel.get("confidence") or 0)
        videos = int(channel.get("video_count") or 0)
        method_bonus = 2 if method == "website_scrape" else 1 if method == "pattern_match" else 0
        return (method_bonus, int(confidence * 1000), videos)

    usable = [c for c in channels if isinstance(c, dict) and (c.get("channel_id") or c.get("channel_url"))]
    if not usable:
        return {}
    usable.sort(key=score, reverse=True)
    return usable[0]


async def discover_channels(
    rows: list[dict[str, Any]],
    state_code: str,
    *,
    skip_homepage_scrape: bool = False,
    on_result: Optional[Callable[[dict[str, Any]], None]] = None,
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []

    def _emit(result: dict[str, Any]) -> None:
        out.append(result)
        if on_result is not None:
            on_result(result)

    def title_fallback(channel: dict[str, Any]) -> str:
        title = str(channel.get("channel_title") or "").strip()
        if title:
            return title
        url = str(channel.get("channel_url") or "").strip().rstrip("/")
        if url:
            return url.split("/")[-1]
        cid = str(channel.get("channel_id") or "").strip()
        return cid

    def summarize_candidates(channels: list[dict[str, Any]], limit: int = 3) -> str:
        parts: list[str] = []
        for channel in channels[:limit]:
            name = title_fallback(channel) or "(unknown)"
            method = str(channel.get("discovery_method") or "")
            videos = channel.get("video_count")
            latest = str(channel.get("latest_upload") or "")
            bits = [name]
            if method:
                bits.append(method)
            if videos not in (None, ""):
                bits.append(f"videos={videos}")
            if latest:
                bits.append(f"latest={latest}")
            parts.append(" | ".join(bits))
        return " || ".join(parts)

    async with YouTubeChannelDiscovery() as discovery:
        async def resolve_channel_identity(channel: dict[str, Any], *, fallback_method: str) -> dict[str, Any]:
            """Resolve missing channel_id from channel_url for resilient downstream loading."""
            channel_id = str(channel.get("channel_id") or "").strip()
            if channel_id:
                return channel

            channel_url = str(channel.get("channel_url") or "").strip()
            if not channel_url:
                return channel

            method = str(channel.get("discovery_method") or "").strip() or fallback_method
            resolved = await discovery._check_channel_exists(channel_url, method)
            if not resolved:
                return channel

            merged = dict(channel)
            merged["channel_id"] = str(resolved.get("channel_id") or "").strip()
            merged["channel_url"] = str(resolved.get("channel_url") or channel_url).strip()
            merged["channel_title"] = str(channel.get("channel_title") or "").strip() or str(
                resolved.get("channel_title") or ""
            ).strip()
            for key in ("video_count", "subscriber_count", "view_count", "latest_upload", "policy_score"):
                if merged.get(key) in (None, ""):
                    merged[key] = resolved.get(key, "")
            if not str(merged.get("discovery_method") or "").strip():
                merged["discovery_method"] = method
            if merged.get("confidence") in (None, "") and resolved.get("confidence") not in (None, ""):
                merged["confidence"] = resolved.get("confidence")
            return merged

        total = len(rows)
        for idx, row in enumerate(rows, 1):
            county_name = str(row["county_name"]).strip()
            website = str(row.get("website_url") or "").strip() or None
            if skip_homepage_scrape:
                website = None

            scraped_top = choose_scraped_channel(row.get("scraped_youtube_channels"))
            if scraped_top:
                scraped_top = await resolve_channel_identity(
                    scraped_top,
                    fallback_method=str(scraped_top.get("discovery_method") or "").strip() or "website_scrape",
                )
                _emit(
                    {
                        "jurisdiction_id": row["jurisdiction_id"],
                        "geoid": row.get("geoid", "") or "",
                        "county_name": county_name,
                        "website_url": website or "",
                        "channel_id": scraped_top.get("channel_id", "") or "",
                        "channel_url": scraped_top.get("channel_url", "") or "",
                        "channel_title": title_fallback(scraped_top),
                        "video_count": scraped_top.get("video_count", "") or "",
                        "subscriber_count": scraped_top.get("subscriber_count", "") or "",
                        "view_count": scraped_top.get("view_count", "") or "",
                        "latest_upload": scraped_top.get("latest_upload", "") or "",
                        "policy_score": scraped_top.get("policy_score", "") or "",
                        "discovery_method": scraped_top.get("discovery_method", "website_scrape") or "website_scrape",
                        "candidate_count": len(row.get("scraped_youtube_channels") or []),
                        "top_candidates": summarize_candidates(row.get("scraped_youtube_channels") or [scraped_top]),
                        "source_priority": "scraped_official_website",
                        "scraped_discovered_at": row.get("scraped_discovered_at", "") or "",
                    }
                )
                if idx % 10 == 0 or idx == total:
                    logger.info("Progress: {}/{}", idx, total)
                continue

            try:
                channels = await discovery.discover_channels(
                    city_name=None,
                    county_name=county_name,
                    state_code=state_code,
                    homepage_url=website,
                )
            except Exception as exc:
                logger.warning("Discovery failed for {}: {}", county_name, exc)
                channels = []

            top = channels[0] if channels else {}
            if top:
                top = await resolve_channel_identity(
                    top,
                    fallback_method=str(top.get("discovery_method") or "").strip() or "fallback_discovery",
                )
            _emit(
                {
                    "jurisdiction_id": row["jurisdiction_id"],
                    "geoid": row.get("geoid", "") or "",
                    "county_name": county_name,
                    "website_url": website or "",
                    "channel_id": top.get("channel_id", "") or "",
                    "channel_url": top.get("channel_url", "") or "",
                    "channel_title": title_fallback(top),
                    "video_count": top.get("video_count", "") or "",
                    "subscriber_count": top.get("subscriber_count", "") or "",
                    "view_count": top.get("view_count", "") or "",
                    "latest_upload": top.get("latest_upload", "") or "",
                    "policy_score": top.get("policy_score", "") or "",
                    "discovery_method": top.get("discovery_method", "") or "",
                    "candidate_count": len(channels),
                    "top_candidates": summarize_candidates(channels),
                    "source_priority": "fallback_discovery",
                    "scraped_discovered_at": row.get("scraped_discovered_at", "") or "",
                }
            )
            if idx % 10 == 0 or idx == total:
                logger.info("Progress: {}/{}", idx, total)
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "jurisdiction_id",
        "geoid",
        "county_name",
        "website_url",
        "channel_id",
        "channel_url",
        "channel_title",
        "video_count",
        "subscriber_count",
        "view_count",
        "latest_upload",
        "policy_score",
        "discovery_method",
        "candidate_count",
        "top_candidates",
        "source_priority",
        "scraped_discovered_at",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _state_output_path(output: str, state_code: str, multi: bool) -> Path:
    """Resolve the CSV path for a state. For multi-state runs, insert the state
    code before the suffix (``cands.csv`` -> ``cands_GA.csv``) so states don't
    overwrite each other."""
    base = Path(output).expanduser().resolve()
    if not multi:
        return base
    return base.with_name(f"{base.stem}_{state_code}{base.suffix}")


def discover_one_state(
    state_code: str,
    db_url: str,
    *,
    output: str,
    multi: bool,
    skip_homepage_scrape: bool,
    data_center_jids: frozenset[str] | None = None,
    write_bronze: bool = True,
) -> int:
    """Discover candidate channels for one state; returns # rows with a channel."""
    missing = fetch_missing_counties(
        db_url, state_code, data_center_jids=data_center_jids,
    )
    logger.info("Missing county mappings in {}: {}", state_code, len(missing))
    if not missing:
        logger.success("No missing county mappings for {}", state_code)
        return 0

    bronze_writes = 0
    bronze_conn = None
    on_result: Optional[Callable[[dict[str, Any]], None]] = None
    if write_bronze:
        bronze_conn = psycopg2.connect(db_url)

        def _persist(result: dict[str, Any]) -> None:
            nonlocal bronze_writes
            if not str(result.get("channel_id") or "").strip():
                return
            try:
                if persist_discovered_channel_to_bronze(
                    bronze_conn, result, state_code=state_code,
                ):
                    bronze_writes += 1
            except Exception as exc:
                if bronze_conn is not None:
                    bronze_conn.rollback()
                logger.warning(
                    "Bronze write-through failed for {}: {}",
                    result.get("jurisdiction_id"),
                    exc,
                )

        on_result = _persist

    try:
        results = asyncio.run(
            discover_channels(
                missing,
                state_code,
                skip_homepage_scrape=skip_homepage_scrape,
                on_result=on_result,
            )
        )
    finally:
        if bronze_conn is not None:
            bronze_conn.close()

    out_path = _state_output_path(output, state_code, multi)
    write_csv(out_path, results)

    with_channel = sum(1 for r in results if r.get("channel_id"))
    logger.success(
        "Wrote {} rows to {} ({} with candidate channel_id; {} bronze write-through)",
        len(results),
        out_path,
        with_channel,
        bronze_writes,
    )
    return with_channel


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--state", default="GA", help="Two-letter state code (default: GA)")
    p.add_argument(
        "--states",
        default="",
        help="Comma-separated state codes to sweep (e.g. AL,GA,IN). Overrides --state.",
    )
    p.add_argument(
        "--skip-homepage-scrape",
        action="store_true",
        help="Skip website scraping and use handle patterns + YouTube API only",
    )
    p.add_argument(
        "--output",
        default="/tmp/ga_channel_candidates.csv",
        help="Output CSV path (per-state suffix added when sweeping multiple states)",
    )
    p.add_argument("--database-url", default="", help="Postgres URL override")
    p.add_argument(
        "--cohort",
        default="",
        help="Launch cohort (e.g. data_centers restricts to data-center jurisdictions)",
    )
    p.add_argument(
        "--no-bronze-write",
        action="store_true",
        help="CSV only — do not UPDATE bronze_jurisdictions_counties_scraped (#695)",
    )
    args = p.parse_args()

    cohort = (args.cohort or "").strip().lower()
    data_center_jids: frozenset[str] | None = None
    if cohort == "data_centers":
        from api.batch_jobs.cohorts import data_center_jurisdiction_ids

        with psycopg2.connect(resolve_database_url(args.database_url)) as conn:
            data_center_jids = frozenset(data_center_jurisdiction_ids(conn))
        if not data_center_jids:
            logger.warning("data_centers cohort: no jurisdiction ids in warehouse")
            return 0

    if args.states.strip():
        states = [s.strip().upper() for s in args.states.split(",") if s.strip()]
    else:
        states = [args.state.strip().upper()]
    db_url = resolve_database_url(args.database_url)

    multi = len(states) > 1
    for state_code in states:
        discover_one_state(
            state_code,
            db_url,
            output=args.output,
            multi=multi,
            skip_homepage_scrape=args.skip_homepage_scrape,
            data_center_jids=data_center_jids,
            write_bronze=not args.no_bronze_write,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
