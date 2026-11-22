"""Admin review / override for Jev meeting-kind screens (#668).

List videos labeled ``not_government`` (or other kinds), sort by probability,
and persist human overrides so false skips can be corrected without re-Jev.

    GET    /api/admin/meeting-kind-reviews
    PUT    /api/admin/meeting-kind-overrides/{video_id}
    DELETE /api/admin/meeting-kind-overrides/{video_id}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field

from api.auth import require_admin
from api.models import User
from api.routes.stats_neon import get_db_pool

admin_router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

tracer = trace.get_tracer(__name__)

OVERRIDE_TABLE = "bronze.bronze_video_meeting_kind_override"
TX_SCREEN = "bronze.bronze_transcript_screen_jev"
META_SCREEN = "bronze.bronze_video_meta_screen_jev"

OverrideKind = Literal[
    "government_meeting",
    "town_hall",
    "government_other",
    "not_government",
]
Source = Literal["transcript", "meta"]
SortField = Literal["not_government_p", "keep_score", "screened_at"]

CREATE_OVERRIDE_SQL = f"""
CREATE TABLE IF NOT EXISTS {OVERRIDE_TABLE} (
    video_id        text PRIMARY KEY,
    override_kind   text NOT NULL,
    note            text,
    overridden_by   text,
    overridden_at   timestamptz NOT NULL DEFAULT now()
)
"""


class MeetingKindReviewItem(BaseModel):
    video_id: str
    title: str | None = None
    state_code: str | None = None
    jurisdiction_id: str | None = None
    source: Source
    meeting_kind: str | None = None
    not_government_p: float | None = None
    keep_score: float | None = None
    screened_at: datetime | None = None
    youtube_url: str
    override_kind: str | None = None
    override_note: str | None = None
    effective_kind: str | None = None


class MeetingKindReviewsResponse(BaseModel):
    items: list[MeetingKindReviewItem]
    total: int
    source: Source
    kind: str


class MeetingKindOverrideIn(BaseModel):
    override_kind: OverrideKind
    note: str | None = Field(None, max_length=2000)


class MeetingKindOverrideOut(BaseModel):
    video_id: str
    override_kind: str
    note: str | None = None
    overridden_by: str | None = None
    overridden_at: datetime


async def _ensure_override_table(conn: Any) -> None:
    await conn.execute(CREATE_OVERRIDE_SQL)


def _keep_score_sql(alias: str = "s") -> str:
    return (
        f"COALESCE(({alias}.meeting_kind_probabilities->>'government_meeting')::float, 0) "
        f"+ COALESCE(({alias}.meeting_kind_probabilities->>'town_hall')::float, 0)"
    )


def _not_gov_p_sql(alias: str = "s") -> str:
    return f"({alias}.meeting_kind_probabilities->>'not_government')::float"


@admin_router.get("/meeting-kind-reviews", response_model=MeetingKindReviewsResponse)
async def list_meeting_kind_reviews(
    source: Source = Query("transcript"),
    kind: str = Query("not_government"),
    sort: SortField = Query("not_government_p"),
    order: Literal["asc", "desc"] = Query("desc"),
    state: Optional[str] = Query(None, min_length=2, max_length=2),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Videos whose screen ``meeting_kind`` matches ``kind``, with override columns."""
    with tracer.start_as_current_span("admin.meeting_kind_reviews") as span:
        span.set_attribute("source", source)
        span.set_attribute("kind", kind)
        try:
            pool = await get_db_pool()
        except ValueError as e:
            raise HTTPException(status_code=503, detail="Database not configured") from e

        screen = TX_SCREEN if source == "transcript" else META_SCREEN
        keep_sql = _keep_score_sql("s")
        ng_sql = _not_gov_p_sql("s")
        sort_col = {
            "not_government_p": "not_government_p",
            "keep_score": "keep_score",
            "screened_at": "screened_at",
        }[sort]
        direction = "DESC" if order == "desc" else "ASC"
        nulls = "NULLS LAST"

        where = ["s.meeting_kind = $1"]
        params: list[Any] = [kind]
        if state:
            params.append(state.upper())
            where.append(f"e.state_code = ${len(params)}")

        where_sql = " AND ".join(where)
        params.extend([limit, offset])
        lim_i = len(params) - 1
        off_i = len(params)

        sql = f"""
            SELECT s.video_id,
                   e.title,
                   e.state_code,
                   e.jurisdiction_id,
                   s.meeting_kind,
                   {ng_sql} AS not_government_p,
                   {keep_sql} AS keep_score,
                   s.screened_at,
                   o.override_kind,
                   o.note AS override_note
            FROM {screen} s
            JOIN bronze.bronze_event_youtube e ON e.video_id = s.video_id
            LEFT JOIN {OVERRIDE_TABLE} o ON o.video_id = s.video_id
            WHERE {where_sql}
            ORDER BY {sort_col} {direction} {nulls}, s.video_id
            LIMIT ${lim_i} OFFSET ${off_i}
        """
        count_sql = f"""
            SELECT count(*)::int AS n
            FROM {screen} s
            JOIN bronze.bronze_event_youtube e ON e.video_id = s.video_id
            WHERE {where_sql}
        """

        async with pool.acquire() as conn:
            await _ensure_override_table(conn)
            # Table may be missing on a fresh DB — degrade to empty
            exists = await conn.fetchval(
                "SELECT to_regclass($1)", screen
            )
            if exists is None:
                logger.warning("Screen table {} missing — empty review list", screen)
                return MeetingKindReviewsResponse(
                    items=[], total=0, source=source, kind=kind
                )
            total = await conn.fetchval(count_sql, *params[:-2])
            rows = await conn.fetch(sql, *params)

        items: list[MeetingKindReviewItem] = []
        for r in rows:
            mk = r["meeting_kind"]
            ov = r["override_kind"]
            items.append(
                MeetingKindReviewItem(
                    video_id=r["video_id"],
                    title=r["title"],
                    state_code=r["state_code"],
                    jurisdiction_id=r["jurisdiction_id"],
                    source=source,
                    meeting_kind=mk,
                    not_government_p=float(r["not_government_p"])
                    if r["not_government_p"] is not None
                    else None,
                    keep_score=float(r["keep_score"])
                    if r["keep_score"] is not None
                    else None,
                    screened_at=r["screened_at"],
                    youtube_url=f"https://www.youtube.com/watch?v={r['video_id']}",
                    override_kind=ov,
                    override_note=r["override_note"],
                    effective_kind=ov or mk,
                )
            )
        span.set_attribute("total", int(total or 0))
        return MeetingKindReviewsResponse(
            items=items, total=int(total or 0), source=source, kind=kind
        )


@admin_router.put(
    "/meeting-kind-overrides/{video_id}",
    response_model=MeetingKindOverrideOut,
)
async def upsert_meeting_kind_override(
    video_id: str,
    body: MeetingKindOverrideIn,
    user: User = Depends(require_admin),
):
    """Set or replace the human override for one video."""
    with tracer.start_as_current_span("admin.meeting_kind_override_put") as span:
        span.set_attribute("video_id", video_id)
        try:
            pool = await get_db_pool()
        except ValueError as e:
            raise HTTPException(status_code=503, detail="Database not configured") from e

        now = datetime.now(timezone.utc)
        async with pool.acquire() as conn:
            await _ensure_override_table(conn)
            row = await conn.fetchrow(
                f"""
                INSERT INTO {OVERRIDE_TABLE}
                    (video_id, override_kind, note, overridden_by, overridden_at)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (video_id) DO UPDATE SET
                    override_kind = EXCLUDED.override_kind,
                    note = EXCLUDED.note,
                    overridden_by = EXCLUDED.overridden_by,
                    overridden_at = EXCLUDED.overridden_at
                RETURNING video_id, override_kind, note, overridden_by, overridden_at
                """,
                video_id,
                body.override_kind,
                body.note,
                user.email,
                now,
            )
        logger.info(
            "meeting_kind override {} → {} by {}",
            video_id,
            body.override_kind,
            user.email,
        )
        return MeetingKindOverrideOut(
            video_id=row["video_id"],
            override_kind=row["override_kind"],
            note=row["note"],
            overridden_by=row["overridden_by"],
            overridden_at=row["overridden_at"],
        )


@admin_router.delete(
    "/meeting-kind-overrides/{video_id}",
    status_code=204,
)
async def delete_meeting_kind_override(
    video_id: str,
    user: User = Depends(require_admin),
):
    """Clear the override so the screen kind is used again."""
    with tracer.start_as_current_span("admin.meeting_kind_override_delete") as span:
        span.set_attribute("video_id", video_id)
        try:
            pool = await get_db_pool()
        except ValueError as e:
            raise HTTPException(status_code=503, detail="Database not configured") from e

        async with pool.acquire() as conn:
            await _ensure_override_table(conn)
            await conn.execute(
                f"DELETE FROM {OVERRIDE_TABLE} WHERE video_id = $1", video_id
            )
        logger.info("meeting_kind override cleared for {} by {}", video_id, user.email)
        return Response(status_code=204)
