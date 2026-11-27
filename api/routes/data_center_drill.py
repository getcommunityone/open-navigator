"""The records behind each "Who spoke up" number on the data center story (#1288).

Each list endpoint here returns the rows one story KPI counts, with the same filter the KPI's own
endpoint uses, so the list's total equals the number on the tile:

* ``GET /api/data-centers/speakers?side=for|against|question`` — the counted public speakers behind
  "spoke for / against / asked a question" (``/positions`` sums ``data_center_meeting_position``,
  whose per-meeting counts are these ``data_center_public_comment`` rows).
* ``GET /api/data-centers/vote-decisions?side=for|against`` — the decisions with a recorded tally behind
  "votes for / against"; ``total_votes`` is the tile (a sum of votes), ``total_decisions`` the rows.
* ``GET /api/data-centers/comments`` — the caption-segmented public comments behind the
  ``/comment-metrics`` counts (all, ``ai=true``, or ``company=<key>``). The mart carries no comment text
  (privacy by construction, #1233), so these rows link to the moment in the recording instead of quoting.

Every row is a real row of a ``public`` mart; nothing is invented or defaulted (CLAUDE.md, No Fabricated
Data). Residents appear only as the mart's "First L." (``speaker_display_name``); a comment flagged as a
possible minor is listed (so the count still adds up) with its name, link and keywords withheld (AGENTS.md,
Privacy). Each response echoes the applied scope so the list's label matches the data.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any, Literal

import asyncpg
from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.routes.data_center_comments import _where as comment_where
from api.routes.data_centers import JobClaimScope, build_scope, jump_url
from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/data-centers", tags=["data-centers"])
tracer = trace.get_tracer(__name__)

PAGE_DEFAULT = 25
PAGE_MAX = 100

# The dbt macro data_center_regex() in Python, to mark the data center words inside a verbatim quote.
DATA_CENTER_RE = re.compile(r"\b(data[ -]?cent(?:er|re)s?|datacent(?:er|re)s?|hyperscal(?:e|er|ers)?)\b", re.IGNORECASE)

WITHHELD_MINOR = "The speaker may be a minor, so the name, the link and the keywords are withheld."
NO_TEXT_NOTE = (
    "Comments segmented from our captions are stored without their words (privacy by construction, #1233): "
    "each one links to its moment in the recording instead of being quoted."
)


def mark_terms(quote: str | None) -> str | None:
    """The quote with each data center word wrapped in <mark> (for highlightSnippet); any <mark> already in the
    text is removed first so only our marks remain. The words themselves are unchanged."""
    if quote is None:
        return None
    clean = re.sub(r"</?mark>", "", quote)
    return DATA_CENTER_RE.sub(lambda m: f"<mark>{m.group(0)}</mark>", clean)


def applied_scope(state: str | None, city: str | None) -> JobClaimScope:
    """The scope ``/positions`` and ``/decisions`` apply: state, then city as a jurisdiction-name substring."""
    s = build_scope(state, city, None)
    return JobClaimScope(
        level="city" if s.city else ("state" if s.state_code else "national"),
        state_code=s.state_code,
        state=s.state,
        city=s.city,
    )


def position_where(scope: JobClaimScope, params: list[Any]) -> str:
    """The ``/positions`` totals filter, on the joined ``data_center_meeting_position p``."""
    where: list[str] = []
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"p.state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        where.append(f"p.jurisdiction_name ILIKE ${len(params)}")
    return " AND ".join(where) or "TRUE"


# --- speakers -----------------------------------------------------------------------------------------------------


class Speaker(BaseModel):
    public_comment_id: str
    quote: str | None = Field(None, description="The speaker's own words, verbatim from the transcript.")
    quote_highlighted: str | None = Field(None, description="The same words with data center terms in <mark>.")
    speaker_display_name: str | None = Field(None, description='"First L."; null when no name was heard.')
    speaker_role: str | None = None
    match_basis: str | None = Field(
        None, description="Why it counts: data_center_decision, data_center_item, own_words or same_item."
    )
    decision_headline: str | None = Field(None, description="The item the comment is on, when there is one.")
    event_decision_id: str | None = None
    jurisdiction_name: str | None = None
    state_code: str | None = None
    meeting_date: date | None = None
    video_url: str | None = None
    start_seconds: float | None = None
    jump_url: str | None = None


class SpeakersResponse(BaseModel):
    scope: JobClaimScope
    side: Literal["for", "against", "question"]
    available: bool = True
    total: int | None = Field(None, description="Every counted speaker on this side in scope (the tile's number).")
    limit: int
    offset: int
    items: list[Speaker] = Field(default_factory=list)


def build_speaker_queries(
    scope: JobClaimScope, side: str, limit: int, offset: int
) -> tuple[str, list[Any], str, list[Any]]:
    """(count SQL, params, page SQL, params). The rows the ``data_center_meeting_position`` speaker counts are made
    of: counted comments on the side, scoped on their meeting's position row exactly as ``/positions`` scopes."""
    params: list[Any] = [side]
    where = position_where(scope, params)
    base = (
        "FROM data_center_public_comment c "
        "JOIN data_center_meeting_position p ON p.data_center_meeting_position_id = c.data_center_meeting_position_id "
        f"WHERE c.is_counted AND c.stance_bucket = $1 AND {where}"
    )
    count_sql = f"SELECT count(*)::int AS n {base}"
    page_params = [*params, limit, offset]
    page_sql = (
        "SELECT c.public_comment_id, c.quote, c.speaker_display_name, c.speaker_role, c.match_basis, "
        "c.decision_headline, c.event_decision_id, p.jurisdiction_name, p.state_code, "
        "coalesce(c.meeting_date, p.meeting_date) AS meeting_date, c.video_url, c.start_seconds::float8 AS start_seconds "
        f"{base} "
        "ORDER BY coalesce(c.meeting_date, p.meeting_date) DESC NULLS LAST, c.event_meeting_id, "
        "c.start_seconds NULLS LAST, c.public_comment_id "
        f"LIMIT ${len(page_params) - 1} OFFSET ${len(page_params)}"
    )
    return count_sql, params, page_sql, page_params


@router.get("/speakers", response_model=SpeakersResponse)
async def data_center_speakers(
    side: Literal["for", "against", "question"] = Query(..., description="The tile: for, against or question."),
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the jurisdiction name."),
    limit: int = Query(PAGE_DEFAULT, ge=1, le=PAGE_MAX),
    offset: int = Query(0, ge=0),
) -> SpeakersResponse:
    """
    The public speakers behind "spoke for", "spoke against" or "asked a question" on the story's "Who spoke up"
    screen, each with their own words and the moment in the recording. ``total`` equals the tile.

    Example:
        GET /api/data-centers/speakers?side=against&state=AZ
    """
    scope = applied_scope(state, city)
    count_sql, params, page_sql, page_params = build_speaker_queries(scope, side, limit, offset)
    with tracer.start_as_current_span("data-centers.speakers") as span:
        span.set_attribute("drill.side", side)
        span.set_attribute("drill.scope_level", scope.level)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                count_rows = await conn.fetch(count_sql, *params)
                rows = await conn.fetch(page_sql, *page_params)
        except asyncpg.exceptions.UndefinedTableError as e:
            logger.warning("data-centers speakers: mart not loaded ({})", e)
            return SpeakersResponse(scope=scope, side=side, available=False, limit=limit, offset=offset)
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers speakers error (scope={}): {}", scope.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load the speakers")
        items: list[Speaker] = []
        for r in rows:
            row = dict(r)
            row["quote_highlighted"] = mark_terms(row.get("quote"))
            row["jump_url"] = jump_url(row["video_url"], row.get("start_seconds")) if row.get("video_url") else None
            items.append(Speaker(**row))
        total = int(count_rows[0]["n"]) if count_rows else 0
        span.set_attribute("drill.total", total)
        return SpeakersResponse(scope=scope, side=side, total=total, limit=limit, offset=offset, items=items)


# --- votes --------------------------------------------------------------------------------------------------------


class VoteDecision(BaseModel):
    data_center_decision_id: str
    headline: str | None = None
    outcome: str | None = None
    votes_for: int
    votes_against: int
    meeting_date: date | None = None
    jurisdiction_name: str | None = None
    state_code: str | None = None
    video_url: str | None = None
    decision_url: str | None = Field(None, description="Site path of the decision's page (/decisions/:id).")


class VoteDecisionsResponse(BaseModel):
    scope: JobClaimScope
    side: Literal["for", "against"]
    available: bool = True
    total_decisions: int | None = Field(None, description="Decisions with a recorded tally and a vote on this side.")
    total_votes: int | None = Field(None, description="Their votes on this side summed: the tile's number.")
    limit: int
    offset: int
    items: list[VoteDecision] = Field(default_factory=list)


def build_vote_queries(
    scope: JobClaimScope, side: str, limit: int, offset: int
) -> tuple[str, list[Any], str, list[Any]]:
    """(totals SQL, params, page SQL, params). ``data_center_meeting_position`` sums the tallies of the meeting's data
    center decisions where both sides parse; ``data_center_decision`` carries votes_for / votes_against only for
    those. Decisions with 0 votes on the side add nothing to the tile and are left out of its list."""
    col = "votes_for" if side == "for" else "votes_against"
    params: list[Any] = []
    where = position_where(scope, params)
    base = (
        "FROM data_center_decision d "
        "JOIN data_center_meeting_position p ON p.event_meeting_id = d.event_meeting_id "
        f"WHERE d.votes_for IS NOT NULL AND d.votes_against IS NOT NULL AND d.{col} > 0 AND {where}"
    )
    totals_sql = f"SELECT count(*)::int AS decisions, coalesce(sum(d.{col}), 0)::int AS votes {base}"
    page_params = [*params, limit, offset]
    page_sql = (
        "SELECT d.data_center_decision_id, d.headline, d.outcome, d.votes_for, d.votes_against, d.meeting_date, "
        "p.jurisdiction_name, p.state_code, d.video_url, d.decision_url "
        f"{base} ORDER BY d.meeting_date DESC NULLS LAST, d.data_center_decision_id "
        f"LIMIT ${len(page_params) - 1} OFFSET ${len(page_params)}"
    )
    return totals_sql, params, page_sql, page_params


@router.get("/vote-decisions", response_model=VoteDecisionsResponse)
async def data_center_vote_decisions(
    side: Literal["for", "against"] = Query(..., description="The tile: for or against."),
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the jurisdiction name."),
    limit: int = Query(PAGE_DEFAULT, ge=1, le=PAGE_MAX),
    offset: int = Query(0, ge=0),
) -> VoteDecisionsResponse:
    """
    The decisions behind "votes for" or "votes against": each data center decision with a recorded tally and at
    least one vote on that side, newest first. ``total_votes`` equals the tile.

    Example:
        GET /api/data-centers/vote-decisions?side=for&state=AL
    """
    scope = applied_scope(state, city)
    totals_sql, params, page_sql, page_params = build_vote_queries(scope, side, limit, offset)
    with tracer.start_as_current_span("data-centers.vote-decisions") as span:
        span.set_attribute("drill.side", side)
        span.set_attribute("drill.scope_level", scope.level)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                totals = await conn.fetch(totals_sql, *params)
                rows = await conn.fetch(page_sql, *page_params)
        except asyncpg.exceptions.UndefinedTableError as e:
            logger.warning("data-centers vote-decisions: mart not loaded ({})", e)
            return VoteDecisionsResponse(scope=scope, side=side, available=False, limit=limit, offset=offset)
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers vote-decisions error (scope={}): {}", scope.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load the decisions")
        t = dict(totals[0]) if totals else {"decisions": 0, "votes": 0}
        return VoteDecisionsResponse(
            scope=scope,
            side=side,
            total_decisions=int(t["decisions"]),
            total_votes=int(t["votes"]),
            limit=limit,
            offset=offset,
            items=[VoteDecision(**dict(r)) for r in rows],
        )


# --- caption comments ---------------------------------------------------------------------------------------------


class CaptionComment(BaseModel):
    data_center_comment_id: str
    speaker_display_name: str | None = Field(None, description='"First L."; null when unknown or withheld.')
    possible_minor: bool = False
    withheld_reason: str | None = None
    jurisdiction_name: str | None = None
    state_code: str | None = None
    meeting_date: date | None = None
    start_seconds: float | None = None
    jump_url: str | None = Field(None, description="The recording at the comment's start; null for a possible minor.")
    concern_keys: list[str] = Field(default_factory=list)
    company_keys: list[str] = Field(default_factory=list)
    mentions_ai: bool | None = None


class CaptionCommentsResponse(BaseModel):
    scope: JobClaimScope
    year: str | None = Field(None, description="Calendar year filter as a string; null for all years.")
    filter: Literal["all", "ai", "company"] = "all"
    company: str | None = None
    available: bool = True
    total: int | None = Field(None, description="Every comment matching the filter in scope (the tile's number).")
    limit: int
    offset: int
    note: str = NO_TEXT_NOTE
    items: list[CaptionComment] = Field(default_factory=list)


def build_comment_queries(
    scope: JobClaimScope, year: int | None, ai: bool, company: str | None, limit: int, offset: int
) -> tuple[str, list[Any], str, list[Any]]:
    """(count SQL, params, page SQL, params) over ``data_center_comment`` with ``/comment-metrics``' own filter (its
    ``_where``), plus ``mentions_ai`` or the company key when the tile is one of those."""
    where, params = comment_where(scope, year)
    extra: list[str] = []
    if ai:
        extra.append("mentions_ai")
    if company:
        params = [*params, company]
        extra.append(f"${len(params)} = ANY(company_keys)")
    if extra:
        where = f"{where} AND {' AND '.join(extra)}" if where else f" WHERE {' AND '.join(extra)}"
    count_sql = f"SELECT count(*)::int AS n FROM data_center_comment{where}"
    page_params = [*params, limit, offset]
    page_sql = (
        "SELECT data_center_comment_id, speaker_display_name, coalesce(possible_minor, false) AS possible_minor, "
        "jurisdiction_name, state_code, meeting_date, start_seconds::float8 AS start_seconds, video_id, "
        "coalesce(concern_keys, '{}') AS concern_keys, coalesce(company_keys, '{}') AS company_keys, mentions_ai "
        f"FROM data_center_comment{where} "
        "ORDER BY meeting_date DESC NULLS LAST, jurisdiction_name, video_id, start_seconds NULLS LAST, data_center_comment_id "
        f"LIMIT ${len(page_params) - 1} OFFSET ${len(page_params)}"
    )
    return count_sql, params, page_sql, page_params


def shape_comment(row: dict[str, Any]) -> CaptionComment:
    video_id = row.pop("video_id", None)
    if row.get("possible_minor"):
        return CaptionComment(
            data_center_comment_id=row["data_center_comment_id"],
            possible_minor=True,
            withheld_reason=WITHHELD_MINOR,
            jurisdiction_name=row.get("jurisdiction_name"),
            state_code=row.get("state_code"),
            meeting_date=row.get("meeting_date"),
        )
    url = f"https://www.youtube.com/watch?v={video_id}" if video_id else None
    row["jump_url"] = jump_url(url, row.get("start_seconds")) if url else None
    return CaptionComment(**row)


@router.get("/comments", response_model=CaptionCommentsResponse)
async def data_center_caption_comments(
    year: int = Query(2026, ge=0, le=2100, description="Meeting year (default 2026); 0 for all years."),
    state: str | None = Query(None, description="2-letter code or full state name."),
    city: str | None = Query(None, description="City / jurisdiction name (substring)."),
    ai: bool = Query(False, description="Only comments that mention AI (the 'Mention AI' tile)."),
    company: str | None = Query(None, max_length=64, description="Only comments naming this company key."),
    limit: int = Query(PAGE_DEFAULT, ge=1, le=PAGE_MAX),
    offset: int = Query(0, ge=0),
) -> CaptionCommentsResponse:
    """
    The public comments behind the caption counts under "Who spoke up" ("60 public comments", "Mention AI",
    "Name Google"): each comment's place, date, speaker ("First L." when known) and the link to its moment in
    the recording. ``total`` equals the tile. No comment text is served (see ``note``).

    Example:
        GET /api/data-centers/comments?year=2026&state=AL
    """
    scope = build_scope(state, city, None)
    year_filter = year or None
    company_key = company.strip() if company and company.strip() else None
    count_sql, params, page_sql, page_params = build_comment_queries(
        scope, year_filter, ai, company_key, limit, offset
    )
    flt: Literal["all", "ai", "company"] = "ai" if ai else ("company" if company_key else "all")
    with tracer.start_as_current_span("data-centers.comments") as span:
        span.set_attribute("drill.filter", flt)
        span.set_attribute("drill.scope_level", scope.level)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                count_rows = await conn.fetch(count_sql, *params)
                rows = await conn.fetch(page_sql, *page_params)
        except asyncpg.exceptions.UndefinedTableError as e:
            logger.warning("data-centers comments: mart not loaded ({})", e)
            return CaptionCommentsResponse(
                scope=scope, year=str(year_filter) if year_filter else None, filter=flt, company=company_key,
                available=False, limit=limit, offset=offset,
            )
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers comments error (scope={}): {}", scope.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load the comments")
        return CaptionCommentsResponse(
            scope=scope,
            year=str(year_filter) if year_filter else None,
            filter=flt,
            company=company_key,
            total=int(count_rows[0]["n"]) if count_rows else 0,
            limit=limit,
            offset=offset,
            items=[shape_comment(dict(r)) for r in rows],
        )


# --- officials sided against the public (#1330) -----------------------------------------------------------------------


class DisagreementMeeting(BaseModel):
    """One meeting where the transcript reading found officials on the other side from the public (#1330)."""

    video_id: str
    jurisdiction_name: str | None = None
    state_code: str | None = None
    meeting_date: date | None = None
    public_lean: str | None = Field(None, description="The reading of the public's position (e.g. mostly_opposed).")
    official_lean: str | None = Field(None, description="The reading of officials' position (e.g. mostly_supportive).")
    outcome: str | None = Field(None, description="The reading of what the meeting did on the item, when one was read.")
    video_url: str | None = Field(None, description="The meeting's recording; null when it has none.")


class DisagreementMeetingsResponse(BaseModel):
    scope: JobClaimScope
    available: bool = Field(True, description="False when data_center_meeting_lean isn't loaded: total is null, not 0.")
    total: int | None = Field(None, description="Meetings in scope where officials sided against the public.")
    limit: int = PAGE_DEFAULT
    offset: int = 0
    items: list[DisagreementMeeting] = Field(default_factory=list)


def build_disagreement_queries(scope: JobClaimScope, limit: int, offset: int) -> tuple[str, list[Any], str, list[Any]]:
    """(total SQL, params, page SQL, params): the ``officials_sided_against_public`` meetings of the reading, the same flag
    caption-facts counts as ``disagreement_meetings``, so the list's total equals the number tapped."""
    params: list[Any] = []
    where = ["l.officials_sided_against_public"]
    if scope.state_code:
        params.append(scope.state_code)
        where.append(f"l.state_code = ${len(params)}")
    if scope.city:
        params.append(f"%{scope.city}%")
        where.append(f"l.jurisdiction_name ILIKE ${len(params)}")
    where_sql = " AND ".join(where)
    total_sql = f"SELECT count(*)::int AS n FROM data_center_meeting_lean l WHERE {where_sql}"
    page_params = [*params, limit, offset]
    page_sql = (
        "SELECT l.video_id, l.jurisdiction_name, l.state_code, l.meeting_date, l.public_lean, l.official_lean, "
        "l.dc_outcome AS outcome, "
        "CASE WHEN l.video_id IS NOT NULL THEN 'https://www.youtube.com/watch?v=' || l.video_id END AS video_url "
        f"FROM data_center_meeting_lean l WHERE {where_sql} "
        "ORDER BY l.meeting_date DESC NULLS LAST, l.video_id "
        f"LIMIT ${len(page_params) - 1} OFFSET ${len(page_params)}"
    )
    return total_sql, params, page_sql, page_params


@router.get("/disagreement-meetings", response_model=DisagreementMeetingsResponse)
async def data_center_disagreement_meetings(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring of the jurisdiction name."),
    limit: int = Query(PAGE_DEFAULT, ge=1, le=PAGE_MAX),
    offset: int = Query(0, ge=0),
) -> DisagreementMeetingsResponse:
    """
    The meetings behind "officials sided against the public in N meetings" (#1330), newest first. ``total`` equals the
    caption facts' ``disagreement_meetings`` for the same scope.

    Example:
        GET /api/data-centers/disagreement-meetings?state=GA
    """
    scope = applied_scope(state, city)
    total_sql, params, page_sql, page_params = build_disagreement_queries(scope, limit, offset)
    with tracer.start_as_current_span("data-centers.disagreement-meetings") as span:
        span.set_attribute("drill.scope_level", scope.level)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                totals = await conn.fetch(total_sql, *params)
                rows = await conn.fetch(page_sql, *page_params)
        except asyncpg.exceptions.UndefinedTableError as e:
            logger.warning("data-centers disagreement-meetings: mart not loaded ({})", e)
            return DisagreementMeetingsResponse(scope=scope, available=False, limit=limit, offset=offset)
        except Exception as e:  # noqa: BLE001
            span.record_exception(e)
            logger.error("data-centers disagreement-meetings error (scope={}): {}", scope.model_dump(), e)
            raise HTTPException(status_code=500, detail="Failed to load the meetings")
        n = int(dict(totals[0])["n"]) if totals else 0
        return DisagreementMeetingsResponse(
            scope=scope,
            total=n,
            limit=limit,
            offset=offset,
            items=[DisagreementMeeting(**dict(r)) for r in rows],
        )
