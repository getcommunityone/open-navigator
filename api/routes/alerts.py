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
async def create_proximity_alert_and_scan(
    alert_in: ProximityAlertCreate,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db)
):
    """
    Creates a new proximity alert and immediately scans for nearby municipal organizations 
    within the specified radius using PostGIS ST_DWithin.
    """
    # 1. Create the alert record
    wkt_point = f"POINT({alert_in.longitude} {alert_in.latitude})"
    
    new_alert = ProximityAlert(
        user_id=current_user.user_id,
        alert_name=alert_in.alert_name,
        target_radius_meters=alert_in.target_radius_meters,
        is_active=alert_in.is_active,
        center_point=wkt_point
    )
    db.add(new_alert)
    db.commit()
    db.refresh(new_alert)

    # 2. Query nearby municipal items (civic organizations) using ST_DWithin
    sql_query = text("""
        SELECT org_id, org_name, latitude, longitude
        FROM civic_organization
        WHERE latitude IS NOT NULL AND longitude IS NOT NULL
          AND ST_DWithin(
              CAST(ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) AS geography),
              CAST(:center_geom AS geography),
              :radius
          )
        LIMIT 100;
    """)
    
    result = db.execute(sql_query, {
        "center_geom": wkt_point,
        "radius": alert_in.target_radius_meters
    })
    
    nearby_items = [dict(row._mapping) for row in result]
    
    return {
        "alert_id": new_alert.id,
        "status": "created",
        "nearby_municipal_items_found": len(nearby_items),
        "items": nearby_items
    }
