from app.models.user import User

def is_admin(user: User) -> bool:
    return (user.role or "").upper() == "ADMIN"
 
from sqlalchemy.orm import Session
from app.models.company_permission import CompanyPermission
from app.core.permissions_defaults import DEFAULT_STAFF_PERMS
from app.models.user_permission import UserPermission

def get_or_create_company_permissions(db: Session, company_id: int) -> CompanyPermission:
    row = db.query(CompanyPermission).filter(CompanyPermission.company_id == company_id).first()
    if row:
        # garante que sempre tenha algo
        if not row.staff_permissions:
            row.staff_permissions = DEFAULT_STAFF_PERMS
            db.add(row)
            db.commit()
            db.refresh(row)
        return row

    row = CompanyPermission(company_id=company_id, staff_permissions=DEFAULT_STAFF_PERMS)
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def has_permission(perms: dict, module: str, action: str) -> bool:
    m = (perms or {}).get(module) or {}
    return bool(m.get(action, False))


def get_effective_permissions(db, user):
    if user.role in ("ADMIN", "GROUP_ADMIN"):
        return {"*": True}

    user_row = db.query(UserPermission).filter(UserPermission.user_id == user.id).first()
    if user_row and user_row.permissions:
        return user_row.permissions

    company_row = (
        db.query(CompanyPermission)
        .filter(CompanyPermission.company_id == user.company_id)
        .first()
    )
    if company_row and company_row.staff_permissions:
        return company_row.staff_permissions

    return {}