"""
Civic-topic catalog API — GET /api/topics.

Serves the CivicSearch topic taxonomy (public.civicsearch_topic): a small,
fixed list (~75 rows) of named topics, each with its query slug and the
keyword set used to recall it. Reads the published serving view over gold
(resolves as public.civicsearch_topic / gold.civicsearch_topic via the
connection search_path, matching the other routes).

asyncpg gotcha: the pool has no JSONB codec, so `keyword_stats` arrives as a
TEXT blob and must be json.loads()'d before it is a real list.
"""
from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, Query
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


# Sorted by transcript occurrences (most-discussed first) so the browse flyout's
# top-N is the topics that actually come up most in the record; name breaks ties.
# keyword_stats is JSONB (returned as TEXT by this pool) — parsed below.
#
# THREE place grains, each surfacing a count that matches the selected place so
# the displayed number actually changes as the user narrows/broadens:
#
#   NATIONAL (no place): the full catalog, count = civicsearch_topic's own global
#   transcript_occurrences column.
#
#   STATE ($2 set, no city): INNER JOIN browse_entity_state_transcript_count to
#   both restrict to topics discussed in that state AND surface that state's
#   per-topic transcript_count as the count.
#
#   CITY ($2 + $3 set): INNER JOIN browse_entity_place_transcript_count (the
#   city-grain sibling) to restrict to the one jurisdiction and surface its
#   city-scoped transcript_count. City needs the state too — jurisdiction_name is
#   only unique within a state.
#
# All three sort by the count they surface, so the top-N pills are the
# most-discussed topics AT THE SELECTED GRAIN, not nationally.
_TOPICS_SQL_NATIONAL = """
    SELECT topic_id, name, query_id, keyword_stats, transcript_occurrences
    FROM civicsearch_topic t
    WHERE ($1::text IS NULL OR name ILIKE $1)
    ORDER BY transcript_occurrences DESC NULLS LAST, name ASC
"""

_TOPICS_SQL_STATE = """
    SELECT t.topic_id, t.name, t.query_id, t.keyword_stats,
           b.transcript_count AS transcript_occurrences
    FROM civicsearch_topic t
    JOIN browse_entity_state_transcript_count b
      ON b.entity_type = 'topic'
     AND b.entity_id = t.topic_id::text
     AND b.state_code = $2::text
    WHERE ($1::text IS NULL OR t.name ILIKE $1)
    ORDER BY b.transcript_count DESC NULLS LAST, t.name ASC
"""

_TOPICS_SQL_CITY = """
    SELECT t.topic_id, t.name, t.query_id, t.keyword_stats,
           b.transcript_count AS transcript_occurrences
    FROM civicsearch_topic t
    JOIN browse_entity_place_transcript_count b
      ON b.entity_type = 'topic'
     AND b.entity_id = t.topic_id::text
     AND b.state_code = $2::text
     AND lower(b.jurisdiction_name) = lower($3::text)
    WHERE ($1::text IS NULL OR t.name ILIKE $1)
    ORDER BY b.transcript_count DESC NULLS LAST, t.name ASC
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
    city: Optional[str] = Query(None, description="Optional jurisdiction/city name; with `state`, restricts to topics discussed in that one city and surfaces the city-scoped count."),
) -> List[TopicSummary]:
    """Civic topics (most-discussed first), optionally narrowed by a name
    substring and scoped to a place. The surfaced count matches the place grain:
    national catalog count, per-state count, or per-city count."""
    with tracer.start_as_current_span("topics-list") as span:
        span.set_attribute("topics.q", (q or "").strip())
        like = f"%{q.strip()}%" if q and q.strip() else None
        # Normalize to the 2-letter upper-case form the bridge stores; blank -> None.
        state_code = state.strip().upper() if state and state.strip() else None
        city_name = city.strip() if city and city.strip() else None
        span.set_attribute("topics.state", state_code or "")
        span.set_attribute("topics.city", city_name or "")
        # Pick the grain: city needs a state (jurisdiction_name is only unique
        # within a state), so a city without a state falls back to national.
        if state_code and city_name:
            sql, params = _TOPICS_SQL_CITY, (like, state_code, city_name)
        elif state_code:
            sql, params = _TOPICS_SQL_STATE, (like, state_code)
        else:
            sql, params = _TOPICS_SQL_NATIONAL, (like,)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("topics-query"):
                    rows = await conn.fetch(sql, *params)
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
            )
            for r in rows
        ]
