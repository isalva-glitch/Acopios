"""Pedido model."""
from sqlalchemy import Column, String, Integer, ForeignKey, Numeric, Date, Enum as SQLEnum
from sqlalchemy.orm import relationship
from models.base import BaseModel
import enum


class EstadoPedido(str, enum.Enum):
    """Estado de pedido."""
    PENDIENTE = "PENDIENTE"
    CONFIRMADO = "CONFIRMADO"
    EN_PREPARACION = "EN_PREPARACION"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"


class Pedido(BaseModel):
    """Pedido entity."""
    
    __tablename__ = "pedidos"
    
    numero = Column(String(100), nullable=False)
    fecha = Column(Date, nullable=False)
    estado = Column(SQLEnum(EstadoPedido), default=EstadoPedido.PENDIENTE, nullable=False)
    
    # Totales del pedido
    total_m2 = Column(Numeric(12, 2), nullable=False, default=0)
    total_ml = Column(Numeric(12, 2), nullable=False, default=0)
    total_pesos = Column(Numeric(15, 2), nullable=False, default=0)
    
    # Foreign keys
    obra_id = Column(Integer, ForeignKey("obras.id"), nullable=False)
    
    # Relationships
    obra = relationship("Obra", back_populates="pedidos")
    remitos = relationship("Remito", back_populates="pedido", cascade="all, delete-orphan")
    imputaciones = relationship("Imputacion", back_populates="pedido", cascade="all, delete-orphan")
