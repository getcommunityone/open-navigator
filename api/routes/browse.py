"""
Homepage "Browse" card directory API.

Serves the four browse categories (place / topic / question / cause) for the
homepage Browse cards, plus a per-category top-items list, both backed by two
published serving views over gold:

- public.browse_directory_summary — one national row (state_code IS NULL) per
  entity_type plus per-state rows for place/topic. Used by GET /summary.
- public.browse_transcript_count — item grain (PK entity_type, entity_id) with a
  genuine distinct-transcript count per entity. Used by GET /top-items.

Both resolve as bare table names via the connection search_path (matching the
other routes — see topics.py / search_postgres.py). The columns are plain
text/int, so the pool's missing JSONB codec is irrelevant here.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from fastapi import APIRouter, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/api/browse", tags=["browse"])
tracer = trace.get_tracer(__name__)

# The four browse entity types and their card labels (plural noun). Order here is
# the canonical fallback order; the served list is re-sorted by transcript_count
# but `cause` is always forced last (it is genuinely 0 transcripts).
_LABELS: Dict[str, str] = {
    "place": "places",
    "topic": "topics",
    "question": "questions",
    "cause": "causes",
}


class BrowseCategory(BaseModel):
    entity_type: str
    label: str
    transcript_count: int
    entity_count: int
    has_transcripts: bool


class BrowseSummary(BaseModel):
    categories: List[BrowseCategory]


class BrowseTopItem(BaseModel):
    entity_id: str
    entity_name: str
    transcript_count: int
    # Nullable: question/cause items have no state_code; place/topic carry one.
    state_code: Optional[str] = None


class BrowseTopItems(BaseModel):
    items: List[BrowseTopItem]


class PlaceMapPin(BaseModel):
    """A single map pin for an indexed place (or a state/county rollup of them)."""
    geoid: str
    name: str
    state_code: Optional[str] = None
    latitude: float
    longitude: float
    # Distinct indexed places represented by this pin (1 for an individual
    # place; the rollup count for a state pin).
    place_count: int
    transcript_count: int


class PlaceMapLevel(BaseModel):
    level: str           # state | county | city | school_district
    label: str           # display label for the filter toggle
    count: int           # number of pins at this level
    pins: List[PlaceMapPin]


class PlaceMapResponse(BaseModel):
    levels: List[PlaceMapLevel]


# One round-trip: pull the national row (state_code IS NULL) and, when a state is
# given, the matching per-state row for each entity_type. We pick the per-state
# row in Python (preferring it over the national fallback). $1 is the upper-cased
# state code or NULL.
_SUMMARY_SQL = """
    SELECT entity_type, state_code, transcript_count, entity_count
    FROM browse_directory_summary
    WHERE state_code IS NULL OR state_code = $1::text
"""

# Top items in a category by transcript count. For place/topic, filter to the
# given state when provided; question/cause have no per-state rows, so the state
# filter is a no-op handled by passing NULL.
_TOP_ITEMS_SQL = """
    SELECT entity_id, entity_name, transcript_count, state_code
    FROM browse_transcript_count
    WHERE entity_type = $1::text
      AND ($2::text IS NULL OR state_code = $2::text)
    ORDER BY transcript_count DESC NULLS LAST, entity_name ASC
    LIMIT $3::int
"""

# Questions are special: they surface from the curated/pinned registry, NOT by
# transcript count. The homepage "Browse questions" dropdown (and any other
# top-items question consumer) shows ONLY the featured policy questions, in
# editorial order (display_order), matching the /policy-questions page. Real
# distinct-transcript counts are LEFT-joined so a pinned question with no linked
# transcripts honestly shows 0 rather than being dropped.
_TOP_QUESTIONS_FEATURED_SQL = """
    SELECT q.question_id                     AS entity_id,
           q.canonical_text                  AS entity_name,
           COALESCE(b.transcript_count, 0)   AS transcript_count,
           NULL::text                        AS state_code
    FROM public.policy_question q
    LEFT JOIN browse_transcript_count b
      ON b.entity_type = 'question'
     AND b.entity_id = q.question_id
    WHERE q.is_featured = true
    ORDER BY q.display_order ASC NULLS LAST, q.instances_total DESC NULLS LAST
    LIMIT $1::int
"""


# --- Place map (clustered pins of the places we index) ------------------------
#
# The honest "places we index" universe is browse_transcript_count where
# entity_type='place' (one row per indexed place geoid, with its real distinct
# transcript_count). We join each place to its census centroid in `jurisdictions`
# for lat/lon + jurisdiction_type. geoid is NOT unique in `jurisdictions`
# (city/school_district collisions), so DISTINCT ON (geoid) with a type-priority
# tiebreaker emits exactly one centroid per place.
#
# Individual-place levels (city / county / school_district) are bucketed in
# Python from this one query by jurisdiction_type. The STATE level is a genuine
# rollup: one pin per state that has any indexed place, at the real state
# centroid, sized by the count of distinct indexed places in that state.
_PLACE_MAP_PLACES_SQL = """
    SELECT DISTINCT ON (b.entity_id)
        b.entity_id            AS geoid,
        b.entity_name          AS name,
        b.state_code           AS state_code,
        j.jurisdiction_type    AS jurisdiction_type,
        j.latitude::float8     AS latitude,
        j.longitude::float8    AS longitude,
        b.transcript_count     AS transcript_count
    FROM browse_transcript_count b
    JOIN jurisdictions j
        ON j.geoid = b.entity_id
       AND j.latitude IS NOT NULL
       AND j.longitude IS NOT NULL
    WHERE b.entity_type = 'place'
    ORDER BY b.entity_id,
        CASE j.jurisdiction_type
            WHEN 'city' THEN 0 WHEN 'town' THEN 1
            WHEN 'county' THEN 2 WHEN 'school_district' THEN 3 ELSE 4
        END
"""

_PLACE_MAP_STATE_SQL = """
    WITH place AS (
        SELECT DISTINCT ON (b.entity_id)
            b.entity_id AS geoid, b.state_code, b.transcript_count
        FROM browse_transcript_count b
        WHERE b.entity_type = 'place' AND b.state_code IS NOT NULL
    )
    SELECT
        s.geoid                        AS geoid,
        s.name                         AS name,
        s.state_code                   AS state_code,
        s.latitude::float8             AS latitude,
        s.longitude::float8            AS longitude,
        count(DISTINCT p.geoid)::int   AS place_count,
        sum(p.transcript_count)::int   AS transcript_count
    FROM place p
    JOIN jurisdictions s
        ON s.jurisdiction_type = 'state'
       AND s.state_code = p.state_code
       AND s.latitude IS NOT NULL
       AND s.longitude IS NOT NULL
    GROUP BY s.geoid, s.name, s.state_code, s.latitude, s.longitude
    ORDER BY place_count DESC
"""

# jurisdiction_type -> (level key, plural label). town folds into the city level
# (both are sub-county localities); state is built from its own rollup query.
_PLACE_LEVEL_LABELS: Dict[str, str] = {
    "state": "States",
    "county": "Counties",
    "city": "Cities & towns",
    "school_district": "School districts",
}
_TYPE_TO_LEVEL: Dict[str, str] = {
    "city": "city",
    "town": "city",
    "county": "county",
    "school_district": "school_district",
}


def _normalize_state(state: Optional[str]) -> Optional[str]:
    """Upper-case a 2-letter state code, or None when blank/absent."""
    if state is None:
        return None
    s = state.strip().upper()
    return s or None


@router.get("/summary", response_model=BrowseSummary)
async def browse_summary(
    state: Optional[str] = Query(
        None, description="Optional 2-letter state code. Scopes place/topic to that state; question/cause stay national."
    ),
) -> BrowseSummary:
    """The four homepage Browse cards, sorted by transcript_count desc (cause last)."""
    with tracer.start_as_current_span("browse-summary") as span:
        state_code = _normalize_state(state)
        span.set_attribute("browse.state", state_code or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("browse-summary-query"):
                    rows = await conn.fetch(_SUMMARY_SQL, state_code)
        except Exception as exc:  # noqa: BLE001
            logger.exception("browse summary failed")
            span.record_exception(exc)
            # Empty list over a 500 — the homepage renders an empty Browse state.
            return BrowseSummary(categories=[])

        # For each entity_type prefer the per-state row over the national one.
        chosen: Dict[str, dict] = {}
        for r in rows:
            et = r["entity_type"]
            is_state_row = r["state_code"] is not None
            existing = chosen.get(et)
            if existing is None or (is_state_row and existing["state_code"] is None):
                chosen[et] = dict(r)

        categories = [
            BrowseCategory(
                entity_type=et,
                label=_LABELS.get(et, f"{et}s"),
                transcript_count=row["transcript_count"] or 0,
                entity_count=row["entity_count"] or 0,
                has_transcripts=(row["transcript_count"] or 0) > 0,
            )
            for et, row in chosen.items()
        ]

        # Sort by transcript_count desc, but always pin `place` to the very end so
        # the "Browse places" card sits at the far right of the homepage row (a
        # product choice — places dwarfs the others on transcript count, but we
        # want it last). `cause` (genuinely 0 transcripts) then naturally falls
        # just before place via the descending count.
        categories.sort(
            key=lambda c: (c.entity_type == "place", -c.transcript_count)
        )

        span.set_attribute("browse.categories", len(categories))
        return BrowseSummary(categories=categories)


@router.get("/top-items", response_model=BrowseTopItems)
async def browse_top_items(
    entity_type: str = Query(..., description="One of: place, topic, question, cause."),
    state: Optional[str] = Query(
        None, description="Optional 2-letter state code (applies to place/topic; ignored for question/cause)."
    ),
    limit: int = Query(8, ge=1, le=50, description="Max items (default 8, cap 50)."),
) -> BrowseTopItems:
    """Top items in a browse category, ranked by transcript_count desc."""
    with tracer.start_as_current_span("browse-top-items") as span:
        et = (entity_type or "").strip().lower()
        span.set_attribute("browse.entity_type", et)
        if et not in _LABELS:
            # Unknown entity_type — empty list rather than a 4xx, matching the
            # forgiving posture of the other browse/topic routes.
            span.set_attribute("browse.unknown_entity_type", True)
            return BrowseTopItems(items=[])

        state_code = _normalize_state(state)
        # question/cause have no per-state rows; never filter them by state.
        if et in ("question", "cause"):
            state_code = None
        span.set_attribute("browse.state", state_code or "")

        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("browse-top-items-query"):
                    if et == "question":
                        # Pinned/featured registry questions only, editorial order.
                        rows = await conn.fetch(_TOP_QUESTIONS_FEATURED_SQL, limit)
                    else:
                        rows = await conn.fetch(_TOP_ITEMS_SQL, et, state_code, limit)
        except Exception as exc:  # noqa: BLE001
            logger.exception("browse top-items failed")
            span.record_exception(exc)
            return BrowseTopItems(items=[])

        span.set_attribute("browse.items", len(rows))
        return BrowseTopItems(
            items=[
                BrowseTopItem(
                    entity_id=r["entity_id"],
                    entity_name=r["entity_name"],
                    transcript_count=r["transcript_count"] or 0,
                    state_code=r["state_code"],
                )
                for r in rows
            ]
        )


@router.get("/place-map", response_model=PlaceMapResponse)
async def browse_place_map() -> PlaceMapResponse:
    """Clustered map pins for every place we index, grouped into filterable levels.

    Returns four levels — state (a per-state rollup), county, city (cities +
    towns) and school_district — each an independently toggleable layer of pins
    plotted at real census centroids. Every pin is a place with >=1 transcript;
    no fabricated coordinates or counts.
    """
    with tracer.start_as_current_span("browse-place-map") as span:
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("browse-place-map-query"):
                    place_rows = await conn.fetch(_PLACE_MAP_PLACES_SQL)
                    state_rows = await conn.fetch(_PLACE_MAP_STATE_SQL)
        except Exception as exc:  # noqa: BLE001
            logger.exception("browse place-map failed")
            span.record_exception(exc)
            # Empty levels over a 500 — the map renders an empty state.
            return PlaceMapResponse(levels=[])

        # Bucket the individual indexed places by jurisdiction_type into levels.
        buckets: Dict[str, List[PlaceMapPin]] = {
            "city": [], "county": [], "school_district": [],
        }
        for r in place_rows:
            level = _TYPE_TO_LEVEL.get(r["jurisdiction_type"])
            if level is None:
                continue  # an indexed place of an unmapped type — skip, don't guess
            buckets[level].append(
                PlaceMapPin(
                    geoid=r["geoid"],
                    name=r["name"],
                    state_code=r["state_code"],
                    latitude=r["latitude"],
                    longitude=r["longitude"],
                    place_count=1,
                    transcript_count=r["transcript_count"] or 0,
                )
            )

        state_pins = [
            PlaceMapPin(
                geoid=r["geoid"],
                name=r["name"],
                state_code=r["state_code"],
                latitude=r["latitude"],
                longitude=r["longitude"],
                place_count=r["place_count"] or 0,
                transcript_count=r["transcript_count"] or 0,
            )
            for r in state_rows
        ]

        # Stable level order: state, county, city, school_district.
        ordered = [("state", state_pins)] + [
            (lvl, buckets[lvl]) for lvl in ("county", "city", "school_district")
        ]
        levels = [
            PlaceMapLevel(
                level=lvl,
                label=_PLACE_LEVEL_LABELS[lvl],
                count=len(pins),
                pins=pins,
            )
            for lvl, pins in ordered
        ]

        span.set_attribute(
            "browse.place_map_pins", sum(len(p) for _, p in ordered)
        )
        return PlaceMapResponse(levels=levels)
