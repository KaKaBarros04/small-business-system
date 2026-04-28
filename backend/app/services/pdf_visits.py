from __future__ import annotations

from io import BytesIO
from datetime import datetime
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


BASE_DIR = Path(__file__).resolve().parents[2]

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def _register_pdf_fonts():
    global FONT_REGULAR, FONT_BOLD

    candidates = [
        (str(BASE_DIR / "fonts" / "DejaVuSans.ttf"), str(BASE_DIR / "fonts" / "DejaVuSans-Bold.ttf")),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        ("/app/fonts/DejaVuSans.ttf", "/app/fonts/DejaVuSans-Bold.ttf"),
        ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ]

    for regular, bold in candidates:
        if Path(regular).exists() and Path(bold).exists():
            pdfmetrics.registerFont(TTFont("AppFont", regular))
            pdfmetrics.registerFont(TTFont("AppFont-Bold", bold))
            FONT_REGULAR = "AppFont"
            FONT_BOLD = "AppFont-Bold"
            return


_register_pdf_fonts()


def fix_mojibake(value) -> str:
    if value is None:
        return ""

    text = str(value)

    repl = {
        "├º": "ç",
        "├ú": "ã",
        "├í": "á",
        "├®": "é",
        "├¡": "í",
        "├│": "ó",
        "├║": "ú",
        "├á": "à",
        "├ó": "â",
        "├¬": "ê",
        "├┤": "ô",
        "├Á": "Á",
        "├Ç": "Ç",
        "├É": "É",
        "├Õ": "Õ",
        "┬º": "º",
        "┬ª": "ª",
        "Âº": "º",
        "Âª": "ª",
        "Ã§": "ç",
        "Ã£": "ã",
        "Ã¡": "á",
        "Ã©": "é",
        "Ã­": "í",
        "Ã³": "ó",
        "Ãº": "ú",
        "Ãµ": "õ",
        "Ãª": "ê",
        "Ã¢": "â",
        "Ã ": "à",
    }

    for bad, good in repl.items():
        text = text.replace(bad, good)

    if any(m in text for m in ("Ã", "Â")):
        for enc in ("latin1", "cp1252"):
            try:
                fixed = text.encode(enc).decode("utf-8")
                if fixed and fixed != text:
                    text = fixed
                    break
            except Exception:
                pass

    return text.strip()


def build_visits_pdf(*, company: dict, rows: list[dict], start: datetime, end: datetime) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    margin_x = 10 * mm
    margin_top = 12 * mm
    margin_bottom = 12 * mm

    x_num = margin_x
    w_num = 18 * mm

    x_name = x_num + w_num
    w_name = 78 * mm

    x_addr = x_name + w_name
    w_addr = 78 * mm

    x_date = x_addr + w_addr
    x_right = W - margin_x

    y = H - margin_top
    page_no = 1

    def safe(s) -> str:
        return fix_mojibake(s)

    def dash(s) -> str:
        s = safe(s)
        return s if s else "—"

    def fmt_pt_date(dt: datetime) -> str:
        return dt.strftime("%d/%m/%Y") if dt else ""

    def fit_text(text: str, max_width: float, font: str, size: int) -> str:
        t = safe(text)
        if not t:
            return ""

        if stringWidth(t, font, size) <= max_width:
            return t

        ell = "…"
        lo, hi = 0, len(t)

        while lo < hi:
            mid = (lo + hi) // 2
            cand = t[:mid].rstrip() + ell

            if stringWidth(cand, font, size) <= max_width:
                lo = mid + 1
            else:
                hi = mid

        cut = max(0, lo - 1)
        return (t[:cut].rstrip() + ell) if cut > 0 else ell

    def parse_service_from_notes(notes: str) -> dict:
        notes = safe(notes)
        if not notes:
            return {}

        out = {}

        for raw in notes.splitlines():
            line = raw.strip()
            upper = line.upper()

            if upper.startswith("SERVICE_ADDR:"):
                out["service_address"] = safe(line.split(":", 1)[1])
            elif upper.startswith("SERVICE_PC:"):
                out["service_postal_code"] = safe(line.split(":", 1)[1])
            elif upper.startswith("SERVICE_CITY:"):
                out["service_city"] = safe(line.split(":", 1)[1])

        return {k: v for k, v in out.items() if v}

    def pick_service_address(row: dict) -> tuple[str, str, str]:
        tagged = parse_service_from_notes(row.get("notes"))

        addr = (
            safe(row.get("service_address"))
            or safe(tagged.get("service_address"))
            or safe(row.get("address"))
        )

        postal = (
            safe(row.get("service_postal_code"))
            or safe(tagged.get("service_postal_code"))
            or safe(row.get("postal_code"))
        )

        city = (
            safe(row.get("service_city"))
            or safe(tagged.get("service_city"))
            or safe(row.get("city"))
        )

        return addr, postal, city

    def draw_logo():
        logo = company.get("logo") or company.get("logo_path")

        if not logo:
            return

        try:
            if isinstance(logo, (bytes, bytearray)):
                img = ImageReader(BytesIO(logo))
                c.drawImage(
                    img,
                    margin_x,
                    y - 18 * mm,
                    width=34 * mm,
                    height=18 * mm,
                    preserveAspectRatio=True,
                    mask="auto",
                )
                return

            logo_path = str(logo).strip()
            p = Path(logo_path)

            if logo_path.startswith("/uploads/"):
                p = BASE_DIR / "uploads" / logo_path.split("/uploads/", 1)[1]
            elif not p.is_absolute():
                p = (BASE_DIR / p).resolve()

            if p.exists() and p.is_file():
                img = ImageReader(str(p))
                c.drawImage(
                    img,
                    margin_x,
                    y - 18 * mm,
                    width=34 * mm,
                    height=18 * mm,
                    preserveAspectRatio=True,
                    mask="auto",
                )
        except Exception:
            pass

    company_name_raw = dash(company.get("name") or company.get("business_name"))

    def draw_main_header():
        nonlocal y

        draw_logo()

        c.setFillColor(colors.black)

        c.setFont(FONT_BOLD, 14)
        company_name = fit_text(company_name_raw.upper(), max_width=135 * mm, font=FONT_BOLD, size=14)
        c.drawCentredString(W / 2, y, company_name)
        y -= 6 * mm

        c.setFont(FONT_REGULAR, 9)
        c.drawCentredString(W / 2, y, f"Entre {fmt_pt_date(start)} e {fmt_pt_date(end)}")
        y -= 7 * mm

        c.setFont(FONT_BOLD, 13)
        c.drawCentredString(W / 2, y, "Lista de Clientes a visitar")
        y -= 8 * mm

    def draw_footer():
        c.setFont(FONT_REGULAR, 9)
        c.setFillColor(colors.black)
        c.drawCentredString(W / 2, 8 * mm, f"Página {page_no}")

    def draw_table_header():
        nonlocal y

        c.setStrokeColor(colors.black)
        c.setFillColor(colors.black)

        c.setLineWidth(1.0)
        c.line(margin_x, y, x_right, y)
        y -= 5 * mm

        c.setFont(FONT_BOLD, 9)
        c.drawString(x_num + 1.5 * mm, y, "Número")
        c.drawString(x_name + 1.5 * mm, y, "Nome")
        c.drawString(x_addr + 1.5 * mm, y, "Morada")
        c.drawString(x_date + 1.5 * mm, y, "Data")

        y -= 3 * mm

        c.setLineWidth(1.0)
        c.line(margin_x, y, x_right, y)

        y_top = y + 8 * mm
        y_bot = y

        c.setLineWidth(0.8)
        c.line(x_name, y_top, x_name, y_bot)
        c.line(x_addr, y_top, x_addr, y_bot)
        c.line(x_date, y_top, x_date, y_bot)

        y -= 6 * mm
        c.setFont(FONT_REGULAR, 9)

    def new_page():
        nonlocal y, page_no

        draw_footer()
        c.showPage()

        page_no += 1
        y = H - margin_top

        draw_main_header()
        draw_table_header()

    draw_main_header()
    draw_table_header()

    row_h = 12 * mm
    line_gap = 4.2 * mm

    for r in rows:
        if y < margin_bottom + row_h:
            new_page()

        client_code = dash(r.get("client_code"))
        client_name_raw = dash(r.get("business_name"))

        addr, postal, city = pick_service_address(r)
        date_str = dash(r.get("scheduled_at_str"))

        c.setFillColor(colors.black)

        c.setFont(FONT_REGULAR, 9)
        c.drawString(x_num + 1.5 * mm, y, client_code[:12])

        c.setFont(FONT_BOLD, 9)
        client_name = fit_text(client_name_raw, max_width=w_name - 3 * mm, font=FONT_BOLD, size=9)
        c.drawString(x_name + 1.5 * mm, y, client_name)

        c.setFont(FONT_REGULAR, 9)
        addr1 = fit_text(addr, max_width=w_addr - 3 * mm, font=FONT_REGULAR, size=9)
        c.drawString(x_addr + 1.5 * mm, y, addr1)

        addr2 = " ".join([x for x in [postal, city] if x]).strip()

        if addr2:
            c.setFont(FONT_REGULAR, 8)
            addr2_fit = fit_text(addr2, max_width=w_addr - 3 * mm, font=FONT_REGULAR, size=8)
            c.drawString(x_addr + 1.5 * mm, y - line_gap, addr2_fit)

        c.setFont(FONT_REGULAR, 9)
        c.drawString(x_date + 1.5 * mm, y, date_str[:12])

        y -= row_h

    draw_footer()
    c.save()

    return buf.getvalue()