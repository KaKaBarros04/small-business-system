from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel

from app.schemas.common import UserMini

class AuditLogOut(BaseModel):
    id: int
    company_id: int
    user_id: Optional[int]
    action: str
    entity: str
    entity_id: Optional[int]
    old_values: Optional[dict[str, Any]]
    new_values: Optional[dict[str, Any]]
    ip: Optional[str]
    user_agent: Optional[str]
    created_at: datetime

    user: UserMini|None = None

    class Config:
        from_attributes = True
