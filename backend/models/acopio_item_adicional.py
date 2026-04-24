"""AcopioItemAdicional model."""
from sqlalchemy import Column, String, Integer, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from models.base import BaseModel


class AcopioItemAdicional(BaseModel):
    """Acopio Item Adicional entity for complements, services, freight, etc."""
    
    __tablename__ = "acopio_item_adicionales"
    
    descripcion = Column(String(500), nullable=False)
    cantidad = Column(Integer, nullable=False, default=1)
    precio_unitario = Column(Numeric(15, 2), nullable=True)
    precio_total = Column(Numeric(15, 2), nullable=True)
    tipo = Column(String(50), nullable=True, default="adicional")
    origen = Column(String(50), nullable=True, default="pdf")
    
    # Foreign keys
    item_id = Column(Integer, ForeignKey("acopio_items.id"), nullable=False)
    
    # Relationships
    item = relationship("AcopioItem", back_populates="adicionales")
