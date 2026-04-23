from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.deps_permissions import require_admin
from app.core.permission_guard import require_permission
from app.core.permissions import get_or_create_company_permissions
from app.models.user import User
from app.schemas.permissions import PermissionsUpdate

router = APIRouter(prefix="/admin/permissions", tags=["admin-permissions"])


@router.get("")
def get_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    require_permission(db, current_user, "permissions", "view")

    row = get_or_create_company_permissions(db, current_user.company_id)
    return {"staff_permissions": row.staff_permissions}


@router.put("")
def update_permissions(
    payload: PermissionsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    require_permission(db, current_user, "permissions", "edit")

    row = get_or_create_company_permissions(db, current_user.company_id)
    row.staff_permissions = payload.staff_permissions
    db.add(row)
    db.commit()
    db.refresh(row)
    return {"staff_permissions": row.staff_permissions}