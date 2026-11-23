"""#778: a re-crawl by another town on a shared channel does not take over videos.

Pure: no database. The ON CONFLICT behaviour itself was checked against Postgres on a
rolled-back temp table (see PR); here we pin the parameter and the SQL fragment.
"""

from __future__ import annotations

from scrapers.youtube import load_youtube_events_to_postgres as mod


def _event(title: str, name: str | None, jid: str = "winfield_0182992") -> dict:
    return {"video_id": "v1", "title": title, "jurisdiction_id": jid,
            "jurisdiction_name": name, "jurisdiction_type": "municipality"}


def test_title_naming_the_town_claims_it():
    assert mod.event_title_names_its_jurisdiction(
        _event("Hamilton City Council Meeting 02/22/2021", "Hamilton", "hamilton_0132848"))


def test_neutral_or_other_town_title_does_not_claim():
    assert not mod.event_title_names_its_jurisdiction(_event("Bear Creek Christmas Parade 12/11/2020", "Marion"))
    assert not mod.event_title_names_its_jurisdiction(_event("Hamilton City Council Meeting 02/22/2021", "Winfield"))
    assert not mod.event_title_names_its_jurisdiction(_event("Winfield City Council Meeting", None))


def test_keep_rule_compares_geoid_suffix_and_title_flag():
    sql = mod._KEEP_OTHER_PLACE_SQL
    assert "substring(y.jurisdiction_id from '[0-9]+$')" in sql
    assert "%(title_names_jurisdiction)s" in sql


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
    assert params["title_names_jurisdiction"] is True
    for col in ("jurisdiction_id", "jurisdiction_name", "jurisdiction_type", "state_code", "state", "city"):
        assert f"{col} = CASE WHEN {mod._KEEP_OTHER_PLACE_SQL} THEN y.{col}" in query
