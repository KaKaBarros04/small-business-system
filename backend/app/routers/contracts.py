from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.auth import get_current_user
from app.models.contract import Contract
from app.models.client import Client
from app.models.service import Service
from app.models.user import User
from app.schemas.contract import ContractCreate, ContractOut
from app.services.contract_service import create_contract_visits


router = APIRouter(prefix="/contracts", tags=["contracts"])


@router.post("", response_model=ContractOut)
def create_contract(
    payload: ContractCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(
        Client.id == payload.client_id,
        Client.company_id == current_user.company_id,
    ).first()

    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    default_service = db.query(Service).filter(
        Service.company_id == current_user.company_id
    ).first()

    if not default_service:
        raise HTTPException(status_code=400, detail="Nenhum serviço padrão encontrado")

    start = payload.start_date
    end = start + timedelta(days=365)

    contract = Contract(
        company_id=current_user.company_id,
        client_id=payload.client_id,
        start_date=start,
        end_date=end,
        visits_per_year=payload.visits_per_year,
    )

    db.add(contract)
    db.flush()

    create_contract_visits(
        db=db,
        contract=contract,
        user_id=current_user.id,
        default_service=default_service,
        address=client.name,  # depois troca por morada
    )

    db.commit()
    db.refresh(contract)
    return contract
