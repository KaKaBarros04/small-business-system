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


def build_visits_pdf(*, company: dict, rows: list[dict], start: datetime, end: datetime) -> bytes:
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    margin_x = 10 * mm
    margin_top = 12 * mm
    margin_bottom = 12 * mm

    # ====== Layout: Número | Nome | Morada | Data
    x_num = margin_x
    w_num = 18 * mm

    x_name = x_num + w_num
    w_name = 78 * mm

    x_addr = x_name + w_name
    w_addr = 78 * mm

    x_date = x_addr + w_addr
    w_date = W - margin_x - x_date

    x_right = W - margin_x

    y = H - margin_top
    page_no = 1

    def safe(s) -> str:
        return ("" if s is None else str(s)).strip()

    def dash(s: str) -> str:
        s = safe(s)
        return s if s else "—"

    def fmt_pt_date(dt: datetime) -> str:
        return dt.strftime("%d/%m/%Y") if dt else ""

    def fit_text(text: str, max_width: float, font: str, size: int) -> str:
        """Corta com reticências para caber exatamente na largura (em points)."""
        t = safe(text)
        if not t:
            return ""
        if stringWidth(t, font, size) <= max_width:
            return t
        ell = "…"
        lo, hi = 0, len(t)
        while lo < hi:
            mid = (lo + hi) // 2
            cand = (t[:mid].rstrip() + ell)
            if stringWidth(cand, font, size) <= max_width:
                lo = mid + 1
            else:
                hi = mid
        cut = max(0, lo - 1)
        return (t[:cut].rstrip() + ell) if cut > 0 else ell

    def parse_service_from_notes(notes: str) -> dict:
        """
        Lê morada de serviço a partir das notas:
          SERVICE_ADDR: Rua X nº 10
          SERVICE_PC: 1000-001
          SERVICE_CITY: Lisboa
        """
        if not notes:
            return {}

        out = {}
        for raw in str(notes).splitlines():
            line = raw.strip()
            upper = line.upper()

            if upper.startswith("SERVICE_ADDR:"):
                out["service_address"] = line.split(":", 1)[1].strip()
            elif upper.startswith("SERVICE_PC:"):
                out["service_postal_code"] = line.split(":", 1)[1].strip()
            elif upper.startswith("SERVICE_CITY:"):
                out["service_city"] = line.split(":", 1)[1].strip()

        return {k: v for k, v in out.items() if v}

    def pick_service_address(row: dict) -> tuple[str, str, str]:
        """
        Prioridade:
        1) service_address/service_postal_code/service_city
        2) SERVICE_* dentro de notes
        3) address/postal_code/city
        """
        notes = safe(row.get("notes"))
        tagged = parse_service_from_notes(notes)

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

    company_name_raw = dash(company.get("name") or company.get("business_name"))

    # ================= HEADER =================
    logo = company.get("logo") or company.get("logo_path")
    if logo:
        try:
            # Caso 1: bytes (imagem no banco)
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
            # Caso 2: caminho (string)
            else:
                logo_path = str(logo).strip()
                p = Path(logo_path)

                # Se vier "/uploads/..." (estilo URL), resolve para "<project>/uploads/..."
                if logo_path.startswith("/uploads/"):
                    project_root = Path(__file__).resolve().parents[2]
                    p = project_root / "uploads" / logo_path.split("/uploads/", 1)[1]

                # Se for relativo, resolve a partir da raiz do projeto
                elif not p.is_absolute():
                    project_root = Path(__file__).resolve().parents[2]
                    p = (project_root / p).resolve()

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

    # limita o nome da empresa para não invadir outras linhas
    c.setFont("Helvetica-Bold", 14)
    company_name = fit_text(company_name_raw.upper(), max_width=135 * mm, font="Helvetica-Bold", size=14)
    c.drawCentredString(W / 2, y, company_name)
    y -= 6 * mm

    c.setFont("Helvetica", 9)
    c.drawCentredString(W / 2, y, f"Entre {fmt_pt_date(start)} e {fmt_pt_date(end)}")
    y -= 7 * mm

    c.setFont("Helvetica-Bold", 13)
    c.drawCentredString(W / 2, y, "Lista de Clientes a visitar")
    y -= 8 * mm

    def draw_footer():
        c.setFont("Helvetica", 9)
        c.setFillColor(colors.black)
        c.drawCentredString(W / 2, 8 * mm, f"Página {page_no}")

    def draw_table_header():
        nonlocal y
        c.setLineWidth(1.0)
        c.line(margin_x, y, x_right, y)
        y -= 5 * mm

        c.setFont("Helvetica-Bold", 9)
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
        c.setFont("Helvetica", 9)

    def new_page():
        nonlocal y, page_no
        draw_footer()
        c.showPage()
        page_no += 1
        y = H - margin_top

        # repete header em cada página
        logo2 = company.get("logo") or company.get("logo_path")
        if logo2:
            try:
                if isinstance(logo2, (bytes, bytearray)):
                    img2 = ImageReader(BytesIO(logo2))
                    c.drawImage(
                        img2,
                        margin_x,
                        y - 18 * mm,
                        width=34 * mm,
                        height=18 * mm,
                        preserveAspectRatio=True,
                        mask="auto",
                    )
                else:
                    logo_path2 = str(logo2).strip()
                    p2 = Path(logo_path2)

                    if logo_path2.startswith("/uploads/"):
                        project_root = Path(__file__).resolve().parents[2]
                        p2 = project_root / "uploads" / logo_path2.split("/uploads/", 1)[1]
                    elif not p2.is_absolute():
                        project_root = Path(__file__).resolve().parents[2]
                        p2 = (project_root / p2).resolve()

                    if p2.exists() and p2.is_file():
                        img2 = ImageReader(str(p2))
                        c.drawImage(
                            img2,
                            margin_x,
                            y - 18 * mm,
                            width=34 * mm,
                            height=18 * mm,
                            preserveAspectRatio=True,
                            mask="auto",
                        )
            except Exception:
                pass

        c.setFont("Helvetica-Bold", 14)
        company_name2 = fit_text(company_name_raw.upper(), max_width=135 * mm, font="Helvetica-Bold", size=14)
        c.drawCentredString(W / 2, y, company_name2)
        y -= 6 * mm

        c.setFont("Helvetica", 9)
        c.drawCentredString(W / 2, y, f"Entre {fmt_pt_date(start)} e {fmt_pt_date(end)}")
        y -= 7 * mm

        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(W / 2, y, "Lista de Clientes a visitar")
        y -= 8 * mm

        draw_table_header()

    # Cabeçalho da tabela na 1ª página
    draw_table_header()

    # ================= LINHAS =================
    row_h = 12 * mm
    line_gap = 4.2 * mm

    for r in rows:
        if y < margin_bottom + row_h:
            new_page()

        client_code = dash(r.get("client_code"))
        client_name_raw = dash(r.get("business_name"))

        # usa morada de serviço; fallback para fiscal
        addr, postal, city = pick_service_address(r)

        date_str = dash(r.get("scheduled_at_str"))

        # Número (código)
        c.setFont("Helvetica", 9)
        c.drawString(x_num + 1.5 * mm, y, client_code[:12])

        # Nome (cliente)
        c.setFont("Helvetica-Bold", 9)
        client_name = fit_text(client_name_raw, max_width=w_name - 3 * mm, font="Helvetica-Bold", size=9)
        c.drawString(x_name + 1.5 * mm, y, client_name)

        # Morada (linha 1) + postal/cidade (linha 2)
        c.setFont("Helvetica", 9)
        addr1 = fit_text(addr, max_width=w_addr - 3 * mm, font="Helvetica", size=9)
        c.drawString(x_addr + 1.5 * mm, y, addr1)

        addr2 = " ".join([x for x in [postal, city] if x]).strip()
        if addr2:
            c.setFont("Helvetica", 8)
            addr2_fit = fit_text(addr2, max_width=w_addr - 3 * mm, font="Helvetica", size=8)
            c.drawString(x_addr + 1.5 * mm, y - line_gap, addr2_fit)

        # Data
        c.setFont("Helvetica", 9)
        c.drawString(x_date + 1.5 * mm, y, date_str[:12])

        y -= row_h

    draw_footer()
    c.save()
    return buf.getvalue()