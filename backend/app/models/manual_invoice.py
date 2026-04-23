# models/manual_invoice.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class ManualInvoice(Base):
    __tablename__ = "manual_invoices"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)

    # ✅ NOVO: ligação opcional ao cliente
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=True, index=True)

    # ✅ NOVO: tipo da fatura
    invoice_kind = Column(String(30), nullable=False, default="MANUAL")  # MANUAL | CONTRACT

    supplier_name = Column(String(200), nullable=False)

    # ✅ agora pode ser nulo enquanto for pré-fatura
    invoice_number = Column(String(80), nullable=True)

    issue_date = Column(DateTime, nullable=False)
    due_date = Column(DateTime, nullable=True)

    # ✅ agora aceita DRAFT
    status = Column(String(20), nullable=False, default="DRAFT")  # DRAFT | ISSUED | PAID | CANCELED
    paid_at = Column(DateTime, nullable=True)

    subtotal = Column(Float, nullable=False, default=0.0)
    tax = Column(Float, nullable=False, default=0.0)
    total = Column(Float, nullable=False, default=0.0)

    notes = Column(String(500), nullable=True)
    pdf_path = Column(String(255), nullable=True)

    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    updated_by_user_id = Column(Integer, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)

    items = relationship(
        "ManualInvoiceItem",
        back_populates="invoice",
        cascade="all, delete-orphan"
    )

    client = relationship("Client")