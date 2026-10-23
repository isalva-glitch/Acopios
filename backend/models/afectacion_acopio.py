"""AfectacionAcopio model."""
from sqlalchemy import Column, Integer, ForeignKey, Numeric, Boolean
from sqlalchemy.orm import relationship
from models.base import BaseModel


class AfectacionAcopio(BaseModel):
    """Afectación de comprobante contra acopio."""
    
    __tablename__ = "afectaciones_acopio"
    
    importe = Column(Numeric(15, 2), nullable=False)
    
    # NULL indica una afectacion historica aun sin clasificar.
    importe_facturado = Column(Numeric(15, 2), nullable=True)
    referencia_id = Column(Integer, ForeignKey("afectaciones_acopio.id", ondelete="SET NULL"), nullable=True, index=True)
    anulada = Column(Boolean, nullable=False, default=False, server_default="false" )

    # Foreign keys
    acopio_id = Column(Integer, ForeignKey("acopios.id"), nullable=False)
    comprobante_id = Column(Integer, ForeignKey("comprobantes.id"), nullable=False)
    
    # Relationships
    acopio = relationship("Acopio", back_populates="afectaciones")
    comprobante = relationship("Comprobante", back_populates="afectaciones")
