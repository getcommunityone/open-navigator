from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

import api.routes.feed as feed_module
from api.auth import get_current_user
from api.database import get_db
from api.main import app
from api.models import User
from api.routes.feed import LocationIn, _derive_state_code, _extract_primary_city


def test_derive_state_code_supports_iso_abbr_and_full_name():
    """Verify _derive_state_code resolves ISO3166-2-lvl4, 2-letter codes, and full names."""
    assert _derive_state_code({"ISO3166-2-lvl4": "US-AL", "state": "Alabama"}) == "AL"
    assert _derive_state_code({"state": "IN"}) == "IN"
    assert _derive_state_code({"state": "Indiana"}) == "IN"
    assert _derive_state_code({"state": "District of Columbia"}) == "DC"
    assert _derive_state_code({"state": "UnknownPlace"}) is None


def test_extract_primary_city_handles_explicit_city_and_verbose_display_name():
    """Verify _extract_primary_city prefers explicit city and strips verbose display_name suffixes."""
    loc_explicit = LocationIn(
        name="Tuscaloosa, Tuscaloosa County, Alabama, 35401, United States",
        city="Tuscaloosa",
        state_code="AL",
    )
    assert _extract_primary_city(loc_explicit) == "Tuscaloosa"

    loc_short = LocationIn(name="Westfield, IN", state_code="IN")
    assert _extract_primary_city(loc_short) == "Westfield"

    loc_verbose = LocationIn(
        name="Birmingham, Jefferson County, Alabama, United States",
        state_code="AL",
    )
    assert _extract_primary_city(loc_verbose) == "Birmingham"


def test_feed_places_zip_uses_postalcode_and_reverse_centroid(monkeypatch: pytest.MonkeyPatch):
    """Verify 5-digit ZIP lookup uses structured postalcode and reverse-geocodes centroid when city is omitted."""
    calls: list[tuple[str, dict[str, str]]] = []

    async def fake_throttled_get(path: str, params: dict[str, str]):
        calls.append((path, params))
        if path == "/search" and params.get("postalcode") == "35401":
            return [
                {
                    "lat": "33.2098",
                    "lon": "-87.5692",
                    "display_name": "35401, Tuscaloosa County, Alabama, United States",
                    "address": {
                        "postcode": "35401",
                        "county": "Tuscaloosa County",
                        "state": "Alabama",
                    },
                }
            ]
        if path == "/reverse":
            return {
                "lat": "33.2098",
                "lon": "-87.5692",
                "display_name": "Tuscaloosa, Tuscaloosa County, Alabama, 35401, United States",
                "address": {
                    "city": "Tuscaloosa",
                    "county": "Tuscaloosa County",
                    "state": "Alabama",
                    "ISO3166-2-lvl4": "US-AL",
                    "postcode": "35401",
                },
            }
        return []

    monkeypatch.setattr(feed_module, "_throttled_get", fake_throttled_get)
    client = TestClient(app)

    response = client.get("/api/feed/places", params={"q": "35401-1234"})
    assert response.status_code == 200
    data = response.json()

    # Should have called /search with postalcode=35401 and /reverse for the centroid
    assert calls[0][0] == "/search"
    assert calls[0][1]["postalcode"] == "35401"
    assert calls[1][0] == "/reverse"

    # Both the city-resolved hit and the unincorporated county-level hit are returned
    results = data["results"]
    assert len(results) == 2
    assert results[0]["city"] == "Tuscaloosa"
    assert results[0]["county"] == "Tuscaloosa County"
    assert results[0]["state_code"] == "AL"
    assert results[0]["postal_code"] == "35401"
    assert results[1]["city"] is None
    assert results[1]["county"] == "Tuscaloosa County"
    assert results[1]["state_code"] == "AL"


def test_feed_places_deduplicates_identical_municipality_hits(monkeypatch: pytest.MonkeyPatch):
    """Verify duplicate Nominatim items for the same (city, county, state_code) collapse to one PlaceHit."""
    mock_get = AsyncMock(
        return_value=[
            {
                "lat": "40.0428",
                "lon": "-86.1275",
                "display_name": "Westfield, Hamilton County, Indiana, United States",
                "address": {
                    "city": "Westfield",
                    "county": "Hamilton County",
                    "state": "Indiana",
                    "ISO3166-2-lvl4": "US-IN",
                },
            },
            {
                "lat": "40.0430",
                "lon": "-86.1279",
                "display_name": "Westfield, Hamilton County, Indiana, 46074, United States",
                "address": {
                    "town": "Westfield",
                    "county": "Hamilton County",
                    "state": "Indiana",
                },
            },
        ]
    )
    monkeypatch.setattr(feed_module, "_throttled_get", mock_get)
    client = TestClient(app)

    response = client.get("/api/feed/places", params={"q": "Westfield, IN"})
    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["city"] == "Westfield"
    assert results[0]["state_code"] == "IN"


def test_put_feed_config_syncs_clean_user_city_and_state():
    """Verify PUT /api/feed/config syncs clean city, county, and full state name onto User."""
    user = User(user_id=7, email="resident@example.com", profile_completed=False)
    db_mock = MagicMock()
    db_mock.query.return_value.filter.return_value.order_by.return_value.all.return_value = []

    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: (yield db_mock)
    try:
        client = TestClient(app)
        response = client.put(
            "/api/feed/config",
            json={
                "locations": [
                    {
                        "name": "Tuscaloosa, Tuscaloosa County, Alabama, 35401, United States",
                        "city": "Tuscaloosa",
                        "shared_level": "city",
                        "is_primary": True,
                        "state_code": "AL",
                        "county": "Tuscaloosa County",
                        "latitude": 33.2098,
                        "longitude": -87.5692,
                    }
                ],
                "lenses": ["local-economy"],
                "signals": ["money-moves"],
            },
        )
        assert response.status_code == 200
        assert user.city == "Tuscaloosa"
        assert user.county == "Tuscaloosa County"
        assert user.state == "Alabama"
        assert user.profile_completed is True
        assert db_mock.commit.called
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        app.dependency_overrides.pop(get_db, None)
