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
# Bind params:
#   $1 = optional name substring (ILIKE pattern, %…%) — applied in every mode.
#   $2 = optional 2-letter state code (upper-cased to the bridge's storage form).
#   $3 = optional city/place name (original case; matched ILIKE against
#        jurisdiction_name in the per-place bridge).
#
# Per-scope occurrence semantics — `effective_occurrences` is HONEST to the
# active scope so a place-scoped list never shows national numbers:
#   * city given ($3 not null): restrict to topics with a row in
#     browse_entity_place_transcript_count for (entity_type='topic',
#     entity_id=topic_id, jurisdiction_name ILIKE $3 [AND state_code=$2 when
#     state is also given]); count = that place row's transcript_count.
#   * state given, no city ($2 not null, $3 null): restrict via
#     browse_entity_state_transcript_count (per-state bridge); count = that
#     state row's transcript_count (NOT the national column — fixes the latent
#     national-count-on-state-scoped-list inconsistency).
#   * no place filter: count = the national civicsearch_topic.transcript_occurrences.
# LEFT JOINs keep the no-filter case from dropping rows; the WHERE only requires
# a bridge match when the corresponding place param is supplied. ORDER BY uses
# the effective (scope-correct) count so ordering matches the displayed numbers.
_TOPICS_SQL = """
    SELECT
        t.topic_id,
        t.name,
        t.query_id,
        t.keyword_stats,
        CASE
            WHEN $3::text IS NOT NULL THEN p.transcript_count
            WHEN $2::text IS NOT NULL THEN s.transcript_count
            ELSE t.transcript_occurrences
        END AS effective_occurrences
    FROM civicsearch_topic t
    LEFT JOIN browse_entity_state_transcript_count s
           ON s.entity_type = 'topic'
          AND s.entity_id = t.topic_id::text
          AND s.state_code = $2::text
    LEFT JOIN browse_entity_place_transcript_count p
           ON p.entity_type = 'topic'
          AND p.entity_id = t.topic_id::text
          AND p.jurisdiction_name ILIKE $3::text
          AND ($2::text IS NULL OR p.state_code = $2::text)
    WHERE ($1::text IS NULL OR t.name ILIKE $1)
      AND ($3::text IS NULL OR p.entity_id IS NOT NULL)
      AND ($3::text IS NOT NULL OR $2::text IS NULL OR s.entity_id IS NOT NULL)
    ORDER BY effective_occurrences DESC NULLS LAST, t.name ASC
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
    city: Optional[str] = Query(None, description="Optional city/place name; restricts to topics discussed in that place and scopes the count to it."),
) -> List[TopicSummary]:
    """Civic topics (most-discussed first), optionally narrowed by a name
    substring and/or restricted to a single state and/or a single city/place.
    The returned `transcript_occurrences` is scoped to whichever place filter is
    active (city > state > national)."""
    with tracer.start_as_current_span("topics-list") as span:
        span.set_attribute("topics.q", (q or "").strip())
        like = f"%{q.strip()}%" if q and q.strip() else None
        # Normalize to the 2-letter upper-case form the bridge stores; blank -> None.
        state_code = state.strip().upper() if state and state.strip() else None
        # Keep original case for the place name (matched with ILIKE); blank -> None.
        city_name = city.strip() if city and city.strip() else None
        span.set_attribute("topics.state", state_code or "")
        span.set_attribute("topics.city", city_name or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("topics-query"):
                    rows = await conn.fetch(_TOPICS_SQL, like, state_code, city_name)
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
                transcript_occurrences=r["effective_occurrences"] or 0,
            )
            for r in rows
        ]
