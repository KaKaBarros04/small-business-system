from pydantic import BaseModel
from typing import Dict, Any

class PermissionsUpdate(BaseModel):
    staff_permissions: Dict[str, Any]