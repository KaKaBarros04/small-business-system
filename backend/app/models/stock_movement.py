# app/models/stock_movement.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Numeric
from app.core.database import Base

class StockMovement(Base):
    __tablename__ = "stock_movements"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    stock_item_id = Column(Integer, ForeignKey("stock_items.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    type = Column(String(20), nullable=False)  # IN | OUT | ADJUST

    qty = Column(Numeric(14, 3), nullable=False)
    unit_cost = Column(Numeric(14, 4), nullable=True)
    total_cost = Column(Numeric(14, 4), nullable=True)

    reason = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
