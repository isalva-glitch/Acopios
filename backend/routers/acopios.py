"""Acopios router."""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from decimal import Decimal

from database import get_db
from models import Acopio
from storage import save_file
from extraction import extract_standard_budget_pdf
from services import acopio_service
from integrations.spf import services as spf_services
from integrations.spf.database import get_spf_db

router = APIRouter()


# Pydantic models
class AcopioPreview(BaseModel):
    """Preview of extraction before confirmation."""
    extraction_package: dict
    warnings: List[dict]
    
    class Config:
        from_attributes = True


class AcopioConfirmSpf(BaseModel):
    """Confirmation payload for SPF."""
    v_presupuesto_id: str


class AcopioConfirm(BaseModel):
    """Confirmation payload."""
    extraction_package: dict


class AcopioResponse(BaseModel):
    """Acopio response."""
    id: int
    numero: str
    obra_id: Optional[int]
    fecha_alta: str
    estado: str
    total_m2: Decimal
    total_ml: Decimal
    total_pesos: Decimal
    total_unidades: int
    saldo_m2: Decimal
    saldo_ml: Decimal
    saldo_pesos: Decimal
    saldo_unidades: int
    
    class Config:
        from_attributes = True


@router.post("/upload-pdf", response_model=AcopioPreview)
async def upload_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload PDF and extract data.
    
    Returns preview with warnings for user confirmation.
    """
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed"
        )
    
    # Save file
    file_hash, file_path = await save_file(file)
    
    # Extract data
    try:
        extraction_package = extract_standard_budget_pdf(str(file_path))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )
    
    return AcopioPreview(
        extraction_package=extraction_package,
        warnings=extraction_package.get("warnings", [])
    )


@router.post("/confirm", response_model=AcopioResponse)
async def confirm_acopio(
    payload: AcopioConfirm,
    db: Session = Depends(get_db)
):
    """
    Confirm and create acopio from extraction package.
    """
    try:
        acopio = acopio_service.create_from_extraction(db, payload.extraction_package)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create acopio: {str(e)}"
        )
    
    return AcopioResponse(
        id=acopio.id,
        numero=acopio.numero,
        obra_id=acopio.obra_id,
        fecha_alta=acopio.fecha_alta.isoformat(),
        estado=acopio.estado.value,
        total_m2=acopio.total_m2,
        total_ml=acopio.total_ml,
        total_pesos=acopio.total_pesos,
        total_unidades=acopio.total_unidades,
        saldo_m2=acopio.saldo_m2,
        saldo_ml=acopio.saldo_ml,
        saldo_pesos=acopio.saldo_pesos,
        saldo_unidades=acopio.saldo_unidades
    )


@router.post("/from-spf", response_model=AcopioResponse)
async def create_acopio_from_spf(
    payload: AcopioConfirmSpf,
    db: Session = Depends(get_db),
    spf_db: Session = Depends(get_spf_db)
):
    """
    Create an acopio directly from the SPF database.
    """
    try:
        details = spf_services.get_presupuesto_details(spf_db, payload.v_presupuesto_id)
        if not details:
            raise HTTPException(status_code=404, detail="Presupuesto no encontrado en SPF")
            
        acopio = acopio_service.create_from_spf(db, details)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create acopio from SPF: {str(e)}"
        )
        
    return AcopioResponse(
        id=acopio.id,
        numero=acopio.numero or "",
        obra_id=acopio.obra_id,
        fecha_alta=acopio.fecha_alta.isoformat(),
        estado=acopio.estado.value,
        total_m2=acopio.total_m2,
        total_ml=acopio.total_ml,
        total_pesos=acopio.total_pesos,
        total_unidades=acopio.total_unidades,
        saldo_m2=acopio.saldo_m2,
        saldo_ml=acopio.saldo_ml,
        saldo_pesos=acopio.saldo_pesos,
        saldo_unidades=acopio.saldo_unidades
    )


@router.get("", response_model=List[AcopioResponse])
async def list_acopios(
    obra_id: Optional[int] = None,
    estado: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List acopios with optional filters."""
    query = db.query(Acopio)
    
    if obra_id:
        query = query.filter(Acopio.obra_id == obra_id)
    
    if estado:
        query = query.filter(Acopio.estado == estado)
    
    acopios = query.all()
    
    return [
        AcopioResponse(
            id=a.id,
            numero=a.numero,
            obra_id=a.obra_id,
            fecha_alta=a.fecha_alta.isoformat(),
            estado=a.estado.value,
            total_m2=a.total_m2,
            total_ml=a.total_ml,
            total_pesos=a.total_pesos,
            total_unidades=a.total_unidades,
            saldo_m2=a.saldo_m2,
            saldo_ml=a.saldo_ml,
            saldo_pesos=a.saldo_pesos,
            saldo_unidades=a.saldo_unidades
        )
        for a in acopios
    ]


@router.get("/{acopio_id}")
async def get_acopio_detail(
    acopio_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed acopio information."""
    acopio = db.query(Acopio).filter(Acopio.id == acopio_id).first()
    
    if not acopio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acopio not found"
        )
    
    return {
        "id": acopio.id,
        "numero": acopio.numero,
        "obra": {
            "id": acopio.obra.id,
            "nombre": acopio.obra.nombre,
            "cliente": {
                "id": acopio.obra.cliente.id,
                "nombre": acopio.obra.cliente.nombre
            }
        } if acopio.obra else None,
        "cliente_id": acopio.cliente_id,
        "origen_datos": acopio.origen_datos,
        "v_presupuesto_id": acopio.v_presupuesto_id,
        "fecha_alta": acopio.fecha_alta.isoformat(),
        "estado": acopio.estado.value,
        "totals": {
            "m2": float(acopio.total_m2),
            "ml": float(acopio.total_ml),
            "pesos": float(acopio.total_pesos),
            "unidades": acopio.total_unidades
        },
        "saldos": {
            "m2": float(acopio.saldo_m2),
            "ml": float(acopio.saldo_ml),
            "pesos": float(acopio.saldo_pesos),
            "unidades": acopio.saldo_unidades
        },
        "presupuestos": [
            {
                "id": p.id,
                "numero": p.numero,
                "fecha": p.fecha.isoformat()
            }
            for p in acopio.presupuestos
        ],
        "items": [
            {
                "id": item.id,
                "descripcion": item.descripcion,
                "material": item.material,
                "tipologia": item.tipologia,
                "cantidad": item.cantidad,
                "totals": {
                    "m2": float(item.total_m2),
                    "ml": float(item.total_ml),
                    "pesos": float(item.total_pesos),
                    "unidades": item.cantidad
                },
                "saldos": {
                    "m2": float(item.saldo_m2),
                    "ml": float(item.saldo_ml),
                    "pesos": float(item.saldo_pesos),
                    "unidades": item.saldo_cantidad
                },
                "panos": [
                    {
                        "id": pano.id,
                        "cantidad": pano.cantidad,
                        "ancho": float(pano.ancho),
                        "alto": float(pano.alto),
                        "superficie_m2": float(pano.superficie_m2),
                        "perimetro_ml": float(pano.perimetro_ml)
                    }
                    for pano in item.panos
                ]
            }
            for item in acopio.items
        ],
        "imputaciones": [
            {
                "id": imp.id,
                "pedido_id": imp.pedido_id,
                "pedido_numero": imp.pedido.numero if imp.pedido else None,
                "cantidad_m2": float(imp.cantidad_m2),
                "cantidad_ml": float(imp.cantidad_ml),
                "cantidad_pesos": float(imp.cantidad_pesos),
                "cantidad_unidades": imp.cantidad_unidades,
                "es_excedente": imp.es_excedente
            }
            for imp in acopio.imputaciones
        ]
    }


@router.delete("/{acopio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_acopio(
    acopio_id: int,
    db: Session = Depends(get_db)
):
    """Delete an acopio."""
    acopio = db.query(Acopio).filter(Acopio.id == acopio_id).first()
    
    if not acopio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Acopio not found"
        )
    
    db.delete(acopio)
    db.commit()
    return None
