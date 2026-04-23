from pydantic import BaseModel, Field
from typing import Optional


class ServiceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    base_price: float = Field(gt=0)
    duration_minutes: int = Field(ge=1)


class ServiceUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=150)
    base_price: Optional[float] = Field(default=None, gt=0)
    duration_minutes: Optional[int] = Field(default=None, ge=1)


class ServiceOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    name: str
    base_price: float
    duration_minutes: int

    class Config:
        from_attributes = True
