
from datetime import datetime, time, date
from dateutil.relativedelta import relativedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from app.core.auth import get_current_user
from app.core.deps import get_db
from app.core.permission_guard import require_permission
from app.models.user import User
from app.models.client import Client
from app.models.appointment import Appointment
from app.models.contract import Contract
from app.models.manual_invoice import ManualInvoice
from app.models.manual_invoice_item import ManualInvoiceItem
from app.models.monitoring_visit import MonitoringVisit
from app.models.monitoring_point_result import MonitoringPointResult
from app.models.site_map import SiteMap
from app.models.site_map_point import SiteMapPoint
from app.models.service import Service
from app.schemas.client import ClientCreate, ClientUpdate, ClientOut
from app.utils.audit import log_action
from app.models.company import Company
from app.integrations.google_calendar import safe_resync, delete_event

router = APIRouter(prefix="/clients", tags=["clients"])


IVA_RATE_DEFAULT = 23.0
DESINFEX_NAME = "desinfex"
DESINFEX_CLIENT_CODE_START = 70161


class ContractRenewPayload(BaseModel):
    renew_start_date: date | None = None
    visits_per_year: int | None = Field(default=None, ge=1, le=12)
    contract_value_yearly: float | None = Field(default=None, ge=0)
    replace: bool = True


class ClientBulkDeletePayload(BaseModel):
    ids: list[int] = Field(default_factory=list)
    force: bool = False


def _round_money(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 2)


def _apply_iva(value: float | None, iva_rate: float = IVA_RATE_DEFAULT) -> float | None:
    if value is None:
        return None

    base = float(value)
    total = base * (1 + iva_rate / 100)
    return round(total, 2)


def _calc_contract_prices(
    yearly_base_value: float | None,
    visits_per_year: int | None,
    iva_rate: float = IVA_RATE_DEFAULT,
) -> dict:
    yearly_base = float(yearly_base_value or 0)
    visits = int(visits_per_year or 0)

    yearly_iva = 0.0
    yearly_total = 0.0
    per_visit_base = 0.0
    per_visit_iva = 0.0
    per_visit_total = 0.0

    if yearly_base > 0:
        yearly_iva = round(yearly_base * (iva_rate / 100), 2)
        yearly_total = round(yearly_base + yearly_iva, 2)

    if yearly_base > 0 and visits > 0:
        per_visit_base = round(yearly_base / visits, 2)
        per_visit_iva = round(per_visit_base * (iva_rate / 100), 2)
        per_visit_total = round(per_visit_base + per_visit_iva, 2)

    return {
        "yearly_base": round(yearly_base, 2),
        "yearly_iva": yearly_iva,
        "yearly_total": yearly_total,
        "per_visit_base": per_visit_base,
        "per_visit_iva": per_visit_iva,
        "per_visit_total": per_visit_total,
        "iva_rate": iva_rate,
    }


def _is_desinfex_company(db: Session, company_id: int) -> bool:
    company = (
        db.query(Company)
        .filter(Company.id == company_id)
        .first()
    )
    if not company:
        return False

    return (getattr(company, "name", "") or "").strip().lower() == DESINFEX_NAME


def _generate_next_desinfex_client_code(db: Session, company_id: int) -> str:
    rows = (
        db.query(Client.client_code)
        .filter(
            Client.company_id == company_id,
            Client.client_code.isnot(None),
        )
        .all()
    )

    numeric_codes = []
    for row in rows:
        raw = str(row[0]).strip() if row and row[0] is not None else ""
        if raw.isdigit():
            numeric_codes.append(int(raw))

    if not numeric_codes:
        return str(DESINFEX_CLIENT_CODE_START)

    return str(max(numeric_codes) + 1)


def _resolve_client_code(db: Session, company_id: int, payload_client_code: str | None) -> str | None:
    if payload_client_code is not None and str(payload_client_code).strip():
        return str(payload_client_code).strip()

    if _is_desinfex_company(db, company_id):
        return _generate_next_desinfex_client_code(db, company_id)

    return None


def client_to_dict(c: Client):
    prices = _calc_contract_prices(
        yearly_base_value=getattr(c, "contract_value_yearly", None),
        visits_per_year=getattr(c, "visits_per_year", None),
    )

    return {
        "id": c.id,
        "company_id": c.company_id,
        "name": c.name,
        "email": c.email,
        "phone": c.phone,
        "client_code": getattr(c, "client_code", None),
        "business_name": getattr(c, "business_name", None),
        "contact_name": getattr(c, "contact_name", None),
        "nickname": getattr(c, "nickname", None),
        "vat_number": getattr(c, "vat_number", None),
        "address": getattr(c, "address", None),
        "postal_code": getattr(c, "postal_code", None),
        "city": getattr(c, "city", None),
        "pest_type": getattr(c, "pest_type", None),
        "notes": getattr(c, "notes", None),
        "has_contract": bool(getattr(c, "has_contract", False)),
        "contract_start_date": c.contract_start_date.isoformat() if getattr(c, "contract_start_date", None) else None,
        "visits_per_year": getattr(c, "visits_per_year", None),
        "contract_value_yearly": float(getattr(c, "contract_value_yearly", 0) or 0),
        "contract_value_yearly_iva": prices["yearly_iva"],
        "contract_value_yearly_total": prices["yearly_total"],
        "contract_visit_value_base": prices["per_visit_base"],
        "contract_visit_value_iva": prices["per_visit_iva"],
        "contract_visit_value_total": prices["per_visit_total"],
        "is_active": bool(getattr(c, "is_active", True)),
        "created_at": getattr(c, "created_at", None).isoformat() if getattr(c, "created_at", None) else None,
    }


def _pick_default_service(db: Session, company_id: int) -> Service | None:
    return (
        db.query(Service)
        .filter(Service.company_id == company_id)
        .order_by(Service.id.asc())
        .first()
    )


def _calc_visit_dates(start_date, visits_per_year: int):
    v = max(0, min(int(visits_per_year or 0), 12))
    if v == 0 or not start_date:
        return []

    dates = []
    for i in range(v):
        month_offset = int(round(i * 12 / v))
        dates.append(start_date + relativedelta(months=month_offset))

    uniq = []
    seen = set()
    for d in dates:
        k = (d.year, d.month, d.day)
        if k not in seen:
            seen.add(k)
            uniq.append(d)

    return uniq[:v]


def _parse_service_from_notes(notes: str) -> dict:
    if not notes:
        return {}

    out = {}
    for raw in str(notes).splitlines():
        line = raw.strip()
        u = line.upper()

        if u.startswith("SERVICE_ADDR:"):
            out["service_address"] = line.split(":", 1)[1].strip()
        elif u.startswith("SERVICE_PC:"):
            out["service_postal_code"] = line.split(":", 1)[1].strip()
        elif u.startswith("SERVICE_CITY:"):
            out["service_city"] = line.split(":", 1)[1].strip()

    return {k: v for k, v in out.items() if v}


def _pick_service_address_from_client(client: Client) -> str:
    notes = (getattr(client, "notes", None) or "").strip()
    tagged = _parse_service_from_notes(notes)

    addr = (
        getattr(client, "service_address", None)
        or tagged.get("service_address")
        or getattr(client, "address", None)
        or ""
    ).strip()

    pc = (
        getattr(client, "service_postal_code", None)
        or tagged.get("service_postal_code")
        or getattr(client, "postal_code", None)
        or ""
    ).strip()

    city = (
        getattr(client, "service_city", None)
        or tagged.get("service_city")
        or getattr(client, "city", None)
        or ""
    ).strip()

    line2 = " ".join([x for x in [pc, city] if x]).strip()
    if addr and line2:
        return f"{addr} • {line2}"
    return addr or line2 or ""


def _create_contract_appointments(
    db: Session,
    *,
    current_user: User,
    client: Client,
    replace_existing: bool = False,
) -> list[int]:
    if not client.has_contract:
        raise HTTPException(status_code=400, detail="Cliente está sem contrato.")
    if not client.is_active:
        raise HTTPException(status_code=400, detail="Cliente está inativo.")
    if not client.contract_start_date:
        raise HTTPException(status_code=400, detail="Falta data de início do contrato.")
    if not client.visits_per_year or int(client.visits_per_year) < 1:
        raise HTTPException(status_code=400, detail="Visitas por ano inválidas (1 a 12).")

    service = _pick_default_service(db, current_user.company_id)
    if not service:
        raise HTTPException(
            status_code=400,
            detail="Não existe nenhum serviço cadastrado para criar visitas do contrato.",
        )

    if replace_existing:
        db.query(Appointment).filter(
            Appointment.company_id == current_user.company_id,
            Appointment.client_id == client.id,
            Appointment.is_contract_visit == True,  # noqa: E712
        ).delete(synchronize_session=False)

    dates = _calc_visit_dates(client.contract_start_date, int(client.visits_per_year))
    created_ids: list[int] = []

    client_notes = (getattr(client, "notes", None) or "").strip() or None
    appt_address = _pick_service_address_from_client(client)

    prices = _calc_contract_prices(
        yearly_base_value=getattr(client, "contract_value_yearly", 0),
        visits_per_year=getattr(client, "visits_per_year", 0),
    )

    per_visit_price_base = prices["per_visit_base"]

    for d in dates:
        appt = Appointment(
            company_id=current_user.company_id,
            user_id=current_user.id,
            client_id=client.id,
            service_id=service.id,
            scheduled_at=datetime.combine(d, time(9, 0)),
            address=appt_address,
            notes=client_notes,
            price=per_visit_price_base,
            status="SCHEDULED",
            is_contract_visit=True,
            service_name=getattr(service, "name", None) or "Serviço",
            service_price=per_visit_price_base,
        )
        db.add(appt)
        db.flush()
        created_ids.append(appt.id)

    return created_ids


def _sync_appointments_to_google(db: Session, company_id: int, appointment_ids: list[int]):
    if not appointment_ids:
        return

    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        return

    for appt_id in appointment_ids:
        appt_full = (
            db.query(Appointment)
            .options(joinedload(Appointment.client), joinedload(Appointment.service))
            .filter(Appointment.id == appt_id, Appointment.company_id == company_id)
            .first()
        )
        if not appt_full:
            continue

        try:
            safe_resync(db=db, appointment=appt_full, company=company)
        except Exception as e:
            appt_full.google_sync_error = str(e)[:480]
            db.add(appt_full)
            db.commit()


def _create_contract_total_draft_invoice(
    db: Session,
    *,
    current_user: User,
    client: Client,
    issue_date: date,
) -> int | None:
    if not client.has_contract:
        return None

    yearly_base = float(getattr(client, "contract_value_yearly", 0) or 0)
    if yearly_base <= 0:
        return None

    supplier_name = (
        (getattr(client, "business_name", None) or "").strip()
        or (getattr(client, "name", None) or "").strip()
        or f"Cliente {client.id}"
    )

    issue_dt = datetime.combine(issue_date, time(0, 0))
    cycle_end = issue_date + relativedelta(years=1) - relativedelta(days=1)

    prices = _calc_contract_prices(
        yearly_base_value=yearly_base,
        visits_per_year=getattr(client, "visits_per_year", 0),
    )

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
        subtotal=prices["yearly_base"],
        tax=prices["yearly_iva"],
        total=prices["yearly_total"],
        notes=f"Pré-fatura automática do contrato anual iniciada em {issue_date.strftime('%d/%m/%Y')}",
        created_by_user_id=current_user.id,
        updated_by_user_id=None,
        created_at=datetime.utcnow(),
    )

    inv.items.append(
        ManualInvoiceItem(
            company_id=current_user.company_id,
            description=(
                f"Contrato anual de controlo de pragas "
                f"({issue_date.strftime('%d/%m/%Y')} a {cycle_end.strftime('%d/%m/%Y')})"
            ),
            qty=1,
            unit_price=prices["yearly_base"],
            line_total=prices["yearly_base"],
        )
    )

    db.add(inv)
    db.flush()
    return inv.id


@router.get("", response_model=list[ClientOut])
@router.get("/", response_model=list[ClientOut])
def list_clients(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "clients", "view")

    return (
        db.query(Client)
        .filter(Client.company_id == current_user.company_id)
        .order_by(Client.id.desc())
        .all()
    )


@router.post("", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=ClientOut, status_code=status.HTTP_201_CREATED)
def create_client(
    payload: ClientCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "clients", "create")

    client = Client(
        company_id=current_user.company_id,
        name=payload.name.strip(),
        email=payload.email,
        phone=payload.phone,
        client_code=_resolve_client_code(db, current_user.company_id, payload.client_code),
        business_name=(payload.business_name.strip() if payload.business_name else None),
        contact_name=(payload.contact_name.strip() if payload.contact_name else None),
        nickname=(payload.nickname.strip() if payload.nickname else None),
        vat_number=(payload.vat_number.strip() if payload.vat_number else None),
        address=(payload.address.strip() if payload.address else None),
        postal_code=(payload.postal_code.strip() if payload.postal_code else None),
        city=(payload.city.strip() if payload.city else None),
        pest_type=(payload.pest_type.strip() if payload.pest_type else None),
        notes=(payload.notes.strip() if payload.notes else None),
        has_contract=bool(payload.has_contract),
        contract_start_date=payload.contract_start_date,
        visits_per_year=(int(payload.visits_per_year) if payload.visits_per_year is not None else None),
        contract_value_yearly=(
            _round_money(payload.contract_value_yearly)
            if getattr(payload, "contract_value_yearly", None) is not None
            else None
        ),
        is_active=(bool(payload.is_active) if payload.is_active is not None else True),
    )

    created_appt_ids: list[int] = []
    created_invoice_id: int | None = None

    try:
        db.add(client)
        db.flush()

        if client.has_contract and client.is_active and client.contract_start_date and (client.visits_per_year or 0) > 0:
            created_appt_ids = _create_contract_appointments(
                db,
                current_user=current_user,
                client=client,
                replace_existing=False,
            )

        if client.has_contract and client.is_active and client.contract_start_date and float(client.contract_value_yearly or 0) > 0:
            created_invoice_id = _create_contract_total_draft_invoice(
                db,
                current_user=current_user,
                client=client,
                issue_date=client.contract_start_date,
            )

        log_action(
            db=db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            action="CREATE",
            entity="clients",
            entity_id=client.id,
            old_values=None,
            new_values={
                **client_to_dict(client),
                "created_contract_draft_invoice_id": created_invoice_id,
            },
        )

        db.commit()
        db.refresh(client)

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email já cadastrado para outro cliente.")
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao criar cliente: {str(e)}")

    _sync_appointments_to_google(db, current_user.company_id, created_appt_ids)

    return client


@router.delete("/bulk", status_code=status.HTTP_200_OK)
def delete_clients_bulk(
    payload: ClientBulkDeletePayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "clients", "delete")

    ids = list({int(x) for x in (payload.ids or []) if x})
    if not ids:
        raise HTTPException(status_code=400, detail="Nenhum ID enviado para apagar.")

    clients = (
        db.query(Client)
        .filter(
            Client.company_id == current_user.company_id,
            Client.id.in_(ids),
        )
        .all()
    )

    if not clients:
        raise HTTPException(status_code=404, detail="Nenhum cliente encontrado.")

    found_ids = {c.id for c in clients}
    not_found_ids = sorted(list(set(ids) - found_ids))

    deleted_ids = []
    blocked = []

    try:
        for client in clients:
            old_data = client_to_dict(client)

            has_appointments = (
                db.query(Appointment.id)
                .filter(
                    Appointment.company_id == current_user.company_id,
                    Appointment.client_id == client.id,
                )
                .first()
                is not None
            )

            has_invoices = (
                db.query(ManualInvoice.id)
                .filter(
                    ManualInvoice.company_id == current_user.company_id,
                    ManualInvoice.client_id == client.id,
                )
                .first()
                is not None
            )

            has_contracts = (
                db.query(Contract.id)
                .filter(
                    Contract.company_id == current_user.company_id,
                    Contract.client_id == client.id,
                )
                .first()
                is not None
            )

            has_monitoring_visits = (
                db.query(MonitoringVisit.id)
                .filter(
                    MonitoringVisit.company_id == current_user.company_id,
                    MonitoringVisit.client_id == client.id,
                )
                .first()
                is not None
            )

            has_site_maps = (
                db.query(SiteMap.id)
                .filter(
                    SiteMap.company_id == current_user.company_id,
                    SiteMap.client_id == client.id,
                )
                .first()
                is not None
            )

            if (
                has_appointments
                or has_invoices
                or has_contracts
                or has_monitoring_visits
                or has_site_maps
            ) and not payload.force:
                blocked.append({
                    "client_id": client.id,
                    "name": client.name,
                    "reason": "Cliente tem agendamentos, faturas, contratos, monitorizações ou mapas associados. Use force=true para apagar tudo."
                })
                continue

            if payload.force:
                visit_ids = [
                    row[0]
                    for row in db.query(MonitoringVisit.id)
                    .filter(
                        MonitoringVisit.company_id == current_user.company_id,
                        MonitoringVisit.client_id == client.id,
                    )
                    .all()
                ]

                if visit_ids:
                    db.query(MonitoringPointResult).filter(
                        MonitoringPointResult.visit_id.in_(visit_ids)
                    ).delete(synchronize_session=False)

                db.query(MonitoringVisit).filter(
                    MonitoringVisit.company_id == current_user.company_id,
                    MonitoringVisit.client_id == client.id,
                ).delete(synchronize_session=False)

                site_map_ids = [
                    row[0]
                    for row in db.query(SiteMap.id)
                    .filter(
                        SiteMap.company_id == current_user.company_id,
                        SiteMap.client_id == client.id,
                    )
                    .all()
                ]

                point_ids = []
                if site_map_ids:
                    point_ids = [
                        row[0]
                        for row in db.query(SiteMapPoint.id)
                        .filter(SiteMapPoint.site_map_id.in_(site_map_ids))
                        .all()
                    ]

                if point_ids:
                    db.query(MonitoringPointResult).filter(
                        MonitoringPointResult.site_map_point_id.in_(point_ids)
                    ).delete(synchronize_session=False)

                    db.query(SiteMapPoint).filter(
                        SiteMapPoint.id.in_(point_ids)
                    ).delete(synchronize_session=False)

                if site_map_ids:
                    db.query(SiteMap).filter(
                        SiteMap.id.in_(site_map_ids)
                    ).delete(synchronize_session=False)

                invoices = (
                    db.query(ManualInvoice)
                    .filter(
                        ManualInvoice.company_id == current_user.company_id,
                        ManualInvoice.client_id == client.id,
                    )
                    .all()
                )

                for inv in invoices:
                    db.query(ManualInvoiceItem).filter(
                        ManualInvoiceItem.company_id == current_user.company_id,
                        ManualInvoiceItem.manual_invoice_id == inv.id,
                    ).delete(synchronize_session=False)

                db.query(ManualInvoice).filter(
                    ManualInvoice.company_id == current_user.company_id,
                    ManualInvoice.client_id == client.id,
                ).delete(synchronize_session=False)

                appointments = (
                    db.query(Appointment)
                    .filter(
                        Appointment.company_id == current_user.company_id,
                        Appointment.client_id == client.id,
                    )
                    .all()
                )

                for appt in appointments:
                    if appt.google_event_id:
                        try:
                            company = db.query(Company).get(appt.company_id)
                            if company:
                                delete_event(appt.google_event_id, company)
                        except Exception:
                            pass

                db.query(Appointment).filter(
                    Appointment.company_id == current_user.company_id,
                    Appointment.client_id == client.id,
                ).delete(synchronize_session=False)

                db.query(Contract).filter(
                    Contract.company_id == current_user.company_id,
                    Contract.client_id == client.id,
                ).delete(synchronize_session=False)

            log_action(
                db=db,
                company_id=current_user.company_id,
                user_id=current_user.id,
                action="DELETE",
                entity="clients",
                entity_id=client.id,
                old_values=old_data,
                new_values=None,
            )

            db.delete(client)
            deleted_ids.append(client.id)

        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Alguns clientes não puderam ser apagados por terem registos associados.",
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro ao apagar clientes em lote: {str(e)}")

    return {
        "ok": True,
        "deleted_count": len(deleted_ids),
        "deleted_ids": deleted_ids,
        "blocked": blocked,
        "not_found_ids": not_found_ids,
    }


@router.get("/{client_id}", response_model=ClientOut)
def get_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "clients", "view")

    c = (
        db.query(Client)
        .filter(Client.id == client_id, Client.company_id == current_user.company_id)
        .first()
    )
    if not c:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return c


@router.put("/{client_id}", response_model=ClientOut)
def update_client(
    client_id: int,
    payload: ClientUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "clients", "edit")

    client = (
        db.query(Client)
        .filter(Client.id == client_id, Client.company_id == current_user.company_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    old_data = client_to_dict(client)

    if payload.name is not None:
        client.name = payload.name.strip()
    if payload.email is not None:
        client.email = payload.email
    if payload.phone is not None:
        client.phone = payload.phone

    if payload.client_code is not None:
        client.client_code = payload.client_code.strip() if payload.client_code else None
    if payload.business_name is not None:
        client.business_name = payload.business_name.strip() if payload.business_name else None
    if payload.contact_name is not None:
        client.contact_name = payload.contact_name.strip() if payload.contact_name else None
    if payload.nickname is not None:
        client.nickname = payload.nickname.strip() if payload.nickname else None

    if payload.vat_number is not None:
        client.vat_number = payload.vat_number.strip() if payload.vat_number else None
    if payload.address is not None:
        client.address = payload.address.strip() if payload.address else None
    if payload.postal_code is not None:
        client.postal_code = payload.postal_code.strip() if payload.postal_code else None
    if payload.city is not None:
        client.city = payload.city.strip() if payload.city else None
    if payload.pest_type is not None:
        client.pest_type = payload.pest_type.strip() if payload.pest_type else None
    if payload.notes is not None:
        client.notes = payload.notes.strip() if payload.notes else None

    if payload.has_contract is not None:
        client.has_contract = bool(payload.has_contract)
    if payload.contract_start_date is not None:
        client.contract_start_date = payload.contract_start_date
    if payload.visits_per_year is not None:
        client.visits_per_year = int(payload.visits_per_year) if payload.visits_per_year is not None else None

    if getattr(payload, "contract_value_yearly", None) is not None:
        client.contract_value_yearly = (
            _round_money(payload.contract_value_yearly)
            if payload.contract_value_yearly is not None
            else None
        )

    if payload.is_active is not None:
        client.is_active = bool(payload.is_active)

    new_data = client_to_dict(client)

    try:
        log_action(
            db=db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            action="UPDATE",
            entity="clients",
            entity_id=client.id,
            old_values=old_data,
            new_values=new_data,
        )

        db.commit()
        db.refresh(client)

    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Email já cadastrado para outro cliente.")

    return client


@router.delete("/{client_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "clients", "delete")

    client = (
        db.query(Client)
        .filter(Client.id == client_id, Client.company_id == current_user.company_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    old_data = client_to_dict(client)

    try:
        db.delete(client)

        log_action(
            db=db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            action="DELETE",
            entity="clients",
            entity_id=client.id,
            old_values=old_data,
            new_values=None,
        )

        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Não é possível apagar este cliente porque ele tem registos associados.",
        )

    return None


@router.post("/{client_id}/contract-visits", status_code=200)
def generate_contract_visits(
    client_id: int,
    replace: bool = True,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "appointments", "create")

    client = (
        db.query(Client)
        .filter(Client.id == client_id, Client.company_id == current_user.company_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    created_ids = _create_contract_appointments(
        db,
        current_user=current_user,
        client=client,
        replace_existing=bool(replace),
    )

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="CREATE",
        entity="contract_visits",
        entity_id=client.id,
        old_values=None,
        new_values={"client_id": client.id, "created": len(created_ids), "replace": bool(replace)},
    )

    db.commit()
    _sync_appointments_to_google(db, current_user.company_id, created_ids)

    return {"ok": True, "created": len(created_ids), "synced": True}


@router.post("/{client_id}/contract/renew", status_code=200)
def renew_contract(
    client_id: int,
    payload: ContractRenewPayload | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "clients", "edit")

    payload = payload or ContractRenewPayload()

    client = (
        db.query(Client)
        .filter(Client.id == client_id, Client.company_id == current_user.company_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    if not client.has_contract:
        raise HTTPException(status_code=400, detail="Cliente está sem contrato.")
    if not client.is_active:
        raise HTTPException(status_code=400, detail="Cliente está inativo.")

    old_data = client_to_dict(client)

    renew_start = payload.renew_start_date
    if not renew_start:
        if not client.contract_start_date:
            raise HTTPException(status_code=400, detail="Falta renew_start_date e contract_start_date.")
        renew_start = client.contract_start_date + relativedelta(years=1)

    vpy = int(payload.visits_per_year) if payload.visits_per_year is not None else int(client.visits_per_year or 0)
    if vpy < 1 or vpy > 12:
        raise HTTPException(status_code=400, detail="Visitas por ano inválidas (1 a 12).")

    client.contract_start_date = renew_start
    client.visits_per_year = vpy

    if payload.contract_value_yearly is not None:
        client.contract_value_yearly = _round_money(payload.contract_value_yearly)

    cycle_end = renew_start + relativedelta(years=1)
    created_ids: list[int] = []
    created_invoice_id: int | None = None

    try:
        if bool(payload.replace):
            db.query(Appointment).filter(
                Appointment.company_id == current_user.company_id,
                Appointment.client_id == client.id,
                Appointment.is_contract_visit == True,  # noqa: E712
                Appointment.scheduled_at >= datetime.combine(renew_start, time(0, 0)),
                Appointment.scheduled_at < datetime.combine(cycle_end, time(0, 0)),
            ).delete(synchronize_session=False)
        else:
            existing = (
                db.query(Appointment.id)
                .filter(
                    Appointment.company_id == current_user.company_id,
                    Appointment.client_id == client.id,
                    Appointment.is_contract_visit == True,  # noqa: E712
                    Appointment.scheduled_at >= datetime.combine(renew_start, time(0, 0)),
                    Appointment.scheduled_at < datetime.combine(cycle_end, time(0, 0)),
                )
                .limit(1)
                .first()
            )
            if existing:
                raise HTTPException(
                    status_code=409,
                    detail="Já existem visitas de contrato neste ciclo. Use replace=true para recriar.",
                )

        created_ids = _create_contract_appointments(
            db,
            current_user=current_user,
            client=client,
            replace_existing=False,
        )

        created_invoice_id = _create_contract_total_draft_invoice(
            db,
            current_user=current_user,
            client=client,
            issue_date=renew_start,
        )

        log_action(
            db=db,
            company_id=current_user.company_id,
            user_id=current_user.id,
            action="RENEW",
            entity="contract",
            entity_id=client.id,
            old_values=old_data,
            new_values={
                "client_id": client.id,
                "renew_start_date": renew_start.isoformat(),
                "cycle_end_date": cycle_end.isoformat(),
                "visits_per_year": int(client.visits_per_year),
                "contract_value_yearly": float(client.contract_value_yearly or 0),
                "contract_value_yearly_total": _apply_iva(float(client.contract_value_yearly or 0)),
                "created": len(created_ids),
                "replace": bool(payload.replace),
                "created_contract_draft_invoice_id": created_invoice_id,
            },
        )

        db.commit()
        db.refresh(client)

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    _sync_appointments_to_google(db, current_user.company_id, created_ids)

    prices = _calc_contract_prices(
        yearly_base_value=client.contract_value_yearly,
        visits_per_year=client.visits_per_year,
    )

    return {
        "ok": True,
        "client_id": client.id,
        "renew_start_date": renew_start.isoformat(),
        "cycle_end_date": cycle_end.isoformat(),
        "visits_per_year": int(client.visits_per_year or 0),
        "contract_value_yearly": float(client.contract_value_yearly or 0),
        "contract_value_yearly_total": prices["yearly_total"],
        "contract_visit_value_base": prices["per_visit_base"],
        "contract_visit_value_iva": prices["per_visit_iva"],
        "contract_visit_value_total": prices["per_visit_total"],
        "created": len(created_ids),
        "synced": True,
        "created_contract_draft_invoice_id": created_invoice_id,
    }