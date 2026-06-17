"""Reference prices by acopio item and process concept."""
from sqlalchemy import Boolean, Column, ForeignKey, Numeric, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from models.base import BaseModel


class AcopioItemPrecioReferencia(BaseModel):
    """Reference price scoped to an acopio item and process concept."""

    __tablename__ = "acopio_item_precios_referencia"
    __table_args__ = (
        UniqueConstraint(
            "acopio_item_id",
            "concepto",
            name="uq_acopio_item_precio_referencia_item_concepto",
        ),
    )

    acopio_id = Column(Integer, ForeignKey("acopios.id"), nullable=False, index=True)
    acopio_item_id = Column(Integer, ForeignKey("acopio_items.id"), nullable=False, index=True)
    concepto = Column(String(80), nullable=False)
    unidad = Column(String(20), nullable=False)
    precio_base = Column(Numeric(15, 2), nullable=True)
    precio_actual = Column(Numeric(15, 2), nullable=True)
    habilitado = Column(Boolean, nullable=False, default=True)
    origen = Column(String(40), nullable=False, default="autodetectado")

    acopio = relationship("Acopio", back_populates="items_precios_referencia")
    item = relationship("AcopioItem", back_populates="precios_referencia")
