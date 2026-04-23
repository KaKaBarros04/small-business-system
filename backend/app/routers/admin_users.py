from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.deps_permissions import require_admin
from app.core.permission_guard import require_permission
from app.core.security import hash_password
from app.models.user import User
from app.schemas.users_admin import StaffCreate

router = APIRouter(prefix="/admin/users", tags=["admin-users"])


@router.get("")
def list_company_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    require_permission(db, current_user, "employees", "view")

    users = (
        db.query(User)
        .filter(User.company_id == current_user.company_id)
        .order_by(User.id.desc())
        .all()
    )
    return [
        {"id": u.id, "name": u.name, "email": u.email, "role": u.role}
        for u in users
    ]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_staff(
    payload: StaffCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    require_permission(db, current_user, "employees", "create")

    exists = db.query(User).filter(User.email == payload.email).first()
    if exists:
        raise HTTPException(status_code=400, detail="Email já existe")

    u = User(
        name=payload.name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        role="STAFF",  # ✅ força STAFF
        company_id=current_user.company_id,  # ✅ sempre mesma empresa
    )

    db.add(u)
    db.commit()
    db.refresh(u)

    return {"id": u.id, "name": u.name, "email": u.email, "role": u.role}