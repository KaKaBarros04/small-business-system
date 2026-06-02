# backend/app/services/pdf_visits.py
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from datetime import datetime
from typing import List, Dict

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE_DIR = Path(__file__).resolve().parents[2]

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _register_fonts():
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
    ]

    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            try:
                pdfmetrics.registerFont(TTFont("VisitFont", regular))
                pdfmetrics.registerFont(TTFont("VisitFont-Bold", bold))
                FONT_REGULAR = "VisitFont"
                FONT_BOLD = "VisitFont-Bold"
                return
            except Exception:
                continue


_register_fonts()


def _fix(x) -> str:
    """Corrige mojibake de caracteres portugueses vindos da DB."""
    if x is None:
        return ""

    text = str(x)

    # Todas as chaves usam \uXXXX para evitar problemas de encoding do ficheiro
    replacements = {
        # Sequencias Ã (UTF-8 lido como latin1)
        "\u00c3\u00a1": "\u00e1",  # a com acento agudo
        "\u00c3\u00a0": "\u00e0",  # a com acento grave
        "\u00c3\u00a2": "\u00e2",  # a com circunflexo
        "\u00c3\u00a3": "\u00e3",  # a com til
        "\u00c3\u00aa": "\u00ea",  # e com circunflexo
        "\u00c3\u00a9": "\u00e9",  # e com acento agudo
        "\u00c3\u00ad": "\u00ed",  # i com acento agudo
        "\u00c3\u00b3": "\u00f3",  # o com acento agudo
        "\u00c3\u00b4": "\u00f4",  # o com circunflexo
        "\u00c3\u00b5": "\u00f5",  # o com til
        "\u00c3\u00ba": "\u00fa",  # u com acento agudo
        "\u00c3\u00a7": "\u00e7",  # c cedilha
        "\u00c3\u0080": "\u00c0",  # A com acento grave
        "\u00c3\u0081": "\u00c1",  # A com acento agudo
        "\u00c3\u0089": "\u00c9",  # E com acento agudo
        "\u00c3\u0093": "\u00d3",  # O com acento agudo
        "\u00c3\u009a": "\u00da",  # U com acento agudo
        "\u00c3\u0087": "\u00c7",  # C cedilha maiuscula
        "\u00c3\u0095": "\u00d5",  # O com til maiusculo
        "\u00c3\u0083": "\u00c3",  # A com til maiusculo
        "\u00c3\u0082": "\u00c2",  # A com circunflexo maiusculo
        # Sequencias Â
        "\u00c2\u00ba": "\u00ba",  # ordinal masculino º
        "\u00c2\u00aa": "\u00aa",  # ordinal feminino ª
        "\u00c2\u00b0": "\u00b0",  # grau
        "\u00c2\u00b7": "\u00b7",  # ponto medio
        "\u00c2\u00ab": "\u00ab",  # guilhemets esquerda
        "\u00c2\u00bb": "\u00bb",  # guilhemets direita
    }

    for bad, good in replacements.items():
        text = text.replace(bad, good)

    # Sequencias com caracteres de box-drawing (┬ e ├)
    # Estes nao se conseguem representar bem como literais, usa replace direto
    box_replacements = [
        ("\u252c\u00ba", "\u00ba"),   # ┬º -> º
        ("\u252c\u2551", "\u00ba"),   # ┬║ -> º  (o bug principal!)
        ("\u252c\u00aa", "\u00aa"),   # ┬ª -> ª
        ("\u251c\u00ba", "\u00e7"),   # ├º -> ç
        ("\u251c\u00fa", "\u00e3"),   # ├ú -> ã
        ("\u251c\u00ed", "\u00e1"),   # ├í -> á
        ("\u251c\u00ae", "\u00e9"),   # ├® -> é
        ("\u251c\u00a1", "\u00ed"),   # ├¡ -> í
        ("\u251c\u2502", "\u00f3"),   # ├│ -> ó
        ("\u251c\u2551", "\u00fa"),   # ├║ -> ú
        ("\u251c\u00e1", "\u00e0"),   # ├á -> à
        ("\u251c\u00f3", "\u00e2"),   # ├ó -> â
        ("\u251c\u00ac", "\u00ea"),   # ├¬ -> ê
        ("\u251c\u2524", "\u00f4"),   # ├┤ -> ô
    ]

    for bad, good in box_replacements:
        text = text.replace(bad, good)

    # Tentativa generica para casos nao cobertos
    if any(m in text for m in ("\u00c3", "\u00c2")):
        for enc in ("latin1", "cp1252"):
            try:
                fixed = text.encode(enc).decode("utf-8")
                if fixed and fixed != text:
                    text = fixed
                    break
            except Exception:
                pass

    return text.strip()


def _safe(x, fallback="") -> str:
    s = _fix(x).strip()
    return s if s else fallback


def _resolve_logo(logo_path) -> str | None:
    if not logo_path:
        return None

    path = str(logo_path).lstrip("/")
    candidates = [
        BASE_DIR / path,
        BASE_DIR / "uploads" / Path(path).name,
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


BRAND_BLUE = colors.HexColor("#1E3A5F")
LIGHT_GRAY = colors.HexColor("#F3F4F6")
BORDER_GRAY = colors.HexColor("#E5E7EB")
TEXT_DARK = colors.HexColor("#111827")
TEXT_MUTED = colors.HexColor("#6B7280")

_styles = getSampleStyleSheet()

CELL_STYLE = ParagraphStyle(
    "VISITS_CELL",
    parent=_styles["Normal"],
    fontName=FONT_REGULAR,
    fontSize=8,
    leading=10,
    textColor=TEXT_DARK,
    wordWrap="CJK",
    splitLongWords=True,
)

CELL_BOLD_STYLE = ParagraphStyle(
    "VISITS_CELL_BOLD",
    parent=CELL_STYLE,
    fontName=FONT_BOLD,
)

CELL_MUTED = ParagraphStyle(
    "VISITS_CELL_MUTED",
    parent=CELL_STYLE,
    fontSize=7.5,
    textColor=TEXT_MUTED,
)


def _p(text, style=CELL_STYLE):
    return Paragraph(_safe(text, "\u2014"), style)


def _draw_page_header(
    c: canvas.Canvas,
    *,
    company: Dict,
    start: datetime,
    end: datetime,
    page_w: float,
    page_h: float,
):
    margin = 14 * mm

    logo_abs = _resolve_logo(company.get("logo_path"))
    if logo_abs:
        try:
            c.drawImage(
                logo_abs,
                margin,
                page_h - margin - 18 * mm,
                width=30 * mm,
                height=18 * mm,
                preserveAspectRatio=True,
                mask="auto",
            )
        except Exception:
            pass

    company_name = _safe(company.get("name") or company.get("business_name"), "")
    c.setFont(FONT_BOLD, 14)
    c.setFillColor(BRAND_BLUE)
    c.drawCentredString(page_w / 2, page_h - margin - 8 * mm, company_name)

    fmt_start = start.strftime("%d/%m/%Y")
    fmt_end = end.strftime("%d/%m/%Y")
    c.setFont(FONT_REGULAR, 9)
    c.setFillColor(TEXT_MUTED)
    c.drawCentredString(page_w / 2, page_h - margin - 14 * mm, f"Entre {fmt_start} e {fmt_end}")

    c.setFont(FONT_BOLD, 12)
    c.setFillColor(TEXT_DARK)
    c.drawCentredString(page_w / 2, page_h - margin - 21 * mm, "Lista de Clientes a visitar")

    c.setStrokeColor(BRAND_BLUE)
    c.setLineWidth(1.2)
    c.line(margin, page_h - margin - 24 * mm, page_w - margin, page_h - margin - 24 * mm)


def _draw_page_footer(c: canvas.Canvas, *, page_w: float):
    margin = 14 * mm
    footer_y = 9 * mm

    c.setStrokeColor(BORDER_GRAY)
    c.setLineWidth(0.5)
    c.line(margin, footer_y + 4 * mm, page_w - margin, footer_y + 4 * mm)

    c.setFont(FONT_REGULAR, 7.5)
    c.setFillColor(TEXT_MUTED)
    c.drawCentredString(page_w / 2, footer_y, f"P\u00e1gina {c.getPageNumber()}")


def _resolve_visit_address(row: Dict) -> str:
    service_addr = _safe(row.get("service_address"))
    service_pc = _safe(row.get("service_postal_code"))
    service_city = _safe(row.get("service_city"))

    fiscal_addr = _safe(row.get("address"))
    fiscal_pc = _safe(row.get("postal_code"))
    fiscal_city = _safe(row.get("city"))

    if service_addr and service_addr != fiscal_addr:
        addr = service_addr
        pc = service_pc or fiscal_pc
        city = service_city or fiscal_city
    else:
        addr = fiscal_addr
        pc = fiscal_pc
        city = fiscal_city

    parts = [p for p in [addr, f"{pc} {city}".strip()] if p]
    return "\n".join(parts) if parts else "\u2014"


def build_visits_pdf(
    *,
    company: Dict,
    rows: List[Dict],
    start: datetime,
    end: datetime,
) -> bytes:
    buf = BytesIO()
    page_w, page_h = A4
    c = canvas.Canvas(buf, pagesize=A4)

    margin = 14 * mm
    table_top = page_h - margin - 28 * mm
    bottom_limit = 16 * mm

    header = [
        Paragraph("N\u00famero", CELL_BOLD_STYLE),
        Paragraph("Nome", CELL_BOLD_STYLE),
        Paragraph("Morada", CELL_BOLD_STYLE),
        Paragraph("Data", CELL_BOLD_STYLE),
    ]

    col_widths = [18 * mm, 62 * mm, 82 * mm, 22 * mm]

    table_style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), LIGHT_GRAY),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("TEXTCOLOR", (0, 0), (-1, 0), TEXT_DARK),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
        ("GRID", (0, 0), (-1, -1), 0.4, BORDER_GRAY),
        ("LINEBELOW", (0, 0), (-1, 0), 1, BRAND_BLUE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, -1), "CENTER"),
        ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])

    def _make_address_cell(row: Dict) -> Paragraph:
        addr = _resolve_visit_address(row)
        addr_html = addr.replace("\n", "<br/>")
        return Paragraph(addr_html, CELL_STYLE)

    data_rows = []
    for row in rows:
        code = _safe(row.get("client_code"), "\u2014")
        name = _safe(row.get("business_name"), "\u2014")
        scheduled = _safe(row.get("scheduled_at_str"), "\u2014")

        data_rows.append([
            Paragraph(code, CELL_STYLE),
            Paragraph(f"<b>{name}</b>", CELL_STYLE),
            _make_address_cell(row),
            Paragraph(scheduled, CELL_STYLE),
        ])

    if not data_rows:
        data_rows = [[
            Paragraph("\u2014", CELL_MUTED),
            Paragraph("Sem visitas no per\u00edodo selecionado.", CELL_MUTED),
            Paragraph("", CELL_MUTED),
            Paragraph("", CELL_MUTED),
        ]]

    all_data = [header] + data_rows
    remaining = all_data

    while remaining:
        _draw_page_header(c, company=company, start=start, end=end, page_w=page_w, page_h=page_h)
        current_y = table_top
        available_h = current_y - bottom_limit

        table = Table(remaining, colWidths=col_widths, repeatRows=1, splitByRow=1)
        table.setStyle(table_style)

        parts = table.split(page_w - 2 * margin, available_h)

        if not parts:
            _, h = table.wrapOn(c, page_w - 2 * margin, available_h)
            table.drawOn(c, margin, current_y - h)
            break

        current_part = parts[0]
        _, h = current_part.wrapOn(c, page_w - 2 * margin, available_h)
        current_part.drawOn(c, margin, current_y - h)

        rows_drawn = len(current_part._cellvalues)

        _draw_page_footer(c, page_w=page_w)

        if rows_drawn >= len(remaining):
            break

        remaining = [remaining[0]] + remaining[rows_drawn:]
        c.showPage()

    c.save()
    buf.seek(0)
    return buf.getvalue()