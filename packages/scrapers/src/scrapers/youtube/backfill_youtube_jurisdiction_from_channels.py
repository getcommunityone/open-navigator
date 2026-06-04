#!/usr/bin/env python3
"""Backfill ``jurisdiction_id`` / geo onto channel-discovered ``bronze_event_youtube`` rows.

A large slice of ``datasource = 'youtube'`` rows in ``bronze.bronze_event_youtube``
were ingested channel-first and never had jurisdiction resolution written back:
``jurisdiction_id`` / ``jurisdiction_name`` / ``jurisdiction_type`` / ``state_code``
are all NULL. That starves the per-jurisdiction analyze loop
(``llm.gemini.meeting_transcript_policy``) — those videos can't be targeted, so
their transcripts sit unanalyzed (~40k of the unanalyzed backlog as of 2026-06).

Unlike the CivicSearch case (``enrich_civicsearch_jurisdictions``), the geo here
does NOT need fuzzy entity resolution — it already exists in the warehouse. In
practice the whole blank set is LocalView-origin, so source 0 below resolves
essentially all of it; the channel-based sources (1-2) are a fallback for any
future non-LocalView blanks. In descending trust:

0. **LocalView resolved model** — ``intermediate.int_events_localview_enriched``
   carries a geoid-resolved canonical ``jurisdiction_id`` per ``video_url`` (these
   videos were promoted into bronze with their channel/jurisdiction columns
   stripped). A materialized geoid match, no guessing. ``confidence = high``.

1. **Scraped channel map** — ``bronze.bronze_jurisdictions_counties_scraped`` and
   ``bronze.bronze_jurisdictions_municipalities_scraped`` carry a 1:1
   ``youtube_channel_id → jurisdiction_id`` (the priority-states scrape campaign).
   No ambiguity by construction. ``confidence = high``, ``method = scraped``.
2. **Channel catalog** — ``bronze.bronze_events_channels.jurisdictions`` (JSONB
   array) aggregates every discovery method (localview, wikidata, public-website).
   Most arrays are one place expressed with duplicate id forms (canonical
   ``municipality_<geoid>`` + a legacy ``<slug>_<geoid>`` sharing the same geoid),
   so they collapse to a single jurisdiction (``confidence = high``). A parent
   county/state plus exactly one local jurisdiction is the venue, not ambiguity
   ("Howell Township" = Monmouth County + Howell township) → ``confidence = medium``.
   Only a channel spanning several distinct local jurisdictions (regional PEG media
   like "Town Meeting TV", covering 6 towns) is genuinely lossy → ``confidence =
   low`` with a deterministic pick (most specific type, then lowest geoid), so it
   can be withheld via ``--min-confidence``.

Name / ``state_code`` / canonical type are taken from ``intermediate.int_jurisdictions``
(authoritative), falling back to the catalog JSONB fields when a jurisdiction_id is
absent there. Only rows with a NULL/blank ``jurisdiction_id`` and
``datasource = 'youtube'`` are touched, so the job is idempotent.

Usage (repo root)::

    .venv/bin/python packages/scrapers/src/scrapers/youtube/backfill_youtube_jurisdiction_from_channels.py --dry-run
    .venv/bin/python packages/scrapers/src/scrapers/youtube/backfill_youtube_jurisdiction_from_channels.py
    .venv/bin/python packages/scrapers/src/scrapers/youtube/backfill_youtube_jurisdiction_from_channels.py --min-confidence high

Configuration: ``NEON_DATABASE_URL_DEV`` / ``NEON_DATABASE_URL`` / ``DATABASE_URL`` (dev only).
"""

from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple

from dotenv import load_dotenv
from loguru import logger

# .../packages/scrapers/src/scrapers/youtube/<this file> → repo root is 5 levels up.
_REPO_ROOT = Path(__file__).resolve().parents[5]

# Confidence ranks, lowest → highest, for --min-confidence gating.
_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}

# Canonical bronze/int_jurisdictions ids are slug-form ending in a census geoid
# (``carver_2502311665``, ``lake_park_1344704``). The catalog also carries a
# foreign ``<type>_<geoid>`` form (``municipality_1719161``) for the SAME place —
# both are reconciled to the canonical slug id by their shared trailing geoid.
_TRAILING_GEOID_RE = re.compile(r"_([0-9]+)$")

# Type specificity for breaking a genuine multi-jurisdiction tie — most specific
# first (a regional channel is most usefully attributed to the municipality).
_TYPE_SPECIFICITY = {
    "municipality": 0,
    "township": 1,
    "school_district": 2,
    "county": 3,
    "state": 4,
}


def _database_url(explicit: Optional[str]) -> str:
    env_path = _REPO_ROOT / ".env"
    load_dotenv(env_path if env_path.exists() else None)
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    )


def _geoid_of(jurisdiction_id: str) -> Optional[str]:
    """Trailing census geoid of any id form (``dekalb_1719161`` → ``1719161``)."""
    m = _TRAILING_GEOID_RE.search((jurisdiction_id or "").strip())
    return m.group(1) if m else None


def _to_canonical(
    jurisdiction_id: str,
    geoid_index: Dict[str, set],
    lookup: Dict[str, "JurisInfo"],
) -> Optional[str]:
    """Map any catalog/scraped id to the canonical ``int_jurisdictions`` slug id.

    Reconciliation is by trailing geoid, so the catalog's foreign
    ``municipality_1719161`` and its sibling slug ``dekalb_1719161`` both land on
    the one id bronze actually uses. If a geoid backs several canonical ids (rare —
    same FIPS, different type) the most specific type wins.
    """
    jid = (jurisdiction_id or "").strip()
    if jid in lookup:  # already a canonical int_jurisdictions id
        return jid
    geoid = _geoid_of(jid)
    if geoid is None:
        return None
    cands = geoid_index.get(geoid)
    if not cands:
        return None
    if len(cands) == 1:
        return next(iter(cands))
    return min(
        cands,
        key=lambda x: _TYPE_SPECIFICITY.get(
            (lookup[x].jurisdiction_type or ""), 99
        ),
    )


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class JurisInfo:
    name: str
    state_code: Optional[str]
    state: Optional[str]
    jurisdiction_type: Optional[str]


@dataclass(frozen=True)
class Resolution:
    jurisdiction_id: str
    jurisdiction_name: str
    jurisdiction_type: Optional[str]
    state_code: Optional[str]
    state: Optional[str]
    confidence: str
    method: str


def load_jurisdiction_lookup(
    conn,
) -> Tuple[Dict[str, JurisInfo], Dict[str, set]]:
    """``jurisdiction_id → info`` plus ``geoid → {canonical ids}`` from int_jurisdictions."""
    lookup: Dict[str, JurisInfo] = {}
    geoid_index: Dict[str, set] = defaultdict(set)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT jurisdiction_id, name, state_code, state, jurisdiction_type
            FROM intermediate.int_jurisdictions
            WHERE jurisdiction_id IS NOT NULL
            """
        )
        for jid, name, sc, st, jt in cur.fetchall():
            lookup[jid] = JurisInfo(
                name=name, state_code=sc, state=st, jurisdiction_type=jt
            )
            geoid = _geoid_of(jid)
            if geoid is not None:
                geoid_index[geoid].add(jid)
    logger.info(
        "Loaded {:,} canonical jurisdictions ({:,} distinct geoids)",
        len(lookup),
        len(geoid_index),
    )
    return lookup, geoid_index


def load_scraped_channel_map(conn) -> Dict[str, str]:
    """``youtube_channel_id → jurisdiction_id`` from the scraped jurisdiction tables.

    1:1 by construction (the priority-states campaign picks one channel per
    jurisdiction). If the same channel ever appears under two jurisdictions the
    later row wins — logged so it can be audited.
    """
    out: Dict[str, str] = {}
    collisions = 0
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT youtube_channel_id, jurisdiction_id
            FROM bronze.bronze_jurisdictions_counties_scraped
            WHERE youtube_channel_id IS NOT NULL AND youtube_channel_id <> ''
              AND jurisdiction_id IS NOT NULL AND jurisdiction_id <> ''
            UNION ALL
            SELECT youtube_channel_id, jurisdiction_id
            FROM bronze.bronze_jurisdictions_municipalities_scraped
            WHERE youtube_channel_id IS NOT NULL AND youtube_channel_id <> ''
              AND jurisdiction_id IS NOT NULL AND jurisdiction_id <> ''
            """
        )
        for channel_id, jid in cur.fetchall():
            if channel_id in out and out[channel_id] != jid:
                collisions += 1
            out[channel_id] = jid
    logger.info(
        "Loaded {:,} scraped channel→jurisdiction mappings ({} collisions)",
        len(out),
        collisions,
    )
    return out


def load_catalog_channel_map(conn) -> Dict[str, list]:
    """``channel_id → jurisdictions JSONB array`` from bronze_events_channels."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT channel_id, jurisdictions
            FROM bronze.bronze_events_channels
            WHERE channel_id IS NOT NULL AND channel_id <> ''
              AND jurisdictions IS NOT NULL
              AND jurisdictions::text NOT IN ('', '[]', 'null', '{}')
            """
        )
        out = {channel_id: juris for channel_id, juris in cur.fetchall()}
    logger.info("Loaded {:,} catalog channels with jurisdictions", len(out))
    return out


def load_localview_video_map(conn) -> Dict[str, str]:
    """``video_id → jurisdiction_id`` from the resolved LocalView dbt model.

    LocalView videos promoted into ``bronze_event_youtube`` lost their channel /
    jurisdiction columns, but ``intermediate.int_events_localview_enriched`` already
    carries the geoid-resolved canonical ``jurisdiction_id`` (keyed by ``video_url``).
    This is the highest-trust source — a materialized geoid match, no guessing.
    """
    with conn.cursor() as cur:
        cur.execute(
            r"""
            SELECT regexp_replace(video_url, '^.*[=/]', '') AS video_id,
                   jurisdiction_id
            FROM intermediate.int_events_localview_enriched
            WHERE jurisdiction_id IS NOT NULL AND jurisdiction_id <> ''
              AND video_url IS NOT NULL AND video_url <> ''
            """
        )
        out = {vid: jid for vid, jid in cur.fetchall()}
    logger.info("Loaded {:,} LocalView video→jurisdiction mappings", len(out))
    return out


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------


def _build_resolution(
    jurisdiction_id: str,
    *,
    confidence: str,
    method: str,
    lookup: Dict[str, JurisInfo],
    catalog_fallback: Optional[dict] = None,
) -> Optional[Resolution]:
    """Attach name / state / type from int_jurisdictions (catalog JSONB fallback)."""
    info = lookup.get(jurisdiction_id)
    if info is not None:
        name = info.name
        state_code = info.state_code
        state = info.state
        jtype = info.jurisdiction_type
    elif catalog_fallback is not None:
        name = catalog_fallback.get("jurisdiction_name") or ""
        state_code = catalog_fallback.get("state_code")
        state = catalog_fallback.get("state")
        jtype = catalog_fallback.get("jurisdiction_type")
    else:
        return None
    return Resolution(
        jurisdiction_id=jurisdiction_id,
        jurisdiction_name=name,
        jurisdiction_type=jtype,
        state_code=state_code,
        state=state,
        confidence=confidence,
        method=method,
    )


def resolve_from_catalog(
    jurisdictions: list,
    lookup: Dict[str, JurisInfo],
    geoid_index: Dict[str, set],
) -> Optional[Resolution]:
    """Pick one jurisdiction from a catalog JSONB array.

    Every entry is first canonicalized to an ``int_jurisdictions`` id (legacy
    ``<slug>_<geoid>`` forms recovered via geoid), then deduped by geoid: a single
    distinct geoid is unambiguous (``high``); a genuine multi-jurisdiction channel
    gets a deterministic pick (most specific type, then lowest geoid) at ``low``.
    """
    # canonical slug id → original entry (first seen), for name/state fallback.
    canonical: Dict[str, dict] = {}
    for entry in jurisdictions or []:
        raw = (entry or {}).get("jurisdiction_id") or ""
        cid = _to_canonical(raw, geoid_index, lookup)
        if cid is not None:
            canonical.setdefault(cid, entry)

    if not canonical:
        return None

    distinct_geoids = {_geoid_of(jid) for jid in canonical}
    if len(distinct_geoids) == 1:
        jid = next(iter(canonical))
        return _build_resolution(
            jid,
            confidence="high",
            method="catalog_single",
            lookup=lookup,
            catalog_fallback=canonical[jid],
        )

    # Multiple distinct geoids. Separate parent containers (county / state) from
    # the local jurisdictions (municipality / township / school_district) they
    # nest. A parent plus exactly ONE local jurisdiction is not ambiguous — the
    # local one is the venue, the parent is just its container ("Howell Township"
    # = Monmouth County + Howell township). Genuinely lossy is a channel spanning
    # several local jurisdictions (regional PEG media: "Town Meeting TV").
    locals_ = [
        jid
        for jid in canonical
        if (lookup[jid].jurisdiction_type if jid in lookup else None)
        not in ("county", "state")
    ]
    local_geoids = {_geoid_of(jid) for jid in locals_}

    if len(local_geoids) == 1:
        jid = locals_[0]
        return _build_resolution(
            jid,
            confidence="medium",
            method="catalog_county_town",
            lookup=lookup,
            catalog_fallback=canonical[jid],
        )

    # Genuine multi-jurisdiction channel: deterministic pick (most specific type,
    # then lowest geoid), preferring local jurisdictions over bare counties.
    def _rank(jid: str) -> tuple:
        jtype = lookup[jid].jurisdiction_type or "" if jid in lookup else ""
        return (_TYPE_SPECIFICITY.get(jtype, 99), _geoid_of(jid) or "")

    candidates = locals_ or list(canonical)
    jid = min(candidates, key=_rank)
    return _build_resolution(
        jid,
        confidence="low",
        method="catalog_multi",
        lookup=lookup,
        catalog_fallback=canonical[jid],
    )


def build_resolutions(
    conn,
) -> Tuple[Dict[str, Resolution], Dict[str, int]]:
    """Resolve every blank ``datasource='youtube'`` video (channel-based or LocalView)."""
    lookup, geoid_index = load_jurisdiction_lookup(conn)
    localview = load_localview_video_map(conn)
    scraped = load_scraped_channel_map(conn)
    catalog = load_catalog_channel_map(conn)

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT y.video_id, y.channel_id
            FROM bronze.bronze_event_youtube y
            WHERE y.datasource = 'youtube'
              AND (y.jurisdiction_id IS NULL OR y.jurisdiction_id = '')
            """
        )
        targets = cur.fetchall()

    # Channel resolutions are cached per distinct channel; LocalView is per video.
    chan_res: Dict[str, Optional[Resolution]] = {}
    out: Dict[str, Resolution] = {}
    stats: Dict[str, int] = defaultdict(int)
    stats["target_videos"] = len(targets)

    for video_id, channel_id in targets:
        # 1. LocalView resolved model (highest trust — materialized geoid match).
        lv_jid = localview.get(video_id)
        if lv_jid:
            res: Optional[Resolution] = _build_resolution(
                lv_jid, confidence="high", method="localview_enriched", lookup=lookup
            )
        else:
            res = None
        # 2. Fall back to the channel-based sources (scraped, then catalog).
        if res is None and channel_id:
            if channel_id not in chan_res:
                if channel_id in scraped:
                    chan_res[channel_id] = _build_resolution(
                        scraped[channel_id],
                        confidence="high",
                        method="scraped",
                        lookup=lookup,
                    )
                elif channel_id in catalog:
                    chan_res[channel_id] = resolve_from_catalog(
                        catalog[channel_id], lookup, geoid_index
                    )
                else:
                    chan_res[channel_id] = None
            res = chan_res[channel_id]

        if res is None:
            stats["unresolved_videos"] += 1
            continue
        out[video_id] = res
        stats[f"conf_{res.confidence}_videos"] += 1
        stats[f"method_{res.method}_videos"] += 1

    stats["resolved_videos"] = len(out)
    stats["distinct_channels"] = len(chan_res)
    stats["resolved_channels"] = sum(1 for r in chan_res.values() if r is not None)
    return out, stats


# ---------------------------------------------------------------------------
# Writeback
# ---------------------------------------------------------------------------


def write_back(
    conn,
    resolutions: Dict[str, Resolution],
    *,
    min_confidence: str,
    dry_run: bool,
) -> Dict[str, int]:
    """Write resolved geo onto the blank ``datasource='youtube'`` rows."""
    from psycopg2.extras import execute_values

    threshold = _CONFIDENCE_ORDER[min_confidence]
    rows = [
        (
            vid,
            r.jurisdiction_id,
            r.jurisdiction_name,
            r.jurisdiction_type,
            r.state_code,
            r.state,
        )
        for vid, r in resolutions.items()
        if _CONFIDENCE_ORDER[r.confidence] >= threshold
    ]
    stats = {"eligible": len(rows), "updated": 0}
    if not rows:
        return stats

    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TEMP TABLE _yt_geo (
                video_id text PRIMARY KEY,
                jurisdiction_id text,
                jurisdiction_name text,
                jurisdiction_type text,
                state_code text,
                state text
            ) ON COMMIT DROP
            """
        )
        execute_values(
            cur,
            """
            INSERT INTO _yt_geo (
                video_id, jurisdiction_id, jurisdiction_name,
                jurisdiction_type, state_code, state
            ) VALUES %s
            ON CONFLICT (video_id) DO NOTHING
            """,
            rows,
        )
        cur.execute(
            """
            UPDATE bronze.bronze_event_youtube y
            SET jurisdiction_id   = g.jurisdiction_id,
                jurisdiction_name = COALESCE(NULLIF(g.jurisdiction_name, ''), y.jurisdiction_name),
                jurisdiction_type = COALESCE(g.jurisdiction_type, y.jurisdiction_type),
                state_code        = COALESCE(g.state_code, y.state_code),
                state             = COALESCE(g.state, y.state),
                last_updated      = CURRENT_TIMESTAMP
            FROM _yt_geo g
            WHERE y.video_id = g.video_id
              AND y.datasource = 'youtube'
              AND (y.jurisdiction_id IS NULL OR y.jurisdiction_id = '')
            """
        )
        stats["updated"] = cur.rowcount

    if dry_run:
        conn.rollback()
        stats["dry_run"] = 1
    else:
        conn.commit()
    return stats


def backfill(
    conn,
    *,
    min_confidence: str = "low",
    dry_run: bool = False,
    sample: int = 0,
) -> Dict[str, int]:
    """Resolve channel→jurisdiction geo and write it onto ``bronze_event_youtube``.

    Importable entry point. Returns merged resolution + writeback stats.
    Idempotent — only blank ``datasource='youtube'`` rows are touched.
    """
    resolutions, stats = build_resolutions(conn)

    logger.info(
        "Targets: {:,} videos — resolved {:,} "
        "({} localview, {} scraped, {} catalog-single, {} catalog-county-town, "
        "{} catalog-multi); {:,} unresolved (no localview row + no channel match)",
        stats["target_videos"],
        stats["resolved_videos"],
        stats.get("method_localview_enriched_videos", 0),
        stats.get("method_scraped_videos", 0),
        stats.get("method_catalog_single_videos", 0),
        stats.get("method_catalog_county_town_videos", 0),
        stats.get("method_catalog_multi_videos", 0),
        stats.get("unresolved_videos", 0),
    )
    logger.info(
        "Confidence: {:,} high, {:,} medium, {:,} low",
        stats.get("conf_high_videos", 0),
        stats.get("conf_medium_videos", 0),
        stats.get("conf_low_videos", 0),
    )
    for vid, r in list(resolutions.items())[: max(0, sample)]:
        logger.info(
            "  {} → {} [{}] {}, {} ({}, {})",
            vid,
            r.jurisdiction_id,
            r.jurisdiction_type,
            r.jurisdiction_name,
            r.state_code,
            r.confidence,
            r.method,
        )

    wstats = write_back(
        conn, resolutions, min_confidence=min_confidence, dry_run=dry_run
    )
    logger.info(
        "{} {:,} eligible (≥{}) → {:,} bronze_event_youtube rows updated",
        "DRY-RUN" if dry_run else "WROTE",
        wstats["eligible"],
        min_confidence,
        wstats["updated"],
    )
    return {**stats, **wstats}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--min-confidence",
        choices=tuple(_CONFIDENCE_ORDER),
        default="low",
        help=(
            "Lowest confidence to write back (default: low — write best match). "
            "high = scraped + single-jurisdiction only; medium = also county+single-town "
            "picks; low = also genuine multi-town channels (one town guessed)."
        ),
    )
    parser.add_argument(
        "--sample",
        type=int,
        default=12,
        help="Print this many example resolutions for eyeballing.",
    )
    args = parser.parse_args()

    db_url = _database_url(args.database_url or None)
    if not db_url:
        raise SystemExit("Set NEON_DATABASE_URL_DEV / DATABASE_URL")

    import psycopg2

    with psycopg2.connect(db_url) as conn:
        backfill(
            conn,
            min_confidence=args.min_confidence,
            dry_run=args.dry_run,
            sample=args.sample,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
