from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from pathlib import Path


def generate_invoice_pdf(
    filepath: Path,
    invoice_number: str,
    company: dict,
    client: dict,
    items: list[dict],
    totals: dict,
    logo_abs_path: Path | None = None,
):
    w, h = A4
    c = canvas.Canvas(str(filepath), pagesize=A4)

    margin = 40
    y = h - margin

    # Logo
    if logo_abs_path and logo_abs_path.exists():
        try:
            img = ImageReader(str(logo_abs_path))
            c.drawImage(img, margin, y - 60, width=120, height=50, preserveAspectRatio=True, mask="auto")
        except Exception:
            pass

    # Company
    c.setFont("Helvetica-Bold", 14)
    c.drawString(margin + 140, y - 20, company.get("company_name", "") or "Empresa")
    c.setFont("Helvetica", 10)
    c.drawString(margin + 140, y - 36, f"NIF: {company.get('vat_number') or '-'}")
    c.drawString(margin + 140, y - 50, company.get("address") or "")
    c.drawString(margin + 140, y - 64, f"{company.get('phone') or ''} {company.get('email') or ''}".strip())

    # Title
    y -= 95
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, f"Fatura / Recibo: {invoice_number}")

    # Client block
    y -= 30
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "Cliente")
    y -= 14
    c.setFont("Helvetica", 10)
    c.drawString(margin, y, client.get("name", ""))
    y -= 14
    if client.get("email"):
        c.drawString(margin, y, client["email"]); y -= 14
    if client.get("phone"):
        c.drawString(margin, y, client["phone"]); y -= 14

    # Items table header
    y -= 12
    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, "Descrição")
    c.drawString(w - margin - 200, y, "Qtd")
    c.drawString(w - margin - 150, y, "Preço")
    c.drawString(w - margin - 80, y, "Total")
    y -= 8
    c.line(margin, y, w - margin, y)
    y -= 14

    # Items
    c.setFont("Helvetica", 10)
    for it in items:
        if y < 120:
            c.showPage()
            y = h - margin

        c.drawString(margin, y, it["description"])
        c.drawRightString(w - margin - 190, y, str(it["qty"]))
        c.drawRightString(w - margin - 120, y, f"€ {it['unit_price']:.2f}")
        c.drawRightString(w - margin, y, f"€ {it['line_total']:.2f}")
        y -= 16

    # Totals
    y -= 10
    c.line(margin, y, w - margin, y)
    y -= 18

    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(w - margin - 120, y, "Subtotal:")
    c.drawRightString(w - margin, y, f"€ {totals['subtotal']:.2f}")
    y -= 16
    c.setFont("Helvetica", 10)
    c.drawRightString(w - margin - 120, y, "IVA:")
    c.drawRightString(w - margin, y, f"€ {totals['tax']:.2f}")
    y -= 16
    c.setFont("Helvetica-Bold", 12)
    c.drawRightString(w - margin - 120, y, "Total:")
    c.drawRightString(w - margin, y, f"€ {totals['total']:.2f}")

    y -= 40
    c.setFont("Helvetica", 9)
    c.drawString(margin, y, "Documento gerado pelo sistema (uso interno/gestão).")

    c.save()
