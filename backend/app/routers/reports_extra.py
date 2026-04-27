# app/routers/reports_extra.py
from __future__ import annotations

from datetime import datetime, date
from pathlib import Path
from typing import Optional
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.company import Company
from app.models.client import Client
from app.models.expense import Expense
from app.models.stock_item import StockItem

from reportlab.lib.pagesizes import A4
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

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _register_pdf_fonts():
    global FONT_REGULAR, FONT_BOLD

    candidates = [
        (
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ),
        (
            str(BASE_DIR / "fonts" / "DejaVuSans.ttf"),
            str(BASE_DIR / "fonts" / "DejaVuSans-Bold.ttf"),
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


_register_pdf_fonts()


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


_styles = getSampleStyleSheet()

CELL = ParagraphStyle(
    "CELL",
    parent=_styles["Normal"],
    fontName=FONT_REGULAR,
    fontSize=9,
    leading=11,
    spaceBefore=0,
    spaceAfter=0,
    alignment=TA_LEFT,
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

    if company and company.logo_path:
        logo_path = company.logo_path or ""
        if logo_path.startswith("/"):
            logo_path = logo_path.lstrip("/")

        p = BASE_DIR / logo_path

        if not p.exists():
            p2 = UPLOADS_DIR / Path(logo_path).name
            if p2.exists():
                p = p2

        if p.exists():
            try:
                logo_w = 32 * mm
                logo_h = 16 * mm
                c.drawImage(
                    str(p),
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
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("FONT", (0, 0), (-1, 0), FONT_BOLD, 9),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F3F4F6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),

        ("FONT", (0, 1), (-1, -1), FONT_REGULAR, 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))

    w, h = t.wrapOn(c, 0, 0)
    t.drawOn(c, x, y - h)
    return h


def _get_company(db: Session, company_id: int) -> Company:
    return db.query(Company).filter(Company.id == company_id).first()


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
            _safe_str(it.name),
            _safe_str(it.sku),
            _safe_str(it.unit),
            f"{qty:.3f}".rstrip("0").rstrip("."),
            f"{target:.3f}".rstrip("0").rstrip("."),
            f"{lack:.3f}".rstrip("0").rstrip("."),
            f"{suggest:.3f}".rstrip("0").rstrip("."),
            _eur(unit_cost),
            _eur(est),
        ])

    total_value = sum(_as_number(it.qty_on_hand) * _as_number(it.avg_unit_cost) for it in items)

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    margin = 14 * mm

    _draw_header_footer(c, company=company, title="Relatório de Stock", page_w=page_w, page_h=page_h)

    y = page_h - margin - 55 * mm
    c.setFont(FONT_BOLD, 11)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawString(margin, y, "Lista de Itens")
    y -= 8 * mm

    table_data = [[
        "Produto", "SKU", "Un", "Stock", "Mín", "Falta", "Comprar", "Custo (un)", "Estimado"
    ]] + (rows if rows else [["Sem itens", "", "", "", "", "", "", "", ""]])

    col_widths = [64 * mm, 28 * mm, 10 * mm, 16 * mm, 16 * mm, 16 * mm, 18 * mm, 20 * mm, 22 * mm]
    used_h = _draw_table(c, table_data, margin, y, col_widths)
    y -= used_h + 8 * mm

    c.setFont(FONT_REGULAR, 9)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawString(margin, y, f"Total itens: {len(items)}")
    y -= 5 * mm
    c.drawString(margin, y, f"Valor estimado em stock (médio): {_eur(total_value)}")

    c.showPage()
    _draw_header_footer(c, company=company, title="Lista de Compras (Stock)", page_w=page_w, page_h=page_h)
    y = page_h - margin - 55 * mm

    restock_rows = rows if only_restock else [r for r, it in zip(rows, items) if needs_restock(it)]

    c.setFont(FONT_BOLD, 11)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawString(margin, y, "Itens a repor")
    y -= 8 * mm

    buy_table = [["Produto", "SKU", "Un", "Em stock", "Alvo", "Comprar"]] + (
        [[r[0], r[1], r[2], r[3], r[4], r[6]] for r in restock_rows]
        if restock_rows else [["Nenhum item precisa reposição", "", "", "", "", ""]]
    )

    buy_colw = [88 * mm, 34 * mm, 10 * mm, 22 * mm, 22 * mm, 22 * mm]
    _draw_table(c, buy_table, margin, y, buy_colw)

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

    qry = db.query(Client).filter(Client.company_id == current_user.company_id).order_by(Client.id.asc())

    if contract_only:
        qry = qry.filter(Client.has_contract == True)  # noqa: E712

    clients = qry.all()

    rows = []
    for cst in clients:
        rows.append([
            str(getattr(cst, "client_code", "") or cst.id),
            _safe_str(getattr(cst, "business_name", None)),
            _safe_str(getattr(cst, "vat_number", None)),
            _safe_str(getattr(cst, "city", None)),
            _safe_str(getattr(cst, "phone", None)),
            _fmt_date(getattr(cst, "contract_start_date", None)),
            str(getattr(cst, "visits_per_year", "") or "—") if getattr(cst, "has_contract", False) else "—",
            "Ativo" if getattr(cst, "is_active", True) else "Inativo",
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
        "ID", "Cliente", "NIF", "Localidade", "Telefone", "Início contrato", "Visitas/ano", "Estado"
    ]] + (rows if rows else [["Sem clientes", "", "", "", "", "", "", ""]])

    colw = [12 * mm, 52 * mm, 22 * mm, 30 * mm, 26 * mm, 24 * mm, 18 * mm, 18 * mm]
    _draw_table(c, table, margin, y, colw)

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