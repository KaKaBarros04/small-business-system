from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.deps import get_db
from app.core.auth import get_current_user
from app.models.user import User
from app.models.client import Client

from app.services.dossier.builder import build_client_dossier_pdf

router = APIRouter(prefix="/clients", tags=["dossiers"])


@router.get("/{client_id}/dossier.pdf")
def client_dossier_pdf(
    client_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    pdf_bytes = build_client_dossier_pdf(db, client)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="dossier_{client_id}.pdf"'},
    )