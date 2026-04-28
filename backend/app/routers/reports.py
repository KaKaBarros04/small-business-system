from __future__ import annotations

from datetime import datetime, date
from pathlib import Path
from typing import Optional
import io

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import cast, Integer

from app.core.deps import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.company import Company
from app.models.client import Client
from app.models.expense import Expense
from app.models.stock_item import StockItem
from app.models.appointment import Appointment
from app.models.manual_invoice import ManualInvoice
from app.services.pdf_visits import build_visits_pdf

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

router = APIRouter(prefix="/reports", tags=["reports"])

BASE_DIR = Path(__file__).resolve().parents[2]
UPLOADS_DIR = BASE_DIR / "uploads"

# =========================================================
# PDF Fonts - Unicode para acentos, ç, ã, õ, é, etc.
# =========================================================

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _register_pdf_fonts():
    global FONT_REGULAR, FONT_BOLD

    candidates = [
        (
            str(BASE_DIR / "fonts" / "DejaVuSans.ttf"),
            str(BASE_DIR / "fonts" / "DejaVuSans-Bold.ttf"),
        ),
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ),
        (
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ),
        (
            "/app/fonts/DejaVuSans.ttf",
            "/app/fonts/DejaVuSans-Bold.ttf",
        ),
        (
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
        ),
    ]

    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("AppFont", regular))
            pdfmetrics.registerFont(TTFont("AppFont-Bold", bold))
            FONT_REGULAR = "AppFont"
            FONT_BOLD = "AppFont-Bold"
            return


# =========================================================
# Helpers
# =========================================================

def _eur(v) -> str:
    try:
        x = float(v or 0)
    except Exception:
        x = 0.0
    return f"{x:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_dt(dt: Optional[datetime]) -> str:
    if not dt:
        return "—"
    return dt.strftime("%d/%m/%Y %H:%M")


def _fmt_date(d: Optional[date]) -> str:
    if not d:
        return "—"
    return d.strftime("%d/%m/%Y")


def _safe_str(x, fallback="—"):
    s = (str(x).strip() if x is not None else "")
    return s if s else fallback


def _as_number(x) -> float:
    try:
        return float(x or 0)
    except Exception:
        return 0.0


def _join_address_parts(*parts) -> str:
    vals = []
    for p in parts:
        s = (str(p).strip() if p is not None else "")
        if s:
            vals.append(s)
    return ", ".join(vals) if vals else "—"


def _get_company(db: Session, company_id: int) -> Company:
    return db.query(Company).filter(Company.id == company_id).first()


def _invoice_service_text(inv: ManualInvoice) -> str:
    items = getattr(inv, "items", None) or []
    if not items:
        return "—"

    descriptions = []
    for it in items:
        desc = (getattr(it, "description", None) or "").strip()
        if desc:
            descriptions.append(desc)

    if not descriptions:
        return "—"

    text = " | ".join(descriptions)
    return text[:140] + "..." if len(text) > 140 else text


def _fmt_number(v, decimals: int = 2) -> str:
    try:
        x = float(v or 0)
    except Exception:
        x = 0.0
    s = f"{x:,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _build_avi_document_number(
    inv: ManualInvoice | None,
    *,
    client: Client,
    issue_date: datetime | None = None,
) -> str:
    client_code_raw = _safe_str(getattr(client, "client_code", None), str(client.id))
    client_code_digits = "".join(ch for ch in client_code_raw if ch.isdigit())

    if client_code_digits.startswith("70") and len(client_code_digits) > 2:
        avi_number = client_code_digits[2:]
    else:
        avi_number = client_code_digits or client_code_raw

    avi_number = avi_number.lstrip("0") or "0"
    return avi_number.zfill(2)


def _extract_avi_lines_from_invoice(inv: ManualInvoice):
    items = getattr(inv, "items", None) or []
    lines = []

    if not items:
        subtotal = float(getattr(inv, "subtotal", 0) or 0)
        tax = float(getattr(inv, "tax", 0) or 0)
        total = float(getattr(inv, "total", 0) or 0)

        inferred_rate = 0.0
        if subtotal > 0 and tax > 0:
            inferred_rate = round((tax / subtotal) * 100, 2)

        lines.append({
            "article": "DOM/CORR",
            "description": _invoice_service_text(inv),
            "qty": 1.0,
            "unit": "UN",
            "unit_price": subtotal if subtotal > 0 else total,
            "discount": 0.0,
            "vat_rate": inferred_rate,
            "line_total": subtotal if subtotal > 0 else total,
            "line_subtotal": subtotal,
            "line_tax": tax,
        })
        return lines

    for item in items:
        qty = (
            getattr(item, "quantity", None)
            or getattr(item, "qty", None)
            or getattr(item, "qtd", None)
            or 1
        )
        qty = _as_number(qty)

        unit = (
            getattr(item, "unit", None)
            or getattr(item, "unit_name", None)
            or "UN"
        )

        unit_price = (
            getattr(item, "unit_price", None)
            or getattr(item, "price", None)
            or getattr(item, "rate", None)
            or getattr(item, "price_unit", None)
            or 0
        )
        unit_price = _as_number(unit_price)

        discount = (
            getattr(item, "discount", None)
            or getattr(item, "discount_pct", None)
            or getattr(item, "discount_percent", None)
            or 0
        )
        discount = _as_number(discount)

        vat_rate = (
            getattr(item, "tax_rate", None)
            or getattr(item, "vat_rate", None)
            or getattr(item, "iva", None)
            or getattr(item, "tax_percentage", None)
            or 23
        )
        vat_rate = _as_number(vat_rate)

        article = (
            getattr(item, "code", None)
            or getattr(item, "sku", None)
            or getattr(item, "article_code", None)
            or getattr(item, "item_code", None)
            or "DOM/CORR"
        )

        description = (
            getattr(item, "description", None)
            or getattr(item, "name", None)
            or "—"
        )

        line_subtotal = qty * unit_price * (1 - (discount / 100.0))
        line_tax = line_subtotal * (vat_rate / 100.0)

        lines.append({
            "article": _safe_str(article),
            "description": _safe_str(description),
            "qty": qty,
            "unit": _safe_str(unit, "UN"),
            "unit_price": unit_price,
            "discount": discount,
            "vat_rate": vat_rate,
            "line_total": line_subtotal,
            "line_subtotal": line_subtotal,
            "line_tax": line_tax,
        })

    return lines


def _resolve_logo_path(company: Company) -> str | None:
    if not company or not getattr(company, "logo_path", None):
        return None

    logo_path = company.logo_path or ""
    if logo_path.startswith("/"):
        logo_path = logo_path.lstrip("/")

    p = BASE_DIR / logo_path
    if not p.exists():
        p2 = UPLOADS_DIR / Path(logo_path).name
        if p2.exists():
            p = p2

    return str(p) if p.exists() else None


# =========================================================
# Visual system
# =========================================================

BRAND = colors.HexColor("#0F172A")
TEXT = colors.HexColor("#111827")
MUTED = colors.HexColor("#6B7280")
LINE = colors.HexColor("#E5E7EB")
SOFT = colors.HexColor("#F8FAFC")
ACCENT = colors.HexColor("#334155")
SUCCESS_DARK = colors.HexColor("#14532D")

_styles = getSampleStyleSheet()

CELL = ParagraphStyle(
    "CELL",
    parent=_styles["Normal"],
    fontName=FONT_REGULAR,
    fontSize=8,
    leading=9.5,
    textColor=TEXT,
    spaceBefore=0,
    spaceAfter=0,
    alignment=TA_LEFT,
    wordWrap="CJK",
    splitLongWords=True,
)

CELL_BOLD = ParagraphStyle(
    "CELL_BOLD",
    parent=CELL,
    fontName=FONT_BOLD,
)

CELL_RIGHT = ParagraphStyle(
    "CELL_RIGHT",
    parent=CELL,
    alignment=TA_RIGHT,
)

CELL_SMALL = ParagraphStyle(
    "CELL_SMALL",
    parent=CELL,
    fontSize=7.8,
    leading=9,
)

CELL_SMALL_BOLD = ParagraphStyle(
    "CELL_SMALL_BOLD",
    parent=CELL_SMALL,
    fontName=FONT_BOLD,
)

LABEL = ParagraphStyle(
    "LABEL",
    parent=CELL_SMALL,
    fontName=FONT_BOLD,
    fontSize=7,
    leading=8,
    textColor=MUTED,
)

MUTED_TEXT = ParagraphStyle(
    "MUTED_TEXT",
    parent=CELL_SMALL,
    textColor=MUTED,
)

AVI_DESC = ParagraphStyle(
    "AVI_DESC",
    parent=CELL_SMALL,
    fontName=FONT_REGULAR,
    fontSize=7.2,
    leading=8.2,
)

# =========================================================
# Generic header/footer/table helpers
# =========================================================

def _draw_header_footer(
    c: canvas.Canvas,
    *,
    company: Company,
    title: str,
    page_w: float,
    page_h: float,
):
    margin = 14 * mm
    top = page_h - margin
    left = margin

    c.setFillColor(colors.black)
    c.setFont(FONT_BOLD, 14)
    c.drawString(left, top, title)

    c.setFont(FONT_REGULAR, 9)
    info_y = top - 14
    line_h = 11

    logo_abs = _resolve_logo_path(company)
    if logo_abs:
        try:
            logo_w = 32 * mm
            logo_h = 16 * mm
            c.drawImage(
                logo_abs,
                page_w - margin - logo_w,
                top - 6,
                width=logo_w,
                height=logo_h,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    lines = [
        _safe_str(getattr(company, "name", None)),
        f"NIF: {_safe_str(getattr(company, 'vat_number', None))}",
        f"Morada: {_safe_str(getattr(company, 'address', None))}",
        f"Telefone: {_safe_str(getattr(company, 'phone', None))}   Email: {_safe_str(getattr(company, 'email', None))}",
    ]
    for i, ln in enumerate(lines):
        c.drawString(left, info_y - i * line_h, ln)

    c.setStrokeColor(colors.HexColor("#D1D5DB"))
    c.line(margin, info_y - 4 * line_h - 3, page_w - margin, info_y - 4 * line_h - 3)

    c.setFont(FONT_REGULAR, 8)
    footer_y = 10 * mm
    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawString(margin, footer_y, f"Gerado em {now}")
    c.drawRightString(page_w - margin, footer_y, f"Página {c.getPageNumber()}")


def _draw_table(c: canvas.Canvas, data, x, y, col_widths):
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("FONTSIZE", (0, 1), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#E5E7EB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    w, h = t.wrapOn(c, 0, 0)
    t.drawOn(c, x, y - h)
    return h


def _draw_table_paginated(
    c: canvas.Canvas,
    *,
    company: Company,
    title: str,
    data,
    col_widths,
    page_w: float,
    page_h: float,
    margin: float,
    start_y: float,
):
    available_width = page_w - (2 * margin)
    bottom_limit = 16 * mm

    top_after_header = page_h - margin - 55 * mm
    available_height_first = start_y - bottom_limit
    available_height_next = top_after_header - bottom_limit

    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("FONTSIZE", (0, 1), (-1, -1), 7.4),
        ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#E5E7EB")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])

    remaining = data
    first_page = True

    while remaining:
        available_height = available_height_first if first_page else available_height_next
        current_y = start_y if first_page else top_after_header

        table = Table(
            remaining,
            colWidths=col_widths,
            repeatRows=1,
            splitByRow=1,
        )
        table.setStyle(style)

        parts = table.split(available_width, available_height)

        if not parts:
            w, h = table.wrapOn(c, available_width, available_height)
            table.drawOn(c, margin, current_y - h)
            break

        current = parts[0]
        w, h = current.wrapOn(c, available_width, available_height)
        current.drawOn(c, margin, current_y - h)

        rows_drawn = len(current._cellvalues)
        if rows_drawn >= len(remaining):
            break

        remaining = [remaining[0]] + remaining[rows_drawn:]

        c.showPage()
        _draw_header_footer(c, company=company, title=title, page_w=page_w, page_h=page_h)
        c.setFont(FONT_BOLD, 11)
        c.setFillColor(colors.HexColor("#111827"))
        c.drawString(margin, top_after_header, "Lista")
        first_page = False


# =========================================================
# AVI-specific helpers
# =========================================================

def _draw_clean_footer(c: canvas.Canvas, *, page_w: float):
    margin = 14 * mm
    footer_y = 9 * mm

    c.setStrokeColor(LINE)
    c.setLineWidth(0.6)
    c.line(margin, footer_y + 4 * mm, page_w - margin, footer_y + 4 * mm)

    c.setFont(FONT_REGULAR, 7.5)
    c.setFillColor(MUTED)
    c.drawString(margin, footer_y, f"Gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    c.drawRightString(page_w - margin, footer_y, f"Pág. {c.getPageNumber()}")


def _draw_avi_header(
    c: canvas.Canvas,
    *,
    company: Company,
    title: str,
    page_w: float,
    page_h: float,
    client_name: str = "—",
    client_responsible: str = "—",
    client_address: str = "—",
    client_vat: str = "—",
    period_label: str = "—",
    invoice_count: int = 0,
    document_number: str = "—",
    issue_date_label: str = "—",
):
    margin = 14 * mm
    top = page_h - margin

    logo_abs = _resolve_logo_path(company)
    if logo_abs:
        try:
            c.drawImage(
                logo_abs,
                margin,
                top - 8 * mm,
                width=38 * mm,
                height=24 * mm,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    header_line_y = top - 10 * mm
    c.setStrokeColor(LINE)
    c.setLineWidth(0.8)
    c.line(margin, header_line_y, page_w - margin, header_line_y)

    left_x = margin
    right_x = page_w / 2 + 6 * mm
    block_title_y = header_line_y - 6 * mm

    info_style = ParagraphStyle(
        "AVI_INFO_BODY",
        parent=CELL,
        fontName=FONT_REGULAR,
        fontSize=8,
        leading=10,
        textColor=TEXT,
    )

    left_text = "<br/>".join([
        "<b>SACRED VISION LDA</b>",
        "Contribuinte N.º: 518205045",
        "",
        "RUA S TOME E PRINCIPE, 267",
        "VILA NOVA DE GAIA",
        "4430-228 VILA NOVA DE GAIA",
        "Telef. +351 938 421 503",
        "",
        "Capital Social 500,00 EUR",
        "Cons. Reg. Com. Lisboa",
        "Matricula N.º 518205045",
        "E-mail: sacredvision2021@gmail.com",
        "IBAN: PT50 0010 0000 6341 7070 00163",
    ])

    right_text = "<br/>".join([
        "Exmo.(s) Sr.(s)",
        f"<b>{client_name}</b>",
        f"Responsável: {client_responsible}",
        client_address,
    ])

    left_p = Paragraph(left_text, info_style)
    right_p = Paragraph(right_text, info_style)

    left_w = 80 * mm
    right_w = 80 * mm

    _, lh = left_p.wrap(left_w, 70 * mm)
    _, rh = right_p.wrap(right_w, 70 * mm)

    left_p.drawOn(c, left_x, block_title_y - 1.5 * mm - lh)
    right_p.drawOn(c, right_x, block_title_y - 1.5 * mm - rh)

    info_bottom = block_title_y - 3 * mm - max(lh, rh)

    doc_y = info_bottom - 6 * mm

    c.setFont(FONT_REGULAR, 8)
    c.setFillColor(TEXT)
    c.drawString(margin, doc_y, f"Encomendas  NE AVI.{document_number}")

    c.setFont(FONT_BOLD, 13)
    c.drawString(margin, doc_y - 7 * mm, "Aviso de Cobrança")

    meta_top = doc_y - 18 * mm
    c.setFont(FONT_REGULAR, 7.2)
    c.setFillColor(TEXT)
    c.drawString(margin, meta_top, "Data")
    c.drawString(60 * mm, meta_top, "Requisição")
    c.drawString(85 * mm, meta_top, "Moeda")
    c.drawString(103 * mm, meta_top, "Câmbio")
    c.drawString(121 * mm, meta_top, "Desconto Comercial")
    c.drawString(157 * mm, meta_top, "Desconto Adicional")
    c.drawString(191 * mm, meta_top, "Vencimento")
    c.drawString(222 * mm, meta_top, "Condição Pagamento")

    c.setFont(FONT_REGULAR, 8)
    c.drawString(margin, meta_top - 5 * mm, issue_date_label)
    c.drawString(85 * mm, meta_top - 5 * mm, "EUR")
    c.drawRightString(113 * mm, meta_top - 5 * mm, "1,00")
    c.drawRightString(151 * mm, meta_top - 5 * mm, "0,00")
    c.drawRightString(186 * mm, meta_top - 5 * mm, "0,00")
    c.drawString(191 * mm, meta_top - 5 * mm, issue_date_label)
    c.drawString(222 * mm, meta_top - 5 * mm, "Pronto Pagamento")

    c.drawString(margin, meta_top - 11 * mm, "V/N.º Contrib.")
    c.drawString(margin, meta_top - 16 * mm, client_vat)

    return meta_top - 23 * mm


def _draw_intro_notice(c: canvas.Canvas, *, x: float, y: float):
    c.setFont(FONT_BOLD, 8)
    c.setFillColor(ACCENT)
    c.drawString(x, y, "NOTA")

    c.setFont(FONT_REGULAR, 8)
    c.setFillColor(TEXT)
    c.drawString(
        x + 18 * mm,
        y,
        "Este documento não serve de fatura e destina-se apenas a cobrança / conferência contabilística."
    )


def _build_main_table(table_data, colw):
    t = Table(table_data, colWidths=colw, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.white),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEXT),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 7.6),

        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("FONTSIZE", (0, 1), (-1, -1), 7.4),

        ("VALIGN", (0, 0), (-1, -1), "TOP"),

        ("LEFTPADDING", (0, 0), (-1, -1), 2.2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2.2),
        ("TOPPADDING", (0, 0), (-1, -1), 3.2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.2),

        ("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.black),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#D1D5DB")),

        ("ALIGN", (0, 0), (2, -1), "LEFT"),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
    ]))
    return t


def _draw_summary_box(
    c: canvas.Canvas,
    *,
    x: float,
    y: float,
    width: float,
    client_name: str,
    total_subtotal: float,
    total_tax: float,
    total_total: float,
    company_iban: str,
    invoice_count: int,
):
    rows = [
        ("Cliente", client_name),
        ("Quantidade", str(invoice_count)),
        ("Subtotal", _eur(total_subtotal)),
        ("IVA", _eur(total_tax)),
        ("Total", _eur(total_total)),
        ("IBAN", company_iban),
    ]

    row_h = 5.4 * mm
    box_h = 10 * mm + row_h * len(rows)

    c.setFillColor(SOFT)
    c.roundRect(x, y - box_h, width, box_h, 3 * mm, stroke=0, fill=1)

    c.setFont(FONT_BOLD, 9)
    c.setFillColor(TEXT)
    c.drawString(x + 5 * mm, y - 6 * mm, "Resumo financeiro")

    current_y = y - 12 * mm
    for idx, (label, value) in enumerate(rows):
        if idx > 0:
            c.setStrokeColor(LINE)
            c.setLineWidth(0.45)
            c.line(x + 5 * mm, current_y + 2.2 * mm, x + width - 5 * mm, current_y + 2.2 * mm)

        c.setFont(FONT_REGULAR, 8)
        c.setFillColor(MUTED)
        c.drawString(x + 5 * mm, current_y, label)

        c.setFont(FONT_BOLD if label in {"Total", "IBAN"} else FONT_REGULAR, 8.2)
        c.setFillColor(SUCCESS_DARK if label == "Total" else TEXT)
        c.drawRightString(x + width - 5 * mm, current_y, value)

        current_y -= row_h

    return box_h


def _draw_notes_block(
    c: canvas.Canvas,
    *,
    x: float,
    y: float,
    width: float,
    company_iban: str,
):
    c.setFont(FONT_BOLD, 7.2)
    c.setFillColor(MUTED)
    c.drawString(x, y, "OBSERVAÇÕES")

    text_style = ParagraphStyle(
        "NOTES_STYLE",
        parent=CELL_SMALL,
        fontName=FONT_REGULAR,
        fontSize=7.8,
        leading=9.2,
        textColor=TEXT,
    )

    notes_text = (
        "Este documento é um aviso de cobrança / pré-fatura e não substitui a fatura final emitida.<br/>"
        f"O pagamento deverá ser efetuado por transferência bancária para o IBAN {company_iban}.<br/>"
        "Após pagamento ou validação contabilística, poderá ser emitida a fatura definitiva."
    )

    p = Paragraph(notes_text, text_style)
    _, ph = p.wrap(width, 40 * mm)
    p.drawOn(c, x, y - 4 * mm - ph)


# =========================================================
# Routes
# =========================================================

@router.get("/stock.pdf")
def stock_pdf(
    only_restock: bool = Query(False),
    threshold: float | None = Query(None, description="Se vier, usa qty <= threshold em vez de min_qty"),
    q: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = _get_company(db, current_user.company_id)

    qry = db.query(StockItem).filter(StockItem.company_id == current_user.company_id)

    if q:
        like = f"%{q.strip()}%"
        qry = qry.filter(
            (StockItem.name.ilike(like)) |
            (StockItem.sku.ilike(like)) |
            (StockItem.category.ilike(like))
        )

    items = qry.order_by(StockItem.name.asc()).all()

    def needs_restock(it: StockItem) -> bool:
        qty = _as_number(it.qty_on_hand)
        if threshold is not None:
            return qty <= float(threshold)
        return qty <= _as_number(it.min_qty)

    if only_restock:
        items = [it for it in items if needs_restock(it)]

    rows = []
    for it in items:
        qty = _as_number(it.qty_on_hand)
        minq = _as_number(it.min_qty)

        target = float(threshold) if threshold is not None else minq
        lack = max(0.0, target - qty)
        suggest = lack

        last_cost = _as_number(it.last_purchase_unit_cost) if it.last_purchase_unit_cost is not None else None
        avg_cost = _as_number(it.avg_unit_cost)
        unit_cost = last_cost if last_cost is not None and last_cost > 0 else avg_cost
        est = suggest * unit_cost

        rows.append([
            Paragraph(_safe_str(it.name), CELL_SMALL),
            Paragraph(_safe_str(it.sku), CELL_SMALL),
            Paragraph(_safe_str(it.unit), CELL_SMALL),
            Paragraph(f"{qty:.3f}".rstrip("0").rstrip("."), CELL_RIGHT),
            Paragraph(f"{target:.3f}".rstrip("0").rstrip("."), CELL_RIGHT),
            Paragraph(f"{lack:.3f}".rstrip("0").rstrip("."), CELL_RIGHT),
            Paragraph(f"{suggest:.3f}".rstrip("0").rstrip("."), CELL_RIGHT),
            Paragraph(_eur(unit_cost), CELL_RIGHT),
            Paragraph(_eur(est), CELL_RIGHT),
        ])

    total_value = sum(_as_number(it.qty_on_hand) * _as_number(it.avg_unit_cost) for it in items)
    restock_rows = rows if only_restock else [r for r, it in zip(rows, items) if needs_restock(it)]

    buf = io.BytesIO()
    page_size = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page_size)
    page_w, page_h = page_size
    margin = 10 * mm

    title = "Relatório de Stock"
    _draw_header_footer(c, company=company, title=title, page_w=page_w, page_h=page_h)

    y = page_h - margin - 55 * mm

    c.setFont(FONT_BOLD, 11)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawString(margin, y, "Lista de Itens")
    y -= 7 * mm

    c.setFont(FONT_REGULAR, 9)
    c.drawString(margin, y, f"Total itens: {len(items)}")
    y -= 5 * mm
    c.drawString(margin, y, f"Valor estimado em stock (médio): {_eur(total_value)}")
    y -= 8 * mm

    table_data = [[
        Paragraph("Produto", CELL_SMALL_BOLD),
        Paragraph("SKU", CELL_SMALL_BOLD),
        Paragraph("Un", CELL_SMALL_BOLD),
        Paragraph("Stock", CELL_SMALL_BOLD),
        Paragraph("Mín", CELL_SMALL_BOLD),
        Paragraph("Falta", CELL_SMALL_BOLD),
        Paragraph("Comprar", CELL_SMALL_BOLD),
        Paragraph("Custo (un)", CELL_SMALL_BOLD),
        Paragraph("Estimado", CELL_SMALL_BOLD),
    ]] + (rows if rows else [[
        Paragraph("Sem itens", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
    ]])

    col_widths = [
        70 * mm,
        28 * mm,
        12 * mm,
        18 * mm,
        18 * mm,
        18 * mm,
        20 * mm,
        24 * mm,
        24 * mm,
    ]

    _draw_table_paginated(
        c,
        company=company,
        title=title,
        data=table_data,
        col_widths=col_widths,
        page_w=page_w,
        page_h=page_h,
        margin=margin,
        start_y=y,
    )

    c.showPage()
    _draw_header_footer(c, company=company, title="Lista de Compras (Stock)", page_w=page_w, page_h=page_h)
    y = page_h - margin - 55 * mm

    c.setFont(FONT_BOLD, 11)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawString(margin, y, "Itens a repor")
    y -= 8 * mm

    buy_table = [[
        Paragraph("Produto", CELL_SMALL_BOLD),
        Paragraph("SKU", CELL_SMALL_BOLD),
        Paragraph("Un", CELL_SMALL_BOLD),
        Paragraph("Em stock", CELL_SMALL_BOLD),
        Paragraph("Alvo", CELL_SMALL_BOLD),
        Paragraph("Comprar", CELL_SMALL_BOLD),
    ]] + (
        [[r[0], r[1], r[2], r[3], r[4], r[6]] for r in restock_rows]
        if restock_rows else [[
            Paragraph("Nenhum item precisa reposição", CELL_SMALL),
            Paragraph("", CELL_SMALL),
            Paragraph("", CELL_SMALL),
            Paragraph("", CELL_SMALL),
            Paragraph("", CELL_SMALL),
            Paragraph("", CELL_SMALL),
        ]]
    )

    buy_colw = [95 * mm, 35 * mm, 14 * mm, 24 * mm, 24 * mm, 24 * mm]

    _draw_table_paginated(
        c,
        company=company,
        title="Lista de Compras (Stock)",
        data=buy_table,
        col_widths=buy_colw,
        page_w=page_w,
        page_h=page_h,
        margin=margin,
        start_y=y,
    )

    c.save()
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="stock.pdf"'},
    )


@router.get("/clients.pdf")
def clients_pdf(
    contract_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = _get_company(db, current_user.company_id)

    qry = (
        db.query(Client)
        .filter(Client.company_id == current_user.company_id)
        .order_by(cast(Client.client_code, Integer).asc(), Client.id.asc())
    )

    if contract_only:
        qry = qry.filter(Client.has_contract == True)  # noqa: E712

    clients = qry.all()

    rows = []
    for cst in clients:
        rows.append([
            Paragraph(str(getattr(cst, "client_code", "") or cst.id), CELL_SMALL),
            Paragraph(_safe_str(getattr(cst, "business_name", None)), CELL_SMALL),
            Paragraph(_safe_str(getattr(cst, "vat_number", None)), CELL_SMALL),
            Paragraph(_safe_str(getattr(cst, "city", None)), CELL_SMALL),
            Paragraph(_safe_str(getattr(cst, "phone", None)), CELL_SMALL),
            Paragraph(_fmt_date(getattr(cst, "contract_start_date", None)), CELL_SMALL),
            Paragraph(
                str(getattr(cst, "visits_per_year", "") or "—") if getattr(cst, "has_contract", False) else "—",
                CELL_SMALL,
            ),
            Paragraph("Ativo" if getattr(cst, "is_active", True) else "Inativo", CELL_SMALL),
        ])

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    margin = 14 * mm

    title = "Relatório de Clientes" + (" (com contrato)" if contract_only else "")
    _draw_header_footer(c, company=company, title=title, page_w=page_w, page_h=page_h)

    y = page_h - margin - 55 * mm
    c.setFont(FONT_BOLD, 11)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawString(margin, y, "Lista")
    y -= 8 * mm

    table = [[
        Paragraph("ID", CELL_SMALL_BOLD),
        Paragraph("Cliente", CELL_SMALL_BOLD),
        Paragraph("NIF", CELL_SMALL_BOLD),
        Paragraph("Localidade", CELL_SMALL_BOLD),
        Paragraph("Telefone", CELL_SMALL_BOLD),
        Paragraph("Início contrato", CELL_SMALL_BOLD),
        Paragraph("Visitas/ano", CELL_SMALL_BOLD),
        Paragraph("Estado", CELL_SMALL_BOLD),
    ]] + (rows if rows else [[
        Paragraph("Sem clientes", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
        Paragraph("", CELL_SMALL),
    ]])

    colw = [16 * mm, 56 * mm, 22 * mm, 26 * mm, 22 * mm, 20 * mm, 14 * mm, 16 * mm]

    _draw_table_paginated(
        c,
        company=company,
        title=title,
        data=table,
        col_widths=colw,
        page_w=page_w,
        page_h=page_h,
        margin=margin,
        start_y=y,
    )

    c.save()
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="clients.pdf"'},
    )


@router.get("/expenses.pdf")
def expenses_pdf(
    year: int = Query(..., ge=1900, le=3000),
    month: int = Query(0, ge=0, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = _get_company(db, current_user.company_id)

    qry = db.query(Expense).filter(Expense.company_id == current_user.company_id)

    if month and month >= 1:
        start = datetime(year, month, 1)
        end = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        period_label = f"{month:02d}/{year}"
    else:
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)
        period_label = f"Ano {year}"

    qry = qry.filter(Expense.date >= start, Expense.date < end).order_by(Expense.date.asc())
    expenses = qry.all()

    total = 0.0
    rows = []
    for e in expenses:
        total += _as_number(e.amount)
        rows.append([
            Paragraph(_fmt_dt(getattr(e, "date", None)), CELL),
            Paragraph(_safe_str(getattr(e, "category", None)), CELL),
            Paragraph(_safe_str(getattr(e, "description", None)), CELL),
            Paragraph(_eur(getattr(e, "amount", 0)), CELL_RIGHT),
        ])

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    margin = 14 * mm

    _draw_header_footer(
        c,
        company=company,
        title=f"Relatório de Despesas — {period_label}",
        page_w=page_w,
        page_h=page_h,
    )

    y = page_h - margin - 55 * mm
    c.setFont(FONT_REGULAR, 9)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawString(margin, y, f"Total: {_eur(total)}")
    y -= 8 * mm

    table = [[
        Paragraph("Data", CELL_BOLD),
        Paragraph("Categoria", CELL_BOLD),
        Paragraph("Descrição", CELL_BOLD),
        Paragraph("Valor", CELL_BOLD),
    ]] + (rows if rows else [[
        Paragraph("Sem despesas", CELL),
        Paragraph("", CELL),
        Paragraph("", CELL),
        Paragraph("", CELL),
    ]])

    colw = [32 * mm, 36 * mm, 100 * mm, 22 * mm]
    _draw_table(c, table, margin, y, colw)

    c.save()
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="expenses.pdf"'},
    )


@router.get("/visits.pdf")
def visits_pdf(
    year: int = Query(..., ge=1900, le=3000),
    month: int = Query(0, ge=0, le=12),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = _get_company(db, current_user.company_id)

    if month and month >= 1:
        start = datetime(year, month, 1)
        end = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    else:
        start = datetime(year, 1, 1)
        end = datetime(year + 1, 1, 1)

    appts = (
        db.query(Appointment)
        .options(joinedload(Appointment.client))
        .filter(
            Appointment.company_id == current_user.company_id,
            Appointment.scheduled_at >= start,
            Appointment.scheduled_at < end,
        )
        .order_by(Appointment.scheduled_at.asc())
        .all()
    )

    rows = []
    for appt in appts:
        client = getattr(appt, "client", None)
        if not client:
            continue

        rows.append({
            "client_code": getattr(client, "client_code", None) or getattr(client, "id", None),
            "business_name": getattr(client, "business_name", None) or getattr(client, "name", None),
            "address": getattr(client, "address", None),
            "postal_code": getattr(client, "postal_code", None),
            "city": getattr(client, "city", None),
            "service_address": getattr(client, "service_address", None),
            "service_postal_code": getattr(client, "service_postal_code", None),
            "service_city": getattr(client, "service_city", None),
            "notes": getattr(client, "notes", None),
            "scheduled_at_str": appt.scheduled_at.strftime("%d/%m/%Y") if appt.scheduled_at else "",
        })

    pdf_bytes = build_visits_pdf(
        company={
            "name": getattr(company, "name", None),
            "business_name": getattr(company, "business_name", None),
            "logo": None,
            "logo_path": getattr(company, "logo_path", None),
        },
        rows=rows,
        start=start,
        end=end,
    )

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="visits.pdf"'},
    )


@router.get("/pending-invoices.pdf")
def pending_invoices_pdf(
    year: int | None = Query(None, ge=1900, le=3000),
    month: int | None = Query(None, ge=1, le=12),
    invoice_kind: str | None = Query(None, description="Ex.: CONTRACT ou MANUAL"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = _get_company(db, current_user.company_id)

    qry = (
        db.query(ManualInvoice)
        .options(
            joinedload(ManualInvoice.items),
            joinedload(ManualInvoice.client),
        )
        .filter(
            ManualInvoice.company_id == current_user.company_id,
            ManualInvoice.status == "DRAFT",
        )
    )

    if year is not None:
        if month is not None:
            start = datetime(year, month, 1)
            end = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        else:
            start = datetime(year, 1, 1)
            end = datetime(year + 1, 1, 1)

        qry = qry.filter(
            ManualInvoice.issue_date >= start,
            ManualInvoice.issue_date < end,
        )

    if invoice_kind:
        qry = qry.filter(ManualInvoice.invoice_kind == invoice_kind.strip().upper())

    invoices = qry.order_by(ManualInvoice.issue_date.asc(), ManualInvoice.id.asc()).all()

    rows = []
    total_subtotal = 0.0
    total_tax = 0.0
    total_total = 0.0

    for inv in invoices:
        client = getattr(inv, "client", None)

        client_code = getattr(client, "client_code", None) or "—"
        client_company_name = (
            getattr(client, "business_name", None)
            or getattr(client, "name", None)
            or getattr(inv, "supplier_name", None)
            or "—"
        )
        client_responsible = (
            getattr(client, "contact_name", None)
            or getattr(client, "name", None)
            or "—"
        )

        address = _join_address_parts(
            getattr(client, "address", None),
            " ".join(
                [x for x in [
                    getattr(client, "postal_code", None),
                    getattr(client, "city", None),
                ] if x]
            ) if client else None,
        )

        service_text = _invoice_service_text(inv)

        subtotal = float(getattr(inv, "subtotal", 0) or 0)
        tax = float(getattr(inv, "tax", 0) or 0)
        total = float(getattr(inv, "total", 0) or 0)

        total_subtotal += subtotal
        total_tax += tax
        total_total += total

        issue_date = getattr(inv, "issue_date", None)
        issue_date_text = _fmt_date(issue_date.date()) if issue_date else "—"

        rows.append([
            Paragraph(_safe_str(client_code), CELL_SMALL),
            Paragraph(_safe_str(client_company_name), CELL_SMALL),
            Paragraph(_safe_str(client_responsible), CELL_SMALL),
            Paragraph(_safe_str(address), CELL_SMALL),
            Paragraph(_safe_str(getattr(inv, "invoice_kind", None), "—"), CELL_SMALL),
            Paragraph(issue_date_text, CELL_SMALL),
            Paragraph(_safe_str(service_text), CELL_SMALL),
            Paragraph(_eur(subtotal), CELL_RIGHT),
            Paragraph(_eur(tax), CELL_RIGHT),
            Paragraph(_eur(total), CELL_RIGHT),
            Paragraph(_safe_str(getattr(inv, "invoice_number", None)), CELL_SMALL),
        ])

    buf = io.BytesIO()
    page_size = landscape(A4)
    c = canvas.Canvas(buf, pagesize=page_size)
    page_w, page_h = page_size
    margin = 10 * mm

    title = "Pré-faturas pendentes de emissão"
    if invoice_kind:
        title += f" ({invoice_kind.strip().upper()})"

    _draw_header_footer(c, company=company, title=title, page_w=page_w, page_h=page_h)

    y = page_h - margin - 55 * mm

    c.setFont(FONT_REGULAR, 9)
    c.setFillColor(colors.HexColor("#111827"))

    period_label = "Todos os períodos"
    if year is not None and month is not None:
        period_label = f"{month:02d}/{year}"
    elif year is not None:
        period_label = f"Ano {year}"

    c.drawString(margin, y, f"Período: {period_label}")
    y -= 5 * mm
    c.drawString(margin, y, f"Total de pré-faturas: {len(invoices)}")
    y -= 8 * mm

    if not rows:
        empty_box = [
            [Paragraph("Sem pré-faturas pendentes para os filtros selecionados.", CELL_BOLD)]
        ]
        _draw_table(c, empty_box, margin, y, [120 * mm])
    else:
        table = [[
            Paragraph("Cód.", CELL_SMALL_BOLD),
            Paragraph("Empresa cliente", CELL_SMALL_BOLD),
            Paragraph("Responsável", CELL_SMALL_BOLD),
            Paragraph("Morada", CELL_SMALL_BOLD),
            Paragraph("Tipo", CELL_SMALL_BOLD),
            Paragraph("Data", CELL_SMALL_BOLD),
            Paragraph("Serviço", CELL_SMALL_BOLD),
            Paragraph("Subtotal", CELL_SMALL_BOLD),
            Paragraph("IVA", CELL_SMALL_BOLD),
            Paragraph("Total", CELL_SMALL_BOLD),
            Paragraph("Nº", CELL_SMALL_BOLD),
        ]] + rows

        colw = [
            12 * mm,
            32 * mm,
            28 * mm,
            38 * mm,
            15 * mm,
            20 * mm,
            42 * mm,
            18 * mm,
            15 * mm,
            18 * mm,
            12 * mm,
        ]

        _draw_table_paginated(
            c,
            company=company,
            title=title,
            data=table,
            col_widths=colw,
            page_w=page_w,
            page_h=page_h,
            margin=margin,
            start_y=y,
        )

    c.showPage()
    _draw_header_footer(c, company=company, title=title, page_w=page_w, page_h=page_h)

    y2 = page_h - margin - 55 * mm
    c.setFont(FONT_BOLD, 11)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawString(margin, y2, "Resumo")
    y2 -= 10 * mm

    summary_table = [
        [Paragraph("Quantidade", CELL_BOLD), Paragraph(str(len(invoices)), CELL_RIGHT)],
        [Paragraph("Subtotal total", CELL_BOLD), Paragraph(_eur(total_subtotal), CELL_RIGHT)],
        [Paragraph("IVA total", CELL_BOLD), Paragraph(_eur(total_tax), CELL_RIGHT)],
        [Paragraph("Total geral", CELL_BOLD), Paragraph(_eur(total_total), CELL_RIGHT)],
    ]

    _draw_table(c, summary_table, margin, y2, [70 * mm, 40 * mm])

    c.save()
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'inline; filename="pending_invoices.pdf"'},
    )


@router.get("/client/{client_id}/pending-invoices-avi.pdf")
def client_pending_invoices_avi_pdf(
    client_id: int,
    year: int | None = Query(None, ge=1900, le=3000),
    month: int | None = Query(None, ge=1, le=12),
    invoice_kind: str | None = Query(None, description="Ex.: CONTRACT ou MANUAL"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    company = _get_company(db, current_user.company_id)

    client = (
        db.query(Client)
        .filter(
            Client.id == client_id,
            Client.company_id == current_user.company_id,
        )
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    qry = (
        db.query(ManualInvoice)
        .options(
            joinedload(ManualInvoice.items),
            joinedload(ManualInvoice.client),
        )
        .filter(
            ManualInvoice.company_id == current_user.company_id,
            ManualInvoice.client_id == client_id,
            ManualInvoice.status == "DRAFT",
        )
    )

    if year is not None:
        if month is not None:
            start = datetime(year, month, 1)
            end = datetime(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        else:
            start = datetime(year, 1, 1)
            end = datetime(year + 1, 1, 1)

        qry = qry.filter(
            ManualInvoice.issue_date >= start,
            ManualInvoice.issue_date < end,
        )

    if invoice_kind:
        qry = qry.filter(ManualInvoice.invoice_kind == invoice_kind.strip().upper())

    invoices = qry.order_by(ManualInvoice.issue_date.asc(), ManualInvoice.id.asc()).all()

    client_name = (
        getattr(client, "business_name", None)
        or getattr(client, "name", None)
        or "—"
    )
    client_responsible = (
        getattr(client, "contact_name", None)
        or getattr(client, "name", None)
        or "—"
    )
    client_vat = _safe_str(getattr(client, "vat_number", None))
    client_address = _join_address_parts(
        getattr(client, "address", None),
        " ".join(
            [x for x in [
                getattr(client, "postal_code", None),
                getattr(client, "city", None),
            ] if x]
        ),
    )

    rows = []
    total_subtotal = 0.0
    total_tax = 0.0
    total_total = 0.0

    first_issue_date = None
    first_invoice = invoices[0] if invoices else None

    line_no = 1
    for inv in invoices:
        issue_date = getattr(inv, "issue_date", None)
        if first_issue_date is None and issue_date is not None:
            first_issue_date = issue_date

        line_items = _extract_avi_lines_from_invoice(inv)

        for line in line_items:
            total_subtotal += line["line_subtotal"]
            total_tax += line["line_tax"]
            total_total += line["line_total"]

            rows.append([
                Paragraph(str(line_no), CELL_SMALL),
                Paragraph(_safe_str(line["article"]), CELL_SMALL),
                Paragraph(_safe_str(line["description"]), AVI_DESC),
                Paragraph(_fmt_number(line["qty"]), CELL_RIGHT),
                Paragraph(_safe_str(line["unit"], "UN"), CELL_SMALL),
                Paragraph(_fmt_number(line["unit_price"]), CELL_RIGHT),
                Paragraph(_fmt_number(line["discount"]), CELL_RIGHT),
                Paragraph(_fmt_number(line["vat_rate"]), CELL_RIGHT),
                Paragraph(_eur(line["line_total"]), CELL_RIGHT),
            ])
            line_no += 1

    buf = io.BytesIO()
    page_w, page_h = A4
    c = canvas.Canvas(buf, pagesize=A4)

    margin = 14 * mm
    bottom_limit = 16 * mm

    title = "Aviso de Cobrança"

    period_label = "Todos os períodos"
    if year is not None and month is not None:
        period_label = f"{month:02d}/{year}"
    elif year is not None:
        period_label = f"Ano {year}"

    issue_date_label = _fmt_date(first_issue_date.date()) if first_issue_date else _fmt_date(date.today())
    document_number = _build_avi_document_number(
        first_invoice,
        client=client,
        issue_date=first_issue_date,
    )

    y = _draw_avi_header(
        c,
        company=company,
        title=title,
        page_w=page_w,
        page_h=page_h,
        client_name=client_name,
        client_responsible=client_responsible,
        client_address=client_address,
        client_vat=client_vat,
        period_label=period_label,
        invoice_count=len(rows),
        document_number=document_number,
        issue_date_label=issue_date_label,
    )

    _draw_intro_notice(c, x=margin, y=y)
    y -= 8 * mm

    table_data = [[
        Paragraph("Nº", CELL_SMALL_BOLD),
        Paragraph("Artigo", CELL_SMALL_BOLD),
        Paragraph("Descrição", CELL_SMALL_BOLD),
        Paragraph("Qtd.", CELL_SMALL_BOLD),
        Paragraph("Un.", CELL_SMALL_BOLD),
        Paragraph("Pr. Unit.", CELL_SMALL_BOLD),
        Paragraph("Desc.", CELL_SMALL_BOLD),
        Paragraph("IVA", CELL_SMALL_BOLD),
        Paragraph("Valor", CELL_SMALL_BOLD),
    ]] + (
        rows if rows else [[
            Paragraph("—", CELL_SMALL),
            Paragraph("—", CELL_SMALL),
            Paragraph("Sem pré-faturas pendentes para este cliente nos filtros selecionados.", AVI_DESC),
            Paragraph("—", CELL_SMALL),
            Paragraph("—", CELL_SMALL),
            Paragraph("—", CELL_SMALL),
            Paragraph("—", CELL_SMALL),
            Paragraph("—", CELL_SMALL),
            Paragraph("—", CELL_SMALL),
        ]]
    )

    colw = [
        9 * mm,   # Nº
        18 * mm,  # Artigo
        72 * mm,  # Descrição
        12 * mm,  # Qtd.
        10 * mm,  # Un.
        17 * mm,  # Pr. Unit.
        12 * mm,  # Desc.
        12 * mm,  # IVA
        18 * mm,  # Valor
    ]

    t = _build_main_table(table_data, colw)
    _, th = t.wrapOn(c, page_w - 2 * margin, page_h)

    if y - th < 62 * mm:
        c.showPage()
        y = page_h - 28 * mm

    t.drawOn(c, margin, y - th)
    y = y - th - 10 * mm

    company_iban = "PT50 0010 0000 6341 7070 00163"

    summary_width = 78 * mm
    summary_x = page_w - margin - summary_width
    summary_y = 80 * mm

    summary_needed = 54 * mm
    notes_needed = 22 * mm

    if y - (summary_needed + notes_needed) < bottom_limit:
        c.showPage()
        summary_y = page_h - 28 * mm

    summary_height = _draw_summary_box(
        c,
        x=summary_x,
        y=summary_y,
        width=summary_width,
        client_name=client_name,
        total_subtotal=total_subtotal,
        total_tax=total_tax,
        total_total=total_total,
        company_iban=company_iban,
        invoice_count=len(rows),
    )

    notes_y = summary_y - summary_height - 8 * mm

    _draw_notes_block(
        c,
        x=margin,
        y=notes_y,
        width=page_w - 2 * margin,
        company_iban=company_iban,
    )

    _draw_clean_footer(c, page_w=page_w)

    c.save()
    buf.seek(0)

    safe_client_name = "".join(
        ch if ch.isalnum() or ch in ("-", "_") else "_"
        for ch in client_name
    )[:40] or "cliente"

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="avi_prefaturas_{client.id}_{safe_client_name}.pdf"'
        },
    )