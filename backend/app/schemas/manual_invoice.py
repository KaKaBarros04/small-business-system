from datetime import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel


class ManualInvoiceClientOut(BaseModel):
    id: int
    client_code: str | None = None
    business_name: str | None = None
    name: str | None = None
    address: str | None = None
    postal_code: str | None = None
    city: str | None = None

    class Config:
        from_attributes = True


class ManualInvoiceItemCreate(BaseModel):
    description: str
    qty: int = 1
    unit_price: float


class ManualInvoiceItemOut(BaseModel):
    id: int
    description: str
    qty: int
    unit_price: float
    line_total: float

    class Config:
        from_attributes = True


class ManualInvoiceCreate(BaseModel):
    client_id: Optional[int] = None
    invoice_kind: Optional[str] = "MANUAL"

    supplier_name: str
    invoice_number: Optional[str] = None

    issue_date: datetime
    due_date: Optional[datetime] = None
    notes: Optional[str] = None
    items: List[ManualInvoiceItemCreate] = []

    tax_rate: Optional[float] = 0.0
    status: Optional[Literal["DRAFT", "ISSUED", "PAID", "CANCELED"]] = "ISSUED"


class ManualInvoiceUpdate(BaseModel):
    client_id: Optional[int] = None
    invoice_kind: Optional[str] = None

    supplier_name: Optional[str] = None
    invoice_number: Optional[str] = None
    issue_date: Optional[datetime] = None
    due_date: Optional[datetime] = None
    notes: Optional[str] = None

    items: Optional[List[ManualInvoiceItemCreate]] = None
    tax_rate: Optional[float] = None

    status: Optional[Literal["DRAFT", "ISSUED", "PAID", "CANCELED"]] = None


class ManualInvoiceStatusUpdate(BaseModel):
    status: Literal["DRAFT", "ISSUED", "PAID", "CANCELED"]


class ManualInvoiceOut(BaseModel):
    id: int
    company_id: int
    client_id: Optional[int] = None
    invoice_kind: str

    supplier_name: str
    invoice_number: Optional[str] = None

    issue_date: datetime
    due_date: Optional[datetime]
    status: str
    paid_at: Optional[datetime]

    subtotal: float
    tax: float
    total: float

    notes: Optional[str]
    pdf_path: Optional[str]

    created_by_user_id: int
    updated_by_user_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]

    client: Optional[ManualInvoiceClientOut] = None
    items: List[ManualInvoiceItemOut] = []

    class Config:
        from_attributes = True