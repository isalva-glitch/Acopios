"""Acopio package model."""
from sqlalchemy import Column, Date, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship

from models.base import BaseModel


class AcopioPaquete(BaseModel):
    """Grouping entity for multiple operational acopios."""

    __tablename__ = "acopio_paquetes"

    numero = Column(String(50), unique=True, index=True, nullable=True)
    nombre = Column(String(200), nullable=False)
    cliente = Column(String(200), nullable=False)
    fecha_alta = Column(Date, nullable=False)
    estado = Column(String(50), default="ACTIVO", nullable=False)
    observaciones = Column(Text, nullable=True)

    total_pesos = Column(Numeric(15, 2), nullable=False, default=0)
    total_m2 = Column(Numeric(12, 2), nullable=False, default=0)
    total_ml = Column(Numeric(12, 2), nullable=False, default=0)
    total_unidades = Column(Integer, nullable=False, default=0)

    acopios = relationship("Acopio", back_populates="paquete")
