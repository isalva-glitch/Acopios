"""Remito model."""
from sqlalchemy import Column, String, Integer, ForeignKey, Date, Text
from sqlalchemy.orm import relationship
from models.base import BaseModel


class Remito(BaseModel):
    """Remito entity."""
    
    __tablename__ = "remitos"
    
    numero = Column(String(100), nullable=False)
    fecha = Column(Date, nullable=False)
    descripcion = Column(Text, nullable=True)
    
    # Foreign keys
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    
    # Relationships
    pedido = relationship("Pedido", back_populates="remitos")
