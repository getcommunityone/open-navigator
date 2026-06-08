"""Jurisdiction-grain civic documents API.

Serves the documents that belong to a JURISDICTION (rather than a single
meeting) — comprehensive plans / frameworks, zoning ordinances, ordinance codes,
zoning maps — from public.jurisdiction_document. This is the serving side of the
jurisdiction_document mart: a jurisdiction view can list its "plans &
ordinances" (e.g. the City of Tuscaloosa "Framework").

DISTINCT from /decision documents (api.routes.decisions), which surface the
meeting-grain agenda/minutes for a specific decision via event_meeting_document.

public.jurisdiction_document has no JSONB columns, so the asyncpg JSONB-as-text
caveat that applies to decisions.py does not apply here.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/jurisdiction", tags=["jurisdiction"])

tracer = trace.get_tracer(__name__)


class JurisdictionDocument(BaseModel):
    """One jurisdiction-grain document (plan / ordinance / map)."""

    jurisdiction_document_id: str
    jurisdiction_id: str
    document_type: str          # comprehensive_plan | zoning_ordinance | ordinance_code | zoning_map
    title: Optional[str] = None
    document_url: str
    adopted_date: Optional[date] = None  # real DATE -> serializes as ISO
    source: Optional[str] = None


_DOCUMENTS_SQL = """
    SELECT jurisdiction_document_id, jurisdiction_id, document_type, title,
           document_url, adopted_date, source
    FROM public.jurisdiction_document
    WHERE jurisdiction_id = $1
    ORDER BY document_type, title NULLS LAST
"""


@router.get("/{jurisdiction_id}/documents", response_model=list[JurisdictionDocument])
async def get_jurisdiction_documents(jurisdiction_id: str) -> list[JurisdictionDocument]:
    """Plans & ordinances owned by a jurisdiction (empty list if none on file)."""
    with tracer.start_as_current_span("get_jurisdiction_documents") as span:
        span.set_attribute("jurisdiction_id", jurisdiction_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(_DOCUMENTS_SQL, jurisdiction_id)
        except Exception as exc:  # noqa: BLE001 — surface as 500, don't leak internals
            logger.error("jurisdiction documents query failed for {}: {}", jurisdiction_id, exc)
            raise HTTPException(status_code=500, detail="Failed to load jurisdiction documents")

        span.set_attribute("document_count", len(rows))
        return [JurisdictionDocument(**dict(r)) for r in rows]
