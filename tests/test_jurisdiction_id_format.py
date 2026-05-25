"""Canonical jurisdiction_id: {place_slug}_{geoid}."""

from scripts.jurisdictions.jurisdiction_id import (
    jurisdiction_id_from_name_geoid,
    jurisdiction_pk_from_geoid,
    parse_jurisdiction_id,
    place_slug_for_jurisdiction_id,
    resolve_canonical_jurisdiction_id,
)


def test_andalusia_municipality_id():
    assert jurisdiction_id_from_name_geoid("Andalusia city", "0101708") == "andalusia_0101708"


def test_mobile_county_id():
    assert jurisdiction_id_from_name_geoid("Mobile County", "01097", jurisdiction_type="county") == "mobile_01097"


def test_jurisdiction_pk_from_bronze_geoid_lookup():
    from scripts.jurisdictions.jurisdiction_id import (
        lookup_canonical_jurisdiction_id_from_bronze,
    )

    canonical = lookup_canonical_jurisdiction_id_from_bronze("0177256", "municipality")
    if canonical:
        assert canonical == "tuscaloosa_0177256"


def test_jurisdiction_pk_with_name():
    assert (
        jurisdiction_pk_from_geoid("0101708", "municipality", name="Andalusia city")
        == "andalusia_0101708"
    )


def test_parse_legacy_typed_id():
    jt, geoid, slug = parse_jurisdiction_id("municipality_0101708")
    assert jt == "municipality"
    assert geoid == "0101708"


def test_parse_canonical_id():
    jt, geoid, slug = parse_jurisdiction_id("andalusia_0101708")
    assert geoid == "0101708"
    assert slug == "andalusia"
    assert jt == "municipality"


def test_resolve_legacy_to_canonical():
    assert (
        resolve_canonical_jurisdiction_id("municipality_0101708", name="Andalusia city")
        == "andalusia_0101708"
    )


def test_place_slug_strips_city_suffix():
    assert place_slug_for_jurisdiction_id("Abbeville\u00a0city") == "abbeville"


def test_extract_channel_id_from_subscribe_endpoint_html():
    from scripts.datasources.youtube.load_youtube_events_to_postgres import (
        YouTubeEventsLoader,
    )

    snippet = (
        '"subscribeEndpoint":{"channelIds":["UCeV9EK3GqBVa6tgCjpIzXlA"],'
        '"channelId":"UCeV9EK3GqBVa6tgCjpIzXlA"}'
    )
    assert (
        YouTubeEventsLoader._extract_channel_id_from_youtube_html(snippet)
        == "UCeV9EK3GqBVa6tgCjpIzXlA"
    )
