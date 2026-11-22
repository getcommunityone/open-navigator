#!/usr/bin/env python3
"""Discover candidate YouTube channels for county jurisdictions missing channel mappings.

Each hit is gated automatically before bronze write-through (#697):

1. Channel name/mismatch gate (website-linked finds skip this)
2. Jev meta screen on the newest channel upload — accept when
   ``P(government_meeting)+P(town_hall) >= --jev-min-meeting-p`` (default 0.6)

Accepted rows UPDATE ``bronze.bronze_jurisdictions_counties_scraped`` with
``youtube_channel_selection_method = discover_jev``. CSV audit output is always
written. Use ``--no-bronze-write`` or ``--skip-jev-gate`` for CSV-only / gates-only.
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

# Accepted after channel gates + Jev meta keep-score (#697).
DISCOVER_JEV_METHOD = "discover_jev"
# Legacy label from #695 (human-review queue); no longer written by default.
DISCOVER_UNREVIEWED_METHOD = "discover_unreviewed"
DEFAULT_JEV_MIN_MEETING_P = 0.6
# Try this many newest uploads before rejecting the channel (#697 follow-up).
DEFAULT_JEV_MAX_VIDEOS = 7


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


def channel_gate_reject_reason(row: dict[str, Any], *, state_code: str) -> Optional[str]:
    """Return a reject reason from name/mismatch gates, or None if the hit may proceed to Jev.

    Website-linked finds skip the title-mismatch gate (the site is the proof).
    API / pattern guesses that name another government are rejected here.
    """
    method = str(row.get("discovery_method") or "").strip().lower()
    if method in ("website_scrape", "scraped_official_website"):
        return None
    from scrapers.discovery.channel_government_mismatch import title_names_other_government

    reason = title_names_other_government(
        str(row.get("channel_title") or ""),
        jurisdiction_name=str(row.get("county_name") or ""),
        jurisdiction_type="county",
        state_code=state_code,
        channel_url=str(row.get("channel_url") or ""),
    )
    return reason


def fetch_newest_channel_uploads(
    api_key: str,
    channel_id: str,
    *,
    limit: int = DEFAULT_JEV_MAX_VIDEOS,
) -> list[dict[str, Any]]:
    """Up to *limit* newest uploads-playlist items for *channel_id*."""
    from scrapers.youtube.backfill_channel_from_api import list_uploads

    cid = (channel_id or "").strip()
    if not cid.startswith("UC") or not (api_key or "").strip():
        return []
    n = max(1, int(limit or DEFAULT_JEV_MAX_VIDEOS))
    uploads = list_uploads(
        api_key.strip(),
        cid,
        published_after=None,
        published_before=None,
        max_pages=1,
    )
    return uploads[:n]


def fetch_newest_channel_upload(
    api_key: str, channel_id: str
) -> Optional[dict[str, Any]]:
    """Newest uploads-playlist item for *channel_id*, or None."""
    uploads = fetch_newest_channel_uploads(api_key, channel_id, limit=1)
    return uploads[0] if uploads else None


def jev_meta_keep_for_upload(
    upload: dict[str, Any],
    *,
    channel_title: str = "",
    client: Any = None,
) -> tuple[Optional[float], str]:
    """Screen one upload's title/description with Jev; return (keep_p, video_id)."""
    from llm.typesafe.client import JevClient
    from llm.typesafe.screen_transcripts import meeting_keep_p
    from llm.typesafe.screen_video_meta import build_meta_state, screen_meta

    video_id = str(upload.get("video_id") or "").strip()
    if not video_id:
        return None, ""
    state = build_meta_state(
        title=upload.get("title"),
        description=upload.get("description"),
        channel_title=channel_title or None,
    )
    own_client = client is None
    jev = client or JevClient()
    try:
        if own_client and hasattr(jev, "__enter__"):
            jev.__enter__()
        result = screen_meta(jev, video_id, state)
    finally:
        if own_client and hasattr(jev, "__exit__"):
            jev.__exit__(None, None, None)
    if result is None:
        return None, video_id
    return meeting_keep_p(result.meeting_kind_probabilities), video_id


def evaluate_discover_for_bronze(
    row: dict[str, Any],
    *,
    state_code: str,
    min_meeting_p: float = DEFAULT_JEV_MIN_MEETING_P,
    youtube_api_key: str = "",
    jev_client: Any = None,
    skip_jev: bool = False,
    max_jev_videos: int = DEFAULT_JEV_MAX_VIDEOS,
) -> tuple[bool, str, Optional[float]]:
    """Channel gates then Jev meta keep-score. Returns (accepted, reason, keep_p).

    Tries up to ``max_jev_videos`` newest uploads; the first keep-score at or
    above ``min_meeting_p`` accepts. Only fails after every tried video is
    below threshold, unscreenable, or errors.
    """
    channel_id = str(row.get("channel_id") or "").strip()
    if not channel_id:
        return False, "no_channel_id", None

    mismatch = channel_gate_reject_reason(row, state_code=state_code)
    if mismatch:
        return False, f"channel_gate:{mismatch}", None

    if skip_jev:
        return True, "skip_jev_gate", _confidence_from_row(row)

    key = (youtube_api_key or os.getenv("YOUTUBE_API_KEY") or "").strip()
    if not key:
        return False, "missing_youtube_api_key", None

    try:
        uploads = fetch_newest_channel_uploads(
            key, channel_id, limit=max_jev_videos,
        )
    except Exception as exc:
        return False, f"uploads_fetch_failed:{exc}", None
    if not uploads:
        return False, "no_uploads", None

    channel_title = str(row.get("channel_title") or "")
    attempts: list[str] = []
    best_keep: Optional[float] = None
    for upload in uploads:
        video_id = str(upload.get("video_id") or "").strip()
        try:
            keep_p, vid = jev_meta_keep_for_upload(
                upload,
                channel_title=channel_title,
                client=jev_client,
            )
        except Exception as exc:
            attempts.append(f"{video_id or '?'}:jev_failed:{exc}")
            logger.info(
                "Discover Jev miss {} video {}: {}",
                row.get("jurisdiction_id"),
                video_id or "?",
                exc,
            )
            continue
        if keep_p is None:
            attempts.append(f"{vid or video_id}:unscreened")
            logger.info(
                "Discover Jev unscreened {} video {}",
                row.get("jurisdiction_id"),
                vid or video_id,
            )
            continue
        if best_keep is None or keep_p > best_keep:
            best_keep = keep_p
        if keep_p >= float(min_meeting_p):
            return True, f"jev_ok:{keep_p:.3f} video={vid}", keep_p
        attempts.append(f"{vid}:{keep_p:.3f}")
        logger.info(
            "Discover Jev below threshold {} video {} keep_p={:.3f} (try next)",
            row.get("jurisdiction_id"),
            vid,
            keep_p,
        )

    tried = len(attempts)
    detail = ",".join(attempts[:7])
    return (
        False,
        f"jev_exhausted:{tried}_videos best={best_keep} [{detail}]",
        best_keep,
    )


def persist_discovered_channel_to_bronze(
    conn: Any,
    row: dict[str, Any],
    *,
    state_code: str,
    method: str = DISCOVER_JEV_METHOD,
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
    jev_min_meeting_p: float = DEFAULT_JEV_MIN_MEETING_P,
    skip_jev_gate: bool = False,
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
    bronze_rejects = 0
    bronze_conn = None
    jev_client = None
    on_result: Optional[Callable[[dict[str, Any]], None]] = None
    if write_bronze:
        bronze_conn = psycopg2.connect(db_url)
        if not skip_jev_gate:
            from llm.typesafe.client import JevClient

            jev_client = JevClient()
            jev_client.__enter__()

        def _persist(result: dict[str, Any]) -> None:
            nonlocal bronze_writes, bronze_rejects
            if not str(result.get("channel_id") or "").strip():
                return
            try:
                ok, reason, keep_p = evaluate_discover_for_bronze(
                    result,
                    state_code=state_code,
                    min_meeting_p=jev_min_meeting_p,
                    jev_client=jev_client,
                    skip_jev=skip_jev_gate,
                )
                if not ok:
                    bronze_rejects += 1
                    logger.info(
                        "Discover reject {}: {} (keep_p={})",
                        result.get("jurisdiction_id"),
                        reason,
                        keep_p,
                    )
                    return
                conf = keep_p if keep_p is not None else _confidence_from_row(result)
                row = dict(result)
                if conf is not None:
                    row["policy_score"] = conf
                if persist_discovered_channel_to_bronze(
                    bronze_conn,
                    row,
                    state_code=state_code,
                    method=DISCOVER_JEV_METHOD,
                ):
                    bronze_writes += 1
                    logger.success(
                        "Discover accept {}: {}",
                        result.get("jurisdiction_id"),
                        reason,
                    )
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
        if jev_client is not None:
            jev_client.__exit__(None, None, None)
        if bronze_conn is not None:
            bronze_conn.close()

    out_path = _state_output_path(output, state_code, multi)
    write_csv(out_path, results)

    with_channel = sum(1 for r in results if r.get("channel_id"))
    logger.success(
        "Wrote {} rows to {} ({} with candidate channel_id; "
        "{} bronze accepted; {} gated rejects)",
        len(results),
        out_path,
        with_channel,
        bronze_writes,
        bronze_rejects,
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
    p.add_argument(
        "--skip-jev-gate",
        action="store_true",
        help="Channel mismatch gate only — skip Jev meta keep-score (#697)",
    )
    p.add_argument(
        "--jev-min-meeting-p",
        type=float,
        default=float(os.getenv("DISCOVER_JEV_MIN_MEETING_P") or DEFAULT_JEV_MIN_MEETING_P),
        help="Min P(government_meeting)+P(town_hall) to accept (default 0.6)",
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
            jev_min_meeting_p=args.jev_min_meeting_p,
            skip_jev_gate=args.skip_jev_gate,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
