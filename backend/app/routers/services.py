from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.deps import get_db
from app.models.user import User
from app.models.service import Service
from app.schemas.service import ServiceCreate, ServiceUpdate, ServiceOut

router = APIRouter(prefix="/services", tags=["services"])


@router.post("", response_model=ServiceOut, status_code=status.HTTP_201_CREATED)
def create_service(
    payload: ServiceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # opcional: impedir serviços com mesmo nome (por user)
    exists = (
        db.query(Service)
        .filter(Service.company_id == current_user.company_id, Service.name == payload.name.strip())
        .first()
    )
    if exists:
        raise HTTPException(status_code=409, detail="Já existe um serviço com este nome")

    service = Service(
        company_id=current_user.company_id,
        name=payload.name.strip(),
        base_price=float(payload.base_price),
        duration_minutes=int(payload.duration_minutes),
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return service


@router.get("", response_model=list[ServiceOut])
def list_services(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Service)
        .filter(Service.company_id == current_user.company_id)
        .order_by(Service.id.desc())
        .all()
    )


@router.get("/{service_id}", response_model=ServiceOut)
def get_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = (
        db.query(Service)
        .filter(Service.id == service_id, Service.company_id == current_user.company_id)
        .first()
    )
    if not service:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    return service


@router.put("/{service_id}", response_model=ServiceOut)
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = (
        db.query(Service)
        .filter(Service.id == service_id, Service.company_id == current_user.company_id)
        .first()
    )
    if not service:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    if payload.name is not None:
        new_name = payload.name.strip()
        # opcional: impedir duplicado ao editar
        exists = (
            db.query(Service)
            .filter(
                Service.company_id == current_user.company_id,
                Service.name == new_name,
                Service.id != service_id,
            )
            .first()
        )
        if exists:
            raise HTTPException(status_code=409, detail="Já existe um serviço com este nome")
        service.name = new_name

    if payload.base_price is not None:
        service.base_price = float(payload.base_price)

    if payload.duration_minutes is not None:
        service.duration_minutes = int(payload.duration_minutes)

    db.commit()
    db.refresh(service)
    return service


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(
    service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service = (
        db.query(Service)
        .filter(Service.id == service_id, Service.company_id == current_user.company_id)
        .first()
    )
    if not service:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    db.delete(service)
    db.commit()
    return None
