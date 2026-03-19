"""Documento model."""
from sqlalchemy import Column, String, Text
from models.base import BaseModel


class Documento(BaseModel):
    """Documento entity for file tracking."""
    
    __tablename__ = "documentos"
    
    # Entidad asociada
    entidad_tipo = Column(String(50), nullable=False)  # "acopio", "pedido", etc.
    entidad_id = Column(String(50), nullable=False)
    
    # Datos del documento
    tipo_documento = Column(String(100), nullable=False)  # "presupuesto_original", "pedido_pdf", etc.
    nombre_archivo = Column(String(500), nullable=False)
    hash = Column(String(64), nullable=False, unique=True)  # SHA256
    ruta_storage = Column(Text, nullable=False)
