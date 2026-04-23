# app/schemas/stock.py
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field

ALLOWED_UNITS = {"un", "kg", "L", "cx"}
ALLOWED_MOVE_TYPES = {"IN", "OUT", "ADJUST"}


class StockItemBase(BaseModel):
    name: str
    sku: str | None = None
    category: str | None = None
    unit: str = "un"  # un | kg | L | cx
    min_qty: Decimal = Field(default=Decimal("5"))
    supplier_name: str | None = None
    is_active: bool = True


class StockItemCreate(StockItemBase):
    qty_on_hand: Decimal = Field(default=Decimal("0"))
    avg_unit_cost: Decimal = Field(default=Decimal("0"))
    last_purchase_unit_cost: Decimal | None = None


class StockItemUpdate(BaseModel):
    name: str | None = None
    sku: str | None = None
    category: str | None = None
    unit: str | None = None
    min_qty: Decimal | None = None
    supplier_name: str | None = None
    is_active: bool | None = None


class StockItemOut(StockItemBase):
    id: int
    company_id: int
    qty_on_hand: Decimal
    avg_unit_cost: Decimal
    last_purchase_unit_cost: Decimal | None = None

    needs_restock: bool = False
    stock_value: Decimal = Decimal("0")

    created_at: datetime
    updated_at: datetime | None = None

    class Config:
        from_attributes = True


class StockMoveCreate(BaseModel):
    type: str  # IN | OUT | ADJUST
    qty: Decimal

    # custo só faz sentido no IN (ou ADJUST se quiseres) — mas vamos aceitar opcional
    unit_cost: Decimal | None = None

    reason: str | None = None

    # ✅ se True (default), movimento IN cria despesa STOCK automaticamente
    create_expense: bool = True


class StockMovementOut(BaseModel):
    id: int
    company_id: int
    stock_item_id: int
    user_id: int

    type: str
    qty: Decimal
    unit_cost: Decimal | None = None
    total_cost: Decimal | None = None
    reason: str | None = None

    created_at: datetime

    class Config:
        from_attributes = True


class StockSummaryOut(BaseModel):
    total_items: int
    needs_restock: int
    total_stock_value: Decimal
