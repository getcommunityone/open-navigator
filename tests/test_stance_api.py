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
    def __init__(
        self, results=None, yours=None, saved=None, choices=None, your_choices=None
    ):
        self.results = results or []
        self.yours = yours or []
        self.saved = saved
        self.choices = choices or []
        self.your_choices = your_choices or []
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def execute(self, sql: str, *params: Any):
        self.calls.append((sql, params))

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if "stance_choice_response" in sql:
            return self.your_choices if "player_id = $1" in sql else self.choices
        return self.yours if "player_id = $1" in sql else self.results

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if self.saved is not None:
            return self.saved
        if "stance_choice_response" in sql:
            return {
                "pack_id": params[1],
                "question_id": params[2],
                "question_version": params[3],
                "moment": params[4],
                "choice": params[5],
                "state_code": params[6],
                "state": params[7],
                "place_name": params[8],
            }
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
            "title": "Data Center Challenge",
            "version": 3,
            "statement_count": 7,
        }
    ]


def test_pack_content_and_404(call):
    ok = call(_Conn(), "GET", "/api/stance/packs/data-centers")
    assert ok.status_code == 200
    assert [s["order"] for s in ok.json()["statements"]] == list(range(1, 8))
    assert ok.json()["question"] == {
        "question_id": "allow-new",
        "version": 1,
        "text": "Should we allow new data centers?",
        "place_text": "Should {place} allow new data centers?",
        "options": [
            {"id": "yes", "label": "Yes"},
            {"id": "no", "label": "No"},
            {"id": "moratorium", "label": "Pause for now"},
        ],
    }
    assert call(_Conn(), "GET", "/api/stance/packs/nope").status_code == 404
    assert call(_Conn(), "GET", "/api/stance/packs/nope/results").status_code == 404


def test_pack_file_ids_unique_and_charts_allowed():
    packs = stance.load_packs()
    sts = packs["data-centers"]["statements"]
    ids = [s["statement_id"] for s in sts]
    assert len(ids) == len(set(ids)) == 7
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


def test_story_screen_and_speaker_lean_are_checked():
    """#981: the screen a statement is asked on, and what agreeing lines up with among meeting speakers."""
    good = {
        "statement_id": "a", "version": 1, "order": 1, "category": "c", "statement": "s",
        "chart": "concerns", "story_screen": "concerns", "speaker_lean": None,
    }
    base = {"pack_id": "p", "title": "t", "version": 1}
    ok = stance.validate_pack(
        {**base, "statements": [good, dict(good, statement_id="b", order=2, story_screen="jobs", speaker_lean="for")]}
    )
    assert [s["story_screen"] for s in ok["statements"]] == ["concerns", "jobs"]
    with pytest.raises(stance.PackError, match="speaker_lean"):
        stance.validate_pack({**base, "statements": [dict(good, speaker_lean="maybe")]})
    with pytest.raises(stance.PackError, match="share a story_screen"):
        stance.validate_pack({**base, "statements": [good, dict(good, statement_id="b", order=2)]})
    with pytest.raises(stance.PackError, match="story_screen"):
        stance.validate_pack({**base, "statements": [dict(good, story_screen="")]})


def test_data_center_pack_maps_each_story_screen_once():
    pack = stance.load_packs()["data-centers"]
    by_screen = {s["story_screen"]: s for s in pack["statements"] if s.get("story_screen")}
    assert set(by_screen) == {"sites", "projects", "jobs", "concerns", "meetings", "agendas", "gatherings"}
    # A lean only where agreeing clearly lines up with one side of the meeting speakers.
    assert {k: v["speaker_lean"] for k, v in by_screen.items() if v["speaker_lean"]} == {
        "jobs": "for", "sites": "against", "projects": "for",
    }


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
    assert len(data["statements"]) == 7
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
    assert params[2] == [1] * 7
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


# --- the before/after question (#915) ----------------------------------------

CHOICES_URL = "/api/stance/choices"
CHOICE_RESULTS_URL = "/api/stance/packs/data-centers/choice-results"
_QUESTION = {
    "question_id": "q",
    "version": 1,
    "text": "Should we?",
    "place_text": "Should {place}?",
    "options": [{"id": "yes", "label": "Yes"}, {"id": "no", "label": "No"}],
}


def _choice(**over):
    b = {
        "player_id": PID,
        "pack_id": "data-centers",
        "question_id": "allow-new",
        "moment": "before",
        "choice": "moratorium",
    }
    b.update(over)
    return b


def _crow(moment, choice, nat=0, st=0, pl=0):
    return {"moment": moment, "choice": choice, "nat_n": nat, "st_n": st, "pl_n": pl}


@pytest.mark.parametrize(
    "change",
    [
        {"options": [{"id": "yes", "label": "Yes"}]},
        {"options": [{"id": "yes", "label": "Yes"}, {"id": "yes", "label": "Yes"}]},
        {"options": [{"id": "yes", "label": "Yes"}, {"id": "no"}]},
        {"place_text": "Should we?"},
        {"version": "1"},
        {"text": ""},
    ],
)
def test_validate_pack_rejects_bad_question(change):
    st = {
        "statement_id": "a",
        "version": 1,
        "order": 1,
        "category": "c",
        "statement": "s",
        "chart": "sites",
    }
    pack = {"pack_id": "p", "title": "t", "version": 1, "statements": [st]}
    assert stance.validate_pack({**pack, "question": dict(_QUESTION)})
    with pytest.raises(stance.PackError):
        stance.validate_pack({**pack, "question": {**_QUESTION, **change}})


@pytest.mark.parametrize(
    "over,code",
    [
        ({"choice": "maybe"}, 422),
        ({"choice": "agree"}, 422),
        ({"moment": "during"}, 422),
        ({"player_id": "not-a-uuid"}, 422),
        ({"question_id": "nope"}, 404),
        ({"pack_id": "nope"}, 404),
        ({"state_code": "ZZ"}, 400),
        ({"place_name": "Tuscaloosa"}, 400),
        ({"state_code": "AL", "place_name": "x" * 121}, 400),
    ],
)
def test_choice_validation_stores_nothing(call, over, code):
    conn = _Conn()
    assert call(conn, "POST", CHOICES_URL, json=_choice(**over)).status_code == code
    assert conn.calls == []


def test_choice_upserts_once_per_reader_question_and_moment(call):
    conn = _Conn()
    r = call(
        conn,
        "POST",
        CHOICES_URL,
        json=_choice(moment="after", state_code="al", place_name=" Tuscaloosa "),
        headers={"x-forwarded-for": "203.0.113.9"},
    )
    assert r.status_code == 200
    upserts = [c for c in conn.calls if "ON CONFLICT" in c[0]]
    assert len(upserts) == 1
    sql, params = upserts[0]
    assert (
        "ON CONFLICT (player_id, pack_id, question_id, question_version, moment)" in sql
    )
    assert params == (
        uuid.UUID(PID),
        "data-centers",
        "allow-new",
        1,
        "after",
        "moratorium",
        "AL",
        "Alabama",
        "Tuscaloosa",
    )
    create = next(c[0] for c in conn.calls if "CREATE TABLE" in c[0])
    assert "public.stance_choice_response" in create
    assert "stance_choice_response_id bigserial PRIMARY KEY" in create
    assert (
        "UNIQUE (player_id, pack_id, question_id, question_version, moment)" in create
    )
    assert "203.0.113.9" not in repr(conn.calls)
    body = r.json()
    assert body["stance_choice_response"] == {
        "pack_id": "data-centers",
        "question_id": "allow-new",
        "question_version": 1,
        "moment": "after",
        "choice": "moratorium",
        "state_code": "AL",
        "state": "Alabama",
        "place_name": "Tuscaloosa",
    }
    assert body["results"]["after"]["national"] == {
        "available": False,
        "n": 0,
        "counts": None,
    }


def test_choice_shares_the_rate_limit(call, monkeypatch):
    monkeypatch.setattr(stance, "_RATE_PER_HOUR", 2)
    conn = _Conn()
    assert call(conn, "POST", "/api/stance/responses", json=_body()).status_code == 200
    assert call(conn, "POST", CHOICES_URL, json=_choice()).status_code == 200
    assert call(conn, "POST", CHOICES_URL, json=_choice()).status_code == 429


def test_choice_results_empty_table_seeds_nothing(call):
    data = call(_Conn(), "GET", CHOICE_RESULTS_URL).json()
    none = {"available": False, "n": 0, "counts": None}
    assert data == {
        "min_sample": 30,
        "question_id": "allow-new",
        "question_version": 1,
        "your": {"before": None, "after": None},
        "before": {"national": none, "state": None, "place": None},
        "after": {"national": none, "state": None, "place": None},
    }


def test_choice_results_withhold_below_min_sample_per_group(call):
    rows = [
        _crow("before", "yes", nat=20, st=10, pl=1),
        _crow("before", "no", nat=10, st=19, pl=0),
        _crow("after", "yes", nat=12, st=30),
        _crow("after", "moratorium", nat=17),
        _crow("after", "retired-option", nat=500, st=500, pl=500),
    ]
    conn = _Conn(
        choices=rows,
        your_choices=[
            {"moment": "before", "choice": "yes"},
            {"moment": "after", "choice": "no"},
        ],
    )
    r = call(
        conn,
        "GET",
        CHOICE_RESULTS_URL,
        params={"state_code": "al", "place_name": " TuscaLoosa ", "player_id": PID},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["your"] == {"before": "yes", "after": "no"}
    assert data["before"]["national"] == {
        "available": True,
        "n": 30,
        "counts": {"yes": 20, "no": 10, "moratorium": 0},
    }
    assert data["before"]["state"] == {"available": False, "n": 29, "counts": None}
    assert data["before"]["place"] == {"available": False, "n": 1, "counts": None}
    assert data["after"]["national"] == {"available": False, "n": 29, "counts": None}
    assert data["after"]["state"] == {
        "available": True,
        "n": 30,
        "counts": {"yes": 30, "no": 0, "moratorium": 0},
    }
    assert data["after"]["place"] == {"available": False, "n": 0, "counts": None}
    grouped = [c for c in conn.calls if "GROUP BY c.moment, c.choice" in c[0]]
    assert len(grouped) == 1
    assert grouped[0][1] == ("data-centers", "allow-new", 1, "AL", "tuscaloosa")


def test_choice_results_errors(call):
    assert (
        call(_Conn(), "GET", "/api/stance/packs/nope/choice-results").status_code == 404
    )
    assert (
        call(_Conn(), "GET", CHOICE_RESULTS_URL, params={"place_name": "X"}).status_code
        == 400
    )
    assert (
        call(
            _Conn(), "GET", CHOICE_RESULTS_URL, params={"player_id": "bad"}
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
