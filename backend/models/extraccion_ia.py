"""ExtraccionIA model."""
from sqlalchemy import Column, Integer, ForeignKey, Boolean, DateTime, JSON
from sqlalchemy.orm import relationship
from models.base import BaseModel
from datetime import datetime


class ExtraccionIA(BaseModel):
    """Extracción de IA de documentos."""
    
    __tablename__ = "extracciones_ia"
    
    # Contenido extraído y validado
    contenido_extraido = Column(JSON, nullable=False)
    warnings = Column(JSON, nullable=True)
    validado = Column(Boolean, default=False, nullable=False)
    fecha_extraccion = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Foreign keys
    documento_id = Column(Integer, ForeignKey("documentos.id"), nullable=False)
