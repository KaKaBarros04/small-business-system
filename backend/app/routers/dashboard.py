from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.deps import get_db
from app.core.permission_guard import require_permission
from app.models.user import User
from app.services.dashboard_service import build_dashboard_summary

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("")
def dashboard(
    year: int,
    month: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "dashboard", "view")

    return build_dashboard_summary(db, current_user.company_id, year, month)


# Compatibilidade com front antigo
@router.get("/summary")
def dashboard_summary(
    year: int,
    month: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "dashboard", "view")

    return build_dashboard_summary(db, current_user.company_id, year, month)