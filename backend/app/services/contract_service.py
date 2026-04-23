from __future__ import annotations

from datetime import datetime, time

from sqlalchemy.orm import Session

from app.models.contract import Contract
from app.models.appointment import Appointment
from app.models.service import Service
from app.services.contract_scheduler import generate_visit_dates


def create_contract_visits(
    db: Session,
    *,
    contract: Contract,
    user_id: int,
    default_service: Service,
    address: str,
) -> list[int]:
    """
    Cria appointments para um contrato (visitas distribuídas no ano),
    respeitando cutoff_days.
    Retorna lista de IDs criados.

    As visitas são criadas com horas sequenciais:
    09:00, 10:00, 11:00, 12:00...
    """
    dates = generate_visit_dates(
        start_date=contract.start_date,
        visits_per_year=contract.visits_per_year,
        cutoff_days=contract.cutoff_days,
    )

    created_ids: list[int] = []
    start_hour = 9

    for idx, d in enumerate(dates):
        hour = start_hour + idx

        # segurança para não passar muito do horário normal
        if hour > 18:
            hour = 18

        scheduled_dt = datetime.combine(d, time(hour, 0))

        appt = Appointment(
            company_id=contract.company_id,
            user_id=user_id,
            client_id=contract.client_id,
            service_id=default_service.id,
            scheduled_at=scheduled_dt,
            address=address,
            price=float(default_service.base_price or 0),
            status="SCHEDULED",
            is_contract_visit=True,
            contract_id=contract.id,

            service_name=getattr(default_service, "name", None) or "Serviço",
            service_price=float(getattr(default_service, "base_price", 0) or 0),
        )
        db.add(appt)
        db.flush()
        created_ids.append(appt.id)

    return created_ids