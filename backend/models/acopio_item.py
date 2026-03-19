"""AcopioItem model."""
from sqlalchemy import Column, String, Integer, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from models.base import BaseModel


class AcopioItem(BaseModel):
    """Acopio Item entity."""
    
    __tablename__ = "acopio_items"
    
    descripcion = Column(String(500), nullable=False)
    material = Column(String(200), nullable=True)
    tipologia = Column(String(200), nullable=True)
    cantidad = Column(Integer, nullable=False, default=0)
    
    # Totales del item
    total_m2 = Column(Numeric(12, 2), nullable=False, default=0)
    total_ml = Column(Numeric(12, 2), nullable=False, default=0)
    total_pesos = Column(Numeric(15, 2), nullable=False, default=0)
    
    # Saldos del item
    saldo_m2 = Column(Numeric(12, 2), nullable=False, default=0)
    saldo_ml = Column(Numeric(12, 2), nullable=False, default=0)
    saldo_pesos = Column(Numeric(15, 2), nullable=False, default=0)
    saldo_cantidad = Column(Integer, nullable=False, default=0)
    
    # Foreign keys
    acopio_id = Column(Integer, ForeignKey("acopios.id"), nullable=False)
    
    # Relationships
    acopio = relationship("Acopio", back_populates="items")
    panos = relationship("AcopioItemPano", back_populates="item", cascade="all, delete-orphan")
    imputaciones = relationship("Imputacion", back_populates="acopio_item")
