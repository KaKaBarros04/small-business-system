from contextvars import ContextVar
from typing import Optional

audit_user_id: ContextVar[Optional[int]] = ContextVar("audit_user_id", default=None)
audit_company_id: ContextVar[Optional[int]] = ContextVar("audit_company_id", default=None)
audit_ip: ContextVar[Optional[str]] = ContextVar("audit_ip", default=None)
audit_user_agent: ContextVar[Optional[str]] = ContextVar("audit_user_agent", default=None)

def set_audit_context(*, user_id: int | None, company_id: int | None, ip: str | None, user_agent: str | None):
    audit_user_id.set(user_id)
    audit_company_id.set(company_id)
    audit_ip.set(ip)
    audit_user_agent.set(user_agent)

def get_audit_context():
    return {
        "user_id": audit_user_id.get(),
        "company_id": audit_company_id.get(),
        "ip": audit_ip.get(),
        "user_agent": audit_user_agent.get(),
    }
