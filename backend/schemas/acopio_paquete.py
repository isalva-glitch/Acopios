"""Schemas for acopio packages."""
from datetime import date
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AcopioPaquetePreviewRequest(BaseModel):
    presupuestos: List[str] = Field(..., min_length=1)


class AcopioPaquetePreviewItem(BaseModel):
    presupuesto: str
    cliente: Optional[str] = None
    obra: Optional[str] = None
    importe: float = 0
    m2: float = 0
    ml: float = 0
    unidades: int = 0
    estado_validacion: str
    observaciones: Optional[str] = None
    valido: bool


class AcopioPaquetePreviewResponse(BaseModel):
    presupuestos: List[AcopioPaquetePreviewItem]


class AcopioPaquetePdfPreviewResponse(AcopioPaquetePreviewItem):
    extraction_package: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)


class AcopioPaqueteCreate(BaseModel):
    nombre: str = Field(..., min_length=1)
    cliente: str = Field(..., min_length=1)
    fecha_alta: date
    observaciones: Optional[str] = None
    presupuestos: List[str] = Field(default_factory=list)
    pdf_presupuestos: List[Dict[str, Any]] = Field(default_factory=list)


class AcopioPaqueteUpdate(BaseModel):
    nombre: Optional[str] = None
    cliente: Optional[str] = None
    fecha_alta: Optional[date] = None
    observaciones: Optional[str] = None
    estado: Optional[str] = None


class AcopioPaqueteListItem(BaseModel):
    id: int
    numero: Optional[str] = None
    nombre: str
    cliente: str
    fecha_alta: str
    estado: str
    cantidad_acopios: int
    total_pesos: float
    total_m2: float
    total_ml: float
    total_unidades: int


class AcopioPaqueteAcopio(BaseModel):
    id: int
    numero_acopio: Optional[str] = None
    presupuesto: Optional[str] = None
    obra: Optional[str] = None
    cliente: Optional[str] = None
    estado: str
    total_pesos: float
    saldo_pesos: float
    total_m2: float
    total_ml: float
    total_unidades: int


class AcopioPaqueteDetalle(BaseModel):
    id: int
    numero: Optional[str] = None
    nombre: str
    cliente: str
    fecha_alta: str
    estado: str
    observaciones: Optional[str] = None
    cantidad_acopios: int
    total_pesos: float
    total_m2: float
    total_ml: float
    total_unidades: int
    acopios: List[AcopioPaqueteAcopio]
