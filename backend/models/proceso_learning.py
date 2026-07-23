"""Process learning feedback and proposed rules."""
from sqlalchemy import Column, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint

from models.base import BaseModel


class CorreccionProceso(BaseModel):
    """Audit row for manual process corrections on acopio items."""

    __tablename__ = "correcciones_proceso"

    acopio_id = Column(Integer, ForeignKey("acopios.id"), nullable=True, index=True)
    acopio_item_id = Column(Integer, ForeignKey("acopio_items.id"), nullable=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=True, index=True)
    origen = Column(String(40), nullable=False, default="manual")
    estado = Column(String(40), nullable=False, default="registrada")
    texto_original = Column(Text, nullable=False, default="")
    texto_normalizado = Column(Text, nullable=False, default="")
    procesos_antes = Column(JSON, nullable=False, default=dict)
    procesos_despues = Column(JSON, nullable=False, default=dict)
    cambios = Column(JSON, nullable=False, default=dict)


class ReglaProceso(BaseModel):
    """Candidate or approved deterministic process rule."""

    __tablename__ = "reglas_proceso"
    __table_args__ = (
        UniqueConstraint(
            "patron",
            "proceso",
            "accion",
            "alcance",
            name="uq_regla_proceso_patron_proceso_accion_alcance",
        ),
    )

    patron = Column(Text, nullable=False)
    tipo_patron = Column(String(40), nullable=False, default="texto_normalizado")
    proceso = Column(String(100), nullable=False)
    accion = Column(String(20), nullable=False)
    alcance = Column(String(50), nullable=False, default="item_text_exact")
    estado = Column(String(40), nullable=False, default="propuesta")
    prioridad = Column(Integer, nullable=False, default=100)
    soporte_count = Column(Integer, nullable=False, default=1)
    confianza = Column(Numeric(6, 4), nullable=False, default=0)
    ejemplos = Column(JSON, nullable=False, default=list)
    creada_desde_correccion_id = Column(
        Integer,
        ForeignKey("correcciones_proceso.id"),
        nullable=True,
        index=True,
    )
