"""Imputacion model."""
from sqlalchemy import Column, Integer, ForeignKey, Numeric, Boolean
from sqlalchemy import String
from sqlalchemy.orm import relationship
from models.base import BaseModel


class Imputacion(BaseModel):
    """Imputacion (consumption) entity."""
    
    __tablename__ = "imputaciones"
    
    # Cantidades imputadas
    cantidad_m2 = Column(Numeric(12, 2), nullable=False, default=0)
    cantidad_ml = Column(Numeric(12, 2), nullable=False, default=0)
    cantidad_pesos = Column(Numeric(15, 2), nullable=False, default=0)
    cantidad_unidades = Column(Integer, nullable=False, default=0)
    
    # Control de excedente
    es_excedente = Column(Boolean, default=False, nullable=False)

    # Control de composicion
    pedido_item_descripcion = Column(String(500), nullable=True)
    composicion_normalizada = Column(String(1200), nullable=True)
    composicion_match_estado = Column(String(50), nullable=True)
    composicion_match_score = Column(Numeric(6, 4), nullable=True)
    composicion_advertencia = Column(String(1200), nullable=True)
    
    # Foreign keys
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False)
    acopio_id = Column(Integer, ForeignKey("acopios.id"), nullable=False)
    acopio_item_id = Column(Integer, ForeignKey("acopio_items.id"), nullable=True)
    
    # Relationships
    pedido = relationship("Pedido", back_populates="imputaciones")
    acopio = relationship("Acopio", back_populates="imputaciones")
    acopio_item = relationship("AcopioItem", back_populates="imputaciones")
    procesos = relationship("ImputacionProceso", back_populates="imputacion", cascade="all, delete-orphan")
