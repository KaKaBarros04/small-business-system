from datetime import datetime, date
from sqlalchemy import Column, Integer, Date, String, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class Contract(Base):
    __tablename__ = "contracts"

    id = Column(Integer, primary_key=True, index=True)

    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    visits_per_year = Column(Integer, nullable=False)  # 1..12
    cutoff_days = Column(Integer, nullable=False, default=20)

    status = Column(String(20), nullable=False, default="ACTIVE")
    # ACTIVE | CANCELED | EXPIRED

    created_at = Column(Date, default=date.today, nullable=False)

    client = relationship("Client")
