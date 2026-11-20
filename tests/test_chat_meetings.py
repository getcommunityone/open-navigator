"""POST /api/chat/meetings (#630) — mocked DB + LLM."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from api.routes import chat_meetings as chat

PATH = "/api/chat/meetings"


class _Row(dict):
    pass


class _Conn:
    def __init__(self, rows=None, segment_row=None):
        self.rows = [_Row(r) for r in (rows or [])]
        self.segment_row = _Row(segment_row) if segment_row is not None else None
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.rows

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.segment_row


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
def _reset_limits():
    chat.clear_chat_rate_limits()
    yield
    chat.clear_chat_rate_limits()


@pytest.fixture
def post(monkeypatch):
    def _post(
        conn: _Conn,
        body: dict[str, Any],
        *,
        llm_text: str = "Based on the Madison meeting summary, …",
    ) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(chat, "get_db_pool", pool)
        monkeypatch.setattr(
            chat,
            "_call_flash_lite",
            lambda system, user: (llm_text, "gemini-2.5-flash-lite", 900, 200, 0.0002),
        )

        app = FastAPI()
        app.include_router(chat.router, prefix="/api")

        async def go():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://t"
            ) as c:
                return await c.post(PATH, json=body)

        return asyncio.run(go())

    return _post


def _meeting_row(**kw) -> dict[str, Any]:
    base = dict(
        event_meeting_id=5238,
        body_name="Common Council",
        jurisdiction_name="Madison",
        state="Wisconsin",
        state_code="WI",
        city="Madison",
        iso_date="2026-04-21",
        meeting_summary="Council discussed water rates and a fluoride petition.",
        agenda_summary="Water, fluoride",
        video_id="Sk0m1dHUJjg",
    )
    base.update(kw)
    return base


def test_summaries_path_returns_citations(post):
    resp = post(_Conn(rows=[_meeting_row()]), {"question": "fluoride in Madison"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "summaries"
    assert data["found"] is True
    assert data["citations"][0]["title"] == "Common Council"
    assert data["citations"][0]["date"] == "2026-04-21"
    assert data["citations"][0]["url"] == "/meetings/5238"


def test_no_meetings_found_false_no_llm_needed(post, monkeypatch):
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise AssertionError("LLM should not run when search is empty")

    monkeypatch.setattr(chat, "_call_flash_lite", boom)
    resp = post(_Conn(rows=[]), {"question": "zzz-no-match-term"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["found"] is False
    assert data["citations"] == []
    assert calls["n"] == 0


def test_rate_limit_min_interval(post):
    conn = _Conn(rows=[_meeting_row()])
    assert post(conn, {"question": "budget"}).status_code == 200
    assert post(conn, {"question": "budget again"}).status_code == 429


def test_spend_cap_returns_503(post, monkeypatch):
    monkeypatch.setattr(chat, "_DAILY_SPEND_CAP_USD", 0.0001)
    chat._spend_by_utc_day[chat._utc_day_key()] = 0.0001
    assert post(_Conn(rows=[_meeting_row()]), {"question": "taxes"}).status_code == 503


def test_filter_topic_passages_caps_and_matches():
    cues = [
        chat.TranscriptCue(start=1.0, text="Opening remarks"),
        chat.TranscriptCue(start=10.0, text="We will discuss fluoride levels today"),
        chat.TranscriptCue(start=20.0, text="Unrelated zoning"),
        chat.TranscriptCue(start=30.0, text="Fluoride again in public comment"),
    ]
    passages = chat.filter_topic_passages(cues, "fluoride", char_cap=500)
    assert len(passages) == 2
    huge = [chat.TranscriptCue(start=float(i), text="fluoride " + ("x" * 200)) for i in range(200)]
    capped = chat.filter_topic_passages(huge, "fluoride", char_cap=500)
    assert sum(len(p) for p in capped) <= 550
    assert len(capped) < len(huge)


def test_passages_path(post):
    segs = [
        {"s": 10, "t": "Council debated fluoride in the water supply"},
        {"s": 99, "t": "Adjournment"},
    ]
    resp = post(
        _Conn(rows=[], segment_row={"segments": segs}),
        {
            "question": "What did they say about fluoride?",
            "detail_video_id": "Sk0m1dHUJjg",
            "detail_topic": "fluoride",
        },
        llm_text="At 10s they debated fluoride in the water supply.",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["mode"] == "passages"
    assert data["found"] is True
    assert data["citations"][0]["video_id"] == "Sk0m1dHUJjg"
