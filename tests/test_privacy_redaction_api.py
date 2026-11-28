"""#1468: no endpoint serves a private resident's full name or home address inside meeting text.

Three layers of checks:

1. Every handler that serves meeting text returns through ``redact_response`` (read from the source, so a new
   ``return`` that skips it fails here).
2. For each of those endpoints, its own response model, with every text-like field set to a passage that names a
   private resident and their address, comes back with the surname and the house number gone. A text field the
   endpoint forgot to list fails here.
3. Requests through the real routes (trending-term evidence, the meeting transcript, data-center job claims, search
   results) with a seeded private name in the database rows: the name never reaches the response, and an official of
   that government keeps theirs.
"""

from __future__ import annotations

import ast
import asyncio
import datetime as dt
import importlib
import re
import typing
from pathlib import Path
from typing import Any

import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel

from api import privacy_redaction as pr

ROUTES = Path(__file__).resolve().parents[1] / "api" / "routes"

# Invented people; nothing here is served by the app.
SURNAME = "Pemberton"
HOUSE = "4127"
SEEDED = (
    f"Thank you. Next speaker is Johnathan {SURNAME} of {HOUSE} Elmwood Street. "
    f"My neighbor Bob Hartwell agrees with Mr. {SURNAME} about the <mark>data center</mark>."
)

# handler -> module; every one of these serves verbatim meeting text (the #1468 audit).
HANDLERS: dict[str, list[str]] = {
    "trending_terms": ["trending_term_evidence"],
    "topics": ["list_topic_meetings", "topic_states", "list_topic_decisions"],
    "topic_outcomes": ["topic_outcomes"],
    "topic_upcoming": ["topic_upcoming"],
    "topic_companies": ["topic_companies"],
    "topic_organizations": ["topic_organizations"],
    "data_centers": [
        "list_data_center_meeting_mentions", "data_center_positions", "list_data_center_agenda_items",
        "list_job_claims", "list_data_center_projects", "data_center_decisions", "list_data_center_hearings",
    ],
    "data_center_drill": ["data_center_speakers", "data_center_caption_comments", "data_center_vote_decisions"],
    "policy_questions": ["get_question_meetings", "get_question_jev", "get_question_instances", "get_policy_question"],
    "meeting_browse": ["list_meetings"],
    "meetings": ["get_meeting"],
    "meeting_comparison": ["get_meeting_comparison", "analyze_document_gaps"],
    "decisions": ["get_decision", "get_decision_map", "get_related_decisions", "get_decision_thread"],
    "decision_browse": ["list_decisions"],
    "lenses": ["get_lenses"],
    "chat_meetings": ["chat_meetings"],
    "organizations": ["organization_profile"],
    "short_term_rentals": ["platform_companies"],
}
CASES = [(m, h) for m, hs in HANDLERS.items() for h in hs]

# Field names that carry text a person could be named in.
TEXTISH = re.compile(
    r"(excerpt|quote|evidence|passage|snippet|statement|summary|headline|^description$|^text$|^detail$|matched_text|"
    r"match_text|^answer$|cue_text|vote_text|speaker_name|possible_name|event_description)"
)
# Text-like names that are not meeting text: our own labels, URLs and enum-like codes.
NOT_MEETING_TEXT = {"evidence_source", "excerpt_source", "evidence_label", "match_basis", "attribution_evidence",
                    "evidence_url", "quote_url", "summary_url", "match_text_source", "description_source"}


# (handler, field): text-like fields that are not meeting text.
EXEMPT = {("list_job_claims", "description"): "a job source's citation, from our own seed"}


def _handler_node(module: str, handler: str) -> ast.AsyncFunctionDef:
    tree = ast.parse((ROUTES / f"{module}.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == handler:
            return node
    raise AssertionError(f"{module}.{handler} not found")


def _own_returns(fn: ast.AST) -> list[ast.Return]:
    out: list[ast.Return] = []

    def walk(node: ast.AST) -> None:
        for ch in ast.iter_child_nodes(node):
            if isinstance(ch, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            if isinstance(ch, ast.Return) and ch.value is not None:
                out.append(ch)
            walk(ch)

    walk(fn)
    return out


def _redact_call(ret: ast.Return) -> ast.Call | None:
    v = ret.value
    if isinstance(v, ast.Await) and isinstance(v.value, ast.Call):
        f = v.value.func
        if isinstance(f, ast.Name) and f.id == "redact_response":
            return v.value
    return None


@pytest.mark.parametrize("module,handler", CASES)
def test_every_return_goes_through_redact_response(module: str, handler: str) -> None:
    rets = _own_returns(_handler_node(module, handler))
    assert rets, f"{module}.{handler} has no return"
    for r in rets:
        assert _redact_call(r) is not None, f"{module}.{handler} line {r.lineno} returns without redact_response"


# --- 2. each endpoint's own response model --------------------------------------------------------------------------


def _fields_for(module: str, handler: str) -> tuple[frozenset[str], frozenset[str]]:
    call = _redact_call(_own_returns(_handler_node(module, handler))[-1])
    assert call is not None
    ns = {k: getattr(pr, k) for k in dir(pr) if k.isupper()}
    fields = eval(compile(ast.Expression(call.args[1]), "<fields>", "eval"), ns) if len(call.args) > 1 else pr.TEXT_FIELDS
    deep = frozenset()
    for kw in call.keywords:
        if kw.arg == "deep_fields":
            deep = eval(compile(ast.Expression(kw.value), "<deep>", "eval"), ns)
    return frozenset(fields), frozenset(deep)


def _response_model(module: str, handler: str) -> Any:
    mod = importlib.import_module(f"api.routes.{module}")
    for route in mod.router.routes:
        if getattr(route, "endpoint", None) is not None and route.endpoint.__name__ == handler:
            return route.response_model or typing.get_type_hints(route.endpoint).get("return")
    raise AssertionError(f"no route for {module}.{handler}")


def _build(tp: Any, name: str = "", depth: int = 0) -> Any:
    origin, args = typing.get_origin(tp), typing.get_args(tp)
    if origin is typing.Union or str(origin) == "<class 'types.UnionType'>":
        real = [a for a in args if a is not type(None)]
        return _build(real[0], name, depth) if real else None
    if origin is typing.Literal:
        return args[0]
    if origin in (list, typing.List, tuple, set):
        return [_build(args[0], name, depth + 1)] if args and depth < 6 else []
    if origin in (dict, typing.Dict):
        return {}
    if isinstance(tp, type) and issubclass(tp, BaseModel):
        if depth > 6:
            return None
        values = {}
        for fname, finfo in tp.model_fields.items():
            values[fname] = _build(finfo.annotation, fname, depth + 1)
        return tp.model_construct(**values)
    if tp is str:
        return SEEDED if TEXTISH.search(name) and name not in NOT_MEETING_TEXT else "x"
    if tp is bool:
        return True
    if tp is int:
        return 1
    if tp is float:
        return 1.0
    if tp is dt.date:
        return dt.date(2026, 11, 1)
    if tp is dt.datetime:
        return dt.datetime(2026, 11, 1)
    return None


def _text_strings(obj: Any, name: str = "") -> list[str]:
    """Every seeded text value left in the payload."""
    if isinstance(obj, BaseModel):
        return [s for f in type(obj).model_fields for s in _text_strings(getattr(obj, f, None), f)]
    if isinstance(obj, list):
        return [s for x in obj for s in _text_strings(x, name)]
    if isinstance(obj, dict):
        return [s for k, v in obj.items() for s in _text_strings(v, k)]
    return [f"{name}={obj}"] if isinstance(obj, str) and (SURNAME in obj or HOUSE in obj) else []


@pytest.fixture
def no_officials(monkeypatch):
    monkeypatch.setitem(pr._cache, "by_place", {})
    monkeypatch.setitem(pr._cache, "by_state", {})


@pytest.mark.parametrize("module,handler", CASES)
def test_the_endpoint_model_loses_a_seeded_private_name(module: str, handler: str, no_officials) -> None:
    fields, deep = _fields_for(module, handler)
    payload = _build(_response_model(module, handler))
    assert payload is not None
    pr.redact_payload(payload, fields, deep_fields=deep)
    left = [s for s in _text_strings(payload) if (handler, s.split("=", 1)[0]) not in EXEMPT]
    assert not left, f"{module}.{handler} still serves: {left[:3]}"


# --- 3. through the real routes -------------------------------------------------------------------------------------


class _Conn:
    def __init__(self, rows: list[dict[str, Any]], row: dict[str, Any] | None = None):
        self.rows, self.row = rows, row

    async def fetch(self, sql: str, *params: Any):
        return self.rows

    async def fetchrow(self, sql: str, *params: Any):
        return self.row


class _Acquire:
    def __init__(self, conn):
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, *a):
        return False


class _Pool:
    def __init__(self, conn):
        self.conn = conn

    def acquire(self):
        return _Acquire(self.conn)


@pytest.fixture
def tuscaloosa_officials(monkeypatch):
    """The officials index as loaded from person_government: one Tuscaloosa council member."""
    monkeypatch.setitem(pr._cache, "ok", True)
    monkeypatch.setitem(pr._cache, "at", 1e18)  # fresh: no load attempted
    monkeypatch.setitem(pr._cache, "by_place", {"AL|tuscaloosa": frozenset({"kip tyner"})})
    monkeypatch.setitem(pr._cache, "by_state", {})


def _get(module, router, path: str, conn: _Conn, monkeypatch, params: dict | None = None) -> httpx.Response:
    async def pool():
        return _Pool(conn)

    monkeypatch.setattr(module, "get_db_pool", pool)
    app = FastAPI()
    app.include_router(router, prefix="/api" if not router.prefix.startswith("/api") else "")

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            return await c.get(path, params=params)

    return asyncio.run(go())


def test_trending_term_evidence_route(monkeypatch, tuscaloosa_officials) -> None:
    from api.routes import trending_terms as tt

    tid = "0123456789abcdef0123456789abcdef"
    ev = {"video_id": "abcdefghijk", "meeting_date": dt.date(2026, 10, 1), "jurisdiction_name": "Tuscaloosa",
          "state_code": "AL", "excerpt": SEEDED + " Kip Tyner moved to table it.", "excerpt_source": "transcript",
          "start_seconds": None, "speaker_display_name": None, "total": 1}
    conn = _Conn([ev], row={"term": "data center", "is_sensitive": False, "n_meetings": 3})
    body = _get(tt, tt.router, f"/api/trends/terms/{tid}/evidence", conn, monkeypatch, {"state": "AL"})
    assert body.status_code == 200
    excerpt = body.json()["items"][0]["excerpt"]
    assert SURNAME not in excerpt and HOUSE not in excerpt and "Hartwell" not in excerpt
    assert "Johnathan P." in excerpt and "Kip Tyner" in excerpt  # the official keeps their name
    assert "<mark>data center</mark>" in excerpt


def test_meeting_transcript_route(monkeypatch, tuscaloosa_officials) -> None:
    from api.routes import meetings

    row = {"video_id": "abcdefghijk", "language": "en", "has_transcript": True, "state_code": "AL",
           "jurisdiction_name": "Tuscaloosa",
           "segments": [{"start": 1.0, "text": "next speaker is Johnathan"},
                        {"start": 3.0, "text": f"{SURNAME} of {HOUSE} Elmwood Street"},
                        {"start": 6.0, "text": "Councilman Kip Tyner, you may respond"}]}
    body = _get(meetings, meetings.router, "/api/meeting/abcdefghijk/transcript", _Conn([], row), monkeypatch)
    assert body.status_code == 200
    texts = [s["text"] for s in body.json()["segments"]]
    joined = " ".join(texts)
    assert SURNAME not in joined and HOUSE not in joined
    assert texts[0] == "next speaker is Johnathan P."
    assert "Kip Tyner" in texts[2]


def test_job_claim_speaker_name_route(monkeypatch, tuscaloosa_officials) -> None:
    from api.routes import data_centers as dc

    base = {"job_claim_id": "j1", "phase": "construction", "headcount_low": 100, "headcount_high": 200,
            "starts_on": None, "ends_on": None, "project_name": "Project X", "person_id": None,
            "event_meeting_id": 9, "meeting_date": dt.date(2026, 3, 2), "body_name": "City Council",
            "video_id": "abcdefghijk", "start_seconds": 1.0, "state_code": "AL", "jurisdiction_name": "Tuscaloosa"}
    rows = [{**base, "quote": SEEDED, "speaker_name": f"Johnathan {SURNAME}", "speaker_role": "resident"},
            {**base, "job_claim_id": "j2", "quote": "we expect 200 jobs", "speaker_name": "Kip Tyner",
             "speaker_role": "council member"}]

    class _JC(_Conn):
        async def fetch(self, sql: str, *params: Any):
            return [] if "count(" in sql.lower() else self.rows

    async def _no_payroll(scope):
        return [], []

    monkeypatch.setattr(dc, "_payroll_and_sources", _no_payroll)
    body = _get(dc, dc.router, "/api/data-centers/job-claims", _JC(rows), monkeypatch, {"state": "AL"})
    assert body.status_code == 200, body.text
    text = body.text
    assert SURNAME not in text and HOUSE not in text
    names = [i["speaker_name"] for i in body.json()["items"]]
    assert names == ["Johnathan P.", "Kip Tyner"]


def test_search_results_quote_meeting_text_redacted(tuscaloosa_officials) -> None:
    from api.routes import search, search_postgres

    def result(kind: str, title: str = "City Council") -> Any:
        return search_postgres.SearchResult(
            result_type=kind, title=title, subtitle="", description=SEEDED, url="/x", score=1.0,
            metadata={"state_code": "AL", "jurisdiction": "Tuscaloosa"})

    for kind in ("meeting", "document", "meeting_document", "decision", "topic"):
        out = search.convert_pg_result(result(kind, title=f"Council thanks Johnathan {SURNAME}"))
        assert SURNAME not in (out.description or "") and HOUSE not in (out.description or ""), kind
        assert "<mark>data center</mark>" in out.description
        if kind in ("decision", "topic"):
            assert SURNAME not in out.title
    # People and organizations are not meeting text: their names are untouched.
    person = search.convert_pg_result(result("leader", title="Kip Tyner"))
    assert person.title == "Kip Tyner"


def test_officials_index_from_served_rows() -> None:
    by_place, by_state = pr.build_official_index(
        [{"state_code": "AL", "jurisdiction": "Tuscaloosa Government", "full_name": "Kip Tyner", "office": "government"},
         {"state_code": "TX", "jurisdiction": "Criminal Jurisprudence", "full_name": "A.J. Louderback", "office": "legislature"}],
        [{"state_code": "AL", "jurisdiction": "Northport", "full_name": "Jeff Hogg"}],
    )
    assert by_place["AL|tuscaloosa"] == {"kip tyner"}
    assert by_place["AL|northport"] == {"jeff hogg"}
    assert by_state["TX"] == {"aj louderback"}


def test_school_board_rows_serve_no_name_at_all(no_officials) -> None:
    """The minors rule holds on the newly covered paths: a school district's excerpt names nobody."""
    payload = {"items": [{"state_code": "AL", "jurisdiction_name": "Tuscaloosa City Schools",
                          "excerpt": "Thank you, Emma. Next speaker is Jacob Pemberton."},
                         {"state_code": "AL", "jurisdiction_name": "Tuscaloosa", "jurisdiction_type": "municipality",
                          "meeting_title": "Board of Education joint session", "evidence": "my name is Jacob Pemberton"}]}
    pr.redact_payload(payload)
    assert payload["items"][0]["excerpt"] == "Thank you, [name]. Next speaker is [name]."
    assert payload["items"][1]["evidence"] == "my name is [name]"
