# models/appointment.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.core.database import Base

class Appointment(Base):
    __tablename__ = "appointments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False)
    service_id = Column(Integer, ForeignKey("services.id"), nullable=False)

    scheduled_at = Column(DateTime, nullable=False, index=True)
    address = Column(String(255), nullable=False)
    notes = Column(String(500), nullable=True)

    price = Column(Float, nullable=False, default=0.0)
    status = Column(String(20), nullable=False, default="SCHEDULED")

    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", lazy="joined")
    service = relationship("Service", lazy="joined")

    # ✅ NOVO (Google Calendar sync)
    google_event_id = Column(String(255), nullable=True, index=True)
    google_sync_error = Column(String(500), nullable=True)

    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=True, index=True)
    is_contract_visit = Column(Boolean, nullable=False, default=False)

    service_name = Column(String(255), nullable=True)
    service_price = Column(Float, nullable=True)