# app/core/permission_guard.py

from fastapi import HTTPException
from app.core.permissions import get_effective_permissions


def require_permission(db, user, section: str, action: str):
    perms = get_effective_permissions(db, user)

    if perms.get("*") is True:
        return True

    allowed = (((perms or {}).get(section) or {}).get(action)) is True
    if not allowed:
        raise HTTPException(status_code=403, detail="Sem permissão")

    return True