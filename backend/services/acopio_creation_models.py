from typing import List, Optional
from pydantic import BaseModel
from decimal import Decimal
from datetime import date


class NormalizedPano(BaseModel):
    """Pano data normalized across SPF and PDF sources."""
    cantidad: int
    ancho_mm: int
    alto_mm: int
    superficie_m2: Decimal
    perimetro_ml: Decimal
    denominacion: Optional[str] = None
    precio_unitario: Optional[Decimal] = None
    precio_total: Optional[Decimal] = None


class NormalizedAdicional(BaseModel):
    """Adicional/Complemento data normalized across SPF and PDF sources."""
    cantidad: int
    descripcion: str
    precio_unitario: Optional[Decimal] = None
    precio_total: Optional[Decimal] = None
    tipo: str = "adicional"


class NormalizedItem(BaseModel):
    """Item data normalized across SPF and PDF sources."""
    numero_item: Optional[int] = None
    descripcion: str
    material: Optional[str] = ""
    tipologia: Optional[str] = ""
    cantidad: int
    total_m2: Decimal
    total_ml: Decimal
    total_pesos: Decimal
    panos: List[NormalizedPano]
    adicionales: List[NormalizedAdicional] = []


class NormalizedPresupuesto(BaseModel):
    """Presupuesto data normalized across SPF and PDF sources."""
    numero: str
    fecha: Optional[date] = None
    empresa: Optional[str] = None
    contacto: Optional[str] = None
    cotizado_por: Optional[str] = None
    peso_estimado_kg: Optional[Decimal] = None
    estado: Optional[str] = None
    condiciones: Optional[str] = None


class NormalizedAcopioData(BaseModel):
    """Full Acopio data normalized from any source."""
    numero: str                  # Budget ID or Ref
    cliente_nombre: str
    obra_nombre: Optional[str] = None
    total_m2: Decimal
    total_ml: Decimal
    total_pesos: Decimal
    total_unidades: int
    origen_datos: str             # 'spf_production' | 'pdf_upload'
    v_presupuesto_id: Optional[str] = None
    cliente_id_spf: Optional[int] = None
    presupuestos: List[NormalizedPresupuesto]
    items: List[NormalizedItem]
    warnings: List[str] = []
    metadata: dict = {}
