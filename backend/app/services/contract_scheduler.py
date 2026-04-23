from __future__ import annotations

from datetime import date
from dateutil.relativedelta import relativedelta
import calendar


def safe_day(year: int, month: int, day: int) -> date:
    """Garante que o dia existe no mês (ex: dia 31 -> vira 30/28)."""
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day, last_day))


def generate_visit_dates(
    *,
    start_date: date,
    visits_per_year: int,
    cutoff_days: int = 0,
) -> list[date]:
    """
    Regra:
    - 1ª visita: mês de início (no mesmo dia do start_date, ajustado pelo safe_day)
    - resto distribuído igualmente ao longo de 12 meses
    - sempre no mesmo dia (ou último dia do mês quando não existir)
    - não cair nos últimos cutoff_days dias do contrato (1 ano)
    """
    v = int(visits_per_year or 0)
    if v < 1:
        return []

    cutoff = int(cutoff_days or 0)
    if cutoff < 0:
        cutoff = 0

    # fim do contrato = +12 meses
    contract_end = start_date + relativedelta(months=12)
    cutoff_limit = contract_end - relativedelta(days=cutoff)

    # Distribuição mensal: para v visitas, usamos step ≈ 12/v
    # Ex: v=3 -> 0, 4, 8 meses
    step = 12 / v
    start_day = start_date.day

    out: list[date] = []
    seen = set()

    for i in range(v):
        months = int(round(step * i))
        base = start_date + relativedelta(months=months)

        visit_date = safe_day(base.year, base.month, start_day)

        # cutoff: se caiu dentro da zona proibida, para (não cria mais)
        if visit_date >= cutoff_limit:
            break

        key = (visit_date.year, visit_date.month, visit_date.day)
        if key in seen:
            continue
        seen.add(key)
        out.append(visit_date)

    return out