from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any

from api.database import get_db
from api.models import User, ProximityAlert
from api.auth import get_current_user, require_auth
from packages.datamodels.models.proximity_alert import ProximityAlertCreate

router = APIRouter(prefix="/alerts", tags=["alerts"])

@router.post("/proximity", response_model=Dict[str, Any])
def create_proximity_alert_and_scan(
    alert_in: ProximityAlertCreate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    # 1. Create the alert record
    
    new_alert = ProximityAlert(
        user_id=current_user.user_id,
        alert_name=alert_in.alert_name,
        target_radius_meters=alert_in.target_radius_meters,
        is_active=alert_in.is_active,
        latitude=alert_in.latitude,
        longitude=alert_in.longitude
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)

    # 2. Query nearby municipal items using Haversine distance
    sql_query = text("""
        SELECT id, name, latitude, longitude,
               (6371000 * acos(
                   cos(radians(:lat)) * cos(radians(latitude)) * 
                   cos(radians(longitude) - radians(:lon)) + 
                   sin(radians(:lat)) * sin(radians(latitude))
               )) AS distance
        FROM gold.civic_organization
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND (6371000 * acos(
                   cos(radians(:lat)) * cos(radians(latitude)) * 
                   cos(radians(longitude) - radians(:lon)) + 
                   sin(radians(:lat)) * sin(radians(latitude))
               )) <= :radius
        ORDER BY distance
        LIMIT 100;
    """)
    
    result = db.execute(sql_query, {
        "lat": alert_in.latitude,
        "lon": alert_in.longitude,
        "radius": alert_in.target_radius_meters
    })
    
    nearby_items = [dict(row._mapping) for row in result]
    
    return {
        "alert_id": new_alert.id,
        "status": "created",
        "nearby_municipal_items_found": len(nearby_items),
        "items": nearby_items
    }
