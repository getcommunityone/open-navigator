"""
Where places stand on a contested local topic (#1437) — the data behind "Where towns stand".

``GET /api/rankings/topics``
    One row per topic with any place in ``topic_place_ranking``: how many places are ranked (enough evidence) and
    unranked, how many ranked places lean against or for (shrunk against-share above or below one half), the topic's
    national against-share, and the median shrunk against-share of the ranked places.

``GET /api/rankings?topic=<slug|id>&band=<large|mid|small|unknown>&state=<XX>``
    The topic's places in scope, ranked places first by band then band rank, each with distinct-speaker counts,
    raw and shrunk against-share, and the roster-confirmed officials' side (null when none). ``national`` summarises
    the same scope.

All counting, shrinkage, thresholds and bands live in the dbt mart (``topic_place_ranking``; decision record
``web_docs/docs/development/topic-place-rankings.md``). Python only filters and shapes. Nothing is defaulted: a scope
with no rows returns an empty list and null shares, never a placeholder. No person is named; rows are places.
"""

from __future__ import annotations

import re
import statistics
from datetime import date
from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/api/rankings", tags=["rankings"])
tracer = trace.get_tracer(__name__)

VALID_BANDS = ("large", "mid", "small", "unknown")
BAND_ORDER = {b: i for i, b in enumerate(VALID_BANDS)}
#: The mart's single window (var ranking_window_months).
WINDOW_MONTHS = 24


class RankingTopic(BaseModel):
    topic_id: int
    slug: str = Field(..., description="civicsearch_topic.query_id.")
    name: str
    places_ranked: int
    places_unranked: int
    places_leaning_against: int = Field(..., description="Ranked places with shrunk against-share above 0.5.")
    places_leaning_for: int = Field(..., description="Ranked places with shrunk against-share below 0.5.")
    national_against_share: float | None = None
    median_shrunk_against_share: float | None = Field(None, description="Median over ranked places; null when none.")


class RankingPlace(BaseModel):
    jurisdiction_id: str
    jurisdiction_name: str | None
    state_code: str | None
    size_band: str
    population: int | None
    speakers_for: int
    speakers_against: int
    meetings: int
    against_share: float | None
    shrunk_against_share: float | None
    is_ranked: bool
    band_rank: int | None
    band_ranked_count: int | None
    officials_side: str | None = Field(None, description="Roster-confirmed officials only; null when none took a side.")
    last_meeting_date: date | None


class RankingNational(BaseModel):
    against_share: float | None = Field(None, description="Against share over every sided speaker in scope.")
    median_shrunk_against_share: float | None = None
    places_ranked: int
    places_unranked: int
    places_leaning_against: int
    places_leaning_for: int
    speakers_for: int
    speakers_against: int


class RankingTopicRef(BaseModel):
    topic_id: int
    slug: str
    name: str


class RankingResponse(BaseModel):
    topic: RankingTopicRef
    window_months: int = WINDOW_MONTHS
    national: RankingNational = Field(
        ..., description="A summary of the places in scope: national with no band/state filter, else that scope only "
        "(label it by the active filter). Each place's shrinkage target is always the true national rate."
    )
    places: list[RankingPlace]


def _f(v: Any) -> float | None:
    return None if v is None else round(float(v), 4)


def summarise(places: list[dict[str, Any]]) -> dict[str, Any]:
    """Scope summary from place rows (each with is_ranked, shrunk_against_share, speakers_for/against)."""
    ranked = [p for p in places if p["is_ranked"]]
    shrunk = [float(p["shrunk_against_share"]) for p in ranked if p["shrunk_against_share"] is not None]
    sf = sum(int(p["speakers_for"]) for p in places)
    sa = sum(int(p["speakers_against"]) for p in places)
    return {
        "against_share": round(sa / (sf + sa), 4) if sf + sa else None,
        "median_shrunk_against_share": round(statistics.median(shrunk), 4) if shrunk else None,
        "places_ranked": len(ranked),
        "places_unranked": len(places) - len(ranked),
        "places_leaning_against": sum(1 for s in shrunk if s > 0.5),
        "places_leaning_for": sum(1 for s in shrunk if s < 0.5),
        "speakers_for": sf,
        "speakers_against": sa,
    }


TOPICS_SQL = """
    SELECT r.topic_id, t.query_id AS slug, t.name, r.is_ranked, r.shrunk_against_share, r.national_against_share,
           r.speakers_for, r.speakers_against
    FROM topic_place_ranking r
    JOIN civicsearch_topic t ON t.topic_id = r.topic_id
    WHERE r.window_months = $1
"""


@router.get("/topics", response_model=list[RankingTopic])
async def ranking_topics() -> list[RankingTopic]:
    with tracer.start_as_current_span("rankings.topics"):
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(TOPICS_SQL, WINDOW_MONTHS)
        except asyncpg.exceptions.UndefinedTableError:
            return []
        except Exception as exc:
            logger.exception("rankings topics failed")
            raise HTTPException(status_code=503, detail="Rankings are unavailable right now.") from exc
    by_topic: dict[int, dict[str, Any]] = {}
    for r in rows:
        t = by_topic.setdefault(int(r["topic_id"]), {"topic_id": int(r["topic_id"]), "slug": r["slug"],
                                                     "name": r["name"], "national": r["national_against_share"],
                                                     "places": []})
        t["places"].append(dict(r))
    out = []
    for t in by_topic.values():
        s = summarise(t["places"])
        out.append(RankingTopic(
            topic_id=t["topic_id"], slug=t["slug"], name=t["name"], places_ranked=s["places_ranked"],
            places_unranked=s["places_unranked"], places_leaning_against=s["places_leaning_against"],
            places_leaning_for=s["places_leaning_for"], national_against_share=_f(t["national"]),
            median_shrunk_against_share=s["median_shrunk_against_share"],
        ))
    out.sort(key=lambda t: (-t.places_ranked, -(t.places_ranked + t.places_unranked), t.name))
    return out


PLACES_SQL = """
    SELECT r.jurisdiction_id, r.jurisdiction_name, r.state_code, r.size_band, r.population, r.speakers_for,
           r.speakers_against, r.meetings, r.against_share, r.shrunk_against_share, r.is_ranked, r.band_rank,
           r.band_ranked_count, r.officials_side, r.last_meeting_date
    FROM topic_place_ranking r
    WHERE r.window_months = $1 AND r.topic_id = $2
      AND ($3::text IS NULL OR r.size_band = $3)
      AND ($4::text IS NULL OR r.state_code = $4)
"""
TOPIC_SQL = """
    SELECT topic_id, query_id AS slug, name FROM civicsearch_topic
    WHERE ($1::int IS NOT NULL AND topic_id = $1) OR ($2::text IS NOT NULL AND query_id = $2)
    LIMIT 1
"""


@router.get("", response_model=RankingResponse)
async def rankings(
    topic: str = Query(..., description="Topic slug (civicsearch_topic.query_id) or topic id."),
    band: str | None = Query(None, description="large | mid | small | unknown"),
    state: str | None = Query(None, description="Two-letter state code."),
) -> RankingResponse:
    band = (band or "").strip().lower() or None
    if band is not None and band not in VALID_BANDS:
        raise HTTPException(status_code=422, detail=f"band must be one of {', '.join(VALID_BANDS)}.")
    state = (state or "").strip().upper() or None
    if state is not None and not re.fullmatch(r"[A-Z]{2}", state):
        raise HTTPException(status_code=422, detail="state must be a two-letter code.")
    topic = topic.strip()
    tid = int(topic) if re.fullmatch(r"[0-9]{1,9}", topic) else None
    with tracer.start_as_current_span("rankings.places") as span:
        span.set_attribute("topic", topic)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                trow = await conn.fetchrow(TOPIC_SQL, tid, None if tid is not None else topic)
                if trow is None:
                    raise HTTPException(status_code=404, detail="Unknown topic.")
                rows = await conn.fetch(PLACES_SQL, WINDOW_MONTHS, int(trow["topic_id"]), band, state)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("rankings failed")
            raise HTTPException(status_code=503, detail="Rankings are unavailable right now.") from exc
    places = [dict(r) for r in rows]
    places.sort(key=lambda p: (not p["is_ranked"], BAND_ORDER.get(p["size_band"], 9), p["band_rank"] or 0,
                               -(int(p["speakers_for"]) + int(p["speakers_against"])), p["jurisdiction_name"] or ""))
    return RankingResponse(
        topic=RankingTopicRef(topic_id=int(trow["topic_id"]), slug=trow["slug"], name=trow["name"]),
        national=RankingNational(**summarise(places)),
        places=[RankingPlace(
            jurisdiction_id=p["jurisdiction_id"], jurisdiction_name=p["jurisdiction_name"], state_code=p["state_code"],
            size_band=p["size_band"], population=p["population"], speakers_for=int(p["speakers_for"]),
            speakers_against=int(p["speakers_against"]), meetings=int(p["meetings"]),
            against_share=_f(p["against_share"]), shrunk_against_share=_f(p["shrunk_against_share"]),
            is_ranked=bool(p["is_ranked"]), band_rank=p["band_rank"], band_ranked_count=p["band_ranked_count"],
            officials_side=p["officials_side"], last_meeting_date=p["last_meeting_date"],
        ) for p in places],
    )
