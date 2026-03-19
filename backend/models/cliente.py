"""Cliente model."""
from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from models.base import BaseModel


class Cliente(BaseModel):
    """Cliente entity."""
    
    __tablename__ = "clientes"
    
    nombre = Column(String(200), nullable=False)
    cuit = Column(String(20), nullable=True, unique=True)
    email = Column(String(200), nullable=True)
    telefono = Column(String(50), nullable=True)
    direccion = Column(String(500), nullable=True)
    
    # Relationships
    obras = relationship("Obra", back_populates="cliente", cascade="all, delete-orphan")
