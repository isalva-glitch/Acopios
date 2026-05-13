"""Process quantities captured for an imputation."""
from sqlalchemy import Column, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship
from models.base import BaseModel


class ImputacionProceso(BaseModel):
    """Snapshot of process quantities consumed by one imputation."""

    __tablename__ = "imputacion_procesos"
    __table_args__ = (
        UniqueConstraint("imputacion_id", "proceso", name="uq_imputacion_proceso"),
    )

    proceso = Column(String(100), nullable=False)
    unidad = Column(String(10), nullable=False)
    cantidad = Column(Numeric(14, 4), nullable=False, default=0)
    origen = Column(String(50), nullable=False, default="snapshot_spf")

    imputacion_id = Column(
        Integer,
        ForeignKey("imputaciones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    imputacion = relationship("Imputacion", back_populates="procesos")
