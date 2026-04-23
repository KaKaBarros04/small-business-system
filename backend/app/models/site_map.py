from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class SiteMap(Base):
    __tablename__ = "site_maps"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), nullable=False, index=True)
    client_id = Column(Integer, ForeignKey("clients.id"), nullable=False, index=True)

    name = Column(String(150), nullable=False)          # Ex: Piso 0, Piso 1, Cozinha
    image_path = Column(String(500), nullable=False)
    page_order = Column(Integer, nullable=False, default=1)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    client = relationship("Client")
    points = relationship(
        "SiteMapPoint",
        back_populates="site_map",
        cascade="all, delete-orphan",
        order_by="SiteMapPoint.point_number.asc()",
    )