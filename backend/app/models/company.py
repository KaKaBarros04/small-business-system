# models/company.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from app.core.database import Base
from sqlalchemy.orm import relationship


class Company(Base):
    __tablename__ = "companies"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False, index=True)

    clients = relationship("Client", back_populates="company")

    name = Column(String(200), nullable=False)
    slug = Column(String(80), nullable=False, unique=True, index=True)

    vat_number = Column(String(50), nullable=True)
    address = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    iban = Column(String(60), nullable=True)

    logo_path = Column(String(255), nullable=True)

    invoice_prefix = Column(String(20), nullable=False, default="FT")
    next_invoice_number = Column(Integer, nullable=False, default=1)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    google_calendar_id = Column(String, nullable=True)
    google_timezone = Column(String, nullable=True)  # opcional
    google_client_color_mode = Column(String(20), nullable=False, default="none")

    is_group_company = Column(Boolean, default=False)