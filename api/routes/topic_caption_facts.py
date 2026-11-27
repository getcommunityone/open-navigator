"""Caption facts for a topic story or tile (#1125): ``GET /api/topics/{topic}/caption-facts?state=&city=``.

The web caption picker (``web_app/src/utils/storyCaption.ts``) chooses the strongest statement the record supports for
one topic and one scope (national, state or city). This route only gathers the real counts it chooses from:

- meetings in scope, and meetings per state for the whole country (never narrowed, so a state can be ranked), each state
  with its population when ``jurisdictions`` has it on record;
- for a city scope, meetings per place in that state, so the city can be ranked among its neighbours;
- for data centers, the counted speakers for and against and the recorded votes (``data_center_meeting_position``,
  #1289), with how many meetings were reviewed;
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
    meetings_reviewed: int = Field(
        0, description="Meetings in scope reviewed by hand (#1289): 0 speakers here means nobody spoke in these meetings."
    )

    model_config = {"populate_by_name": True}


class CaptionVotes(BaseModel):
    """Recorded votes in scope (#1289), so the stance headline is checked against what officials voted."""

    decisions: int = Field(0, description="Decisions with a recorded tally in scope.")
    for_: int = Field(0, alias="for", description="Votes for, summed over those decisions.")
    against: int = Field(0, description="Votes against, summed over those decisions.")
    decisions_for: int | None = Field(
        None,
        description="#1290: decisions whose vote went for the data center (with these, decisions / for / against are read "
        "from data_center_decision too) (data_center_decision.vote_side); null when "
        "that column or table isn't in this database.",
    )
    decisions_against: int | None = Field(
        None, description="#1290: decisions whose vote went against it (vote_side); null when not available."
    )

    model_config = {"populate_by_name": True}


class CaptionComments(BaseModel):
    """Public comments segmented from our own captions in scope (#1290, ``data_center_comment``), all years. Their side
    isn't classified yet, so they never set a stance; they say people spoke where no side was counted."""

    comments: int = Field(0, description="Public comments on a data center item found in our captions.")
    governments: int = Field(0, description="Local governments those comments were made at.")


class CaptionWiderLean(BaseModel):
    """One broader scope's AI reading (#1182), so a place too thin for its own reading can name the scope the map colours."""

    level: str = Field(..., description="state or national.")
    state_code: str | None = None
    state: str | None = None
    lean_meetings: int
    public_against_meetings: int
    public_against_states: int
    public_for_meetings: int = 0
    public_split_meetings: int = 0
    public_silent_meetings: int = 0
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
    votes: CaptionVotes | None = Field(
        None, description="Recorded votes in scope (data centers only, #1289); null when no meeting in scope was reviewed."
    )
    caption_comments: CaptionComments | None = Field(
        None, description="#1290: public comments from our captions in scope (data centers only); null when not available."
    )
    lean_meetings: int | None = Field(None, description="Meetings in scope with an AI reading (Jev); null when none loaded.")
    public_against_meetings: int | None = Field(
        None, description="AI reading: meetings where the public mostly opposed. Null when not loaded."
    )
    public_against_states: int | None = Field(
        None, description="AI reading: states with at least one public-against meeting in scope (#1134). Null when not loaded."
    )
    public_for_meetings: int | None = Field(
        None, description="AI reading: meetings where the public mostly supported (P >= 0.7). Null when not loaded."
    )
    public_split_meetings: int | None = Field(
        None,
        description=(
            "AI reading (#1200): meetings where the public spoke but was split, or the reading was not sure which way "
            "(mixed, or a lean under P 0.7). Null when not loaded."
        ),
    )
    public_silent_meetings: int | None = Field(
        None, description="AI reading (#1200): meetings read where the public didn't speak on the topic. Null when not loaded."
    )
    disagreement_meetings: int | None = Field(
        None, description="AI reading: meetings where officials sided against the public. Null when not loaded."
    )
    disagreement_states: int | None = Field(None, description="States with at least one disagreement meeting in scope.")
    official_against_meetings: int | None = Field(
        None, description="#1330 reading: meetings where officials mostly opposed (P >= 0.7). Null when not loaded."
    )
    official_for_meetings: int | None = Field(
        None, description="#1330 reading: meetings where officials mostly supported (P >= 0.7). Null when not loaded."
    )
    official_divided_meetings: int | None = Field(
        None, description="#1330 reading: meetings where officials were divided or mixed, or leaned under P 0.7."
    )
    position_meetings: int | None = Field(
        None,
        description="#1330: meetings with any recorded position, public (against, for or split) or official. Null when "
        "not loaded.",
    )
    both_position_meetings: int | None = Field(
        None, description="#1330: meetings where both the public and officials took a position. Null when not loaded."
    )
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
    "+ p.speakers_neutral > 0)::int AS states, "
    "coalesce(sum(p.decisions_with_tally), 0)::int AS decisions_with_tally, "
    "coalesce(sum(p.votes_for), 0)::int AS votes_for, coalesce(sum(p.votes_against), 0)::int AS votes_against "
    "FROM data_center_meeting_position p "
    "WHERE ($1::text IS NULL OR p.state_code = $1::text) AND ($2::text IS NULL OR p.jurisdiction_name ILIKE $2::text)"
)


# #1290: which way each tallied vote went (data_center_decision.vote_side, dbt), read defensively so a serving copy
# without the column still answers (has_side false: sides null).
VOTE_SIDES_SQL = (
    "SELECT count(*)::int AS decisions_tallied, sum(d.votes_for)::int AS yes_votes, sum(d.votes_against)::int AS no_votes, "
    "count(*) FILTER (WHERE to_jsonb(d) ->> 'vote_side' = 'for')::int AS decisions_for, "
    "count(*) FILTER (WHERE to_jsonb(d) ->> 'vote_side' = 'against')::int AS decisions_against, "
    "coalesce(bool_or(to_jsonb(d) ? 'vote_side'), false) AS has_side "
    "FROM data_center_decision d WHERE d.votes_for IS NOT NULL AND d.votes_against IS NOT NULL "
    "AND ($1::text IS NULL OR d.state_code = $1::text) AND ($2::text IS NULL OR d.jurisdiction_name ILIKE $2::text)"
)
CAPTION_COMMENTS_SQL = (
    "SELECT count(*)::int AS comments, count(DISTINCT c.jurisdiction_id)::int AS governments "
    "FROM data_center_comment c "
    "WHERE ($1::text IS NULL OR c.state_code = $1::text) AND ($2::text IS NULL OR c.jurisdiction_name ILIKE $2::text)"
)


def vote_sides(rows: list[Any] | None, decisions: int) -> tuple[int | None, int | None]:
    """(for, against) decisions by vote_side; (None, None) when the read failed or the column isn't there (unless there
    is no tallied decision at all, which is a real 0 each)."""
    if rows is None:
        return None, None
    r = dict(rows[0]) if rows else {}
    if not r.get("has_side"):
        return (0, 0) if decisions == 0 else (None, None)
    return int(r.get("decisions_for") or 0), int(r.get("decisions_against") or 0)


# The four positions of one meeting's AI reading (#1200), the same for both lean marts (their ``public_lean`` labels
# differ only in spelling): against = ``public_against`` (mostly opposed, P >= 0.7); for = mostly supportive, P >= 0.7;
# silent = the public didn't speak on the topic; split = mixed, or a for/against lean under P 0.7. A label outside the
# question's choices (an older or broken writer, #1201) is in none of the four: never shown as a position.
PUBLIC_FOR_SQL = (
    "l.public_lean IN ('mostly_supportive', 'mostly_supported') AND coalesce(l.public_lean_p, 0) >= 0.7"
)
PUBLIC_SILENT_SQL = "l.public_lean IN ('did_not_speak', 'no_public_comment_on_data_center')"
PUBLIC_SPLIT_SQL = (
    "(l.public_lean = 'mixed' OR (l.public_lean IN ('mostly_opposed', 'mostly_supportive', 'mostly_supported') "
    "AND coalesce(l.public_lean_p, 0) < 0.7))"
)


# #1330: officials' position in the same reading (``official_lean`` / ``official_lean_p``), on the same P >= 0.7 rule as the
# public's. against = mostly opposed; for = mostly supportive; divided = divided or mixed, or a lean under P 0.7. "No
# official position", "no opinion" and "did not speak" are no position. A meeting has a position when the public took one
# (against, for or split) or the officials did.
OFFICIAL_AGAINST_SQL = "l.official_lean = 'mostly_opposed' AND coalesce(l.official_lean_p, 0) >= 0.7"
OFFICIAL_FOR_SQL = (
    "l.official_lean IN ('mostly_supportive', 'mostly_supported') AND coalesce(l.official_lean_p, 0) >= 0.7"
)
OFFICIAL_DIVIDED_SQL = (
    "(l.official_lean IN ('divided', 'mixed') OR (l.official_lean IN ('mostly_opposed', 'mostly_supportive', "
    "'mostly_supported') AND coalesce(l.official_lean_p, 0) < 0.7))"
)
OFFICIAL_ANY_SQL = f"(({OFFICIAL_AGAINST_SQL}) OR ({OFFICIAL_FOR_SQL}) OR {OFFICIAL_DIVIDED_SQL})"
PUBLIC_ANY_SQL = f"(l.public_against OR ({PUBLIC_FOR_SQL}) OR {PUBLIC_SPLIT_SQL})"


def split_count(row: dict[str, Any]) -> int:
    """Meetings read as split (counted in SQL; 0 when absent)."""
    return int(row.get("public_split_meetings") or 0)


def build_lean_sql(topic_id: int, state_code: str | None, city_like: str | None) -> tuple[str, list[Any]]:
    """AI-reading counts in scope. Data centers read ``data_center_meeting_lean``; other topics ``topic_meeting_lean``
    (#1126, one row per meeting x topic). Both carry ``public_lean`` and ``public_lean_p``, which the for and silent
    counts read (#1200)."""
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
        f"count(*) FILTER (WHERE {PUBLIC_FOR_SQL})::int AS public_for_meetings, "
        f"count(*) FILTER (WHERE {PUBLIC_SILENT_SQL})::int AS public_silent_meetings, "
        f"count(*) FILTER (WHERE {PUBLIC_SPLIT_SQL})::int AS public_split_meetings, "
        "count(*) FILTER (WHERE l.officials_sided_against_public)::int AS disagreement_meetings, "
        "count(DISTINCT l.state_code) FILTER (WHERE l.officials_sided_against_public)::int AS disagreement_states, "
        f"count(*) FILTER (WHERE {OFFICIAL_AGAINST_SQL})::int AS official_against_meetings, "
        f"count(*) FILTER (WHERE {OFFICIAL_FOR_SQL})::int AS official_for_meetings, "
        f"count(*) FILTER (WHERE {OFFICIAL_DIVIDED_SQL})::int AS official_divided_meetings, "
        f"count(*) FILTER (WHERE {PUBLIC_ANY_SQL} OR {OFFICIAL_ANY_SQL})::int AS position_meetings, "
        f"count(*) FILTER (WHERE {PUBLIC_ANY_SQL} AND {OFFICIAL_ANY_SQL})::int AS both_position_meetings "
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
        public_for_meetings=int(r.get("public_for_meetings") or 0),
        public_split_meetings=split_count(r),
        public_silent_meetings=int(r.get("public_silent_meetings") or 0),
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
                side_rows = (
                    await _optional(conn, "data_center_decision", VOTE_SIDES_SQL, state_code, city_like) if is_dc else None
                )
                comment_rows = (
                    await _optional(conn, "data_center_comment", CAPTION_COMMENTS_SQL, state_code, city_like)
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
    votes: CaptionVotes | None = None
    if speaker_rows:
        r = dict(speaker_rows[0])
        if int(r.get("meetings_reviewed") or 0) > 0:
            speakers = CaptionSpeakers(
                for_=int(r["for_"] or 0), against=int(r["against"] or 0),
                question=int(r["question"] or 0), neutral=int(r["neutral"] or 0),
                states=int(r.get("states") or 0),
                meetings_reviewed=int(r.get("meetings_reviewed") or 0),
            )
            n_dec = int(r.get("decisions_with_tally") or 0)
            yes, no = int(r.get("votes_for") or 0), int(r.get("votes_against") or 0)
            d_for, d_against = vote_sides(side_rows, n_dec)
            if d_for is not None and side_rows:
                # #1290: with the sides, every vote count comes from data_center_decision (the preferred analysis), so
                # "N decisions" and "k of N went for" never count from two marts.
                sr = dict(side_rows[0])
                n_dec = int(sr.get("decisions_tallied") or 0)
                yes, no = int(sr.get("yes_votes") or 0), int(sr.get("no_votes") or 0)
            votes = CaptionVotes(
                decisions=n_dec,
                for_=yes,
                against=no,
                decisions_for=d_for,
                decisions_against=d_against,
            )

    caption_comments: CaptionComments | None = None
    if comment_rows is not None:
        r = dict(comment_rows[0]) if comment_rows else {}
        caption_comments = CaptionComments(comments=int(r.get("comments") or 0), governments=int(r.get("governments") or 0))

    lean: dict[str, Any] = {}
    if lean_rows:
        r = dict(lean_rows[0])
        if int(r.get("lean_meetings") or 0) == 0:
            # Read fine, nothing read yet (#1200): 0, so the page can say "no reading yet". A failed read stays null.
            lean = {"lean_meetings": 0}
        if int(r.get("lean_meetings") or 0) > 0:
            lean = {
                "lean_meetings": int(r["lean_meetings"]),
                "public_against_meetings": int(r["public_against_meetings"] or 0),
                "public_against_states": int(r.get("public_against_states") or 0),
                "public_for_meetings": int(r.get("public_for_meetings") or 0),
                "public_split_meetings": split_count(r),
                "public_silent_meetings": int(r.get("public_silent_meetings") or 0),
                "disagreement_meetings": int(r["disagreement_meetings"] or 0),
                "disagreement_states": int(r["disagreement_states"] or 0),
            }
            # #1330: officials' position and the meetings with any position; left out (null) on an older reading
            # without the columns, never a 0 that would read as "none".
            for k in ("official_against_meetings", "official_for_meetings", "official_divided_meetings",
                      "position_meetings", "both_position_meetings"):
                if r.get(k) is not None:
                    lean[k] = int(r[k])

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
        votes=votes,
        caption_comments=caption_comments,
        wider=wider,
        **lean,
    )
