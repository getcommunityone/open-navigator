from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any

from api.database import get_db
from api.models import User, ProximityAlert
from api.auth import require_auth
from models.proximity_alert import ProximityAlertCreate

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.post("/proximity", response_model=Dict[str, Any])
def create_proximity_alert_and_scan(
    alert_in: ProximityAlertCreate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Create a proximity alert and scan for nearby municipal meeting places.

    Persists a ProximityAlert row for the authenticated user, then runs a
    Haversine-distance scan against ``event_place_geocoded`` (the public
    serving view of geocoded meeting venues) to return nearby items within
    the requested radius.  The alert and scan results are committed
    atomically — if the scan fails the alert is rolled back.

    The ``acos()`` argument is clamped to [-1, 1] via LEAST/GREATEST to
    guard against floating-point rounding on near-identical points, which
    would otherwise raise ``ERROR: input is out of range`` in Postgres.
    """

    # Stage the alert — do NOT commit yet so a scan failure rolls back
    new_alert = ProximityAlert(
        user_id=current_user.user_id,
        alert_name=alert_in.alert_name,
        target_radius_meters=alert_in.target_radius_meters,
        is_active=alert_in.is_active,
        latitude=alert_in.latitude,
        longitude=alert_in.longitude,
    )
    db.add(new_alert)
    db.flush()  # assigns new_alert.id without committing the transaction

    # Haversine distance scan against the public serving view.
    # Table name is UNQUALIFIED so it resolves via the ORM session's
    # search_path (public-first); never hard-code a schema qualifier.
    # acos() input is clamped to [-1, 1] to prevent domain errors.
    sql_query = text("""
        SELECT
            event_place_id  AS id,
            COALESCE(normalized_address, raw_text, place_id) AS name,
            latitude,
            longitude,
            jurisdiction_name,
            city,
            state_code,
            (6371000 * acos(
                LEAST(1.0, GREATEST(-1.0,
                    cos(radians(:lat)) * cos(radians(latitude))
                    * cos(radians(longitude) - radians(:lon))
                    + sin(radians(:lat)) * sin(radians(latitude))
                ))
            )) AS distance
        FROM event_place_geocoded
        WHERE latitude IS NOT NULL
          AND longitude IS NOT NULL
          AND (6371000 * acos(
                LEAST(1.0, GREATEST(-1.0,
                    cos(radians(:lat)) * cos(radians(latitude))
                    * cos(radians(longitude) - radians(:lon))
                    + sin(radians(:lat)) * sin(radians(latitude))
                ))
              )) <= :radius
        ORDER BY distance
        LIMIT 100;
    """)

    result = db.execute(
        sql_query,
        {"lat": alert_in.latitude, "lon": alert_in.longitude, "radius": alert_in.target_radius_meters},
    )

    nearby_items = [dict(row._mapping) for row in result]

    # Commit atomically after the scan succeeds
    db.commit()
    db.refresh(new_alert)

    return {
        "alert_id": new_alert.id,
        "status": "created",
        "nearby_municipal_items_found": len(nearby_items),
        "items": nearby_items,
    }
