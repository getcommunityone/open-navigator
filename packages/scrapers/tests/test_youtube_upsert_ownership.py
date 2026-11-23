"""#778: a re-crawl by another town on a shared channel does not take over videos.

The pure tests pin the parameters and the SQL fragment. ``test_upsert_against_postgres``
runs the real ON CONFLICT on a TEMP copy of bronze.bronze_event_youtube inside a
transaction that is always rolled back; it runs only with OPEN_NAVIGATOR_PG_TESTS=1.
"""

from __future__ import annotations

import inspect
import os
import re

import pytest
from scrapers.youtube import load_youtube_events_to_postgres as mod


def _event(title: str, name: str | None, jid: str = "winfield_0182992", shared: bool = True) -> dict:
    return {"video_id": "v1", "title": title, "jurisdiction_id": jid,
            "jurisdiction_name": name, "jurisdiction_type": "municipality", "shared_channel": shared}


def test_title_naming_the_town_claims_it():
    assert mod.event_title_names_its_jurisdiction(
        _event("Hamilton City Council Meeting 02/22/2021", "Hamilton", "hamilton_0132848"))


def test_neutral_or_other_town_title_does_not_claim():
    assert not mod.event_title_names_its_jurisdiction(_event("Bear Creek Christmas Parade 12/11/2020", "Marion"))
    assert not mod.event_title_names_its_jurisdiction(_event("Hamilton City Council Meeting 02/22/2021", "Winfield"))
    assert not mod.event_title_names_its_jurisdiction(_event("Winfield City Council Meeting", None))


def test_keep_rule_compares_geoid_suffix_and_title_flag():
    sql = mod._KEEP_OTHER_PLACE_SQL
    assert "substring(y.jurisdiction_id from '[0-9]{5,}$')" in sql
    assert "%(title_names_jurisdiction)s" in sql and "%(shared_channel)s" in sql
    assert "!~ '^c-[A-Z]{2}-[0-9]+$'" in sql  # placeholder ids are never kept
    assert "{{" not in sql  # inserted verbatim by str.format: braces must be single


def test_insert_events_passes_title_flag_and_guards_geo_columns():
    executed: list[tuple[str, dict]] = []

    class Cur:
        def execute(self, q, p):
            executed.append((q, p))

        def fetchone(self):
            return (1, 1, "v1")

        def close(self):
            pass

    class Conn:
        def cursor(self):
            return Cur()

        def commit(self):
            pass

        def rollback(self):
            pass

    loader = object.__new__(mod.YouTubeEventsLoader)
    loader.conn = Conn()
    loader.fetch_transcripts = False
    loader.insert_events([_event("Hamilton City Council Meeting", "Hamilton", "hamilton_0132848")])
    query, params = executed[0]
    assert params["title_names_jurisdiction"] is True and params["shared_channel"] is True
    for col in ("jurisdiction_id", "jurisdiction_name", "jurisdiction_type", "state_code", "state", "city"):
        assert f"{col} = CASE WHEN {mod._KEEP_OTHER_PLACE_SQL} THEN y.{col}" in query


@pytest.mark.skipif(os.environ.get("OPEN_NAVIGATOR_PG_TESTS") != "1", reason="needs the local warehouse")
def test_upsert_against_postgres():
    import psycopg2

    src = inspect.getsource(mod.YouTubeEventsLoader.insert_events)
    q = re.search(r'insert_query = """(.*?)"""\.format', src, re.DOTALL).group(1).format(keep=mod._KEEP_OTHER_PLACE_SQL)
    q = q.replace("INSERT INTO bronze.bronze_event_youtube AS y", "INSERT INTO pg_temp.t AS y")
    conn = psycopg2.connect(host="localhost", port=5433, dbname="open_navigator",
                            user=os.environ.get("POSTGRES_USER", "postgres"),
                            password=os.environ.get("POSTGRES_PASSWORD", ""))
    cur = conn.cursor()
    base = {"event_id": 1, "channel_id": "UCZ", "channel_url": None, "description": "", "event_date": None,
                "event_time": None, "published_at": None, "jurisdiction_type": "municipality", "state_code": "AL",
                "state": "Alabama", "location": None, "location_description": None, "meeting_type": "x", "view_count": 1,
                "duration_minutes": 1, "like_count": 0, "language": "en", "channel_type": "unknown", "datasource": "youtube",
                "last_updated": None}

    def up(vid, jid, name, title, shared=True):
        e = {**base, "video_id": vid, "video_url": "u" + vid, "datasource_id": vid, "jurisdiction_id": jid,
             "jurisdiction_name": name, "city": name, "title": title, "shared_channel": shared}
        cur.execute(q, {**e, "title_names_jurisdiction": mod.event_title_names_its_jurisdiction(e)})

    def owner(vid):
        cur.execute("select jurisdiction_id from pg_temp.t where video_id = %s", (vid,))
        return cur.fetchone()[0]

    try:
        cur.execute("CREATE TEMP TABLE t (LIKE bronze.bronze_event_youtube INCLUDING DEFAULTS INCLUDING INDEXES)")
        up("parade", "bear_creek_0104852", "Bear Creek", "Christmas Parade 12/11/2020")
        up("parade", "marion_0146768", "Marion", "Christmas Parade 12/11/2020")
        assert owner("parade") == "bear_creek_0104852"  # neutral title: first place kept
        up("ham", "winfield_0182992", "Winfield", "Hamilton City Council Meeting 02/22/2021")
        up("ham", "hamilton_0132848", "Hamilton", "Hamilton City Council Meeting 02/22/2021")
        assert owner("ham") == "hamilton_0132848"  # title names the refreshing town
        up("ham", "winfield_0182992", "Winfield", "Hamilton City Council Meeting 02/22/2021")
        assert owner("ham") == "hamilton_0132848"
        up("ids", "municipality_0182992", None, "Some video")
        up("ids", "winfield_0182992", "Winfield", "Some video")
        assert owner("ids") == "winfield_0182992"  # same GEOID, id normalized
        up("ph", "c-AL-01125", None, "Some video")
        up("ph", "tuscaloosa_0177256", "Tuscaloosa", "Some video")
        assert owner("ph") == "tuscaloosa_0177256"  # placeholder id is never kept
        up("solo", "bear_creek_0104852", "Bear Creek", "Some video", shared=False)
        up("solo", "marion_0146768", "Marion", "Some video", shared=False)
        assert owner("solo") == "marion_0146768"  # not a shared channel: old behaviour
    finally:
        conn.rollback()
        conn.close()
