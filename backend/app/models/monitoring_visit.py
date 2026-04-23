from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class MonitoringVisit(Base):
    __tablename__ = "monitoring_visits"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)
    appointment_id = Column(Integer, ForeignKey("appointments.id"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    visit_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    pest_type = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    client = relationship("Client")
    appointment = relationship("Appointment")
    results = relationship(
        "MonitoringPointResult",
        back_populates="visit",
        cascade="all, delete-orphan",
    )