"""Precio de Referencia model."""
from sqlalchemy import Column, ForeignKey, Numeric, Integer
from sqlalchemy.orm import relationship
from models.base import BaseModel


class PrecioReferencia(BaseModel):
    """Precio de Referencia entity."""
    
    __tablename__ = "precios_referencia"
    
    vidrio_exterior = Column(Numeric(15, 2), nullable=False, default=0)
    vidrio_interior = Column(Numeric(15, 2), nullable=False, default=0)
    camara_estructural = Column(Numeric(15, 2), nullable=False, default=0)
    pulido = Column(Numeric(15, 2), nullable=False, default=0)
    fason_templado_exterior = Column(Numeric(15, 2), nullable=False, default=0)
    pegado_bastidor = Column(Numeric(15, 2), nullable=False, default=0)
    camara_normal = Column(Numeric(15, 2), nullable=False, default=0)
    opacificado_perimetral = Column(Numeric(15, 2), nullable=False, default=0)
    opacificado_total = Column(Numeric(15, 2), nullable=False, default=0)
    camara_offset = Column(Numeric(15, 2), nullable=False, default=0)
    
    # Foreign key
    acopio_id = Column(Integer, ForeignKey("acopios.id"), unique=True, nullable=False)
    
    # Relationships
    acopio = relationship("Acopio", back_populates="precios_referencia")
