from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.security import SECRET_KEY, ALGORITHM
from app.models.user import User
from app.core.audit_context import set_audit_context

security = HTTPBearer()


def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = creds.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])

        if payload.get("type") != "access":
            raise ValueError("wrong token type")

        sub = payload.get("sub")
        token_company_id = payload.get("company_id")

        if not sub:
            raise ValueError("sub missing")

        user_id = int(sub)

        if token_company_id is not None:
            token_company_id = int(token_company_id)

    except (JWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Utilizador não encontrado",
        )

    if user.company_id is not None:
        if token_company_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido ou expirado",
            )
        if int(user.company_id) != int(token_company_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido ou expirado",
            )

    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")

    set_audit_context(
        user_id=user.id,
        company_id=getattr(user, "company_id", None),
        ip=ip,
        user_agent=ua,
    )

    return user