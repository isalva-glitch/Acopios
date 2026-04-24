"""AcopioItemPano model."""
from sqlalchemy import Column, String, Integer, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from models.base import BaseModel


class AcopioItemPano(BaseModel):
    """Acopio Item Paño entity."""
    
    __tablename__ = "acopio_item_panos"
    
    cantidad = Column(Integer, nullable=False, default=1)
    ancho = Column(Numeric(10, 2), nullable=False)
    alto = Column(Numeric(10, 2), nullable=False)
    superficie_m2 = Column(Numeric(12, 2), nullable=False)
    perimetro_ml = Column(Numeric(12, 2), nullable=False)
    precio_unitario = Column(Numeric(15, 2), nullable=True)
    precio_total = Column(Numeric(15, 2), nullable=True)
    denominacion = Column(String(50), nullable=True)  # PDF: PV1, PA1, PFA1, etc.
    
    # Foreign keys
    item_id = Column(Integer, ForeignKey("acopio_items.id"), nullable=False)
    
    # Relationships
    item = relationship("AcopioItem", back_populates="panos")
