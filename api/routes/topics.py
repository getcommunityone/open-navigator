"""
Civic-topic catalog API — GET /api/topics.

Serves the topic taxonomy (public.civicsearch_topic): a small, fixed list of
named topics, each with its query slug and the keyword set used to recall it.
Most are CivicSearch's (~75); a few are hand-curated (source = 'curated',
topic_id >= 100000, e.g. "Data centers", issue #500).

GET /api/topics/{topic_id}/meetings lists the meetings a curated topic's
keywords matched, each with a stored, highlighted verbatim passage
(public.topic_transcript_link, cut in dbt because production event_documents
carries no transcript content, #496). Reads the published serving view over gold
(resolves as public.civicsearch_topic / gold.civicsearch_topic via the
connection search_path, matching the other routes).

asyncpg gotcha: the pool has no JSONB codec, so `keyword_stats` arrives as a
TEXT blob and must be json.loads()'d before it is a real list.
"""
from __future__ import annotations

import json
from typing import Any, List, Optional

import asyncpg

from fastapi import APIRouter, HTTPException, Path, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/api/topics", tags=["topics"])
tracer = trace.get_tracer(__name__)


class TopicSummary(BaseModel):
    topic_id: int
    name: str
    query_id: Optional[str] = None
    keywords: List[str] = []
    # How many CivicSearch transcript snippets are tagged with this topic — the
    # "how often it comes up" signal the catalog is sorted by (desc).
    transcript_occurrences: int = 0
    # 'civicsearch' (CivicSearch taxonomy) or 'curated' (hand-authored, #500).
    source: str = "civicsearch"
    # Meetings (transcripts) whose text matched the topic, in the requested scope:
    # national / state / city (state+city → place grain). None = no count row.
    meeting_count: Optional[int] = None


# Sorted by transcript occurrences (most-discussed first) so the browse flyout's
# top-N is the topics that actually come up most in the record; name breaks ties.
# keyword_stats is JSONB (returned as TEXT by this pool) — parsed below.
#
# $2 = optional 2-letter state code. $3 = optional city / jurisdiction ILIKE
# pattern (e.g. '%Atlanta%'); $4 = the bare city, to prefer an exact name match. When $3 is set, meeting_count and the existence
# filter come from browse_entity_place_transcript_count (city grain, #590).
# Otherwise: browse_transcript_count (national) or browse_entity_state_… ($2).
_TOPICS_SQL = """
    SELECT t.topic_id, t.name, t.query_id, t.keyword_stats, t.transcript_occurrences,
           -- Defensive read: works before the `source` column reaches Neon.
           to_jsonb(t) ->> 'source' AS source,
           CASE
                WHEN $3::text IS NOT NULL THEN (
                    -- One place (#1026): "%Tuscaloosa%" also matches "Tuscaloosa City School District", and a
                    -- scalar subquery with two rows errors. Prefer the exact city name ($4), then the most meetings.
                    SELECT p.transcript_count FROM browse_entity_place_transcript_count p
                    WHERE p.entity_type = 'topic' AND p.entity_id = t.topic_id::text
                      AND p.state_code = $2::text
                      AND p.jurisdiction_name ILIKE $3::text
                    ORDER BY (lower(p.jurisdiction_name) = lower($4::text)) DESC, p.transcript_count DESC
                    LIMIT 1
                )
                WHEN $2::text IS NULL THEN (
                    SELECT n.transcript_count FROM browse_transcript_count n
                    WHERE n.entity_type = 'topic' AND n.entity_id = t.topic_id::text
                ) ELSE (
                    SELECT s.transcript_count FROM browse_entity_state_transcript_count s
                    WHERE s.entity_type = 'topic' AND s.entity_id = t.topic_id::text
                      AND s.state_code = $2::text
                ) END AS meeting_count
    FROM civicsearch_topic t
    WHERE ($1::text IS NULL OR t.name ILIKE $1)
      AND ($2::text IS NULL OR $3::text IS NOT NULL OR EXISTS (
            SELECT 1 FROM browse_entity_state_transcript_count b
            WHERE b.entity_type = 'topic'
              AND b.entity_id = t.topic_id::text
              AND b.state_code = $2::text
      ))
      AND ($3::text IS NULL OR EXISTS (
            SELECT 1 FROM browse_entity_place_transcript_count bp
            WHERE bp.entity_type = 'topic'
              AND bp.entity_id = t.topic_id::text
              AND bp.state_code = $2::text
              AND bp.jurisdiction_name ILIKE $3::text
      ))
    ORDER BY t.transcript_occurrences DESC NULLS LAST, t.name ASC
"""


def _parse_keywords(raw) -> List[str]:
    """Coerce the JSONB keyword_stats column into a clean list[str].

    The pool hands JSONB back as a TEXT string, so json.loads it; tolerate an
    already-parsed list, a null, or malformed JSON (-> empty list) rather than
    500-ing the whole catalog over one bad row.
    """
    if raw is None:
        return []
    if isinstance(raw, list):
        return [str(k) for k in raw]
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if isinstance(parsed, list):
        return [str(k) for k in parsed]
    return []


@router.get("", response_model=List[TopicSummary])
async def list_topics(
    q: Optional[str] = Query(None, description="Optional case-insensitive substring filter on topic name."),
    state: Optional[str] = Query(None, description="Optional 2-letter state code; restricts to topics discussed in that state."),
    city: Optional[str] = Query(
        None,
        description="Optional city / jurisdiction name; with state, meeting_count is city grain (#590).",
    ),
) -> List[TopicSummary]:
    """Civic topics (most-discussed first), optionally narrowed by name, state,
    and/or city (city grain uses browse_entity_place_transcript_count)."""
    with tracer.start_as_current_span("topics-list") as span:
        span.set_attribute("topics.q", (q or "").strip())
        like = f"%{q.strip()}%" if q and q.strip() else None
        # Normalize to the 2-letter upper-case form the bridge stores; blank -> None.
        state_code = state.strip().upper() if state and state.strip() else None
        city_like = f"%{city.strip()}%" if city and city.strip() else None
        # City grain needs a state; ignore a lone city rather than invent a scope.
        if city_like and not state_code:
            city_like = None
        span.set_attribute("topics.state", state_code or "")
        span.set_attribute("topics.city", (city or "").strip())
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("topics-query"):
                    rows = await conn.fetch(
                        _TOPICS_SQL, like, state_code, city_like, (city or '').strip() if city_like else None
                    )
        except Exception as exc:  # noqa: BLE001
            logger.exception("topics list failed")
            span.record_exception(exc)
            # A failed query is not "no topics": say so, so Browse Topics shows
            # "Couldn't load topics" instead of a blank row and a dead dropdown.
            raise HTTPException(status_code=503, detail="Topics are unavailable right now.") from exc

        span.set_attribute("topics.count", len(rows))
        return [
            TopicSummary(
                topic_id=r["topic_id"],
                name=r["name"],
                query_id=r["query_id"],
                keywords=_parse_keywords(r["keyword_stats"]),
                transcript_occurrences=r["transcript_occurrences"] or 0,
                source=r["source"] or "civicsearch",
                meeting_count=r["meeting_count"],
            )
            for r in rows
        ]


class TopicMeeting(BaseModel):
    video_id: str
    title: Optional[str] = None
    # Bare ISO date string (YYYY-MM-DD) or None.
    date: Optional[str] = None
    state_code: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    video_url: Optional[str] = None
    # Verbatim transcript passage with the matched words wrapped in <mark>…</mark>
    # (render with highlightSnippet, never as raw HTML).
    excerpt: Optional[str] = None
    n_keyword_hits: int = 0


class TopicMeetingList(BaseModel):
    topic_id: int
    total: int
    items: List[TopicMeeting]


_TOPIC_MEETINGS_WHERE = """
    WHERE l.topic_id = $1
      AND ($2::text IS NULL OR l.state_code = $2::text)
      AND ($3::text IS NULL OR l.city ILIKE $3::text OR l.jurisdiction_name ILIKE $3::text)
"""

_TOPIC_MEETINGS_SQL = f"""
    SELECT l.video_id, l.event_title, l.event_date, l.state_code, l.state, l.city,
           l.jurisdiction_name, l.video_url, l.evidence_passage, l.n_keyword_hits
    FROM topic_transcript_link l
    {_TOPIC_MEETINGS_WHERE}
    ORDER BY l.event_date DESC NULLS LAST, l.n_keyword_hits DESC, l.video_id
    LIMIT $4 OFFSET $5
"""

_TOPIC_MEETINGS_COUNT_SQL = f"""
    SELECT count(*) FROM topic_transcript_link l
    {_TOPIC_MEETINGS_WHERE}
"""


@router.get("/{topic_id}/meetings", response_model=TopicMeetingList)
async def list_topic_meetings(
    topic_id: int = Path(..., description="Topic id (curated topics have meeting links)."),
    state: Optional[str] = Query(None, description="Optional 2-letter state code."),
    city: Optional[str] = Query(None, description="Optional city / jurisdiction name (ILIKE)."),
    limit: int = Query(12, ge=1, le=60, description="Page size (1..60)."),
    offset: int = Query(0, ge=0, description="Pagination offset."),
) -> TopicMeetingList:
    """Meetings whose transcript matched a curated topic's keywords, newest
    first, each with its highlighted verbatim passage. Empty (total 0) for a
    topic without stored links (the CivicSearch topics) or an empty scope."""
    with tracer.start_as_current_span("topic-meetings") as span:
        state_code = state.strip().upper() if state and state.strip() else None
        city_like = f"%{city.strip()}%" if city and city.strip() else None
        span.set_attribute("topics.topic_id", topic_id)
        span.set_attribute("topics.state", state_code or "")
        span.set_attribute("topics.city", (city or "").strip())
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                total = await conn.fetchval(
                    _TOPIC_MEETINGS_COUNT_SQL, topic_id, state_code, city_like
                )
                rows = await conn.fetch(
                    _TOPIC_MEETINGS_SQL, topic_id, state_code, city_like, limit, offset
                )
        except Exception as exc:  # noqa: BLE001
            logger.exception("topic meetings failed")
            span.record_exception(exc)
            # A failed query is not "no meetings" (#816): the list component shows its error state.
            raise HTTPException(
                status_code=503, detail="Meetings for this topic are unavailable right now."
            ) from exc

        span.set_attribute("topics.meetings_total", int(total or 0))
        return TopicMeetingList(
            topic_id=topic_id,
            total=int(total or 0),
            items=[
                TopicMeeting(
                    video_id=r["video_id"],
                    title=r["event_title"],
                    date=r["event_date"].isoformat() if r["event_date"] else None,
                    state_code=r["state_code"],
                    state=r["state"],
                    city=r["city"],
                    jurisdiction_name=r["jurisdiction_name"],
                    video_url=r["video_url"],
                    excerpt=r["evidence_passage"],
                    n_keyword_hits=r["n_keyword_hits"] or 0,
                )
                for r in rows
            ],
        )


class TopicStateCount(BaseModel):
    state_code: str
    state: Optional[str] = None
    # Distinct meetings (videos) in the state whose transcript matched the topic.
    meetings: int


class TopicStates(BaseModel):
    topic_id: int
    # Distinct meetings in scope (all states, or the one state asked for).
    total_meetings: int
    states: List[TopicStateCount]
    # The newest matched meeting per state, with its verbatim passage (<mark>ed).
    newest: List[TopicMeeting]


_TOPIC_STATES_SQL = """
    SELECT l.state_code, max(l.state) AS state, count(DISTINCT l.video_id) AS meetings
    FROM topic_transcript_link l
    WHERE l.topic_id = $1 AND l.state_code IS NOT NULL
      AND ($2::text IS NULL OR l.state_code = $2::text)
    GROUP BY l.state_code
    ORDER BY meetings DESC, l.state_code
"""

_TOPIC_NEWEST_PER_STATE_SQL = """
    SELECT DISTINCT ON (l.state_code)
           l.video_id, l.event_title, l.event_date, l.state_code, l.state, l.city,
           l.jurisdiction_name, l.video_url, l.evidence_passage, l.n_keyword_hits
    FROM topic_transcript_link l
    WHERE l.topic_id = $1 AND l.state_code IS NOT NULL AND l.evidence_passage IS NOT NULL
      AND ($2::text IS NULL OR l.state_code = $2::text)
    ORDER BY l.state_code, l.event_date DESC NULLS LAST, l.n_keyword_hits DESC
"""


class TopicStanceStateCount(BaseModel):
    """One state's meetings and the AI reading of them (#1127). The counts are distinct meetings in
    ``topic_meeting_lean`` (#1126), never counted speakers; 0 where the state has no reading."""

    state_code: str
    state: Optional[str] = None
    # Distinct meetings in the state whose transcript matched the topic (topic_transcript_link).
    meetings: int
    # Meetings the AI read for this topic in the state.
    lean_meetings: int = 0
    public_against_meetings: int = 0
    public_for_meetings: int = 0
    # Read as split: the public neither mostly supported nor mostly opposed.
    no_side_meetings: int = 0
    # The public mostly opposed while officials mostly supported it (same rule as data centers).
    disagreement_meetings: int = 0


class TopicStanceMap(BaseModel):
    topic_id: int
    # False when topic_meeting_lean isn't in this database yet or has no row for the topic: the map shows
    # meetings only and says so. Never a 0 that would read as "the public took no side anywhere".
    available: bool
    by_state: List[TopicStanceStateCount]


_TOPIC_LEAN_BY_STATE_SQL = """
    SELECT l.state_code,
           count(*)::int AS lean_meetings,
           count(*) FILTER (WHERE l.public_against)::int AS public_against_meetings,
           count(*) FILTER (WHERE (to_jsonb(l) ->> 'public_for')::boolean)::int AS public_for_meetings,
           count(*) FILTER (
               WHERE to_jsonb(l) ->> 'public_lean' = 'mixed'
                 AND NOT coalesce(l.public_against, false)
                 AND NOT coalesce((to_jsonb(l) ->> 'public_for')::boolean, false)
           )::int AS no_side_meetings,
           count(*) FILTER (WHERE l.officials_sided_against_public)::int AS disagreement_meetings
    FROM topic_meeting_lean l
    WHERE l.topic_id = $1 AND l.state_code IS NOT NULL
      AND ($2::text IS NULL OR l.state_code = $2::text)
    GROUP BY l.state_code
"""


def merge_stance_by_state(
    counts: List[Any], lean: Optional[List[Any]]
) -> tuple[bool, List[TopicStanceStateCount]]:
    """Meetings per state with each state's AI-reading counts. ``lean`` is None when the table can't be read."""
    lean_by = {r["state_code"]: r for r in (lean or [])}
    out: List[TopicStanceStateCount] = []
    for r in counts:
        lr = lean_by.get(r["state_code"])
        out.append(
            TopicStanceStateCount(
                state_code=r["state_code"],
                state=r["state"],
                meetings=int(r["meetings"]),
                lean_meetings=int(lr["lean_meetings"]) if lr else 0,
                public_against_meetings=int(lr["public_against_meetings"]) if lr else 0,
                public_for_meetings=int(lr["public_for_meetings"]) if lr else 0,
                no_side_meetings=int(lr["no_side_meetings"]) if lr else 0,
                disagreement_meetings=int(lr["disagreement_meetings"]) if lr else 0,
            )
        )
    return bool(lean), out


@router.get("/{topic_id}/state-map", response_model=TopicStanceMap)
async def topic_state_map(
    topic_id: int = Path(..., description="Topic id (curated topics have meeting links)."),
    state: Optional[str] = Query(None, description="Optional 2-letter state code."),
) -> TopicStanceMap:
    """Meetings per state for a topic story's box map, with the AI reading of those meetings (#1127): how many the
    public mostly opposed, mostly supported or was split on, from ``topic_meeting_lean`` (#1126). Until that table has the
    topic, ``available`` is false and the map shows meetings only."""
    with tracer.start_as_current_span("topic-state-map") as span:
        state_code = state.strip().upper() if state and state.strip() else None
        span.set_attribute("topics.topic_id", topic_id)
        span.set_attribute("topics.state", state_code or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                counts = await conn.fetch(_TOPIC_STATES_SQL, topic_id, state_code)
                try:
                    lean: Optional[List[Any]] = list(await conn.fetch(_TOPIC_LEAN_BY_STATE_SQL, topic_id, state_code))
                except asyncpg.exceptions.PostgresError as e:
                    # Not built yet (#1126) or a column is missing: meetings only, never a 500.
                    logger.warning("topic state-map: topic_meeting_lean unavailable ({}); meetings only", e)
                    lean = None
        except Exception as exc:  # noqa: BLE001
            logger.exception("topic state-map failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This topic's map is unavailable right now.") from exc
        available, by_state = merge_stance_by_state(list(counts), lean)
        span.set_attribute("topics.lean_available", available)
        return TopicStanceMap(topic_id=topic_id, available=available, by_state=by_state)


@router.get("/{topic_id}/states", response_model=TopicStates)
async def topic_states(
    topic_id: int = Path(..., description="Topic id (curated topics have meeting links)."),
    state: Optional[str] = Query(None, description="Optional 2-letter state code."),
) -> TopicStates:
    """Meetings per state for a curated topic, and each state's newest matched passage (#1013): the data behind a
    topic story's map and headline. Counts are distinct meetings; nothing is estimated."""
    with tracer.start_as_current_span("topic-states") as span:
        state_code = state.strip().upper() if state and state.strip() else None
        span.set_attribute("topics.topic_id", topic_id)
        span.set_attribute("topics.state", state_code or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                counts = await conn.fetch(_TOPIC_STATES_SQL, topic_id, state_code)
                newest = await conn.fetch(_TOPIC_NEWEST_PER_STATE_SQL, topic_id, state_code)
        except Exception as exc:  # noqa: BLE001
            logger.exception("topic states failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="This topic's map is unavailable right now.") from exc
        states = [TopicStateCount(state_code=r["state_code"], state=r["state"], meetings=int(r["meetings"])) for r in counts]
        span.set_attribute("topics.states", len(states))
        return TopicStates(
            topic_id=topic_id,
            total_meetings=sum(s.meetings for s in states),
            states=states,
            newest=[
                TopicMeeting(
                    video_id=r["video_id"],
                    title=r["event_title"],
                    date=r["event_date"].isoformat() if r["event_date"] else None,
                    state_code=r["state_code"],
                    state=r["state"],
                    city=r["city"],
                    jurisdiction_name=r["jurisdiction_name"],
                    video_url=r["video_url"],
                    excerpt=r["evidence_passage"],
                    n_keyword_hits=r["n_keyword_hits"] or 0,
                )
                for r in newest
            ],
        )
