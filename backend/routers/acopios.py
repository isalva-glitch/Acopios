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
from integrations.pdf import extract_budget_pdf, parsed_budget_to_dict
from services import acopio_service
from integrations.spf import services as spf_services
from integrations.spf.database import get_spf_db

router = APIRouter()


# Pydantic models
class AcopioPreview(BaseModel):
    """Preview of extraction before confirmation."""
    extraction_package: dict
    warnings: List[str]
    
    class Config:
        from_attributes = True


class AcopioConfirmSpf(BaseModel):
    """Confirmation payload for SPF."""
    v_presupuesto_id: str


class AcopioConfirm(BaseModel):
    """Confirmation payload."""
    extraction_package: dict


class AcopioTotals(BaseModel):
    cantidad: int
    m2: float
    ml: float
    importe: float

class AcopioCreationResult(BaseModel):
    success: bool
    source: str
    acopio_id: int
    presupuesto_id: Optional[int] = None
    numero_presupuesto: Optional[str] = None
    cliente: Optional[str] = None
    totals: AcopioTotals
    items_count: int
    panos_count: int
    warnings: List[str] = []

    class Config:
        from_attributes = True


class AcopioResponse(BaseModel):
    """Acopio response for list and other general views."""
    id: int
    numero: Optional[str] = None
    obra_id: Optional[int] = None
    fecha_alta: str
    estado: str
    total_m2: float
    total_ml: float
    total_pesos: float
    total_unidades: int
    saldo_m2: float
    saldo_ml: float
    saldo_pesos: float
    saldo_unidades: int
    cliente: Optional[str] = None
    
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
    
    # Extract data using the new specialized Fontela extractor
    try:
        budget = extract_budget_pdf(str(file_path))
        extraction_package = parsed_budget_to_dict(budget)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )
    
    return AcopioPreview(
        extraction_package=extraction_package,
        warnings=extraction_package.get("warnings", [])
    )


@router.post("/confirm-pdf", response_model=AcopioCreationResult)
async def confirm_acopio_pdf(
    payload: AcopioConfirm,
    db: Session = Depends(get_db)
):
    """
    Confirm and create acopio from the new PDF extraction package.
    """
    try:
        # Check for duplicates
        budget_no = payload.extraction_package.get("presupuesto", {}).get("numero")
        if budget_no:
            existing = db.query(Acopio).filter(Acopio.numero == budget_no).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ya existe un acopio para el presupuesto {budget_no}"
                )

        acopio = acopio_service.create_from_pdf(db, payload.extraction_package)
        
        # Calculate pano count (sum of quantities, not sum of rows)
        panos_count = sum(p.cantidad for item in acopio.items for p in item.panos)
        
        return AcopioCreationResult(
            success=True,
            source="pdf",
            acopio_id=acopio.id,
            presupuesto_id=acopio.presupuestos[0].id if acopio.presupuestos else None,
            numero_presupuesto=acopio.numero,
            cliente=acopio.obra.cliente.nombre if acopio.obra and acopio.obra.cliente else "Desconocido",
            totals=AcopioTotals(
                cantidad=acopio.total_unidades,
                m2=acopio.total_m2,
                ml=acopio.total_ml,
                importe=acopio.total_pesos
            ),
            items_count=len(acopio.items),
            panos_count=panos_count,
            warnings=[] # Warnings could be passed from the payload if needed
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create acopio from PDF: {str(e)}"
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
        fecha_alta=acopio.fecha_alta.isoformat() if acopio.fecha_alta else "",
        estado=acopio.estado.value if hasattr(acopio.estado, 'value') else str(acopio.estado),
        total_m2=acopio.total_m2 or Decimal('0'),
        total_ml=acopio.total_ml or Decimal('0'),
        total_pesos=acopio.total_pesos or Decimal('0'),
        total_unidades=acopio.total_unidades or 0,
        saldo_m2=acopio.saldo_m2 or Decimal('0'),
        saldo_ml=acopio.saldo_ml or Decimal('0'),
        saldo_pesos=acopio.saldo_pesos or Decimal('0'),
        saldo_unidades=acopio.saldo_unidades or 0
    )


@router.post("/from-spf", response_model=AcopioCreationResult)
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
            
        # Check for duplicates
        existing = db.query(Acopio).filter(
            (Acopio.v_presupuesto_id == payload.v_presupuesto_id) | 
            (Acopio.numero == payload.v_presupuesto_id)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un acopio para el presupuesto {payload.v_presupuesto_id}"
            )

        acopio = acopio_service.create_from_spf(db, details)

        # Calculate pano count
        panos_count = sum(p.cantidad for item in acopio.items for p in item.panos)
        
        return AcopioCreationResult(
            success=True,
            source="spf",
            acopio_id=acopio.id,
            presupuesto_id=acopio.presupuestos[0].id if acopio.presupuestos else None,
            numero_presupuesto=acopio.numero,
            cliente=acopio.obra.cliente.nombre if acopio.obra and acopio.obra.cliente else "Desconocido",
            totals=AcopioTotals(
                cantidad=acopio.total_unidades,
                m2=acopio.total_m2,
                ml=acopio.total_ml,
                importe=acopio.total_pesos
            ),
            items_count=len(acopio.items),
            panos_count=panos_count,
            warnings=[]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create acopio from SPF: {str(e)}"
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
            fecha_alta=a.fecha_alta.isoformat() if a.fecha_alta else "",
            estado=a.estado.value if hasattr(a.estado, 'value') else str(a.estado),
            total_m2=a.total_m2 or Decimal('0'),
            total_ml=a.total_ml or Decimal('0'),
            total_pesos=a.total_pesos or Decimal('0'),
            total_unidades=a.total_unidades or 0,
            saldo_m2=a.saldo_m2 or Decimal('0'),
            saldo_ml=a.saldo_ml or Decimal('0'),
            saldo_pesos=a.saldo_pesos or Decimal('0'),
            saldo_unidades=a.saldo_unidades or 0,
            cliente=(a.obra.cliente.nombre if a.obra and a.obra.cliente else None)
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
                "id": acopio.obra.cliente.id if acopio.obra.cliente else None,
                "nombre": acopio.obra.cliente.nombre if acopio.obra.cliente else "Desconocido"
            }
        } if acopio.obra else None,
        "cliente_id": acopio.cliente_id,
        "origen_datos": acopio.origen_datos,
        "v_presupuesto_id": acopio.v_presupuesto_id,
        "fecha_alta": acopio.fecha_alta.isoformat() if acopio.fecha_alta else None,
        "estado": acopio.estado.value if hasattr(acopio.estado, 'value') else str(acopio.estado),
        "totals": {
            "m2": float(acopio.total_m2 or 0),
            "ml": float(acopio.total_ml or 0),
            "pesos": float(acopio.total_pesos or 0),
            "unidades": acopio.total_unidades or 0
        },
        "saldos": {
            "m2": float(acopio.saldo_m2 or 0),
            "ml": float(acopio.saldo_ml or 0),
            "pesos": float(acopio.saldo_pesos or 0),
            "unidades": acopio.saldo_unidades or 0
        },
        "presupuestos": [
            {
                "id": p.id,
                "numero": p.numero,
                "fecha": p.fecha.isoformat() if p.fecha else None
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
                    "m2": float(item.total_m2 or 0),
                    "ml": float(item.total_ml or 0),
                    "pesos": float(item.total_pesos or 0),
                    "unidades": item.cantidad or 0
                },
                "saldos": {
                    "m2": float(item.saldo_m2 or 0),
                    "ml": float(item.saldo_ml or 0),
                    "pesos": float(item.saldo_pesos or 0),
                    "unidades": item.saldo_cantidad or 0
                },
                "panos": [
                    {
                        "id": pano.id,
                        "cantidad": pano.cantidad or 1,
                        "ancho": float(pano.ancho or 0),
                        "alto": float(pano.alto or 0),
                        "superficie_m2": float(pano.superficie_m2 or 0),
                        "perimetro_ml": float(pano.perimetro_ml or 0)
                    }
                    for pano in item.panos
                ],
                "adicionales": [
                    {
                        "id": adc.id,
                        "cantidad": adc.cantidad or 1,
                        "descripcion": adc.descripcion,
                        "precio_unitario": float(adc.precio_unitario or 0),
                        "precio_total": float(adc.precio_total or 0),
                        "tipo": adc.tipo,
                        "origen": adc.origen
                    }
                    for adc in item.adicionales
                ]
            }
            for item in acopio.items
        ],
        "imputaciones": [
            {
                "id": imp.id,
                "pedido_id": imp.pedido_id,
                "pedido_numero": imp.pedido.numero if imp.pedido else None,
                "cantidad_m2": float(imp.cantidad_m2 or 0),
                "cantidad_ml": float(imp.cantidad_ml or 0),
                "cantidad_pesos": float(imp.cantidad_pesos or 0),
                "cantidad_unidades": imp.cantidad_unidades or 0,
                "es_excedente": imp.es_excedente or False
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


@router.get("/{acopio_id}/avance-comercial")
async def get_acopio_avance_comercial(
    acopio_id: int,
    db: Session = Depends(get_db),
    spf_db: Session = Depends(get_spf_db)
):
    """
    Obtiene el avance comercial (facturación/remitos) para un acopio local 
    consultando en tiempo real a la base SPF.
    """
    acopio = db.query(Acopio).filter(Acopio.id == acopio_id).first()
    if not acopio:
        raise HTTPException(status_code=404, detail="Acopio no encontrado")
    
    if not acopio.v_presupuesto_id:
        raise HTTPException(status_code=400, detail="Este acopio no está vinculado a un presupuesto SPF")
        
    try:
        avance = spf_services.get_avance_comercial_acopio(spf_db, acopio.v_presupuesto_id)
        return avance
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
