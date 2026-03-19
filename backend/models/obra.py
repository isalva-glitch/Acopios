"""Obra model."""
from sqlalchemy import Column, String, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from models.base import BaseModel
import enum


class EstadoObra(str, enum.Enum):
    """Estado de obra."""
    ACTIVA = "ACTIVA"
    PAUSADA = "PAUSADA"
    FINALIZADA = "FINALIZADA"
    CANCELADA = "CANCELADA"


class Obra(BaseModel):
    """Obra entity."""
    
    __tablename__ = "obras"
    
    nombre = Column(String(200), nullable=False)
    direccion = Column(String(500), nullable=True)
    estado = Column(SQLEnum(EstadoObra), default=EstadoObra.ACTIVA, nullable=False)
    
    # Foreign keys
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    
    # Relationships
    cliente = relationship("Cliente", back_populates="obras")
    acopios = relationship("Acopio", back_populates="obra", cascade="all, delete-orphan")
    pedidos = relationship("Pedido", back_populates="obra", cascade="all, delete-orphan")
