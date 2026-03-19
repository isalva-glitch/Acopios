"""Remitos router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import date

from database import get_db
from models import Remito

router = APIRouter()


# Pydantic models
class RemitoCreate(BaseModel):
    """Create remito payload."""
    pedido_id: int
    numero: str
    fecha: str
    descripcion: str = ""


class RemitoResponse(BaseModel):
    """Remito response."""
    id: int
    pedido_id: int
    numero: str
    fecha: str
    descripcion: str
    
    class Config:
        from_attributes = True


@router.post("", response_model=RemitoResponse)
async def create_remito(
    payload: RemitoCreate,
    db: Session = Depends(get_db)
):
    """Create a new remito."""
    remito = Remito(
        pedido_id=payload.pedido_id,
        numero=payload.numero,
        fecha=date.fromisoformat(payload.fecha),
        descripcion=payload.descripcion
    )
    
    db.add(remito)
    db.commit()
    db.refresh(remito)
    
    return RemitoResponse(
        id=remito.id,
        pedido_id=remito.pedido_id,
        numero=remito.numero,
        fecha=remito.fecha.isoformat(),
        descripcion=remito.descripcion
    )
