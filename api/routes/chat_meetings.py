"""
Public meeting Q&A chat (#630).

Normal path: analyzed-meeting search (top 5 summaries) → one model call.
Detail path: one video's Neon segments → topic passages → one model call.
The model is Claude Haiku by default (#848); CHAT_PROVIDER=gemini keeps the Flash-Lite path.
No agent framework; no transcript dump into the prompt.
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

_RATE_PER_HOUR = int(os.environ.get("CHAT_RATE_PER_HOUR", "60"))
_BURST_PER_5MIN = int(os.environ.get("CHAT_BURST_PER_5MIN", "20"))
_MIN_INTERVAL_SECONDS = float(os.environ.get("CHAT_MIN_INTERVAL_SECONDS", "2"))
_DAILY_SPEND_CAP_USD = float(os.environ.get("CHAT_DAILY_SPEND_CAP_USD", "1.0"))
_PASSAGE_CHAR_CAP = int(os.environ.get("CHAT_PASSAGE_CHAR_CAP", "12000"))
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
    date: str
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
    mode: str
    usage: Optional[ChatUsage] = None
    # How the meetings were matched (#922): the question as typed, all of its content words, or any of them.
    match: Optional[str] = None


@dataclass
class MeetingContext:
    event_meeting_id: int
    title: str
    place: str
    date: str
    url: str
    video_id: Optional[str]
    summary: str


def _visitor_key(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    ip = (forwarded.split(",")[0].strip() if forwarded else None) or (
        request.client.host if request.client else "unknown"
    )
    cookie = request.cookies.get("on_chat_sid") or ""
    return hashlib.sha256(f"{ip}|{cookie}".encode()).hexdigest()[:32]


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
            k for k, ts in _visitor_timestamps.items() if not ts or now - ts[-1] >= _HOUR
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
    if _spend_by_utc_day.get(_utc_day_key(), 0.0) >= _DAILY_SPEND_CAP_USD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Daily chat budget reached. Try again tomorrow.",
        )


def _record_spend(usd: Optional[float]) -> None:
    if usd is None or usd <= 0:
        return
    key = _utc_day_key()
    _spend_by_utc_day[key] = _spend_by_utc_day.get(key, 0.0) + usd
    for k in list(_spend_by_utc_day):
        if k != key:
            _spend_by_utc_day.pop(k, None)


def _estimate_cost_usd(
    model: str,
    input_tokens: Optional[int],
    output_tokens: Optional[int],
    *,
    cached_tokens: int = 0,
) -> Optional[float]:
    """Cost from the sourced, dated price of ``model`` in prices.yaml; ``None`` when there is none."""
    if input_tokens is None or output_tokens is None:
        return None
    try:
        from llm.usage.prices import call_cost_usd, load_prices

        return call_cost_usd(
            {
                "model": model,
                "api_mode": "interactive",
                "input_token_count": input_tokens,
                "output_token_count": output_tokens,
                "cached_input_token_count": cached_tokens,
                "thinking_token_count": 0,
                "called_at": datetime.now(timezone.utc).isoformat(),
            },
            load_prices(),
        )
    except Exception as exc:  # noqa: BLE001
        # No guessed rate (#848): an unknown cost is reported as unknown.
        logger.warning("chat cost estimate skipped: {}", exc)
        return None


# Words that carry no topic in a question to this chat (#922): question words, glue, and the civic words that
# appear in nearly every meeting record. What is left is what the search looks for.
_CHAT_STOP_WORDS = frozenset(
    """a about after all also am an and any are as at be been before but by can could did do does for from had
    has have how i if in into is it its just me my of on or our over should so some than that the their them
    then there these they this to under up us was we were what when where which who whom why will with would
    you your tell show give find know say says said saying talk talks talked talking discuss discusses discussed
    discussing discussion mention mentions mentioned happen happens happened happening think thinks thought
    going get got go please recent recently latest lately today now anything something everything nothing
    council councils board boards commission commissions committee committees meeting meetings city cities
    county counties town towns local government governments official officials member members people public
    resident residents""".split()
)
_MAX_CHAT_TERMS = 8


def chat_search_terms(question: str) -> List[str]:
    """The content words of a question, lowercase, with quoted phrases kept whole; at most eight (#922).

    "What did councils say about data centers?" -> ["data", "centers"]. A question with nothing left
    ("what happened?") gives an empty list, and the caller keeps the typed-question search only.
    """
    text = (question or "").lower()
    terms: List[str] = [p.strip() for p in re.findall(r'"([^"]{2,60})"', text) if p.strip()]
    rest = re.sub(r'"[^"]*"', " ", text)
    for word in re.findall(r"[a-z0-9][a-z0-9'-]*", rest):
        word = word.strip("'-")
        if len(word) > 1 and word not in _CHAT_STOP_WORDS:
            terms.append(word)
    seen: List[str] = []
    for term in terms:
        if term not in seen:
            seen.append(term)
    return seen[:_MAX_CHAT_TERMS]


# One search document per meeting, and whether one term ($n is the term) is in it or in one of its decisions.
_CHAT_DOC_SQL = (
    "to_tsvector('english', coalesce(em.body_name, '') || ' ' || coalesce(em.jurisdiction_name, '') || ' ' || "
    "coalesce(em.city, '') || ' ' || coalesce(em.meeting_summary, '') || ' ' || coalesce(em.agenda_summary, ''))"
)


def _chat_term_hits_sql(terms_idx: int) -> str:
    """How many of the terms ($terms_idx::text[]) a meeting matches, in its own text or a decision's."""
    return (
        f"(SELECT count(*) FROM unnest(${terms_idx}::text[]) AS t(term) "
        f"WHERE x.doc @@ plainto_tsquery('english', t.term) "
        f"OR EXISTS (SELECT 1 FROM event_decision d WHERE d.c1_event_id = em.c1_event_id "
        f"AND d.search_tsv @@ plainto_tsquery('english', t.term)))"
    )


async def search_meetings_with_match(
    *,
    query: str,
    state: Optional[str] = None,
    city: Optional[str] = None,
    county_fips: Optional[str] = None,
    limit: int = 5,
) -> Tuple[List[MeetingContext], Optional[str]]:
    """Meetings for a chat question, and how they matched (#922).

    Strict first, widening only when nothing is found: the question as typed ("exact"), then every content
    word ("all_terms"), then any content word ranked by how many it matches ("any_term").
    """
    found = await search_analyzed_meetings_for_chat(
        query=query, state=state, city=city, county_fips=county_fips, limit=limit
    )
    if found:
        return found, "exact"
    terms = chat_search_terms(query)
    if not terms:
        return [], None
    for mode in ("all_terms", "any_term"):
        if mode == "any_term" and len(terms) == 1:
            break  # one term: "any" is the same search as "all"
        found = await search_analyzed_meetings_for_chat(
            query=query, state=state, city=city, county_fips=county_fips, limit=limit, terms=terms, match=mode
        )
        if found:
            return found, mode
    return [], None


async def search_analyzed_meetings_for_chat(
    *,
    query: str,
    state: Optional[str] = None,
    city: Optional[str] = None,
    county_fips: Optional[str] = None,
    limit: int = 5,
    terms: Optional[List[str]] = None,
    match: str = "exact",
) -> List[MeetingContext]:
    """Top matching analyzed meetings with full meeting_summary for the LLM prompt.

    ``match="exact"`` matches the question as typed. ``"all_terms"`` and ``"any_term"`` match ``terms``
    (from ``chat_search_terms``) and rank by how many a meeting matches. Terms are always parameters.
    """
    state = normalize_state_input(state)
    q = (query or "").strip()
    if not q:
        return []

    params: List[Any] = []
    hits_sql = ""
    if match == "exact" or not terms:
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
    else:
        params.append(list(terms))
        hits_sql = _chat_term_hits_sql(len(params))
        need = "cardinality($%d::text[])" % len(params) if match == "all_terms" else "1"
        where = [f"{hits_sql} >= {need}"]

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
    # Wider matches are ranked by how many terms a meeting has, then by date.
    rank_order = f"{hits_sql} DESC, " if hits_sql else ""
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
        CROSS JOIN LATERAL (SELECT {_CHAT_DOC_SQL} AS doc) x
        WHERE {" AND ".join(where)}
        ORDER BY {rank_order}{em_iso} DESC NULLS LAST, em.event_meeting_id DESC
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


def filter_topic_passages(
    cues: List[TranscriptCue],
    topic: str,
    *,
    char_cap: int = _PASSAGE_CHAR_CAP,
) -> List[str]:
    """Keep cue texts that mention the topic; cap total characters."""
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
    return f"Question: {question}\n\nMeetings:\n\n" + "\n\n".join(blocks)


def _passages_to_prompt(question: str, topic: str, video_id: str, passages: List[str]) -> str:
    body = "\n".join(passages) if passages else "(no matching passages)"
    return (
        f"Question: {question}\n"
        f"Topic filter: {topic}\n"
        f"Video id: {video_id}\n\n"
        f"Passages:\n{body}"
    )


def chat_provider() -> str:
    """``anthropic`` (default) or ``gemini``, from ``CHAT_PROVIDER`` (#848)."""
    name = (os.environ.get("CHAT_PROVIDER") or "anthropic").strip().lower()
    if name not in ("anthropic", "gemini"):
        raise ValueError(f"CHAT_PROVIDER must be 'anthropic' or 'gemini', not {name!r}")
    return name


def _call_claude(
    system: str, user: str
) -> Tuple[str, str, Optional[int], Optional[int], Optional[float]]:
    from llm.claude.text_client import DEFAULT_CHAT_MODEL, call_claude_text

    model = (os.environ.get("CHAT_MODEL") or "").strip() or DEFAULT_CHAT_MODEL
    result = call_claude_text(model=model, system=system, user_text=user)
    usd = _estimate_cost_usd(
        model, result.input_tokens, result.output_tokens, cached_tokens=result.cached_input_tokens
    )
    return result.text, model, result.input_tokens, result.output_tokens, usd


def _call_gemini(
    system: str, user: str
) -> Tuple[str, str, Optional[int], Optional[int], Optional[float]]:
    from llm.gemini.genai_text_client import (
        call_gemini_text,
        default_flash_lite_model,
        resolve_gemini_api_key,
    )

    model = (os.environ.get("CHAT_MODEL") or "").strip() or default_flash_lite_model()
    result = call_gemini_text(
        api_key=resolve_gemini_api_key(),
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


def _call_chat_model(
    system: str, user: str
) -> Tuple[str, str, Optional[int], Optional[int], Optional[float]]:
    """The chat's one model call: Claude Haiku by default, Gemini when ``CHAT_PROVIDER=gemini``."""
    if chat_provider() == "gemini":
        return _call_gemini(system, user)
    return _call_claude(system, user)


CHAT_NOT_SET_UP = "Chat is not set up on this site yet."


def chat_model_name() -> str:
    """The model the chat would call, without calling it."""
    override = (os.environ.get("CHAT_MODEL") or "").strip()
    if override:
        return override
    if chat_provider() == "gemini":
        from llm.gemini.genai_text_client import default_flash_lite_model

        return default_flash_lite_model()
    from llm.claude.text_client import DEFAULT_CHAT_MODEL

    return DEFAULT_CHAT_MODEL


def chat_missing_setting() -> Optional[str]:
    """The name of the key variable the chat's provider needs and does not have, or None (#916).

    Only names are returned and logged; a key's value is never read into a message.
    """
    if chat_provider() == "gemini":
        from llm.gemini.genai_text_client import resolve_gemini_api_key

        try:
            return None if (resolve_gemini_api_key() or "").strip() else "GEMINI_API_KEY"
        except Exception:  # noqa: BLE001 - the resolver raises when no key is configured
            return "GEMINI_API_KEY"
    return None if (os.environ.get("ANTHROPIC_API_KEY") or "").strip() else "ANTHROPIC_API_KEY"


def _require_chat_configured() -> None:
    """Answer 503 before any model call when the provider's key is not set (#916)."""
    missing = chat_missing_setting()
    if missing:
        logger.error("chat is not set up: provider={} needs {} and it is not set", chat_provider(), missing)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=CHAT_NOT_SET_UP)


def _log_model_failure(where: str, exc: Exception) -> None:
    """One error line that says what was called and how it failed, for the operator (#916)."""
    try:
        provider, model = chat_provider(), chat_model_name()
    except Exception:  # noqa: BLE001
        provider, model = "unknown", "unknown"
    logger.error(
        "{} model call failed: provider={} model={} error={} status={} detail={}",
        where,
        provider,
        model,
        type(exc).__name__,
        getattr(exc, "status_code", None),
        exc,
    )


class ChatStatus(BaseModel):
    provider: str
    model: str
    configured: bool


@router.get("/status", response_model=ChatStatus)
async def chat_status() -> ChatStatus:
    """Whether the chat can answer on this site: provider, model and whether its key is set. No secrets."""
    return ChatStatus(
        provider=chat_provider(), model=chat_model_name(), configured=chat_missing_setting() is None
    )


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


@router.post("/meetings", response_model=ChatMeetingsResponse)
async def chat_meetings(body: ChatMeetingsRequest, request: Request) -> ChatMeetingsResponse:
    with tracer.start_as_current_span("chat.meetings") as span:
        visitor = _visitor_key(request)
        span.set_attribute("chat.visitor", visitor)
        _check_rate_limit(visitor)
        _check_spend_cap()

        question = body.question.strip()
        filters = {"state": body.state, "city": body.city, "county_fips": body.county_fips}
        span.set_attribute("chat.question_len", len(question))

        if body.detail_video_id and body.detail_topic:
            return await _chat_passages(
                question=question,
                video_id=body.detail_video_id.strip(),
                topic=body.detail_topic.strip(),
                filters=filters,
                span=span,
            )

        meetings, match = await search_meetings_with_match(
            query=question,
            state=body.state,
            city=body.city,
            county_fips=body.county_fips,
            limit=5,
        )
        span.set_attribute("chat.meeting_hits", len(meetings))
        span.set_attribute("chat.match", match or "none")

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

        _require_chat_configured()
        prompt = _meetings_to_prompt(question, meetings)
        if match == "any_term":
            # Tell the model the match was loose, so it says so and does not stretch a weak meeting into an answer.
            prompt += (
                "\n\nNote: no meeting matched every word of the question. These meetings mention at least one of: "
                + ", ".join(chat_search_terms(question))
                + ". Say which of these terms each meeting you use is about, and say plainly if none answers the question."
            )
        try:
            text, model, in_tok, out_tok, usd = await run_in_threadpool(
                _call_chat_model, _SYSTEM_SUMMARIES, prompt
            )
        except Exception as exc:  # noqa: BLE001
            span.record_exception(exc)
            _log_model_failure("chat", exc)
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
                model=model, input_tokens=in_tok, output_tokens=out_tok, estimated_usd=usd
            ),
            match=match,
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

    _require_chat_configured()
    try:
        text, model, in_tok, out_tok, usd = await run_in_threadpool(
            _call_chat_model,
            _SYSTEM_PASSAGES,
            _passages_to_prompt(question, topic, video_id, passages),
        )
    except Exception as exc:  # noqa: BLE001
        span.record_exception(exc)
        _log_model_failure("chat passages", exc)
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
            model=model, input_tokens=in_tok, output_tokens=out_tok, estimated_usd=usd
        ),
    )
