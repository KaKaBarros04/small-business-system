from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, Field


# -------------------------
# Site maps
# -------------------------
class SiteMapPointCreate(BaseModel):
    point_number: Optional[int] = Field(default=None, ge=1)
    label: Optional[str] = Field(default=None, max_length=120)
    device_type: str = Field(..., max_length=50)
    x_percent: float = Field(..., ge=0, le=100)
    y_percent: float = Field(..., ge=0, le=100)
    is_active: bool = True


class SiteMapPointUpdate(BaseModel):
    point_number: Optional[int] = Field(default=None, ge=1)
    label: Optional[str] = Field(default=None, max_length=120)
    device_type: Optional[str] = Field(default=None, max_length=50)
    x_percent: Optional[float] = Field(default=None, ge=0, le=100)
    y_percent: Optional[float] = Field(default=None, ge=0, le=100)
    is_active: Optional[bool] = None


class SiteMapPointOut(BaseModel):
    id: int
    site_map_id: int
    point_number: int
    label: Optional[str] = None
    device_type: str
    x_percent: float
    y_percent: float
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class SiteMapCreate(BaseModel):
    client_id: int
    name: str = Field(..., max_length=150)
    page_order: int = Field(default=1, ge=1)
    notes: Optional[str] = None
    is_active: bool = True


class SiteMapUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=150)
    page_order: Optional[int] = Field(default=None, ge=1)
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class SiteMapOut(BaseModel):
    id: int
    company_id: int
    client_id: int
    name: str
    image_path: str
    page_order: int
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    points: List[SiteMapPointOut] = []

    class Config:
        from_attributes = True


# -------------------------
# Monitoring visits
# -------------------------
class MonitoringPointResultCreate(BaseModel):
    site_map_point_id: int
    status_code: Optional[str] = Field(default=None, max_length=20)
    consumption_percent: Optional[float] = Field(default=None, ge=0, le=100)
    action_taken: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None
    replaced: bool = False


class MonitoringPointResultUpdate(BaseModel):
    status_code: Optional[str] = Field(default=None, max_length=20)
    consumption_percent: Optional[float] = Field(default=None, ge=0, le=100)
    action_taken: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None
    replaced: Optional[bool] = None


class MonitoringPointResultOut(BaseModel):
    id: int
    visit_id: int
    site_map_point_id: int
    status_code: Optional[str] = None
    consumption_percent: Optional[float] = None
    action_taken: Optional[str] = None
    notes: Optional[str] = None
    replaced: bool
    created_at: datetime

    class Config:
        from_attributes = True


class MonitoringVisitCreate(BaseModel):
    client_id: int
    appointment_id: Optional[int] = None
    visit_date: Optional[datetime] = None
    pest_type: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None
    results: List[MonitoringPointResultCreate] = []


class MonitoringVisitUpdate(BaseModel):
    appointment_id: Optional[int] = None
    visit_date: Optional[datetime] = None
    pest_type: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = None
    results: Optional[List[MonitoringPointResultCreate]] = None


class MonitoringVisitOut(BaseModel):
    id: int
    company_id: int
    client_id: int
    appointment_id: Optional[int] = None
    user_id: int
    visit_date: datetime
    pest_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    results: List[MonitoringPointResultOut] = []

    class Config:
        from_attributes = True