from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.auth import get_current_user
from app.core.permissions import get_or_create_company_permissions
from app.models.user import User

router = APIRouter(prefix="/permissions", tags=["permissions"])

@router.get("/me")
def get_my_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    row = get_or_create_company_permissions(db, current_user.company_id)
    return {"staff_permissions": row.staff_permissions}
