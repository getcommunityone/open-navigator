"""
Public meeting Q&A chat (#630).

Normal path: analyzed-meeting search (top 5 summaries) → one Flash-Lite call.
Detail path: one video's Neon segments (or Azure blob later) → topic passages →
one Flash-Lite call. No agent framework; no transcript dump into the prompt.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, HTTPException, Request, status
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from api.routes.meetings import TranscriptCue, _coerce_segments
from api.routes.search_postgres import (
    get_db_pool,
    normalize_state_input,
    resolve_county_city_names,
)

router = APIRouter(prefix="/chat", tags=["chat"])
tracer = trace.get_tracer(__name__)

# --- Limits (env-overridable; defaults from #630) ---------------------------------
_RATE_PER_HOUR = int(os.environ.get("CHAT_RATE_PER_HOUR", "60"))
_BURST_PER_5MIN = int(os.environ.get("CHAT_BURST_PER_5MIN", "20"))
_MIN_INTERVAL_SECONDS = float(os.environ.get("CHAT_MIN_INTERVAL_SECONDS", "2"))
_DAILY_SPEND_CAP_USD = float(os.environ.get("CHAT_DAILY_SPEND_CAP_USD", "1.0"))
_PASSAGE_CHAR_CAP = int(os.environ.get("CHAT_PASSAGE_CHAR_CAP", "12000"))  # ~3k tokens
_MAX_TRACKED_VISITORS = 2048

_HOUR = 3600.0
_FIVE_MIN = 300.0

_visitor_timestamps: Dict[str, List[float]] = {}
_visitor_last: Dict[str, float] = {}
_spend_by_utc_day: Dict[str, float] = {}


def clear_chat_rate_limits() -> None:
    """Test helper: reset in-memory rate / spend state."""
    _visitor_timestamps.clear()
    _visitor_last.clear()
    _spend_by_utc_day.clear()


# --- Request / response ----------------------------------------------------------


class ChatMeetingsRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    state: Optional[str] = None
    city: Optional[str] = None
    county_fips: Optional[str] = None
    detail_video_id: Optional[str] = Field(
        default=None,
        description="When set with detail_topic, run quote/detail path for one video",
    )
    detail_topic: Optional[str] = None


class ChatCitation(BaseModel):
    title: str
    place: str
    date: str  # ISO calendar date as string (wire form)
    url: str
    event_meeting_id: Optional[int] = None
    video_id: Optional[str] = None


class ChatUsage(BaseModel):
    model: str
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    estimated_usd: Optional[float] = None


class ChatMeetingsResponse(BaseModel):
    answer: str
    citations: List[ChatCitation]
    found: bool
    mode: str  # "summaries" | "passages"
    usage: Optional[ChatUsage] = None


@dataclass
class MeetingContext:
    event_meeting_id: int
    title: str
    place: str
    date: str
    url: str
    video_id: Optional[str]
    summary: str


# --- Rate / spend ----------------------------------------------------------------


def _visitor_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    ip = (forwarded.split(",")[0].strip() if forwarded else None) or (
        request.client.host if request.client else "unknown"
    )
    cookie = request.cookies.get("on_chat_sid") or ""
    raw = f"{ip}|{cookie}"
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


def _check_rate_limit(visitor: str) -> None:
    now = time.monotonic()
    last = _visitor_last.get(visitor)
    if last is not None and (now - last) < _MIN_INTERVAL_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait a moment before sending another message.",
        )

    if len(_visitor_timestamps) >= _MAX_TRACKED_VISITORS and visitor not in _visitor_timestamps:
        stale = [
            k
            for k, ts in _visitor_timestamps.items()
            if not ts or now - ts[-1] >= _HOUR
        ]
        for k in stale:
            _visitor_timestamps.pop(k, None)
            _visitor_last.pop(k, None)

    history = [t for t in _visitor_timestamps.get(visitor, []) if now - t < _HOUR]
    if len(history) >= _RATE_PER_HOUR:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Hourly chat limit reached. Try again later.",
        )
    burst = [t for t in history if now - t < _FIVE_MIN]
    if len(burst) >= _BURST_PER_5MIN:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many messages in a short time. Please slow down.",
        )

    history.append(now)
    _visitor_timestamps[visitor] = history
    _visitor_last[visitor] = now


def _utc_day_key() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _check_spend_cap() -> None:
    spent = _spend_by_utc_day.get(_utc_day_key(), 0.0)
    if spent >= _DAILY_SPEND_CAP_USD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Daily chat budget reached. Try again tomorrow.",
        )


def _record_spend(usd: Optional[float]) -> None:
    if usd is None or usd <= 0:
        return
    key = _utc_day_key()
    _spend_by_utc_day[key] = _spend_by_utc_day.get(key, 0.0) + usd
    # Drop older days
    for k in list(_spend_by_utc_day):
        if k != key:
            _spend_by_utc_day.pop(k, None)


def _estimate_cost_usd(model: str, input_tokens: Optional[int], output_tokens: Optional[int]) -> Optional[float]:
    if input_tokens is None or output_tokens is None:
        return None
    try:
        from llm.usage.prices import call_cost_usd, load_prices

        prices = load_prices()
        return call_cost_usd(
            {
                "model": model,
                "api_mode": "interactive",
                "input_token_count": input_tokens,
                "output_token_count": output_tokens,
                "cached_input_token_count": 0,
                "thinking_token_count": 0,
                "called_at": datetime.now(timezone.utc).isoformat(),
            },
            prices,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("chat cost estimate skipped: {}", exc)
        # Fallback Flash-Lite rates from prices.yaml (2026-11-14)
        return round(
            (input_tokens * 0.10 + output_tokens * 0.40) / 1_000_000,
            6,
        )


# --- Search (analyzed only) ------------------------------------------------------


async def search_analyzed_meetings_for_chat(
    *,
    query: str,
    state: Optional[str] = None,
    city: Optional[str] = None,
    county_fips: Optional[str] = None,
    limit: int = 5,
) -> List[MeetingContext]:
    """Top matching analyzed meetings with full meeting_summary for the LLM prompt."""
    state = normalize_state_input(state)
    q = (query or "").strip()
    if not q:
        return []

    params: List[Any] = []
    params.append(f"%{q}%")
    q_like_idx = len(params)
    params.append(q)
    q_fts_idx = len(params)

    where: List[str] = [
        f"(em.body_name ILIKE ${q_like_idx} OR em.jurisdiction_name ILIKE ${q_like_idx} "
        f"OR em.meeting_summary ILIKE ${q_like_idx} OR em.city ILIKE ${q_like_idx} "
        f"OR EXISTS (SELECT 1 FROM event_decision d "
        f"WHERE d.c1_event_id = em.c1_event_id "
        f"AND d.search_tsv @@ plainto_tsquery('english', ${q_fts_idx})))"
    ]

    if state:
        params.append(state.upper())
        where.append(f"em.state_code = ${len(params)}")

    use_county = bool(county_fips and county_fips.strip())
    if use_county:
        names = await resolve_county_city_names(county_fips)
        if names:
            params.append([n.lower() for n in names])
            where.append(
                f"(lower(em.jurisdiction_name) = ANY(${len(params)}) "
                f"OR lower(em.city) = ANY(${len(params)}))"
            )
        else:
            where.append("FALSE")
    elif city and city.strip():
        params.append(city.strip())
        where.append(
            f"(lower(em.jurisdiction_name) = lower(${len(params)}) "
            f"OR lower(em.city) = lower(${len(params)}))"
        )

    params.append(max(1, min(limit, 5)))
    limit_idx = len(params)
    em_iso = (
        "(CASE WHEN em.meeting_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' "
        "THEN em.meeting_date END)"
    )
    sql = f"""
        SELECT
            em.event_meeting_id,
            em.body_name,
            em.jurisdiction_name,
            em.state,
            em.state_code,
            em.city,
            {em_iso} AS iso_date,
            em.meeting_summary,
            em.agenda_summary,
            em.video_id
        FROM event_meeting em
        WHERE {" AND ".join(where)}
        ORDER BY {em_iso} DESC NULLS LAST, em.event_meeting_id DESC
        LIMIT ${limit_idx}
    """

    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(sql, *params)

    out: List[MeetingContext] = []
    for row in rows:
        place_bits = [p for p in (row["jurisdiction_name"], row["state"]) if p]
        place = ", ".join(place_bits) if place_bits else (row["city"] or "")
        date_str = row["iso_date"] or ""
        if isinstance(date_str, date):
            date_str = date_str.isoformat()
        title = row["body_name"] or row["jurisdiction_name"] or "Meeting"
        summary = (row["meeting_summary"] or row["agenda_summary"] or "").strip()
        mid = int(row["event_meeting_id"])
        out.append(
            MeetingContext(
                event_meeting_id=mid,
                title=title,
                place=place,
                date=str(date_str),
                url=f"/meetings/{mid}",
                video_id=row["video_id"],
                summary=summary,
            )
        )
    return out


# --- Passages --------------------------------------------------------------------


def filter_topic_passages(
    cues: List[TranscriptCue],
    topic: str,
    *,
    char_cap: int = _PASSAGE_CHAR_CAP,
) -> List[str]:
    """Keep cue texts that mention the topic; cap total characters (never dump full transcript)."""
    terms = [t for t in re.split(r"\W+", (topic or "").lower()) if len(t) >= 3]
    if not terms:
        terms = [(topic or "").strip().lower()]
    terms = [t for t in terms if t]
    passages: List[str] = []
    used = 0
    for cue in cues:
        text = cue.text.strip()
        if not text:
            continue
        low = text.lower()
        if not any(t in low for t in terms):
            continue
        line = f"[{int(cue.start)}s] {text}"
        if used + len(line) > char_cap:
            break
        passages.append(line)
        used += len(line) + 1
    return passages


async def load_segments_for_video(video_id: str) -> List[TranscriptCue]:
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT segments
            FROM public.event_documents
            WHERE video_id = $1 AND document_type = 'transcript'
            LIMIT 1
            """,
            video_id,
        )
    if not row:
        return []
    return _coerce_segments(row["segments"])


# --- LLM -------------------------------------------------------------------------

_SYSTEM_SUMMARIES = """You answer questions about local government meetings using ONLY the meeting summaries provided.
Rules:
- Base every claim on those summaries. If they do not cover the question, say you found nothing relevant in the meetings provided.
- Cite meetings by title, place, and date for each substantive point.
- Never invent dollar amounts, vote counts, or other figures that are not in the summaries.
- Keep the answer concise (a few short paragraphs).
- Respond as plain text (no JSON wrapper).
"""

_SYSTEM_PASSAGES = """You answer using ONLY the transcript passages provided from one meeting.
Rules:
- Quote or paraphrase only from those passages; cite the timestamps when useful.
- If the passages do not answer the question, say so clearly.
- Never invent figures or quotes that are not in the passages.
- Keep the answer concise. Plain text only.
"""


def _meetings_to_prompt(question: str, meetings: List[MeetingContext]) -> str:
    blocks = []
    for i, m in enumerate(meetings, 1):
        blocks.append(
            f"[{i}] Title: {m.title}\n"
            f"Place: {m.place}\n"
            f"Date: {m.date}\n"
            f"Link: {m.url}\n"
            f"Summary: {m.summary or '(no summary)'}"
        )
    return (
        f"Question: {question}\n\n"
        f"Meetings:\n\n" + "\n\n".join(blocks)
    )


def _passages_to_prompt(question: str, topic: str, video_id: str, passages: List[str]) -> str:
    body = "\n".join(passages) if passages else "(no matching passages)"
    return (
        f"Question: {question}\n"
        f"Topic filter: {topic}\n"
        f"Video id: {video_id}\n\n"
        f"Passages:\n{body}"
    )


def _call_flash_lite(system: str, user: str) -> Tuple[str, str, Optional[int], Optional[int], Optional[float]]:
    from llm.gemini.genai_text_client import (
        call_gemini_text,
        default_flash_lite_model,
        resolve_gemini_api_key,
    )

    model = default_flash_lite_model()
    api_key = resolve_gemini_api_key()
    result = call_gemini_text(
        api_key=api_key,
        model=model,
        user_text=user,
        system_instruction=system,
        temperature=0.2,
        max_output_tokens=1024,
        thinking_budget=0,
    )
    usage = result.usage
    in_tok = getattr(usage, "input_token_count", None) if usage else None
    out_tok = getattr(usage, "output_token_count", None) if usage else None
    usd = _estimate_cost_usd(model, in_tok, out_tok)
    return (result.text or "").strip(), model, in_tok, out_tok, usd


def _answer_looks_empty(text: str) -> bool:
    low = (text or "").lower()
    if not text.strip():
        return True
    markers = (
        "nothing relevant",
        "no relevant",
        "not find",
        "don't have enough",
        "do not have enough",
        "no meetings",
        "couldn't find",
        "could not find",
    )
    return any(m in low for m in markers)


def _log_zero_result(question: str, *, mode: str, filters: dict) -> None:
    q_hash = hashlib.sha256(question.encode()).hexdigest()[:16]
    logger.info(
        "chat.zero_result mode={} q_hash={} q_len={} filters={}",
        mode,
        q_hash,
        len(question),
        json.dumps(filters, sort_keys=True),
    )


# --- Endpoint --------------------------------------------------------------------


@router.post("/meetings", response_model=ChatMeetingsResponse)
async def chat_meetings(body: ChatMeetingsRequest, request: Request) -> ChatMeetingsResponse:
    with tracer.start_as_current_span("chat.meetings") as span:
        visitor = _visitor_key(request)
        span.set_attribute("chat.visitor", visitor)
        _check_rate_limit(visitor)
        _check_spend_cap()

        question = body.question.strip()
        filters = {
            "state": body.state,
            "city": body.city,
            "county_fips": body.county_fips,
        }
        span.set_attribute("chat.question_len", len(question))

        # Detail / quote path
        if body.detail_video_id and body.detail_topic:
            return await _chat_passages(
                question=question,
                video_id=body.detail_video_id.strip(),
                topic=body.detail_topic.strip(),
                filters=filters,
                span=span,
            )

        meetings = await search_analyzed_meetings_for_chat(
            query=question,
            state=body.state,
            city=body.city,
            county_fips=body.county_fips,
            limit=5,
        )
        span.set_attribute("chat.meeting_hits", len(meetings))

        citations = [
            ChatCitation(
                title=m.title,
                place=m.place,
                date=m.date,
                url=m.url,
                event_meeting_id=m.event_meeting_id,
                video_id=m.video_id,
            )
            for m in meetings
        ]

        if not meetings:
            _log_zero_result(question, mode="summaries", filters=filters)
            return ChatMeetingsResponse(
                answer=(
                    "No matching analyzed meetings were found for that question "
                    "in the current scope. Try different wording or broaden the place filter."
                ),
                citations=[],
                found=False,
                mode="summaries",
            )

        user_prompt = _meetings_to_prompt(question, meetings)
        try:
            text, model, in_tok, out_tok, usd = await run_in_threadpool(
                _call_flash_lite, _SYSTEM_SUMMARIES, user_prompt
            )
        except Exception as exc:  # noqa: BLE001
            span.record_exception(exc)
            logger.error("chat Flash-Lite failed: {}", exc)
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="The answer service is temporarily unavailable.",
            ) from exc

        _record_spend(usd)
        found = not _answer_looks_empty(text)
        if not found:
            _log_zero_result(question, mode="summaries", filters=filters)

        return ChatMeetingsResponse(
            answer=text or "No answer was returned.",
            citations=citations,
            found=found,
            mode="summaries",
            usage=ChatUsage(
                model=model,
                input_tokens=in_tok,
                output_tokens=out_tok,
                estimated_usd=usd,
            ),
        )


async def _chat_passages(
    *,
    question: str,
    video_id: str,
    topic: str,
    filters: dict,
    span: Any,
) -> ChatMeetingsResponse:
    span.set_attribute("chat.mode", "passages")
    span.set_attribute("chat.video_id", video_id)
    cues = await load_segments_for_video(video_id)
    passages = filter_topic_passages(cues, topic)
    span.set_attribute("chat.passage_count", len(passages))

    if not passages:
        _log_zero_result(question, mode="passages", filters={**filters, "video_id": video_id})
        return ChatMeetingsResponse(
            answer=(
                "No transcript passages mentioning that topic were found for this meeting. "
                "The recording may lack cues, or the topic wording may not appear in the transcript."
            ),
            citations=[],
            found=False,
            mode="passages",
        )

    user_prompt = _passages_to_prompt(question, topic, video_id, passages)
    try:
        text, model, in_tok, out_tok, usd = await run_in_threadpool(
            _call_flash_lite, _SYSTEM_PASSAGES, user_prompt
        )
    except Exception as exc:  # noqa: BLE001
        span.record_exception(exc)
        logger.error("chat passages Flash-Lite failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The answer service is temporarily unavailable.",
        ) from exc

    _record_spend(usd)
    found = not _answer_looks_empty(text)
    if not found:
        _log_zero_result(question, mode="passages", filters={**filters, "video_id": video_id})

    return ChatMeetingsResponse(
        answer=text or "No answer was returned.",
        citations=[
            ChatCitation(
                title="Meeting transcript",
                place="",
                date="",
                url=f"https://www.youtube.com/watch?v={video_id}",
                video_id=video_id,
            )
        ],
        found=found,
        mode="passages",
        usage=ChatUsage(
            model=model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            estimated_usd=usd,
        ),
    )
