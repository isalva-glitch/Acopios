"""Acopio package router."""
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session
from typing import List

from database import get_db
from integrations.spf.database import get_spf_db
from integrations.pdf import extract_budget_pdf, parsed_budget_to_dict
from schemas.acopio_paquete import (
    AcopioPaqueteAddPdf,
    AcopioPaqueteCreate,
    AcopioPaqueteDetalle,
    AcopioPaqueteListItem,
    AcopioPaquetePdfPreviewResponse,
    AcopioPaquetePreviewRequest,
    AcopioPaquetePreviewResponse,
    AcopioPaqueteUpdate,
    AcopioPaqueteAddPresupuesto,
)
from services.acopio_paquete_service import AcopioPaqueteService
from storage import save_file


router = APIRouter()


@router.post("/upload-pdf", response_model=AcopioPaquetePdfPreviewResponse)
async def upload_pdf_acopio_paquete(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a budget PDF to use as a package child acopio source."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are allowed",
        )

    _file_hash, file_path = await save_file(file)

    try:
        budget = extract_budget_pdf(str(file_path))
        extraction_package = parsed_budget_to_dict(budget)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}",
        )

    return AcopioPaqueteService.preview_pdf_extraction(db, extraction_package)


@router.post("/preview", response_model=AcopioPaquetePreviewResponse)
async def preview_acopio_paquete(
    payload: AcopioPaquetePreviewRequest,
    db: Session = Depends(get_db),
    spf_db: Session = Depends(get_spf_db),
):
    """Preview SPF budgets before creating a package."""
    return AcopioPaquetePreviewResponse(
        presupuestos=AcopioPaqueteService.preview_presupuestos(
            db,
            spf_db,
            payload.presupuestos,
        )
    )


@router.post("", response_model=AcopioPaqueteDetalle)
async def create_acopio_paquete(
    payload: AcopioPaqueteCreate,
    db: Session = Depends(get_db),
    spf_db: Session = Depends(get_spf_db),
):
    """Create a package and one operational acopio per SPF budget."""
    try:
        return AcopioPaqueteService.create_paquete(db, spf_db, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create acopio package: {str(e)}",
        )


@router.get("", response_model=List[AcopioPaqueteListItem])
async def list_acopio_paquetes(db: Session = Depends(get_db)):
    """List packages with consolidated totals."""
    return AcopioPaqueteService.list_paquetes(db)


@router.get("/{paquete_id}", response_model=AcopioPaqueteDetalle)
async def get_acopio_paquete(paquete_id: int, db: Session = Depends(get_db)):
    """Get package details and child acopios."""
    paquete = AcopioPaqueteService.get_paquete(db, paquete_id)
    if not paquete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paquete no encontrado")
    return paquete


@router.patch("/{paquete_id}", response_model=AcopioPaqueteDetalle)
async def update_acopio_paquete(
    paquete_id: int,
    payload: AcopioPaqueteUpdate,
    db: Session = Depends(get_db),
):
    """Update package-level fields without modifying child acopios."""
    try:
        paquete = AcopioPaqueteService.update_paquete(db, paquete_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update acopio package: {str(e)}",
        )

    if not paquete:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Paquete no encontrado")
    return paquete


@router.post("/{paquete_id}/presupuestos", response_model=AcopioPaqueteDetalle)
async def add_presupuesto_to_paquete(
    paquete_id: int,
    payload: AcopioPaqueteAddPresupuesto,
    db: Session = Depends(get_db),
    spf_db: Session = Depends(get_spf_db),
):
    """Add a new SPF budget to an existing package."""
    try:
        paquete = AcopioPaqueteService.add_presupuesto(db, spf_db, paquete_id, payload.presupuesto)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add presupuesto: {str(e)}",
        )
    return paquete


@router.post("/{paquete_id}/presupuestos-pdf", response_model=AcopioPaqueteDetalle)
async def add_pdf_presupuesto_to_paquete(
    paquete_id: int,
    payload: AcopioPaqueteAddPdf,
    db: Session = Depends(get_db),
):
    """Add a new PDF-based budget to an existing package."""
    try:
        paquete = AcopioPaqueteService.add_presupuesto_pdf(db, paquete_id, payload.extraction_package)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to add PDF presupuesto: {str(e)}",
        )
    return paquete


@router.delete("/{paquete_id}/acopios/{acopio_id}", response_model=AcopioPaqueteDetalle)
async def remove_acopio_from_paquete(
    paquete_id: int,
    acopio_id: int,
    db: Session = Depends(get_db),
):
    """Remove a child acopio from an existing package."""
    try:
        paquete = AcopioPaqueteService.remove_acopio(db, paquete_id, acopio_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to remove acopio: {str(e)}",
        )
    return paquete
