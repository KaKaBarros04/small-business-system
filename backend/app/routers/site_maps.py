from __future__ import annotations

import os
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import Response
from sqlalchemy.orm import Session, joinedload

from app.core.auth import get_current_user
from app.core.deps import get_db
from app.core.permission_guard import require_permission
from app.models.user import User
from app.models.client import Client
from app.models.company import Company
from app.models.appointment import Appointment
from app.models.site_map import SiteMap
from app.models.site_map_point import SiteMapPoint
from app.models.monitoring_visit import MonitoringVisit
from app.models.monitoring_point_result import MonitoringPointResult
from app.schemas.site_map import (
    SiteMapCreate,
    SiteMapUpdate,
    SiteMapOut,
    SiteMapPointCreate,
    SiteMapPointUpdate,
    SiteMapPointOut,
    MonitoringVisitCreate,
    MonitoringVisitUpdate,
    MonitoringVisitOut,
)
from app.services.pdf_monitoring import build_site_map_pdf, build_monitoring_visit_pdf
from app.utils.audit import log_action

router = APIRouter(prefix="/site-maps", tags=["site-maps"])

BASE_DIR = Path(__file__).resolve().parents[2]   # backend/
UPLOADS_DIR = BASE_DIR / "uploads"
SITE_MAPS_DIR = UPLOADS_DIR / "site_maps"
SITE_MAPS_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _company_or_404(db: Session, company_id: int) -> Company:
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Empresa não encontrada")
    return company


def _client_or_404(db: Session, company_id: int, client_id: int) -> Client:
    client = (
        db.query(Client)
        .filter(Client.id == client_id, Client.company_id == company_id)
        .first()
    )
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return client


def _site_map_or_404(db: Session, company_id: int, map_id: int) -> SiteMap:
    site_map = (
        db.query(SiteMap)
        .options(joinedload(SiteMap.points))
        .filter(SiteMap.id == map_id, SiteMap.company_id == company_id)
        .first()
    )
    if not site_map:
        raise HTTPException(status_code=404, detail="Mapa não encontrado")
    return site_map


def _point_or_404(db: Session, company_id: int, point_id: int) -> SiteMapPoint:
    point = (
        db.query(SiteMapPoint)
        .join(SiteMap, SiteMap.id == SiteMapPoint.site_map_id)
        .filter(SiteMap.company_id == company_id, SiteMapPoint.id == point_id)
        .first()
    )
    if not point:
        raise HTTPException(status_code=404, detail="Ponto não encontrado")
    return point


def _visit_or_404(db: Session, company_id: int, visit_id: int) -> MonitoringVisit:
    visit = (
        db.query(MonitoringVisit)
        .options(joinedload(MonitoringVisit.results))
        .filter(MonitoringVisit.id == visit_id, MonitoringVisit.company_id == company_id)
        .first()
    )
    if not visit:
        raise HTTPException(status_code=404, detail="Visita não encontrada")
    return visit


def _save_upload(company_id: int, client_id: int, upload: UploadFile) -> str:
    filename = upload.filename or ""
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTS:
        raise HTTPException(
            status_code=400,
            detail="Formato inválido. Use PNG, JPG, JPEG ou WEBP.",
        )

    dest_dir = SITE_MAPS_DIR / str(company_id) / str(client_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}{ext}"
    dest = dest_dir / safe_name

    with dest.open("wb") as f:
        shutil.copyfileobj(upload.file, f)

    return f"/uploads/site_maps/{company_id}/{client_id}/{safe_name}"


def _abs_upload_path(rel_path: str) -> Path | None:
    if not rel_path:
        return None
    rel = rel_path.lstrip("/")
    p = BASE_DIR / rel
    return p


def _next_point_number(db: Session, map_id: int) -> int:
    last = (
        db.query(SiteMapPoint)
        .filter(SiteMapPoint.site_map_id == map_id)
        .order_by(SiteMapPoint.point_number.desc())
        .first()
    )
    return (last.point_number if last else 0) + 1


# -----------------------------
# MAPAS
# -----------------------------
@router.get("/client/{client_id}", response_model=list[SiteMapOut])
def list_client_site_maps(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "view")

    _client_or_404(db, current_user.company_id, client_id)

    maps = (
        db.query(SiteMap)
        .options(joinedload(SiteMap.points))
        .filter(
            SiteMap.company_id == current_user.company_id,
            SiteMap.client_id == client_id,
        )
        .order_by(SiteMap.page_order.asc(), SiteMap.id.asc())
        .all()
    )
    return maps


@router.get("/{map_id}", response_model=SiteMapOut)
def get_site_map(
    map_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "view")
    return _site_map_or_404(db, current_user.company_id, map_id)


@router.post("", response_model=SiteMapOut, status_code=status.HTTP_201_CREATED)
@router.post("/", response_model=SiteMapOut, status_code=status.HTTP_201_CREATED)
def create_site_map(
    client_id: int = Form(...),
    name: str = Form(...),
    page_order: int = Form(1),
    notes: str | None = Form(None),
    is_active: bool = Form(True),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "create")

    client = _client_or_404(db, current_user.company_id, client_id)

    image_path = _save_upload(current_user.company_id, client_id, image)

    site_map = SiteMap(
        company_id=current_user.company_id,
        client_id=client.id,
        name=name.strip(),
        image_path=image_path,
        page_order=max(1, int(page_order or 1)),
        notes=notes.strip() if notes else None,
        is_active=bool(is_active),
    )

    db.add(site_map)
    db.flush()

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="CREATE",
        entity="site_maps",
        entity_id=site_map.id,
        old_values=None,
        new_values={
            "id": site_map.id,
            "client_id": site_map.client_id,
            "name": site_map.name,
            "image_path": site_map.image_path,
            "page_order": site_map.page_order,
            "is_active": site_map.is_active,
        },
    )

    db.commit()
    db.refresh(site_map)
    return site_map


@router.put("/{map_id}", response_model=SiteMapOut)
def update_site_map(
    map_id: int,
    payload: SiteMapUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "edit")

    site_map = _site_map_or_404(db, current_user.company_id, map_id)

    old_data = {
        "name": site_map.name,
        "page_order": site_map.page_order,
        "notes": site_map.notes,
        "is_active": site_map.is_active,
    }

    if payload.name is not None:
        site_map.name = payload.name.strip()
    if payload.page_order is not None:
        site_map.page_order = max(1, int(payload.page_order))
    if payload.notes is not None:
        site_map.notes = payload.notes.strip() if payload.notes else None
    if payload.is_active is not None:
        site_map.is_active = bool(payload.is_active)

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="UPDATE",
        entity="site_maps",
        entity_id=site_map.id,
        old_values=old_data,
        new_values={
            "name": site_map.name,
            "page_order": site_map.page_order,
            "notes": site_map.notes,
            "is_active": site_map.is_active,
        },
    )

    db.commit()
    db.refresh(site_map)
    return site_map


@router.delete("/{map_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_site_map(
    map_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "delete")

    site_map = _site_map_or_404(db, current_user.company_id, map_id)

    old_data = {
        "id": site_map.id,
        "client_id": site_map.client_id,
        "name": site_map.name,
        "image_path": site_map.image_path,
    }

    abs_path = _abs_upload_path(site_map.image_path)

    db.delete(site_map)

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="DELETE",
        entity="site_maps",
        entity_id=map_id,
        old_values=old_data,
        new_values=None,
    )

    db.commit()

    if abs_path and abs_path.exists():
        try:
            abs_path.unlink(missing_ok=True)
        except Exception:
            pass

    return None


@router.get("/{map_id}/pdf")
def site_map_pdf(
    map_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "view")

    site_map = _site_map_or_404(db, current_user.company_id, map_id)
    client = _client_or_404(db, current_user.company_id, site_map.client_id)
    company = _company_or_404(db, current_user.company_id)

    pdf_bytes = build_site_map_pdf(company=company, client=client, site_map=site_map)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="site_map_{map_id}.pdf"'},
    )


# -----------------------------
# PONTOS
# -----------------------------
@router.get("/{map_id}/points", response_model=list[SiteMapPointOut])
def list_map_points(
    map_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "view")

    _site_map_or_404(db, current_user.company_id, map_id)

    points = (
        db.query(SiteMapPoint)
        .filter(SiteMapPoint.site_map_id == map_id)
        .order_by(SiteMapPoint.point_number.asc(), SiteMapPoint.id.asc())
        .all()
    )
    return points


@router.post("/{map_id}/points", response_model=SiteMapPointOut, status_code=status.HTTP_201_CREATED)
def create_map_point(
    map_id: int,
    payload: SiteMapPointCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "create")

    site_map = _site_map_or_404(db, current_user.company_id, map_id)

    point = SiteMapPoint(
        site_map_id=site_map.id,
        point_number=int(payload.point_number or _next_point_number(db, map_id)),
        label=payload.label.strip() if payload.label else None,
        device_type=payload.device_type.strip().upper(),
        x_percent=float(payload.x_percent),
        y_percent=float(payload.y_percent),
        is_active=bool(payload.is_active),
    )

    db.add(point)
    db.flush()

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="CREATE",
        entity="site_map_points",
        entity_id=point.id,
        old_values=None,
        new_values={
            "site_map_id": point.site_map_id,
            "point_number": point.point_number,
            "label": point.label,
            "device_type": point.device_type,
            "x_percent": point.x_percent,
            "y_percent": point.y_percent,
            "is_active": point.is_active,
        },
    )

    db.commit()
    db.refresh(point)
    return point


@router.put("/points/{point_id}", response_model=SiteMapPointOut)
def update_map_point(
    point_id: int,
    payload: SiteMapPointUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "edit")

    point = _point_or_404(db, current_user.company_id, point_id)

    old_data = {
        "point_number": point.point_number,
        "label": point.label,
        "device_type": point.device_type,
        "x_percent": point.x_percent,
        "y_percent": point.y_percent,
        "is_active": point.is_active,
    }

    if payload.point_number is not None:
        point.point_number = int(payload.point_number)
    if payload.label is not None:
        point.label = payload.label.strip() if payload.label else None
    if payload.device_type is not None:
        point.device_type = payload.device_type.strip().upper()
    if payload.x_percent is not None:
        point.x_percent = float(payload.x_percent)
    if payload.y_percent is not None:
        point.y_percent = float(payload.y_percent)
    if payload.is_active is not None:
        point.is_active = bool(payload.is_active)

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="UPDATE",
        entity="site_map_points",
        entity_id=point.id,
        old_values=old_data,
        new_values={
            "point_number": point.point_number,
            "label": point.label,
            "device_type": point.device_type,
            "x_percent": point.x_percent,
            "y_percent": point.y_percent,
            "is_active": point.is_active,
        },
    )

    db.commit()
    db.refresh(point)
    return point


@router.delete("/points/{point_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_map_point(
    point_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "delete")

    point = _point_or_404(db, current_user.company_id, point_id)

    old_data = {
        "site_map_id": point.site_map_id,
        "point_number": point.point_number,
        "label": point.label,
    }

    db.delete(point)

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="DELETE",
        entity="site_map_points",
        entity_id=point_id,
        old_values=old_data,
        new_values=None,
    )

    db.commit()
    return None


# -----------------------------
# VISITAS DE MONITORIZAÇÃO
# -----------------------------
@router.post("/visits", response_model=MonitoringVisitOut, status_code=status.HTTP_201_CREATED)
@router.post("/visits/", response_model=MonitoringVisitOut, status_code=status.HTTP_201_CREATED)
def create_monitoring_visit(
    payload: MonitoringVisitCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "create")

    client = _client_or_404(db, current_user.company_id, payload.client_id)

    if payload.appointment_id is not None:
        appt = (
            db.query(Appointment)
            .filter(
                Appointment.id == payload.appointment_id,
                Appointment.company_id == current_user.company_id,
                Appointment.client_id == client.id,
            )
            .first()
        )
        if not appt:
            raise HTTPException(status_code=404, detail="Agendamento não encontrado para este cliente.")
    else:
        appt = None

    visit = MonitoringVisit(
        company_id=current_user.company_id,
        client_id=client.id,
        appointment_id=payload.appointment_id,
        user_id=current_user.id,
        visit_date=payload.visit_date or datetime.utcnow(),
        pest_type=(payload.pest_type.strip() if payload.pest_type else None),
        notes=(payload.notes.strip() if payload.notes else None),
    )

    db.add(visit)
    db.flush()

    for item in payload.results:
        point = (
            db.query(SiteMapPoint)
            .join(SiteMap, SiteMap.id == SiteMapPoint.site_map_id)
            .filter(
                SiteMap.company_id == current_user.company_id,
                SiteMap.client_id == client.id,
                SiteMapPoint.id == item.site_map_point_id,
            )
            .first()
        )
        if not point:
            raise HTTPException(
                status_code=400,
                detail=f"Ponto inválido para este cliente: {item.site_map_point_id}",
            )

        db.add(MonitoringPointResult(
            visit_id=visit.id,
            site_map_point_id=point.id,
            status_code=item.status_code.strip().upper() if item.status_code else None,
            consumption_percent=item.consumption_percent,
            action_taken=item.action_taken.strip() if item.action_taken else None,
            notes=item.notes.strip() if item.notes else None,
            replaced=bool(item.replaced),
        ))

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="CREATE",
        entity="monitoring_visits",
        entity_id=visit.id,
        old_values=None,
        new_values={
            "client_id": visit.client_id,
            "appointment_id": visit.appointment_id,
            "visit_date": visit.visit_date.isoformat() if visit.visit_date else None,
            "pest_type": visit.pest_type,
            "results_count": len(payload.results or []),
        },
    )

    db.commit()
    db.refresh(visit)
    return _visit_or_404(db, current_user.company_id, visit.id)


@router.get("/visits/client/{client_id}", response_model=list[MonitoringVisitOut])
def list_client_monitoring_visits(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "view")

    _client_or_404(db, current_user.company_id, client_id)

    visits = (
        db.query(MonitoringVisit)
        .options(joinedload(MonitoringVisit.results))
        .filter(
            MonitoringVisit.company_id == current_user.company_id,
            MonitoringVisit.client_id == client_id,
        )
        .order_by(MonitoringVisit.visit_date.desc(), MonitoringVisit.id.desc())
        .all()
    )
    return visits


@router.get("/visits/{visit_id}", response_model=MonitoringVisitOut)
def get_monitoring_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "view")
    return _visit_or_404(db, current_user.company_id, visit_id)


@router.put("/visits/{visit_id}", response_model=MonitoringVisitOut)
def update_monitoring_visit(
    visit_id: int,
    payload: MonitoringVisitUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "edit")

    visit = _visit_or_404(db, current_user.company_id, visit_id)
    client = _client_or_404(db, current_user.company_id, visit.client_id)

    old_data = {
        "appointment_id": visit.appointment_id,
        "visit_date": visit.visit_date.isoformat() if visit.visit_date else None,
        "pest_type": visit.pest_type,
        "notes": visit.notes,
        "results_count": len(visit.results or []),
    }

    if payload.appointment_id is not None:
        appt = (
            db.query(Appointment)
            .filter(
                Appointment.id == payload.appointment_id,
                Appointment.company_id == current_user.company_id,
                Appointment.client_id == client.id,
            )
            .first()
        )
        if not appt:
            raise HTTPException(status_code=404, detail="Agendamento não encontrado para este cliente.")
        visit.appointment_id = payload.appointment_id

    if payload.visit_date is not None:
        visit.visit_date = payload.visit_date
    if payload.pest_type is not None:
        visit.pest_type = payload.pest_type.strip() if payload.pest_type else None
    if payload.notes is not None:
        visit.notes = payload.notes.strip() if payload.notes else None

    if payload.results is not None:
        db.query(MonitoringPointResult).filter(
            MonitoringPointResult.visit_id == visit.id
        ).delete(synchronize_session=False)

        for item in payload.results:
            point = (
                db.query(SiteMapPoint)
                .join(SiteMap, SiteMap.id == SiteMapPoint.site_map_id)
                .filter(
                    SiteMap.company_id == current_user.company_id,
                    SiteMap.client_id == client.id,
                    SiteMapPoint.id == item.site_map_point_id,
                )
                .first()
            )
            if not point:
                raise HTTPException(
                    status_code=400,
                    detail=f"Ponto inválido para este cliente: {item.site_map_point_id}",
                )

            db.add(MonitoringPointResult(
                visit_id=visit.id,
                site_map_point_id=point.id,
                status_code=item.status_code.strip().upper() if item.status_code else None,
                consumption_percent=item.consumption_percent,
                action_taken=item.action_taken.strip() if item.action_taken else None,
                notes=item.notes.strip() if item.notes else None,
                replaced=bool(item.replaced),
            ))

    log_action(
        db=db,
        company_id=current_user.company_id,
        user_id=current_user.id,
        action="UPDATE",
        entity="monitoring_visits",
        entity_id=visit.id,
        old_values=old_data,
        new_values={
            "appointment_id": visit.appointment_id,
            "visit_date": visit.visit_date.isoformat() if visit.visit_date else None,
            "pest_type": visit.pest_type,
            "notes": visit.notes,
            "results_count": len(payload.results or visit.results or []),
        },
    )

    db.commit()
    db.refresh(visit)
    return _visit_or_404(db, current_user.company_id, visit.id)


@router.get("/visits/{visit_id}/pdf")
def monitoring_visit_pdf(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_permission(db, current_user, "site_maps", "view")

    visit = (
        db.query(MonitoringVisit)
        .options(joinedload(MonitoringVisit.results))
        .filter(
            MonitoringVisit.id == visit_id,
            MonitoringVisit.company_id == current_user.company_id,
        )
        .first()
    )
    if not visit:
        raise HTTPException(status_code=404, detail="Visita não encontrada")

    client = _client_or_404(db, current_user.company_id, visit.client_id)
    company = _company_or_404(db, current_user.company_id)

    site_maps = (
        db.query(SiteMap)
        .options(joinedload(SiteMap.points))
        .filter(
            SiteMap.company_id == current_user.company_id,
            SiteMap.client_id == client.id,
            SiteMap.is_active == True,  # noqa: E712
        )
        .order_by(SiteMap.page_order.asc(), SiteMap.id.asc())
        .all()
    )

    pdf_bytes = build_monitoring_visit_pdf(
        company=company,
        client=client,
        visit=visit,
        site_maps=site_maps,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="monitoring_visit_{visit_id}.pdf"'},
    )