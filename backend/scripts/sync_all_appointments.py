from app.core.database import SessionLocal
from app.models.appointment import Appointment
from app.models.company import Company
from app.integrations.google_calendar import safe_resync

from sqlalchemy.orm import joinedload

db = SessionLocal()

print("🚀 A sincronizar todos os agendamentos...")

appointments = (
    db.query(Appointment)
    .options(joinedload(Appointment.client))
    .all()
)

total = len(appointments)
ok = 0
fail = 0

for appt in appointments:
    try:
        company = db.query(Company).filter(Company.id == appt.company_id).first()

        if not company:
            print(f"❌ Empresa não encontrada para appt {appt.id}")
            fail += 1
            continue

        safe_resync(db=db, appointment=appt, company=company)

        print(f"✅ OK → {appt.id}")
        ok += 1

    except Exception as e:
        print(f"❌ ERRO → {appt.id} | {e}")
        fail += 1

print("\n====================")
print(f"TOTAL: {total}")
print(f"OK: {ok}")
print(f"FAIL: {fail}")
print("====================")