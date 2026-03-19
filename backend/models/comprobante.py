"""Comprobante model."""
from sqlalchemy import Column, String, Date, Numeric, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from models.base import BaseModel
import enum


class TipoComprobante(str, enum.Enum):
    """Tipo de comprobante contable."""
    FAC_ANTICIPO = "FAC_ANTICIPO"
    RECIBO = "RECIBO"
    FAC_MERCADERIA = "FAC_MERCADERIA"
    NC = "NC"  # Nota de crédito


class Comprobante(BaseModel):
    """Comprobante contable entity."""
    
    __tablename__ = "comprobantes"
    
    tipo = Column(SQLEnum(TipoComprobante), nullable=False)
    numero = Column(String(100), nullable=False)
    fecha = Column(Date, nullable=False)
    importe = Column(Numeric(15, 2), nullable=False)
    descripcion = Column(Text, nullable=True)
    
    # Relationships
    afectaciones = relationship("AfectacionAcopio", back_populates="comprobante", cascade="all, delete-orphan")
