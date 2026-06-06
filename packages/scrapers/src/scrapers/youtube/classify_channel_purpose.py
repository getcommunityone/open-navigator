#!/usr/bin/env python3
"""Classify jurisdiction-stamped YouTube channels as government vs. junk.

A fuzzy channel→jurisdiction matcher (name collisions + fuzzy homepage-link
resolution) has mis-assigned many ENTERTAINMENT / CREATOR channels onto
government meeting feeds — bands (Kittie → Morgan County IN), hunting shows
(The Hunting Public → Double Springs AL), talk shows (The Breakfast Club →
Lauderdale AL), music videos, AMVs, game trailers, real-estate listings. They
then surface in ``public.event_youtube_with_jurisdiction`` as if they were
public-body meetings, and pollute every downstream policy / trending mart.

This module writes one government-vs-junk verdict per ``channel_id`` into
``bronze.bronze_youtube_channel_classification`` (migration 107). The dbt
registry track (``intermediate.int_events_channels_registry``) reads that table
to populate its previously hardcoded-NULL ``is_government`` / ``is_verified``
gate, and the served mart excludes positively-classified junk.

Why video signals, not the channel title: ``bronze_events_channels.channel_title``
is *corrupted for exactly the junk channels* — it stores the jurisdiction code
("c-IN-18109") or place name ("Double Springs") rather than the real channel
name, with NULL view/description. The reliable signal lives at the video level
in the served mart: the per-video ``title`` / ``meeting_type`` / ``view_count``.

Heuristic (sibling of ``enrich_civicsearch_jurisdictions`` — entity judgement in
Python, not dbt):

* ``civic_fraction`` = share of a channel's videos whose ``meeting_type`` is a
  recognised public-body type. A clearly civic channel is GOVERNMENT.
* A channel with **zero** civic-typed videos that also draws big views, or whose
  video titles read as entertainment / commercial, is JUNK.
* Everything in between is left UNDECIDED (``is_government``/``is_junk`` NULL) —
  deliberately, because some zero-civic channels are legit municipal ones that
  post non-meeting content (police PR, public works, city events). Better NULL
  than a wrong purge; an optional ``--llm`` pass adjudicates the middle.

Seeds (``classification_method = 'seed'``) are never downgraded by a weaker
heuristic verdict, so curated known-junk rows survive re-runs.

Usage (repo root)::

    .venv/bin/python packages/scrapers/src/scrapers/youtube/classify_channel_purpose.py --dry-run
    .venv/bin/python packages/scrapers/src/scrapers/youtube/classify_channel_purpose.py
    .venv/bin/python packages/scrapers/src/scrapers/youtube/classify_channel_purpose.py --llm

Configuration: ``NEON_DATABASE_URL_DEV`` / ``NEON_DATABASE_URL`` / ``DATABASE_URL``.
"""

from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence

from dotenv import load_dotenv
from loguru import logger

# packages/scrapers/src/scrapers/youtube/<file> → repo root is 5 levels up.
_REPO_ROOT = Path(__file__).resolve().parents[5]

# --- Decision thresholds -----------------------------------------------------
# A channel publishing this share of recognised public-body meetings is govt.
_CIVIC_GOV_FRACTION = 0.30
# Zero-civic channels need a view spike OR an entertainment-title hit to be
# called junk; below this they stay UNDECIDED (could be a quiet city channel).
_JUNK_MAX_VIEWS = 5000
# A lower view bar applies when the titles themselves read as entertainment.
_JUNK_MAX_VIEWS_WITH_KEYWORD = 1000

# meeting_type values that mark a genuine public-body meeting (word-boundary
# regex; mirrors the dbt gate's civic vocabulary).
_CIVIC_MEETING_RE = re.compile(
    r"council|board|commission|committee|aldermen|selectmen|trustees|"
    r"supervisors|education|zoning|planning|health|town|village|county|"
    r"municipal|workshop|special|school",
    re.IGNORECASE,
)

# Distinctive entertainment / commercial title markers. Kept tight and
# word-boundary-anchored so civic titles ("LIVE City Council") don't trip them —
# e.g. bare "live" is excluded on purpose; "live @"/"live at" is not.
_ENTERTAINMENT_PATTERNS: Sequence[str] = (
    r"official music video",
    r"official video",
    r"official audio",
    r"lyric video",
    r"\bmusic video\b",
    r"\bmixtape\b",
    r"\bamv\b",
    r"\bremix\b",
    r"\bfeat\.",
    r"\bft\.",
    r"live @",
    r"live at ozzfest",
    r"\bozzfest\b",
    r"official trailer",
    r"\bgameplay\b",
    r"\bwalkthrough\b",
    r"\bunboxing\b",
    r"reaction video",
    r"\bvlog\b",
    r"in studio performance",
    r"\btour\b 20",
)
_ENTERTAINMENT_RE = re.compile("|".join(_ENTERTAINMENT_PATTERNS), re.IGNORECASE)

# Obvious non-government broadcasters (channel title OR video titles).
_NEWS_NETWORK_RE = re.compile(
    r"\bcnn\b|fox news|msnbc|\bnbc news\b|\babc news\b|\bcbs news\b|"
    r"the breakfast club|breakfast club",
    re.IGNORECASE,
)


def _database_url(explicit: Optional[str]) -> str:
    # Prefer the repo-root .env; fall back to the default upward search so the
    # CLI works regardless of where it is launched from.
    if not load_dotenv(_REPO_ROOT / ".env"):
        load_dotenv()
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    )


# ---------------------------------------------------------------------------
# Per-channel signal + verdict
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChannelStats:
    """Aggregated signals for one channel, drawn from the served video mart."""

    channel_id: str
    total_videos: int
    civic_videos: int
    max_views: int
    avg_views: float
    sample_titles: List[str]
    channel_title: Optional[str] = None

    @property
    def civic_fraction(self) -> float:
        return civic_fraction(self.civic_videos, self.total_videos)

    @property
    def title_blob(self) -> str:
        parts = list(self.sample_titles)
        if self.channel_title:
            parts.append(self.channel_title)
        return " • ".join(p for p in parts if p)


@dataclass(frozen=True)
class Verdict:
    is_government: Optional[bool]
    is_junk: Optional[bool]
    method: str  # heuristic | llm | seed
    confidence: float
    reason: str

    @property
    def decided(self) -> bool:
        return self.is_government is not None or self.is_junk is not None


def civic_fraction(civic_videos: int, total_videos: int) -> float:
    """Share of a channel's videos that are recognised public-body meetings."""
    if total_videos <= 0:
        return 0.0
    return max(0.0, min(1.0, civic_videos / total_videos))


def is_civic_meeting_type(meeting_type: Optional[str]) -> bool:
    """True when a ``meeting_type`` names a genuine public-body meeting."""
    if not meeting_type:
        return False
    return bool(_CIVIC_MEETING_RE.search(meeting_type))


def entertainment_hits(text: str) -> List[str]:
    """Distinct entertainment / commercial markers found in ``text``."""
    if not text:
        return []
    found = {m.group(0).lower() for m in _ENTERTAINMENT_RE.finditer(text)}
    found.update(m.group(0).lower() for m in _NEWS_NETWORK_RE.finditer(text))
    return sorted(found)


def classify_channel(stats: ChannelStats) -> Verdict:
    """Heuristic government / junk / undecided verdict for one channel.

    Conservative by design: only positively classify the clear cases and leave
    the ambiguous middle UNDECIDED rather than risk purging a real (but quiet,
    non-meeting) municipal channel.
    """
    if stats.total_videos <= 0:
        return Verdict(None, None, "heuristic", 0.0, "no videos")

    frac = stats.civic_fraction
    if frac >= _CIVIC_GOV_FRACTION:
        conf = round(min(0.95, 0.6 + frac / 2), 3)
        return Verdict(
            is_government=True,
            is_junk=False,
            method="heuristic",
            confidence=conf,
            reason=f"civic_fraction={frac:.2f} (>= {_CIVIC_GOV_FRACTION})",
        )

    if stats.civic_videos == 0:
        hits = entertainment_hits(stats.title_blob)
        if hits:
            if stats.max_views >= _JUNK_MAX_VIEWS_WITH_KEYWORD:
                return Verdict(
                    is_government=False,
                    is_junk=True,
                    method="heuristic",
                    confidence=0.9,
                    reason=(
                        "zero-civic + entertainment titles "
                        f"[{', '.join(hits[:3])}] + max_views="
                        f"{stats.max_views}"
                    ),
                )
            # Entertainment-looking but tiny reach: flag low-confidence junk.
            return Verdict(
                is_government=False,
                is_junk=True,
                method="heuristic",
                confidence=0.6,
                reason=f"zero-civic + entertainment titles [{', '.join(hits[:3])}]",
            )
        if stats.max_views >= _JUNK_MAX_VIEWS:
            return Verdict(
                is_government=False,
                is_junk=True,
                method="heuristic",
                confidence=0.8,
                reason=f"zero-civic + max_views={stats.max_views} (>= {_JUNK_MAX_VIEWS})",
            )

    return Verdict(
        is_government=None,
        is_junk=None,
        method="heuristic",
        confidence=0.0,
        reason=f"ambiguous: civic_fraction={frac:.2f}, max_views={stats.max_views}",
    )


# ---------------------------------------------------------------------------
# Data access
# ---------------------------------------------------------------------------


def load_channel_stats(conn, *, sample_titles: int = 30) -> List[ChannelStats]:
    """Aggregate per-channel signals from the UNGATED bronze video table.

    Reads ``bronze.bronze_event_youtube`` rather than the served mart so the
    classifier keeps full visibility of every jurisdiction-stamped channel even
    after the dbt gate has dropped a channel from the served feed (reading the
    gated mart would make already-flagged channels invisible to re-runs).
    """
    from psycopg2.extras import RealDictCursor

    out: List[ChannelStats] = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                y.channel_id,
                COUNT(*) AS total_videos,
                COUNT(*) FILTER (
                    WHERE y.meeting_type ~* %(civic)s
                ) AS civic_videos,
                COALESCE(MAX(y.view_count), 0) AS max_views,
                COALESCE(AVG(y.view_count), 0)::float8 AS avg_views,
                (ARRAY_AGG(
                    y.title ORDER BY y.view_count DESC NULLS LAST
                ))[1:%(n)s] AS sample_titles,
                MAX(bc.channel_title) AS channel_title
            FROM bronze.bronze_event_youtube y
            LEFT JOIN bronze.bronze_events_channels bc
                   ON bc.channel_id = y.channel_id
            WHERE y.channel_id IS NOT NULL AND y.channel_id <> ''
            GROUP BY y.channel_id
            """,
            {"civic": _CIVIC_MEETING_RE.pattern, "n": sample_titles},
        )
        for row in cur.fetchall():
            titles = [t for t in (row["sample_titles"] or []) if t]
            out.append(
                ChannelStats(
                    channel_id=row["channel_id"],
                    total_videos=int(row["total_videos"]),
                    civic_videos=int(row["civic_videos"]),
                    max_views=int(row["max_views"]),
                    avg_views=float(row["avg_views"]),
                    sample_titles=titles,
                    channel_title=row["channel_title"],
                )
            )
    logger.info("Loaded signals for {:,} channels", len(out))
    return out


def load_seed_channels(conn) -> set[str]:
    """Channel ids carrying a curated seed verdict (``seed`` / ``manual_seed``)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT channel_id
            FROM bronze.bronze_youtube_channel_classification
            WHERE classification_method LIKE '%%seed%%'
            """
        )
        return {r[0] for r in cur.fetchall()}


def write_back(
    conn,
    verdicts: Dict[str, Verdict],
    *,
    preserve: set[str],
    dry_run: bool,
) -> Dict[str, int]:
    """Upsert verdicts; never downgrade a preserved (seed) channel."""
    from psycopg2.extras import execute_values

    rows = [
        (
            cid,
            v.is_government,
            v.is_junk,
            v.reason,
            v.method,
            v.confidence,
        )
        for cid, v in verdicts.items()
        if cid not in preserve
    ]
    stats = {"eligible": len(rows), "written": 0}
    if not rows:
        return stats

    with conn.cursor() as cur:
        execute_values(
            cur,
            """
            INSERT INTO bronze.bronze_youtube_channel_classification (
                channel_id, is_government, is_junk,
                flag_reason, classification_method, confidence
            ) VALUES %s
            ON CONFLICT (channel_id) DO UPDATE SET
                is_government        = EXCLUDED.is_government,
                is_junk              = EXCLUDED.is_junk,
                flag_reason          = EXCLUDED.flag_reason,
                classification_method = EXCLUDED.classification_method,
                confidence           = EXCLUDED.confidence,
                classified_at        = now()
            WHERE bronze_youtube_channel_classification.classification_method
                  NOT LIKE '%%seed%%'
            """,
            rows,
        )
        # execute_values reports only the last page's rowcount; count eligible
        # rows for an accurate written total instead.
        stats["written"] = len(rows)

    if dry_run:
        conn.rollback()
        stats["dry_run"] = 1
    else:
        conn.commit()
    return stats


# ---------------------------------------------------------------------------
# Optional LLM adjudication of the undecided middle
# ---------------------------------------------------------------------------


def _llm_verdict(stats: ChannelStats) -> Optional[Verdict]:
    """Ask the repo Gemini client whether an ambiguous channel is government.

    Returns None (leaving the channel UNDECIDED) when no client / API key is
    available, or on any error — the heuristic path must work standalone.
    """
    try:
        from llm.gemini.client import generate_text  # type: ignore
    except Exception:  # pragma: no cover - optional dependency / wiring
        try:
            from llm.gemini import generate_text  # type: ignore
        except Exception:
            logger.warning("No Gemini client available; skipping LLM pass")
            return None

    titles = "\n".join(f"- {t}" for t in stats.sample_titles[:20])
    prompt = (
        "You judge whether a YouTube channel belongs to an official US local "
        "government / public body (city, county, school district, council, "
        "board) versus a non-government channel (entertainment, music, sports, "
        "news network, business, personal).\n"
        f"Channel title (may be unreliable): {stats.channel_title!r}\n"
        f"Total videos: {stats.total_videos}; max views: {stats.max_views}\n"
        f"Recent video titles:\n{titles}\n\n"
        "Answer with exactly one word: gov, nongov, or unsure."
    )
    try:
        raw = (generate_text(prompt) or "").strip().lower()  # type: ignore
    except Exception as err:  # pragma: no cover - network/runtime
        logger.warning("LLM call failed for {}: {}", stats.channel_id, err)
        return None

    answer = raw.split()[0] if raw else ""
    if answer.startswith("gov"):
        return Verdict(True, False, "llm", 0.7, "llm: gov")
    if answer.startswith("nongov"):
        return Verdict(False, True, "llm", 0.7, "llm: nongov")
    return None


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def classify(
    conn,
    *,
    dry_run: bool = False,
    use_llm: bool = False,
    sample_titles: int = 30,
) -> Dict[str, int]:
    """Classify every served channel and upsert verdicts. Returns run stats."""
    seeds = load_seed_channels(conn)
    channels = load_channel_stats(conn, sample_titles=sample_titles)

    verdicts: Dict[str, Verdict] = {}
    counts: Dict[str, int] = defaultdict(int)
    undecided: List[ChannelStats] = []

    for c in channels:
        v = classify_channel(c)
        verdicts[c.channel_id] = v
        if v.is_government:
            counts["government"] += 1
        elif v.is_junk:
            counts["junk"] += 1
        else:
            counts["undecided"] += 1
            undecided.append(c)

    counts["seeds_preserved"] = len(seeds & {c.channel_id for c in channels})

    if use_llm and undecided:
        logger.info("LLM-adjudicating {:,} undecided channels", len(undecided))
        for c in undecided:
            lv = _llm_verdict(c)
            if lv is None:
                continue
            verdicts[c.channel_id] = lv
            counts["undecided"] -= 1
            counts["llm_gov" if lv.is_government else "llm_junk"] += 1

    logger.info(
        "Heuristic verdicts: {:,} government, {:,} junk, {:,} undecided "
        "({} seeds preserved)",
        counts["government"],
        counts["junk"],
        counts["undecided"],
        counts["seeds_preserved"],
    )

    wstats = write_back(conn, verdicts, preserve=seeds, dry_run=dry_run)
    logger.info(
        "{} {:,} channel verdicts ({:,} eligible, excl. {} seeds)",
        "DRY-RUN" if dry_run else "WROTE",
        wstats["written"],
        wstats["eligible"],
        len(seeds),
    )
    return {**counts, **wstats}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--llm",
        action="store_true",
        help="Adjudicate the undecided middle with the Gemini client (opt-in).",
    )
    parser.add_argument(
        "--sample-titles",
        type=int,
        default=30,
        help="How many top-viewed video titles to feed the heuristic / LLM.",
    )
    args = parser.parse_args()

    db_url = _database_url(args.database_url or None)
    if not db_url:
        raise SystemExit("Set NEON_DATABASE_URL_DEV / DATABASE_URL")

    import psycopg2

    with psycopg2.connect(db_url) as conn:
        classify(
            conn,
            dry_run=args.dry_run,
            use_llm=args.llm,
            sample_titles=args.sample_titles,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
