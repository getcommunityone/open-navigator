"""DC-1.3 (#248): admin-kept job-application links, verified-at and 30-day staleness."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import api.routes.application_links as links_module
from api.auth import require_admin, require_auth
from api.database import get_db
from api.main import app
from api.models import JobApplicationLink, User
from ingestion.data_centers.application_links import LinkCheck


class TestClient:
    """Sync client over httpx.ASGITransport (starlette's TestClient breaks on httpx 0.28)."""

    __test__ = False

    def __init__(self, asgi_app):
        self._app = asgi_app

    def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        async def go() -> httpx.Response:
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
                return await c.request(method, url, **kwargs)

        return asyncio.run(go())

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)

    def patch(self, url, **kw):
        return self.request("PATCH", url, **kw)

    def delete(self, url, **kw):
        return self.request("DELETE", url, **kw)


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    User.__table__.create(engine)
    JobApplicationLink.__table__.create(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture()
def client(db_session):
    admin = User(user_id=1, email="admin@example.com", is_admin=True)

    def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    app.dependency_overrides[require_admin] = lambda: admin
    yield TestClient(app)
    app.dependency_overrides.clear()


def _add(db, **kw) -> JobApplicationLink:
    base = dict(project_name="Project Blue", state_code="AL", state="Alabama", city="Tuscaloosa",
                url="https://jobs.example.com/blue")
    base.update(kw)
    link = JobApplicationLink(**base)
    db.add(link)
    db.commit()
    return link


def test_admin_create_normalizes_state_and_starts_stale(client) -> None:
    resp = client.post(
        "/api/admin/application-links",
        json={"project_name": " Project Blue ", "state_code": "Alabama", "city": "Tuscaloosa",
              "url": "https://jobs.example.com/blue", "employer": "Blue LLC"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["project_name"] == "Project Blue"
    assert body["state_code"] == "AL" and body["state"] == "Alabama"
    assert body["last_verified_at"] is None and body["is_stale"] is True


def test_admin_rejects_non_http_url_and_duplicates(client) -> None:
    bad = client.post("/api/admin/application-links",
                      json={"project_name": "X", "state_code": "AL", "url": "javascript:alert(1)"})
    assert bad.status_code == 422
    ok = {"project_name": "X", "state_code": "AL", "url": "https://jobs.example.com/x"}
    assert client.post("/api/admin/application-links", json=ok).status_code == 201
    assert client.post("/api/admin/application-links", json=ok).status_code == 409


def test_unknown_state_is_422(client) -> None:
    resp = client.post("/api/admin/application-links",
                       json={"project_name": "X", "state_code": "ZZ", "url": "https://a.example.com"})
    assert resp.status_code == 422


def test_check_live_sets_verified_dead_does_not(client, db_session, monkeypatch) -> None:
    link = _add(db_session)
    when = datetime(2026, 11, 15, tzinfo=timezone.utc)
    monkeypatch.setattr(links_module, "check_link", lambda url: LinkCheck("live", 200, when))
    live = client.post(f"/api/admin/application-links/{link.job_application_link_id}/check").json()
    assert live["last_check_status"] == "live" and live["last_http_status"] == 200
    assert live["last_verified_at"].startswith("2026-11-15")

    later = when + timedelta(days=1)
    monkeypatch.setattr(links_module, "check_link", lambda url: LinkCheck("dead", 404, later))
    dead = client.post(f"/api/admin/application-links/{link.job_application_link_id}/check").json()
    assert dead["last_check_status"] == "dead"
    assert dead["last_verified_at"].startswith("2026-11-15")  # unchanged by a failed check


def test_manual_verify_clears_stale(client, db_session) -> None:
    link = _add(db_session)
    body = client.post(f"/api/admin/application-links/{link.job_application_link_id}/verify").json()
    assert body["last_verified_at"] is not None and body["is_stale"] is False


def test_admin_stale_filter_and_counts(client, db_session) -> None:
    now = datetime.now(timezone.utc)
    _add(db_session, url="https://a.example.com", last_verified_at=now - timedelta(days=2))
    _add(db_session, url="https://b.example.com", last_verified_at=now - timedelta(days=45))
    _add(db_session, url="https://c.example.com")
    everything = client.get("/api/admin/application-links").json()
    assert everything["total"] == 3 and everything["stale"] == 2
    only_stale = client.get("/api/admin/application-links?stale=true").json()
    assert {i["url"] for i in only_stale["items"]} == {"https://b.example.com", "https://c.example.com"}


def test_changing_the_url_clears_its_verification(client, db_session) -> None:
    link = _add(db_session, last_verified_at=datetime.now(timezone.utc), last_check_status="live",
                last_http_status=200)
    body = client.patch(f"/api/admin/application-links/{link.job_application_link_id}",
                        json={"url": "https://jobs.example.com/new"}).json()
    assert body["url"] == "https://jobs.example.com/new"
    assert body["last_verified_at"] is None and body["last_check_status"] is None and body["is_stale"]


def test_delete_and_404(client, db_session) -> None:
    link = _add(db_session)
    lid = link.job_application_link_id
    assert client.delete(f"/api/admin/application-links/{lid}").status_code == 204
    assert client.post(f"/api/admin/application-links/{lid}/verify").status_code == 404


def test_public_list_scopes_hides_dead_and_flags_stale(client, db_session) -> None:
    now = datetime.now(timezone.utc)
    _add(db_session, url="https://fresh.example.com", last_verified_at=now - timedelta(days=1),
         last_check_status="live")
    _add(db_session, url="https://old.example.com", last_verified_at=now - timedelta(days=40))
    _add(db_session, url="https://gone.example.com", last_check_status="dead")
    _add(db_session, url="https://ga.example.com", state_code="GA", state="Georgia", city="Atlanta")
    resp = client.get("/api/data-centers/application-links?state=AL&city=tuscaloosa")
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope"]["level"] == "city" and body["scope"]["state_code"] == "AL"
    urls = [i["url"] for i in body["items"]]
    assert urls == ["https://fresh.example.com", "https://old.example.com"]
    assert [i["is_stale"] for i in body["items"]] == [False, True]
    assert "last_check_status" not in body["items"][0]  # admin-only field


def test_admin_routes_need_an_admin(db_session) -> None:
    def _db():
        yield db_session

    app.dependency_overrides[get_db] = _db
    try:
        anon = TestClient(app).get("/api/admin/application-links")
        assert anon.status_code == 401
        app.dependency_overrides[require_auth] = lambda: User(user_id=2, email="u@example.com", is_admin=False)
        user = TestClient(app).get("/api/admin/application-links")
        assert user.status_code == 403
    finally:
        app.dependency_overrides.clear()
