"""Tests for business rules."""
import pytest
from decimal import Decimal
from datetime import date
from models import Acopio, EstadoAcopio, Cliente, Obra
from services.imputacion_service import check_excedente, imputar_consumo, imputar_consumos
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
        fecha_alta=date(2024, 1, 1),
        total_m2=Decimal("100"),
        total_ml=Decimal("50"),
        total_pesos=Decimal("10000"),
        total_unidades=0,
        saldo_m2=Decimal("100"),
        saldo_ml=Decimal("50"),
        saldo_pesos=Decimal("10000"),
        saldo_unidades=0,
    )
    db_session.add(acopio)
    db_session.flush()
    
    # Check excedente when consuming more than available
    is_excedente, excedente_tipo, warning = check_excedente(
        db_session,
        acopio.id,
        None,
        Decimal("150"),  # More than available
        Decimal("25"),
        Decimal("5000"),
        0,
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
        fecha_alta=date(2024, 1, 1),
        total_m2=Decimal("100"),
        total_ml=Decimal("50"),
        total_pesos=Decimal("10000"),
        total_unidades=0,
        saldo_m2=Decimal("100"),
        saldo_ml=Decimal("50"),
        saldo_pesos=Decimal("10000"),
        saldo_unidades=0,
    )
    db_session.add(acopio)
    db_session.flush()
    
    pedido = Pedido(
        obra_id=obra.id,
        numero="PED001",
        fecha=date(2024, 1, 2),
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
            Decimal("5000"),
            0,
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


def test_imputar_consumos_detects_batch_excedente(db_session):
    """The complete pedido can exceed saldo even when each item row fits."""
    from models import Pedido

    cliente = Cliente(nombre="Test Cliente")
    db_session.add(cliente)
    db_session.flush()

    obra = Obra(nombre="Test Obra", cliente_id=cliente.id)
    db_session.add(obra)
    db_session.flush()

    acopio = Acopio(
        obra_id=obra.id,
        numero="TEST003",
        fecha_alta=date(2024, 1, 1),
        total_m2=Decimal("10"),
        total_ml=Decimal("10"),
        total_pesos=Decimal("1000"),
        total_unidades=0,
        saldo_m2=Decimal("10"),
        saldo_ml=Decimal("10"),
        saldo_pesos=Decimal("1000"),
        saldo_unidades=0,
    )
    db_session.add(acopio)
    db_session.flush()

    pedido = Pedido(
        obra_id=obra.id,
        numero="PED002",
        fecha=date(2024, 1, 2),
        total_m2=Decimal("12"),
        total_ml=Decimal("0"),
        total_pesos=Decimal("0"),
    )
    db_session.add(pedido)
    db_session.flush()

    original_policy = settings.excedente_policy

    try:
        settings.excedente_policy = "WARN"

        imputaciones, warnings = imputar_consumos(db_session, [
            {
                "pedido_id": pedido.id,
                "acopio_id": acopio.id,
                "acopio_item_id": None,
                "cantidad_m2": Decimal("6"),
                "cantidad_ml": Decimal("0"),
                "cantidad_pesos": Decimal("0"),
                "cantidad_unidades": 0,
            },
            {
                "pedido_id": pedido.id,
                "acopio_id": acopio.id,
                "acopio_item_id": None,
                "cantidad_m2": Decimal("6"),
                "cantidad_ml": Decimal("0"),
                "cantidad_pesos": Decimal("0"),
                "cantidad_unidades": 0,
            },
        ])

        assert len(imputaciones) == 2
        assert all(imputacion.es_excedente for imputacion in imputaciones)
        assert any("consumo acumulado m2" in warning for warning in warnings)
    finally:
        settings.excedente_policy = original_policy
