"""Presupuesto model."""
from sqlalchemy import Column, String, Integer, ForeignKey, Date, Text, Numeric
from sqlalchemy.orm import relationship
from models.base import BaseModel


class Presupuesto(BaseModel):
    """Presupuesto entity."""
    
    __tablename__ = "presupuestos"
    
    numero = Column(String(100), nullable=False)
    fecha = Column(Date, nullable=True)   # nullable: PDF puede no tener fecha de aprobación
    condiciones = Column(Text, nullable=True)
    estado = Column(String(50), nullable=True)
    
    # Campos adicionales para origen PDF
    empresa = Column(String(200), nullable=True)        # empresa/cliente del PDF
    contacto = Column(String(200), nullable=True)       # contacto en la empresa
    cotizado_por = Column(String(100), nullable=True)   # quien cotizó
    peso_estimado_kg = Column(Numeric(10, 2), nullable=True)  # peso total estimado

    # Foreign keys
    acopio_id = Column(Integer, ForeignKey("acopios.id"), nullable=False)
    
    # Relationships
    acopio = relationship("Acopio", back_populates="presupuestos")
