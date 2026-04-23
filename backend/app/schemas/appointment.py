from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Literal


class AppointmentCreate(BaseModel):
    client_id: int

    # serviço livre no agendamento
    service_name: str = Field(min_length=1, max_length=255)
    service_price: Optional[float] = Field(default=None, ge=0)

    scheduled_at: datetime
    address: str = Field(min_length=1, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=500)

    # preço do agendamento (opcional)
    price: Optional[float] = Field(default=None, ge=0)

    status: Optional[Literal["SCHEDULED", "DONE", "CANCELED"]] = None


class AppointmentUpdate(BaseModel):
    # editar serviço
    service_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    service_price: Optional[float] = Field(default=None, ge=0)

    scheduled_at: Optional[datetime] = None
    address: Optional[str] = Field(default=None, min_length=1, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=500)
    price: Optional[float] = Field(default=None, ge=0)
    status: Optional[Literal["SCHEDULED", "DONE", "CANCELED"]] = None


class ClientMini(BaseModel):
    id: int
    name: str
    client_code: Optional[str] = None

    class Config:
        from_attributes = True


class AppointmentOut(BaseModel):
    id: int
    status: str
    price: Optional[float]
    scheduled_at: datetime
    address: str
    maps_link: Optional[str] = None
    notes: Optional[str]
    created_at: datetime

    service_name: Optional[str] = None
    service_price: Optional[float] = None

    client: ClientMini

    class Config:
        from_attributes = True