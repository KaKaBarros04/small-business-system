from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, Boolean, DateTime, Float
from sqlalchemy.orm import relationship

from app.core.database import Base


class SiteMapPoint(Base):
    __tablename__ = "site_map_points"

    id = Column(Integer, primary_key=True, index=True)
    site_map_id = Column(Integer, ForeignKey("site_maps.id"), nullable=False, index=True)

    point_number = Column(Integer, nullable=False)
    label = Column(String(120), nullable=True)           # Ex: Entrada, WC, Cozinha
    device_type = Column(String(50), nullable=False)     # RAT_PVC, RAT_CARDBOARD, COCKROACH_TRAP, INSECT_CATCHER, OTHER
    x_percent = Column(Float, nullable=False)            # Guardar em percentagem
    y_percent = Column(Float, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    site_map = relationship("SiteMap", back_populates="points")