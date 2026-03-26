"""Router for SPF integrations."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import List

from integrations.spf import services
from integrations.spf.database import get_spf_db
from database import get_db
from models import Acopio


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


@router.get("/pedidos/{nro_pedido}/imputation-preview")
async def get_pedido_imputation_preview(
    nro_pedido: str,
    db: Session = Depends(get_db),
    spf_db: Session = Depends(get_spf_db)
):
    """
    Busca un pedido en SPF y previsualiza la imputación contra el acopio local correspondiente.
    """
    spf_pedido = services.get_pedido_for_imputation(spf_db, nro_pedido)
    if not spf_pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado en SPF")
    
    if not spf_pedido["v_presupuesto_id"]:
        raise HTTPException(status_code=400, detail="El pedido no tiene un presupuesto (v_presupuesto_id) asociado")
        
    # Find local acopio
    acopio = db.query(Acopio).filter(Acopio.v_presupuesto_id == spf_pedido["v_presupuesto_id"]).first()
    
    return {
        "spf_pedido": spf_pedido,
        "acopio_local": {
            "id": acopio.id,
            "numero": acopio.numero,
            "saldo_m2": float(acopio.saldo_m2),
            "saldo_ml": float(acopio.saldo_ml),
            "saldo_pesos": float(acopio.saldo_pesos),
            "saldo_unidades": acopio.saldo_unidades
        } if acopio else None
    }
