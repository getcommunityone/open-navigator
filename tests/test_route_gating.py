"""End-to-end gating tests for the control-plane routes and the OAuth redirect drop.

The vulnerability this PR fixed was a *wiring* failure: `require_auth`/`require_admin`
existed but were attached to no route, so the pipeline launch/stop, log-tail, and
prod-deploy endpoints were reachable anonymously. The origins/account-link unit tests
cover the validators in isolation; these tests assert the routes themselves are
actually gated (401 anonymous, 403 non-admin) and that an unsafe `redirect_uri` is
dropped before it is ever persisted.
"""
import asyncio

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.auth import get_current_user
from api.database import get_db
from api.models import Base, OAuthState, User
from api.routes import auth as auth_routes
from api.routes import batch_jobs, deployments


class TestClient:
    """Minimal sync client over httpx.ASGITransport (same API as starlette's).

    starlette's TestClient passes ``app=`` to httpx.Client, which httpx 0.28
    removed, so it fails in CI with "unexpected keyword argument 'app'". Like
    starlette's client, this follows redirects unless told otherwise.
    """

    __test__ = False  # not a pytest test class

    def __init__(self, asgi_app):
        self._app = asgi_app

    def request(self, method: str, url: str, follow_redirects: bool = True, **kwargs) -> httpx.Response:
        async def go() -> httpx.Response:
            transport = httpx.ASGITransport(app=self._app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://testserver", follow_redirects=follow_redirects
            ) as client:
                return await client.request(method.upper(), url, **kwargs)

        return asyncio.run(go())

    def get(self, url: str, **kwargs) -> httpx.Response:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs) -> httpx.Response:
        return self.request("POST", url, **kwargs)

    def put(self, url: str, **kwargs) -> httpx.Response:
        return self.request("PUT", url, **kwargs)

    def delete(self, url: str, **kwargs) -> httpx.Response:
        return self.request("DELETE", url, **kwargs)


# Every mutating control-plane route that must be admin-gated. (method, path).
GATED_ROUTES = [
    ("post", "/api/batch-jobs/launch"),
    ("post", "/api/batch-jobs/launch/stop"),
    ("post", "/api/batch-jobs/failures/retry"),
    ("get", "/api/batch-jobs/launch/log?step=ingest"),
    ("post", "/api/deployments/launch"),
    ("post", "/api/deployments/some-job/stop"),
    ("get", "/api/deployments/some-job/log"),
    ("get", "/api/deployments/"),
]


@pytest.fixture
def db_session():
    # StaticPool + a single shared connection so the create_all schema and the
    # request-thread session see the same in-memory database.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def app(db_session):
    """Minimal app mounting just the routers under test, sharing one in-memory DB."""
    application = FastAPI()
    application.include_router(batch_jobs.router, prefix="/api")
    application.include_router(deployments.router, prefix="/api")
    application.include_router(auth_routes.router, prefix="/api")
    application.dependency_overrides[get_db] = lambda: db_session
    return application


def _make_user(is_admin: bool) -> User:
    return User(user_id=1, email="user@example.com", is_admin=is_admin)


@pytest.mark.parametrize("method,path", GATED_ROUTES)
def test_gated_route_rejects_anonymous(app, method, path):
    # No Authorization header → HTTPBearer(auto_error=False) yields no user →
    # require_auth raises 401 before the endpoint body runs.
    client = TestClient(app)
    kwargs = {"json": {}} if method == "post" else {}
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == 401, f"{method.upper()} {path} was reachable anonymously"


@pytest.mark.parametrize("method,path", GATED_ROUTES)
def test_gated_route_rejects_non_admin(app, method, path):
    # Authenticated but not an admin → require_admin raises 403.
    app.dependency_overrides[get_current_user] = lambda: _make_user(is_admin=False)
    client = TestClient(app)
    kwargs = {"json": {}} if method == "post" else {}
    resp = getattr(client, method)(path, **kwargs)
    assert resp.status_code == 403, f"{method.upper()} {path} was reachable by a non-admin"
    app.dependency_overrides.pop(get_current_user, None)


def test_stale_admin_flag_without_env_is_rejected(app, monkeypatch):
    # A user carries a persisted is_admin=True, but their email is no longer in
    # ADMIN_EMAILS. Because the env is authoritative at request time, admin
    # access is revoked immediately — the stale DB flag is not enough.
    monkeypatch.setenv("ADMIN_EMAILS", "current-admin@example.com")
    app.dependency_overrides[get_current_user] = lambda: User(
        user_id=2, email="removed-admin@example.com", is_admin=True
    )
    client = TestClient(app)
    resp = client.post("/api/batch-jobs/launch", json={})
    assert resp.status_code == 403
    app.dependency_overrides.pop(get_current_user, None)


def test_admin_in_env_passes_the_gate(app, monkeypatch):
    # Same persisted flag, but the email IS in ADMIN_EMAILS → require_admin lets
    # the request through. Launch is still opt-in (BATCH_JOBS_ALLOW_LAUNCH unset),
    # so the endpoint's own guard answers 403 with a *different* detail — proving
    # the request got past the admin gate rather than being blocked by it.
    monkeypatch.setenv("ADMIN_EMAILS", "live-admin@example.com")
    monkeypatch.delenv("BATCH_JOBS_ALLOW_LAUNCH", raising=False)
    app.dependency_overrides[get_current_user] = lambda: User(
        user_id=3, email="live-admin@example.com", is_admin=True
    )
    client = TestClient(app)
    resp = client.post("/api/batch-jobs/launch", json={"step": "discover"})
    # Past the admin gate: launch is opt-in, so the endpoint's own guard answers
    # with its specific disabled message — not the require_admin rejection.
    assert resp.status_code == 403
    assert resp.json().get("detail") != "Admin privileges required"
    assert "launch disabled" in resp.json().get("detail", "").lower()
    app.dependency_overrides.pop(get_current_user, None)


def test_malformed_redirect_uri_does_not_500(app, db_session, monkeypatch):
    # A malformed redirect_uri (out-of-range port) used to raise ValueError deep
    # in _normalize_origin and 500 the login endpoint, violating its "never
    # hard-fail login over redirect_uri" contract. It must instead be dropped
    # and login proceed, storing no redirect target.
    monkeypatch.setenv("HUGGINGFACE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HUGGINGFACE_CLIENT_SECRET", "test-client-secret")
    client = TestClient(app)

    resp = client.get(
        "/api/auth/login/huggingface",
        params={"redirect_uri": "https://evil.example:99999"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 307)
    state = db_session.query(OAuthState).filter(OAuthState.provider == "huggingface").one()
    assert state.redirect_uri is None


def test_unsafe_redirect_uri_dropped_before_persist(app, db_session, monkeypatch):
    # Provider must be configured so the flow reaches OAuthState persistence
    # instead of short-circuiting on a missing-credentials 503.
    monkeypatch.setenv("HUGGINGFACE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HUGGINGFACE_CLIENT_SECRET", "test-client-secret")
    client = TestClient(app)

    resp = client.get(
        "/api/auth/login/huggingface",
        params={"redirect_uri": "https://evil.example/collect"},
        follow_redirects=False,
    )

    # Login still proceeds (redirects to the provider), but the attacker target
    # must never have been stored — the callback appends the JWT to it.
    assert resp.status_code in (302, 307)
    state = db_session.query(OAuthState).filter(OAuthState.provider == "huggingface").one()
    assert state.redirect_uri is None


def test_safe_redirect_uri_is_preserved(app, db_session, monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("HUGGINGFACE_CLIENT_SECRET", "test-client-secret")
    client = TestClient(app)

    resp = client.get(
        "/api/auth/login/huggingface",
        params={"redirect_uri": "/dashboard"},
        follow_redirects=False,
    )

    assert resp.status_code in (302, 307)
    state = db_session.query(OAuthState).filter(OAuthState.provider == "huggingface").one()
    assert state.redirect_uri == "/dashboard"
