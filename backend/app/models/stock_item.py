# app/models/stock_item.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Numeric
from app.core.database import Base

class StockItem(Base):
    __tablename__ = "stock_items"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    name = Column(String(200), nullable=False)
    sku = Column(String(100), nullable=True)

    category = Column(String(100), nullable=True)  # EX: VENENO, PRODUTO LIMPEZA
    unit = Column(String(20), nullable=False, default="un")  # un | kg | L | cx

    min_qty = Column(Numeric(12, 3), nullable=False, default=5)
    qty_on_hand = Column(Numeric(14, 3), nullable=False, default=0)

    avg_unit_cost = Column(Numeric(14, 4), nullable=False, default=0)
    last_purchase_unit_cost = Column(Numeric(14, 4), nullable=True)

    supplier_name = Column(String(200), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, nullable=True)
