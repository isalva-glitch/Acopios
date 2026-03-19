"""SQLAlchemy models mapped to the external spf_production database."""
from sqlalchemy import Column, Integer, String, Date, Numeric, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from .database import SpfBase

class SpfPedido(SpfBase):
    """
    Mapping to public.pedidos in SPF.
    """
    __tablename__ = 'pedidos'

    id = Column(Integer, primary_key=True)
    id_presupuesto = Column(String(50))
    nro_pedido = Column(String(50))
    cliente_id = Column(Integer)
    contacto_id = Column(Integer)
    fecha_activacion = Column(Date)
    fecha_finalizacion = Column(Date)
    fecha_entrega = Column(Date)
    fecha_est_entrega = Column(Date)
    fecha_compromiso = Column(Date)
    fecha_anulacion = Column(Date)
    fecha_canc = Column(Date)
    comentario_pedido = Column(String)
    criterio_facturacion = Column(String(100))
    estado_id = Column(Integer)
    tipo_pedido_id = Column(Integer)
    prioridad_id = Column(Integer)
    porcentaje_presupuesto = Column(Numeric(5, 2))
    nro_factura_pedido = Column(String(50))
    observaciones = Column(String)
    con_iva = Column(Boolean)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    items = relationship("SpfItem", back_populates="pedido")


class SpfItem(SpfBase):
    """
    Mapping to public.items in SPF.
    """
    __tablename__ = 'items'

    id = Column(Integer, primary_key=True)
    descripcion = Column(String)
    pedido_id = Column(Integer, ForeignKey('pedidos.id'))
    v_presupuesto_id = Column(String(100), index=True)
    v_item_id = Column(Integer)
    medida_burlete = Column(Numeric(12, 2))
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    pedido = relationship("SpfPedido", back_populates="items")
    medidas = relationship("SpfItemMedida", back_populates="item")
    complementos = relationship("SpfItemComplemento", back_populates="item")


class SpfItemMedida(SpfBase):
    """
    Mapping to public.item_medidas in SPF.
    """
    __tablename__ = 'item_medidas'

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey('items.id'))
    cantidad = Column(Integer)
    denominacion = Column(String(255))
    superficie = Column(Numeric(12, 2))
    perimtero = Column(Numeric(12, 2))
    total_item = Column(Numeric(15, 2))
    medida_id = Column(Integer)
    con_forma = Column(Boolean)
    alto = Column(Numeric(12, 2))
    ancho = Column(Numeric(12, 2))
    forma_id = Column(Integer)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    item = relationship("SpfItem", back_populates="medidas")


class SpfItemComplemento(SpfBase):
    """
    Mapping to public.item_complementos in SPF.
    """
    __tablename__ = 'item_complementos'

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey('items.id'))
    v_complemento_id = Column(Integer)
    minimo = Column(Numeric(12, 2))
    total_complemento = Column(Numeric(15, 2))
    cantidad = Column(Integer)
    created_at = Column(DateTime)
    updated_at = Column(DateTime)

    item = relationship("SpfItem", back_populates="complementos")
