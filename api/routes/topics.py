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
from typing import List, Optional

from fastapi import APIRouter, Path, Query
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
# pattern (e.g. '%Atlanta%'). When $3 is set, meeting_count and the existence
# filter come from browse_entity_place_transcript_count (city grain, #590).
# Otherwise: browse_transcript_count (national) or browse_entity_state_… ($2).
_TOPICS_SQL = """
    SELECT t.topic_id, t.name, t.query_id, t.keyword_stats, t.transcript_occurrences,
           -- Defensive read: works before the `source` column reaches Neon.
           to_jsonb(t) ->> 'source' AS source,
           CASE
                WHEN $3::text IS NOT NULL THEN (
                    SELECT p.transcript_count FROM browse_entity_place_transcript_count p
                    WHERE p.entity_type = 'topic' AND p.entity_id = t.topic_id::text
                      AND p.state_code = $2::text
                      AND p.jurisdiction_name ILIKE $3::text
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
                    rows = await conn.fetch(_TOPICS_SQL, like, state_code, city_like)
        except Exception as exc:  # noqa: BLE001
            logger.exception("topics list failed")
            span.record_exception(exc)
            # Empty list over a 500 — the frontend renders an empty state.
            return []

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
            return TopicMeetingList(topic_id=topic_id, total=0, items=[])

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
