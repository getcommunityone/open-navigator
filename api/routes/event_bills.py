"""
Bill-reference detail endpoint, backed by public.event_bill (AI-extracted
legislation references from meeting analysis — local ordinances, resolutions,
agenda items).

These are NOT OpenStates state-legislature bills (those live in bills_neon.py at
/api/bills/{bill_id}); event_bill is the meeting-derived feed that /search
returns for type='bill', linked from results as url=/bills/{event_bill_id}.

Joins event_meeting on c1_event_id to surface the meeting body + date the
reference came from. event_bill has no JSONB columns, so no codec workaround is
needed here (cf. decisions.py).
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/event-bill", tags=["bill"])

tracer = trace.get_tracer(__name__)


class BillReferenceDetail(BaseModel):
    """A single AI-extracted legislation reference, keyed by event_bill_id."""
    event_bill_id: str
    official_number: Optional[str] = None
    title: Optional[str] = None
    leg_type: Optional[str] = None
    status: Optional[str] = None
    relevance: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    jurisdiction_type: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    city: Optional[str] = None
    c1_event_id: Optional[str] = None
    meeting_name: Optional[str] = None
    meeting_date: Optional[str] = None
    meeting_video_id: Optional[str] = None
    source_ai_model: Optional[str] = None
    extracted_at: Optional[str] = None


_BILL_SQL = """
    SELECT
        b.event_bill_id,
        b.official_number,
        b.title,
        b.leg_type,
        b.status,
        b.relevance,
        b.jurisdiction_name,
        b.jurisdiction_type,
        b.state,
        b.state_code,
        b.city,
        b.c1_event_id,
        b.source_ai_model,
        b.extracted_at,
        m.body_name AS meeting_name,
        COALESCE(NULLIF(m.event_date, ''), NULLIF(m.meeting_date, '')) AS meeting_date,
        m.video_id AS meeting_video_id
    FROM event_bill b
    LEFT JOIN event_meeting m ON m.c1_event_id = b.c1_event_id
    WHERE b.event_bill_id = $1
"""


@router.get("/{event_bill_id}", response_model=BillReferenceDetail)
async def get_bill_reference(event_bill_id: str) -> BillReferenceDetail:
    """
    Return a single AI-extracted legislation reference by event_bill_id.
    404 if no row matches.
    """
    with tracer.start_as_current_span("bill-reference-detail") as span:
        span.set_attribute("bill.event_bill_id", event_bill_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("bill-reference-detail.query"):
                    row = await conn.fetchrow(_BILL_SQL, event_bill_id)

            if row is None:
                span.set_attribute("bill.found", False)
                raise HTTPException(
                    status_code=404,
                    detail=f"No bill reference found for event_bill_id '{event_bill_id}'",
                )
            span.set_attribute("bill.found", True)

            data = dict(row)
            extracted = data.get("extracted_at")
            data["extracted_at"] = extracted.isoformat() if extracted is not None else None

            logger.info("📜 Bill reference detail {} -> {}", event_bill_id, data.get("official_number"))
            return BillReferenceDetail(**data)

        except HTTPException:
            raise
        except Exception as e:
            span.record_exception(e)
            logger.error("Bill reference detail error for {}: {}", event_bill_id, e)
            raise HTTPException(status_code=500, detail="Failed to load bill reference detail")
