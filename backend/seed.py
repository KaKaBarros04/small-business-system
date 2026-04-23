from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.group import Group
from app.models.company import Company

def run():
    db: Session = SessionLocal()
    try:
        g = Group(name="Grupo Mae")
        db.add(g)
        db.commit()
        db.refresh(g)

        a = Company(
            group_id=g.id,
            name="Empresa A",
            slug="empresa-a",
            vat_number="",
            address="",
            phone="",
            email="",
            iban="",
            invoice_prefix="FT-A",
            next_invoice_number=1,
        )
        b = Company(
            group_id=g.id,
            name="Empresa B",
            slug="empresa-b",
            vat_number="",
            address="",
            phone="",
            email="",
            iban="",
            invoice_prefix="FT-B",
            next_invoice_number=1,
        )
        db.add_all([a, b])
        db.commit()
        print("Seed OK: Grupo + Empresa A/B")
    finally:
        db.close()

if __name__ == "__main__":
    run()
