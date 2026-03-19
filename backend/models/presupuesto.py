"""Presupuesto model."""
from sqlalchemy import Column, String, Integer, ForeignKey, Date, Text
from sqlalchemy.orm import relationship
from models.base import BaseModel


class Presupuesto(BaseModel):
    """Presupuesto entity."""
    
    __tablename__ = "presupuestos"
    
    numero = Column(String(100), nullable=False)
    fecha = Column(Date, nullable=False)
    condiciones = Column(Text, nullable=True)
    estado = Column(String(50), nullable=True)
    
    # Foreign keys
    acopio_id = Column(Integer, ForeignKey("acopios.id"), nullable=False)
    
    # Relationships
    acopio = relationship("Acopio", back_populates="presupuestos")
