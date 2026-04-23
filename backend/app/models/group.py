# models/group.py
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from app.core.database import Base

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
