# routers/appointments.py
from urllib.parse import quote_plus
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload

from app.integrations.google_calendar import safe_resync, delete_event

from app.core.auth import get_current_user
from app.core.deps import get_db
from app.core.permission_guard import require_permission
from app.models.user import User
from app.models.client import Client
from app.models.service import Service
from app.models.company import Company
from app.models.appointment import Appointment
from app.schemas.appointment import AppointmentCreate, AppointmentUpdate, AppointmentOut

from app.utils.audit import log_action

router = APIRouter(prefix="/appointments", tags=["appointments"])


class BulkDeletePayload(BaseModel):
    ids: list[int] = Field(default_factory=list)


_POSTAL_RE = re.compile(r"\b\d{4}-\d{3}\b")


def _safe_str(x) -> str:
    return ("" if x is None else str(x)).strip()


def _build_google_maps_link(address: str | None) -> str | None:
    address = _safe_str(address)
    if not address:
        return None
    return f"https://www.google.com/maps/search/?api=1&query={quote_plus(address)}"


def _decorate_appt_response(appt: Appointment | None) -> Appointment | None:
    if not appt:
        return None
    try:
        appt.maps_link = _build_google_maps_link(getattr(appt, "address", None))
    except Exception:
        appt.maps_link = None
    return appt


def _parse_service_from_client_notes(notes: str) -> dict:
    """
    Tags suportadas nas notas do cliente:
      SERVICE_ADDR: Rua X nº Y
      SERVICE_PC: 1478-965
      SERVICE_CITY: Porto

    Também suporta formato:
      SERVICE_ADDR: Rua cinco 54, 4di
      1478-965, Porto
    """
    out = {"addr": "", "pc": "", "city": ""}

    if not notes:
        return out

    lines = [ln.strip() for ln in str(notes).splitlines() if ln.strip()]

    for i, line in enumerate(lines):
        u = line.upper()

        if u.startswith("SERVICE_ADDR:"):
            out["addr"] = line.split(":", 1)[1].strip()

            if i + 1 < len(lines):
                nxt = lines[i + 1].strip()
                m = _POSTAL_RE.search(nxt)
                if m and not out["pc"]:
                    out["pc"] = m.group(0)
                    tail = nxt.replace(out["pc"], "").strip(" ,")
                    if tail and not out["city"]:
                        out["city"] = tail

        elif u.startswith("SERVICE_PC:"):
            out["pc"] = line.split(":", 1)[1].strip()

        elif u.startswith("SERVICE_CITY:"):
            out["city"] = line.split(":", 1)[1].strip()

    return out


def _build_service_address_for_appointment(client: Client) -> str:
    """
    Preferência:
      1) SERVICE_* nas notas do cliente
      2) address/postal_code/city do cliente (fiscal)
    """
    notes = _safe_str(getattr(client, "notes", None))
    svc = _parse_service_from_client_notes(notes)

    fiscal_addr = _safe_str(getattr(client, "address", None))
    fiscal_pc = _safe_str(getattr(client, "postal_code", None))
    fiscal_city = _safe_str(getattr(client, "city", None))

    addr = svc["addr"] or _safe_str(getattr(client, "service_address", None)) or fiscal_addr
    pc = svc["pc"] or _safe_str(getattr(client, "service_postal_code", None)) or fiscal_pc
    city = svc["city"] or _safe_str(getattr(client, "service_city", None)) or fiscal_city

    tail = " ".join([p for p in [pc, city] if p]).strip()
    full = ", ".join([p for p in [addr, tail] if p]).strip()
    return full or fiscal_addr or ""


def appt_to_dict(a: Appointment):
    address = _safe_str(getattr(a, "address", None))
    return {
        "id": a.id,
        "company_id": a.company_id,
        "user_id": a.user_id,
        "client_id": a.client_id,
        "service_id": a.service_id,
        "scheduled_at": a.scheduled_at.isoformat() if a.scheduled_at else None,
        "address": address,
        "maps_link": _build_google_maps_link(address),
        "notes": a.notes,
        "price": float(a.price or 0),
        "status": a.status,
        "created_at": a.created_at.isoformat() if getattr(a, "created_at", None) else None,
        "updated_at": a.updated_at.isoformat() if getattr(a, "updated_at", None) else None,
        "google_event_id": getattr(a, "google_event_id", None),
        "google_sync_error": getattr(a, "google_sync_error", None),
        "service_name": getattr(a, "service_name", None),
        "service_price": getattr(a, "service_price", None),
    }


@router.post("", response_model=AppointmentOut, status_code=status.HTTP_201_CREATED)
def create_appointment(
    payload: AppointmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "appointments", "create")

    client = (
        db.query(Client)
        .filter(
            Client.id == payload.client_id,
            Client.company_id == current_user.company_id,
        )
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    service = (
        db.query(Service)
        .filter(
            Service.id == payload.service_id,
            Service.company_id == current_user.company_id,
        )
        .first()
    )
    if not service:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    price = float(payload.price) if payload.price is not None else float(service.base_price)

    appt_notes = (payload.notes or "").strip()
    if not appt_notes:
        appt_notes = (_safe_str(getattr(client, "notes", None)) or None)

    appt_address = _build_service_address_for_appointment(client)

    appt = Appointment(
        company_id=current_user.company_id,
        user_id=current_user.id,
        client_id=payload.client_id,
        service_id=payload.service_id,
        scheduled_at=payload.scheduled_at,
        address=appt_address,
        notes=appt_notes,
        price=price,
        status=payload.status or "SCHEDULED",
        service_name=payload.service_name,
        service_price=payload.service_price,
    )

    db.add(appt)
    db.flush()

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="CREATE",
        entity="appointments",
        entity_id=appt.id,
        old_values=None,
        new_values=appt_to_dict(appt),
    )

    db.commit()
    db.refresh(appt)

    appt_full = (
        db.query(Appointment)
        .options(joinedload(Appointment.client), joinedload(Appointment.service))
        .filter(Appointment.id == appt.id, Appointment.company_id == current_user.company_id)
        .first()
    )

    try:
        if not appt_full:
            raise RuntimeError("appt_full veio None (falha ao recarregar appointment)")

        company = db.query(Company).filter(Company.id == appt_full.company_id).first()
        if not company:
            raise RuntimeError(f"Company {appt_full.company_id} não encontrada para sincronizar Google Calendar")

        safe_resync(db=db, appointment=appt_full, company=company)

    except Exception as e:
        print("❌ GOOGLE SYNC FALHOU:", repr(e))
        if appt_full:
            appt_full.google_sync_error = str(e)[:480]
            db.add(appt_full)
            db.commit()

    appt_full = (
        db.query(Appointment)
        .options(joinedload(Appointment.client), joinedload(Appointment.service))
        .filter(Appointment.id == appt.id, Appointment.company_id == current_user.company_id)
        .first()
    )

    if not appt_full:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado após criação")

    return _decorate_appt_response(appt_full)


@router.get("", response_model=list[AppointmentOut])
def list_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "appointments", "view")

    rows = (
        db.query(Appointment)
        .options(joinedload(Appointment.client), joinedload(Appointment.service))
        .filter(Appointment.company_id == current_user.company_id)
        .order_by(Appointment.scheduled_at.desc())
        .all()
    )

    return [_decorate_appt_response(a) for a in rows]


@router.delete("/bulk", status_code=status.HTTP_200_OK)
def delete_appointments_bulk(
    payload: BulkDeletePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "appointments", "delete")

    ids = list({int(x) for x in (payload.ids or []) if x})
    if not ids:
        raise HTTPException(status_code=400, detail="Nenhum ID enviado para apagar.")

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.company_id == current_user.company_id,
            Appointment.id.in_(ids),
        )
        .all()
    )

    if not appointments:
        raise HTTPException(status_code=404, detail="Nenhum agendamento encontrado.")

    found_ids = {a.id for a in appointments}
    not_found_ids = sorted(list(set(ids) - found_ids))
    deleted_ids = []

    for appt in appointments:
        old_data = appt_to_dict(appt)

        if appt.google_event_id:
            try:
                company = db.query(Company).get(appt.company_id)
                if company:
                    delete_event(appt.google_event_id, company)
            except Exception:
                pass

        log_action(
            db=db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            action="DELETE",
            entity="appointments",
            entity_id=appt.id,
            old_values=old_data,
            new_values=None,
        )

        deleted_ids.append(appt.id)
        db.delete(appt)

    db.commit()

    return {
        "ok": True,
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "not_found_ids": not_found_ids,
    }


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "appointments", "view")

    appt = (
        db.query(Appointment)
        .options(joinedload(Appointment.client), joinedload(Appointment.service))
        .filter(
            Appointment.id == appointment_id,
            Appointment.company_id == current_user.company_id,
        )
        .first()
    )
    if not appt:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    return _decorate_appt_response(appt)


@router.put("/{appointment_id}", response_model=AppointmentOut)
def update_appointment(
    appointment_id: int,
    payload: AppointmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "appointments", "edit")

    appt = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.company_id == current_user.company_id,
        )
        .first()
    )
    if not appt:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    old_data = appt_to_dict(appt)
    data = payload.dict(exclude_unset=True)

    if payload.scheduled_at is not None:
        appt.scheduled_at = payload.scheduled_at

    if payload.address is not None:
        client = (
            db.query(Client)
            .filter(Client.id == appt.client_id, Client.company_id == current_user.company_id)
            .first()
        )
        if client:
            appt.address = _build_service_address_for_appointment(client)

    if payload.notes is not None:
        new_notes = (payload.notes or "").strip()
        if not new_notes:
            client = (
                db.query(Client)
                .filter(Client.id == appt.client_id, Client.company_id == current_user.company_id)
                .first()
            )
            new_notes = (_safe_str(getattr(client, "notes", None)) if client else "")
        appt.notes = new_notes or None

    if payload.price is not None:
        appt.price = float(payload.price)

    if payload.status is not None:
        appt.status = payload.status

    if "service_name" in data:
        appt.service_name = data["service_name"]

    if "service_price" in data:
        appt.service_price = data["service_price"]

    new_data = appt_to_dict(appt)

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="UPDATE",
        entity="appointments",
        entity_id=appt.id,
        old_values=old_data,
        new_values=new_data,
    )

    db.add(appt)
    db.commit()
    db.refresh(appt)

    appt_full = (
        db.query(Appointment)
        .options(joinedload(Appointment.client), joinedload(Appointment.service))
        .filter(
            Appointment.id == appointment_id,
            Appointment.company_id == current_user.company_id,
        )
        .first()
    )
    if not appt_full:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    try:
        company = db.query(Company).filter(Company.id == appt_full.company_id).first()
        if not company:
            raise RuntimeError("Company não encontrada para sincronizar Google Calendar")

        safe_resync(db=db, appointment=appt_full, company=company)

        if getattr(appt_full, "google_sync_error", None):
            appt_full.google_sync_error = None
            db.add(appt_full)
            db.commit()

    except Exception as e:
        print("❌ GOOGLE SYNC FALHOU (UPDATE):", repr(e))
        appt_full.google_sync_error = str(e)[:480]
        db.add(appt_full)
        db.commit()

    db.refresh(appt_full)
    return _decorate_appt_response(appt_full)


@router.delete("/{appointment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "appointments", "delete")

    appt = (
        db.query(Appointment)
        .filter(
            Appointment.id == appointment_id,
            Appointment.company_id == current_user.company_id,
        )
        .first()
    )
    if not appt:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    old_data = appt_to_dict(appt)

    if appt.google_event_id:
        try:
            company = db.query(Company).get(appt.company_id)
            if company:
                delete_event(appt.google_event_id, company)
        except Exception:
            pass

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="DELETE",
        entity="appointments",
        entity_id=appt.id,
        old_values=old_data,
        new_values=None,
    )

    db.delete(appt)
    db.commit()
    return None


@router.post("/{appointment_id}/sync-google", response_model=AppointmentOut)
def sync_google_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "appointments", "edit")

    appt_full = (
        db.query(Appointment)
        .options(joinedload(Appointment.client), joinedload(Appointment.service))
        .filter(
            Appointment.id == appointment_id,
            Appointment.company_id == current_user.company_id,
        )
        .first()
    )
    if not appt_full:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado")

    try:
        company = db.query(Company).filter(Company.id == appt_full.company_id).first()
        if not company:
            raise RuntimeError("Company não encontrada para sincronizar Google Calendar")

        safe_resync(db=db, appointment=appt_full, company=company)

        if getattr(appt_full, "google_sync_error", None):
            appt_full.google_sync_error = None
            db.add(appt_full)
            db.commit()

    except Exception as e:
        appt_full.google_sync_error = str(e)[:480]
        db.add(appt_full)
        db.commit()
        raise HTTPException(status_code=400, detail=f"Google sync falhou: {str(e)[:200]}")

    appt_full = (
        db.query(Appointment)
        .options(joinedload(Appointment.client), joinedload(Appointment.service))
        .filter(
            Appointment.id == appointment_id,
            Appointment.company_id == current_user.company_id,
        )
        .first()
    )
    if not appt_full:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado após sync")

    return _decorate_appt_response(appt_full)