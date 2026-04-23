# app/models/service.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from app.core.database import Base


class Service(Base):
    __tablename__ = "services"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    name = Column(String(150), nullable=False)
    base_price = Column(Float, nullable=False, default=0.0)
    duration_minutes = Column(Integer, nullable=False, default=60)

