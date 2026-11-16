"""/user/ and /c/ channel URLs resolve from the channel page (494 homepage-linked
channels use them; the catalog used to skip every one)."""

from __future__ import annotations

from scrapers.youtube.load_youtube_events_to_postgres import YouTubeEventsLoader


def _loader(seen):
    loader = YouTubeEventsLoader.__new__(YouTubeEventsLoader)

    def fake_page(base_url, label):
        seen.append((base_url, label))
        return "UCr-5eqw0JKW4LKl8xmWNAdw"

    loader._resolve_channel_page_html = fake_page
    return loader


def test_user_and_c_urls_resolve_from_the_page():
    seen: list = []
    loader = _loader(seen)
    cid, url = loader.resolve_channel_id_from_url("https://www.youtube.com/user/SussexCountyDelaware")
    assert cid == "UCr-5eqw0JKW4LKl8xmWNAdw" and url.endswith("/channel/UCr-5eqw0JKW4LKl8xmWNAdw")
    loader.resolve_channel_id_from_url("http://youtube.com/c/CityofX/videos?view=0")
    assert seen == [
        ("https://www.youtube.com/user/SussexCountyDelaware", "/user/SussexCountyDelaware"),
        ("https://www.youtube.com/c/CityofX", "/c/CityofX"),
    ]


def test_channel_urls_need_no_lookup():
    seen: list = []
    cid, _ = _loader(seen).resolve_channel_id_from_url("https://www.youtube.com/channel/UCabcdefghijklmnopqrstuv")
    assert cid == "UCabcdefghijklmnopqrstuv" and seen == []
