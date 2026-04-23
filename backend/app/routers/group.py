from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.deps import get_db
from app.models.user import User
from app.models.company import Company
from app.models.group import Group
from app.services.dashboard_service import build_dashboard_summary

router = APIRouter(prefix="/group", tags=["group"])


@router.get("/dashboard")
def group_dashboard(
    year: int,
    month: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if getattr(current_user, "role", "") != "GROUP_ADMIN":
        raise HTTPException(status_code=403, detail="Forbidden")

    group = db.query(Group).filter(Group.name == "SACRED VISION").first()
    if not group:
        raise HTTPException(status_code=404, detail="Grupo não encontrado")

    companies = (
        db.query(Company)
        .filter(Company.group_id == group.id)
        .order_by(Company.id.asc())
        .all()
    )

    if not companies:
        raise HTTPException(status_code=404, detail="Sem empresas registadas")

    companies_data = []

    group_totals = {
        "invoices_total": 0.0,
        "invoices_paid_count": 0,
        "revenue_paid_total": 0.0,
        "revenue_issued_total": 0.0,
        "expenses_total": 0.0,
        "profit_total": 0.0,
        "appointments_total": 0,
        "appointments_scheduled": 0,
        "appointments_done": 0,
        "appointments_canceled": 0,
    }

    for c in companies:
        data = build_dashboard_summary(db, c.id, year, month)
        companies_data.append({"company_id": c.id, "name": c.name, "data": data})

        t = (data or {}).get("totals") or {}
        group_totals["invoices_total"] += float(t.get("invoices_total", 0) or 0)
        group_totals["invoices_paid_count"] += int(t.get("invoices_paid_count", 0) or 0)
        group_totals["revenue_paid_total"] += float(t.get("revenue_paid_total", 0) or 0)
        group_totals["revenue_issued_total"] += float(t.get("revenue_issued_total", 0) or 0)
        group_totals["expenses_total"] += float(t.get("expenses_total", 0) or 0)
        group_totals["profit_total"] += float(t.get("profit_total", 0) or 0)
        group_totals["appointments_total"] += int(t.get("appointments_total", 0) or 0)
        group_totals["appointments_scheduled"] += int(t.get("appointments_scheduled", 0) or 0)
        group_totals["appointments_done"] += int(t.get("appointments_done", 0) or 0)
        group_totals["appointments_canceled"] += int(t.get("appointments_canceled", 0) or 0)

    return {
        "range": {"year": year, "month": month},
        "selected_period": {"year": year, "month": month},
        "companies": companies_data,
        "totals": group_totals,
    }