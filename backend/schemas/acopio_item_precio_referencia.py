"""Schemas for item-scoped reference prices."""
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


UnidadPrecioReferencia = Literal["m2", "ml", "unidad"]
OrigenPrecioReferencia = Literal["autodetectado", "manual", "migrado"]
EstadoPreciosReferencia = Literal["completo", "incompleto", "sin_conceptos", "revisar"]


class ConceptoPrecioReferenciaInput(BaseModel):
    """Editable reference price for a process concept."""

    concepto: str
    unidad: Optional[UnidadPrecioReferencia] = None
    precio_base: Optional[Decimal] = None
    precio_actual: Optional[Decimal] = None
    habilitado: bool = True
    confirmar_cero: bool = False


class ItemPreciosReferenciaInput(BaseModel):
    """Batch update payload for one acopio item."""

    item_id: int
    conceptos: list[ConceptoPrecioReferenciaInput]


class ItemPreciosReferenciaPatch(BaseModel):
    """Patch payload for one acopio item."""

    conceptos: list[ConceptoPrecioReferenciaInput]


class ItemsPreciosReferenciaUpdate(BaseModel):
    """Batch update payload for all item reference prices in an acopio."""

    items: list[ItemPreciosReferenciaInput]


class ConceptoPrecioReferenciaResponse(BaseModel):
    """Reference price returned to the frontend."""

    concepto: str
    unidad: UnidadPrecioReferencia
    habilitado: bool
    precio_base: Optional[Decimal] = None
    precio_actual: Optional[Decimal] = None
    origen: OrigenPrecioReferencia

    model_config = ConfigDict(from_attributes=True)


class ItemPreciosReferenciaResponse(BaseModel):
    """Reference-price matrix row for one item."""

    item_id: int
    numero_item: str
    descripcion: str
    cantidad: int
    total_m2: Decimal
    total_ml: Decimal
    total_pesos: Decimal
    conceptos: list[ConceptoPrecioReferenciaResponse]
    estado_precios_referencia: EstadoPreciosReferencia


class AcopioItemsPreciosReferenciaResponse(BaseModel):
    """Full reference-price matrix for an acopio."""

    acopio_id: int
    items: list[ItemPreciosReferenciaResponse]
