from fastapi import FastAPI, Depends
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from pathlib import Path

import app.models  # garante que todos os models sejam carregados

from app.core.database import engine, Base  # ✅ IMPORTANTE: trazer Base daqui

from app.routers.auth import router as auth_router
from app.routers.clients import router as clients_router
from app.core.auth import get_current_user
from app.models.user import User
from app.schemas.user import UserMe
from app.routers import company
from app.routers import services
from app.routers import appointments
from app.routers import manual_invoices
from app.routers import dashboard
from app.routers import expenses
from app.routers import audit_logs
from app.routers import group
from app.routers import reports
from app.routers import stock
from app.routers import reports_extra
from app.routers.admin_permissions import router as admin_permissions_router
from app.routers import admin_users
from app.routers.permissions_me import router as permissions_me_router
from app.routers.dossiers import router as dossiers_router
from app.core.audit_listeners import register_audit_listeners
from app.routers.dossiers import router as dossiers_router
from app.routers import site_maps
from app.routers import permissions

app = FastAPI(
    title="Small Business Management API",
    version="0.1.0",
)

BASE_DIR = Path(__file__).resolve().parents[1]  # backend/
UPLOADS_DIR = BASE_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

app.include_router(auth_router)
app.include_router(clients_router)
app.include_router(company.router)
app.include_router(services.router)
app.include_router(appointments.router)
app.include_router(manual_invoices.router)
app.include_router(dashboard.router)
app.include_router(expenses.router)
app.include_router(audit_logs.router)
app.include_router(group.router)
app.include_router(reports.router)
app.include_router(stock.router)
app.include_router(reports_extra.router)
app.include_router(admin_permissions_router)
app.include_router(admin_users.router)
app.include_router(permissions_me_router)
app.include_router(dossiers_router)
app.include_router(dossiers_router)
app.include_router(site_maps.router)
app.include_router(permissions.router)


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/db-check")
def db_check():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"db": "ok"}

@app.get("/me", response_model=UserMe)
def me(current_user: User = Depends(get_current_user)):
    return current_user
