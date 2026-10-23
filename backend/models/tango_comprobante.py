"""Stable Tango identity for documents explicitly associated by the user."""
from sqlalchemy import Column, Integer, String, JSON, ForeignKey, UniqueConstraint
from models.base import BaseModel


class TangoComprobante(BaseModel):
    __tablename__ = "tango_comprobantes"
    empresa = Column(String(20), nullable=False)
    origen_tipo = Column(String(10), nullable=False)
    origen_id = Column(Integer, nullable=False)
    comprobante_id = Column(Integer, ForeignKey("comprobantes.id"), nullable=False, unique=True)
    datos = Column(JSON, nullable=False)
    __table_args__ = (
        UniqueConstraint("empresa", "origen_tipo", "origen_id", name="uq_tango_comprobante_origen"),
    )
