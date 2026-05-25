"""YouTube channel page HTML parsing (shared pilot + loader)."""

from scripts.datasources.youtube.youtube_channel_page import (
    extract_channel_id_from_youtube_html,
    extract_channel_title_from_youtube_html,
)

_SUBSCRIBE_HTML = """
<script>
{"subscribeEndpoint":{"channelIds":["UCeV9EK3GqBVa6tgCjpIzXlA"]}}
</script>
"""


def test_extract_channel_id_from_subscribe_endpoint():
    cid = extract_channel_id_from_youtube_html(_SUBSCRIBE_HTML)
    assert cid == "UCeV9EK3GqBVa6tgCjpIzXlA"


def test_extract_channel_id_from_final_url():
    cid = extract_channel_id_from_youtube_html(
        "",
        final_url="https://www.youtube.com/channel/UCiOI7RWQKqnEuM3AKnWYLuA",
    )
    assert cid == "UCiOI7RWQKqnEuM3AKnWYLuA"


def test_extract_title_from_og_meta():
    html = '<meta property="og:title" content="Baldwin County Government">'
    assert extract_channel_title_from_youtube_html(html) == "Baldwin County Government"
