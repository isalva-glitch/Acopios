"""Validated manual document input. All money is ARS, without IVA."""
from datetime import date
from decimal import Decimal
from typing import Literal, Annotated
from pydantic import BaseModel, Field, ConfigDict, field_validator

Money = Decimal


class RepartoInput(BaseModel):
    porcentaje_facturado: Annotated[Decimal, Field(ge=0, le=100, decimal_places=2)] | None = None


class AplicacionInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    comprobante_id: int | None = None
    importe_aplicado: Money = Field(gt=0, max_digits=15, decimal_places=2)
    importe_facturado: Money = Field(ge=0, max_digits=15, decimal_places=2)
    referencia_id: int | None = None


class ComprobanteInput(AplicacionInput):
    tipo: Literal['ORDEN_COMPRA', 'FAC_ANTICIPO', 'FAC_MERCADERIA', 'RECIBO']
    numero: str = Field(min_length=1, max_length=100)
    emisor: str = Field(min_length=1, max_length=200)
    fecha: date
    importe: Money = Field(gt=0, max_digits=15, decimal_places=2)
    iva: Annotated[Decimal, Field(ge=0, max_digits=15, decimal_places=2)] | None = None
    descripcion: str | None = Field(default=None, max_length=2000)

    @field_validator('numero', 'emisor')
    @classmethod
    def clean_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError('El numero y el emisor son obligatorios')
        return value


class EstadoAplicacionInput(BaseModel):
    anulada: bool
