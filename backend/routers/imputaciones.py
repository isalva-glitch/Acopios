"""Imputaciones router."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from decimal import Decimal
from typing import Optional

from database import get_db
from services import imputacion_service

router = APIRouter()


# Pydantic models
class ImputacionCreate(BaseModel):
    """Create imputacion payload."""
    pedido_id: int
    acopio_id: int
    acopio_item_id: Optional[int] = None
    cantidad_m2: Decimal
    cantidad_ml: Decimal
    cantidad_pesos: Decimal


class ImputacionResponse(BaseModel):
    """Imputacion response."""
    id: int
    pedido_id: int
    acopio_id: int
    acopio_item_id: Optional[int]
    cantidad_m2: Decimal
    cantidad_ml: Decimal
    cantidad_pesos: Decimal
    cantidad_unidades: int
    es_excedente: bool
    warning: Optional[str] = None
    
    class Config:
        from_attributes = True


@router.post("", response_model=ImputacionResponse)
async def create_imputacion(
    payload: ImputacionCreate,
    db: Session = Depends(get_db)
):
    """
    Create imputacion (consume acopio against pedido).
    
    Applies excedente policy (BLOCK, WARN, ALLOW).
    """
    try:
        imputacion, warning = imputacion_service.imputar_consumo(
            db=db,
            pedido_id=payload.pedido_id,
            acopio_id=payload.acopio_id,
            acopio_item_id=payload.acopio_item_id,
            cantidad_m2=payload.cantidad_m2,
            cantidad_ml=payload.cantidad_ml,
            cantidad_pesos=payload.cantidad_pesos,
            cantidad_unidades=payload.cantidad_unidades
        )
    except ValueError as e:
        # BLOCK policy raised exception
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create imputacion: {str(e)}"
        )
    
    return ImputacionResponse(
        id=imputacion.id,
        pedido_id=imputacion.pedido_id,
        acopio_id=imputacion.acopio_id,
        acopio_item_id=imputacion.acopio_item_id,
        cantidad_m2=imputacion.cantidad_m2,
        cantidad_ml=imputacion.cantidad_ml,
        cantidad_pesos=imputacion.cantidad_pesos,
        cantidad_unidades=imputacion.cantidad_unidades,
        es_excedente=imputacion.es_excedente,
        warning=warning
    )


@router.delete("/{imputacion_id}")
async def anular_imputacion(
    imputacion_id: int,
    db: Session = Depends(get_db)
):
    """
    Anula (elimina) una imputación y recalcula los saldos del acopio afectado.
    """
    try:
        result = imputacion_service.anular_imputacion(db, imputacion_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al anular imputación: {str(e)}"
        )

    return {
        "success": True,
        "message": f"Imputación {imputacion_id} anulada correctamente.",
        "acopio_id": result["acopio_id"]
    }
