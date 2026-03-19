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
from services import pedido_service

router = APIRouter()


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
    total_m2: Decimal
    total_ml: Decimal
    total_pesos: Decimal
    
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
        fecha=pedido.fecha.isoformat(),
        estado=pedido.estado.value,
        total_m2=pedido.total_m2,
        total_ml=pedido.total_ml,
        total_pesos=pedido.total_pesos
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
            fecha=p.fecha.isoformat(),
            estado=p.estado.value,
            total_m2=p.total_m2,
            total_ml=p.total_ml,
            total_pesos=p.total_pesos
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
        "fecha": pedido.fecha.isoformat(),
        "estado": pedido.estado.value,
        "totals": {
            "m2": float(pedido.total_m2),
            "ml": float(pedido.total_ml),
            "pesos": float(pedido.total_pesos)
        },
        "remitos": [
            {
                "id": r.id,
                "numero": r.numero,
                "fecha": r.fecha.isoformat()
            }
            for r in pedido.remitos
        ],
        "imputaciones": [
            {
                "id": imp.id,
                "acopio_id": imp.acopio_id,
                "cantidad_m2": float(imp.cantidad_m2),
                "cantidad_ml": float(imp.cantidad_ml),
                "cantidad_pesos": float(imp.cantidad_pesos),
                "es_excedente": imp.es_excedente
            }
            for imp in pedido.imputaciones
        ]
    }
