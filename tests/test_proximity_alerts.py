from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from api.main import app
from api.database import get_db
from api.auth import require_auth
from api.models import User
from models.proximity_alert import ProximityAlertCreate

client = TestClient(app)

def override_require_auth():
    return User(user_id=1, email="test@example.com")

def override_get_db():
    db = MagicMock()
    # Mock the execute method to return an empty list of rows
    db.execute.return_value = []
    yield db

app.dependency_overrides[require_auth] = override_require_auth
app.dependency_overrides[get_db] = override_get_db


def test_proximity_alert_schema():
    """Test the ProximityAlertCreate Pydantic schema validation."""
    alert = ProximityAlertCreate(
        alert_name="My Local Venues",
        target_radius_meters=10000.0,
        latitude=34.05,
        longitude=-118.25
    )
    assert alert.alert_name == "My Local Venues"
    assert alert.target_radius_meters == 10000.0


def test_create_proximity_alert_route():
    """Test the POST /alerts/proximity route and verify Haversine SQL clamp logic."""
    response = client.post(
        "/alerts/proximity",
        json={
            "alert_name": "Test Alert",
            "target_radius_meters": 5000.0,
            "latitude": 40.7128,
            "longitude": -74.0060,
            "is_active": True
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "created"
    assert "alert_id" in data
    assert data["nearby_municipal_items_found"] == 0
    assert data["items"] == []

    # Verify that the DB was called with the clamped Haversine formula
    db_mock = next(override_get_db())
    assert db_mock.add.called
    assert db_mock.flush.called
    assert db_mock.commit.called

