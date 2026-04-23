# app/routers/permissions.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.auth import get_current_user
from app.core.permission_guard import require_permission
from app.models.user import User
from app.models.company_permission import CompanyPermission
from app.models.user_permission import UserPermission

router = APIRouter(prefix="/permissions", tags=["permissions"])


DEFAULT_PERMISSIONS = {
    "dashboard": {"view": True},
    "clients": {"view": True, "create": True, "edit": True, "delete": False},
    "services": {"view": True, "create": False, "edit": False, "delete": False},
    "appointments": {"view": True, "create": True, "edit": True, "delete": True},
    "agenda": {"view": True},
    "invoices": {"view": False, "create": False, "edit": False, "delete": False},
    "expenses": {"view": False, "create": False, "edit": False, "delete": False},
    "stock": {"view": False, "create": False, "edit": False, "delete": False},
    "audit": {"view": False},
    "employees": {"view": False, "create": False, "edit": False, "delete": False},
    "permissions": {"view": False, "edit": False},
    "site_maps": {"view": True, "create": True, "edit": True, "delete": True},
}


class PermissionsPayload(BaseModel):
    permissions: dict


class RolePayload(BaseModel):
    role: str


def ensure_admin(user: User):
    if user.role not in ("ADMIN", "GROUP_ADMIN"):
        raise HTTPException(status_code=403, detail="Sem permissão")


@router.get("/company")
def get_company_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "permissions", "view")
    ensure_admin(current_user)

    row = (
        db.query(CompanyPermission)
        .filter(CompanyPermission.company_id == current_user.company_id)
        .first()
    )

    if not row:
        row = CompanyPermission(
            company_id=current_user.company_id,
            staff_permissions=DEFAULT_PERMISSIONS,
        )
        db.add(row)
        db.commit()
        db.refresh(row)

    return {"permissions": row.staff_permissions or DEFAULT_PERMISSIONS}


@router.put("/company")
def update_company_permissions(
    payload: PermissionsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "permissions", "edit")
    ensure_admin(current_user)

    row = (
        db.query(CompanyPermission)
        .filter(CompanyPermission.company_id == current_user.company_id)
        .first()
    )

    if not row:
        row = CompanyPermission(
            company_id=current_user.company_id,
            staff_permissions=payload.permissions,
        )
        db.add(row)
    else:
        row.staff_permissions = payload.permissions

    db.commit()
    db.refresh(row)
    return {"ok": True, "permissions": row.staff_permissions}


@router.get("/user/{user_id}")
def get_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "permissions", "view")
    ensure_admin(current_user)

    user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == current_user.company_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")

    row = db.query(UserPermission).filter(UserPermission.user_id == user_id).first()

    if row:
        return {
            "scope": "user",
            "permissions": row.permissions or {},
            "role": user.role,
        }

    company_row = (
        db.query(CompanyPermission)
        .filter(CompanyPermission.company_id == current_user.company_id)
        .first()
    )

    return {
        "scope": "company",
        "permissions": (company_row.staff_permissions if company_row else DEFAULT_PERMISSIONS),
        "role": user.role,
    }


@router.put("/user/{user_id}")
def update_user_permissions(
    user_id: int,
    payload: PermissionsPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "permissions", "edit")
    ensure_admin(current_user)

    user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == current_user.company_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")

    row = db.query(UserPermission).filter(UserPermission.user_id == user_id).first()

    if not row:
        row = UserPermission(user_id=user_id, permissions=payload.permissions)
        db.add(row)
    else:
        row.permissions = payload.permissions

    db.commit()
    db.refresh(row)

    return {"ok": True, "permissions": row.permissions}


@router.delete("/user/{user_id}")
def delete_user_permissions(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "permissions", "edit")
    ensure_admin(current_user)

    user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == current_user.company_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")

    row = db.query(UserPermission).filter(UserPermission.user_id == user_id).first()
    if row:
        db.delete(row)
        db.commit()

    return {"ok": True}


@router.put("/user/{user_id}/role")
def update_user_role(
    user_id: int,
    payload: RolePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "permissions", "edit")
    ensure_admin(current_user)

    role = (payload.role or "").upper().strip()
    if role not in ("ADMIN", "STAFF"):
        raise HTTPException(status_code=400, detail="Role inválido")

    user = (
        db.query(User)
        .filter(User.id == user_id, User.company_id == current_user.company_id)
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Funcionário não encontrado")

    user.role = role
    db.commit()
    db.refresh(user)

    return {"ok": True, "id": user.id, "role": user.role}