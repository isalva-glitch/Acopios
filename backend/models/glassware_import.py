"""Auditable, server-side previews for Glassware imports; no cookies or HTML."""
from sqlalchemy import Column, String, JSON, Integer, ForeignKey, DateTime
from models.base import BaseModel


class GlasswareImport(BaseModel):
    __tablename__ = 'glassware_imports'
    token = Column(String(36), nullable=False, unique=True)
    glassware_id = Column(String(30), nullable=False, index=True)
    numero = Column(String(50), nullable=False, index=True)
    datos = Column(JSON, nullable=False)
    acopio_id = Column(Integer, ForeignKey('acopios.id', ondelete='SET NULL'), nullable=True, unique=True)
    confirmado_en = Column(DateTime, nullable=True)
