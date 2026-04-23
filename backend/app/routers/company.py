from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.auth import get_current_user
from app.core.permission_guard import require_permission

from app.models.user import User
from app.models.company import Company

router = APIRouter(prefix="/company", tags=["company"])


@router.get("/me")
def get_my_company(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "company", "view")

    c = db.query(Company).filter(Company.id == current_user.company_id).first()

    return {
        "id": c.id,
        "name": c.name,
        "slug": c.slug,
        "vat_number": c.vat_number,
        "address": c.address,
        "phone": c.phone,
        "email": c.email,
        "iban": c.iban,
        "logo_path": c.logo_path,
        "invoice_prefix": c.invoice_prefix,
    }