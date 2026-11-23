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


def test_loader_split_drops_hamilton_meetings_from_winfield():
    videos = [{"title": t} for t in (HAMILTON_MEETING, HAMILTON_WORK, WINFIELD_MEETING, WINFIELD_ZOOM, PARADE)]
    kept, skipped = split_videos_naming_other_government(
        videos, jurisdiction_name="Winfield", jurisdiction_type="municipality", state_code="AL"
    )
    assert [v["title"] for v in kept] == [WINFIELD_MEETING, WINFIELD_ZOOM, PARADE]
    assert [(v["title"], r) for v, r in skipped] == [
        (HAMILTON_MEETING, "names_other_city"),
        (HAMILTON_WORK, "names_other_city"),
    ]


def test_loader_split_keeps_hamilton_meetings_for_hamilton():
    kept, skipped = split_videos_naming_other_government(
        [{"title": HAMILTON_MEETING}], jurisdiction_name="Hamilton", jurisdiction_type="municipality", state_code="AL"
    )
    assert kept == [{"title": HAMILTON_MEETING}] and skipped == []


def test_loader_split_skips_county_commission_for_a_town():
    _, skipped = split_videos_naming_other_government(
        [{"title": COUNTY_COMMISSION}], jurisdiction_name="Winfield", jurisdiction_type="municipality", state_code="AL"
    )
    assert skipped and skipped[0][1] == "names_county_government"


def test_loader_split_without_a_name_keeps_everything():
    kept, skipped = split_videos_naming_other_government(
        [{"title": HAMILTON_MEETING}], jurisdiction_name=None, jurisdiction_type="municipality"
    )
    assert len(kept) == 1 and skipped == []


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
