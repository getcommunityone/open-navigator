"""Jurisdiction-grain scraped meeting documents API.

Serves the agenda/minutes documents scraped for a JURISDICTION's meetings from
public.event_meeting_document, grouped by meeting (doc_date + body_name). Crucially
this INCLUDES orphan rows where event_meeting_id IS NULL — documents that were
scraped but never matched to an analyzed meeting (e.g. ~2,090 Tuscaloosa rows,
2021-2026). Those rows are otherwise only reachable from the decision-detail page,
which requires an analyzed meeting; this endpoint surfaces them directly.

DISTINCT from /jurisdiction/{id}/documents (api.routes.jurisdiction_documents),
which serves jurisdiction-OWNED plans & ordinances, and from /decision documents
(api.routes.decisions), which require an analyzed decision.

public.event_meeting_document has no JSONB columns we read here, so the asyncpg
JSONB-as-text caveat that applies to decisions.py does not apply. We still group
in Python rather than using jsonb_agg, since the pool has no JSONB codec.
"""

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/jurisdiction", tags=["jurisdiction"])

tracer = trace.get_tracer(__name__)


class MeetingDocumentFile(BaseModel):
    """One scraped document (agenda or minutes) within a meeting group."""

    document_type: str          # 'agenda' | 'minutes'
    document_url: str
    source: Optional[str] = None


class MeetingDocumentGroup(BaseModel):
    """All scraped documents for a single meeting (doc_date + body_name)."""

    doc_date: Optional[date] = None      # real DATE -> serializes as ISO string
    body_name: Optional[str] = None
    event_meeting_id: Optional[int] = None   # set if any doc matched an analyzed meeting
    documents: list[MeetingDocumentFile]


class JurisdictionMeetingDocuments(BaseModel):
    """Scraped meeting documents for a jurisdiction, grouped by meeting."""

    jurisdiction_id: str
    meeting_count: int
    document_count: int
    meetings: list[MeetingDocumentGroup]


# Accept EITHER the slug-style jurisdiction_id ('tuscaloosa_0177256') OR the bare
# Census geoid ('0177256'). The jurisdiction-search results the UI links from only
# expose the geoid (api.routes.search_postgres builds /jurisdictions/{geoid}), so
# the path param is usually a geoid; analyst/API callers may pass the full id.
_MEETING_DOCUMENTS_SQL = """
    SELECT doc_date, body_name, document_type, document_url, source, event_meeting_id
    FROM public.event_meeting_document
    WHERE jurisdiction_id = $1 OR census_geoid = $1
    ORDER BY doc_date DESC NULLS LAST, body_name ASC,
      CASE document_type WHEN 'agenda' THEN 0 WHEN 'minutes' THEN 1 ELSE 2 END
"""


def _group_meeting_documents(rows: list[dict[str, Any]]) -> list[MeetingDocumentGroup]:
    """Group already-ordered flat rows into meetings by (doc_date, body_name).

    Rows are assumed pre-sorted by the SQL ORDER BY, so consecutive rows sharing a
    (doc_date, body_name) key form one meeting group. event_meeting_id for the group
    is the first non-null value among its rows (may be None for orphan-only groups).
    """
    groups: list[MeetingDocumentGroup] = []
    current_key: Optional[tuple[Any, Any]] = None

    for row in rows:
        key = (row.get("doc_date"), row.get("body_name"))
        doc = MeetingDocumentFile(
            document_type=row["document_type"],
            document_url=row["document_url"],
            source=row.get("source"),
        )
        if not groups or key != current_key:
            groups.append(
                MeetingDocumentGroup(
                    doc_date=row.get("doc_date"),
                    body_name=row.get("body_name"),
                    event_meeting_id=row.get("event_meeting_id"),
                    documents=[doc],
                )
            )
            current_key = key
        else:
            group = groups[-1]
            group.documents.append(doc)
            if group.event_meeting_id is None and row.get("event_meeting_id") is not None:
                group.event_meeting_id = row.get("event_meeting_id")

    return groups


@router.get(
    "/{jurisdiction_id}/meeting-documents",
    response_model=JurisdictionMeetingDocuments,
)
async def get_jurisdiction_meeting_documents(
    jurisdiction_id: str,
) -> JurisdictionMeetingDocuments:
    """Scraped agenda/minutes for a jurisdiction's meetings, grouped by meeting.

    Includes orphan documents (event_meeting_id IS NULL). Returns empty lists with
    a 200 (not 404) when the jurisdiction has no scraped meeting documents.
    """
    with tracer.start_as_current_span("get_jurisdiction_meeting_documents") as span:
        span.set_attribute("jurisdiction_id", jurisdiction_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                rows = await conn.fetch(_MEETING_DOCUMENTS_SQL, jurisdiction_id)
        except Exception as exc:  # noqa: BLE001 — surface as 500, don't leak internals
            logger.error(
                "jurisdiction meeting documents query failed for {}: {}",
                jurisdiction_id,
                exc,
            )
            raise HTTPException(
                status_code=500, detail="Failed to load jurisdiction meeting documents"
            )

        meetings = _group_meeting_documents([dict(r) for r in rows])
        span.set_attribute("meeting_count", len(meetings))
        span.set_attribute("document_count", len(rows))
        return JurisdictionMeetingDocuments(
            jurisdiction_id=jurisdiction_id,
            meeting_count=len(meetings),
            document_count=len(rows),
            meetings=meetings,
        )
