from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class ProximityAlertBase(BaseModel):
    alert_name: str = Field(..., min_length=1, max_length=255, description="Name of the alert")
    target_radius_meters: float = Field(..., ge=100.0, le=50000.0, description="Radius in meters (100m to 50km)")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude of the center point (-90 to 90)")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude of the center point (-180 to 180)")
    is_active: bool = True

class ProximityAlertCreate(ProximityAlertBase):
    pass

class ProximityAlertUpdate(BaseModel):
    alert_name: Optional[str] = Field(None, min_length=1, max_length=255)
    target_radius_meters: Optional[float] = Field(None, ge=100.0, le=50000.0)
    latitude: Optional[float] = Field(None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(None, ge=-180.0, le=180.0)
    is_active: Optional[bool] = None

class ProximityAlertResponse(ProximityAlertBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
