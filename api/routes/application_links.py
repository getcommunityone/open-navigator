"""
Job-application links for data center projects (issue #248, DC-1.3).

Admins keep the links on the admin screen; the public page shows the ones still
worth following. Backed by the app-owned table ``public.job_application_link``
(``api.models.JobApplicationLink``), not a dbt model.

Public:
    GET /api/data-centers/application-links?state=&city=&limit=
        Links for the scope, newest-verified first. Links whose last check found
        the page gone (``dead``) are left out; every item says when it was last
        verified and whether that was more than 30 days ago (``is_stale``).

Admin (``require_admin``):
    GET    /api/admin/application-links[?stale=true]
    POST   /api/admin/application-links
    PATCH  /api/admin/application-links/{id}
    DELETE /api/admin/application-links/{id}
    POST   /api/admin/application-links/{id}/check   request the page now
    POST   /api/admin/application-links/{id}/verify  an admin confirmed it by hand

Nothing is defaulted: a link never verified has ``last_verified_at = null`` and is
stale (CLAUDE.md, No Fabricated Data).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from ingestion.data_centers.application_links import check_link, is_http_url, is_stale
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.auth import require_admin
from api.database import get_db
from api.models import JobApplicationLink, User
from api.routes.data_centers import JobClaimScope, build_scope

public_router = APIRouter(prefix="/data-centers", tags=["data-centers"])
admin_router = APIRouter(
    prefix="/admin/application-links",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)

tracer = trace.get_tracer(__name__)

DEFAULT_LIMIT = 100
MAX_LIMIT = 500

CheckStatus = Literal["live", "dead", "error"]


# --- models -------------------------------------------------------------------


class ApplicationLink(BaseModel):
    """A link as the public page shows it."""

    job_application_link_id: int
    project_name: str
    employer: str | None = None
    state_code: str
    state: str | None = None
    city: str | None = None
    url: str
    last_verified_at: datetime | None = Field(
        None, description="When a check or an admin last confirmed the page works; null if never."
    )
    is_stale: bool = Field(..., description="Never verified, or not verified in the last 30 days.")


class ApplicationLinksResponse(BaseModel):
    scope: JobClaimScope
    items: list[ApplicationLink]


class AdminApplicationLink(ApplicationLink):
    """A link with everything the admin screen needs."""

    source_note: str | None = None
    last_checked_at: datetime | None = None
    last_check_status: CheckStatus | None = None
    last_http_status: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AdminApplicationLinksResponse(BaseModel):
    total: int = Field(..., description="Links in the list (after the stale filter).")
    stale: int = Field(..., description="Of those, how many are stale.")
    items: list[AdminApplicationLink]


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


class ApplicationLinkIn(BaseModel):
    project_name: str = Field(..., min_length=1, max_length=300)
    employer: str | None = Field(None, max_length=300)
    state_code: str = Field(..., description="2-letter state code (a full name is normalized).")
    city: str | None = Field(None, max_length=200)
    url: str = Field(..., max_length=2000)
    source_note: str | None = Field(None, max_length=1000)

    @field_validator("project_name", "employer", "city", "source_note", mode="before")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return _clean(v) if isinstance(v, str) or v is None else v

    @field_validator("url")
    @classmethod
    def _http_only(cls, v: str) -> str:
        v = v.strip()
        if not is_http_url(v):
            raise ValueError("url must be an absolute http(s) URL")
        return v


class ApplicationLinkPatch(BaseModel):
    project_name: str | None = Field(None, min_length=1, max_length=300)
    employer: str | None = Field(None, max_length=300)
    state_code: str | None = None
    city: str | None = Field(None, max_length=200)
    url: str | None = Field(None, max_length=2000)
    source_note: str | None = Field(None, max_length=1000)

    @field_validator("url")
    @classmethod
    def _http_only(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not is_http_url(v):
            raise ValueError("url must be an absolute http(s) URL")
        return v


# --- helpers ------------------------------------------------------------------


def _place(state_code_raw: str) -> tuple[str, str | None]:
    """Normalize a state code or name to (code, full name); 422 when unknown."""
    scope = build_scope(state_code_raw, None, None)
    if not scope.state_code or not scope.state:
        raise HTTPException(status_code=422, detail=f"Unknown state: {state_code_raw!r}")
    return scope.state_code, scope.state


def _public(link: JobApplicationLink, now: datetime) -> ApplicationLink:
    return ApplicationLink(
        job_application_link_id=link.job_application_link_id,
        project_name=link.project_name,
        employer=link.employer,
        state_code=link.state_code,
        state=link.state,
        city=link.city,
        url=link.url,
        last_verified_at=link.last_verified_at,
        is_stale=is_stale(link.last_verified_at, now),
    )


def _admin(link: JobApplicationLink, now: datetime) -> AdminApplicationLink:
    return AdminApplicationLink(
        **_public(link, now).model_dump(),
        source_note=link.source_note,
        last_checked_at=link.last_checked_at,
        last_check_status=link.last_check_status,
        last_http_status=link.last_http_status,
        created_at=link.created_at,
        updated_at=link.updated_at,
    )


def _get_or_404(db: Session, link_id: int) -> JobApplicationLink:
    link = db.get(JobApplicationLink, link_id)
    if link is None:
        raise HTTPException(status_code=404, detail=f"No application link {link_id}")
    return link


def _commit_unique(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="That URL is already in the list")


# --- public -------------------------------------------------------------------


@public_router.get("/application-links", response_model=ApplicationLinksResponse)
def list_application_links(
    state: str | None = Query(None, description="2-letter state code (a full name is normalized)."),
    city: str | None = Query(None, description="City; case-insensitive substring."),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    db: Session = Depends(get_db),
) -> ApplicationLinksResponse:
    """Application links for the scope; dead links are left out, stale ones are flagged."""
    scope = build_scope(state, city, None)
    with tracer.start_as_current_span("data-centers.application-links") as span:
        span.set_attribute("application_links.scope_level", scope.level)
        q = db.query(JobApplicationLink).filter(
            or_(
                JobApplicationLink.last_check_status.is_(None),
                JobApplicationLink.last_check_status != "dead",
            )
        )
        if scope.state_code:
            q = q.filter(JobApplicationLink.state_code == scope.state_code)
        if scope.city:
            q = q.filter(JobApplicationLink.city.ilike(f"%{scope.city}%"))
        rows = (
            q.order_by(
                JobApplicationLink.last_verified_at.desc().nulls_last(),
                JobApplicationLink.job_application_link_id,
            )
            .limit(limit)
            .all()
        )
        now = datetime.now(timezone.utc)
        span.set_attribute("application_links.count", len(rows))
        return ApplicationLinksResponse(scope=scope, items=[_public(r, now) for r in rows])


# --- admin --------------------------------------------------------------------


@admin_router.get("", response_model=AdminApplicationLinksResponse)
def admin_list(
    stale: bool = Query(False, description="Only links not verified in the last 30 days."),
    db: Session = Depends(get_db),
) -> AdminApplicationLinksResponse:
    rows = (
        db.query(JobApplicationLink)
        .order_by(func.lower(JobApplicationLink.project_name), JobApplicationLink.job_application_link_id)
        .all()
    )
    now = datetime.now(timezone.utc)
    items = [_admin(r, now) for r in rows]
    if stale:
        items = [i for i in items if i.is_stale]
    return AdminApplicationLinksResponse(
        total=len(items), stale=sum(1 for i in items if i.is_stale), items=items
    )


@admin_router.post("", response_model=AdminApplicationLink, status_code=201)
def admin_create(
    body: ApplicationLinkIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> AdminApplicationLink:
    state_code, state_name = _place(body.state_code)
    link = JobApplicationLink(
        project_name=body.project_name,
        employer=body.employer,
        state_code=state_code,
        state=state_name,
        city=body.city,
        url=body.url,
        source_note=body.source_note,
        created_by_user_id=getattr(user, "user_id", None),
    )
    db.add(link)
    _commit_unique(db)
    db.refresh(link)
    logger.info("Application link {} added: {}", link.job_application_link_id, link.url)
    return _admin(link, datetime.now(timezone.utc))


@admin_router.patch("/{link_id}", response_model=AdminApplicationLink)
def admin_update(
    link_id: int, body: ApplicationLinkPatch, db: Session = Depends(get_db)
) -> AdminApplicationLink:
    link = _get_or_404(db, link_id)
    changes = body.model_dump(exclude_unset=True)
    if "state_code" in changes:
        link.state_code, link.state = _place(changes.pop("state_code") or "")
    if "url" in changes and changes["url"] != link.url:
        # A new URL hasn't been verified: clear the old check so it reads as stale.
        link.last_verified_at = None
        link.last_checked_at = None
        link.last_check_status = None
        link.last_http_status = None
    for key, value in changes.items():
        if key == "project_name" and not _clean(value):
            raise HTTPException(status_code=422, detail="project_name can't be blank")
        setattr(link, key, _clean(value) if isinstance(value, str) else value)
    _commit_unique(db)
    db.refresh(link)
    return _admin(link, datetime.now(timezone.utc))


@admin_router.delete("/{link_id}", status_code=204)
def admin_delete(link_id: int, db: Session = Depends(get_db)) -> Response:
    link = _get_or_404(db, link_id)
    db.delete(link)
    db.commit()
    return Response(status_code=204)


@admin_router.post("/{link_id}/check", response_model=AdminApplicationLink)
def admin_check(link_id: int, db: Session = Depends(get_db)) -> AdminApplicationLink:
    """Request the page now; a live answer counts as verifying it."""
    link = _get_or_404(db, link_id)
    with tracer.start_as_current_span("admin.application-links.check") as span:
        result = check_link(link.url)
        span.set_attribute("application_links.check_status", result.status)
    link.last_checked_at = result.checked_at
    link.last_check_status = result.status
    link.last_http_status = result.http_status
    if result.verified:
        link.last_verified_at = result.checked_at
    db.commit()
    db.refresh(link)
    return _admin(link, datetime.now(timezone.utc))


@admin_router.post("/{link_id}/verify", response_model=AdminApplicationLink)
def admin_verify(link_id: int, db: Session = Depends(get_db)) -> AdminApplicationLink:
    """An admin opened the page and confirmed the posting is open."""
    link = _get_or_404(db, link_id)
    link.last_verified_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(link)
    return _admin(link, datetime.now(timezone.utc))
