"""Official profile claims and pending edits (#1062).

The warehouse is mocked with a fake asyncpg pool (person_government lookup); the
runtime ORM tables run on in-memory SQLite. Auth goes through the real
``require_auth`` with a JWT from ``create_access_token``.
"""

from __future__ import annotations

import asyncio
import hashlib
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import create_access_token
from api.database import get_db
from api.models import PersonClaim, PersonProfileEdit, User
from api.routes import person_claims

OFFICIAL_ID = "ocd-membership/scraped-tuscaloosa-council-1"
OFFICIAL_EMAIL = "Council.One@TuscaloosaAL.gov"


def _hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()


class _Conn:
    def __init__(self, officials: dict[str, str | None]):
        self.officials = officials
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        pid = params[0]
        if pid in self.officials:
            return [{"person_id": pid, "email_sha256": self.officials[pid]}]
        return []


class _Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *_):
        return None


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    for model in (User, PersonClaim, PersonProfileEdit):
        model.__table__.create(engine)
    session = sessionmaker(bind=engine)()
    session.add_all(
        [
            User(user_id=1, email="council.one@tuscaloosaal.gov"),  # matches (case differs)
            User(user_id=2, email="someone@gmail.com"),
        ]
    )
    session.commit()
    yield session
    session.close()


@pytest.fixture()
def conn():
    return _Conn({OFFICIAL_ID: _hash(OFFICIAL_EMAIL), "ocd-membership/no-email": None})


@pytest.fixture()
def call(monkeypatch, db_session, conn):
    async def pool():
        return _Pool(conn)

    monkeypatch.setattr(person_claims, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(person_claims.router, prefix="/api")

    def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db

    def _call(method: str, path: str, user_id: int | None = None, **kw) -> httpx.Response:
        headers = kw.pop("headers", {})
        if user_id is not None:
            headers["Authorization"] = f"Bearer {create_access_token({'sub': str(user_id)})}"

        async def go():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://t"
            ) as c:
                return await c.request(method, path, headers=headers, **kw)

        return asyncio.run(go())

    return _call


def _claim(call, user_id: int, person_id: str = OFFICIAL_ID) -> httpx.Response:
    return call("POST", "/api/people/claim", user_id=user_id, json={"person_id": person_id})


def test_requires_auth(call) -> None:
    assert call("POST", "/api/people/claim", json={"person_id": OFFICIAL_ID}).status_code == 401
    assert call("GET", "/api/people/claim", params={"person_id": OFFICIAL_ID}).status_code == 401
    assert call("POST", "/api/people/claim/1/edits",
                json={"field": "feedback", "new_value": "hi"}).status_code == 401


def test_unknown_official_is_404(call) -> None:
    assert _claim(call, 1, "ocd-membership/nobody").status_code == 404


def test_verified_when_email_hash_matches(call, conn) -> None:
    resp = _claim(call, 1)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "verified" and body["verified_via"] == "official_email"
    # Neither the email nor any hash leaks to the client.
    text = resp.text.lower()
    assert "email" not in text.replace("official_email", "") and _hash(OFFICIAL_EMAIL) not in text
    # The lookup is parameterized and reads the hash defensively.
    sql, params = conn.calls[-1]
    assert params == (OFFICIAL_ID,) and "to_jsonb(o) ->> 'email_sha256'" in sql

    mine = call("GET", "/api/people/claim", user_id=1, params={"person_id": OFFICIAL_ID})
    assert mine.status_code == 200 and mine.json()["person_claim_id"] == body["person_claim_id"]


def test_pending_when_email_does_not_match(call) -> None:
    body = _claim(call, 2).json()
    assert body["status"] == "pending" and body["verified_via"] is None
    # Re-claiming is idempotent: same row, still pending.
    again = _claim(call, 2).json()
    assert again["person_claim_id"] == body["person_claim_id"] and again["status"] == "pending"


def test_pending_when_official_has_no_email(call) -> None:
    assert _claim(call, 1, "ocd-membership/no-email").json()["status"] == "pending"


def test_get_claim_is_null_when_none(call) -> None:
    resp = call("GET", "/api/people/claim", user_id=2, params={"person_id": OFFICIAL_ID})
    assert resp.status_code == 200 and resp.json() is None


def test_pending_claim_can_send_feedback_but_not_edit(call) -> None:
    cid = _claim(call, 2).json()["person_claim_id"]
    url = f"/api/people/claim/{cid}/edits"
    for field in ("title", "biography", "photo_url"):
        value = "https://example.gov/me.jpg" if field == "photo_url" else "New value"
        assert call("POST", url, user_id=2, json={"field": field, "new_value": value}).status_code == 403
    fb = call("POST", url, user_id=2, json={"field": "feedback", "new_value": "Please fix my title"})
    assert fb.status_code == 201, fb.text
    assert fb.json()["status"] == "pending" and fb.json()["field"] == "feedback"


def test_verified_claim_edits_are_stored_pending(call, db_session) -> None:
    cid = _claim(call, 1).json()["person_claim_id"]
    url = f"/api/people/claim/{cid}/edits"
    for field, value in (("title", "Council Member, District 1"),
                         ("biography", "Served since 2021."),
                         ("photo_url", "https://www.tuscaloosa.com/photo.jpg")):
        resp = call("POST", url, user_id=1, json={"field": field, "new_value": value})
        assert resp.status_code == 201, resp.text
        assert resp.json()["status"] == "pending" and resp.json()["new_value"] == value
    assert db_session.query(PersonProfileEdit).filter_by(status="pending").count() == 3


def test_another_users_claim_is_not_found(call) -> None:
    cid = _claim(call, 1).json()["person_claim_id"]
    resp = call("POST", f"/api/people/claim/{cid}/edits", user_id=2,
                json={"field": "feedback", "new_value": "hijack"})
    assert resp.status_code == 404


def test_bad_field_and_non_https_photo_rejected(call) -> None:
    cid = _claim(call, 1).json()["person_claim_id"]
    url = f"/api/people/claim/{cid}/edits"
    assert call("POST", url, user_id=1, json={"field": "email", "new_value": "x"}).status_code == 422
    for bad in ("http://example.gov/me.jpg", "javascript:alert(1)", "example.gov/me.jpg"):
        resp = call("POST", url, user_id=1, json={"field": "photo_url", "new_value": bad})
        assert resp.status_code == 422, bad
    too_long = "x" * (person_claims.MAX_VALUE_CHARS + 1)
    assert call("POST", url, user_id=1,
                json={"field": "biography", "new_value": too_long}).status_code == 422
