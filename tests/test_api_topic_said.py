"""People and position on "What was said", and decisions on the topic vs in passing (#1293).

GET /api/topics/{id}/meetings carries who spoke (meeting_passage_speaker, named commenters from meeting_comment) and a
position chip from the most specific real source; GET /api/topics/{id}/decisions splits decisions into "on the topic"
and "mentioned in passing" (api/routes/topic_relevance.py). The DB layer is mocked; rows are test stand-ins, not warehouse
figures, except the two Alabama headlines, which are quoted from the record the owner flagged.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from typing import Any

import httpx
import pytest
from fastapi import FastAPI

from api.routes import search, topics
from api.routes.topic_relevance import TOPIC_RULES, classify_decision


def _row(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "topic_transcript_link_id": "t1", "video_id": "v1", "event_title": "BOC Meeting", "event_date": dt.date(2026, 5, 14),
        "state_code": "GA", "state": "Georgia", "city": None, "jurisdiction_name": "Fayette County",
        "video_url": "https://www.youtube.com/watch?v=v1", "evidence_passage": "the <mark>fluoride</mark> feed system",
        "n_keyword_hits": 1, "public_stance": None, "public_position": None, "vote": None, "speaker_kind": None,
        "speaker_display_name": None, "speaker_role": None, "commenter_count": 0, "commenters": None, "said_rank": 2,
    }
    base.update(kw)
    return base


COUNTS = {"total": 3, "against": 1, "for_": 0, "split": 0, "silent": 2, "unread": 0, "vote_advanced": 1,
          "vote_blocked": 0, "vote_tabled": 0, "with_person": 1, "public_position_meetings": 1, "in_passing": 1}


class _Conn:
    def __init__(self, rows: list[dict[str, Any]], counts: dict[str, Any] | None = None):
        self.rows = rows
        self.counts = counts
        self.calls: list[tuple[str, tuple[Any, ...]]] = []

    async def fetch(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        if "event_meeting e WHERE e.video_id" in sql:
            return [{"video_id": "v2", "event_meeting_id": 42}]
        return self.rows

    async def fetchrow(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return self.counts

    async def fetchval(self, sql: str, *params: Any):
        self.calls.append((sql, params))
        return 3


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
    def _get(conn: Any, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        async def pool():
            return _Pool(conn)

        monkeypatch.setattr(topics, "get_db_pool", pool)
        app = FastAPI()
        app.include_router(topics.router)

        async def go():
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
                return await c.get(path, params=params)

        return asyncio.run(go())

    return _get


# --- /meetings -----------------------------------------------------------------------------------------------------------


def test_meetings_carry_people_position_and_counts(get):
    rows = [
        _row(video_id="v2", topic_transcript_link_id="t2", public_stance="against", public_position="oppose_local_choice",
             speaker_kind="resident", speaker_display_name="Amy Nolan", speaker_role="Resident",
             commenters=["Amy N.", "Tracy B.", "Bob Smith", "Lee K."], commenter_count=4, said_rank=0),
        _row(video_id="v1", public_stance="silent", vote="advanced", said_rank=1),
        _row(video_id="v3", topic_transcript_link_id="t3", public_stance="silent", said_rank=2),
    ]
    conn = _Conn(rows, COUNTS)
    r = get(conn, "/api/topics/100002/meetings", {"state": "ga", "limit": 8, "sort": "people"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 3
    assert body["position_counts"]["against"] == 1 and body["position_counts"]["for"] == 1 - 1
    assert body["position_counts"]["in_passing"] == 1
    a, b, c = body["items"]
    # The meeting's public position, in the five-position words where they agree with the side; a resident is First L.
    assert a["position"] == "oppose_local_choice" and a["position_source"] == "meeting"
    assert a["speaker_display_name"] == "Amy N." and a["speaker_role"] == "Resident"
    # The speaker is not repeated among the commenters; a full name is cut to First L.; at most 3 names.
    assert a["commenters"] == ["Tracy B.", "Bob S.", "Lee K."] and a["commenter_count"] == 3
    assert a["meeting_url"] == "/meetings/42" and a["in_passing"] is False
    # No public side: the body's action is the chip.
    assert b["position"] == "advanced" and b["position_source"] == "vote" and b["public_stance"] == "silent"
    # Nothing on record: no chip, no person, under "Mentioned in passing".
    assert c["position"] is None and c["position_source"] is None and c["speaker_display_name"] is None
    assert c["in_passing"] is True
    sql, params = next((s, p) for s, p in conn.calls if "LIMIT $4" in s)
    assert params == (100002, "GA", None, 8, 0, "people")
    assert "possible_minor" in sql and "is_public_comment" in sql and "school_district" in sql


def test_unknown_sort_is_newest():
    conn = _Conn([], COUNTS)

    async def go():
        async def pool():
            return _Pool(conn)

        topics.get_db_pool, old = pool, topics.get_db_pool  # type: ignore[assignment]
        try:
            return await topics.list_topic_meetings(topic_id=1, state=None, city=None, limit=5, offset=0, sort="drop table")
        finally:
            topics.get_db_pool = old  # type: ignore[assignment]

    asyncio.run(go())
    _, params = next((s, p) for s, p in conn.calls if "LIMIT $4" in s)
    assert params[-1] == "newest"


def test_later_pages_skip_the_counts(get):
    conn = _Conn([_row()], COUNTS)
    body = get(conn, "/api/topics/100002/meetings", {"offset": 8}).json()
    assert body["position_counts"] is None and body["total"] == 3
    assert not any("count(*) FILTER" in s for s, _ in conn.calls)


@pytest.mark.parametrize(
    ("stance", "five", "vote", "want"),
    [
        ("against", "oppose_ban_all", None, ("oppose_ban_all", "meeting", "oppose_ban_all")),
        # A five-position reading on the other side never overrides the lean (the chip must match the counts).
        ("against", "support_local_choice", None, ("against", "meeting", None)),
        ("for", None, "blocked", ("for", "meeting", None)),
        ("split", "oppose_local_choice", None, ("split", "meeting", None)),
        ("silent", None, "tabled_or_deferred", ("tabled_or_deferred", "vote", None)),
        ("silent", None, "discussed_no_action", (None, None, None)),
        (None, None, None, (None, None, None)),
    ],
)
def test_said_position_takes_the_most_specific_real_source(stance, five, vote, want):
    assert topics.said_position(stance, five, vote) == want


# --- /decisions ----------------------------------------------------------------------------------------------------------

# Quoted from the record the owner flagged on /stories/guns?state=AL (Shelby County and Wetumpka).
SHELBY = (
    "Capital Improvement Plan Funds Reallocated from Firearms Training Project",
    (
        "The commission sent down without recommendation the reallocation of $350,000 from the firearms training unit "
        "BURM reclamation project to emergency backup generators."
    ),
)
WETUMPKA = (
    "Firearms Sale Permit Granted to Dunham's Athleisure Corporation",
    "Permission is granted for Dunham's Athleisure Corporation to sell firearms at 4896 US Highway 231.",
)


def test_shelby_budget_move_is_in_passing_even_if_the_body_acted():
    rel, basis = classify_decision("guns", *SHELBY, public_stance="against", vote="blocked")
    assert rel == "in_passing" and "training" in basis


def test_wetumpka_sale_permit_is_in_passing_without_a_public_side():
    assert classify_decision("guns", *WETUMPKA)[0] == "in_passing"
    # The body approving a store's permit is not enough: nobody debated a limit on firearms.
    assert classify_decision("guns", *WETUMPKA, vote="blocked")[0] == "in_passing"
    # Residents taking a side on it at that meeting is the evidence that makes it a gun-control decision.
    assert classify_decision("guns", *WETUMPKA, public_stance="for")[0] == "on_topic"


@pytest.mark.parametrize(
    "headline",
    [
        "Prohibiting felons from possessing firearms",
        "Village Board Adopts Resolution on Gun Violence calling for action on assault weapons",
        "Second Amendment sanctuary resolution adopted",
        "Rezoning for shooting range receives unfavorable recommendation",
    ],
)
def test_named_gun_policy_is_on_topic(headline):
    assert classify_decision("guns", headline, None)[0] == "on_topic"


def test_passive_mention_of_prohibited_people_is_not_a_policy():
    rel, _ = classify_decision(
        "guns", "Updating the Law Enforcement Tactical System",
        "a database of individuals prohibited from possessing firearms",
    )
    assert rel == "in_passing"


def test_unknown_topic_needs_the_meeting_reading():
    assert classify_decision("violent-crime", "Homicide unit budget", None)[0] == "in_passing"
    assert classify_decision("violent-crime", "Homicide unit budget", None, vote="advanced")[0] == "on_topic"


def test_every_rule_compiles():
    for rules in TOPIC_RULES.values():
        for kind in ("on", "off", "needs_reading"):
            rules.match(kind, "x")


def test_decisions_endpoint_splits_and_links(get, monkeypatch):
    async def tsq(_topic_id: int) -> str:
        return "firearm | firearms"

    monkeypatch.setattr(search, "resolve_topic_tsquery", tsq)
    rows = [
        {"event_decision_id": "d1", "headline": SHELBY[0], "decision_statement": SHELBY[1], "outcome": "Sent down",
         "jurisdiction_name": "Shelby County", "state_code": "AL", "state": "Alabama", "event_meeting_id": 7,
         "body_name": "Shelby County Commission", "video_id": "abcdefghijk", "meeting_date": "2026-04-08",
         "excerpt": "from the <mark>firearms</mark> training unit"},
        {"event_decision_id": "d2", "headline": "Prohibiting felons from possessing firearms", "decision_statement": None,
         "competing_views": '{"dominant_view": {"held_by": ["lee_busby_councilor_tuscaloosa", "scott_holmes_unknown_tuscaloosa"]}, "counter_views": []}',
         "vote_tally": '{"yes": 7, "no": 0}', "speaker_ids": None, "jurisdiction_type": "city",
         "outcome": "Supported", "jurisdiction_name": "Tuscaloosa", "state_code": "AL", "state": "Alabama",
         "event_meeting_id": None, "body_name": None, "video_id": None, "meeting_date": None, "excerpt": None},
    ]

    class _DConn(_Conn):
        async def fetchval(self, sql: str, *params: Any):
            return "guns"

        async def fetch(self, sql: str, *params: Any):
            self.calls.append((sql, params))
            return [] if "topic_meeting_lean" in sql else self.rows

    conn = _DConn(rows)
    r = get(conn, "/api/topics/100005/decisions", {"state": "al"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["total"], body["on_topic_total"], body["in_passing_total"]) == (2, 1, 1)
    on, = body["on_topic"]
    off, = body["in_passing"]
    assert on["event_decision_id"] == "d2" and on["decision_url"] == "/decisions/d2" and on["meeting_url"] is None
    # #1320: who supported it (an official by name and title, a resident First L.), no opposition recorded, the vote.
    assert on["supported_by"] == [{"name": "Lee Busby", "role": "Councilor", "kind": "official"},
                                  {"name": "Scott H.", "role": None, "kind": "resident"}]
    assert on["opposition_recorded"] is False and (on["vote_yes"], on["vote_no"]) == (7, 0)
    assert off["supported_by"] == [] and off["opposition_recorded"] is None
    assert off["meeting_url"] == "/meetings/7" and off["video_url"] == "https://www.youtube.com/watch?v=abcdefghijk"
    assert off["meeting_name"] == "Shelby County Commission" and off["meeting_date"] == "2026-04-08"
    assert conn.calls[0][1] == ("firearm | firearms", "AL", None)
