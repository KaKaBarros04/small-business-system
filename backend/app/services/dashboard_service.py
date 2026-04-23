from datetime import datetime
from dateutil.relativedelta import relativedelta

from sqlalchemy.orm import Session
from sqlalchemy import func, extract

from app.models.manual_invoice import ManualInvoice
from app.models.appointment import Appointment
from app.models.expense import Expense


def _range_for_period(year: int, month: int | None):
    if not month or month == 0:
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)
        return start, end, {"year": year, "month": None, "mode": "year"}

    start = datetime(year, month, 1)
    end = start + relativedelta(months=1)
    return start, end, {"year": year, "month": month, "mode": "month"}


def build_dashboard_summary(db: Session, company_id: int, year: int, month: int | None) -> dict:
    sel_year = int(year)
    sel_month = int(month) if month is not None else None
    start, end, meta = _range_for_period(sel_year, sel_month)

    # ─────────────────────
    # Totais (por período selecionado)
    # ─────────────────────

    # Total de faturas emitidas no período (PAID + ISSUED, exclui CANCELED)
    invoices_total = (
        db.query(func.count(ManualInvoice.id))
        .filter(
            ManualInvoice.company_id == company_id,
            ManualInvoice.issue_date >= start,
            ManualInvoice.issue_date < end,
            ManualInvoice.status != "CANCELED",
        )
        .scalar()
        or 0
    )

    # Quantas foram pagas NO período (por paid_at)
    invoices_paid_count = (
        db.query(func.count(ManualInvoice.id))
        .filter(
            ManualInvoice.company_id == company_id,
            ManualInvoice.status == "PAID",
            ManualInvoice.paid_at.isnot(None),
            ManualInvoice.paid_at >= start,
            ManualInvoice.paid_at < end,
        )
        .scalar()
        or 0
    )

    # Total recebido NO período (por paid_at)
    revenue_paid_total = (
        db.query(func.coalesce(func.sum(ManualInvoice.total), 0.0))
        .filter(
            ManualInvoice.company_id == company_id,
            ManualInvoice.status == "PAID",
            ManualInvoice.paid_at.isnot(None),
            ManualInvoice.paid_at >= start,
            ManualInvoice.paid_at < end,
        )
        .scalar()
        or 0.0
    )

    # Total emitido e NÃO pago no período (ISSUED por issue_date)
    revenue_issued_total = (
        db.query(func.coalesce(func.sum(ManualInvoice.total), 0.0))
        .filter(
            ManualInvoice.company_id == company_id,
            ManualInvoice.status == "ISSUED",
            ManualInvoice.issue_date >= start,
            ManualInvoice.issue_date < end,
        )
        .scalar()
        or 0.0
    )

    # Despesas no período (Expense.date é timestamp, então start/end datetime ok)
    expenses_total = (
        db.query(func.coalesce(func.sum(Expense.amount), 0.0))
        .filter(
            Expense.company_id == company_id,
            Expense.date >= start,
            Expense.date < end,
        )
        .scalar()
        or 0.0
    )

    profit_total = float(revenue_paid_total) - float(expenses_total)

    appointments_total = (
        db.query(func.count(Appointment.id))
        .filter(
            Appointment.company_id == company_id,
            Appointment.scheduled_at >= start,
            Appointment.scheduled_at < end,
        )
        .scalar()
        or 0
    )

    appointments_scheduled = (
        db.query(func.count(Appointment.id))
        .filter(
            Appointment.company_id == company_id,
            Appointment.status == "SCHEDULED",
            Appointment.scheduled_at >= start,
            Appointment.scheduled_at < end,
        )
        .scalar()
        or 0
    )

    appointments_done = (
        db.query(func.count(Appointment.id))
        .filter(
            Appointment.company_id == company_id,
            Appointment.status == "DONE",
            Appointment.scheduled_at >= start,
            Appointment.scheduled_at < end,
        )
        .scalar()
        or 0
    )

    appointments_canceled = (
        db.query(func.count(Appointment.id))
        .filter(
            Appointment.company_id == company_id,
            Appointment.status == "CANCELED",
            Appointment.scheduled_at >= start,
            Appointment.scheduled_at < end,
        )
        .scalar()
        or 0
    )

    # ─────────────────────
    # IVA (corrigido e consistente)
    # ─────────────────────
    # IVA emitido no período (por issue_date) — inclui PAID+ISSUED, exclui canceladas
    vat_issued_total = (
        db.query(func.coalesce(func.sum(ManualInvoice.tax), 0.0))
        .filter(
            ManualInvoice.company_id == company_id,
            ManualInvoice.issue_date >= start,
            ManualInvoice.issue_date < end,
            ManualInvoice.status.in_(["PAID", "ISSUED"]),
        )
        .scalar()
        or 0.0
    )

    # IVA pago no período (por paid_at)
    vat_paid_total = (
        db.query(func.coalesce(func.sum(ManualInvoice.tax), 0.0))
        .filter(
            ManualInvoice.company_id == company_id,
            ManualInvoice.status == "PAID",
            ManualInvoice.paid_at.isnot(None),
            ManualInvoice.paid_at >= start,
            ManualInvoice.paid_at < end,
        )
        .scalar()
        or 0.0
    )

    # ✅ IVA pendente no período = apenas IVA das faturas EM ABERTO (ISSUED) emitidas no período
    vat_pending_total = (
        db.query(func.coalesce(func.sum(ManualInvoice.tax), 0.0))
        .filter(
            ManualInvoice.company_id == company_id,
            ManualInvoice.status == "ISSUED",
            ManualInvoice.issue_date >= start,
            ManualInvoice.issue_date < end,
        )
        .scalar()
        or 0.0
    )

    # ─────────────────────
    # Histórico 12 meses (receita/despesas + IVA)
    # ─────────────────────
    rows_paid = (
        db.query(
            extract("year", ManualInvoice.paid_at).label("y"),
            extract("month", ManualInvoice.paid_at).label("m"),
            func.sum(ManualInvoice.total).label("total"),
            func.count(ManualInvoice.id).label("cnt"),
        )
        .filter(
            ManualInvoice.company_id == company_id,
            ManualInvoice.status == "PAID",
            ManualInvoice.paid_at.isnot(None),
        )
        .group_by("y", "m")
        .all()
    )

    rows_issued = (
        db.query(
            extract("year", ManualInvoice.issue_date).label("y"),
            extract("month", ManualInvoice.issue_date).label("m"),
            func.sum(ManualInvoice.total).label("total"),
        )
        .filter(
            ManualInvoice.company_id == company_id,
            ManualInvoice.status == "ISSUED",
        )
        .group_by("y", "m")
        .all()
    )

    rows_expenses = (
        db.query(
            extract("year", Expense.date).label("y"),
            extract("month", Expense.date).label("m"),
            func.sum(Expense.amount).label("total"),
        )
        .filter(Expense.company_id == company_id)
        .group_by("y", "m")
        .all()
    )

    # IVA mensal pago (por paid_at)
    rows_vat_paid = (
        db.query(
            extract("year", ManualInvoice.paid_at).label("y"),
            extract("month", ManualInvoice.paid_at).label("m"),
            func.sum(ManualInvoice.tax).label("total"),
        )
        .filter(
            ManualInvoice.company_id == company_id,
            ManualInvoice.status == "PAID",
            ManualInvoice.paid_at.isnot(None),
        )
        .group_by("y", "m")
        .all()
    )

    # IVA mensal emitido (por issue_date) — inclui PAID+ISSUED, exclui canceladas
    rows_vat_issued = (
        db.query(
            extract("year", ManualInvoice.issue_date).label("y"),
            extract("month", ManualInvoice.issue_date).label("m"),
            func.sum(ManualInvoice.tax).label("total"),
        )
        .filter(
            ManualInvoice.company_id == company_id,
            ManualInvoice.issue_date.isnot(None),
            ManualInvoice.status.in_(["PAID", "ISSUED"]),
        )
        .group_by("y", "m")
        .all()
    )

    paid_map = {
        (int(r.y), int(r.m)): {"total": float(r.total or 0), "cnt": int(r.cnt or 0)}
        for r in rows_paid
        if r.y and r.m
    }
    issued_map = {(int(r.y), int(r.m)): float(r.total or 0) for r in rows_issued if r.y and r.m}
    expenses_map = {(int(r.y), int(r.m)): float(r.total or 0) for r in rows_expenses if r.y and r.m}
    vat_paid_map = {(int(r.y), int(r.m)): float(r.total or 0) for r in rows_vat_paid if r.y and r.m}
    vat_issued_map = {(int(r.y), int(r.m)): float(r.total or 0) for r in rows_vat_issued if r.y and r.m}

    data = []
    y, m = sel_year, (sel_month or 12)
    for _ in range(12):
        paid = paid_map.get((y, m), {"total": 0.0, "cnt": 0})
        issued = issued_map.get((y, m), 0.0)
        exp = expenses_map.get((y, m), 0.0)
        vat_paid_m = vat_paid_map.get((y, m), 0.0)
        vat_issued_m = vat_issued_map.get((y, m), 0.0)

        data.append(
            {
                "year": y,
                "month": m,
                "revenue_paid": round(paid["total"], 2),
                "revenue_issued": round(issued, 2),
                "expenses_total": round(exp, 2),
                "profit": round(paid["total"] - exp, 2),
                "count_paid": paid["cnt"],
                "vat_paid": round(vat_paid_m, 2),
                "vat_issued": round(vat_issued_m, 2),
            }
        )

        m -= 1
        if m == 0:
            m = 12
            y -= 1

    data.reverse()

    # ─────────────────────
    # Expenses por categoria (período)
    # ─────────────────────
    cat_expr = func.coalesce(func.nullif(func.trim(Expense.category), ""), "Sem categoria")

    rows_exp_cat = (
        db.query(
            cat_expr.label("category"),
            func.sum(Expense.amount).label("total"),
        )
        .filter(
            Expense.company_id == company_id,
            Expense.date >= start,
            Expense.date < end,
        )
        .group_by(cat_expr)
        .order_by(func.sum(Expense.amount).desc())
        .all()
    )

    expenses_by_category = [
        {"category": r.category, "amount": round(float(r.total or 0), 2)}
        for r in rows_exp_cat
    ]

    # ─────────────────────
    # Top fornecedores (período)
    # ─────────────────────
    rows_top_suppliers = (
        db.query(
            ManualInvoice.supplier_name,
            func.sum(ManualInvoice.total).label("total"),
            func.count(ManualInvoice.id).label("cnt"),
        )
        .filter(
            ManualInvoice.company_id == company_id,
            ManualInvoice.status == "PAID",
            ManualInvoice.paid_at.isnot(None),
            ManualInvoice.paid_at >= start,
            ManualInvoice.paid_at < end,
        )
        .group_by(ManualInvoice.supplier_name)
        .order_by(func.sum(ManualInvoice.total).desc())
        .limit(10)
        .all()
    )

    top_suppliers = [
        {"name": r.supplier_name, "amount": round(float(r.total or 0), 2), "count": int(r.cnt or 0)}
        for r in rows_top_suppliers
    ]

    return {
        "totals": {
            "invoices_total": int(invoices_total or 0),
            "invoices_paid_count": int(invoices_paid_count or 0),
            "revenue_paid_total": round(float(revenue_paid_total or 0), 2),
            "revenue_issued_total": round(float(revenue_issued_total or 0), 2),
            "expenses_total": round(float(expenses_total or 0), 2),
            "profit_total": round(float(profit_total or 0), 2),
            "appointments_total": int(appointments_total or 0),
            "appointments_scheduled": int(appointments_scheduled or 0),
            "appointments_done": int(appointments_done or 0),
            "appointments_canceled": int(appointments_canceled or 0),

            # ✅ IVA correto
            "vat_issued_total": round(float(vat_issued_total or 0), 2),
            "vat_paid_total": round(float(vat_paid_total or 0), 2),
            "vat_pending_total": round(float(vat_pending_total or 0), 2),
        },
        "revenue_by_month": data,
        "expenses_by_category": expenses_by_category,
        "top_suppliers": top_suppliers,
        "top_services": [],
        "selected_period": {"year": sel_year, "month": sel_month},
        "mode": meta["mode"],
    }
