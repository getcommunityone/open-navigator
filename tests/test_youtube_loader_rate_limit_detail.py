"""Rate-limit error formatting for YouTube events loader."""

from scripts.datasources.youtube.load_youtube_events_to_postgres import YouTubeEventsLoader


def test_rate_limit_detail_strips_prefix_and_video_id():
    exc = Exception(
        "RATE_LIMITED: IP blocked on caption API (video_id=abc123XYZ)"
    )
    assert (
        YouTubeEventsLoader._rate_limit_detail(exc)
        == "IP blocked on caption API"
    )
