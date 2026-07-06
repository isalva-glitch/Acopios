import pytest
from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from models import Acopio, AcopioItem, Imputacion, Pedido
from config import settings
from services.imputacion_service import check_excedente, imputar_consumos

def test_excedente_item_vs_acopio_global(db_session: Session):
    # Create acopio
    acopio = Acopio(
        numero="AC-TEST-1",
        fecha_alta=date(2023, 1, 1),
        total_m2=Decimal("100.00"),
        total_ml=Decimal("100.00"),
        total_pesos=Decimal("10000.00"),
        total_unidades=10,
        saldo_m2=Decimal("100.00"),
        saldo_ml=Decimal("100.00"),
        saldo_pesos=Decimal("10000.00"),
        saldo_unidades=10,
    )
    db_session.add(acopio)
    db_session.commit()

    # Create acopio item
    item = AcopioItem(
        acopio_id=acopio.id,
        descripcion="Item A",
        saldo_m2=Decimal("20.00"),
        saldo_ml=Decimal("20.00"),
        saldo_pesos=Decimal("2000.00"),
        saldo_cantidad=2
    )
    db_session.add(item)
    db_session.commit()

    # Test 1: Consumo exceeds only item, but not acopio global
    # Consumo m2 = 30 (exceeds item's 20, but within acopio's 100)
    is_excedente, excedente_tipo, warning = check_excedente(
        db=db_session,
        acopio_id=acopio.id,
        acopio_item_id=item.id,
        cantidad_m2=Decimal("30.00"),
        cantidad_ml=Decimal("10.00"),
        cantidad_pesos=Decimal("1000.00"),
        cantidad_unidades=1
    )
    
    assert is_excedente is True
    assert excedente_tipo == "ITEM"

    # Test 2: Consumo exceeds acopio global
    # Consumo m2 = 110 (exceeds acopio's 100)
    is_excedente, excedente_tipo, warning = check_excedente(
        db=db_session,
        acopio_id=acopio.id,
        acopio_item_id=item.id,
        cantidad_m2=Decimal("110.00"),
        cantidad_ml=Decimal("10.00"),
        cantidad_pesos=Decimal("1000.00"),
        cantidad_unidades=1
    )
    
    assert is_excedente is True
    assert excedente_tipo == "ACOPIO"

    # Test 3: No excedente
    is_excedente, excedente_tipo, warning = check_excedente(
        db=db_session,
        acopio_id=acopio.id,
        acopio_item_id=item.id,
        cantidad_m2=Decimal("10.00"),
        cantidad_ml=Decimal("10.00"),
        cantidad_pesos=Decimal("1000.00"),
        cantidad_unidades=1
    )
    
    assert is_excedente is False
    assert excedente_tipo == "NONE"


def test_money_precision_does_not_create_excedente_for_equal_cents(db_session: Session):
    acopio = Acopio(
        numero="AC-TEST-2",
        fecha_alta=date(2024, 1, 1),
        total_m2=Decimal("100.00"),
        total_ml=Decimal("100.00"),
        total_pesos=Decimal("1128417.90"),
        total_unidades=19,
        saldo_m2=Decimal("100.00"),
        saldo_ml=Decimal("100.00"),
        saldo_pesos=Decimal("1128417.90"),
        saldo_unidades=19,
    )
    db_session.add(acopio)
    db_session.flush()

    item = AcopioItem(
        acopio_id=acopio.id,
        numero_item=1,
        descripcion="Laminado 4+4 Gris Claro con Borde Pulido",
        cantidad=19,
        total_m2=Decimal("16.62"),
        total_ml=Decimal("73.41"),
        total_pesos=Decimal("1128417.90"),
        saldo_m2=Decimal("16.62"),
        saldo_ml=Decimal("73.41"),
        saldo_pesos=Decimal("1128417.90"),
        saldo_cantidad=19,
    )
    db_session.add(item)
    db_session.flush()

    is_excedente, excedente_tipo, warning = check_excedente(
        db=db_session,
        acopio_id=acopio.id,
        acopio_item_id=item.id,
        cantidad_m2=Decimal("16.61"),
        cantidad_ml=Decimal("73.41"),
        cantidad_pesos=Decimal("1128417.9000000001"),
        cantidad_unidades=19,
    )

    assert is_excedente is False
    assert excedente_tipo == "NONE"
    assert warning is None


def test_money_precision_one_cent_over_item_is_excedente(db_session: Session):
    acopio = Acopio(
        numero="AC-TEST-3",
        fecha_alta=date(2024, 1, 1),
        total_m2=Decimal("100.00"),
        total_ml=Decimal("100.00"),
        total_pesos=Decimal("9999999.99"),
        total_unidades=19,
        saldo_m2=Decimal("100.00"),
        saldo_ml=Decimal("100.00"),
        saldo_pesos=Decimal("9999999.99"),
        saldo_unidades=19,
    )
    db_session.add(acopio)
    db_session.flush()

    item = AcopioItem(
        acopio_id=acopio.id,
        numero_item=1,
        descripcion="Laminado 4+4 Gris Claro con Borde Pulido",
        cantidad=19,
        total_m2=Decimal("16.62"),
        total_ml=Decimal("73.41"),
        total_pesos=Decimal("1128417.90"),
        saldo_m2=Decimal("16.62"),
        saldo_ml=Decimal("73.41"),
        saldo_pesos=Decimal("1128417.90"),
        saldo_cantidad=19,
    )
    db_session.add(item)
    db_session.flush()

    is_excedente, excedente_tipo, warning = check_excedente(
        db=db_session,
        acopio_id=acopio.id,
        acopio_item_id=item.id,
        cantidad_m2=Decimal("16.61"),
        cantidad_ml=Decimal("73.41"),
        cantidad_pesos=Decimal("1128417.91"),
        cantidad_unidades=19,
    )

    assert is_excedente is True
    assert excedente_tipo == "ITEM"
    assert warning is not None
    assert "pesos excede saldo" in warning


def test_money_precision_one_cent_over_acopio_is_excedente(db_session: Session):
    acopio = Acopio(
        numero="AC-TEST-4",
        fecha_alta=date(2024, 1, 1),
        total_m2=Decimal("100.00"),
        total_ml=Decimal("100.00"),
        total_pesos=Decimal("1128417.90"),
        total_unidades=19,
        saldo_m2=Decimal("100.00"),
        saldo_ml=Decimal("100.00"),
        saldo_pesos=Decimal("1128417.90"),
        saldo_unidades=19,
    )
    db_session.add(acopio)
    db_session.flush()

    is_excedente, excedente_tipo, warning = check_excedente(
        db=db_session,
        acopio_id=acopio.id,
        acopio_item_id=None,
        cantidad_m2=Decimal("16.61"),
        cantidad_ml=Decimal("73.41"),
        cantidad_pesos=Decimal("1128417.91"),
        cantidad_unidades=19,
    )

    assert is_excedente is True
    assert excedente_tipo == "ACOPIO"
    assert warning is not None
    assert "pesos: consumo 1128417.91 excede saldo 1128417.90" in warning


def test_money_precision_does_not_create_batch_excedente(db_session: Session):
    acopio = Acopio(
        numero="AC-TEST-5",
        fecha_alta=date(2024, 1, 1),
        total_m2=Decimal("100.00"),
        total_ml=Decimal("100.00"),
        total_pesos=Decimal("1128417.90"),
        total_unidades=19,
        saldo_m2=Decimal("100.00"),
        saldo_ml=Decimal("100.00"),
        saldo_pesos=Decimal("1128417.90"),
        saldo_unidades=19,
    )
    db_session.add(acopio)
    db_session.flush()

    item = AcopioItem(
        acopio_id=acopio.id,
        numero_item=1,
        descripcion="Laminado 4+4 Gris Claro con Borde Pulido",
        cantidad=19,
        total_m2=Decimal("16.62"),
        total_ml=Decimal("73.41"),
        total_pesos=Decimal("1128417.90"),
        saldo_m2=Decimal("16.62"),
        saldo_ml=Decimal("73.41"),
        saldo_pesos=Decimal("1128417.90"),
        saldo_cantidad=19,
    )
    pedido = Pedido(
        numero="23365",
        fecha=date(2024, 1, 2),
        total_m2=Decimal("16.61"),
        total_ml=Decimal("73.41"),
        total_pesos=Decimal("1128417.9000000001"),
    )
    db_session.add_all([item, pedido])
    db_session.flush()

    original_policy = settings.excedente_policy
    try:
        settings.excedente_policy = "WARN"
        imputaciones, warnings = imputar_consumos(db_session, [
            {
                "pedido_id": pedido.id,
                "acopio_id": acopio.id,
                "acopio_item_id": item.id,
                "cantidad_m2": Decimal("16.61"),
                "cantidad_ml": Decimal("73.41"),
                "cantidad_pesos": Decimal("1128417.9000000001"),
                "cantidad_unidades": 19,
            }
        ])
    finally:
        settings.excedente_policy = original_policy

    assert len(imputaciones) == 1
    assert imputaciones[0].es_excedente is False
    assert imputaciones[0].excedente_tipo == "NONE"
    assert warnings == []
