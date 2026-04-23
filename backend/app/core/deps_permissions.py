from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.auth import get_current_user
from app.core.permissions import get_or_create_company_permissions, has_permission
from app.models.user import User

def require_permission(module: str, action: str):
    def _dep(
        db: Session = Depends(get_db),
        current_user: User = Depends(get_current_user),
    ) -> User:
        role = (current_user.role or "").upper()

        # ADMIN sempre passa (ou deixa também configurável, se quiser)
        if role == "ADMIN":
            return current_user

        row = get_or_create_company_permissions(db, current_user.company_id)
        if not has_permission(row.staff_permissions, module, action):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Sem permissão: {module}.{action}",
            )
        return current_user
    return _dep

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if (current_user.role or "").upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Apenas ADMIN",
        )
    return current_user
