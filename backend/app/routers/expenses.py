from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.deps import get_db
from app.core.permission_guard import require_permission
from app.models.user import User
from app.models.expense import Expense
from app.schemas.expense import ExpenseCreate, ExpenseUpdate, ExpenseOut

from app.utils.audit import log_action

router = APIRouter(prefix="/expenses", tags=["expenses"])


def exp_to_dict(exp: Expense):
    return {
        "id": exp.id,
        "company_id": exp.company_id,
        "user_id": exp.user_id,
        "date": exp.date.isoformat() if exp.date else None,
        "category": exp.category,
        "description": exp.description,
        "amount": float(exp.amount or 0),
        "created_at": exp.created_at.isoformat() if getattr(exp, "created_at", None) else None,
        "updated_at": exp.updated_at.isoformat() if getattr(exp, "updated_at", None) else None,
    }


@router.get("", response_model=list[ExpenseOut])
def list_expenses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "expenses", "view")

    return (
        db.query(Expense)
        .filter(Expense.company_id == current_user.company_id)
        .order_by(Expense.date.desc(), Expense.id.desc())
        .all()
    )


@router.post("", response_model=ExpenseOut, status_code=status.HTTP_201_CREATED)
def create_expense(
    payload: ExpenseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "expenses", "create")

    exp = Expense(
        company_id=current_user.company_id,
        user_id=current_user.id,
        date=payload.date or datetime.utcnow(),
        category=payload.category.strip(),
        description=payload.description.strip(),
        amount=float(payload.amount),
    )

    db.add(exp)
    db.flush()

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="CREATE",
        entity="expenses",
        entity_id=exp.id,
        old_values=None,
        new_values=exp_to_dict(exp),
    )

    db.commit()
    db.refresh(exp)
    return exp


@router.put("/{expense_id}", response_model=ExpenseOut)
def update_expense(
    expense_id: int,
    payload: ExpenseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "expenses", "edit")

    exp = (
        db.query(Expense)
        .filter(Expense.id == expense_id, Expense.company_id == current_user.company_id)
        .first()
    )
    if not exp:
        raise HTTPException(status_code=404, detail="Despesa não encontrada")

    old_data = exp_to_dict(exp)

    if payload.date is not None:
        exp.date = payload.date
    if payload.category is not None:
        exp.category = payload.category.strip()
    if payload.description is not None:
        exp.description = payload.description.strip()
    if payload.amount is not None:
        exp.amount = float(payload.amount)

    new_data = exp_to_dict(exp)

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="UPDATE",
        entity="expenses",
        entity_id=exp.id,
        old_values=old_data,
        new_values=new_data,
    )

    db.commit()
    db.refresh(exp)
    return exp


@router.delete("/{expense_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "expenses", "delete")

    exp = (
        db.query(Expense)
        .filter(Expense.id == expense_id, Expense.company_id == current_user.company_id)
        .first()
    )
    if not exp:
        raise HTTPException(status_code=404, detail="Despesa não encontrada")

    old_data = exp_to_dict(exp)

    db.delete(exp)

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="DELETE",
        entity="expenses",
        entity_id=exp.id,
        old_values=old_data,
        new_values=None,
    )

    db.commit()
    return None