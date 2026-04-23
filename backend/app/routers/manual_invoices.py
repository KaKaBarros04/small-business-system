# app/routers/manual_invoices.py

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.core.deps import get_db
from app.core.auth import get_current_user
from app.core.permission_guard import require_permission
from app.models.user import User
from app.models.client import Client
from app.models.manual_invoice import ManualInvoice
from app.models.manual_invoice_item import ManualInvoiceItem
from app.schemas.manual_invoice import (
    ManualInvoiceCreate,
    ManualInvoiceUpdate,
    ManualInvoiceOut,
    ManualInvoiceStatusUpdate,
)

from app.utils.audit import log_action

router = APIRouter(prefix="/manual-invoices", tags=["manual-invoices"])


def is_admin(user: User) -> bool:
    return (getattr(user, "role", "") or "").upper() == "ADMIN"


def calc_totals_from_items(items, tax_rate: float):
    subtotal = 0.0
    for it in items or []:
        qty = int(it["qty"]) if isinstance(it, dict) else int(it.qty)
        unit_price = float(it["unit_price"]) if isinstance(it, dict) else float(it.unit_price)
        subtotal += qty * unit_price

    tr = float(tax_rate or 0.0)
    tax = subtotal * (tr / 100.0)
    total = subtotal + tax
    return round(subtotal, 2), round(tax, 2), round(total, 2)


def inv_to_dict(inv: ManualInvoice):
    return {
        "id": inv.id,
        "company_id": inv.company_id,
        "client_id": getattr(inv, "client_id", None),
        "invoice_kind": getattr(inv, "invoice_kind", "MANUAL"),
        "supplier_name": inv.supplier_name,
        "invoice_number": inv.invoice_number,
        "issue_date": inv.issue_date.isoformat() if inv.issue_date else None,
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "status": inv.status,
        "paid_at": inv.paid_at.isoformat() if inv.paid_at else None,
        "subtotal": float(inv.subtotal or 0),
        "tax": float(inv.tax or 0),
        "total": float(inv.total or 0),
        "notes": inv.notes,
        "pdf_path": inv.pdf_path,
        "created_by_user_id": inv.created_by_user_id,
        "updated_by_user_id": inv.updated_by_user_id,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "updated_at": inv.updated_at.isoformat() if inv.updated_at else None,
    }


def items_to_list(inv: ManualInvoice):
    out = []
    for it in (getattr(inv, "items", None) or []):
        out.append(
            {
                "id": it.id,
                "description": it.description,
                "qty": int(it.qty) if it.qty is not None else None,
                "unit_price": float(it.unit_price or 0),
                "line_total": float(it.line_total or 0),
            }
        )
    return out


def _validate_invoice_transition(current_status: str, target_status: str, current_user: User, invoice_number: str | None):
    current = (current_status or "").upper()
    target = (target_status or "").upper()

    if current == "DRAFT":
        if target == "ISSUED" and not (invoice_number or "").strip():
            raise HTTPException(status_code=400, detail="Para emitir a fatura, informe o número da fatura.")
        if target not in ("DRAFT", "ISSUED", "CANCELED"):
            raise HTTPException(status_code=400, detail="Transição inválida para este status.")

    elif current == "ISSUED":
        if target not in ("ISSUED", "PAID", "CANCELED"):
            raise HTTPException(status_code=400, detail="Transição inválida para este status.")

    elif current in ("PAID", "CANCELED"):
        if target == "ISSUED" and not is_admin(current_user):
            raise HTTPException(status_code=403, detail="Só admin pode reabrir faturas PAID/CANCELED.")
        if target not in ("ISSUED", current):
            raise HTTPException(status_code=400, detail="Transição inválida para este status.")


def create_contract_draft_invoice(
    *,
    db: Session,
    current_user: User,
    client: Client,
    issue_date: datetime,
    yearly_base_value: float,
    tax_rate: float = 23.0,
    notes: str | None = None,
) -> ManualInvoice:
    """
    Helper interno para criar pré-fatura automática de contrato.
    """
    subtotal = round(float(yearly_base_value or 0), 2)
    tax = round(subtotal * (float(tax_rate or 0) / 100.0), 2)
    total = round(subtotal + tax, 2)

    supplier_name = (
        (getattr(client, "business_name", None) or "").strip()
        or (getattr(client, "name", None) or "").strip()
        or f"Cliente {client.id}"
    )

    issue_dt = issue_date if isinstance(issue_date, datetime) else datetime.combine(issue_date, datetime.min.time())

    inv = ManualInvoice(
        company_id=current_user.company_id,
        client_id=client.id,
        invoice_kind="CONTRACT",
        supplier_name=supplier_name,
        invoice_number=None,
        issue_date=issue_dt,
        due_date=None,
        status="DRAFT",
        paid_at=None,
        subtotal=subtotal,
        tax=tax,
        total=total,
        notes=notes.strip() if notes else None,
        created_by_user_id=current_user.id,
        updated_by_user_id=None,
        created_at=datetime.utcnow(),
    )

    inv.items.append(
        ManualInvoiceItem(
            company_id=current_user.company_id,
            description=f"Contrato anual de controlo de pragas ({issue_dt.strftime('%d/%m/%Y')})",
            qty=1,
            unit_price=subtotal,
            line_total=subtotal,
        )
    )

    db.add(inv)
    db.flush()
    return inv


@router.post("", response_model=ManualInvoiceOut, status_code=status.HTTP_201_CREATED)
def create_manual_invoice(
    payload: ManualInvoiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "invoices", "create")

    if not payload.items or len(payload.items) == 0:
        raise HTTPException(status_code=400, detail="Adiciona pelo menos 1 item.")

    status_value = (payload.status or "ISSUED").upper()
    invoice_number = (payload.invoice_number or "").strip() or None

    if status_value == "ISSUED" and not invoice_number:
        raise HTTPException(status_code=400, detail="Número da fatura é obrigatório quando o status é ISSUED.")

    if payload.client_id is not None:
        client = (
            db.query(Client)
            .filter(Client.id == payload.client_id, Client.company_id == current_user.company_id)
            .first()
        )
        if not client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
    else:
        client = None

    subtotal, tax, total = calc_totals_from_items(payload.items, payload.tax_rate or 0.0)

    inv = ManualInvoice(
        company_id=current_user.company_id,
        client_id=payload.client_id,
        invoice_kind=(payload.invoice_kind or "MANUAL").upper(),
        supplier_name=payload.supplier_name.strip(),
        invoice_number=invoice_number,
        issue_date=payload.issue_date,
        due_date=payload.due_date,
        status=status_value,
        subtotal=subtotal,
        tax=tax,
        total=total,
        notes=payload.notes.strip() if payload.notes else None,
        created_by_user_id=current_user.id,
        updated_by_user_id=None,
        created_at=datetime.utcnow(),
        paid_at=datetime.utcnow() if status_value == "PAID" else None,
    )

    for it in payload.items or []:
        qty = int(it.qty)
        unit = float(it.unit_price)
        inv.items.append(
            ManualInvoiceItem(
                company_id=current_user.company_id,
                description=it.description.strip(),
                qty=qty,
                unit_price=unit,
                line_total=round(qty * unit, 2),
            )
        )

    try:
        db.add(inv)
        db.flush()

        log_action(
            db=db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            action="CREATE",
            entity="manual_invoices",
            entity_id=inv.id,
            old_values=None,
            new_values={**inv_to_dict(inv), "items": items_to_list(inv)},
        )

        db.commit()
        db.refresh(inv)

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Já existe uma fatura com esse número nesta empresa.")

    return (
        db.query(ManualInvoice)
        .options(joinedload(ManualInvoice.items), joinedload(ManualInvoice.client))
        .filter(ManualInvoice.id == inv.id, ManualInvoice.company_id == current_user.company_id)
        .first()
    )


@router.get("", response_model=list[ManualInvoiceOut])
def list_manual_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "invoices", "view")

    return (
        db.query(ManualInvoice)
        .options(joinedload(ManualInvoice.items), joinedload(ManualInvoice.client))
        .filter(ManualInvoice.company_id == current_user.company_id)
        .order_by(ManualInvoice.issue_date.desc(), ManualInvoice.id.desc())
        .all()
    )


@router.get("/{invoice_id}", response_model=ManualInvoiceOut)
def get_manual_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "invoices", "view")

    inv = (
        db.query(ManualInvoice)
        .options(joinedload(ManualInvoice.items), joinedload(ManualInvoice.client))
        .filter(ManualInvoice.id == invoice_id, ManualInvoice.company_id == current_user.company_id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")
    return inv


@router.put("/{invoice_id}", response_model=ManualInvoiceOut)
def update_manual_invoice(
    invoice_id: int,
    payload: ManualInvoiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "invoices", "edit")

    inv = (
        db.query(ManualInvoice)
        .options(joinedload(ManualInvoice.items), joinedload(ManualInvoice.client))
        .filter(
            ManualInvoice.id == invoice_id,
            ManualInvoice.company_id == current_user.company_id,
        )
        .first()
    )

    if not inv:
        raise HTTPException(status_code=404, detail="Fatura não encontrada.")

    old_data = {**inv_to_dict(inv), "items": items_to_list(inv)}

    if payload.client_id is not None:
        client = (
            db.query(Client)
            .filter(Client.id == payload.client_id, Client.company_id == current_user.company_id)
            .first()
        )
        if not client:
            raise HTTPException(status_code=404, detail="Cliente não encontrado")
        inv.client_id = payload.client_id

    if payload.invoice_kind is not None:
        inv.invoice_kind = payload.invoice_kind.upper()

    if payload.supplier_name is not None:
        inv.supplier_name = payload.supplier_name.strip()

    if payload.invoice_number is not None:
        inv.invoice_number = payload.invoice_number.strip() if payload.invoice_number else None

    if payload.issue_date is not None:
        inv.issue_date = payload.issue_date
    if payload.due_date is not None:
        inv.due_date = payload.due_date
    if payload.notes is not None:
        inv.notes = payload.notes.strip() if payload.notes else None

    if payload.items is not None:
        inv.items.clear()
        for it in payload.items:
            qty = int(it.qty)
            unit = float(it.unit_price)
            inv.items.append(
                ManualInvoiceItem(
                    company_id=current_user.company_id,
                    description=it.description.strip(),
                    qty=qty,
                    unit_price=unit,
                    line_total=round(qty * unit, 2),
                )
            )

    if payload.tax_rate is not None or payload.items is not None:
        tax_rate = payload.tax_rate if payload.tax_rate is not None else 0.0
        subtotal, tax, total = calc_totals_from_items(
            [{"qty": it.qty, "unit_price": it.unit_price} for it in inv.items],
            tax_rate,
        )
        inv.subtotal = subtotal
        inv.tax = tax
        inv.total = total

    if payload.status is not None:
        target_status = payload.status.upper()
        _validate_invoice_transition(inv.status, target_status, current_user, inv.invoice_number)
        inv.status = target_status
        if target_status == "PAID":
            inv.paid_at = datetime.utcnow()
        elif target_status != "PAID":
            inv.paid_at = None

    inv.updated_by_user_id = current_user.id
    inv.updated_at = datetime.utcnow()

    new_data = {**inv_to_dict(inv), "items": items_to_list(inv)}

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="UPDATE",
        entity="manual_invoices",
        entity_id=inv.id,
        old_values=old_data,
        new_values=new_data,
    )

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Já existe uma fatura com esse número nesta empresa.",
        )

    db.refresh(inv)
    return inv


@router.patch("/{invoice_id}/status", response_model=ManualInvoiceOut)
def update_manual_invoice_status(
    invoice_id: int,
    data: ManualInvoiceStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "invoices", "edit")

    inv = (
        db.query(ManualInvoice)
        .filter(ManualInvoice.id == invoice_id, ManualInvoice.company_id == current_user.company_id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")

    old_data = inv_to_dict(inv)
    target = data.status.upper()

    _validate_invoice_transition(inv.status, target, current_user, inv.invoice_number)

    inv.status = target
    if target == "PAID":
        inv.paid_at = datetime.utcnow()
    elif target != "PAID":
        inv.paid_at = None

    inv.updated_by_user_id = current_user.id
    inv.updated_at = datetime.utcnow()

    new_data = inv_to_dict(inv)

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="UPDATE",
        entity="manual_invoices",
        entity_id=inv.id,
        old_values=old_data,
        new_values=new_data,
    )

    db.commit()
    db.refresh(inv)

    return (
        db.query(ManualInvoice)
        .options(joinedload(ManualInvoice.items), joinedload(ManualInvoice.client))
        .filter(ManualInvoice.id == invoice_id, ManualInvoice.company_id == current_user.company_id)
        .first()
    )


@router.delete("/{invoice_id}", status_code=204)
def delete_manual_invoice(
    invoice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "invoices", "delete")

    inv = db.query(ManualInvoice).filter(
        ManualInvoice.id == invoice_id,
        ManualInvoice.company_id == current_user.company_id,
    ).first()
    if not inv:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")

    if inv.status not in ("DRAFT", "ISSUED"):
        raise HTTPException(status_code=400, detail="Só pode apagar faturas DRAFT ou ISSUED.")

    if not is_admin(current_user):
        raise HTTPException(status_code=403, detail="Só admin pode apagar faturas.")

    old_data = {**inv_to_dict(inv), "items": items_to_list(inv)}

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="DELETE",
        entity="manual_invoices",
        entity_id=inv.id,
        old_values=old_data,
        new_values=None,
    )

    db.delete(inv)
    db.commit()
    return None


@router.post("/{invoice_id}/pdf", response_model=ManualInvoiceOut)
def upload_manual_invoice_pdf(
    invoice_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "invoices", "edit")

    inv = (
        db.query(ManualInvoice)
        .filter(ManualInvoice.id == invoice_id, ManualInvoice.company_id == current_user.company_id)
        .first()
    )
    if not inv:
        raise HTTPException(status_code=404, detail="Fatura não encontrada")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Apenas PDF é permitido")

    old_data = inv_to_dict(inv)

    base_dir = Path(__file__).resolve().parents[2]
    out_dir = base_dir / "uploads" / "manual_invoices" / str(current_user.company_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_number = (inv.invoice_number or f"draft_{inv.id}").replace("/", "-")
    safe_name = f"manual_{inv.id}_{safe_number}.pdf"
    abs_path = out_dir / safe_name
    abs_path.write_bytes(file.file.read())

    inv.pdf_path = f"/uploads/manual_invoices/{current_user.company_id}/{safe_name}"
    inv.updated_by_user_id = current_user.id
    inv.updated_at = datetime.utcnow()

    new_data = inv_to_dict(inv)

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="UPDATE",
        entity="manual_invoices",
        entity_id=inv.id,
        old_values=old_data,
        new_values=new_data,
    )

    db.commit()
    db.refresh(inv)

    return (
        db.query(ManualInvoice)
        .options(joinedload(ManualInvoice.items), joinedload(ManualInvoice.client))
        .filter(ManualInvoice.id == invoice_id, ManualInvoice.company_id == current_user.company_id)
        .first()
    )