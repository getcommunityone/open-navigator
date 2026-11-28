"""Who governs a place: its bodies, their members and roles, and officials heard recently (#1445).

Reads the public serving copies of the dbt marts built for #1441:

- ``public.governing_body``: one row per jurisdiction x body (council, county commission, planning and zoning,
  board of adjustment, committees...), with meeting counts and date range.
- ``public.body_membership``: members and roles (officials data, council roster, Legistar, OpenStates).
- ``public.body_recent_speaker``: roster members heard in the body's recent meetings (chair calls, roll calls),
  with a link to the moment.
- ``public.meeting_body``: the meetings each body held.

Endpoints:

- ``GET /api/jurisdictions/{id}/bodies``: id is the jurisdiction_id ('tuscaloosa_0177256') or the Census geoid
  ('0177256', what the place pages link with). 404 for an unknown place; an empty ``bodies`` list (not invented
  bodies) when we know none.
- ``GET /api/bodies/{id}``: the body, its members, recent speakers and recent meetings.

Members: current seats, plus seats that ended in the last year (``is_current`` false, with ``end_date``) so a vacancy
reads as a vacancy. Officials are public in their role; no resident is ever returned (the marts hold roster members
only). Design: web_docs/docs/development/governing-bodies.md
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel

from api.routes.search_postgres import get_db_pool

router = APIRouter(tags=["governing bodies"])
tracer = trace.get_tracer(__name__)

ROLE_ORDER = {
    "mayor": 0, "president": 1, "president_pro_tem": 2, "vice_mayor": 3, "chair": 4, "vice_chair": 5,
    "council_member": 6, "alderman": 6, "commissioner": 6, "supervisor": 6, "legislator": 6, "member": 7,
    "clerk": 8, "staff": 9,
}


class BodyMember(BaseModel):
    body_membership_id: str
    person_id: Optional[str] = None
    member_name: str
    role: str
    role_title: Optional[str] = None
    district: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    is_current: bool
    source: str


class RecentSpeaker(BaseModel):
    person_id: Optional[str] = None
    member_name: str
    role: Optional[str] = None
    meetings_heard: int
    last_heard_date: Optional[date] = None
    moment_url: Optional[str] = None
    attribution_method: Optional[str] = None


class Body(BaseModel):
    governing_body_id: str
    body_name: str
    body_type: str
    is_primary: bool
    meeting_count: int
    first_meeting_date: Optional[date] = None
    last_meeting_date: Optional[date] = None
    member_count: int
    members: list[BodyMember]
    recent_speakers: list[RecentSpeaker]


class JurisdictionBodies(BaseModel):
    jurisdiction_id: str
    jurisdiction_name: str
    state_code: Optional[str] = None
    state: Optional[str] = None
    bodies: list[Body]


class BodyMeeting(BaseModel):
    meeting_body_id: str
    meeting_title: Optional[str] = None
    meeting_date: Optional[date] = None
    video_id: Optional[str] = None
    video_url: Optional[str] = None
    event_meeting_id: Optional[int] = None


class BodyHeader(BaseModel):
    governing_body_id: str
    body_name: str
    body_type: str
    is_primary: bool
    meeting_count: int
    first_meeting_date: Optional[date] = None
    last_meeting_date: Optional[date] = None
    member_count: int
    jurisdiction_id: str
    jurisdiction_name: str
    state_code: Optional[str] = None
    state: Optional[str] = None


class BodyDetail(BaseModel):
    body: BodyHeader
    members: list[BodyMember]
    recent_speakers: list[RecentSpeaker]
    meetings: list[BodyMeeting]


_JURISDICTION_SQL = """
    SELECT jurisdiction_id, name, state_code, state_name
    FROM public.jurisdictions
    WHERE jurisdiction_id = $1 OR geoid = $1
    ORDER BY (jurisdiction_id = $1) DESC, jurisdiction_type
    LIMIT 1
"""

_BODIES_SQL = """
    SELECT governing_body_id, jurisdiction_id, body_name, body_type, is_primary, meeting_count,
           first_meeting_date, last_meeting_date
    FROM public.governing_body
    WHERE jurisdiction_id = $1
    ORDER BY is_primary DESC, meeting_count DESC, body_name
"""

_MEMBERS_SQL = """
    SELECT body_membership_id, governing_body_id, person_id, member_name, role, role_title, district,
           start_date, end_date, is_current, source
    FROM public.body_membership
    WHERE governing_body_id = ANY($1::text[])
      AND (is_current OR end_date >= current_date - 365)
"""

_SPEAKERS_SQL = """
    SELECT governing_body_id, person_id, member_name, role, meetings_heard, last_heard_date,
           last_moment_url, attribution_method
    FROM public.body_recent_speaker
    WHERE governing_body_id = ANY($1::text[])
    ORDER BY last_heard_date DESC NULLS LAST, meetings_heard DESC, member_name
"""

_BODY_SQL = """
    SELECT g.governing_body_id, g.jurisdiction_id, g.body_name, g.body_type, g.is_primary, g.meeting_count,
           g.first_meeting_date, g.last_meeting_date, j.name AS jurisdiction_name, j.state_code, j.state_name
    FROM public.governing_body g
    JOIN public.jurisdictions j ON j.jurisdiction_id = g.jurisdiction_id
    WHERE g.governing_body_id = $1
"""

_MEETINGS_SQL = """
    SELECT meeting_body_id, meeting_title, meeting_date, video_id, video_url, event_meeting_id
    FROM public.meeting_body
    WHERE governing_body_id = $1
    ORDER BY meeting_date DESC NULLS LAST, meeting_body_id
    LIMIT $2
"""


def sort_members(rows: list[dict[str, Any]]) -> list[BodyMember]:
    """Current seats first, then by role (mayor, president ... member, clerk, staff), district, name."""

    def key(r: dict[str, Any]) -> tuple:
        return (not r["is_current"], ROLE_ORDER.get(r["role"], 7), r.get("district") or "~", r["member_name"])

    return [BodyMember(**{k: r.get(k) for k in BodyMember.model_fields}) for r in sorted(rows, key=key)]


def member_count(rows: list[dict[str, Any]]) -> int:
    """Distinct people holding a current seat (one person with two roles counts once)."""
    return len({r.get("person_id") or r["member_name"] for r in rows if r["is_current"]})


def to_speaker(r: dict[str, Any]) -> RecentSpeaker:
    return RecentSpeaker(
        person_id=r.get("person_id"),
        member_name=r["member_name"],
        role=r.get("role"),
        meetings_heard=r["meetings_heard"],
        last_heard_date=r.get("last_heard_date"),
        moment_url=r.get("last_moment_url"),
        attribution_method=r.get("attribution_method"),
    )


def assemble_bodies(
    bodies: list[dict[str, Any]], members: list[dict[str, Any]], speakers: list[dict[str, Any]]
) -> list[Body]:
    by_body_m: dict[str, list[dict[str, Any]]] = {}
    for m in members:
        by_body_m.setdefault(m["governing_body_id"], []).append(m)
    by_body_s: dict[str, list[dict[str, Any]]] = {}
    for s in speakers:
        by_body_s.setdefault(s["governing_body_id"], []).append(s)
    out: list[Body] = []
    for b in bodies:
        ms = by_body_m.get(b["governing_body_id"], [])
        out.append(
            Body(
                governing_body_id=b["governing_body_id"],
                body_name=b["body_name"],
                body_type=b["body_type"],
                is_primary=b["is_primary"],
                meeting_count=b["meeting_count"],
                first_meeting_date=b.get("first_meeting_date"),
                last_meeting_date=b.get("last_meeting_date"),
                member_count=member_count(ms),
                members=sort_members(ms),
                recent_speakers=[to_speaker(s) for s in by_body_s.get(b["governing_body_id"], [])],
            )
        )
    return out


@router.get("/jurisdictions/{jurisdiction_id}/bodies", response_model=JurisdictionBodies)
async def get_jurisdiction_bodies(jurisdiction_id: str) -> JurisdictionBodies:
    """The bodies that govern a place, each with members, roles, meeting counts and officials heard recently."""
    with tracer.start_as_current_span("get_jurisdiction_bodies") as span:
        span.set_attribute("jurisdiction_id", jurisdiction_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                jur = await conn.fetchrow(_JURISDICTION_SQL, jurisdiction_id)
                if jur is None:
                    raise HTTPException(status_code=404, detail="Unknown jurisdiction")
                bodies = [dict(r) for r in await conn.fetch(_BODIES_SQL, jur["jurisdiction_id"])]
                ids = [b["governing_body_id"] for b in bodies]
                members = [dict(r) for r in await conn.fetch(_MEMBERS_SQL, ids)] if ids else []
                speakers = [dict(r) for r in await conn.fetch(_SPEAKERS_SQL, ids)] if ids else []
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 - surface as 500 without internals
            logger.error("jurisdiction bodies query failed for {}: {}", jurisdiction_id, exc)
            raise HTTPException(status_code=500, detail="Failed to load governing bodies")
        span.set_attribute("body_count", len(bodies))
        return JurisdictionBodies(
            jurisdiction_id=jur["jurisdiction_id"],
            jurisdiction_name=jur["name"],
            state_code=jur["state_code"],
            state=jur["state_name"],
            bodies=assemble_bodies(bodies, members, speakers),
        )


@router.get("/bodies/{governing_body_id}", response_model=BodyDetail)
async def get_body(governing_body_id: str, limit: int = Query(50, ge=1, le=500)) -> BodyDetail:
    """One body: its members and roles, officials heard recently, and its most recent meetings."""
    with tracer.start_as_current_span("get_body") as span:
        span.set_attribute("governing_body_id", governing_body_id)
        try:
            pool = await get_db_pool()
            async with pool.acquire() as conn:
                row = await conn.fetchrow(_BODY_SQL, governing_body_id)
                if row is None:
                    raise HTTPException(status_code=404, detail="Unknown body")
                members = [dict(r) for r in await conn.fetch(_MEMBERS_SQL, [governing_body_id])]
                speakers = [dict(r) for r in await conn.fetch(_SPEAKERS_SQL, [governing_body_id])]
                meetings = [dict(r) for r in await conn.fetch(_MEETINGS_SQL, governing_body_id, limit)]
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001
            logger.error("body query failed for {}: {}", governing_body_id, exc)
            raise HTTPException(status_code=500, detail="Failed to load the body")
        b = dict(row)
        return BodyDetail(
            body=BodyHeader(
                governing_body_id=b["governing_body_id"],
                body_name=b["body_name"],
                body_type=b["body_type"],
                is_primary=b["is_primary"],
                meeting_count=b["meeting_count"],
                first_meeting_date=b.get("first_meeting_date"),
                last_meeting_date=b.get("last_meeting_date"),
                member_count=member_count(members),
                jurisdiction_id=b["jurisdiction_id"],
                jurisdiction_name=b["jurisdiction_name"],
                state_code=b.get("state_code"),
                state=b.get("state_name"),
            ),
            members=sort_members(members),
            recent_speakers=[to_speaker(s) for s in speakers],
            meetings=[BodyMeeting(**m) for m in meetings],
        )
