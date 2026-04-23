# models/client.py
from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, Date, DateTime, Numeric
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    # básicos
    name = Column(String(200), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)

    client_code = Column(String(50), nullable=True)
    business_name = Column(String(200), nullable=True)
    contact_name = Column(String(120), nullable=True)
    nickname = Column(String(120), nullable=True)

    # morada / fiscal
    vat_number = Column(String(50), nullable=True)
    address = Column(String(255), nullable=True)
    postal_code = Column(String(20), nullable=True)
    city = Column(String(120), nullable=True)

    # técnico
    pest_type = Column(String(120), nullable=True)
    notes = Column(String(500), nullable=True)

    # contrato
    has_contract = Column(Boolean, default=False)
    contract_start_date = Column(Date, nullable=True)
    visits_per_year = Column(Integer, nullable=True)

    # ✅ NOVO: valor anual do contrato
    contract_value_yearly = Column(Numeric(10, 2), nullable=True)

    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    company = relationship("Company", back_populates="clients")
