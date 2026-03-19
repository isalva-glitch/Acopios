"""Acopio model."""
from sqlalchemy import Column, String, Integer, ForeignKey, Numeric, Date, Enum as SQLEnum
from sqlalchemy.orm import relationship
from models.base import BaseModel
import enum


class EstadoAcopio(str, enum.Enum):
    """Estado de acopio."""
    PENDIENTE = "PENDIENTE"
    ACTIVO = "ACTIVO"
    PARCIALMENTE_CONSUMIDO = "PARCIALMENTE_CONSUMIDO"
    CONSUMIDO = "CONSUMIDO"
    VENCIDO = "VENCIDO"
    CANCELADO = "CANCELADO"


class Acopio(BaseModel):
    """Acopio entity."""
    
    __tablename__ = "acopios"
    
    numero = Column(String(50), nullable=True)
    fecha_alta = Column(Date, nullable=False)
    estado = Column(SQLEnum(EstadoAcopio), default=EstadoAcopio.PENDIENTE, nullable=False)
    
    # SPF Integration fields
    v_presupuesto_id = Column(String(100), index=True, nullable=True)
    cliente_id = Column(Integer, nullable=True)
    origen_datos = Column(String(50), default='spf_production', nullable=False)
    
    # Totales contratados
    total_m2 = Column(Numeric(12, 2), nullable=False, default=0)
    total_ml = Column(Numeric(12, 2), nullable=False, default=0)
    total_pesos = Column(Numeric(15, 2), nullable=False, default=0)
    total_unidades = Column(Integer, nullable=False, default=0)
    
    # Saldos disponibles
    saldo_m2 = Column(Numeric(12, 2), nullable=False, default=0)
    saldo_ml = Column(Numeric(12, 2), nullable=False, default=0)
    saldo_pesos = Column(Numeric(15, 2), nullable=False, default=0)
    saldo_unidades = Column(Integer, nullable=False, default=0)
    
    # Vencimiento de precio
    fecha_vencimiento_precio = Column(Date, nullable=True)
    
    # Foreign keys
    obra_id = Column(Integer, ForeignKey("obras.id"), nullable=True)
    
    # Relationships
    obra = relationship("Obra", back_populates="acopios")
    presupuestos = relationship("Presupuesto", back_populates="acopio", cascade="all, delete-orphan")
    items = relationship("AcopioItem", back_populates="acopio", cascade="all, delete-orphan")
    imputaciones = relationship("Imputacion", back_populates="acopio", cascade="all, delete-orphan")
    afectaciones = relationship("AfectacionAcopio", back_populates="acopio", cascade="all, delete-orphan")
