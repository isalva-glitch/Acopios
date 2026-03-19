"""Tests for business rules."""
import pytest
from decimal import Decimal
from models import Acopio, EstadoAcopio, Cliente, Obra
from services.imputacion_service import check_excedente, imputar_consumo
from config import settings


def test_excedente_detection(db_session):
    """Test that excedente is correctly detected."""
    # Create cliente, obra, and acopio
    cliente = Cliente(nombre="Test Cliente")
    db_session.add(cliente)
    db_session.flush()
    
    obra = Obra(nombre="Test Obra", cliente_id=cliente.id)
    db_session.add(obra)
    db_session.flush()
    
    acopio = Acopio(
        obra_id=obra.id,
        numero="TEST001",
        fecha_alta="2024-01-01",
        total_m2=Decimal("100"),
        total_ml=Decimal("50"),
        total_pesos=Decimal("10000"),
        saldo_m2=Decimal("100"),
        saldo_ml=Decimal("50"),
        saldo_pesos=Decimal("10000")
    )
    db_session.add(acopio)
    db_session.flush()
    
    # Check excedente when consuming more than available
    is_excedente, warning = check_excedente(
        db_session,
        acopio.id,
        None,
        Decimal("150"),  # More than available
        Decimal("25"),
        Decimal("5000")
    )
    
    assert is_excedente is True
    assert warning is not None
    assert "excede" in warning.lower()


def test_saldo_update_after_imputacion(db_session):
    """Test that saldos are updated after imputacion."""
    from models import Pedido, EstadoPedido
    
    # Create cliente, obra, acopio, and pedido
    cliente = Cliente(nombre="Test Cliente")
    db_session.add(cliente)
    db_session.flush()
    
    obra = Obra(nombre="Test Obra", cliente_id=cliente.id)
    db_session.add(obra)
    db_session.flush()
    
    acopio = Acopio(
        obra_id=obra.id,
        numero="TEST002",
        fecha_alta="2024-01-01",
        total_m2=Decimal("100"),
        total_ml=Decimal("50"),
        total_pesos=Decimal("10000"),
        saldo_m2=Decimal("100"),
        saldo_ml=Decimal("50"),
        saldo_pesos=Decimal("10000")
    )
    db_session.add(acopio)
    db_session.flush()
    
    pedido = Pedido(
        obra_id=obra.id,
        numero="PED001",
        fecha="2024-01-02",
        total_m2=Decimal("50"),
        total_ml=Decimal("25"),
        total_pesos=Decimal("5000")
    )
    db_session.add(pedido)
    db_session.flush()
    
    # Save original policy
    original_policy = settings.excedente_policy
    
    try:
        # Set policy to ALLOW
        settings.excedente_policy = "ALLOW"
        
        # Create imputacion
        imputacion, warning = imputar_consumo(
            db_session,
            pedido.id,
            acopio.id,
            None,
            Decimal("50"),
            Decimal("25"),
            Decimal("5000")
        )
        
        # Refresh acopio
        db_session.refresh(acopio)
        
        # Check saldos were updated
        assert acopio.saldo_m2 == Decimal("50")
        assert acopio.saldo_ml == Decimal("25")
        assert acopio.saldo_pesos == Decimal("5000")
        
        # Check estado
        assert acopio.estado == EstadoAcopio.PARCIALMENTE_CONSUMIDO
        
    finally:
        # Restore original policy
        settings.excedente_policy = original_policy
