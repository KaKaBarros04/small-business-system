from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional


class ExpenseCreate(BaseModel):
    date: Optional[datetime] = None
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=255)
    amount: float = Field(ge=0)


class ExpenseUpdate(BaseModel):
    date: Optional[datetime] = None
    category: Optional[str] = Field(default=None, min_length=1, max_length=80)
    description: Optional[str] = Field(default=None, min_length=1, max_length=255)
    amount: Optional[float] = Field(default=None, ge=0)


class ExpenseOut(BaseModel):
    id: int
    user_id: int
    date: datetime
    category: str
    description: str
    amount: float

    class Config:
        from_attributes = True
