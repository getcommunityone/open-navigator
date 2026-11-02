from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import ingestion.municipal_generic as municipal_generic
from api.auth import require_auth
from api.database import get_db
from api.main import app
from api.models import ProximityAlert, User
from ingestion.municipal_generic import (
    AsyncMunicipalClient,
    RawMunicipalMeeting,
    load_to_bronze,
    transform_to_standard_model,
)
from models.meeting_event import Classification, EventStatus
from models.proximity_alert import ProximityAlertCreate


@pytest.fixture()
def auth_db_client():
    """Provide a TestClient with isolated auth and DB dependency overrides."""
    db_mock = MagicMock()
    db_mock.execute.return_value = []

    def _assign_id_on_flush():
        if db_mock.add.call_args:
            added_obj = db_mock.add.call_args[0][0]
            if isinstance(added_obj, ProximityAlert) and added_obj.id is None:
                added_obj.id = 42

    db_mock.flush.side_effect = _assign_id_on_flush

    app.dependency_overrides[require_auth] = lambda: User(user_id=1, email="test@example.com")
    app.dependency_overrides[get_db] = lambda: (yield db_mock)
    try:
        yield TestClient(app), db_mock
    finally:
        app.dependency_overrides.pop(require_auth, None)
        app.dependency_overrides.pop(get_db, None)


def test_proximity_alert_schema():
    """Validate ProximityAlertCreate bounds and field constraints."""
    alert = ProximityAlertCreate(
        alert_name="My Local Venues",
        target_radius_meters=10000.0,
        latitude=34.05,
        longitude=-118.25,
    )
    assert alert.alert_name == "My Local Venues"
    assert alert.target_radius_meters == 10000.0

    with pytest.raises(ValidationError):
        ProximityAlertCreate(
            alert_name="Too Small Radius",
            target_radius_meters=50.0,
            latitude=34.05,
            longitude=-118.25,
        )

    with pytest.raises(ValidationError):
        ProximityAlertCreate(
            alert_name="Out of Bounds Latitude",
            target_radius_meters=1000.0,
            latitude=95.0,
            longitude=-118.25,
        )


def test_create_proximity_alert_route(auth_db_client):
    """Verify POST /api/alerts/proximity persists alert and executes CTE Haversine query."""
    client, db_mock = auth_db_client
    mock_row = MagicMock()
    mock_row._mapping = {
        "id": "ep_1",
        "name": "100 City Hall Plaza",
        "latitude": 40.7130,
        "longitude": -74.0055,
        "jurisdiction_name": "New York",
        "city": "New York",
        "state_code": "NY",
        "distance": 45.2,
    }
    db_mock.execute.return_value = [mock_row]

    response = client.post(
        "/api/alerts/proximity",
        json={
            "alert_name": "Test Alert",
            "target_radius_meters": 5000.0,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "is_active": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "created"
    assert data["alert_id"] == 42
    assert data["nearby_municipal_items_found"] == 1
    assert data["items"][0]["id"] == "ep_1"

    assert db_mock.add.called
    assert db_mock.flush.called
    assert db_mock.execute.called
    assert db_mock.commit.called
    assert db_mock.refresh.called

    executed_sql = str(db_mock.execute.call_args[0][0])
    assert "WITH scored_places AS" in executed_sql
    assert "FROM event_place_geocoded" in executed_sql
    assert "LEAST(1.0, GREATEST(-1.0," in executed_sql


def test_create_proximity_alert_requires_auth():
    """Verify POST /api/alerts/proximity rejects unauthenticated requests."""
    unauth_client = TestClient(app)
    response = unauth_client.post(
        "/api/alerts/proximity",
        json={
            "alert_name": "Unauth Alert",
            "target_radius_meters": 5000.0,
            "latitude": 40.7128,
            "longitude": -74.0060,
        },
    )
    assert response.status_code == 401


def test_municipal_transform_preserves_null_location_and_writes_parquet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Ensure missing location_name stays None (never 'Unknown') through Parquet write."""
    monkeypatch.setattr(municipal_generic, "_BRONZE_DIR", tmp_path)

    raw = RawMunicipalMeeting(
        id="mtg-101",
        title="  City Council Regular Meeting  ",
        meeting_date=datetime(2026, 5, 10, 18, 0, tzinfo=timezone.utc),
        agenda_html="/agendas/101.pdf",
        status="confirmed",
        location_name=None,
        video_url="https://example.gov/video/101",
    )
    assert raw.title == "City Council Regular Meeting"

    event = transform_to_standard_model(
        raw=raw,
        municipality="Westfield",
        state="IN",
        base_url="https://mock.westfield.in.gov",
    )
    assert event.classification == Classification.COUNCIL
    assert event.status == EventStatus.CONFIRMED
    assert event.location.name is None
    assert str(event.location) == "Westfield, IN"
    assert event.has_agenda()
    assert event.has_video()

    parquet_path = load_to_bronze([event], state="IN", municipality="Westfield")
    assert parquet_path.exists()
    df = pd.read_parquet(parquet_path)
    assert len(df) == 1
    assert pd.isna(df.loc[0, "location_name"])
    assert df.loc[0, "jurisdiction_name"] == "Westfield"
    assert df.loc[0, "state_code"] == "IN"


@pytest.mark.asyncio
async def test_municipal_client_does_not_retry_404():
    """Ensure permanent 4xx errors fail immediately without retry backoff."""
    client = AsyncMunicipalClient(base_url="https://mock.westfield.in.gov", requests_per_second=100.0)
    try:
        req = httpx.Request("GET", "https://mock.westfield.in.gov/api/meetings")
        resp_404 = httpx.Response(404, request=req)
        client.client.get = AsyncMock(return_value=resp_404)

        with pytest.raises(httpx.HTTPStatusError):
            await client._fetch_with_retry("/api/meetings")

        assert client.client.get.await_count == 1
    finally:
        await client.close()
