"""Caption facts for a topic story or tile (#1125): ``GET /api/topics/{topic}/caption-facts?state=&city=``.

The web caption picker (``web_app/src/utils/storyCaption.ts``) chooses the strongest statement the record supports for
one topic and one scope (national, state or city). This route only gathers the real counts it chooses from:

- meetings in scope, and meetings per state for the whole country (never narrowed, so a state can be ranked), each state
  with its population when ``jurisdictions`` has it on record;
- for a city scope, meetings per place in that state, so the city can be ranked among its neighbours;
- for data centers, the counted speakers for and against (``data_center_meeting_position``);
- the AI meeting readings: ``data_center_meeting_lean`` for data centers, ``topic_meeting_lean`` (#1126) for any other
  topic. Every optional read is wrapped on its own: a missing table or column gives null, never a 500, and never a 0
  that would read as "none".

Meeting counts: data centers count distinct meetings in ``data_center_meeting_mention`` (the same figure the Data Center
Story shows); every other topic reads the browse transcript-count marts, which equal the distinct meetings in
``topic_transcript_link`` for curated topics. Nothing here is estimated. Decision record:
``web_docs/docs/development/story-captions.md``.
"""

from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, HTTPException, Path, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/api/topics", tags=["topics"])
tracer = trace.get_tracer(__name__)

DATA_CENTERS_TOPIC_ID = 100001
"""The curated "Data centers" topic (#500): its meetings and readings come from the data-center marts."""

TOPIC_ALIASES: dict[str, str] = {
    # The home strip's Flock card and License plate readers card share one curated topic.
    "flock": "license-plate-readers",
}


class CaptionScope(BaseModel):
    level: str = Field(..., description="national, state or city.")
    state_code: str | None = None
    state: str | None = None
    city: str | None = None


class CaptionStateCount(BaseModel):
    state_code: str
    state: str | None = None
    meetings: int
    population: int | None = Field(None, description="The state's population from jurisdictions; null when not on record.")


class CaptionPlaceCount(BaseModel):
    name: str
    meetings: int


class CaptionSpeakers(BaseModel):
    for_: int = Field(0, alias="for")
    against: int = 0
    question: int = 0
    neutral: int = 0
    states: int = Field(
        0, description="States in scope with any hand-counted speaker (#1134), so a basis can say where they were counted."
    )

    model_config = {"populate_by_name": True}


class CaptionWiderLean(BaseModel):
    """One broader scope's AI reading (#1182), so a place too thin for its own reading can name the scope the map colours."""

    level: str = Field(..., description="state or national.")
    state_code: str | None = None
    state: str | None = None
    lean_meetings: int
    public_against_meetings: int
    public_against_states: int
    disagreement_meetings: int


class TopicCaptionFacts(BaseModel):
    topic: str = Field(..., description="The topic's query slug.")
    topic_id: int
    scope: CaptionScope
    meetings: int | None = Field(None, description="Distinct meetings in scope; null when the count could not be read.")
    states: list[CaptionStateCount] = Field(
        default_factory=list, description="Meetings per state for the whole country, largest first (never narrowed)."
    )
    top_state: str | None = Field(None, description="The state code with the most meetings nationally.")
    ratio_to_next: float | None = Field(
        None, description="The top state's meetings over the second state's; null with fewer than two states."
    )
    place: str | None = Field(None, description="City scope: the place name the city matched.")
    places: list[CaptionPlaceCount] | None = Field(
        None, description="City scope: meetings per place in the state, largest first; null otherwise."
    )
    speakers: CaptionSpeakers | None = Field(
        None, description="Counted speakers in scope (data centers only); null when not on record."
    )
    lean_meetings: int | None = Field(None, description="Meetings in scope with an AI reading (Jev); null when none loaded.")
    public_against_meetings: int | None = Field(
        None, description="AI reading: meetings where the public mostly opposed. Null when not loaded."
    )
    public_against_states: int | None = Field(
        None, description="AI reading: states with at least one public-against meeting in scope (#1134). Null when not loaded."
    )
    public_for_meetings: int | None = Field(
        None, description="AI reading: meetings where the public mostly supported. Null when not loaded or not read."
    )
    disagreement_meetings: int | None = Field(
        None, description="AI reading: meetings where officials sided against the public. Null when not loaded."
    )
    disagreement_states: int | None = Field(None, description="States with at least one disagreement meeting in scope.")
    wider: list[CaptionWiderLean] | None = Field(
        None,
        description=(
            "AI readings for the broader scopes (#1182): city scope [state, national], state scope [national], national "
            "null. A scope with no reading loaded is left out."
        ),
    )


RESOLVE_SQL = (
    "SELECT t.topic_id, t.query_id FROM civicsearch_topic t "
    "WHERE t.query_id = $1 OR t.topic_id::text = $1 ORDER BY t.topic_id LIMIT 1"
)

STATE_POP_SQL = (
    "SELECT j.state_code, max(j.state_name) AS state, max(j.population)::bigint AS population "
    "FROM jurisdictions j WHERE j.jurisdiction_type = 'state' AND j.state_code IS NOT NULL GROUP BY j.state_code"
)

# --- data centers: the Data Center Story's own meeting marts ---------------------------------------------------------
DC_NATIONAL_SQL = "SELECT count(DISTINCT m.video_id)::int AS n FROM data_center_meeting_mention m"
DC_STATES_SQL = (
    "SELECT m.state_code, max(m.state) AS state, count(DISTINCT m.video_id)::int AS meetings "
    "FROM data_center_meeting_mention m WHERE m.state_code IS NOT NULL "
    "GROUP BY m.state_code ORDER BY meetings DESC, m.state_code"
)
DC_PLACES_SQL = (
    "SELECT m.jurisdiction_name AS name, count(DISTINCT m.video_id)::int AS meetings "
    "FROM data_center_meeting_mention m WHERE m.state_code = $1 AND m.jurisdiction_name IS NOT NULL "
    "GROUP BY m.jurisdiction_name ORDER BY meetings DESC, m.jurisdiction_name"
)
DC_CITY_SQL = (
    "SELECT count(DISTINCT m.video_id)::int AS n FROM data_center_meeting_mention m "
    "WHERE m.state_code = $1 AND m.jurisdiction_name ILIKE $2"
)

# --- every other topic: the browse transcript-count marts -----------------------------------------------------------
TOPIC_NATIONAL_SQL = (
    "SELECT n.transcript_count::int AS n FROM browse_transcript_count n "
    "WHERE n.entity_type = 'topic' AND n.entity_id = $1"
)
TOPIC_STATES_SQL = (
    "SELECT s.state_code, NULL::text AS state, s.transcript_count::int AS meetings "
    "FROM browse_entity_state_transcript_count s "
    "WHERE s.entity_type = 'topic' AND s.entity_id = $1 AND s.state_code IS NOT NULL AND s.transcript_count > 0 "
    "ORDER BY meetings DESC, s.state_code"
)
TOPIC_PLACES_SQL = (
    "SELECT p.jurisdiction_name AS name, max(p.transcript_count)::int AS meetings "
    "FROM browse_entity_place_transcript_count p "
    "WHERE p.entity_type = 'topic' AND p.entity_id = $1 AND p.state_code = $2 AND p.jurisdiction_name IS NOT NULL "
    "GROUP BY p.jurisdiction_name ORDER BY meetings DESC, p.jurisdiction_name"
)

SPEAKERS_SQL = (
    "SELECT coalesce(sum(p.speakers_for), 0)::int AS for_, coalesce(sum(p.speakers_against), 0)::int AS against, "
    "coalesce(sum(p.speakers_question), 0)::int AS question, coalesce(sum(p.speakers_neutral), 0)::int AS neutral, "
    "count(*)::int AS meetings_reviewed, "
    "count(DISTINCT p.state_code) FILTER (WHERE p.speakers_for + p.speakers_against + p.speakers_question "
    "+ p.speakers_neutral > 0)::int AS states "
    "FROM data_center_meeting_position p "
    "WHERE ($1::text IS NULL OR p.state_code = $1::text) AND ($2::text IS NULL OR p.jurisdiction_name ILIKE $2::text)"
)


def build_lean_sql(topic_id: int, state_code: str | None, city_like: str | None) -> tuple[str, list[Any]]:
    """AI-reading counts in scope. Data centers read ``data_center_meeting_lean``; other topics ``topic_meeting_lean``
    (#1126, one row per meeting x topic). ``public_for`` is read defensively: the data-center mart has no such column."""
    params: list[Any] = []
    where: list[str] = []
    if topic_id == DATA_CENTERS_TOPIC_ID:
        table = "data_center_meeting_lean"
    else:
        table = "topic_meeting_lean"
        params.append(topic_id)
        where.append(f"l.topic_id = ${len(params)}")
    if state_code:
        params.append(state_code)
        where.append(f"l.state_code = ${len(params)}")
    if city_like:
        params.append(city_like)
        where.append(f"l.jurisdiction_name ILIKE ${len(params)}")
    sql = (
        "SELECT count(*)::int AS lean_meetings, "
        "count(*) FILTER (WHERE l.public_against)::int AS public_against_meetings, "
        "count(DISTINCT l.state_code) FILTER (WHERE l.public_against)::int AS public_against_states, "
        "count(*) FILTER (WHERE (to_jsonb(l) ->> 'public_for')::boolean)::int AS public_for_meetings, "
        "bool_or(to_jsonb(l) ? 'public_for') AS has_public_for, "
        "count(*) FILTER (WHERE l.officials_sided_against_public)::int AS disagreement_meetings, "
        "count(DISTINCT l.state_code) FILTER (WHERE l.officials_sided_against_public)::int AS disagreement_states "
        f"FROM {table} l WHERE {' AND '.join(where) or 'TRUE'}"
    )
    return sql, params


async def _optional(conn: Any, what: str, sql: str, *params: Any) -> list[Any] | None:
    """Rows, or None when the relation or a column isn't in this database (logged, never raised)."""
    try:
        return list(await conn.fetch(sql, *params))
    except asyncpg.exceptions.PostgresError as e:
        logger.warning("caption-facts: {} unavailable ({}); null", what, e)
        return None


def wider_scopes(state_code: str | None, city_like: str | None) -> list[tuple[str, str | None]]:
    """The broader scopes to read for a fallback, nearest first: (level, state_code)."""
    if not state_code:
        return []
    out: list[tuple[str, str | None]] = []
    if city_like:
        out.append(("state", state_code))
    out.append(("national", None))
    return out


def wider_lean(level: str, state_code: str | None, state: str | None, row: Any) -> CaptionWiderLean | None:
    """A broader scope's reading from one lean-count row, or None when no meeting there has a reading."""
    if not row:
        return None
    r = dict(row)
    if int(r.get("lean_meetings") or 0) <= 0:
        return None
    return CaptionWiderLean(
        level=level,
        state_code=state_code,
        state=state,
        lean_meetings=int(r["lean_meetings"]),
        public_against_meetings=int(r.get("public_against_meetings") or 0),
        public_against_states=int(r.get("public_against_states") or 0),
        disagreement_meetings=int(r.get("disagreement_meetings") or 0),
    )


def pick_place(places: list[CaptionPlaceCount], city: str) -> CaptionPlaceCount | None:
    """The place a city names: an exact (case-insensitive) name first, else the busiest name containing it."""
    c = city.lower()
    exact = [p for p in places if p.name.lower() == c]
    if exact:
        return exact[0]
    loose = [p for p in places if c in p.name.lower()]
    return loose[0] if loose else None


@router.get("/{topic}/caption-facts", response_model=TopicCaptionFacts, response_model_by_alias=True)
async def topic_caption_facts(
    topic: str = Path(..., description="Topic query slug (e.g. short-term-rentals) or topic id."),
    state: str | None = Query(None, description="Optional 2-letter state code."),
    city: str | None = Query(None, description="Optional city (with a state); case-insensitive name match."),
) -> TopicCaptionFacts:
    """The real counts behind a topic caption, for one scope. Missing optional data is null, never a guess."""
    slug = TOPIC_ALIASES.get(topic.strip().lower(), topic.strip().lower())
    state_code = state.strip().upper() if state and state.strip() else None
    city_clean = city.strip() if city and city.strip() and state_code else None
    city_like = f"%{city_clean}%" if city_clean else None
    with tracer.start_as_current_span("topics.caption-facts") as span:
        span.set_attribute("caption.topic", slug)
        span.set_attribute("caption.state", state_code or "")
        span.set_attribute("caption.city", city_clean or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                found = await conn.fetch(RESOLVE_SQL, slug)
                if not found:
                    raise HTTPException(status_code=404, detail="No such topic.")
                topic_id = int(found[0]["topic_id"])
                query_id = found[0]["query_id"] or slug
                is_dc = topic_id == DATA_CENTERS_TOPIC_ID
                tid = str(topic_id)
                if is_dc:
                    national_rows = await conn.fetch(DC_NATIONAL_SQL)
                    state_rows = await conn.fetch(DC_STATES_SQL)
                else:
                    national_rows = await conn.fetch(TOPIC_NATIONAL_SQL, tid)
                    state_rows = await conn.fetch(TOPIC_STATES_SQL, tid)
                pop_rows = await _optional(conn, "state population", STATE_POP_SQL)
                place_rows: list[Any] | None = None
                city_rows: list[Any] | None = None
                if city_clean:
                    if is_dc:
                        place_rows = await conn.fetch(DC_PLACES_SQL, state_code)
                        city_rows = await conn.fetch(DC_CITY_SQL, state_code, city_like)
                    else:
                        place_rows = await conn.fetch(TOPIC_PLACES_SQL, tid, state_code)
                speaker_rows = (
                    await _optional(conn, "data_center_meeting_position", SPEAKERS_SQL, state_code, city_like)
                    if is_dc
                    else None
                )
                lean_sql, lean_params = build_lean_sql(topic_id, state_code, city_like)
                lean_rows = await _optional(conn, "meeting lean", lean_sql, *lean_params)
                wider_rows: list[tuple[str, str | None, list[Any] | None]] = []
                for w_level, w_state in wider_scopes(state_code, city_like):
                    w_sql, w_params = build_lean_sql(topic_id, w_state, None)
                    wider_rows.append((w_level, w_state, await _optional(conn, f"{w_level} lean", w_sql, *w_params)))
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("caption facts failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This topic's caption facts are unavailable right now.") from exc

    pops = {r["state_code"]: dict(r) for r in (pop_rows or [])}
    states = [
        CaptionStateCount(
            state_code=r["state_code"],
            state=r["state"] or (pops.get(r["state_code"]) or {}).get("state"),
            meetings=int(r["meetings"]),
            population=(int(p) if (p := (pops.get(r["state_code"]) or {}).get("population")) else None),
        )
        for r in state_rows
        if int(r["meetings"] or 0) > 0
    ]
    states.sort(key=lambda s: (-s.meetings, s.state_code))
    top_state = states[0].state_code if states else None
    ratio = round(states[0].meetings / states[1].meetings, 2) if len(states) >= 2 and states[1].meetings > 0 else None

    state_name = (pops.get(state_code) or {}).get("state") if state_code else None
    if state_code and not state_name:
        state_name = next((s.state for s in states if s.state_code == state_code), None)

    places: list[CaptionPlaceCount] | None = None
    place: str | None = None
    if city_clean:
        places = [CaptionPlaceCount(name=r["name"], meetings=int(r["meetings"])) for r in (place_rows or [])]
        matched = pick_place(places, city_clean)
        place = matched.name if matched else None
        if is_dc:
            meetings = int(city_rows[0]["n"] or 0) if city_rows else 0
        else:
            meetings = matched.meetings if matched else 0
    elif state_code:
        meetings = next((s.meetings for s in states if s.state_code == state_code), 0)
    else:
        meetings = int(national_rows[0]["n"] or 0) if national_rows and national_rows[0]["n"] is not None else None

    speakers: CaptionSpeakers | None = None
    if speaker_rows:
        r = dict(speaker_rows[0])
        if int(r.get("meetings_reviewed") or 0) > 0:
            speakers = CaptionSpeakers(
                for_=int(r["for_"] or 0), against=int(r["against"] or 0),
                question=int(r["question"] or 0), neutral=int(r["neutral"] or 0),
                states=int(r.get("states") or 0),
            )

    lean: dict[str, Any] = {}
    if lean_rows:
        r = dict(lean_rows[0])
        if int(r.get("lean_meetings") or 0) > 0:
            lean = {
                "lean_meetings": int(r["lean_meetings"]),
                "public_against_meetings": int(r["public_against_meetings"] or 0),
                "public_against_states": int(r.get("public_against_states") or 0),
                "public_for_meetings": int(r["public_for_meetings"] or 0) if r.get("has_public_for") else None,
                "disagreement_meetings": int(r["disagreement_meetings"] or 0),
                "disagreement_states": int(r["disagreement_states"] or 0),
            }

    wider: list[CaptionWiderLean] | None = None
    if wider_rows:
        wider = [
            w
            for lvl, code, rows in wider_rows
            if (w := wider_lean(lvl, code, state_name if code else None, rows[0] if rows else None))
        ]

    return TopicCaptionFacts(
        topic=query_id,
        topic_id=topic_id,
        scope=CaptionScope(
            level="city" if city_clean else ("state" if state_code else "national"),
            state_code=state_code,
            state=state_name,
            city=city_clean,
        ),
        meetings=meetings,
        states=states,
        top_state=top_state,
        ratio_to_next=ratio,
        place=place,
        places=places,
        speakers=speakers,
        wider=wider,
        **lean,
    )
