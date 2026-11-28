"""
Meeting transcript endpoint, backed by public.event_documents.

Powers the in-page video player on the decision / legislation drilldowns: the
client embeds the meeting recording (react-player) and renders the timed
transcript segments as clickable cues that seek the player to that moment.

GRAIN: event_documents may carry >1 doc per video_id, so we filter to
document_type='transcript' and LIMIT 1. `segments` is a JSONB array of timed
cues; we expose the minimal {start, text} shape the player needs.

SEGMENT SHAPE: two shapes are in the wild and both are tolerated:
  - dev/local: long form {"start", "duration", "text"}
  - Neon serving: slimmed form {"s": <start_seconds>, "t": <text>}
`_coerce_segments` reads start from `s` OR `start` and text from `t` OR `text`.

This reads only analyzed meetings (~6,397) since the 8.3 GB
bronze.bronze_event_youtube_transcript table is NOT mirrored to the Neon serving
DB; reduced cue coverage is the accepted product tradeoff.

The pool registers no JSON codec, so asyncpg returns JSONB as raw text — we
json.loads() it here.
"""
from __future__ import annotations

import json
from typing import Any, List, Optional

from fastapi import APIRouter, HTTPException, Path
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.meeting_type import (
    meeting_type_available,
    meeting_type_by_video_sql,
    meeting_type_label,
)
from api.provenance import Provenance, build_provenance
from api.routes.search_postgres import get_db_pool
from core_lib.privacy import default_redactor, is_school_board
from api.privacy_redaction import ensure_officials, officials_for, SNIPPET_FIELDS, redact_response

router = APIRouter(prefix="/meeting", tags=["meeting"])

tracer = trace.get_tracer(__name__)


class TranscriptCue(BaseModel):
    """A single timed transcript line. `start` is seconds from the video start."""
    start: float
    text: str


class MeetingTranscript(BaseModel):
    """Timed transcript for a meeting recording, keyed by YouTube video_id."""
    video_id: str
    has_transcript: bool
    language: Optional[str] = None
    segment_count: int = 0
    segments: List[TranscriptCue] = []


_TRANSCRIPT_SQL = """
    SELECT
        video_id,
        language,
        segments,
        state_code,
        jurisdiction_name,
        jurisdiction_type,
        event_title,
        (segments IS NOT NULL AND jsonb_array_length(segments) > 0) AS has_transcript
    FROM public.event_documents
    WHERE video_id = $1
      AND document_type = 'transcript'
    LIMIT 1
"""


def _coerce_segments(value: Any) -> List[TranscriptCue]:
    """Normalize the JSONB `segments` array to a clean list of timed cues.

    Accepts BOTH segment shapes (see module docstring):
      - long form {"start", "duration", "text"} (dev/local)
      - slimmed form {"s": <start_seconds>, "t": <text>} (Neon serving)
    Start is read from `s` OR `start`, text from `t` OR `text`; `start` is kept
    as seconds (float) in the output cue.

    Tolerates already-parsed lists, raw JSON text, missing/invalid entries, and
    non-numeric starts — anything unusable is dropped rather than 500ing.
    """
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            return []
    if not isinstance(value, list):
        return []

    cues: List[TranscriptCue] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        # Slimmed Neon shape uses `s`/`t`; dev long form uses `start`/`text`.
        start = item.get("s")
        if start is None:
            start = item.get("start")
        text = item.get("t")
        if text is None:
            text = item.get("text")
        if start is None or not isinstance(text, str) or not text.strip():
            continue
        try:
            start_f = float(start)
        except (TypeError, ValueError):
            continue
        cues.append(TranscriptCue(start=start_f, text=text.strip()))
    return cues


@router.get("/{video_id}/transcript", response_model=MeetingTranscript)
async def get_meeting_transcript(
    video_id: str = Path(..., description="YouTube video id of the meeting recording"),
) -> MeetingTranscript:
    """
    Return the timed transcript for a meeting recording so the client can render
    clickable cues that seek the embedded player.

    Returns has_transcript=false with an empty segment list (HTTP 200) when no
    transcript row exists — the player still embeds, just without cues.
    """
    with tracer.start_as_current_span("meeting-transcript") as span:
        span.set_attribute("meeting.video_id", video_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                with tracer.start_as_current_span("meeting-transcript.query"):
                    row = await conn.fetchrow(_TRANSCRIPT_SQL, video_id)

            if row is None:
                span.set_attribute("meeting.found", False)
                return MeetingTranscript(video_id=video_id, has_transcript=False)

            span.set_attribute("meeting.found", True)
            segments = _coerce_segments(row["segments"])
            # Private residents' full names -> "First L.", home addresses -> "[address]" (#1468).
            await ensure_officials()
            cleaned = default_redactor().redact_segments(
                [c.text for c in segments],
                official_names=officials_for(row.get("state_code"), row.get("jurisdiction_name")),
                school=is_school_board(row.get("jurisdiction_name"), row.get("jurisdiction_type"), row.get("event_title")),
            )
            segments = [TranscriptCue(start=c.start, text=t) for c, t in zip(segments, cleaned)]
            span.set_attribute("meeting.segment_count", len(segments))

            logger.info("🎬 Meeting transcript {} -> {} cues", video_id, len(segments))
            return MeetingTranscript(
                video_id=row["video_id"],
                has_transcript=bool(row["has_transcript"]) and len(segments) > 0,
                language=row["language"],
                segment_count=len(segments),
                segments=segments,
            )

        except Exception as e:
            span.record_exception(e)
            logger.error("Meeting transcript error for {}: {}", video_id, e)
            raise HTTPException(status_code=500, detail="Failed to load meeting transcript")


# ---------------------------------------------------------------------------
# Meeting detail (by event_meeting_id) — the real drilldown target for homepage
# "Raised Eyebrows" flags: /meetings/{event_meeting_id}?item=FINxxx. Lists the
# meeting's decisions + financial items so a flagged spend lands on its source.
# ---------------------------------------------------------------------------
class MeetingDecision(BaseModel):
    event_decision_id: str
    headline: Optional[str] = None
    outcome: Optional[str] = None
    primary_theme: Optional[str] = None


class MeetingFinancialItem(BaseModel):
    event_financial_item_id: str
    financial_item_id: Optional[str] = None
    event_description: Optional[str] = None
    amount: Optional[float] = None
    amount_type: Optional[str] = None


class MeetingDocument(BaseModel):
    document_type: str
    document_url: str
    doc_date: Optional[str] = None
    body_name: Optional[str] = None


class MeetingDetail(BaseModel):
    event_meeting_id: int
    c1_event_id: Optional[str] = None
    body_name: Optional[str] = None
    jurisdiction_name: Optional[str] = None
    jurisdiction_type: Optional[str] = None
    state: Optional[str] = None
    state_code: Optional[str] = None
    meeting_date: Optional[str] = None
    video_id: Optional[str] = None
    meeting_type: Optional[str] = None  # normalized label; None when blank/UNKNOWN (#797)
    has_agenda: bool = False
    has_minutes: bool = False
    documents: List[MeetingDocument] = []
    decisions: List[MeetingDecision] = []
    financial_items: List[MeetingFinancialItem] = []
    # How the meeting's AI summary was made (#1099), the same facts as the decision page's footer (#798).
    provenance: Optional[Provenance] = None


def _meeting_iso_date(value: Any) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


_MEETING_SQL = """
    SELECT
        event_meeting_id,
        c1_event_id,
        body_name,
        jurisdiction_name,
        jurisdiction_type,
        state,
        state_code,
        CASE WHEN COALESCE(NULLIF(event_date, ''), NULLIF(meeting_date, '')) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
             THEN COALESCE(NULLIF(event_date, ''), NULLIF(meeting_date, '')) END AS meeting_date,
        video_id,
        __MEETING_TYPE__
    FROM event_meeting
    WHERE event_meeting_id = $1
"""

# Decisions / financial items share the meeting's c1_event_id (the stable cross-
# table meeting key), so join on that rather than the per-row analysis_id.
_MEETING_DECISIONS_SQL = """
    SELECT event_decision_id, headline, outcome, primary_theme
    FROM event_decision
    WHERE c1_event_id = $1
    ORDER BY headline
"""

_MEETING_FINANCIAL_SQL = """
    SELECT event_financial_item_id, financial_item_id, event_description,
           amount, amount_type
    FROM event_financial_item
    WHERE c1_event_id = $1
    ORDER BY amount DESC NULLS LAST
"""

# How the meeting's analysis was made (#1099): event_analysis_provenance is keyed by analysis_id, which for a meeting's
# decisions is the event_meeting_id. Best-effort: the table may not be published yet.
_MEETING_PROVENANCE_SQL = """
    SELECT video_id, ai_model, generated_at, analysis_tier, prompt_name, prompt_sha,
           transcript_source, analyses_for_meeting
    FROM event_analysis_provenance
    WHERE analysis_id = $1
"""

_MEETING_DOCUMENTS_SQL = """
    SELECT document_type, document_url, doc_date, body_name
    FROM event_meeting_document
    WHERE event_meeting_id = $1
    ORDER BY
        CASE document_type WHEN 'agenda' THEN 0 WHEN 'minutes' THEN 1 ELSE 2 END,
        doc_date NULLS LAST
"""


@router.get("/{event_meeting_id}", response_model=MeetingDetail)
async def get_meeting(event_meeting_id: int = Path(..., ge=1)) -> MeetingDetail:
    """Return one meeting (+ its decisions and financial items). 404 if absent."""
    with tracer.start_as_current_span("meeting-detail") as span:
        span.set_attribute("meeting.event_meeting_id", event_meeting_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                has_type = await meeting_type_available(conn)
                row = await conn.fetchrow(
                    _MEETING_SQL.replace(
                        "__MEETING_TYPE__", meeting_type_by_video_sql("event_meeting.video_id", has_type)
                    ),
                    event_meeting_id,
                )
                if row is None:
                    raise HTTPException(
                        status_code=404,
                        detail=f"No meeting found for event_meeting_id {event_meeting_id}",
                    )
                c1 = row["c1_event_id"]
                decisions = await conn.fetch(_MEETING_DECISIONS_SQL, c1) if c1 else []
                financial = await conn.fetch(_MEETING_FINANCIAL_SQL, c1) if c1 else []
                documents = await conn.fetch(
                    _MEETING_DOCUMENTS_SQL, event_meeting_id
                )
                prov_row = None
                try:
                    prov_row = await conn.fetchrow(_MEETING_PROVENANCE_SQL, event_meeting_id)
                except Exception as pv_err:  # noqa: BLE001 - never fail the meeting for the footer
                    logger.warning("provenance lookup failed for meeting {}: {}", event_meeting_id, pv_err)
        except HTTPException:
            raise
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("Meeting detail error for {}: {}", event_meeting_id, e)
            raise HTTPException(status_code=500, detail="Failed to load meeting")

        doc_models = [
            MeetingDocument(
                document_type=d["document_type"],
                document_url=d["document_url"],
                doc_date=_meeting_iso_date(d["doc_date"]),
                body_name=d["body_name"],
            )
            for d in documents
        ]
        logger.info(
            "🏛️ Meeting {} -> {} decisions, {} financial items, {} documents",
            event_meeting_id, len(decisions), len(financial), len(doc_models),
        )
        return await redact_response(MeetingDetail(
            event_meeting_id=row["event_meeting_id"],
            c1_event_id=c1,
            body_name=row["body_name"],
            jurisdiction_name=row["jurisdiction_name"],
            jurisdiction_type=row["jurisdiction_type"],
            state=row["state"],
            state_code=row["state_code"],
            meeting_date=_meeting_iso_date(row["meeting_date"]),
            video_id=row["video_id"],
            meeting_type=meeting_type_label(row["meeting_type"]),
            has_agenda=any(d.document_type == "agenda" for d in doc_models),
            has_minutes=any(d.document_type == "minutes" for d in doc_models),
            documents=doc_models,
            decisions=[
                MeetingDecision(
                    event_decision_id=d["event_decision_id"],
                    headline=d["headline"],
                    outcome=d["outcome"],
                    primary_theme=d["primary_theme"],
                )
                for d in decisions
            ],
            financial_items=[
                MeetingFinancialItem(
                    event_financial_item_id=f["event_financial_item_id"],
                    financial_item_id=f["financial_item_id"],
                    event_description=f["event_description"],
                    amount=float(f["amount"]) if f["amount"] is not None else None,
                    amount_type=f["amount_type"],
                )
                for f in financial
            ],
            provenance=build_provenance(
                dict(prov_row) if prov_row is not None else None, video_id=row["video_id"]
            ),
        ), SNIPPET_FIELDS | {"event_description"})
