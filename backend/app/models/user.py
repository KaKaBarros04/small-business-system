# app/models/user.py
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)

    # ✅ novo
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="STAFF")  # ADMIN ou STAFF

    company_id = Column(Integer, ForeignKey("companies.id"), nullable=True, index=True)
