#!/usr/bin/env python3
"""Discover candidate YouTube channels for county jurisdictions missing channel mappings.

Outputs a CSV suitable for manual review and downstream catalog loading.

With ``--load``, each state's CSV is immediately fed to
``load_channel_candidates_to_catalog.py`` so bronze scraped-channel columns
(and ``discovered_at``) update as loads land — the Discover dashboard clock
(#740).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

import psycopg2
from dotenv import load_dotenv
from loguru import logger

from core_lib.paths import repo_root
_REPO_ROOT = repo_root(__file__)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scrapers.youtube.discover_progress import stamp_channel_checked
from scrapers.youtube.vpn_guard import VpnRequiredError, exit_if_vpn_off, require_vpn
from scrapers.youtube.youtube_channel_discovery import YouTubeChannelDiscovery

_LOAD_SCRIPT = (
    _REPO_ROOT
    / "packages/scrapers/src/scrapers/youtube/load_channel_candidates_to_catalog.py"
)


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
    on_checked: Callable[[dict[str, Any]], Any] | None = None,
) -> list[dict[str, Any]]:
    """Search each county for its channel. ``on_checked(row)`` runs after each county, found or not (#770)."""
    out: list[dict[str, Any]] = []

    def report_checked(row: dict[str, Any]) -> None:
        if on_checked is None:
            return
        try:
            on_checked(row)
        except Exception as exc:  # noqa: BLE001 - progress bookkeeping never stops discovery
            logger.warning("Discover progress not recorded for {}: {}", row.get("geoid"), exc)

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
                out.append(
                    {
                        "jurisdiction_id": row["jurisdiction_id"],
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
                report_checked(row)
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
            except VpnRequiredError:
                # Do not keep grinding counties while Surfshark is down — abort so
                # the launch log ends with a clear error the dashboard can surface (#750).
                logger.error(
                    "VPN required — aborting discover for {} (Surfshark off). "
                    "Connect the VPN and re-run.",
                    state_code,
                )
                raise
            except Exception as exc:
                logger.warning("Discovery failed for {}: {}", county_name, exc)
                channels = []

            top = channels[0] if channels else {}
            if top:
                top = await resolve_channel_identity(
                    top,
                    fallback_method=str(top.get("discovery_method") or "").strip() or "fallback_discovery",
                )
            out.append(
                {
                    "jurisdiction_id": row["jurisdiction_id"],
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
            report_checked(row)
            if idx % 10 == 0 or idx == total:
                logger.info("Progress: {}/{}", idx, total)
    return out


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "jurisdiction_id",
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


def load_candidates_for_state(
    csv_path: Path,
    state_code: str,
    *,
    python: str,
    max_videos: int = 100,
    min_duration_seconds: int = 120,
) -> int:
    """Load a state's candidate CSV into bronze; return subprocess exit code."""
    if not _LOAD_SCRIPT.is_file():
        logger.error("Load script missing: {}", _LOAD_SCRIPT)
        return 2
    if not csv_path.is_file():
        logger.warning("No CSV to load for {}: {}", state_code, csv_path)
        return 0
    argv = [
        python,
        str(_LOAD_SCRIPT),
        "--input",
        str(csv_path),
        "--state",
        state_code,
        "--jurisdiction-type",
        "county",
        "--max-videos",
        str(max_videos),
        "--min-duration-seconds",
        str(min_duration_seconds),
        "--python",
        python,
    ]
    logger.info("Loading candidates for {} from {}", state_code, csv_path)
    return subprocess.run(argv, cwd=str(_REPO_ROOT)).returncode


def discover_one_state(
    state_code: str,
    db_url: str,
    *,
    output: str,
    multi: bool,
    skip_homepage_scrape: bool,
    data_center_jids: frozenset[str] | None = None,
    load: bool = False,
    python: str | None = None,
    max_videos: int = 100,
    min_duration_seconds: int = 120,
) -> int:
    """Discover candidate channels for one state; returns # rows with a channel.

    When ``load`` is true, immediately catalogs each candidate with a channel_id
    so scraped bronze ``discovered_at`` advances during the run (#740).
    """
    missing = fetch_missing_counties(
        db_url, state_code, data_center_jids=data_center_jids,
    )
    logger.info("Missing county mappings in {}: {}", state_code, len(missing))
    if not missing:
        logger.success("No missing county mappings for {}", state_code)
        return 0

    # Stamp each county as it is tried, so Discover's Last activity moves during the run (#770).
    progress_conn = None
    try:
        progress_conn = psycopg2.connect(db_url)
    except Exception as exc:  # noqa: BLE001 - discovery still runs; only the clock lags
        logger.warning("Discover progress connection failed ({}); Last activity will lag", exc)

    def on_checked(row: dict[str, Any]) -> None:
        if progress_conn is not None:
            stamp_channel_checked(progress_conn, state_code=state_code, geoid=str(row.get("geoid") or ""))

    try:
        results = asyncio.run(
            discover_channels(
                missing,
                state_code,
                skip_homepage_scrape=skip_homepage_scrape,
                on_checked=on_checked,
            )
        )
    finally:
        if progress_conn is not None:
            progress_conn.close()
    out_path = _state_output_path(output, state_code, multi)
    write_csv(out_path, results)

    with_channel = sum(1 for r in results if r.get("channel_id"))
    logger.success(
        "Wrote {} rows to {} ({} with candidate channel_id)",
        len(results),
        out_path,
        with_channel,
    )

    if load and with_channel > 0:
        ec = load_candidates_for_state(
            out_path,
            state_code,
            python=python or sys.executable,
            max_videos=max_videos,
            min_duration_seconds=min_duration_seconds,
        )
        if ec != 0:
            logger.warning(
                "Load for {} exited {} — Discover last activity may lag for failed rows",
                state_code,
                ec,
            )
    return with_channel


@exit_if_vpn_off
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
        "--load",
        action="store_true",
        help=(
            "After each state CSV, load candidates with a channel_id into bronze "
            "(updates Discover last activity as loads land; #740)"
        ),
    )
    p.add_argument(
        "--max-videos",
        type=int,
        default=100,
        help="When --load, max videos per channel cataloged (default: 100)",
    )
    p.add_argument(
        "--min-duration-seconds",
        type=int,
        default=120,
        help="When --load, skip videos shorter than this (default: 120)",
    )
    args = p.parse_args()

    require_vpn()

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
        require_vpn()
        discover_one_state(
            state_code,
            db_url,
            output=args.output,
            multi=multi,
            skip_homepage_scrape=args.skip_homepage_scrape,
            data_center_jids=data_center_jids,
            load=bool(args.load),
            python=sys.executable,
            max_videos=int(args.max_videos),
            min_duration_seconds=int(args.min_duration_seconds),
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
