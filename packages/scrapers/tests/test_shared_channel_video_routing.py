"""#777: a shared channel's videos are filed under the government their title names.

Verbatim titles from bronze.bronze_event_youtube, channel UCZ47nYYggC17NbmBs0Mx3Ww
("49 County News.Net"), which LocalView links to seven Marion County, AL towns.
Pure: no network, no database.
"""

from __future__ import annotations

from scrapers.discovery.channel_government_mismatch import (
    pick_named_sibling,
    split_videos_naming_other_government,
    title_names_jurisdiction,
)
from scrapers.youtube.reassign_shared_channel_videos import plan_moves

CHANNEL = "UCZ47nYYggC17NbmBs0Mx3Ww"
HAMILTON_MEETING = "Hamilton City Council Meeting 02/22/2021"
HAMILTON_WORK = "Hamilton City Council Work Session 04/13/2021"
WINFIELD_MEETING = "Winfield City Council Meeting 04/02/2019"
WINFIELD_ZOOM = "Winfield City Council Meeting - Zoom Meeting - 04/09/2020"
COUNTY_COMMISSION = "Marion County Commissioners Work Session 08/08/2019"
PARADE = "Bear Creek Christmas Parade 12/11/2020"

SIBLINGS = [
    {"jurisdiction_id": jid, "name": name, "jurisdiction_type": "municipality", "state_code": "AL"}
    for jid, name in [
        ("winfield_0182992", "Winfield"),
        ("hamilton_0132848", "Hamilton"),
        ("guin_0132224", "Guin"),
        ("marion_0146768", "Marion"),
        ("bear_creek_0104852", "Bear Creek"),
    ]
]


def _others(own: str) -> list[dict]:
    return [s for s in SIBLINGS if s["jurisdiction_id"] != own]


def test_loader_split_drops_hamilton_meetings_from_winfield():
    videos = [{"title": t} for t in (HAMILTON_MEETING, HAMILTON_WORK, WINFIELD_MEETING, WINFIELD_ZOOM, PARADE)]
    kept, skipped = split_videos_naming_other_government(
        videos, jurisdiction_name="Winfield", jurisdiction_type="municipality", state_code="AL",
        siblings=_others("winfield_0182992"),
    )
    assert [v["title"] for v in kept] == [WINFIELD_MEETING, WINFIELD_ZOOM, PARADE]
    assert [(v["title"], to) for v, to in skipped] == [
        (HAMILTON_MEETING, "hamilton_0132848"),
        (HAMILTON_WORK, "hamilton_0132848"),
    ]


def test_loader_split_keeps_hamilton_meetings_for_hamilton():
    kept, skipped = split_videos_naming_other_government(
        [{"title": HAMILTON_MEETING}], jurisdiction_name="Hamilton", jurisdiction_type="municipality",
        state_code="AL", siblings=_others("hamilton_0132848"),
    )
    assert kept == [{"title": HAMILTON_MEETING}] and skipped == []


def test_loader_split_keeps_a_government_not_linked_to_the_channel():
    # Marion County is not linked to the channel, so its commission meetings stay put
    # rather than being dropped for good (a city channel posting county meetings).
    kept, skipped = split_videos_naming_other_government(
        [{"title": COUNTY_COMMISSION}], jurisdiction_name="Winfield", jurisdiction_type="municipality",
        state_code="AL", siblings=_others("winfield_0182992"),
    )
    assert len(kept) == 1 and skipped == []


def test_loader_split_single_jurisdiction_channel_keeps_everything():
    kept, skipped = split_videos_naming_other_government(
        [{"title": HAMILTON_MEETING}, {"title": "Tuscaloosa County Commission Meeting"}],
        jurisdiction_name="Winfield", jurisdiction_type="municipality", state_code="AL", siblings=[],
    )
    assert len(kept) == 2 and skipped == []


def test_loader_split_without_a_name_keeps_everything():
    kept, skipped = split_videos_naming_other_government(
        [{"title": HAMILTON_MEETING}], jurisdiction_name=None, jurisdiction_type="municipality",
        siblings=_others("winfield_0182992"),
    )
    assert len(kept) == 1 and skipped == []


def test_process_jurisdiction_files_only_winfield_videos(monkeypatch):
    """Wiring: the loader's refresh path applies the guard before inserting."""
    from scrapers.youtube import load_youtube_events_to_postgres as mod

    loader = object.__new__(mod.YouTubeEventsLoader)
    loader.force_full_fetch = True
    loader.days_lookback = None
    loader.max_videos = 50
    loader.min_duration_seconds = 0
    videos = [
        {"video_id": "p1hBIWUhGtM", "title": HAMILTON_MEETING, "published_at": "2021-02-23T00:00:00Z"},
        {"video_id": "1MLG-iGtIT8", "title": WINFIELD_MEETING, "published_at": "2019-04-03T00:00:00Z"},
    ]
    loader.scraper = type("S", (), {"get_channel_videos": staticmethod(lambda **kw: list(videos))})()
    monkeypatch.setattr(loader, "is_channel_flagged", lambda cid: (False, ""), raising=False)
    monkeypatch.setattr(loader, "upsert_channel", lambda **kw: None, raising=False)
    monkeypatch.setattr(loader, "channel_sibling_jurisdictions", lambda c, j: _others("winfield_0182992"),
                        raising=False)
    inserted: list[dict] = []
    monkeypatch.setattr(loader, "insert_events", lambda events: inserted.extend(events) or len(events),
                        raising=False)
    loader.process_jurisdiction({
        "jurisdiction_id": "winfield_0182992", "jurisdiction_name": "Winfield", "state_code": "AL",
        "state": "Alabama", "jurisdiction_type": "municipality",
        "youtube_channels": [{"channel_id": CHANNEL, "channel_title": "49 County News.Net"}],
    })
    assert [e["video_id"] for e in inserted] == ["1MLG-iGtIT8"]


def test_title_names_jurisdiction():
    assert title_names_jurisdiction(HAMILTON_MEETING, jurisdiction_name="Hamilton", jurisdiction_type="municipality")
    assert not title_names_jurisdiction(HAMILTON_MEETING, jurisdiction_name="Winfield", jurisdiction_type="municipality")
    assert not title_names_jurisdiction(PARADE, jurisdiction_name="Bear Creek", jurisdiction_type="municipality")


def test_pick_named_sibling():
    assert pick_named_sibling(HAMILTON_MEETING, SIBLINGS)["jurisdiction_id"] == "hamilton_0132848"
    assert pick_named_sibling(PARADE, SIBLINGS) is None  # names no government
    assert pick_named_sibling(COUNTY_COMMISSION, SIBLINGS) is None  # county is not a sibling


def test_plan_moves_hamilton_out_of_winfield_and_leaves_the_rest():
    videos = [
        {"video_id": "p1hBIWUhGtM", "channel_id": CHANNEL, "jurisdiction_id": "winfield_0182992",
         "title": HAMILTON_MEETING, "analyzed": False},
        {"video_id": "1MLG-iGtIT8", "channel_id": CHANNEL, "jurisdiction_id": "winfield_0182992",
         "title": WINFIELD_MEETING, "analyzed": False},
        {"video_id": "parade", "channel_id": CHANNEL, "jurisdiction_id": "marion_0146768",
         "title": PARADE, "analyzed": False},
        {"video_id": "county", "channel_id": CHANNEL, "jurisdiction_id": "winfield_0182992",
         "title": COUNTY_COMMISSION, "analyzed": True},
    ]
    planned = {p.video_id: p for p in plan_moves(videos, {CHANNEL: SIBLINGS})}
    assert set(planned) == {"p1hBIWUhGtM", "county"}
    move = planned["p1hBIWUhGtM"]
    assert (move.action, move.from_jurisdiction_id, move.to_jurisdiction_id, move.to_name) == (
        "move", "winfield_0182992", "hamilton_0132848", "Hamilton"
    )
    assert planned["county"].action == "unresolved" and planned["county"].to_jurisdiction_id is None
    assert move.to_jurisdiction_type == "municipality"
