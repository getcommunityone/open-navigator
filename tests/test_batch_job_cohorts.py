# tests/test_batch_job_cohorts.py
import asyncio

import httpx
import pytest
from fastapi import FastAPI

from api.batch_jobs.cohorts import (
    PRIORITY_STATE_CODES,
    cohort_state_codes,
    resolve_launch_states,
)
from api.routes import batch_jobs


class TestClient:
    """Minimal sync client over httpx.ASGITransport (httpx 0.28-compatible)."""

    __test__ = False

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


@pytest.fixture
def api_app():
    application = FastAPI()
    application.include_router(batch_jobs.router, prefix="/api")
    return application


def test_priority_states_are_fixed():
    assert cohort_state_codes("priority") == PRIORITY_STATE_CODES


def test_resolve_launch_states_default_priority_all():
    assert resolve_launch_states("priority", []) == PRIORITY_STATE_CODES


def test_resolve_launch_states_rejects_state_outside_cohort():
    try:
        resolve_launch_states("priority", ["TX"])
        assert False, "expected ValueError"
    except ValueError as e:
        assert "TX" in str(e)


def test_resolve_launch_states_data_centers_intersects(monkeypatch):
    monkeypatch.setattr(
        "api.batch_jobs.cohorts.cohort_state_codes",
        lambda cohort, **kw: ["AL", "VA", "TX"] if cohort == "data_centers" else [],
    )
    assert resolve_launch_states("data_centers", ["AL"]) == ["AL"]
    try:
        resolve_launch_states("data_centers", ["HI"])
        assert False
    except ValueError:
        pass


def test_cohorts_endpoint_shape(api_app, monkeypatch):
    class _FakeConn:
        def close(self) -> None:
            pass

    def _fake_cohort(cohort, **kw):
        return {
            "priority": ["AL", "GA"],
            "data_centers": ["AL", "VA"],
            "all": ["AL", "AK", "DC"],
        }[cohort]

    monkeypatch.setattr(
        "api.batch_jobs.batch_job_db.get_db_connection",
        lambda: _FakeConn(),
    )
    monkeypatch.setattr(
        "api.batch_jobs.cohorts.cohort_state_codes",
        _fake_cohort,
    )
    client = TestClient(api_app)
    r = client.get("/api/batch-jobs/cohorts")
    assert r.status_code == 200
    body = r.json()
    assert set(body.keys()) == {"priority", "data_centers", "all"}
    assert body["priority"] == ["AL", "GA"]
    assert body["data_centers"] == ["AL", "VA"]
    assert body["all"] == ["AL", "AK", "DC"]


def test_cohorts_endpoint_db_failure_returns_500(api_app, monkeypatch):
    def _boom():
        raise RuntimeError("db down")

    monkeypatch.setattr("api.batch_jobs.batch_job_db.get_db_connection", _boom)
    client = TestClient(api_app)
    r = client.get("/api/batch-jobs/cohorts")
    assert r.status_code == 500


@pytest.fixture
def launch_client(api_app, monkeypatch):
    from api.auth import User, require_admin

    monkeypatch.setenv("BATCH_JOBS_ALLOW_LAUNCH", "1")
    monkeypatch.setenv("ADMIN_EMAILS", "admin@test.com")
    api_app.dependency_overrides[require_admin] = lambda: User(
        user_id=1, email="admin@test.com", is_admin=True,
    )
    monkeypatch.setattr("api.routes.batch_jobs._dashboard_runtime", lambda: (0, ""))
    monkeypatch.setattr("api.routes.batch_jobs._read_launches", lambda: [])
    monkeypatch.setattr("api.routes.batch_jobs._write_launches", lambda *_a, **_k: None)
    yield TestClient(api_app)
    api_app.dependency_overrides.pop(require_admin, None)


def test_launch_rejects_unknown_cohort(launch_client):
    r = launch_client.post(
        "/api/batch-jobs/launch",
        json={"step": "analyze", "cohort": "nope", "states": ["AL"]},
    )
    assert r.status_code == 400


def test_launch_sets_cohort_env(launch_client, monkeypatch):
    captured = {}

    def fake_popen(argv, **kwargs):
        captured["env"] = kwargs["env"]
        captured["argv"] = argv

        class P:
            pid = 4242

        return P()

    class _FakeConn:
        def close(self) -> None:
            pass

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    # launch opens a DB conn for data_centers before resolve_launch_states
    monkeypatch.setattr(
        "api.batch_jobs.batch_job_db.get_db_connection",
        lambda: _FakeConn(),
    )
    monkeypatch.setattr(
        "api.batch_jobs.cohorts.resolve_launch_states",
        lambda cohort, states, **kw: ["AL"],
    )
    r = launch_client.post(
        "/api/batch-jobs/launch",
        json={
            "step": "analyze",
            "cohort": "data_centers",
            "states": ["AL"],
            "n": 5,
            "parallel": 2,
        },
    )
    assert r.status_code == 200
    assert captured["env"]["COHORT"] == "data_centers"
    assert captured["env"]["STATES"] == "AL"
    assert captured["argv"][:3] == ["bash", "--noprofile", "--norc"]
    assert not any(k.startswith("BASH_FUNC_") for k in captured["env"])


def test_launch_strips_bash_func_env(launch_client, monkeypatch):
    """Exported completion funcs must not reach child bash (#687)."""
    monkeypatch.setenv(
        "BASH_FUNC__xinetd_services%%",
        "() {  local -a svcs=($(printf '%s\\n' $xinetddir/!($_backup_glob))); }",
    )
    captured = {}

    def fake_popen(argv, **kwargs):
        captured["env"] = kwargs["env"]
        captured["argv"] = argv

        class P:
            pid = 4243

        return P()

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr("api.routes.batch_jobs._dashboard_runtime", lambda: (0, ""))
    r = launch_client.post(
        "/api/batch-jobs/launch",
        json={"step": "catalog", "cohort": "priority", "states": ["AL"]},
    )
    assert r.status_code == 200
    assert "BASH_FUNC__xinetd_services%%" not in captured["env"]
    assert not any(k.startswith("BASH_FUNC_") for k in captured["env"])
    assert captured["argv"][:3] == ["bash", "--noprofile", "--norc"]