from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from app.core.deps import get_db
from app.core.auth import get_current_user
from app.core.permission_guard import require_permission
from app.models.user import User
from app.models.audit_log import AuditLog
from app.schemas.audit_log import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_logs(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    entity: str | None = Query(default=None),
    action: str | None = Query(default=None),
    limit: int = Query(default=200, ge=1, le=1000),
):
    require_permission(db, current_user, "audit", "view")

    q = (
        db.query(AuditLog)
        .options(joinedload(AuditLog.user))
        .filter(AuditLog.company_id == current_user.company_id)
    )

    if entity:
        q = q.filter(AuditLog.entity == entity.lower())

    if action:
        q = q.filter(AuditLog.action == action.upper())

    return (
        q.order_by(AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )