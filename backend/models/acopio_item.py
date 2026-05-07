"""AcopioItem model."""
from sqlalchemy import Boolean, Column, String, Integer, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from models.base import BaseModel


class AcopioItem(BaseModel):
    """Acopio Item entity."""
    
    __tablename__ = "acopio_items"
    
    numero_item = Column(Integer, nullable=True)  # PDF: número secuencial del ítem
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

    # Procesos asociados a precios de referencia
    proceso_vidrio_exterior = Column(Boolean, nullable=False, default=False)
    proceso_vidrio_interior = Column(Boolean, nullable=False, default=False)
    proceso_camara_estructural = Column(Boolean, nullable=False, default=False)
    proceso_pulido = Column(Boolean, nullable=False, default=False)
    proceso_fason_templado_exterior = Column(Boolean, nullable=False, default=False)
    proceso_pegado_bastidor = Column(Boolean, nullable=False, default=False)
    proceso_camara_normal = Column(Boolean, nullable=False, default=False)
    proceso_opacificado_perimetral = Column(Boolean, nullable=False, default=False)
    proceso_opacificado_total = Column(Boolean, nullable=False, default=False)
    proceso_camara_offset = Column(Boolean, nullable=False, default=False)
    
    # Foreign keys
    acopio_id = Column(Integer, ForeignKey("acopios.id"), nullable=False)
    
    # Relationships
    acopio = relationship("Acopio", back_populates="items")
    panos = relationship("AcopioItemPano", back_populates="item", cascade="all, delete-orphan")
    adicionales = relationship("AcopioItemAdicional", back_populates="item", cascade="all, delete-orphan")
    imputaciones = relationship("Imputacion", back_populates="acopio_item")
