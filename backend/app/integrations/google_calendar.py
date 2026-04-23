import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import joinedload
from app.models.appointment import Appointment

from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/calendar"]

try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass


# =========================
# Helpers básicos
# =========================

def _get_default_tz() -> str:
    return os.getenv("GOOGLE_CALENDAR_TIMEZONE", "Europe/Lisbon")


def _get_company_tz(company) -> str:
    tz = (getattr(company, "google_timezone", None) or "").strip()
    return tz or _get_default_tz()


def _get_company_calendar_id(company) -> str:
    cal_id = (getattr(company, "google_calendar_id", None) or "").strip()
    if not cal_id:
        raise RuntimeError("Empresa sem google_calendar_id configurado")
    return cal_id


def _get_duration_minutes_from_appointment(appointment) -> int:
    raw = getattr(appointment, "duration_minutes", None)
    try:
        m = int(raw)
    except Exception:
        m = 60
    return m if m > 0 else 60


# =========================
# Regras de cor por empresa/cliente
# =========================

# Paleta estável e curta para não virar arco-íris caótico.
# São IDs de cor de eventos do Google Calendar.
LALIMPEZAS_EVENT_COLOR_IDS = ["1", "2", "3", "4", "5", "6", "7", "9", "10", "11"]


def _normalize_text(s) -> str:
    return (str(s) if s is not None else "").strip().lower()


def _company_uses_client_colors(company) -> bool:
    mode = _normalize_text(getattr(company, "google_client_color_mode", "none"))
    return mode == "client"


def _get_client_color_seed(client) -> str:
    """
    Usa um identificador estável do cliente.
    Prioridade:
    - id
    - client_code / code
    - nome
    """
    client_id = getattr(client, "id", None)
    if client_id is not None:
        return f"id:{client_id}"

    client_code = _safe_str(getattr(client, "client_code", "")) or _safe_str(getattr(client, "code", ""))
    if client_code:
        return f"code:{client_code}"

    return f"name:{_pick_client_display_name(client)}"


def _stable_index(seed: str, modulo: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % modulo


def _get_event_color_id(company, client) -> str | None:
    """
    Só devolve cor por cliente para a LaLimpezas.
    Para as outras empresas, devolve None e o Google usa a cor normal do calendário/evento.
    """
    if not _company_uses_client_colors(company):
        return None

    seed = _get_client_color_seed(client)
    idx = _stable_index(seed, len(LALIMPEZAS_EVENT_COLOR_IDS))
    return LALIMPEZAS_EVENT_COLOR_IDS[idx]


def _get_apartment_label(appointment) -> str:
    """
    Tenta encontrar um identificador curto da unidade/fração/apartamento.
    Ajusta os campos conforme o teu model real.
    """
    candidates = [
        getattr(appointment, "apartment_name", None),
        getattr(appointment, "apartment_number", None),
        getattr(appointment, "unit_name", None),
        getattr(appointment, "unit_code", None),
        getattr(appointment, "fraction", None),
        getattr(appointment, "fração", None),
        getattr(appointment, "property_label", None),
    ]

    for c in candidates:
        s = _safe_str(c)
        if s:
            return s

    return ""


# =========================
# Service account
# =========================

def _repo_and_backend_root() -> tuple[Path, Path]:
    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if p.name.lower() == "backend":
            return (p.parent, p)
    cwd = Path.cwd().resolve()
    if (cwd / "backend").exists():
        return (cwd, (cwd / "backend").resolve())
    return (cwd, cwd)


def _resolve_service_account_path(service_file: str) -> Path:
    repo_root, backend_root = _repo_and_backend_root()
    p = Path(service_file).expanduser()
    if p.is_absolute():
        return p.resolve()

    cand1 = (repo_root / p).resolve()
    if cand1.exists():
        return cand1

    cand2 = (backend_root / p).resolve()
    if cand2.exists():
        return cand2

    return (Path.cwd() / p).resolve()


def _service():
    service_file = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not service_file:
        raise RuntimeError("GOOGLE_SERVICE_ACCOUNT_FILE não definido")

    service_path = _resolve_service_account_path(service_file)
    if not service_path.exists():
        raise FileNotFoundError(f"Service account não encontrado: {service_path}")

    creds = service_account.Credentials.from_service_account_file(
        str(service_path),
        scopes=SCOPES,
    )
    return build("calendar", "v3", credentials=creds)


# =========================
# Utils
# =========================

def _to_rfc3339(dt: datetime, tz: str) -> str:
    if dt.tzinfo is None:
        try:
            dt = dt.replace(tzinfo=ZoneInfo(tz))
        except ZoneInfoNotFoundError:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def _safe_str(x) -> str:
    return (str(x) if x is not None else "").strip()


def _first_line(s: str, max_len: int = 120) -> str:
    s = (s or "").strip().replace("\n", " ")
    s = " ".join(s.split())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1].rstrip() + "…"


def _norm_status(status: str) -> str:
    s = (status or "").upper().strip()
    aliases = {
        "DONE": "PAGO",
        "COMPLETED": "PAGO",
        "CONCLUIDO": "PAGO",
        "CONCLUÍDO": "PAGO",
        "PAID": "PAGO",
        "CANCELED": "CANCEL",
        "CANCELLED": "CANCEL",
        "CANCELADO": "CANCEL",
        "SCHEDULED": "ISSUD",
        "ISSUED": "ISSUD",
        "AGENDADO": "ISSUD",
        "PENDING": "ISSUD",
    }
    return aliases.get(s, s or "ISSUD")


def _status_label(status: str) -> str:
    s = _norm_status(status)
    if s == "ISSUD":
        return "Agendado"
    if s == "PAGO":
        return "Concluído"
    if s == "CANCEL":
        return "Cancelado"
    return s


def _status_emoji(status: str) -> str:
    s = _norm_status(status)
    if s == "PAGO":
        return "✅"
    if s == "CANCEL":
        return "❌"
    return "🕒"


def _pick_client_display_name(client) -> str:
    business_name = _safe_str(getattr(client, "business_name", "")) or _safe_str(getattr(client, "company_name", ""))
    if business_name:
        return business_name
    name = _safe_str(getattr(client, "name", "")) or _safe_str(getattr(client, "full_name", ""))
    return name or "Sem cliente"


def _build_address(appointment, client) -> str:
    a = _safe_str(getattr(appointment, "address", ""))
    if a:
        return a

    addr = _safe_str(getattr(client, "address", ""))
    pc = _safe_str(getattr(client, "postal_code", ""))
    city = _safe_str(getattr(client, "city", ""))
    parts = [p for p in [addr, f"{pc} {city}".strip()] if p]
    return " • ".join(parts).strip()


# =========================
# Event payload
# =========================

def _build_summary(appointment, client, company) -> str:
    service_name = _safe_str(getattr(appointment, "service_name", "")) or "Serviço"
    client_display = _pick_client_display_name(client)

    client_code = _safe_str(getattr(client, "client_code", "")) or _safe_str(getattr(client, "code", ""))
    left = f"{client_code} • " if client_code else ""

    apartment_label = _get_apartment_label(appointment)
    apartment_suffix = f" — {apartment_label}" if apartment_label else ""

    status = _safe_str(getattr(appointment, "status", "SCHEDULED"))

    summary = f"{_status_emoji(status)} {left}{client_display}{apartment_suffix} — {service_name}"
    return _first_line(summary, 120)


def _build_description(appointment, client, company) -> str:
    lines: list[str] = []
    lines.append(f"🏢 Empresa: {_safe_str(getattr(company, 'name', '')) or '—'}")

    client_display = _pick_client_display_name(client)
    client_code = _safe_str(getattr(client, "client_code", "")) or _safe_str(getattr(client, "code", ""))
    vat = _safe_str(getattr(client, "vat_number", "")) or _safe_str(getattr(client, "nif", ""))

    phone = _safe_str(getattr(client, "phone", ""))
    email = _safe_str(getattr(client, "email", ""))

    contact_name = _safe_str(getattr(client, "contact_name", ""))
    responsible = _safe_str(getattr(client, "name", ""))

    apartment_label = _get_apartment_label(appointment)

    lines.append("")
    lines.append("👤 Cliente")
    if client_code:
        lines.append(f"- Código: {client_code}")
    lines.append(f"- Nome: {client_display}")
    if apartment_label:
        lines.append(f"- Unidade: {apartment_label}")
    if responsible and responsible != client_display:
        lines.append(f"- Responsável: {responsible}")
    if contact_name:
        lines.append(f"- Contacto: {contact_name}")
    if vat:
        lines.append(f"- NIF: {vat}")
    if phone:
        lines.append(f"- Telefone: {phone}")
    if email:
        lines.append(f"- Email: {email}")

    address = _build_address(appointment, client)
    if address:
        lines.append("")
        lines.append("📍 Morada")
        lines.append(f"- {address}")

    service_name = _safe_str(getattr(appointment, "service_name", "")) or "Serviço"
    duration = getattr(appointment, "duration_minutes", None)
    price = getattr(appointment, "price", None)
    service_price = getattr(appointment, "service_price", None)
    status = _safe_str(getattr(appointment, "status", "SCHEDULED"))

    lines.append("")
    lines.append("🧾 Serviço")
    lines.append(f"- {service_name}")
    if duration is not None:
        lines.append(f"- Duração: {duration} min")

    val = price if price is not None else service_price
    if val is not None:
        try:
            lines.append(f"- Preço: € {float(val):.2f}")
        except Exception:
            lines.append(f"- Preço: {val}")

    lines.append(f"- Status: {_status_label(status)}")

    notes = _safe_str(getattr(appointment, "notes", ""))
    if notes:
        lines.append("")
        lines.append("📝 Notas")
        lines.append(notes)

    return "\n".join(lines).strip()


def build_event_payload(appointment, client, company) -> dict:
    tz = _get_company_tz(company)

    start_dt = getattr(appointment, "scheduled_at", None)
    if not isinstance(start_dt, datetime):
        raise RuntimeError("appointment.scheduled_at inválido para Google Calendar")

    duration_min = _get_duration_minutes_from_appointment(appointment)
    end_dt = start_dt + timedelta(minutes=duration_min)

    body = {
        "summary": _build_summary(appointment, client, company),
        "location": _build_address(appointment, client),
        "description": _build_description(appointment, client, company),
        "start": {"dateTime": _to_rfc3339(start_dt, tz), "timeZone": tz},
        "end": {"dateTime": _to_rfc3339(end_dt, tz), "timeZone": tz},
    }

    color_id = _get_event_color_id(company, client)
    if color_id:
        body["colorId"] = color_id

    return body


# =========================
# CRUD Google Calendar
# =========================

def create_event(appointment, client, company) -> dict:
    service_api = _service()
    cal_id = _get_company_calendar_id(company)
    body = build_event_payload(appointment, client, company)

    created = service_api.events().insert(
        calendarId=cal_id,
        body=body,
    ).execute()

    return {"id": created["id"], "htmlLink": created.get("htmlLink")}


def update_event(event_id: str, appointment, client, company):
    service_api = _service()
    cal_id = _get_company_calendar_id(company)
    body = build_event_payload(appointment, client, company)

    service_api.events().patch(
        calendarId=cal_id,
        eventId=event_id,
        body=body,
    ).execute()


def delete_event(event_id: str, company):
    service_api = _service()
    cal_id = _get_company_calendar_id(company)

    service_api.events().delete(
        calendarId=cal_id,
        eventId=event_id,
    ).execute()


# =========================
# Sync principal
# =========================

def sync_appointment_to_calendar(db, appointment, client, company) -> None:
    print("🚀 GOOGLE SYNC EXECUTADO | APPT:", appointment.id)
    status = _norm_status(appointment.status)

    try:
        if status == "CANCEL":
            if getattr(appointment, "google_event_id", None):
                delete_event(appointment.google_event_id, company)

            appointment.google_event_id = None
            if hasattr(appointment, "google_event_html_link"):
                appointment.google_event_html_link = None
            appointment.google_sync_error = None

            db.add(appointment)
            db.commit()
            return

        if not getattr(appointment, "google_event_id", None):
            created = create_event(appointment, client, company)

            appointment.google_event_id = created["id"]
            if hasattr(appointment, "google_event_html_link"):
                appointment.google_event_html_link = created.get("htmlLink")
            appointment.google_sync_error = None

            db.add(appointment)
            db.commit()
            return

        update_event(
            appointment.google_event_id,
            appointment,
            client,
            company,
        )

        appointment.google_sync_error = None
        db.add(appointment)
        db.commit()

    except Exception as e:
        print("❌ GOOGLE CALENDAR ERRO REAL:", repr(e))
        appointment.google_sync_error = str(e)[:480]
        db.add(appointment)
        db.commit()


def safe_resync(db, appointment, company) -> None:
    appointment = (
        db.query(Appointment)
        .options(
            joinedload(Appointment.client),
            joinedload(Appointment.service),
        )
        .filter(Appointment.id == appointment.id)
        .first()
    )

    if not appointment:
        raise RuntimeError("Appointment não encontrado para Google Calendar")

    if not appointment.client:
        raise RuntimeError("Appointment sem client para Google Calendar")

    if not _safe_str(getattr(appointment, "service_name", None)):
        svc = getattr(appointment, "service", None)
        if svc and _safe_str(getattr(svc, "name", None)):
            appointment.service_name = svc.name
        else:
            appointment.service_name = "Serviço"

        db.add(appointment)
        db.commit()
        db.refresh(appointment)

    sync_appointment_to_calendar(
        db=db,
        appointment=appointment,
        client=appointment.client,
        company=company,
    )