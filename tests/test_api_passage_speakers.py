"""Speaker names on story-map quotes from self-introductions (#1231).

GET /api/topics/{id}/states `newest[]` and the data-center mention cards carry speaker_display_name / speaker_role
from meeting_passage_speaker. The DB layer is mocked; the rows are test stand-ins, not warehouse figures.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from api.routes import data_centers, topics

NEWEST = [
    {"topic_transcript_link_id": "t1", "video_id": "v1", "event_title": "Council", "event_date": dt.date(2026, 3, 1),
     "state_code": "TX", "state": "Texas", "city": "Austin", "jurisdiction_name": "Austin", "video_url": "u",
     "evidence_passage": "the <mark>pickleball</mark> courts", "n_keyword_hits": 1},
    {"topic_transcript_link_id": "t2", "video_id": "v2", "event_title": "Council", "event_date": None,
     "state_code": "WI", "state": "Wisconsin", "city": None, "jurisdiction_name": "Madison", "video_url": "u",
     "evidence_passage": "more <mark>pickleball</mark>", "n_keyword_hits": 1},
]


class _Conn:
    def __init__(self, speakers: list[dict[str, Any]] | None, error: bool = False):
        self.speakers = speakers
        self.error = error
        self.calls: list[str] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append(sql)
        if "meeting_passage_speaker" in sql:
            if self.error:
                raise asyncpg.exceptions.UndefinedTableError('relation "meeting_passage_speaker" does not exist')
            return [s for s in (self.speakers or []) if s["topic_transcript_link_id"] in params[0]]
        if "DISTINCT ON" in sql:
            return NEWEST
        if "topic_transcript_link" in sql:
            return [{"state_code": "TX", "state": "Texas", "meetings": 3}, {"state_code": "WI", "state": "Wisconsin", "meetings": 1}]
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


@pytest.fixture
def get(monkeypatch):
    def _get(conn: _Conn) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(topics, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(topics.router)

        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
                return await c.get("/api/topics/100001/states")

        return asyncio.run(go())

    return _get


def test_newest_carries_the_speaker_when_the_recording_names_them(get):
    r = get(_Conn([{"topic_transcript_link_id": "t1", "speaker_kind": "resident",
                    "speaker_display_name": "Jane D.", "speaker_role": "Resident"}]))
    assert r.status_code == 200
    by = {n["video_id"]: n for n in r.json()["newest"]}
    assert by["v1"]["speaker_display_name"] == "Jane D." and by["v1"]["speaker_role"] == "Resident"
    assert by["v2"]["speaker_display_name"] is None and by["v2"]["speaker_role"] is None


def test_missing_speaker_table_leaves_speakers_null(get):
    r = get(_Conn(None, error=True))
    assert r.status_code == 200
    assert all(n["speaker_display_name"] is None for n in r.json()["newest"])


def test_a_resident_full_name_is_cut_to_first_l_again():
    assert topics.speaker_fields({"speaker_kind": "resident", "speaker_display_name": "Jane Doe",
                                  "speaker_role": None}) == ("Jane D.", None)
    assert topics.speaker_fields({"speaker_kind": "resident", "speaker_display_name": "Jane D."})[0] == "Jane D."
    assert topics.speaker_fields({"speaker_kind": "resident", "speaker_display_name": "Jane"})[0] == "Jane"


def test_an_official_keeps_name_and_title():
    assert topics.speaker_fields({"speaker_kind": "official", "speaker_display_name": "Walt Maddox",
                                  "speaker_role": "Mayor"}) == ("Walt Maddox", "Mayor")


def test_no_name_means_no_role():
    assert topics.speaker_fields({"speaker_kind": "suppressed", "speaker_display_name": None,
                                  "speaker_role": "Resident"}) == (None, None)
    assert topics.speaker_fields(None) == (None, None)


def test_speaker_sql_reads_display_form_only():
    sql = topics._PASSAGE_SPEAKER_SQL
    assert "speaker_display_name IS NOT NULL" in sql and "name_tokens" not in sql


class _MentionConn:
    def __init__(self, intro_rows):
        self.intro_rows = intro_rows

    async def fetch(self, sql: str, *params: Any):
        if "meeting_passage_speaker" in sql:
            return [r for r in self.intro_rows if r["data_center_meeting_mention_id"] in params[0]]
        return []


def _mention_rows():
    return [{"data_center_meeting_mention_id": "m1", "video_id": "v1"},
            {"data_center_meeting_mention_id": "m2", "video_id": "v2"},
            {"data_center_meeting_mention_id": "m3", "video_id": "v3"}]


def test_mentions_fall_back_to_self_introductions():
    rows = _mention_rows()
    conn = _MentionConn([
        {"data_center_meeting_mention_id": "m1", "speaker_kind": "resident", "speaker_display_name": "Sam Lee",
         "speaker_role": "Resident"},
        {"data_center_meeting_mention_id": "m2", "speaker_kind": "official", "speaker_display_name": "Walt Maddox",
         "speaker_role": "Mayor"},
    ])
    asyncio.run(data_centers._mention_extras(conn, rows))
    by = {r["data_center_meeting_mention_id"]: r for r in rows}
    assert by["m1"]["speaker_display_name"] == "Sam L." and by["m1"]["speaker_role"] == "Resident"
    assert by["m2"]["speaker_display_name"] == "Walt Maddox" and by["m2"]["speaker_role"] == "Mayor"
    assert "speaker_display_name" not in by["m3"]


def test_mentions_survive_a_missing_speaker_table():
    class _Err(_MentionConn):
        async def fetch(self, sql: str, *params: Any):
            if "meeting_passage_speaker" in sql:
                raise asyncpg.exceptions.UndefinedTableError("missing")
            return []

    rows = _mention_rows()
    asyncio.run(data_centers._mention_extras(_Err([]), rows))
    assert all("speaker_display_name" not in r for r in rows)
