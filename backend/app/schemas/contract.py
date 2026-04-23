from datetime import date
from pydantic import BaseModel, Field


class ContractCreate(BaseModel):
    client_id: int
    start_date: date
    visits_per_year: int = Field(ge=1, le=12)


class ContractOut(BaseModel):
    id: int
    client_id: int
    start_date: date
    end_date: date
    visits_per_year: int
    status: str

    class Config:
        from_attributes = True
