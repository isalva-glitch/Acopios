"""Pedidos router."""
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from decimal import Decimal

from database import get_db
from models import Pedido
from storage import save_file
from extraction import extract_standard_budget_pdf
from services import pedido_service, imputacion_service
from integrations.spf import services as spf_services
from integrations.spf.database import get_spf_db
from models import Pedido, Acopio
from models.pedido import EstadoPedido
from datetime import date

router = APIRouter()


class PedidoConfirmSpf(BaseModel):
    """Confirmation payload for SPF imputation."""
    nro_pedido: str
    acopio_id: Optional[int] = None


# Pydantic models
class PedidoPreview(BaseModel):
    """Preview of extraction before confirmation."""
    extraction_package: dict
    warnings: List[dict]
    
    class Config:
        from_attributes = True


class PedidoConfirm(BaseModel):
    """Confirmation payload."""
    extraction_package: dict
    obra_id: int


class PedidoResponse(BaseModel):
    """Pedido response."""
    id: int
    numero: str
    obra_id: int
    fecha: str
    estado: str
    total_m2: float
    total_ml: float
    total_pesos: float
    
    class Config:
        from_attributes = True


@router.post("/upload-pdf", response_model=PedidoPreview)
async def upload_pdf(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload PDF and extract pedido data.
    
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
    
    return PedidoPreview(
        extraction_package=extraction_package,
        warnings=extraction_package.get("warnings", [])
    )


@router.post("/confirm", response_model=PedidoResponse)
async def confirm_pedido(
    payload: PedidoConfirm,
    db: Session = Depends(get_db)
):
    """
    Confirm and create pedido from extraction package.
    """
    try:
        pedido = pedido_service.create_from_extraction(
            db,
            payload.extraction_package,
            payload.obra_id
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create pedido: {str(e)}"
        )
    
    return PedidoResponse(
        id=pedido.id,
        numero=pedido.numero,
        obra_id=pedido.obra_id,
        fecha=pedido.fecha.isoformat() if pedido.fecha else "",
        estado=pedido.estado.value if hasattr(pedido.estado, 'value') else str(pedido.estado),
        total_m2=pedido.total_m2 or Decimal('0'),
        total_ml=pedido.total_ml or Decimal('0'),
        total_pesos=pedido.total_pesos or Decimal('0')
    )


@router.get("", response_model=List[PedidoResponse])
async def list_pedidos(
    obra_id: Optional[int] = None,
    estado: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List pedidos with optional filters."""
    query = db.query(Pedido)
    
    if obra_id:
        query = query.filter(Pedido.obra_id == obra_id)
    
    if estado:
        query = query.filter(Pedido.estado == estado)
    
    pedidos = query.all()
    
    return [
        PedidoResponse(
            id=p.id,
            numero=p.numero,
            obra_id=p.obra_id,
            fecha=p.fecha.isoformat() if p.fecha else "",
            estado=p.estado.value if hasattr(p.estado, 'value') else str(p.estado),
            total_m2=p.total_m2 or Decimal('0'),
            total_ml=p.total_ml or Decimal('0'),
            total_pesos=p.total_pesos or Decimal('0')
        )
        for p in pedidos
    ]


@router.get("/{pedido_id}")
async def get_pedido_detail(
    pedido_id: int,
    db: Session = Depends(get_db)
):
    """Get detailed pedido information."""
    pedido = db.query(Pedido).filter(Pedido.id == pedido_id).first()
    
    if not pedido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pedido not found"
        )
    
    return {
        "id": pedido.id,
        "numero": pedido.numero,
        "obra": {
            "id": pedido.obra.id,
            "nombre": pedido.obra.nombre
        },
        "fecha": pedido.fecha.isoformat() if pedido.fecha else None,
        "estado": pedido.estado.value if hasattr(pedido.estado, 'value') else str(pedido.estado),
        "totals": {
            "m2": float(pedido.total_m2 or 0),
            "ml": float(pedido.total_ml or 0),
            "pesos": float(pedido.total_pesos or 0)
        },
        "remitos": [
            {
                "id": r.id,
                "numero": r.numero,
                "fecha": r.fecha.isoformat() if r.fecha else None
            }
            for r in pedido.remitos
        ],
        "imputaciones": [
            {
                "id": imp.id,
                "acopio_id": imp.acopio_id,
                "cantidad_m2": float(imp.cantidad_m2 or 0),
                "cantidad_ml": float(imp.cantidad_ml or 0),
                "cantidad_pesos": float(imp.cantidad_pesos or 0),
                "es_excedente": imp.es_excedente or False
            }
            for imp in pedido.imputaciones
        ]
    }


@router.post("/from-spf", response_model=PedidoResponse)
async def create_pedido_from_spf(
    payload: PedidoConfirmSpf,
    db: Session = Depends(get_db),
    spf_db: Session = Depends(get_spf_db)
):
    """
    Crea un pedido local y una imputación automática a partir de un pedido de SPF.
    """
    # 1. Fetch SPF order info
    spf_pedido = spf_services.get_pedido_for_imputation(spf_db, payload.nro_pedido)
    if not spf_pedido:
        raise HTTPException(status_code=404, detail="Pedido no encontrado en SPF")
    
    # 2. Find local Acopio (Budget holder)
    acopio = None
    if payload.acopio_id:
        acopio = db.query(Acopio).filter(Acopio.id == payload.acopio_id).first()
        if not acopio:
            raise HTTPException(status_code=404, detail="Acopio objetivo no encontrado")
    else:
        if not spf_pedido["v_presupuesto_id"]:
            raise HTTPException(status_code=400, detail="El pedido no está vinculado a un presupuesto en SPF y no se especificó un acopio objetivo.")
            
        acopio = db.query(Acopio).filter(Acopio.v_presupuesto_id == spf_pedido["v_presupuesto_id"]).first()
        if not acopio:
            raise HTTPException(
                status_code=404, 
                detail=f"No se encontró un acopio local (presupuesto {spf_pedido['v_presupuesto_id']}) para este pedido. Debe especificar el acopio manualmente."
            )
        
    # 3. Find or Create local Pedido (Execution Record)
    # We use SPF ID or nro_pedido as unique reference to avoid double imputation
    ref_numero = spf_pedido["nro_pedido"] or spf_pedido["nrooc"] or str(spf_pedido["id"])
    local_pedido = db.query(Pedido).filter(Pedido.numero == ref_numero).first()
    
    if local_pedido:
        # Check if already imputed to THIS acopio
        from models import Imputacion
        existing_imp = db.query(Imputacion).filter(
            Imputacion.pedido_id == local_pedido.id,
            Imputacion.acopio_id == acopio.id
        ).first()
        if existing_imp:
             raise HTTPException(status_code=400, detail=f"Este pedido ({ref_numero}) ya ha sido imputado al acopio #{acopio.numero}.")
    else:
        # Create new local Pedido record
        local_pedido = Pedido(
            numero=ref_numero,
            obra_id=acopio.obra_id,
            fecha=date.today(),
            estado=EstadoPedido.CONFIRMADO, 
            total_m2=spf_pedido["totals"]["m2"],
            total_ml=spf_pedido["totals"]["ml"],
            total_pesos=spf_pedido["totals"]["pesos"]
        )
        db.add(local_pedido)
        db.commit()
        db.refresh(local_pedido)
        
    # 4. Create Imputation (The Actual Consumption)
    try:
        imputacion, warning = imputacion_service.imputar_consumo(
            db,
            pedido_id=local_pedido.id,
            acopio_id=acopio.id,
            acopio_item_id=None, # Overall acopio imputation
            cantidad_m2=Decimal(str(spf_pedido["totals"]["m2"])),
            cantidad_ml=Decimal(str(spf_pedido["totals"]["ml"])),
            cantidad_pesos=Decimal(str(spf_pedido["totals"]["pesos"])),
            cantidad_unidades=spf_pedido["totals"]["unidades"]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error al realizar la imputación: " + str(e))
        
    return PedidoResponse(
        id=local_pedido.id,
        numero=local_pedido.numero,
        obra_id=local_pedido.obra_id or 0,
        fecha=local_pedido.fecha.isoformat() if local_pedido.fecha else "",
        estado=local_pedido.estado.value if hasattr(local_pedido.estado, 'value') else str(local_pedido.estado),
        total_m2=local_pedido.total_m2 or Decimal('0'),
        total_ml=local_pedido.total_ml or Decimal('0'),
        total_pesos=local_pedido.total_pesos or Decimal('0')
    )
