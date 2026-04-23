# app/utils/audit.py
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from app.models.audit_log import AuditLog


def _json_safe(value: Any):
    """
    Converte objetos não serializáveis para JSON:
    - Decimal -> float
    - datetime/date -> isoformat()
    - dict/list/tuple -> recursivo
    - outros -> str() (fallback)
    """
    if value is None:
        return None

    if isinstance(value, Decimal):
        # ⚠️ Se precisares precisão total, troca para: return str(value)
        return float(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [_json_safe(v) for v in value]

    # tipos simples OK
    if isinstance(value, (str, int, float, bool)):
        return value

    # fallback
    return str(value)


def log_action(
    *,
    db,
    company_id: int,
    user_id: int | None,
    action: str,
    entity: str,
    entity_id: int | None = None,
    old_values: Any = None,
    new_values: Any = None,
    ip: str | None = None,
    user_agent: str | None = None,
):
    log = AuditLog(
        company_id=company_id,
        user_id=user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        old_values=_json_safe(old_values),
        new_values=_json_safe(new_values),
        ip=ip,
        user_agent=user_agent,
    )
    db.add(log)
    # ⚠️ não faz commit aqui; quem chama decide
    return log
