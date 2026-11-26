"""Claim an official's profile and propose edits (#1062).

    POST /api/people/claim                              body {person_id}
    GET  /api/people/claim?person_id=...
    POST /api/people/claim/{person_claim_id}/edits      body {field, new_value}

Verification is privacy-preserving: the official's email lives only in the
private warehouse; the serving copy carries ``person_government.email_sha256``
(hex sha256 of ``lower(btrim(email))``). We hash the signed-in user's verified
sign-in email the same way and compare. A match makes the claim 'verified'
(``verified_via='official_email'``); anything else is 'pending' for manual review.
Neither the email nor either hash is ever returned to the client or logged.

Edits (title, biography, photo_url) need a verified claim; feedback is allowed on
a pending claim too. Every edit is stored 'pending' for the owner to approve:
nothing is published automatically and nothing is emailed. Design:
web_docs/docs/development/people-claim-and-privacy.md.
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from opentelemetry import trace
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.auth import require_auth
from api.database import get_db
from api.models import PersonClaim, PersonProfileEdit, User
from api.routes.search_postgres import get_db_pool

router = APIRouter(prefix="/people", tags=["person-claims"])

CurrentUser = Annotated[User, Depends(require_auth)]
DbSession = Annotated[Session, Depends(get_db)]
tracer = trace.get_tracer(__name__)

MAX_VALUE_CHARS = 4000
VERIFIED_FIELDS = {"title", "biography", "photo_url"}

# email_sha256 is read via to_jsonb so the endpoint keeps working against a
# serving copy built before the column existed (it then reads NULL -> pending).
_OFFICIAL_SQL = """
    SELECT o.person_id, to_jsonb(o) ->> 'email_sha256' AS email_sha256
    FROM person_government o
    WHERE o.person_id = $1
    LIMIT 1
"""

EditField = Literal["title", "biography", "photo_url", "feedback"]


def email_sha256(email: str | None) -> str | None:
    """Hex sha256 of lower(trim(email)); mirrors the dbt expression. None if blank."""
    norm = (email or "").strip().lower()
    if not norm:
        return None
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


class ClaimIn(BaseModel):
    person_id: str = Field(..., min_length=1, max_length=512)

    @field_validator("person_id")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("person_id is required")
        return v


class ClaimOut(BaseModel):
    person_claim_id: int
    person_id: str
    status: Literal["pending", "verified", "rejected"]
    verified_via: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EditIn(BaseModel):
    field: EditField
    new_value: str = Field(..., min_length=1, max_length=MAX_VALUE_CHARS)

    @field_validator("new_value")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("new_value is required")
        return v


class EditOut(BaseModel):
    person_profile_edit_id: int
    person_claim_id: int
    field: EditField
    new_value: str
    status: Literal["pending", "approved", "rejected"]
    created_at: datetime | None = None


def _claim_out(c: PersonClaim) -> ClaimOut:
    return ClaimOut(
        person_claim_id=c.person_claim_id,
        person_id=c.person_id,
        status=c.status,
        verified_via=c.verified_via,
        created_at=c.created_at,
        updated_at=c.updated_at,
    )


def _is_https_url(value: str) -> bool:
    try:
        u = urlparse(value)
    except ValueError:
        return False
    return u.scheme == "https" and bool(u.netloc) and " " not in value


async def _official_hash(person_id: str) -> tuple[bool, str | None]:
    """(exists, email_sha256) for an official, read from the serving copy."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(_OFFICIAL_SQL, person_id)
    if not rows:
        return False, None
    return True, rows[0]["email_sha256"]


@router.post("/claim", response_model=ClaimOut)
async def claim_profile(
    body: ClaimIn,
    user: CurrentUser,
    db: DbSession,
) -> ClaimOut:
    """Claim an official's profile as the signed-in user."""
    with tracer.start_as_current_span("person_claims.claim") as span:
        span.set_attribute("person_id", body.person_id)
        exists, official_hash = await _official_hash(body.person_id)
        if not exists:
            raise HTTPException(status_code=404, detail="No official with that id")

        user_hash = email_sha256(user.email)
        matched = bool(
            official_hash and user_hash and hmac.compare_digest(official_hash, user_hash)
        )

        claim = (
            db.query(PersonClaim)
            .filter(PersonClaim.person_id == body.person_id, PersonClaim.user_id == user.user_id)
            .first()
        )
        if claim is None:
            claim = PersonClaim(person_id=body.person_id, user_id=user.user_id, status="pending")
            db.add(claim)
        if claim.status != "rejected":
            if matched:
                claim.status, claim.verified_via = "verified", "official_email"
            elif claim.status != "verified":
                claim.status, claim.verified_via = "pending", None
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            claim = (
                db.query(PersonClaim)
                .filter(PersonClaim.person_id == body.person_id, PersonClaim.user_id == user.user_id)
                .first()
            )
            if claim is None:
                raise HTTPException(status_code=409, detail="Claim could not be saved")
        db.refresh(claim)
        span.set_attribute("claim.status", claim.status)
        logger.info(
            "Profile claim {} for {} by user {}: {}",
            claim.person_claim_id, body.person_id, user.user_id, claim.status,
        )
        return _claim_out(claim)


@router.get("/claim", response_model=ClaimOut | None)
def get_my_claim(
    user: CurrentUser,
    db: DbSession,
    person_id: Annotated[str, Query(min_length=1, max_length=512)],
) -> ClaimOut | None:
    """The signed-in user's claim on this official, or null."""
    with tracer.start_as_current_span("person_claims.get"):
        claim = (
            db.query(PersonClaim)
            .filter(PersonClaim.person_id == person_id.strip(), PersonClaim.user_id == user.user_id)
            .first()
        )
        return _claim_out(claim) if claim else None


@router.post("/claim/{person_claim_id}/edits", response_model=EditOut, status_code=201)
def propose_edit(
    person_claim_id: int,
    body: EditIn,
    user: CurrentUser,
    db: DbSession,
) -> EditOut:
    """Store a proposed edit (or feedback) as pending, for the owner to approve."""
    with tracer.start_as_current_span("person_claims.edit") as span:
        span.set_attribute("edit.field", body.field)
        claim = db.get(PersonClaim, person_claim_id)
        # Another user's claim reads as missing: don't confirm it exists.
        if claim is None or claim.user_id != user.user_id:
            raise HTTPException(status_code=404, detail="Claim not found")
        if claim.status == "rejected":
            raise HTTPException(status_code=403, detail="This claim was not approved")
        if body.field in VERIFIED_FIELDS and claim.status != "verified":
            raise HTTPException(
                status_code=403,
                detail="Profile edits need a verified claim; you can still send feedback",
            )
        if body.field == "photo_url" and not _is_https_url(body.new_value):
            raise HTTPException(status_code=422, detail="photo_url must be an https:// URL")

        edit = PersonProfileEdit(
            person_claim_id=claim.person_claim_id,
            field=body.field,
            new_value=body.new_value,
            status="pending",
        )
        db.add(edit)
        db.commit()
        db.refresh(edit)
        logger.info(
            "Profile edit {} ({}) on claim {} stored pending",
            edit.person_profile_edit_id, body.field, claim.person_claim_id,
        )
        return EditOut(
            person_profile_edit_id=edit.person_profile_edit_id,
            person_claim_id=edit.person_claim_id,
            field=edit.field,
            new_value=edit.new_value,
            status=edit.status,
            created_at=edit.created_at,
        )
