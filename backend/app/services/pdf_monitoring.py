from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from app.models.client import Client
from app.models.company import Company
from app.models.site_map import SiteMap
from app.models.monitoring_visit import MonitoringVisit


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
    ]

    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("AppFont", regular))
            pdfmetrics.registerFont(TTFont("AppFont-Bold", bold))
            FONT_REGULAR = "AppFont"
            FONT_BOLD = "AppFont-Bold"
            return


_register_pdf_fonts()


def _safe(x, fallback="—"):
    s = str(x).strip() if x is not None else ""
    return s if s else fallback


def _img_abs_path(image_path: str) -> Path | None:
    if not image_path:
        return None

    p = Path(image_path)
    if p.is_absolute() and p.exists():
        return p

    rel = image_path.lstrip("/")
    p1 = BASE_DIR / rel
    if p1.exists():
        return p1

    p2 = UPLOADS_DIR / Path(rel).name
    if p2.exists():
        return p2

    return None


def _draw_company_header(c: canvas.Canvas, company: Company, title: str, page_w: float, page_h: float):
    margin = 14 * mm
    top = page_h - margin

    c.setFont(FONT_BOLD, 14)
    c.setFillColor(colors.black)
    c.drawString(margin, top, title)

    c.setFont(FONT_REGULAR, 9)
    info_y = top - 14
    line_h = 11

    lines = [
        _safe(getattr(company, "name", None)),
        f"NIF: {_safe(getattr(company, 'vat_number', None))}",
        f"Morada: {_safe(getattr(company, 'address', None))}",
        f"Telefone: {_safe(getattr(company, 'phone', None))}   Email: {_safe(getattr(company, 'email', None))}",
    ]

    for i, ln in enumerate(lines):
        c.drawString(margin, info_y - i * line_h, ln)

    logo_path = getattr(company, "logo_path", None)
    if logo_path:
        logo_abs = _img_abs_path(logo_path)
        if logo_abs and logo_abs.exists():
            try:
                c.drawImage(
                    str(logo_abs),
                    page_w - margin - (30 * mm),
                    top - 4,
                    width=30 * mm,
                    height=15 * mm,
                    preserveAspectRatio=True,
                    mask="auto",
                )
            except Exception:
                pass

    c.setStrokeColor(colors.HexColor("#D1D5DB"))
    c.line(margin, info_y - 4 * line_h, page_w - margin, info_y - 4 * line_h)


def _draw_footer(c: canvas.Canvas, page_w: float):
    margin = 14 * mm
    y = 10 * mm
    now = datetime.now().strftime("%d/%m/%Y %H:%M")

    c.setFont(FONT_REGULAR, 8)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawString(margin, y, f"Gerado em {now}")
    c.drawRightString(page_w - margin, y, f"Página {c.getPageNumber()}")


def _device_style(device_type: str):
    dt = (device_type or "").upper()

    if dt == "RAT_PVC":
        return {"shape": "circle", "fill": colors.HexColor("#FACC15"), "stroke": colors.HexColor("#DC2626")}
    if dt == "RAT_CARDBOARD":
        return {"shape": "square", "fill": colors.HexColor("#FDE047"), "stroke": colors.HexColor("#DC2626")}
    if dt == "COCKROACH_TRAP":
        return {"shape": "rect", "fill": colors.HexColor("#FCA5A5"), "stroke": colors.HexColor("#DC2626")}
    if dt == "INSECT_CATCHER":
        return {"shape": "triangle", "fill": colors.HexColor("#BFDBFE"), "stroke": colors.HexColor("#2563EB")}

    return {"shape": "circle", "fill": colors.HexColor("#E5E7EB"), "stroke": colors.HexColor("#374151")}


def _device_label(device_type: str) -> str:
    dt = (device_type or "").upper()
    return {
        "RAT_PVC": "Caixa rateira PVC",
        "RAT_CARDBOARD": "Caixa rateira cartão",
        "COCKROACH_TRAP": "Armadilha / detetora de baratas",
        "INSECT_CATCHER": "Inseto-captador",
        "OTHER": "Outro",
    }.get(dt, dt or "Outro")


def _draw_marker(c: canvas.Canvas, cx: float, cy: float, point_number: int, device_type: str):
    style = _device_style(device_type)
    shape = style["shape"]

    c.setFillColor(style["fill"])
    c.setStrokeColor(style["stroke"])
    c.setLineWidth(1)

    if shape == "circle":
        c.circle(cx, cy, 8, stroke=1, fill=1)
    elif shape == "square":
        s = 15
        c.rect(cx - s / 2, cy - s / 2, s, s, stroke=1, fill=1)
    elif shape == "rect":
        w, h = 18, 12
        c.roundRect(cx - w / 2, cy - h / 2, w, h, 2, stroke=1, fill=1)
    elif shape == "triangle":
        s = 16
        p = c.beginPath()
        p.moveTo(cx, cy + s / 2)
        p.lineTo(cx - s / 2, cy - s / 2)
        p.lineTo(cx + s / 2, cy - s / 2)
        p.close()
        c.drawPath(p, stroke=1, fill=1)
    else:
        c.circle(cx, cy, 8, stroke=1, fill=1)

    c.setFillColor(colors.black)
    c.setFont(FONT_BOLD, 8)
    c.drawCentredString(cx, cy - 3, str(point_number))


def _draw_legend(c: canvas.Canvas, x: float, y: float):
    c.setFont(FONT_BOLD, 9)
    c.setFillColor(colors.black)
    c.drawString(x, y, "Legenda")
    y -= 12

    items = [
        ("COCKROACH_TRAP", "Armadilha / detetora de baratas"),
        ("RAT_PVC", "Caixa rateira PVC"),
        ("RAT_CARDBOARD", "Caixa rateira cartão"),
        ("INSECT_CATCHER", "Inseto-captador"),
    ]

    for device_type, label in items:
        _draw_marker(c, x + 8, y + 4, 0, device_type)
        c.setFillColor(colors.black)
        c.setFont(FONT_REGULAR, 8)
        c.drawString(x + 20, y, label)
        y -= 16


def build_site_map_pdf(*, company: Company, client: Client, site_map: SiteMap) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    margin = 14 * mm

    _draw_company_header(c, company, f"Mapa técnico — {site_map.name}", page_w, page_h)

    info_y = page_h - margin - 58 * mm
    c.setFont(FONT_BOLD, 10)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawString(margin, info_y, "Cliente")

    c.setFont(FONT_REGULAR, 9)
    info_y -= 12
    c.drawString(margin, info_y, f"Código: {_safe(getattr(client, 'client_code', None), str(client.id))}")
    info_y -= 11
    c.drawString(margin, info_y, f"Nome: {_safe(getattr(client, 'business_name', None) or getattr(client, 'name', None))}")
    info_y -= 11
    c.drawString(margin, info_y, f"NIF: {_safe(getattr(client, 'vat_number', None))}")
    info_y -= 11

    morada = " ".join([
        x for x in [
            getattr(client, "address", None),
            getattr(client, "postal_code", None),
            getattr(client, "city", None),
        ] if x
    ])

    c.drawString(margin, info_y, f"Morada: {_safe(morada)}")

    map_x = margin
    map_y = 35 * mm
    map_w = 130 * mm
    map_h = 150 * mm

    c.setStrokeColor(colors.HexColor("#9CA3AF"))
    c.rect(map_x, map_y, map_w, map_h, stroke=1, fill=0)

    img_abs = _img_abs_path(site_map.image_path)

    if img_abs and img_abs.exists():
        try:
            reader = ImageReader(str(img_abs))
            iw, ih = reader.getSize()
            scale = min(map_w / iw, map_h / ih)
            draw_w = iw * scale
            draw_h = ih * scale
            draw_x = map_x + (map_w - draw_w) / 2
            draw_y = map_y + (map_h - draw_h) / 2

            c.drawImage(
                str(img_abs),
                draw_x,
                draw_y,
                width=draw_w,
                height=draw_h,
                preserveAspectRatio=True,
                mask="auto",
            )

            for p in site_map.points:
                if not p.is_active:
                    continue

                cx = draw_x + (p.x_percent / 100.0) * draw_w
                cy = draw_y + ((100.0 - p.y_percent) / 100.0) * draw_h
                _draw_marker(c, cx, cy, p.point_number, p.device_type)

        except Exception:
            c.setFont(FONT_REGULAR, 10)
            c.drawString(map_x + 10, map_y + map_h - 20, "Erro ao carregar imagem da planta.")
    else:
        c.setFont(FONT_REGULAR, 10)
        c.drawString(map_x + 10, map_y + map_h - 20, "Imagem da planta não encontrada.")

    _draw_legend(c, map_x + map_w + 12 * mm, page_h - margin - 75 * mm)

    obs_y = 32 * mm
    c.setFont(FONT_BOLD, 9)
    c.drawString(margin, obs_y, "Observações")

    c.setFont(FONT_REGULAR, 9)
    c.drawString(margin, obs_y - 12, _safe(site_map.notes, ""))

    _draw_footer(c, page_w)
    c.save()
    buf.seek(0)

    return buf.getvalue()


def build_monitoring_visit_pdf(*, company: Company, client: Client, visit: MonitoringVisit, site_maps: list[SiteMap]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_w, page_h = A4
    margin = 14 * mm

    results_by_point_id = {r.site_map_point_id: r for r in visit.results}

    _draw_company_header(c, company, "Relatório de monitorização", page_w, page_h)

    y = page_h - margin - 58 * mm
    c.setFont(FONT_BOLD, 10)
    c.drawString(margin, y, "Dados da visita")
    y -= 12

    lines = [
        f"Cliente: {_safe(getattr(client, 'business_name', None) or getattr(client, 'name', None))}",
        f"Código: {_safe(getattr(client, 'client_code', None), str(client.id))}",
        f"Data: {visit.visit_date.strftime('%d/%m/%Y %H:%M') if visit.visit_date else '—'}",
        f"Praga: {_safe(visit.pest_type or getattr(client, 'pest_type', None))}",
    ]

    c.setFont(FONT_REGULAR, 9)
    for ln in lines:
        c.drawString(margin, y, ln)
        y -= 10

    for idx, site_map in enumerate(site_maps):
        if idx > 0:
            c.showPage()
            _draw_company_header(c, company, "Relatório de monitorização", page_w, page_h)
            y = page_h - margin - 58 * mm

        c.setFont(FONT_BOLD, 10)
        c.drawString(margin, y, f"Mapa: {site_map.name}")
        y -= 8

        map_x = margin
        map_y = 72 * mm
        map_w = 120 * mm
        map_h = 130 * mm

        c.setStrokeColor(colors.HexColor("#9CA3AF"))
        c.rect(map_x, map_y, map_w, map_h, stroke=1, fill=0)

        img_abs = _img_abs_path(site_map.image_path)

        if img_abs and img_abs.exists():
            try:
                reader = ImageReader(str(img_abs))
                iw, ih = reader.getSize()
                scale = min(map_w / iw, map_h / ih)
                draw_w = iw * scale
                draw_h = ih * scale
                draw_x = map_x + (map_w - draw_w) / 2
                draw_y = map_y + (map_h - draw_h) / 2

                c.drawImage(
                    str(img_abs),
                    draw_x,
                    draw_y,
                    width=draw_w,
                    height=draw_h,
                    preserveAspectRatio=True,
                    mask="auto",
                )

                for p in site_map.points:
                    if not p.is_active:
                        continue

                    cx = draw_x + (p.x_percent / 100.0) * draw_w
                    cy = draw_y + ((100.0 - p.y_percent) / 100.0) * draw_h
                    _draw_marker(c, cx, cy, p.point_number, p.device_type)

            except Exception:
                c.setFont(FONT_REGULAR, 10)
                c.drawString(map_x + 10, map_y + map_h - 20, "Erro ao carregar imagem.")
        else:
            c.setFont(FONT_REGULAR, 10)
            c.drawString(map_x + 10, map_y + map_h - 20, "Imagem da planta não encontrada.")

        _draw_legend(c, map_x + map_w + 10 * mm, page_h - margin - 85 * mm)

        table_x = margin
        table_y = 56 * mm

        c.setFont(FONT_BOLD, 9)
        c.drawString(table_x, table_y, "Resultados dos pontos")
        table_y -= 12

        headers = ["Ponto", "Tipo", "Estado", "Consumo%", "Ação", "Notas"]
        col_x = [
            table_x,
            table_x + 14 * mm,
            table_x + 50 * mm,
            table_x + 72 * mm,
            table_x + 95 * mm,
            table_x + 126 * mm,
        ]

        c.setFont(FONT_BOLD, 8)
        for i, h in enumerate(headers):
            c.drawString(col_x[i], table_y, h)

        table_y -= 6
        c.line(table_x, table_y, page_w - margin, table_y)
        table_y -= 10

        c.setFont(FONT_REGULAR, 8)
        for p in site_map.points:
            r = results_by_point_id.get(p.id)

            c.drawString(col_x[0], table_y, str(p.point_number))
            c.drawString(col_x[1], table_y, _device_label(p.device_type)[:22])
            c.drawString(col_x[2], table_y, _safe(getattr(r, "status_code", None), "—"))

            cons = getattr(r, "consumption_percent", None)
            c.drawString(col_x[3], table_y, f"{float(cons):.0f}%" if cons is not None else "—")
            c.drawString(col_x[4], table_y, _safe(getattr(r, "action_taken", None), "—")[:16])
            c.drawString(col_x[5], table_y, _safe(getattr(r, "notes", None), "—")[:30])

            table_y -= 10

            if table_y < 22 * mm:
                break

        c.setFont(FONT_BOLD, 9)
        c.drawString(margin, 18 * mm, "Observações gerais:")

        c.setFont(FONT_REGULAR, 9)
        c.drawString(margin + 35 * mm, 18 * mm, _safe(visit.notes, ""))

        _draw_footer(c, page_w)

    if not site_maps:
        c.setFont(FONT_REGULAR, 10)
        c.drawString(margin, 100 * mm, "Não existem mapas cadastrados para este cliente.")
        _draw_footer(c, page_w)

    c.save()
    buf.seek(0)

    return buf.getvalue()