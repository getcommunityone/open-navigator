from scrapers.youtube.channel_type_normalize import normalize_channel_type
from scrapers.youtube.backfill_channel_from_api import _iso_duration_minutes


def test_normalize_channel_type_aliases():
    assert normalize_channel_type("municipality") == "municipal"
    assert normalize_channel_type("municipal") == "municipal"
    assert normalize_channel_type("CITY") == "municipal"
    assert normalize_channel_type("county") == "county"
    assert normalize_channel_type("unknown") == "unknown"
    assert normalize_channel_type(None) == "unknown"
    assert normalize_channel_type("weird") == "unknown"


def test_iso_duration_minutes():
    assert _iso_duration_minutes("PT1H30M5S") == 91
    assert _iso_duration_minutes("PT45M") == 45
    assert _iso_duration_minutes("PT2H") == 120
    assert _iso_duration_minutes(None) is None
