from datetime import datetime

from sqlalchemy import Column, Integer, String, ForeignKey, Float, Boolean, DateTime, Text
from sqlalchemy.orm import relationship

from app.core.database import Base


class MonitoringPointResult(Base):
    __tablename__ = "monitoring_point_results"

    id = Column(Integer, primary_key=True, index=True)
    visit_id = Column(Integer, ForeignKey("monitoring_visits.id"), nullable=False, index=True)
    site_map_point_id = Column(Integer, ForeignKey("site_map_points.id"), nullable=False, index=True)

    status_code = Column(String(20), nullable=True)          # ND, D, DI, NC, MC, TC...
    consumption_percent = Column(Float, nullable=True)
    action_taken = Column(String(120), nullable=True)        # Ex: substituído, reabastecido
    notes = Column(Text, nullable=True)
    replaced = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    visit = relationship("MonitoringVisit", back_populates="results")
    point = relationship("SiteMapPoint")