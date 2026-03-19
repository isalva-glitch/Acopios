"""Router for SPF integrations."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List

from integrations.spf import services
from integrations.spf.database import get_spf_db


router = APIRouter()


@router.get("/presupuestos/search", response_model=List[str])
async def search_presupuestos(
    q: str = Query(..., min_length=1, description="v_presupuesto_id o nro_pedido a buscar"),
    db: Session = Depends(get_spf_db)
):
    """
    Busca presupuestos en la base externa SPF por ID o número de pedido.
    """
    try:
        results = services.search_presupuestos(db, q)
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presupuestos/{v_presupuesto_id}")
async def get_presupuesto_details(
    v_presupuesto_id: str,
    db: Session = Depends(get_spf_db)
):
    """
    Obtiene los detalles agregados (totales de m2, ml, pesos) de un presupuesto.
    """
    try:
        details = services.get_presupuesto_details(db, v_presupuesto_id)
        if not details:
            raise HTTPException(status_code=404, detail="Presupuesto no encontrado en SPF")
        return details
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/presupuestos/{v_presupuesto_id}/avance-comercial")
async def get_avance_comercial(
    v_presupuesto_id: str,
    db: Session = Depends(get_spf_db)
):
    """
    Obtiene el detalle de avance de facturación y remitos de un presupuesto desde SPF.
    """
    try:
        avance = services.get_avance_comercial_acopio(db, v_presupuesto_id)
        if not avance:
            raise HTTPException(status_code=404, detail="No se encontró información comercial para este presupuesto")
        return avance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
