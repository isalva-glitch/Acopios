import pytest
from decimal import Decimal
from sqlalchemy.orm import Session
from models import Acopio, AcopioItem, Imputacion
from services.imputacion_service import check_excedente, imputar_consumos

def test_excedente_item_vs_acopio_global(db_session: Session):
    # Create acopio
    acopio = Acopio(
        numero="AC-TEST-1",
        empresa="TEST",
        obra="TEST",
        fecha="2023-01-01",
        saldo_m2=Decimal("100.00"),
        saldo_ml=Decimal("100.00"),
        saldo_pesos=Decimal("10000.00"),
        saldo_unidades=10
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
