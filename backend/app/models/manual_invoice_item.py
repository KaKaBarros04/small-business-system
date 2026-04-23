# models/manual_invoice_item.py
from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class ManualInvoiceItem(Base):
    __tablename__ = "manual_invoice_items"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    manual_invoice_id = Column(
        Integer,
        ForeignKey("manual_invoices.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    description = Column(String(255), nullable=False)
    qty = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0.0)
    line_total = Column(Float, nullable=False, default=0.0)

    invoice = relationship("ManualInvoice", back_populates="items")
