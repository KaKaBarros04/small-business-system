from __future__ import annotations

from io import BytesIO
from pathlib import Path
from datetime import date, datetime, timedelta
from typing import Callable, Dict, Any, List, Tuple

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.lib import colors

from pypdf import PdfReader, PdfWriter

from app.models.appointment import Appointment


# =========================
# CONFIG: Ajustes de layout (mm)
# =========================
COORDS = {
    # CAPA
    "cover": {
        "client_no": (62, 137),  # (x_mm, y_mm)
        "name": (50, 126),
        "addr1": (60, 100),
        "addr2": (60, 90),
        "erase": {
            "client_no": (70, 108, 120, 10),  # x,y,w,h  (mm)
            "name": (70, 98, 130, 10),
            "addr": (70, 72, 160, 26),
        },
        "font": ("Helvetica", 11),
    },

    # CERTIFICADO
    "cert": {
        "block_erase": (40, 500, 160, 60),
        "date_erase": (48, 500, 55, 10),
        "name": (103, 138),
        "nif": (103, 125),
        "addr1": (103, 120),
        "addr2": (103, 115),
        "date": (55, 53),
        "font": ("Helvetica", 10),
    },

    # CONTRATO
    "contract": {
        "erase": {
            "left": (40, 500, 72, 48),
            "right": (118, 500, 88, 48),
            "label": (50, 500, 50, 5),
            "value": (45, 500, 75, 14),
            "visits": (95, 500, 30, 14),
            "service": (55, 500, 155, 34),
        },
        "left": {
            "nif": (31, 256),
            "phone": (40, 249),
            "email": (35, 244),
            "date": (35, 237),
        },
        "right": {
            "name": (133, 256),
            "addr1": (150, 238),
            "addr2": (150, 233),
        },
        "label": (95, 203),         # ORIGINAL/DUPLICADO
        "contract_no": (140, 203),  # Nº 7003
        "value": (50, 115),         # "200,00 EUROS"
        "visits": (119, 108),       # "03"
        "service_addr1": (40, 80),
        "service_addr2": (40, 75),
    },
}


# =========================
# Templates: nomes fixos (sem adivinhação)
# =========================
DOSSIER_DIR = Path(__file__).resolve().parent
PDF_TPL_DIR = DOSSIER_DIR / "pdf_templates"
PDF_ATTACH_DIR = DOSSIER_DIR / "pdf_annexes"

TEMPLATES = {
    "CAPA": PDF_TPL_DIR / "capa.pdf",
    "INDICE": PDF_TPL_DIR / "indice.pdf",
    "INTRO": PDF_TPL_DIR / "introducao.pdf",
    "PLANEAMENTO": PDF_TPL_DIR / "planeamento.pdf",
    "CERTIFICADO": PDF_TPL_DIR / "certificado.pdf",
    "CONTRATO_FRENTE": PDF_TPL_DIR / "contrato_frente.pdf",
    "CONTRATO_CONDICOES": PDF_TPL_DIR / "contrato_condicoes.pdf",
}

# FT primeiro, depois FDS
ANNEXES = [
    PDF_ATTACH_DIR / "FT MICROSIN.pdf",
    PDF_ATTACH_DIR / "FDS_MICROSIN.pdf",

    PDF_ATTACH_DIR / "FT RATROM 3G ISCO FRESCO.pdf",
    PDF_ATTACH_DIR / "FDS RATROM 3G ISCO FRESCO PROFISSIONAL 20230308.pdf",

    PDF_ATTACH_DIR / "Maxforce Prime FT.pdf",
    PDF_ATTACH_DIR / "Maxforce Prime FDS.pdf",
]


def _ensure_templates_exist():
    missing = [k for k, p in TEMPLATES.items() if not p.exists()]
    if missing:
        found = "\n".join(sorted([p.name for p in PDF_TPL_DIR.glob("*.pdf")]))
        raise FileNotFoundError(
            "Templates PDF em falta (confere nomes fixos):\n"
            + "\n".join(missing)
            + "\n\nFicheiros encontrados na pasta:\n"
            + (found or "(nenhum PDF encontrado)")
            + "\n\nRenomeia para:\n"
            + "\n".join([f"- {v.name}" for v in TEMPLATES.values()])
        )


# =========================
# Helpers
# =========================
def _to_int(v, default=0) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _to_float(v, default=0.0) -> float:
    try:
        if isinstance(v, str):
            v = v.replace("€", "").replace(" ", "").replace(".", "").replace(",", ".")
        return float(v)
    except Exception:
        return default


def _get_net_value_from_gross(gross_value: Any, vat_rate: Any = 0.23) -> float | None:
    """
    Recebe um valor com IVA e devolve o valor sem IVA.
    vat_rate pode vir como:
      - 0.23
      - 23
      - "0.23"
      - "23"
    """
    if gross_value in (None, ""):
        return None

    try:
        gross = _to_float(gross_value, None)
        if gross is None:
            return None

        rate = _to_float(vat_rate, 0.23)

        # Se vier 23 em vez de 0.23
        if rate > 1:
            rate = rate / 100.0

        if rate < 0:
            rate = 0.23

        return gross / (1 + rate)
    except Exception:
        return None


def _wrap_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    font="Helvetica",
    size=11,
    leading=13,
) -> float:
    if not text:
        return y
    c.setFont(font, size)
    words = str(text).split()
    line = ""
    lines: List[str] = []

    for w in words:
        test = (line + " " + w).strip()
        if stringWidth(test, font, size) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)

    yy = y
    for ln in lines:
        c.drawString(x, yy, ln)
        yy -= leading
    return yy


def _fit_text_lines(
    text: str,
    max_lines: int,
    c: canvas.Canvas,
    max_width: float,
    font="Helvetica",
    size=11,
) -> List[str]:
    if not text:
        return []

    c.setFont(font, size)

    words = str(text).split()
    lines: List[str] = []
    line = ""

    for w in words:
        test = (line + " " + w).strip()
        if stringWidth(test, font, size) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = w

    if line:
        lines.append(line)

    if len(lines) <= max_lines:
        return lines

    trimmed = lines[:max_lines]
    last = trimmed[-1]

    while last and stringWidth(last + "...", font, size) > max_width:
        parts = last.split()
        if len(parts) > 1:
            last = " ".join(parts[:-1])
        else:
            last = last[:-1]

    trimmed[-1] = (last + "...").strip()
    return trimmed


def _draw_fitted_text(
    c: canvas.Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    max_lines: int,
    font="Helvetica",
    size=11,
    leading=12,
) -> float:
    lines = _fit_text_lines(
        text=text,
        max_lines=max_lines,
        c=c,
        max_width=max_width,
        font=font,
        size=size,
    )

    c.setFont(font, size)
    yy = y
    for ln in lines:
        c.drawString(x, yy, ln)
        yy -= leading
    return yy


def _template_page_size_points(template_pdf: Path) -> Tuple[float, float]:
    r = PdfReader(str(template_pdf))
    p = r.pages[0]
    w = float(p.mediabox.width)
    h = float(p.mediabox.height)
    return w, h


def _make_overlay_for_template(template_pdf: Path, draw_fn: Callable[[canvas.Canvas, Tuple[float, float]], None]) -> bytes:
    """
    Cria overlay com o MESMO tamanho (points) do template.
    Isto corrige texto a aparecer no sítio errado por causa de CropBox/MediaBox diferentes.
    """
    w, h = _template_page_size_points(template_pdf)
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=(w, h))
    draw_fn(c, (w, h))
    c.showPage()
    c.save()
    return buf.getvalue()


def _overlay_on_template(template_pdf: Path, overlay_pdf_bytes: bytes) -> bytes:
    base = PdfReader(str(template_pdf))
    over = PdfReader(BytesIO(overlay_pdf_bytes))

    writer = PdfWriter()
    page = base.pages[0]
    page.merge_page(over.pages[0])
    writer.add_page(page)

    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _append_pdf_file(writer: PdfWriter, pdf_path: Path):
    r = PdfReader(str(pdf_path))
    for p in r.pages:
        writer.add_page(p)


def _append_pdf_bytes(writer: PdfWriter, pdf_bytes: bytes):
    r = PdfReader(BytesIO(pdf_bytes))
    for p in r.pages:
        writer.add_page(p)


def _append_common_annexes(writer: PdfWriter):
    for pdf_path in ANNEXES:
        if pdf_path.exists():
            _append_pdf_file(writer, pdf_path)


# =========================
# "Notas" -> Morada de serviço (gambiarra controlada)
# =========================
def _parse_service_from_notes(notes: str) -> Dict[str, str]:
    """
    Permite guardar morada de serviço dentro do campo notas com tags:

      SERVICE_ADDR: Rua X nº 10
      SERVICE_PC: 1000-001
      SERVICE_CITY: Lisboa
    """
    if not notes:
        return {}

    out: Dict[str, str] = {}
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


# =========================
# Overlays
# =========================
def _draw_cover_overlay(template_pdf: Path, ctx: Dict[str, Any]) -> bytes:
    cfg = COORDS["cover"]

    def draw(c: canvas.Canvas, size):
        # apagar blocos
        c.setFillColor(colors.white)
        ex, ey, ew, eh = cfg["erase"]["client_no"]
        c.rect(ex * mm, ey * mm, ew * mm, eh * mm, stroke=0, fill=1)
        ex, ey, ew, eh = cfg["erase"]["name"]
        c.rect(ex * mm, ey * mm, ew * mm, eh * mm, stroke=0, fill=1)
        ex, ey, ew, eh = cfg["erase"]["addr"]
        c.rect(ex * mm, ey * mm, ew * mm, eh * mm, stroke=0, fill=1)

        font, fsize = cfg["font"]
        c.setFillColor(colors.black)
        c.setFont(font, fsize)

        x, y = cfg["client_no"]
        c.drawString(x * mm, y * mm, str(ctx.get("client_number") or ""))

        # NOME em 2 linhas (fantasia + legal) com quebra controlada
        x, y = cfg["name"]
        fantasy = str(ctx.get("client_fantasy") or "").strip()
        legal = str(ctx.get("client_legal") or "").strip()

        maxw = 135 * mm
        start_y = y * mm

        if fantasy and legal and fantasy.lower() != legal.lower():
            y_after = _draw_fitted_text(
                c,
                fantasy,
                x * mm,
                start_y,
                max_width=maxw,
                max_lines=2,
                font="Helvetica-Bold",
                size=fsize,
                leading=10,
            )
            _draw_fitted_text(
                c,
                legal,
                x * mm,
                y_after - 1 * mm,
                max_width=maxw,
                max_lines=2,
                font="Helvetica",
                size=fsize,
                leading=10,
            )
        else:
            _draw_fitted_text(
                c,
                fantasy or legal,
                x * mm,
                start_y,
                max_width=maxw,
                max_lines=3,
                font="Helvetica-Bold",
                size=fsize,
                leading=10,
            )

        addr1 = str(ctx.get("service_address") or ctx.get("fiscal_address") or "").strip()
        addr2 = f"{ctx.get('service_postal_code') or ctx.get('postal_code') or ''} {ctx.get('service_city') or ctx.get('city') or ''}".strip()

        x, y = cfg["addr1"]
        _draw_fitted_text(
            c,
            addr1,
            x * mm,
            y * mm,
            max_width=120 * mm,
            max_lines=2,
            font=font,
            size=fsize,
            leading=11,
        )

        x, y = cfg["addr2"]
        _draw_fitted_text(
            c,
            addr2,
            x * mm,
            y * mm,
            max_width=120 * mm,
            max_lines=1,
            font=font,
            size=fsize,
            leading=11,
        )

    return _make_overlay_for_template(template_pdf, draw)


def _draw_certificate_overlay(template_pdf: Path, ctx: Dict[str, Any]) -> bytes:
    cfg = COORDS["cert"]
    font, fsize = cfg["font"]

    def draw(c: canvas.Canvas, size):
        # apagar bloco do cliente e data
        c.setFillColor(colors.white)
        ex, ey, ew, eh = cfg["block_erase"]
        c.rect(ex * mm, ey * mm, ew * mm, eh * mm, stroke=0, fill=1)
        ex, ey, ew, eh = cfg["date_erase"]
        c.rect(ex * mm, ey * mm, ew * mm, eh * mm, stroke=0, fill=1)

        c.setFillColor(colors.black)

        # NOME em 2 linhas com quebra controlada
        x, y = cfg["name"]
        fantasy = str(ctx.get("client_fantasy") or "").strip()
        legal = str(ctx.get("client_legal") or "").strip()

        maxw = 110 * mm
        start_y = y * mm

        if fantasy and legal and fantasy.lower() != legal.lower():
            y_after = _draw_fitted_text(
                c,
                fantasy,
                x * mm,
                start_y,
                max_width=maxw,
                max_lines=2,
                font="Helvetica-Bold",
                size=fsize,
                leading=9,
            )
            _draw_fitted_text(
                c,
                legal,
                x * mm,
                y_after - 1 * mm,
                max_width=maxw,
                max_lines=2,
                font=font,
                size=fsize,
                leading=9,
            )
        else:
            _draw_fitted_text(
                c,
                fantasy or legal,
                x * mm,
                start_y,
                max_width=maxw,
                max_lines=3,
                font="Helvetica-Bold",
                size=fsize,
                leading=9,
            )

        x, y = cfg["nif"]
        c.setFont(font, fsize)
        c.drawString(x * mm, y * mm, f"NIF : {ctx.get('vat_number') or ''}")

        addr1 = str(ctx.get("service_address") or ctx.get("fiscal_address") or "").strip()
        addr2 = f"{ctx.get('service_postal_code') or ctx.get('postal_code') or ''} {ctx.get('service_city') or ctx.get('city') or ''}".strip()

        x, y = cfg["addr1"]
        _draw_fitted_text(
            c,
            addr1,
            x * mm,
            y * mm,
            max_width=110 * mm,
            max_lines=2,
            font=font,
            size=fsize,
            leading=10,
        )

        x, y = cfg["addr2"]
        _draw_fitted_text(
            c,
            addr2,
            x * mm,
            y * mm,
            max_width=110 * mm,
            max_lines=1,
            font=font,
            size=fsize,
            leading=10,
        )

        x, y = cfg["date"]
        c.drawString(x * mm, y * mm, str(ctx.get("today_pt") or ""))

    return _make_overlay_for_template(template_pdf, draw)


def _draw_contract_overlay(template_pdf: Path, ctx: Dict[str, Any], variant: str) -> bytes:
    cfg = COORDS["contract"]

    def draw(c: canvas.Canvas, size):
        # apagar áreas
        c.setFillColor(colors.white)
        for _, (ex, ey, ew, eh) in cfg["erase"].items():
            c.rect(ex * mm, ey * mm, ew * mm, eh * mm, stroke=0, fill=1)

        c.setFillColor(colors.black)
        c.setFont("Helvetica", 10)

        # left block
        c.drawString(cfg["left"]["nif"][0] * mm, cfg["left"]["nif"][1] * mm, str(ctx.get("vat_number") or ""))
        c.drawString(cfg["left"]["phone"][0] * mm, cfg["left"]["phone"][1] * mm, str(ctx.get("phone") or ""))
        c.drawString(cfg["left"]["email"][0] * mm, cfg["left"]["email"][1] * mm, str(ctx.get("email") or ""))
        c.drawString(cfg["left"]["date"][0] * mm, cfg["left"]["date"][1] * mm, str(ctx.get("today_pt") or ""))

        # right block (nome fantasia + legal com quebra controlada) + morada fiscal
        nx = cfg["right"]["name"][0] * mm
        ny = cfg["right"]["name"][1] * mm
        fantasy = str(ctx.get("client_fantasy") or "").strip()
        legal = str(ctx.get("client_legal") or "").strip()
        maxw = 68 * mm  # um pouco menor para dar mais folga à direita

        if fantasy and legal and fantasy.lower() != legal.lower():
            y_after = _draw_fitted_text(
                c,
                fantasy,
                nx,
                ny,
                max_width=maxw,
                max_lines=2,
                font="Helvetica-Bold",
                size=10,
                leading=9,
            )
            _draw_fitted_text(
                c,
                legal,
                nx,
                y_after - 1 * mm,
                max_width=maxw,
                max_lines=2,
                font="Helvetica",
                size=10,
                leading=9,
            )
        else:
            _draw_fitted_text(
                c,
                fantasy or legal,
                nx,
                ny,
                max_width=maxw,
                max_lines=3,
                font="Helvetica-Bold",
                size=10,
                leading=9,
            )

        fiscal1 = str(ctx.get("fiscal_address") or "").strip()
        fiscal2 = f"{ctx.get('postal_code') or ''} {ctx.get('city') or ''}".strip()

        # morada fiscal:
        fiscal_x = 147 * mm
        fiscal1_y = 238 * mm
        fiscal2_y = 228 * mm
        fiscal_maxw = 55 * mm

        _draw_fitted_text(
            c,
            fiscal1,
            fiscal_x,
            fiscal1_y,
            max_width=fiscal_maxw,
            max_lines=2,
            font="Helvetica",
            size=9,
            leading=8.5,
        )

        _draw_fitted_text(
            c,
            fiscal2,
            fiscal_x,
            fiscal2_y,
            max_width=fiscal_maxw,
            max_lines=1,
            font="Helvetica",
            size=9,
            leading=8.5,
        )

        # label ORIGINAL/DUPLICADO
        c.setFont("Helvetica-Bold", 10)
        label = "DUPLICADO" if variant == "duplicado" else "ORIGINAL"
        c.drawString(cfg["label"][0] * mm, cfg["label"][1] * mm, label)

        # Nº contrato
        c.setFont("Helvetica-Bold", 11)
        c.drawString(cfg["contract_no"][0] * mm, cfg["contract_no"][1] * mm, f"Nº {ctx.get('client_number') or ''}")

        # value SEM IVA
        value = str(ctx.get("contract_value_yearly") or "").strip()
        c.setFont("Helvetica", 11)
        if value:
            value_lines = _fit_text_lines(
                f"{value} EUROS",
                max_lines=1,
                c=c,
                max_width=60 * mm,
                font="Helvetica",
                size=11,
            )
            if value_lines:
                c.drawString(cfg["value"][0] * mm, cfg["value"][1] * mm, value_lines[0])

        # visits
        visits = _to_int(ctx.get("visits_per_year"), 0)
        c.setFont("Helvetica-Bold", 11)
        if visits:
            c.drawString(cfg["visits"][0] * mm, cfg["visits"][1] * mm, f"{visits:02d}")

        # service address (morada de serviço)
        service1 = str(ctx.get("service_address") or fiscal1).strip()
        service2 = f"{ctx.get('service_postal_code') or ctx.get('postal_code') or ''} {ctx.get('service_city') or ctx.get('city') or ''}".strip()

        c.setFont("Helvetica", 10)
        _draw_fitted_text(
            c,
            service1,
            cfg["service_addr1"][0] * mm,
            cfg["service_addr1"][1] * mm,
            max_width=120 * mm,
            max_lines=2,
            font="Helvetica",
            size=10,
            leading=10,
        )

        _draw_fitted_text(
            c,
            service2,
            cfg["service_addr2"][0] * mm,
            cfg["service_addr2"][1] * mm,
            max_width=120 * mm,
            max_lines=1,
            font="Helvetica",
            size=10,
            leading=10,
        )

    return _make_overlay_for_template(template_pdf, draw)


# =========================
# Builder principal
# =========================
def build_client_dossier_pdf(db, client) -> bytes:
    _ensure_templates_exist()

    client_number = getattr(client, "client_code", None) or getattr(client, "id", "") or ""

    # agora usamos 2 nomes:
    # - fantasia (letreiro): business_name
    # - legal (LDA): name
    client_fantasy = (getattr(client, "business_name", None) or "").strip()
    client_legal = (getattr(client, "name", None) or "").strip()

    # fallback (se um vier vazio)
    if not client_fantasy and client_legal:
        client_fantasy = client_legal
    if not client_legal and client_fantasy:
        client_legal = client_fantasy

    vat_number = getattr(client, "vat_number", None) or ""
    email = getattr(client, "email", None) or ""
    phone = getattr(client, "phone", None) or ""

    fiscal_address = getattr(client, "address", None) or ""
    postal_code = getattr(client, "postal_code", None) or ""
    city = getattr(client, "city", None) or ""

    # ==========================================================
    # Morada de serviço via "notas" (SERVICE_ADDR / SERVICE_PC / SERVICE_CITY)
    # tenta ler de client.service_* (se existir) -> senão busca nas notas -> senão usa fiscal
    # ==========================================================
    notes = (
        getattr(client, "notes", None)
        or getattr(client, "note", None)
        or getattr(client, "observations", None)
        or getattr(client, "obs", None)
        or ""
    )
    service_from_notes = _parse_service_from_notes(notes)

    service_address = (
        getattr(client, "service_address", None)
        or service_from_notes.get("service_address")
        or fiscal_address
    )
    service_postal_code = (
        getattr(client, "service_postal_code", None)
        or service_from_notes.get("service_postal_code")
        or postal_code
    )
    service_city = (
        getattr(client, "service_city", None)
        or service_from_notes.get("service_city")
        or city
    )

    visits_per_year = getattr(client, "visits_per_year", None) or 0

    # ==========================================================
    # VALOR DO CONTRATO: o campo actual já está SEM IVA
    # aqui usamos o valor diretamente, sem converter
    # ==========================================================
    contract_value_yearly_base = getattr(client, "contract_value_yearly", None)

    # DATA DO CONTRATO = data de início definida (contract_start_date)
    contract_start = getattr(client, "contract_start_date", None)
    if isinstance(contract_start, str):
        try:
            contract_start_dt = datetime.fromisoformat(contract_start[:10]).date()
        except Exception:
            contract_start_dt = None
    elif isinstance(contract_start, datetime):
        contract_start_dt = contract_start.date()
    elif isinstance(contract_start, date):
        contract_start_dt = contract_start
    else:
        contract_start_dt = None

    contract_date_pt = (contract_start_dt or date.today()).strftime("%d/%m/%Y")

    # valor sem IVA no formato "200,00"
    if contract_value_yearly_base is None:
        value_str = ""
    else:
        try:
            value_str = f"{float(contract_value_yearly_base):.2f}".replace(".", ",")
        except Exception:
            value_str = str(contract_value_yearly_base)

    ctx: Dict[str, Any] = {
        # data usada no CERTIFICADO + CONTRATO é a data de início do contrato
        "today_pt": contract_date_pt,

        "client_number": client_number,
        "client_fantasy": client_fantasy,
        "client_legal": client_legal,

        "vat_number": vat_number,
        "email": email,
        "phone": phone,

        "fiscal_address": fiscal_address,
        "postal_code": postal_code,
        "city": city,

        "service_address": service_address,
        "service_postal_code": service_postal_code,
        "service_city": service_city,

        "visits_per_year": visits_per_year,
        "contract_value_yearly": value_str,
    }

    w = PdfWriter()

    # 1) CAPA (overlay)
    capa_pdf = TEMPLATES["CAPA"]
    capa_final = _overlay_on_template(capa_pdf, _draw_cover_overlay(capa_pdf, ctx))
    _append_pdf_bytes(w, capa_final)

    # 2) ÍNDICE
    _append_pdf_file(w, TEMPLATES["INDICE"])

    # 3) INTRODUÇÃO
    _append_pdf_file(w, TEMPLATES["INTRO"])

    # 4) PLANEAMENTO EM BRANCO (template puro, sem alterar nada)
    _append_pdf_file(w, TEMPLATES["PLANEAMENTO"])

    # 5) CERTIFICADO
    cert_pdf = TEMPLATES["CERTIFICADO"]
    cert_final = _overlay_on_template(cert_pdf, _draw_certificate_overlay(cert_pdf, ctx))
    _append_pdf_bytes(w, cert_final)

    # 6) CONTRATO ORIGINAL
    contrato_pdf = TEMPLATES["CONTRATO_FRENTE"]
    contrato_orig = _overlay_on_template(contrato_pdf, _draw_contract_overlay(contrato_pdf, ctx, "original"))
    _append_pdf_bytes(w, contrato_orig)

    # 7) CONTRATO DUPLICADO
    contrato_dup = _overlay_on_template(contrato_pdf, _draw_contract_overlay(contrato_pdf, ctx, "duplicado"))
    _append_pdf_bytes(w, contrato_dup)

    # 8) CONDIÇÕES
    _append_pdf_file(w, TEMPLATES["CONTRATO_CONDICOES"])

    # 9) FICHAS TÉCNICAS E DE SEGURANÇA
    _append_common_annexes(w)

    out = BytesIO()
    w.write(out)
    return out.getvalue()