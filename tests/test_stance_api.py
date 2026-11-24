"""Stance responses API (#851) — stub pool/connection, no real database."""

from __future__ import annotations

import asyncio
import importlib
import uuid
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from api.routes import stance

PID = str(uuid.uuid4())


class _Conn:
    def __init__(self, results=None, yours=None, saved=None):
        self.results = results or []
        self.yours = yours or []
        self.saved = saved
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, sql: str, *params: Any):
        self.calls.append((sql, params))

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.yours if "player_id = $1" in sql else self.results

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.saved is not None:
            return self.saved
        return {
            "pack_id": params[1],
            "statement_id": params[2],
            "statement_version": params[3],
            "answer": params[4],
            "state_code": params[5],
            "state": params[6],
            "place_name": params[7],
        }


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


@pytest.fixture(autouse=True)
def _reset():
    stance.clear_stance_rate_limits()
    stance.reset_table_ready()
    yield
    stance.clear_stance_rate_limits()
    stance.reset_table_ready()


@pytest.fixture
def call(monkeypatch):
    def _call(conn, method, path, **kw) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(stance, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(stance.router, prefix="/api")

        async def run():
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
                return await c.request(method, path, **kw)

        return asyncio.run(run())

    return _call


def _body(**over):
    b = {
        "player_id": PID,
        "pack_id": "data-centers",
        "statement_id": "jobs-worth-it",
        "answer": "agree",
    }
    b.update(over)
    return b


def _row(sid="jobs-worth-it", nat=(0, 0, 0, 0), st=(0, 0, 0, 0), pl=(0, 0, 0, 0)):
    r = {"statement_id": sid}
    for prefix, vals in (("nat", nat), ("st", st), ("pl", pl)):
        for suffix, v in zip(("n", "agree", "disagree", "unsure"), vals):
            r[f"{prefix}_{suffix}"] = v
    return r


# --- packs -------------------------------------------------------------------


def test_pack_listing(call):
    r = call(_Conn(), "GET", "/api/stance/packs")
    assert r.status_code == 200
    assert r.json() == [
        {
            "pack_id": "data-centers",
            "title": "Data centers",
            "version": 1,
            "statement_count": 8,
        }
    ]


def test_pack_content_and_404(call):
    ok = call(_Conn(), "GET", "/api/stance/packs/data-centers")
    assert ok.status_code == 200
    assert [s["order"] for s in ok.json()["statements"]] == list(range(1, 9))
    assert call(_Conn(), "GET", "/api/stance/packs/nope").status_code == 404
    assert call(_Conn(), "GET", "/api/stance/packs/nope/results").status_code == 404


def test_pack_file_ids_unique_and_charts_allowed():
    packs = stance.load_packs()
    sts = packs["data-centers"]["statements"]
    ids = [s["statement_id"] for s in sts]
    assert len(ids) == len(set(ids)) == 8
    assert {s["chart"] for s in sts} <= stance.ALLOWED_CHARTS
    assert all(s["version"] == 1 for s in sts)


def test_validate_pack_rejects_bad_packs():
    good = {
        "statement_id": "a",
        "version": 1,
        "order": 1,
        "category": "c",
        "statement": "s",
        "chart": "sites",
    }
    base = {"pack_id": "p", "title": "t", "version": 1}
    with pytest.raises(stance.PackError):
        stance.validate_pack({**base, "statements": [good, dict(good, order=2)]})
    with pytest.raises(stance.PackError):
        stance.validate_pack(
            {**base, "statements": [good, dict(good, statement_id="b")]}
        )
    with pytest.raises(stance.PackError):
        stance.validate_pack(
            {**base, "statements": [{k: v for k, v in good.items() if k != "chart"}]}
        )


# --- validation --------------------------------------------------------------


@pytest.mark.parametrize(
    "over,code",
    [
        ({"answer": "maybe"}, 422),
        ({"player_id": "not-a-uuid"}, 422),
        ({"statement_id": "nope"}, 404),
        ({"pack_id": "nope"}, 404),
        ({"state_code": "ZZ"}, 400),
        ({"place_name": "Tuscaloosa"}, 400),
        ({"state_code": "AL", "place_name": "x" * 121}, 400),
    ],
)
def test_post_validation(call, over, code):
    conn = _Conn()
    assert (
        call(conn, "POST", "/api/stance/responses", json=_body(**over)).status_code
        == code
    )
    assert conn.calls == []


# --- POST --------------------------------------------------------------------


def test_post_upserts_with_right_params_and_no_ip(call):
    conn = _Conn(results=[_row(nat=(2, 1, 1, 0))])
    r = call(
        conn,
        "POST",
        "/api/stance/responses",
        json=_body(state_code="al", place_name="  Tuscaloosa "),
        headers={"x-forwarded-for": "203.0.113.9"},
    )
    assert r.status_code == 200
    upserts = [c for c in conn.calls if "ON CONFLICT" in c[0]]
    assert len(upserts) == 1
    params = upserts[0][1]
    assert params == (
        uuid.UUID(PID),
        "data-centers",
        "jobs-worth-it",
        1,
        "agree",
        "AL",
        "Alabama",
        "Tuscaloosa",
    )
    assert any(
        "CREATE TABLE IF NOT EXISTS public.stance_response" in c[0] for c in conn.calls
    )
    flat = repr(conn.calls)
    assert "203.0.113.9" not in flat
    body = r.json()
    assert body["stance_response"]["state"] == "Alabama"
    assert body["results"]["statement_id"] == "jobs-worth-it"
    assert body["results"]["national"] == {
        "available": False,
        "n": 2,
        "agree": None,
        "disagree": None,
        "unsure": None,
    }
    assert body["results"]["place"]["n"] == 0


def test_table_created_once_per_process(call):
    conn = _Conn()
    call(conn, "POST", "/api/stance/responses", json=_body())
    first = sum("CREATE TABLE" in c[0] for c in conn.calls)
    call(conn, "POST", "/api/stance/responses", json=_body(player_id=str(uuid.uuid4())))
    assert first == 1 and sum("CREATE TABLE" in c[0] for c in conn.calls) == 1


def test_rate_limit_429(call, monkeypatch):
    monkeypatch.setattr(stance, "_RATE_PER_HOUR", 2)
    conn = _Conn()
    codes = [
        call(conn, "POST", "/api/stance/responses", json=_body()).status_code
        for _ in range(3)
    ]
    assert codes == [200, 200, 429]


# --- results -----------------------------------------------------------------


@pytest.mark.parametrize("n,available", [(0, False), (29, False), (30, True)])
def test_suppression_threshold(call, n, available):
    rows = [_row(nat=(n, n, 0, 0), st=(n, 0, n, 0), pl=(n, 0, 0, n))] if n else []
    r = call(
        _Conn(results=rows),
        "GET",
        "/api/stance/packs/data-centers/results",
        params={"state_code": "AL", "place_name": "Tuscaloosa"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["min_sample"] == 30
    assert len(data["statements"]) == 8
    first = data["statements"][0]
    for group, key in (
        ("national", "agree"),
        ("state", "disagree"),
        ("place", "unsure"),
    ):
        g = first[group]
        assert g["available"] is available
        assert g["n"] == n
        assert g[key] == (n if available else None)
    if not available:
        assert (
            first["national"]["agree"] is None and first["national"]["disagree"] is None
        )


def test_empty_table_every_group_n0_unavailable(call):
    data = call(_Conn(), "GET", "/api/stance/packs/data-centers/results").json()
    for st in data["statements"]:
        assert st["national"] == {
            "available": False,
            "n": 0,
            "agree": None,
            "disagree": None,
            "unsure": None,
        }
        assert st["state"] is None and st["place"] is None and st["your_answer"] is None


def test_your_answer_and_single_grouped_query(call):
    conn = _Conn(yours=[{"statement_id": "enough-already", "answer": "unsure"}])
    data = call(
        conn, "GET", "/api/stance/packs/data-centers/results", params={"player_id": PID}
    ).json()
    got = {s["statement_id"]: s["your_answer"] for s in data["statements"]}
    assert got["enough-already"] == "unsure" and got["jobs-worth-it"] is None
    assert sum("FROM public.stance_response r" in c[0] for c in conn.calls) == 1


def test_results_pass_current_versions_and_normalized_place(call):
    conn = _Conn()
    call(
        conn,
        "GET",
        "/api/stance/packs/data-centers/results",
        params={"state_code": "al", "place_name": " TuscaLoosa "},
    )
    sql, params = next(c for c in conn.calls if "FROM public.stance_response r" in c[0])
    assert "r.statement_version" in sql
    assert params[0] == "data-centers"
    assert params[2] == [1] * 8
    assert params[3:] == ("AL", "tuscaloosa")


def test_results_place_without_state_400_and_bad_uuid_422(call):
    assert (
        call(
            _Conn(),
            "GET",
            "/api/stance/packs/data-centers/results",
            params={"place_name": "X"},
        ).status_code
        == 400
    )
    assert (
        call(
            _Conn(),
            "GET",
            "/api/stance/packs/data-centers/results",
            params={"player_id": "bad"},
        ).status_code
        == 422
    )


# --- settings ----------------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected", [(None, 30), ("", 30), ("50", 50), ("0", 1), ("-4", 1), ("abc", 30)]
)
def test_min_sample_parsing(monkeypatch, raw, expected):
    if raw is None:
        monkeypatch.delenv("STANCE_MIN_SAMPLE", raising=False)
    else:
        monkeypatch.setenv("STANCE_MIN_SAMPLE", raw)
    assert stance._int_env("STANCE_MIN_SAMPLE", 30, 1) == expected
    importlib.reload(stance)
    assert stance.MIN_SAMPLE == expected
    monkeypatch.delenv("STANCE_MIN_SAMPLE", raising=False)
    importlib.reload(stance)
