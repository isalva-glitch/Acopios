"""Pedido service with business logic."""
from typing import Dict, Any
from sqlalchemy.orm import Session
from datetime import date
from decimal import Decimal

from models import Pedido, EstadoPedido
from services.acopio_service import get_or_create_cliente, get_or_create_obra


def create_from_extraction(db: Session, extraction_package: Dict[str, Any], obra_id: int) -> Pedido:
    """
    Create pedido from extraction package.
    
    Args:
        db: Database session
        extraction_package: Extraction package (similar to acopio)
        obra_id: ID of the obra
        
    Returns:
        Created Pedido instance
    """
    # For pedido extraction, we expect pedidos array in the package
    pedidos_data = extraction_package.get("pedidos", [])
    
    if not pedidos_data:
        raise ValueError("No pedido data found in extraction package")
    
    # Create first pedido (typically only one per PDF)
    pedido_data = pedidos_data[0]
    
    pedido = Pedido(
        obra_id=obra_id,
        numero=pedido_data["numero"],
        fecha=date.fromisoformat(pedido_data["fecha"]),
        estado=EstadoPedido.PENDIENTE,
        total_m2=Decimal(str(pedido_data.get("total_m2", 0))),
        total_ml=Decimal(str(pedido_data.get("total_ml", 0))),
        total_pesos=Decimal(str(pedido_data.get("total_pesos", 0)))
    )
    
    db.add(pedido)
    db.commit()
    db.refresh(pedido)
    
    return pedido
