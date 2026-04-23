# models/expense.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from app.core.database import Base


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)


    date = Column(DateTime, nullable=False, default=datetime.utcnow)
    category = Column(String(80), nullable=False, default="GENERAL")  # ex: SUPPLIES, FUEL, SALARY...
    description = Column(String(255), nullable=False, default="")
    amount = Column(Float, nullable=False, default=0.0)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
