"""Precio de Referencia schemas."""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict


class PrecioReferenciaBase(BaseModel):
    """Base schema for Precio de Referencia."""
    vidrio_exterior: Decimal = Decimal("0.0")
    vidrio_interior: Decimal = Decimal("0.0")
    camara_estructural: Decimal = Decimal("0.0")
    pulido: Decimal = Decimal("0.0")
    fason_templado_exterior: Decimal = Decimal("0.0")
    pegado_bastidor: Decimal = Decimal("0.0")
    camara_normal: Decimal = Decimal("0.0")
    opacificado_perimetral: Decimal = Decimal("0.0")
    opacificado_total: Decimal = Decimal("0.0")
    camara_offset: Decimal = Decimal("0.0")


class PrecioReferenciaCreate(PrecioReferenciaBase):
    """Schema for creating a Precio de Referencia."""
    acopio_id: int


class PrecioReferenciaUpdate(PrecioReferenciaBase):
    """Schema for updating a Precio de Referencia."""
    pass


class PrecioReferenciaResponse(PrecioReferenciaBase):
    """Schema for Precio de Referencia response."""
    id: int
    acopio_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
