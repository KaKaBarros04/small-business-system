from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from app.core.database import Base  # ajusta pro teu projeto

class CompanyPermission(Base):
    __tablename__ = "company_permissions"

    id = Column(Integer, primary_key=True, index=True)
    company_id = Column(Integer, ForeignKey("companies.id"), unique=True, nullable=False, index=True)

    # permissões configuráveis pelo admin
    staff_permissions = Column(JSONB, nullable=False, default=dict)

    company = relationship("Company")