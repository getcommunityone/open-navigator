#!/usr/bin/env python3
"""Repair jurisdiction tags on ``bronze.bronze_event_youtube``.

Two channel-name-collision data-quality problems are fixed here, in order, in a
single idempotent pass:

PART A — *remove false-positive jurisdiction tags*.
    YouTube channel discovery matched channels to jurisdictions by bare name, so
    entertainment / personal channels whose name collides with a county or city
    word got tagged with a real ``jurisdiction_id`` (the archetype: the iHeart
    radio show *The Breakfast Club*, channel ``UChi08h4577eFsNXGd3sxYhw``, with
    99 rows all tagged ``lauderdale_01077``). We NULL the jurisdiction columns
    (``jurisdiction_id/name/type`` plus the derived ``city/state/state_code``)
    for **high-confidence non-civic channels** only. The rule is deliberately
    conservative — when in doubt we LEAVE the tag (prefer false-negatives over
    wiping a real meeting):

    A channel is cleared when ALL of:
      * NONE of its tagged rows' titles contain a governance keyword (a strict,
        whole-word / phrase vocabulary — ``city council``, ``fiscal court``,
        ``planning commission``, ``fire department`` … — not loose single words
        like "fire"/"mayor" that match celebrity-news headlines), AND
      * the channel never carries an authoritative ``channel_type``
        (``OFFICIAL GOVT`` / ``municipal`` / ``municipality``) — that signal
        protects genuine government departments whose titles happen to be all
        incident reports (e.g. Mesa Fire & Medical), AND
      * the channel's titles are not *all* bare dates (those plausibly are real
        untitled meeting recordings).

PART B — *backfill missing jurisdiction* (rows with NULL ``jurisdiction_id``).
    TIER 1 — channel propagation: for a channel with EXACTLY ONE distinct
        non-null ``jurisdiction_id`` among its (post-Part-A) tagged rows, copy
        that jurisdiction onto the channel's NULL rows. Non-civic channels
        cleared in Part A are skipped on BOTH sides of the propagation.
    TIER 2/3 — per-row title matching: parse a municipality + civic-body out of
        the title ("Cookeville City Council Meeting May 01, 2014" → Cookeville)
        and resolve it against ``intermediate.int_jurisdictions`` by name **and
        a corroborating state** (the channel's sibling-row state). Re-uses the
        battle-tested resolver in ``enrich_civicsearch_jurisdictions``. Ambiguous
        name+state matches are logged and skipped — never guessed (a bare-name
        match once mapped a channel to "Hollywood, AL" wrongly).

Every write is idempotent: Part A only NULLs rows that still carry a tag, Tier 1
only fills NULL rows, and Tier 2/3 only fills NULL rows. A second run changes 0
rows.

Usage (repo root)::

    .venv/bin/python -m scrapers.youtube.clean_jurisdiction_tags --dry-run
    .venv/bin/python -m scrapers.youtube.clean_jurisdiction_tags
    .venv/bin/python -m scrapers.youtube.clean_jurisdiction_tags --skip-backfill

Configuration: ``NEON_DATABASE_URL_DEV`` / ``NEON_DATABASE_URL`` / ``DATABASE_URL``.
"""

from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv
from loguru import logger

from scrapers.youtube.enrich_civicsearch_jurisdictions import (
    Jurisdiction,
    load_jurisdictions,
    resolve_place,
)

def _find_dotenv() -> Optional[Path]:
    """Walk up from this file to the repo root that holds ``.env``."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / ".env"
        if candidate.exists():
            return candidate
    return None


def _database_url(explicit: Optional[str]) -> str:
    dotenv = _find_dotenv()
    if dotenv is not None:
        load_dotenv(dotenv)
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    )


# ---------------------------------------------------------------------------
# PART A — non-civic channel detection
# ---------------------------------------------------------------------------

# Strict governance vocabulary. Single bare words ("fire", "mayor", "water")
# are intentionally EXCLUDED — they match entertainment headlines ("On Fire",
# "Mayor Baraka talks Trump", "water resistant"). Only governance-specific
# whole words and multi-word phrases count as a civic signal.
_CIVIC_WORD = re.compile(
    r"\b("
    r"council|commission|committee|aldermen|alderman|trustee|trustees|"
    r"zoning|legislature|legislative|selectboard"
    r")\b",
    re.IGNORECASE,
)
_CIVIC_PHRASE = re.compile(
    r"("
    r"city council|county council|county commission|county board|"
    r"board of supervisors|board of commissioners|planning commission|"
    r"city of |town of |village of |township of |borough of |town hall|"
    r"select board|public hearing|public comment|regular meeting|"
    r"special meeting|special session|work session|committee of the whole|"
    r"board meeting|council meeting|commission meeting|fire department|"
    r"police department|sheriff.s office|school board|city hall|water board|"
    r"utility board|board of education|fiscal court|water treatment|"
    r"wastewater|treatment plant"
    r")",
    re.IGNORECASE,
)

# A title that is *only* a bare date — e.g. "January 1, 2023", "11-13-18",
# "21 09 09". Such channels are protected (could be untitled meeting uploads).
_BARE_DATE = re.compile(
    r"^("
    r"[A-Z][a-z]+ [0-9]{1,2},? *[0-9]{4}"  # January 1, 2023
    r"|[0-9]{1,4}[-/. ][0-9]{1,2}[-/. ][0-9]{1,4}"  # 11-13-18 / 2023.05.01
    r")$"
)

# Authoritative channel_type values that designate a real government channel.
_OFFICIAL_TYPES = frozenset({"OFFICIAL GOVT", "municipal", "municipality"})


def is_civic_title(title: str) -> bool:
    """True if a single title carries a governance signal."""
    t = title or ""
    return bool(_CIVIC_WORD.search(t) or _CIVIC_PHRASE.search(t))


def is_bare_date_title(title: str) -> bool:
    return bool(_BARE_DATE.match((title or "").strip()))


@dataclass
class ChannelProfile:
    channel_id: str
    tagged_rows: int
    any_civic: bool
    all_dates: bool
    has_official_type: bool

    @property
    def is_non_civic(self) -> bool:
        """High-confidence non-civic: no civic keyword anywhere, no official
        channel_type, and titles are not all bare dates."""
        return (
            not self.any_civic
            and not self.has_official_type
            and not self.all_dates
        )


def profile_tagged_channels(conn) -> Dict[str, ChannelProfile]:
    """Build a Part-A profile for every channel that has >=1 tagged row.

    Computed in Python (not SQL) so the civic vocabulary lives in one place and
    is unit-testable. Only currently-tagged rows define a channel's civic-ness.
    """
    from psycopg2.extras import RealDictCursor

    acc: Dict[str, Dict] = {}
    with conn.cursor(name="profile_cur", cursor_factory=RealDictCursor) as cur:
        cur.itersize = 10000
        cur.execute(
            """
            SELECT channel_id, title, channel_type
            FROM bronze.bronze_event_youtube
            WHERE jurisdiction_id IS NOT NULL
              AND channel_id IS NOT NULL
            """
        )
        for row in cur:
            cid = row["channel_id"]
            p = acc.get(cid)
            if p is None:
                p = acc[cid] = {
                    "n": 0,
                    "any_civic": False,
                    "all_dates": True,
                    "official": False,
                }
            p["n"] += 1
            title = row["title"] or ""
            if is_civic_title(title):
                p["any_civic"] = True
            if not is_bare_date_title(title):
                p["all_dates"] = False
            if (row["channel_type"] or "") in _OFFICIAL_TYPES:
                p["official"] = True

    profiles = {
        cid: ChannelProfile(
            channel_id=cid,
            tagged_rows=p["n"],
            any_civic=p["any_civic"],
            all_dates=p["all_dates"],
            has_official_type=p["official"],
        )
        for cid, p in acc.items()
    }
    logger.info("Profiled {:,} tagged channels", len(profiles))
    return profiles


def clear_non_civic_tags(
    conn, profiles: Dict[str, ChannelProfile], *, dry_run: bool
) -> Dict[str, int]:
    """NULL jurisdiction columns for every high-confidence non-civic channel."""
    from psycopg2.extras import execute_values

    non_civic = [p.channel_id for p in profiles.values() if p.is_non_civic]
    stats = {
        "non_civic_channels": len(non_civic),
        "rows_cleared": 0,
    }
    if not non_civic:
        return stats

    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE _noncivic (channel_id text PRIMARY KEY) "
            "ON COMMIT DROP"
        )
        execute_values(
            cur,
            "INSERT INTO _noncivic (channel_id) VALUES %s "
            "ON CONFLICT DO NOTHING",
            [(c,) for c in non_civic],
        )
        # Idempotent: only rows still carrying a tag are touched.
        cur.execute(
            """
            UPDATE bronze.bronze_event_youtube y
            SET jurisdiction_id   = NULL,
                jurisdiction_name = NULL,
                jurisdiction_type = NULL,
                city              = NULL,
                state             = NULL,
                state_code        = NULL,
                last_updated      = CURRENT_TIMESTAMP
            FROM _noncivic n
            WHERE y.channel_id = n.channel_id
              AND y.jurisdiction_id IS NOT NULL
            """
        )
        stats["rows_cleared"] = cur.rowcount
    return stats


# ---------------------------------------------------------------------------
# PART B / TIER 1 — channel propagation
# ---------------------------------------------------------------------------


def tier1_channel_propagation(
    conn, non_civic_channels: frozenset[str], *, dry_run: bool
) -> Dict[str, int]:
    """Fill NULL rows from a channel's single distinct jurisdiction.

    Operates on the CURRENT (post-Part-A) table state, so any tag cleared in
    Part A no longer contributes a distinct jurisdiction here. Non-civic
    channels are excluded entirely — never propagated to or from.
    """
    from psycopg2.extras import execute_values

    with conn.cursor() as cur:
        cur.execute(
            "CREATE TEMP TABLE _nc (channel_id text PRIMARY KEY) ON COMMIT DROP"
        )
        if non_civic_channels:
            execute_values(
                cur,
                "INSERT INTO _nc (channel_id) VALUES %s ON CONFLICT DO NOTHING",
                [(c,) for c in non_civic_channels],
            )
        # Channels with exactly one distinct non-null jurisdiction_id, not flagged
        # non-civic, that also have >=1 NULL row to fill.
        cur.execute(
            """
            CREATE TEMP TABLE _tier1 ON COMMIT DROP AS
            WITH chan AS (
                SELECT y.channel_id,
                       count(DISTINCT y.jurisdiction_id)
                           FILTER (WHERE y.jurisdiction_id IS NOT NULL) AS distinct_jid,
                       count(*) FILTER (WHERE y.jurisdiction_id IS NULL) AS missing
                FROM bronze.bronze_event_youtube y
                WHERE y.channel_id IS NOT NULL
                  AND NOT EXISTS (SELECT 1 FROM _nc n WHERE n.channel_id = y.channel_id)
                GROUP BY y.channel_id
                HAVING count(DISTINCT y.jurisdiction_id)
                           FILTER (WHERE y.jurisdiction_id IS NOT NULL) = 1
                   AND count(*) FILTER (WHERE y.jurisdiction_id IS NULL) > 0
            )
            SELECT DISTINCT ON (s.channel_id)
                   s.channel_id,
                   s.jurisdiction_id, s.jurisdiction_name, s.jurisdiction_type,
                   s.city, s.state, s.state_code
            FROM bronze.bronze_event_youtube s
            JOIN chan USING (channel_id)
            WHERE s.jurisdiction_id IS NOT NULL
            """
        )
        cur.execute("SELECT count(*) FROM _tier1")
        channels = cur.fetchone()[0]

        cur.execute(
            """
            UPDATE bronze.bronze_event_youtube y
            SET jurisdiction_id   = t.jurisdiction_id,
                jurisdiction_name = t.jurisdiction_name,
                jurisdiction_type = t.jurisdiction_type,
                city              = COALESCE(NULLIF(y.city, ''), t.city),
                state             = COALESCE(NULLIF(y.state, ''), t.state),
                state_code        = COALESCE(NULLIF(y.state_code, ''), t.state_code),
                last_updated      = CURRENT_TIMESTAMP
            FROM _tier1 t
            WHERE y.channel_id = t.channel_id
              AND y.jurisdiction_id IS NULL
            """
        )
        return {"tier1_channels": channels, "tier1_rows_filled": cur.rowcount}


# ---------------------------------------------------------------------------
# PART B / TIER 2-3 — per-row title matching
# ---------------------------------------------------------------------------

# Extract a municipality name from a meeting title. Two shapes cover the corpus:
#   "<Place> City Council ..."   /  "<Place> Town Council ..." / "Village Board"
#   "City of <Place> ..."        /  "Town of <Place> ..."      / "County of ..."
_TITLE_PREFIX = re.compile(
    r"^(?:\d[\d\s/.\-]*[-\s]+)?"  # optional leading date "2011-11-01 - "
    r"(?P<place>[A-Z][A-Za-z.'’\-]+(?: [A-Z][A-Za-z.'’\-]+){0,3}?)"
    r"\s+(?:city council|town council|village board|township board|"
    r"city commission|county commission|board of supervisors|"
    r"board of commissioners|fiscal court|city of|town of)\b",
    re.IGNORECASE,
)
_TITLE_OF = re.compile(
    r"\b(?:city|town|village|township|county) of\s+"
    r"(?P<place>[A-Z][A-Za-z.'’\-]+(?: [A-Z][A-Za-z.'’\-]+){0,3}?)"
    r"(?=[,\-–:]|\s+(?:city|council|commission|board|meeting|special|"
    r"regular|work|planning|session|mo\b|[A-Z]{2}\b)|$)",
    re.IGNORECASE,
)


# Full US state names → 2-letter codes. Used to (a) trim a state name the place
# regex greedily swallowed ("Omaha Nebraska" → place "Omaha" + state "NE", so it
# never mis-resolves to "Nebraska City") and (b) recover a title-local state
# corroborant when the row/channel has none.
_US_STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new hampshire": "NH", "new jersey": "NJ",
    "new mexico": "NM", "new york": "NY", "north carolina": "NC",
    "north dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
    "district of columbia": "DC",
}


def _split_trailing_state(place: str) -> Tuple[str, Optional[str]]:
    """Strip a trailing US state name/2-letter code from a parsed place name.

    Returns ``(clean_place, state_code_or_None)``. "Omaha Nebraska" → ("Omaha",
    "NE"); "Springfield" → ("Springfield", None).
    """
    toks = place.split()
    # Two-word state names first ("new jersey", "west virginia").
    if len(toks) >= 3:
        two = " ".join(toks[-2:]).lower()
        if two in _US_STATE_NAMES:
            return " ".join(toks[:-2]), _US_STATE_NAMES[two]
    if len(toks) >= 2:
        one = toks[-1].lower()
        if one in _US_STATE_NAMES:
            return " ".join(toks[:-1]), _US_STATE_NAMES[one]
        if len(toks[-1]) == 2 and toks[-1].upper() in set(_US_STATE_NAMES.values()):
            return " ".join(toks[:-1]), toks[-1].upper()
    return place, None


def parse_title_place(title: str) -> Tuple[Optional[str], Optional[str]]:
    """Pull a ``(place, state_code)`` pair out of a meeting title.

    ``state_code`` is non-None only when the title itself names the state (a safe
    title-local corroborant). Either element may be None.
    """
    t = (title or "").strip()
    if not t:
        return None, None
    m = _TITLE_OF.search(t)
    if not m:
        m = _TITLE_PREFIX.match(t)
    if not m:
        return None, None
    place, state = _split_trailing_state(m.group("place").strip())
    return (place or None), state


@dataclass
class _MissingRow:
    video_id: str
    channel_id: str
    title: str
    state_code: Optional[str]


def _channel_state(conn) -> Dict[str, str]:
    """Map channel_id → its corroborating state_code (the modal non-null state
    among the channel's rows). Used as the Tier 2/3 collision guard: a title
    name is only resolved within this state."""
    states: Dict[str, str] = {}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT channel_id, state_code
            FROM (
                SELECT channel_id, state_code,
                       row_number() OVER (
                           PARTITION BY channel_id
                           ORDER BY count(*) DESC, state_code
                       ) rn
                FROM bronze.bronze_event_youtube
                WHERE channel_id IS NOT NULL AND state_code IS NOT NULL
                GROUP BY channel_id, state_code
            ) q
            WHERE rn = 1
            """
        )
        for cid, sc in cur.fetchall():
            states[cid] = (sc or "").strip().upper()
    return states


def tier23_title_matching(
    conn,
    by_state: Dict[str, List[Jurisdiction]],
    non_civic_channels: frozenset[str],
    *,
    dry_run: bool,
) -> Dict[str, int]:
    """Resolve still-missing rows by parsing the title + a corroborating state.

    A match is accepted only when the parsed place resolves to a single
    jurisdiction within the channel's corroborating state at HIGH confidence
    (exact / containment name agreement). Anything weaker is logged and left
    unresolved — we never guess across a state collision.
    """
    from psycopg2.extras import RealDictCursor, execute_values

    chan_state = _channel_state(conn)

    rows: List[_MissingRow] = []
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT video_id, channel_id, title, state_code
            FROM bronze.bronze_event_youtube
            WHERE jurisdiction_id IS NULL
              AND video_id IS NOT NULL
            """
        )
        for r in cur.fetchall():
            rows.append(
                _MissingRow(
                    video_id=r["video_id"],
                    channel_id=r["channel_id"],
                    title=r["title"] or "",
                    state_code=(r["state_code"] or None),
                )
            )

    stats = defaultdict(int)
    stats["candidates"] = len(rows)
    updates: List[Tuple] = []
    # Cache (place_lower, state_code) → resolution to avoid rework.
    cache: Dict[Tuple[str, str], Optional[object]] = {}

    for r in rows:
        if r.channel_id in non_civic_channels:
            stats["skipped_non_civic"] += 1
            continue
        place, title_state = parse_title_place(r.title)
        if not place:
            stats["no_place_parsed"] += 1
            continue
        # State corroborant precedence: the channel's own state (row/sibling)
        # first, then the state named in the title itself. Cross-check: if BOTH
        # exist and disagree, skip — that is a collision signal, never guess.
        chan_sc = (
            r.state_code or chan_state.get(r.channel_id) or ""
        ).strip().upper()
        if chan_sc and title_state and chan_sc != title_state:
            stats["state_conflict"] += 1
            continue
        sc = chan_sc or (title_state or "")
        if not sc:
            stats["no_state_corroborant"] += 1
            continue

        key = (place.lower(), sc)
        if key not in cache:
            # No lat/lon for title rows → pure name+state resolution.
            cache[key] = resolve_place(
                place, sc, None, None, is_school=False, by_state=by_state
            )
        res = cache[key]
        if res is None:
            stats["unresolved"] += 1
            continue
        # Collision guard: only accept unambiguous high-confidence name hits.
        if res.confidence != "high":
            stats["rejected_low_conf"] += 1
            continue
        stats["matched"] += 1
        updates.append(
            (
                r.video_id,
                res.jurisdiction_id,
                res.jurisdiction_name,
                res.jurisdiction_type,
                place,
                res.state,
                res.state_code,
            )
        )

    if updates:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TEMP TABLE _tier23 (
                    video_id text PRIMARY KEY,
                    jurisdiction_id text, jurisdiction_name text,
                    jurisdiction_type text, city text, state text, state_code text
                ) ON COMMIT DROP
                """
            )
            execute_values(
                cur,
                """
                INSERT INTO _tier23 (video_id, jurisdiction_id, jurisdiction_name,
                    jurisdiction_type, city, state, state_code) VALUES %s
                ON CONFLICT (video_id) DO NOTHING
                """,
                updates,
            )
            cur.execute(
                """
                UPDATE bronze.bronze_event_youtube y
                SET jurisdiction_id   = t.jurisdiction_id,
                    jurisdiction_name = t.jurisdiction_name,
                    jurisdiction_type = t.jurisdiction_type,
                    city              = COALESCE(NULLIF(y.city, ''), t.city),
                    state             = COALESCE(NULLIF(y.state, ''), t.state),
                    state_code        = COALESCE(NULLIF(y.state_code, ''), t.state_code),
                    last_updated      = CURRENT_TIMESTAMP
                FROM _tier23 t
                WHERE y.video_id = t.video_id
                  AND y.jurisdiction_id IS NULL
                """
            )
            stats["tier23_rows_filled"] = cur.rowcount
    return dict(stats)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run(
    conn,
    *,
    dry_run: bool = False,
    skip_cleanup: bool = False,
    skip_backfill: bool = False,
) -> Dict[str, int]:
    """Run Part A then Part B in one transaction. Returns merged stats."""
    result: Dict[str, int] = {}

    profiles = profile_tagged_channels(conn)
    non_civic = frozenset(p.channel_id for p in profiles.values() if p.is_non_civic)

    if not skip_cleanup:
        a = clear_non_civic_tags(conn, profiles, dry_run=dry_run)
        result.update(a)
        logger.info(
            "PART A: cleared {:,} rows across {} non-civic channels",
            a["rows_cleared"],
            a["non_civic_channels"],
        )

    if not skip_backfill:
        t1 = tier1_channel_propagation(conn, non_civic, dry_run=dry_run)
        result.update(t1)
        logger.info(
            "TIER 1: filled {:,} rows across {} single-jurisdiction channels",
            t1["tier1_rows_filled"],
            t1["tier1_channels"],
        )

        by_state, _ = load_jurisdictions(conn)
        t23 = tier23_title_matching(conn, by_state, non_civic, dry_run=dry_run)
        result.update(t23)
        logger.info(
            "TIER 2/3: matched {:,} rows (filled {:,}); "
            "{:,} no-place, {:,} no-state, {:,} unresolved, {:,} low-conf",
            t23.get("matched", 0),
            t23.get("tier23_rows_filled", 0),
            t23.get("no_place_parsed", 0),
            t23.get("no_state_corroborant", 0),
            t23.get("unresolved", 0),
            t23.get("rejected_low_conf", 0),
        )

    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM bronze.bronze_event_youtube "
            "WHERE jurisdiction_id IS NULL"
        )
        result["still_missing"] = cur.fetchone()[0]

    if dry_run:
        conn.rollback()
        result["dry_run"] = 1
        logger.warning("DRY-RUN: rolled back, no changes persisted")
    else:
        conn.commit()
        logger.success(
            "Committed. {:,} rows still missing jurisdiction_id",
            result["still_missing"],
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--skip-cleanup", action="store_true", help="Skip Part A."
    )
    parser.add_argument(
        "--skip-backfill", action="store_true", help="Skip Part B."
    )
    args = parser.parse_args()

    db_url = _database_url(args.database_url or None)
    if not db_url:
        raise SystemExit("Set NEON_DATABASE_URL_DEV / DATABASE_URL")

    import psycopg2

    with psycopg2.connect(db_url) as conn:
        run(
            conn,
            dry_run=args.dry_run,
            skip_cleanup=args.skip_cleanup,
            skip_backfill=args.skip_backfill,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
