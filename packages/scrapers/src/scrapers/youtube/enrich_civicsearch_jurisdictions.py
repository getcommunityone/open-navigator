#!/usr/bin/env python3
"""Resolve and backfill jurisdiction geo for CivicSearch rows in ``bronze_event_youtube``.

CivicSearch meetings were promoted into ``bronze.bronze_event_youtube`` (migration
103) **without** any jurisdiction resolution — every ``datasource = 'civicsearch'``
row has a NULL ``jurisdiction_id`` / ``jurisdiction_name`` and ~46% have a NULL
``state_code``. That makes the transcript-backfill log read ``None, None - …`` and
starves every downstream consumer that keys off ``bronze_event_youtube`` geo (the
analyze/report batch jobs and the Gemini transcript-policy cache folder naming).

The raw CivicSearch landing tables DO carry enough to resolve geo:
``bronze.bronze_events_civicsearch`` (general / cities portal) and
``bronze.bronze_events_civicsearch_schools`` (school-district portal) both expose
a ``location`` string ("Johnson City, TN", "Austin Isd, Texas",
"New Haven School District, Connecticut") plus a place centroid
(``place_lat`` / ``place_lon``). This module joins those back to the canonical
``intermediate.int_jurisdictions`` reference and writes the resolved geo onto the
matching ``bronze_event_youtube`` rows (``video_id == vid_id``).

Matching strategy (a sibling of ``normalize_youtube_jurisdiction_ids`` — fuzzy
entity resolution lives in Python here, not in dbt):

* Parse ``location`` into a place name + a trailing state/province token.
* Resolve ``state_code`` — 2-letter US codes pass through; full US names map via
  ``int_jurisdictions`` (type ``state``). Canadian provinces have no US match and
  are left unresolved on purpose (CivicSearch indexes Canadian councils too).
* Score in-state candidates by **core-name token agreement first, lat/lon
  distance as the tiebreak** — pure nearest-centroid alone mis-picks large
  districts (e.g. "Austin Isd" sits closer to Eanes ISD's centroid than to
  Austin ISD's). The schools portal prefers ``school_district`` jurisdictions;
  the cities portal prefers municipality → township → county.
* Each resolution carries a ``confidence`` (high / medium / low) so low-confidence
  (lat/lon-only) picks can be audited or withheld via ``--min-confidence``.

Usage (repo root)::

    .venv/bin/python packages/scrapers/src/scrapers/youtube/enrich_civicsearch_jurisdictions.py --dry-run
    .venv/bin/python packages/scrapers/src/scrapers/youtube/enrich_civicsearch_jurisdictions.py
    .venv/bin/python packages/scrapers/src/scrapers/youtube/enrich_civicsearch_jurisdictions.py --min-confidence medium

Configuration: ``NEON_DATABASE_URL_DEV`` / ``NEON_DATABASE_URL`` / ``DATABASE_URL``.
"""

from __future__ import annotations

import argparse
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from dotenv import load_dotenv
from loguru import logger

_REPO_ROOT = Path(__file__).resolve().parents[3]

# Confidence ranks, lowest → highest, for --min-confidence gating.
_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}

# Candidate jurisdiction types by CivicSearch portal, in preference order. A
# row's portal is decided by which landing table its vid_id came from.
_CITY_TYPES = ("municipality", "township", "county")
_SCHOOL_TYPES = ("school_district",)

# Trailing legal-status words stripped from municipal / county / township names
# on both sides before comparison ("Johnson City" ~ "Johnson", "X County" ~ "X").
_PLACE_SUFFIXES = (
    "city",
    "town",
    "village",
    "borough",
    "township",
    "county",
    "parish",
    "ccd",
)

# School-district name noise dropped from BOTH the CivicSearch label and the NCES
# name so the geographic core survives ("Austin Isd" ~ "Austin Independent
# School District" → {austin}; "Sacramento City Unified" ~ "Sacramento City
# Unified School District" → {sacramento, city}).
_SCHOOL_STOPWORDS = frozenset(
    {
        "independent",
        "unified",
        "consolidated",
        "community",
        "public",
        "school",
        "schools",
        "district",
        "isd",
        "sd",
        "usd",
        "cusd",
        "cisd",
        "corporation",
        "corp",
        "area",
        "joint",
        "regional",
        "cooperative",
        "coop",
        "unit",
        "board",
        "education",
        "dist",
        "no",
        "number",
        "the",
        "of",
    }
)

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _database_url(explicit: Optional[str]) -> str:
    load_dotenv(_REPO_ROOT / ".env")
    return (
        explicit
        or os.getenv("NEON_DATABASE_URL_DEV")
        or os.getenv("NEON_DATABASE_URL")
        or os.getenv("DATABASE_URL")
        or ""
    )


# ---------------------------------------------------------------------------
# Parsing & normalization
# ---------------------------------------------------------------------------


def parse_location(location: str) -> Tuple[str, str]:
    """Split a CivicSearch ``location`` into ``(place, state_token)``.

    State is the segment after the LAST comma so place names that contain a comma
    survive ("Winston-Salem, NC" → ("Winston-Salem", "NC")).
    """
    s = (location or "").strip()
    if "," not in s:
        return s, ""
    place, _, tail = s.rpartition(",")
    return place.strip(), tail.strip()


def _tokens(name: str) -> List[str]:
    return [t for t in _NON_ALNUM.split((name or "").lower()) if t]


def core_tokens(name: str, *, is_school: bool) -> frozenset[str]:
    """Reduce a name to its geographic core token set for comparison."""
    toks = _tokens(name)
    if is_school:
        core = [t for t in toks if t not in _SCHOOL_STOPWORDS]
    else:
        # Strip a single trailing legal-status word ("… County", "… city").
        if toks and toks[-1] in _PLACE_SUFFIXES:
            toks = toks[:-1]
        core = toks
    return frozenset(core or toks)


def _name_score(place_core: frozenset[str], cand_core: frozenset[str]) -> float:
    """Token agreement in [0, 1]: exact set = 1.0, subset strong, Jaccard else."""
    if not place_core or not cand_core:
        return 0.0
    if place_core == cand_core:
        return 1.0
    inter = place_core & cand_core
    if not inter:
        return 0.0
    if place_core <= cand_core or cand_core <= place_core:
        # One name fully contains the other's core (e.g. {austin} ⊆ {austin}).
        return 0.9
    return len(inter) / len(place_core | cand_core)


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    )
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Jurisdiction:
    jurisdiction_id: str
    name: str
    jurisdiction_type: str
    state_code: str
    state: str
    latitude: Optional[float]
    longitude: Optional[float]
    core_place: frozenset[str]
    core_school: frozenset[str]

    def core(self, *, is_school: bool) -> frozenset[str]:
        return self.core_school if is_school else self.core_place


def load_jurisdictions(
    conn,
) -> Tuple[Dict[str, List[Jurisdiction]], Dict[str, str]]:
    """Return ``(by_state_code → [Jurisdiction], full_state_name_lower → code)``."""
    from psycopg2.extras import RealDictCursor

    by_state: Dict[str, List[Jurisdiction]] = defaultdict(list)
    name_to_code: Dict[str, str] = {}

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT jurisdiction_id, name, jurisdiction_type,
                   state_code, state, latitude, longitude
            FROM intermediate.int_jurisdictions
            WHERE state_code IS NOT NULL
            """
        )
        for row in cur.fetchall():
            code = (row["state_code"] or "").strip().upper()
            if not code:
                continue
            state_name = (row["state"] or "").strip()
            if state_name and row["jurisdiction_type"] == "state":
                name_to_code[state_name.lower()] = code
            jtype = (row["jurisdiction_type"] or "").strip()
            name = (row["name"] or "").strip()
            lat = float(row["latitude"]) if row["latitude"] is not None else None
            lon = float(row["longitude"]) if row["longitude"] is not None else None
            by_state[code].append(
                Jurisdiction(
                    jurisdiction_id=str(row["jurisdiction_id"]),
                    name=name,
                    jurisdiction_type=jtype,
                    state_code=code,
                    state=state_name,
                    latitude=lat,
                    longitude=lon,
                    core_place=core_tokens(name, is_school=False),
                    core_school=core_tokens(name, is_school=True),
                )
            )
    logger.info(
        "Loaded {:,} jurisdictions across {} states; {} full-name → code entries",
        sum(len(v) for v in by_state.values()),
        len(by_state),
        len(name_to_code),
    )
    return by_state, name_to_code


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------


@dataclass
class Resolution:
    jurisdiction_id: str
    jurisdiction_name: str
    jurisdiction_type: str
    state_code: str
    state: str
    city: str
    confidence: str  # high | medium | low
    method: str


# A name agreement at/above this is treated as a confident name hit; distance is
# then only the tiebreak among equally-named candidates.
_STRONG_NAME = 0.6


def resolve_state_code(
    state_token: str, name_to_code: Dict[str, str], valid_codes: Iterable[str]
) -> Optional[str]:
    t = (state_token or "").strip()
    if not t:
        return None
    if len(t) == 2 and t.upper() in valid_codes:
        return t.upper()
    key = t.lower()
    if key in name_to_code:
        return name_to_code[key]
    # Recover source truncations of multi-word state names: some CivicSearch
    # school rows store "<place>, West" (the "Virginia" was dropped). Accept a
    # token that is the unique prefix of exactly one state name ("west" →
    # "west virginia"); bail on ambiguous directionals ("new", "north", "south").
    hits = {code for name, code in name_to_code.items() if name.startswith(key + " ")}
    return next(iter(hits)) if len(hits) == 1 else None


def resolve_place(
    place: str,
    state_code: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
    *,
    is_school: bool,
    by_state: Dict[str, List[Jurisdiction]],
) -> Optional[Resolution]:
    """Best jurisdiction for one parsed CivicSearch place, or None if unresolved."""
    if not state_code:
        return None
    candidates = by_state.get(state_code)
    if not candidates:
        return None

    pref_types = _SCHOOL_TYPES if is_school else _CITY_TYPES
    type_rank = {t: i for i, t in enumerate(pref_types)}
    place_core = core_tokens(place, is_school=is_school)

    scored: List[Tuple[float, float, int, Jurisdiction]] = []
    for j in candidates:
        if j.jurisdiction_type not in type_rank:
            continue
        nscore = _name_score(place_core, j.core(is_school=is_school))
        if lat is not None and j.latitude is not None:
            dist = _haversine_km(lat, lon, j.latitude, j.longitude)
        else:
            dist = float("inf")
        scored.append((nscore, dist, type_rank[j.jurisdiction_type], j))

    if not scored:
        return None

    strong = [s for s in scored if s[0] >= _STRONG_NAME]
    if strong:
        # Confident name hit(s): pick best name, then preferred type, then nearest.
        best_name = max(s[0] for s in strong)
        finalists = [s for s in strong if s[0] >= best_name - 1e-9]
        finalists.sort(key=lambda s: (s[2], s[1]))
        nscore, dist, _, j = finalists[0]
        conf = "high"
        method = "name" if dist == float("inf") else "name+latlon"
    else:
        partial = [s for s in scored if s[0] > 0.0]
        if partial:
            # Weak name overlap: lean on proximity, keep only some token agreement.
            partial.sort(key=lambda s: (s[1], s[2], -s[0]))
            nscore, dist, _, j = partial[0]
            conf = "medium"
            method = "latlon+weakname"
        else:
            # No name agreement at all → nearest preferred-type centroid.
            withpos = [s for s in scored if s[1] != float("inf")]
            if not withpos:
                return None
            withpos.sort(key=lambda s: (s[2], s[1]))
            nscore, dist, _, j = withpos[0]
            conf = "low"
            method = "latlon"

    return Resolution(
        jurisdiction_id=j.jurisdiction_id,
        jurisdiction_name=j.name,
        jurisdiction_type=j.jurisdiction_type,
        state_code=j.state_code,
        state=j.state,
        city=place,
        confidence=conf,
        method=method,
    )


# ---------------------------------------------------------------------------
# CivicSearch source rows
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Place:
    location: str
    lat: Optional[float]
    lon: Optional[float]
    is_school: bool


def load_civicsearch_places(conn) -> Dict[str, Place]:
    """Map ``vid_id`` → its CivicSearch place. Schools portal wins on overlap."""
    from psycopg2.extras import RealDictCursor

    places: Dict[str, Place] = {}
    queries = (
        ("bronze.bronze_events_civicsearch", False),
        ("bronze.bronze_events_civicsearch_schools", True),
    )
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        for table, is_school in queries:
            cur.execute(
                f"""
                SELECT NULLIF(TRIM(vid_id), '') AS vid_id,
                       NULLIF(TRIM(location), '') AS location,
                       place_lat, place_lon
                FROM {table}
                WHERE NULLIF(TRIM(vid_id), '') IS NOT NULL
                  AND NULLIF(TRIM(location), '') IS NOT NULL
                """
            )
            for row in cur.fetchall():
                vid = row["vid_id"]
                # Schools loaded second; let the school portal win a shared vid_id.
                if vid in places and not is_school:
                    continue
                places[vid] = Place(
                    location=row["location"],
                    lat=(
                        float(row["place_lat"])
                        if row["place_lat"] is not None
                        else None
                    ),
                    lon=(
                        float(row["place_lon"])
                        if row["place_lon"] is not None
                        else None
                    ),
                    is_school=is_school,
                )
    logger.info("Loaded {:,} CivicSearch vid_id → place rows", len(places))
    return places


def build_resolutions(
    places: Dict[str, Place],
    by_state: Dict[str, List[Jurisdiction]],
    name_to_code: Dict[str, str],
) -> Tuple[Dict[str, Resolution], Dict[str, int]]:
    """Resolve every vid_id, caching by distinct place to avoid rework."""
    valid_codes = set(by_state.keys())
    cache: Dict[Place, Optional[Resolution]] = {}
    out: Dict[str, Resolution] = {}
    stats: Dict[str, int] = defaultdict(int)

    for vid, place in places.items():
        if place not in cache:
            name, state_token = parse_location(place.location)
            state_code = resolve_state_code(state_token, name_to_code, valid_codes)
            cache[place] = resolve_place(
                name,
                state_code,
                place.lat,
                place.lon,
                is_school=place.is_school,
                by_state=by_state,
            )
        res = cache[place]
        if res is None:
            stats["unresolved"] += 1
            continue
        out[vid] = res
        stats[f"conf_{res.confidence}"] += 1
    stats["resolved"] = len(out)
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
    """Update ``bronze_event_youtube`` civicsearch rows from the resolutions."""
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
            r.city,
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
            CREATE TEMP TABLE _cs_geo (
                vid_id text PRIMARY KEY,
                jurisdiction_id text,
                jurisdiction_name text,
                jurisdiction_type text,
                state_code text,
                state text,
                city text
            ) ON COMMIT DROP
            """
        )
        execute_values(
            cur,
            """
            INSERT INTO _cs_geo (
                vid_id, jurisdiction_id, jurisdiction_name,
                jurisdiction_type, state_code, state, city
            ) VALUES %s
            ON CONFLICT (vid_id) DO NOTHING
            """,
            rows,
        )
        cur.execute(
            """
            UPDATE bronze.bronze_event_youtube y
            SET jurisdiction_id   = g.jurisdiction_id,
                jurisdiction_name = g.jurisdiction_name,
                jurisdiction_type = g.jurisdiction_type,
                state_code        = COALESCE(g.state_code, y.state_code),
                state             = COALESCE(g.state, y.state),
                city              = COALESCE(NULLIF(y.city, ''), g.city),
                last_updated      = CURRENT_TIMESTAMP
            FROM _cs_geo g
            WHERE y.video_id = g.vid_id
              AND y.datasource = 'civicsearch'
            """
        )
        stats["updated"] = cur.rowcount

    if dry_run:
        conn.rollback()
        stats["dry_run"] = 1
    else:
        conn.commit()
    return stats


def enrich(
    conn,
    *,
    min_confidence: str = "low",
    dry_run: bool = False,
    sample: int = 0,
) -> Dict[str, int]:
    """Resolve CivicSearch geo and write it onto ``bronze_event_youtube``.

    Importable entry point so a CivicSearch end-to-end runner can chain this
    right after the promotion (migration 103) without shelling out. Returns the
    merged resolution + writeback stats. Idempotent — safe to re-run on every
    fresh harvest; only ``datasource = 'civicsearch'`` rows are touched.
    """
    by_state, name_to_code = load_jurisdictions(conn)
    places = load_civicsearch_places(conn)
    resolutions, stats = build_resolutions(places, by_state, name_to_code)

    total = stats["resolved"] + stats["unresolved"]
    logger.info(
        "Resolved {:,}/{:,} vid_ids ({} high, {} medium, {} low); {:,} unresolved",
        stats["resolved"],
        total,
        stats.get("conf_high", 0),
        stats.get("conf_medium", 0),
        stats.get("conf_low", 0),
        stats.get("unresolved", 0),
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
        help="Lowest confidence to write back (default: low — write best match).",
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
        enrich(
            conn,
            min_confidence=args.min_confidence,
            dry_run=args.dry_run,
            sample=args.sample,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
