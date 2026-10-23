"""Reviewed Tango snapshots, independent from manual documents and consumption."""
from sqlalchemy import Column, Integer, String, ForeignKey, JSON, DateTime, UniqueConstraint, CheckConstraint
from models.base import BaseModel


class TangoRegistro(BaseModel):
    __tablename__ = "tango_registros"
    acopio_id = Column(Integer, ForeignKey("acopios.id", ondelete="CASCADE"), nullable=False, index=True)
    empresa = Column(String(20), nullable=False)
    origen_tipo = Column(String(10), nullable=False)
    origen_id = Column(Integer, nullable=False)
    huella = Column(String(64), nullable=False)
    datos = Column(JSON, nullable=False)
    estado = Column(String(12), nullable=False, default="PENDIENTE")
    revisado_at = Column(DateTime, nullable=True)
    __table_args__ = (
        UniqueConstraint("acopio_id", "empresa", "origen_tipo", "origen_id", "huella", name="uq_tango_registro_version"),
        CheckConstraint("estado IN ('PENDIENTE','CONSERVADO','DESCARTADO','SUPERADO')", name="ck_tango_revision"),
    )