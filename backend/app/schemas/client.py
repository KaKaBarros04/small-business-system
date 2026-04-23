# schemas/client.py
from datetime import date
from pydantic import BaseModel, EmailStr, Field

class ClientBase(BaseModel):
    name: str
    email: EmailStr | None = None
    phone: str | None = None

    client_code: str | None = None
    business_name: str | None = None
    contact_name: str | None = None
    nickname: str | None = None

    vat_number: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None

    pest_type: str | None = None
    notes: str | None = None

    has_contract: bool = False
    contract_start_date: date | None = None
    visits_per_year: int | None = Field(default=None, ge=1, le=12)

    # ✅ NOVO
    contract_value_yearly: float | None = Field(default=None, ge=0)

    is_active: bool = True

class ClientCreate(ClientBase):
    pass

class ClientUpdate(BaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None

    client_code: str | None = None
    business_name: str | None = None
    contact_name: str | None = None
    nickname: str | None = None

    vat_number: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None

    pest_type: str | None = None
    notes: str | None = None

    has_contract: bool | None = None
    contract_start_date: date | None = None
    visits_per_year: int | None = Field(default=None, ge=1, le=12)

    # ✅ NOVO
    contract_value_yearly: float | None = Field(default=None, ge=0)

    is_active: bool | None = None

class ClientOut(BaseModel):
    id: int
    company_id: int

    name: str
    email: EmailStr | None = None
    phone: str | None = None

    client_code: str | None = None
    business_name: str | None = None
    contact_name: str | None = None
    nickname: str | None = None

    vat_number: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None

    pest_type: str | None = None
    notes: str | None = None

    has_contract: bool
    contract_start_date: date | None = None
    visits_per_year: int | None = None

    # ✅ NOVO
    contract_value_yearly: float | None = None

    is_active: bool

    class Config:
        from_attributes = True
