"""#796: /api/deployments serves two groups (load, deploy) with the right safety rules."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import types
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture()
def mod(monkeypatch, tmp_path):
    """Load the route module with the admin check stubbed and no subprocess ever started."""
    auth = types.ModuleType("api.auth")
    auth.require_admin = lambda: None
    monkeypatch.setitem(sys.modules, "api", types.ModuleType("api"))
    monkeypatch.setitem(sys.modules, "api.auth", auth)
    spec = importlib.util.spec_from_file_location(
        "deployments_under_test", ROOT / "api" / "routes" / "deployments.py"
    )
    m = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, spec.name, m)  # pydantic resolves annotations through sys.modules
    spec.loader.exec_module(m)
    monkeypatch.setattr(m, "_status_dir", lambda: tmp_path)
    monkeypatch.delenv("DEPLOYMENTS_ALLOW_LAUNCH", raising=False)

    launched: list[list[str]] = []

    class _FakeProc:
        pid = os.getpid()

    def _fake_popen(argv, **_kw):
        launched.append(list(argv))
        return _FakeProc()

    monkeypatch.setattr(m.subprocess, "Popen", _fake_popen)
    m.launched = launched
    return m


@pytest.fixture()
def client(mod):
    app = FastAPI()
    app.include_router(mod.router)
    return TestClient(app)


def _steps_arg(argv: list[str]) -> list[str]:
    return argv[argv.index("--steps") + 1].split(",")


def test_list_load_group_shows_only_load_steps_and_is_enabled(client):
    body = client.get("/deployments/?group=load").json()
    assert [s["key"] for s in body["available_steps"]] == ["load-analysis", "dbt-gold"]
    assert all(s["group"] == "load" for s in body["available_steps"])
    assert body["enabled"] is True  # no prod flag needed: it only writes the local warehouse


def test_list_deploy_group_is_gated_by_the_prod_flag(client, monkeypatch):
    body = client.get("/deployments/?group=deploy").json()
    assert [s["key"] for s in body["available_steps"]] == ["database", "web"]
    assert body["enabled"] is False
    monkeypatch.setenv("DEPLOYMENTS_ALLOW_LAUNCH", "1")
    assert client.get("/deployments/?group=deploy").json()["enabled"] is True


def test_list_rejects_an_unknown_group(client):
    assert client.get("/deployments/?group=nope").status_code == 400


def test_real_load_launch_needs_no_prod_flag(client, mod):
    r = client.post("/deployments/launch", json={"group": "load", "dry_run": False})
    assert r.status_code == 200, r.text
    assert r.json()["job_id"].startswith("load_")
    assert _steps_arg(mod.launched[0]) == ["load-analysis", "dbt-gold"]  # the group's defaults


def test_real_deploy_launch_is_still_blocked_without_the_prod_flag(client, mod):
    r = client.post("/deployments/launch", json={"group": "deploy", "dry_run": False})
    assert r.status_code == 403
    assert mod.launched == []


def test_dry_run_deploy_is_allowed(client):
    r = client.post("/deployments/launch", json={"steps": ["database"], "dry_run": True})
    assert r.status_code == 200 and r.json()["job_id"].startswith("deploy_")


def test_default_launch_without_a_group_is_still_the_database_deploy(client, mod):
    r = client.post("/deployments/launch", json={"dry_run": True})
    assert r.status_code == 200
    assert _steps_arg(mod.launched[0]) == ["database"]


def test_mixed_groups_are_rejected(client, mod):
    r = client.post("/deployments/launch", json={"steps": ["load-analysis", "database"], "dry_run": True})
    assert r.status_code == 400 and "cannot run in the same job" in r.json()["detail"]
    assert mod.launched == []


def test_a_live_load_job_blocks_another_load_but_not_a_deploy(client, mod, tmp_path):
    (tmp_path / "load_live.json").write_text(
        json.dumps(
            {
                "job_id": "load_live",
                "status": "running",
                "pid": os.getpid(),  # alive
                "started_at": "2026-11-24T00:00:00Z",
                "steps": [{"key": "load-analysis"}, {"key": "dbt-gold"}],
            }
        )
    )
    assert client.post("/deployments/launch", json={"group": "load", "dry_run": True}).status_code == 409
    assert client.post("/deployments/launch", json={"group": "deploy", "dry_run": True}).status_code == 200


def test_jobs_are_filtered_by_group(client, tmp_path):
    for jid, key in (("load_a", "dbt-gold"), ("deploy_a", "database")):
        (tmp_path / f"{jid}.json").write_text(
            json.dumps({"job_id": jid, "status": "completed", "pid": 1, "started_at": "x", "steps": [{"key": key}]})
        )
    load = client.get("/deployments/?group=load").json()["jobs"]
    deploy = client.get("/deployments/?group=deploy").json()["jobs"]
    assert [j["job_id"] for j in load] == ["load_a"] and load[0]["group"] == "load"
    assert [j["job_id"] for j in deploy] == ["deploy_a"] and deploy[0]["group"] == "deploy"
    assert {j["job_id"] for j in client.get("/deployments/").json()["jobs"]} == {"load_a", "deploy_a"}
