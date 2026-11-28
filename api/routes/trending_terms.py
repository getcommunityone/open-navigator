"""
Trending terms and hot words in meeting speech (#1399) — the data behind the "Trending in meetings" chips on Browse
all topics (``/browse-topics/all``).

``GET /api/trends/terms?state=&sort=rising|hot|volume&limit=``
    The served terms (``public.trending_term``, ``is_served``) for the national scope or one state, ranked by rise in
    the share of recorded meetings that say the term (this year to date against last year), by how over-represented
    the term is in heated public comment (``hot_score``), or by meetings this year. Only ranked rows are returned: a
    term that isn't rising is never listed under "rising", and one without enough heated speakers is never listed under
    "hot".

``GET /api/trends/terms/{term_id}/evidence?state=&limit=&offset=``
    The meetings behind one term (``public.trending_term_evidence``): a verbatim excerpt with the term in
    ``<mark>``…``</mark>``, the public commenter's "First L." when the excerpt is their own segment (never for a
    sensitive term), newest first. ``total_meetings`` is the term's real meeting count in the scope; ``total`` is how
    many excerpts are stored (the newest ones).

Everything comes from the dbt marts (free, deterministic, no LLM). Years go on the wire as strings (CLAUDE.md). City
scope isn't counted at that grain: the API answers for the state and says so (``scope.level``).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.routes.search_postgres import get_db_pool
from api.routes.topic_timeline import build_scope

router = APIRouter(prefix="/api/trends", tags=["trends"])
tracer = trace.get_tracer(__name__)

Sort = Literal["rising", "hot", "volume"]
RANK_COLUMN: dict[str, str] = {"rising": "rank_rising", "hot": "rank_hot", "volume": "rank_volume"}
MAX_LIMIT = 100
MAX_EVIDENCE_LIMIT = 50


class TrendScope(BaseModel):
    level: Literal["national", "state"]
    state_code: str | None = None
    state: str | None = None
    requested_city: str | None = Field(
        None, description="A city asked for in the request. Terms aren't counted per city, so the state is answered."
    )


class TrendTerm(BaseModel):
    term_id: str = Field(..., description="trending_term.term_key (the same id in every scope).")
    term: str
    rank: int
    meetings_a: int
    meetings_b: int
    recorded_a: int
    recorded_b: int
    share_a: float | None = None
    share_b: float | None = None
    rise: float | None = Field(None, description="share_b / share_a; null when the term wasn't said in year_a.")
    n_meetings: int
    n_jurisdictions: int = Field(..., description="Governments that said the term in year_b.")
    hot_score: float | None = Field(None, description="National log-odds z-score in heated public comment.")
    is_sensitive: bool = Field(..., description="A sensitive term: shown as counts only, never tied to a speaker.")
    latest_meeting_date: str | None = None


class TrendTermsResponse(BaseModel):
    scope: TrendScope
    sort: Sort
    year_a: str | None = None
    year_b: str | None = None
    terms: list[TrendTerm]


class TrendEvidence(BaseModel):
    video_id: str
    meeting_title: str
    meeting_date: str
    jurisdiction_name: str | None = None
    state_code: str | None = None
    video_url: str | None = None
    excerpt: str = Field(..., description="Verbatim excerpt with the term in <mark>…</mark>.")
    excerpt_source: str = Field(..., description="public_comment (a speaker's own segment) or transcript.")
    start_seconds: float | None = None
    speaker_display_name: str | None = Field(None, description='"First L.", or null when not identified.')


class TrendEvidenceResponse(BaseModel):
    term_id: str
    term: str
    scope: TrendScope
    is_sensitive: bool
    total_meetings: int = Field(..., description="Meetings in the scope (both years) whose transcript says the term.")
    total: int = Field(..., description="Stored excerpts in the scope (the newest meetings).")
    limit: int
    offset: int
    items: list[TrendEvidence]


def _scope(state: str | None, city: str | None) -> TrendScope:
    s = build_scope(state, city)
    if s.state_code:
        return TrendScope(level="state", state_code=s.state_code, state=s.state, requested_city=s.city)
    return TrendScope(level="national")


def terms_sql(scope: TrendScope, sort: Sort, limit: int) -> tuple[str, list[Any]]:
    """Ranked served terms for one scope. The rank column is chosen from a fixed map, never from input."""
    rank = RANK_COLUMN[sort]
    params: list[Any] = [scope.state_code or "US", limit]
    sql = (
        f"SELECT term_key, term, {rank} AS rank, meetings_a, meetings_b, recorded_a, recorded_b, share_a, share_b, "
        "rise, n_meetings, n_jurisdictions, hot_score, is_sensitive, latest_meeting_date, year_a, year_b "
        f"FROM trending_term WHERE scope_code = $1 AND is_served AND {rank} IS NOT NULL "
        f"ORDER BY {rank} LIMIT $2"
    )
    return sql, params


def evidence_sql(term_id: str, scope: TrendScope, limit: int, offset: int) -> tuple[str, list[Any]]:
    params: list[Any] = [term_id]
    where = "e.term_key = $1"
    if scope.state_code:
        params.append(scope.state_code)
        where += f" AND e.state_code = ${len(params)}"
    params += [limit, offset]
    sql = (
        "SELECT e.video_id, e.meeting_title, e.meeting_date, e.jurisdiction_name, e.state_code, e.video_url, "
        "e.excerpt, e.excerpt_source, e.start_seconds, e.speaker_display_name, count(*) OVER () AS total "
        f"FROM trending_term_evidence e WHERE {where} "
        f"ORDER BY e.meeting_date DESC, e.video_id LIMIT ${len(params) - 1} OFFSET ${len(params)}"
    )
    return sql, params


def _f(v: Any) -> float | None:
    return None if v is None else float(v)


def _d(v: Any) -> str | None:
    return v.isoformat() if isinstance(v, date) else (str(v) if v else None)


def shape_terms(rows: list[dict[str, Any]], scope: TrendScope, sort: Sort) -> TrendTermsResponse:
    terms = [
        TrendTerm(
            term_id=r["term_key"], term=r["term"], rank=int(r["rank"]),
            meetings_a=int(r["meetings_a"]), meetings_b=int(r["meetings_b"]),
            recorded_a=int(r["recorded_a"]), recorded_b=int(r["recorded_b"]),
            share_a=_f(r["share_a"]), share_b=_f(r["share_b"]), rise=_f(r["rise"]),
            n_meetings=int(r["n_meetings"]), n_jurisdictions=int(r["n_jurisdictions"]),
            hot_score=_f(r["hot_score"]), is_sensitive=bool(r["is_sensitive"]),
            latest_meeting_date=_d(r["latest_meeting_date"]),
        )
        for r in rows
    ]
    ya = str(rows[0]["year_a"]) if rows else None
    yb = str(rows[0]["year_b"]) if rows else None
    return TrendTermsResponse(scope=scope, sort=sort, year_a=ya, year_b=yb, terms=terms)


@router.get("/terms", response_model=TrendTermsResponse)
async def trending_terms(
    state: str | None = Query(None, description="2-letter state code (or full name). Omit for national."),
    city: str | None = Query(None, description="Accepted for scope carry-over; terms are counted per state."),
    sort: Sort = Query("rising", description="rising | hot | volume"),
    limit: int = Query(24, ge=1, le=MAX_LIMIT),
) -> TrendTermsResponse:
    """Terms rising in meeting speech, or over-represented in heated public comment.

    Example: ``GET /api/trends/terms?state=GA&sort=hot``
    """
    scope = _scope(state, city)
    with tracer.start_as_current_span("trends-terms") as span:
        span.set_attribute("scope.state", scope.state_code or "")
        span.set_attribute("sort", sort)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                sql, p = terms_sql(scope, sort, limit)
                rows = [dict(r) for r in await conn.fetch(sql, *p)]
        except Exception as exc:
            logger.exception("trending terms failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="Trending terms are unavailable right now.") from exc
        span.set_attribute("terms", len(rows))
    return shape_terms(rows, scope, sort)


@router.get("/terms/{term_id}/evidence", response_model=TrendEvidenceResponse)
async def trending_term_evidence(
    term_id: str,
    state: str | None = Query(None, description="2-letter state code (or full name). Omit for national."),
    city: str | None = Query(None, description="Accepted for scope carry-over; evidence is per state."),
    limit: int = Query(10, ge=1, le=MAX_EVIDENCE_LIMIT),
    offset: int = Query(0, ge=0),
) -> TrendEvidenceResponse:
    """The meetings and verbatim, highlighted quotes behind one trending term."""
    tid = term_id.strip().lower()
    if len(tid) != 32 or any(c not in "0123456789abcdef" for c in tid):
        raise HTTPException(status_code=404, detail="Unknown term.")
    scope = _scope(state, city)
    with tracer.start_as_current_span("trends-term-evidence") as span:
        span.set_attribute("scope.state", scope.state_code or "")
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                head = await conn.fetchrow(
                    "SELECT term, is_sensitive, n_meetings FROM trending_term WHERE term_key = $1 AND scope_code = $2",
                    tid, scope.state_code or "US",
                )
                if head is None:
                    head = await conn.fetchrow(
                        "SELECT term, is_sensitive, 0 AS n_meetings FROM trending_term WHERE term_key = $1 LIMIT 1", tid
                    )
                if head is None:
                    raise HTTPException(status_code=404, detail="Unknown term.")
                sql, p = evidence_sql(tid, scope, limit, offset)
                rows = [dict(r) for r in await conn.fetch(sql, *p)]
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("trending term evidence failed")
            span.record_exception(exc)
            raise HTTPException(status_code=503, detail="Evidence is unavailable right now.") from exc
    sensitive = bool(head["is_sensitive"])
    items = [
        TrendEvidence(
            video_id=r["video_id"], meeting_title=r["meeting_title"] or "", meeting_date=_d(r["meeting_date"]) or "",
            jurisdiction_name=r["jurisdiction_name"], state_code=r["state_code"], video_url=r["video_url"],
            excerpt=r["excerpt"], excerpt_source=r["excerpt_source"], start_seconds=_f(r["start_seconds"]),
            # Belt and braces: the mart already drops it for sensitive terms.
            speaker_display_name=None if sensitive else r["speaker_display_name"],
        )
        for r in rows
    ]
    total = int(rows[0]["total"]) if rows else 0
    return TrendEvidenceResponse(
        term_id=tid, term=head["term"], scope=scope, is_sensitive=sensitive,
        total_meetings=int(head["n_meetings"]), total=total, limit=limit, offset=offset, items=items,
    )
