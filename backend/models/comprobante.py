"""Comprobante model."""
from sqlalchemy import Column, String, Date, Numeric, Text, Integer, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import relationship
from models.base import BaseModel
import enum


class TipoComprobante(str, enum.Enum):
    """Tipo de comprobante contable."""
    ORDEN_COMPRA = "ORDEN_COMPRA"
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
    
    # Importe es siempre el neto original del comprobante.
    emisor = Column(String(200), nullable=False, default="", server_default="" )
    iva = Column(Numeric(15, 2), nullable=True)
    documento_id = Column(Integer, ForeignKey("documentos.id"), nullable=True)
    documento = relationship("Documento")
    origen_tango = relationship("TangoComprobante", uselist=False)
    __table_args__ = (UniqueConstraint("tipo", "numero", "emisor", name="uq_comprobante_identidad"),)

    # Relationships
    afectaciones = relationship("AfectacionAcopio", back_populates="comprobante", cascade="all, delete-orphan")
