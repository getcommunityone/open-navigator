"""Tests for YouTube channel About-page enrichment."""

from scripts.datasources.jurisdiction_pilot.youtube_channel_enrich import (
    jurisdiction_website_back_links,
)
from scripts.datasources.youtube.youtube_channel_page import (
    extract_channel_title_from_youtube_html,
    fetch_latest_upload_date_from_rss,
    is_junk_channel_title,
)


def test_is_junk_channel_title():
    assert is_junk_channel_title("Home")
    assert is_junk_channel_title("Videos")
    assert not is_junk_channel_title("City of Dothan AL")


def test_extract_channel_title_skips_tab_label():
    html = '''
    "channelMetadataRenderer":{"title":"City of Jasper, Alabama"}
    '''
    assert extract_channel_title_from_youtube_html(html) == "City of Jasper, Alabama"


def test_jurisdiction_website_back_links_from_external_links():
    links = jurisdiction_website_back_links(
        ["http://www.jaspercity.com", "https://www.facebook.com/cityofjasper"],
        "https://www.jaspercity.com",
    )
    assert links == ["http://www.jaspercity.com"]


def test_jurisdiction_website_back_links_from_description_host():
    links = jurisdiction_website_back_links(
        [],
        "https://huntsvilleal.gov",
        description_text="Visit huntsvilleal.gov for more info.",
    )
    assert any("huntsvilleal.gov" in u for u in links)


def test_fetch_latest_upload_from_rss():
    latest = fetch_latest_upload_date_from_rss("UCjQLzllGnzicLNiMMzcLwKQ")
    assert latest
    assert len(latest) == 10
    assert latest[4] == "-"
    assert latest[7] == "-"
