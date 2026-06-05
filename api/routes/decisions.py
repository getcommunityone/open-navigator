"""
Decision-detail endpoint, backed by public.event_decision (AI-extracted policy
decisions).

Serves a single decision by its unique key (event_decision_id), which the
/search decision results link to (url=/decisions/{event_decision_id}). Mirrors
the people.py person-detail pattern: a single fetchrow on the public serving
table, 404 when absent.

The pool registers no JSON codec, so asyncpg returns JSONB columns as raw JSON
text — we json.loads() them here so vote_tally / competing_views / *_refs
serialize to the client as real objects/arrays instead of double-encoded strings.
"""
from __future__ import annotations

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/decision", tags=["decision"])

tracer = trace.get_tracer(__name__)


class DecisionDetail(BaseModel):
    """A single AI-extracted policy decision, keyed by event_decision_id."""
    event_decision_id: str
    headline: Optional[str] = None
    decision_statement: Optional[str] = None
    outcome: Optional[str] = None
    primary_theme: Optional[str] = None
    # JSONB payloads (parsed from text); shapes vary by extraction.
    vote_tally: Optional[Any] = None
    human_element: Optional[Any] = None
    competing_views: Optional[Any] = None
    smart_brevity: Optional[Any] = None
    legislation_refs: Optional[Any] = None
    financial_item_refs: Optional[Any] = None
    place_refs: Optional[Any] = None
    # Location / provenance.
    jurisdiction_name: Optional[str] = None
    jurisdiction_type: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    city: Optional[str] = None
    c1_event_id: Optional[str] = None
    decision_id: Optional[str] = None
    subject_id: Optional[str] = None
    # Meeting context (event_meeting joined on c1_event_id).
    meeting_name: Optional[str] = None
    meeting_date: Optional[str] = None
    meeting_video_id: Optional[str] = None
    source_ai_model: Optional[str] = None
    extracted_at: Optional[str] = None


_DECISION_SQL = """
    SELECT
        event_decision_id,
        headline,
        decision_statement,
        outcome,
        primary_theme,
        vote_tally,
        human_element,
        competing_views,
        smart_brevity,
        legislation_refs,
        financial_item_refs,
        place_refs,
        d.jurisdiction_name,
        d.jurisdiction_type,
        d.state,
        d.state_code,
        d.city,
        d.c1_event_id,
        d.decision_id,
        d.subject_id,
        d.source_ai_model,
        d.extracted_at,
        m.body_name AS meeting_name,
        CASE WHEN COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, '')) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
             THEN COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, '')) END AS meeting_date,
        m.video_id AS meeting_video_id
    FROM event_decision d
    LEFT JOIN event_meeting m ON m.c1_event_id = d.c1_event_id
    WHERE d.event_decision_id = $1
"""

# JSONB columns asyncpg hands back as raw JSON text (no codec on the pool).
_JSON_FIELDS = (
    "vote_tally",
    "human_element",
    "competing_views",
    "smart_brevity",
    "legislation_refs",
    "financial_item_refs",
    "place_refs",
)


def _parse_json(value: Any) -> Any:
    """asyncpg returns JSONB as text without a codec; tolerate already-parsed too."""
    if value is None or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return value


@router.get("/{event_decision_id}", response_model=DecisionDetail)
async def get_decision(event_decision_id: str) -> DecisionDetail:
    """
    Return a single AI-extracted policy decision by event_decision_id.
    404 if no decision row matches.
    """
    with tracer.start_as_current_span("decision-detail") as span:
        span.set_attribute("decision.event_decision_id", event_decision_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("decision-detail.query"):
                    row = await conn.fetchrow(_DECISION_SQL, event_decision_id)

            if row is None:
                span.set_attribute("decision.found", False)
                raise HTTPException(
                    status_code=404,
                    detail=f"No decision found for event_decision_id '{event_decision_id}'",
                )
            span.set_attribute("decision.found", True)

            data = dict(row)
            for field in _JSON_FIELDS:
                data[field] = _parse_json(data.get(field))
            extracted = data.get("extracted_at")
            data["extracted_at"] = extracted.isoformat() if extracted is not None else None

            logger.info("⚖️ Decision detail {} -> {}", event_decision_id, data.get("outcome"))
            return DecisionDetail(**data)

        except HTTPException:
            raise
        except Exception as e:
            span.record_exception(e)
            logger.error("Decision detail error for {}: {}", event_decision_id, e)
            raise HTTPException(status_code=500, detail="Failed to load decision detail")
