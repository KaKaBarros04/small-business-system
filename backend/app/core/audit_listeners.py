from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.core.audit_context import get_audit_context

def _as_jsonable(v):
    # converte coisas tipo datetime/Decimal/etc para string simples
    try:
        import datetime
        if isinstance(v, (datetime.datetime, datetime.date)):
            return v.isoformat()
    except Exception:
        pass
    return v

def _get_entity_name(obj) -> str:
    # default: nome da tabela
    return getattr(obj, "__tablename__", obj.__class__.__name__).lower()

def _get_pk(obj):
    # tenta pegar "id" ou pk real
    if hasattr(obj, "id"):
        return getattr(obj, "id")
    insp = inspect(obj)
    if insp.identity and len(insp.identity) == 1:
        return insp.identity[0]
    return None

def _get_company_id(obj):
    # padrão no teu projeto: company_id
    if hasattr(obj, "company_id"):
        return getattr(obj, "company_id")
    # fallback: se ainda existir user_id em algum modelo antigo
    return None

def _diff_update(obj):
    insp = inspect(obj)
    old_vals = {}
    new_vals = {}
    for attr in insp.mapper.column_attrs:
        key = attr.key
        hist = insp.attrs[key].history
        if hist.has_changes():
            old_vals[key] = _as_jsonable(hist.deleted[0]) if hist.deleted else None
            new_vals[key] = _as_jsonable(hist.added[0]) if hist.added else _as_jsonable(getattr(obj, key))
    return old_vals, new_vals

def _snapshot(obj):
    insp = inspect(obj)
    data = {}
    for attr in insp.mapper.column_attrs:
        key = attr.key
        data[key] = _as_jsonable(getattr(obj, key))
    return data

def register_audit_listeners(Base, ignore_tables: set[str] | None = None):
    ignore_tables = ignore_tables or set()

    @event.listens_for(Session, "after_flush")
    def after_flush(session: Session, flush_context):
        ctx = get_audit_context()

        # se não tem company_id no contexto, não grava (evita lixo)
        # (ex.: tasks internas, seed, etc.)
        # mas dá pra gravar mesmo assim se você quiser.
        company_id_ctx = ctx.get("company_id")

        def add_log(action: str, obj, old_values=None, new_values=None):
            entity = _get_entity_name(obj)
            if entity in ignore_tables:
                return

            company_id = _get_company_id(obj) or company_id_ctx
            if not company_id:
                return

            session.add(
                AuditLog(
                    company_id=company_id,
                    user_id=ctx.get("user_id"),
                    action=action,
                    entity=entity,
                    entity_id=_get_pk(obj),
                    old_values=old_values,
                    new_values=new_values,
                    ip=ctx.get("ip"),
                    user_agent=(ctx.get("user_agent") or "")[:255] if ctx.get("user_agent") else None,
                )
            )

        # CREATE
        for obj in session.new:
            add_log("CREATE", obj, old_values=None, new_values=_snapshot(obj))

        # DELETE
        for obj in session.deleted:
            add_log("DELETE", obj, old_values=_snapshot(obj), new_values=None)

        # UPDATE
        for obj in session.dirty:
            if session.is_modified(obj, include_collections=False):
                old_vals, new_vals = _diff_update(obj)
                if old_vals or new_vals:
                    add_log("UPDATE", obj, old_values=old_vals, new_values=new_vals)
