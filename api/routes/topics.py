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
# $2 = optional 2-letter state code. When given, restrict to topics actually
# discussed in that state via browse_entity_state_transcript_count (the per-state
# bridge) — this is what lets the homepage "Browse topics" land pre-filtered to
# the user's selected place. NULL state = the full national catalog.
_TOPICS_SQL = """
    SELECT topic_id, name, query_id, keyword_stats, transcript_occurrences
    FROM civicsearch_topic t
    WHERE ($1::text IS NULL OR name ILIKE $1)
      AND ($2::text IS NULL OR EXISTS (
            SELECT 1 FROM browse_entity_state_transcript_count b
            WHERE b.entity_type = 'topic'
              AND b.entity_id = t.topic_id::text
              AND b.state_code = $2::text
      ))
    ORDER BY transcript_occurrences DESC NULLS LAST, name ASC
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
) -> List[TopicSummary]:
    """Civic topics (most-discussed first), optionally narrowed by a name
    substring and/or restricted to a single state."""
    with tracer.start_as_current_span("topics-list") as span:
        span.set_attribute("topics.q", (q or "").strip())
        like = f"%{q.strip()}%" if q and q.strip() else None
        # Normalize to the 2-letter upper-case form the bridge stores; blank -> None.
        state_code = state.strip().upper() if state and state.strip() else None
        span.set_attribute("topics.state", state_code or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("topics-query"):
                    rows = await conn.fetch(_TOPICS_SQL, like, state_code)
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
