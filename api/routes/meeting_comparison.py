"""Side-by-side meeting comparison: AI summary vs official agenda/minutes.

Powers the MeetingCompare page, which shows a meeting's AI-generated summary (derived
from the meeting VIDEO transcript) next to the OFFICIAL scraped agenda or minutes, and
on demand highlights omissions / possible errors / interesting gaps between them.

Two endpoints:
  - GET  /api/meeting/{id}/comparison      cheap, refresh-safe; assembles the whole page
                                           (summary + decisions + the meeting's documents
                                           + any already-cached gap analyses). NO Gemini.
  - POST /api/meeting/{id}/document-gaps   the BILLED path. Fetches the document, extracts
                                           text, and calls Gemini (llm.meeting_gap_analysis)
                                           ONLY on this explicit user action. Result is
                                           cached so re-views are free.

The pool registers no JSON codec, so asyncpg returns JSONB as raw text — we json.loads()
vote_tally here, and write gap_json as ``$N::jsonb`` from json.dumps().
"""
from __future__ import annotations

import json
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Path
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from llm.gemini.document_text import extract_text_from_bytes
from llm.gemini.meeting_gap_analysis import analyze_gaps
from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/meeting", tags=["meeting"])

tracer = trace.get_tracer(__name__)

# Upper bound on a fetched document (mirrors api.routes.documents proxy cap).
_MAX_BYTES = 50 * 1024 * 1024

# Lazily-created, runtime-owned cache table. Deliberately NOT a dbt model and with NO
# FK to event_meeting: dbt rebuilds drop/recreate that mart, and a hard FK on a runtime
# table would break the build. Guarded by a module flag so DDL runs at most once.
_CACHE_TABLE_READY = False

_CREATE_CACHE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS public.meeting_document_gap_cache (
        event_meeting_id integer NOT NULL,
        document_url      text    NOT NULL,
        document_type     text,
        gap_json          jsonb   NOT NULL,
        source_ai_model   text,
        created_at        timestamptz NOT NULL DEFAULT now(),
        PRIMARY KEY (event_meeting_id, document_url)
    )
"""


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class ComparisonDecision(BaseModel):
    event_decision_id: str
    headline: Optional[str] = None
    outcome: Optional[str] = None
    decision_statement: Optional[str] = None
    vote_tally: Any = None
    primary_theme: Optional[str] = None


class ComparisonSummary(BaseModel):
    meeting_summary: Optional[str] = None
    agenda_summary: Optional[str] = None
    decisions: list[ComparisonDecision] = []


class ComparisonDocument(BaseModel):
    document_type: str
    document_url: str


class GapItem(BaseModel):
    quote: str = ""
    detail: str = ""


class Correction(BaseModel):
    """An AI fact the official document contradicts → fix applied to the recap."""

    quote: str = ""          # verbatim from the official document
    ai_claim: str = ""       # the AI's incorrect statement
    correction: str = ""     # the corrected fact


class DollarAmount(BaseModel):
    amount: str = ""
    description: str = ""
    quote: str = ""


class DecisionEnrichment(BaseModel):
    """Precise detail pulled from the official document for one decision."""

    decision_ref: str = ""
    addresses: list[str] = []
    legislation: list[str] = []
    dollar_amounts: list[DollarAmount] = []


class GapAnalysis(BaseModel):
    # New fields default empty so older-shape cache rows still validate.
    status: str
    corrections: list[Correction] = []
    corrected_summary: str = ""
    decision_enrichments: list[DecisionEnrichment] = []
    minutes_omissions: list[GapItem] = []
    overall: str = ""
    model: Optional[str] = None


class MeetingComparison(BaseModel):
    event_meeting_id: int
    body_name: Optional[str] = None
    meeting_date: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    summary: ComparisonSummary
    documents: list[ComparisonDocument] = []
    cached_gaps: dict[str, GapAnalysis] = {}


class DocumentGapsRequest(BaseModel):
    document_url: str


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------
_MEETING_SQL = """
    SELECT
        event_meeting_id,
        c1_event_id,
        body_name,
        jurisdiction_name,
        meeting_summary,
        agenda_summary,
        CASE WHEN COALESCE(NULLIF(event_date, ''), NULLIF(meeting_date, '')) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
             THEN COALESCE(NULLIF(event_date, ''), NULLIF(meeting_date, '')) END AS meeting_date
    FROM event_meeting
    WHERE event_meeting_id = $1
"""

_DECISIONS_SQL = """
    SELECT event_decision_id, headline, outcome, decision_statement, vote_tally, primary_theme
    FROM event_decision
    WHERE c1_event_id = $1
    ORDER BY headline
"""

_DOCUMENTS_SQL = """
    SELECT document_type, document_url
    FROM event_meeting_document
    WHERE event_meeting_id = $1
    ORDER BY CASE document_type WHEN 'agenda' THEN 0 WHEN 'minutes' THEN 1 ELSE 2 END,
             document_url
"""

# Ownership + SSRF guard: the (meeting, url) pair must be a document we already serve.
_DOC_OWNED_SQL = """
    SELECT document_type
    FROM event_meeting_document
    WHERE event_meeting_id = $1 AND document_url = $2
    LIMIT 1
"""

_CACHE_SELECT_SQL = """
    SELECT document_url, gap_json
    FROM public.meeting_document_gap_cache
    WHERE event_meeting_id = $1
"""

_CACHE_SELECT_ONE_SQL = """
    SELECT gap_json
    FROM public.meeting_document_gap_cache
    WHERE event_meeting_id = $1 AND document_url = $2
"""

_CACHE_UPSERT_SQL = """
    INSERT INTO public.meeting_document_gap_cache
        (event_meeting_id, document_url, document_type, gap_json, source_ai_model)
    VALUES ($1, $2, $3, $4::jsonb, $5)
    ON CONFLICT (event_meeting_id, document_url)
    DO UPDATE SET gap_json = EXCLUDED.gap_json,
                  document_type = EXCLUDED.document_type,
                  source_ai_model = EXCLUDED.source_ai_model,
                  created_at = now()
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_json(value: Any) -> Any:
    """asyncpg returns JSONB as text without a codec; tolerate already-parsed too."""
    if value is None or not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        return value


def _meeting_iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


async def _ensure_cache_table(conn: Any) -> None:
    """Create the runtime cache table once per process."""
    global _CACHE_TABLE_READY
    if _CACHE_TABLE_READY:
        return
    await conn.execute(_CREATE_CACHE_TABLE_SQL)
    _CACHE_TABLE_READY = True


def _build_decisions(rows: list[Any]) -> list[ComparisonDecision]:
    return [
        ComparisonDecision(
            event_decision_id=d["event_decision_id"],
            headline=d["headline"],
            outcome=d["outcome"],
            decision_statement=d["decision_statement"],
            vote_tally=_parse_json(d["vote_tally"]),
            primary_theme=d["primary_theme"],
        )
        for d in rows
    ]


def _summary_text(meeting_row: Any, decisions: list[ComparisonDecision]) -> str:
    """Flatten the AI summary + decisions into one prompt-ready block."""
    parts: list[str] = []
    if meeting_row["meeting_summary"]:
        parts.append(f"MEETING SUMMARY:\n{meeting_row['meeting_summary']}")
    if meeting_row["agenda_summary"]:
        parts.append(f"AGENDA SUMMARY:\n{meeting_row['agenda_summary']}")
    if decisions:
        lines = []
        for d in decisions:
            head = d.headline or "(untitled decision)"
            outcome = f" — {d.outcome}" if d.outcome else ""
            stmt = f"\n  {d.decision_statement}" if d.decision_statement else ""
            lines.append(f"- {head}{outcome}{stmt}")
        parts.append("DECISIONS:\n" + "\n".join(lines))
    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get("/{event_meeting_id}/comparison", response_model=MeetingComparison)
async def get_meeting_comparison(
    event_meeting_id: int = Path(..., ge=1),
) -> MeetingComparison:
    """Assemble the comparison page: AI summary, decisions, documents, cached gaps.

    Cheap and refresh-safe — runs NO Gemini analysis. 404 if the meeting is absent.
    """
    with tracer.start_as_current_span("meeting.comparison") as span:
        span.set_attribute("meeting.event_meeting_id", event_meeting_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                meeting = await conn.fetchrow(_MEETING_SQL, event_meeting_id)
                if meeting is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No meeting found for event_meeting_id {event_meeting_id}",
                    )
                c1 = meeting["c1_event_id"]
                decision_rows = await conn.fetch(_DECISIONS_SQL, c1) if c1 else []
                document_rows = await conn.fetch(_DOCUMENTS_SQL, event_meeting_id)
                # The cache table may not exist yet on a fresh DB — tolerate that.
                try:
                    cache_rows = await conn.fetch(_CACHE_SELECT_SQL, event_meeting_id)
                except Exception:  # noqa: BLE001 — table absent => no cached gaps
                    cache_rows = []
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("Meeting comparison error for {}: {}", event_meeting_id, e)
            raise HTTPException(status_code=500, detail="Failed to load meeting comparison")

        decisions = _build_decisions(decision_rows)
        cached_gaps: dict[str, GapAnalysis] = {}
        for r in cache_rows:
            parsed = _parse_json(r["gap_json"])
            if isinstance(parsed, dict):
                cached_gaps[r["document_url"]] = GapAnalysis(**parsed)

        return MeetingComparison(
            event_meeting_id=meeting["event_meeting_id"],
            body_name=meeting["body_name"],
            meeting_date=_meeting_iso_date(meeting["meeting_date"]),
            jurisdiction_name=meeting["jurisdiction_name"],
            summary=ComparisonSummary(
                meeting_summary=meeting["meeting_summary"],
                agenda_summary=meeting["agenda_summary"],
                decisions=decisions,
            ),
            documents=[
                ComparisonDocument(document_type=d["document_type"], document_url=d["document_url"])
                for d in document_rows
            ],
            cached_gaps=cached_gaps,
        )


@router.post("/{event_meeting_id}/document-gaps", response_model=GapAnalysis)
async def analyze_document_gaps(
    payload: DocumentGapsRequest,
    event_meeting_id: int = Path(..., ge=1),
) -> GapAnalysis:
    """Compare one document against the AI summary and return highlighted gaps.

    This is the BILLED path: it makes a real Gemini call on the user's explicit
    action. The result is cached on (event_meeting_id, document_url) so repeat
    views (and reloads) are free. Validates the document belongs to this meeting.
    """
    document_url = payload.document_url
    with tracer.start_as_current_span("meeting.document_gaps") as span:
        span.set_attribute("meeting.event_meeting_id", event_meeting_id)
        span.set_attribute("document.url", document_url)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                document_type = await conn.fetchval(
                    _DOC_OWNED_SQL, event_meeting_id, document_url
                )
                if not document_type:
                    raise HTTPException(
                        status_code=404,
                        detail="Document not found for this meeting",
                    )
                await _ensure_cache_table(conn)

                # Cache hit -> return without spending a Gemini call.
                cached = await conn.fetchval(
                    _CACHE_SELECT_ONE_SQL, event_meeting_id, document_url
                )
                if cached is not None:
                    parsed = _parse_json(cached)
                    if isinstance(parsed, dict):
                        span.set_attribute("cache.hit", True)
                        return GapAnalysis(**parsed)

                # Assemble the AI summary side.
                meeting = await conn.fetchrow(_MEETING_SQL, event_meeting_id)
                if meeting is None:
                    raise HTTPException(status_code=404, detail="Meeting not found")
                c1 = meeting["c1_event_id"]
                decision_rows = await conn.fetch(_DECISIONS_SQL, c1) if c1 else []

            span.set_attribute("document.type", document_type)
            decisions = _build_decisions(decision_rows)
            summary_text = _summary_text(meeting, decisions)

            # Fetch the document bytes (same SSRF-validated pattern as the proxy).
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=20.0) as client:
                    resp = await client.get(
                        document_url, headers={"User-Agent": "OpenNavigator/1.0"}
                    )
            except httpx.HTTPError as exc:
                logger.warning("Gap-analysis fetch failed for {}: {}", document_url, exc)
                raise HTTPException(status_code=502, detail="Failed to fetch document") from exc
            if resp.status_code != 200:
                raise HTTPException(
                    status_code=502, detail=f"Upstream returned {resp.status_code}"
                )
            content = resp.content
            if len(content) > _MAX_BYTES:
                raise HTTPException(status_code=413, detail="Document too large to analyze")
            content_type = (resp.headers.get("content-type") or "").split(";")[0].strip() or None

            document_text = extract_text_from_bytes(
                content, url=document_url, content_type=content_type
            )

            # The decisions to enrich from the official document (id keeps the
            # model's enrichments mappable back to each event_decision).
            decision_payload = [
                {
                    "id": d.event_decision_id,
                    "headline": d.headline or "",
                    "statement": d.decision_statement or "",
                }
                for d in decisions
            ]

            # Real (billed) Gemini call — guarded so it only runs on this POST.
            result = analyze_gaps(
                summary_text=summary_text,
                document_text=document_text,
                document_type=document_type,
                decisions=decision_payload,
            )
            span.set_attribute("gap.status", str(result.get("status")))

            # Cache the result (gap_json is a dict -> json.dumps + ::jsonb cast).
            async with pool.acquire() as conn:
                await _ensure_cache_table(conn)
                await conn.execute(
                    _CACHE_UPSERT_SQL,
                    event_meeting_id,
                    document_url,
                    document_type,
                    json.dumps(result),
                    result.get("model"),
                )

            return GapAnalysis(**result)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("Document gap analysis error for {}: {}", event_meeting_id, e)
            raise HTTPException(status_code=500, detail="Failed to analyze document gaps")
