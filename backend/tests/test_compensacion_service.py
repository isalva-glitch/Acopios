from datetime import date
from decimal import Decimal

from models import (
    Acopio,
    AcopioItem,
    Imputacion,
    ImputacionProceso,
    Pedido,
    PrecioReferencia,
)
from services.compensacion_service import build_resumen_compensacion


def test_resumen_compensacion_valoriza_diferencias_positivas_y_negativas(db_session):
    acopio = Acopio(
        numero="COMP-1",
        fecha_alta=date.today(),
        total_m2=Decimal("150.00"),
        total_ml=Decimal("200.00"),
        total_pesos=Decimal("1000.00"),
        total_unidades=10,
        saldo_m2=Decimal("150.00"),
        saldo_ml=Decimal("200.00"),
        saldo_pesos=Decimal("1000.00"),
        saldo_unidades=10,
    )
    db_session.add(acopio)
    db_session.flush()

    db_session.add_all([
        AcopioItem(
            acopio_id=acopio.id,
            descripcion="Eclipse con pulido",
            cantidad=5,
            total_m2=Decimal("100.00"),
            total_ml=Decimal("200.00"),
            total_pesos=Decimal("600.00"),
            saldo_m2=Decimal("100.00"),
            saldo_ml=Decimal("200.00"),
            saldo_pesos=Decimal("600.00"),
            saldo_cantidad=5,
            proceso_vidrio_exterior=True,
            proceso_pulido=True,
        ),
        AcopioItem(
            acopio_id=acopio.id,
            descripcion="Lam 3+3",
            cantidad=5,
            total_m2=Decimal("50.00"),
            total_ml=Decimal("0.00"),
            total_pesos=Decimal("400.00"),
            saldo_m2=Decimal("50.00"),
            saldo_ml=Decimal("0.00"),
            saldo_pesos=Decimal("400.00"),
            saldo_cantidad=5,
            proceso_vidrio_interior=True,
        ),
        PrecioReferencia(
            acopio_id=acopio.id,
            vidrio_exterior=Decimal("10.00"),
            vidrio_interior=Decimal("5.00"),
            pulido=Decimal("2.00"),
        ),
    ])

    pedido = Pedido(
        numero="22628",
        fecha=date.today(),
        total_m2=Decimal("140.00"),
        total_ml=Decimal("150.00"),
        total_pesos=Decimal("800.00"),
    )
    db_session.add(pedido)
    db_session.flush()

    imputacion = Imputacion(
        pedido_id=pedido.id,
        acopio_id=acopio.id,
        cantidad_m2=Decimal("140.00"),
        cantidad_ml=Decimal("150.00"),
        cantidad_pesos=Decimal("800.00"),
        cantidad_unidades=8,
    )
    db_session.add(imputacion)
    db_session.flush()

    db_session.add_all([
        ImputacionProceso(
            imputacion_id=imputacion.id,
            proceso="vidrio_exterior",
            unidad="m2",
            cantidad=Decimal("120.00"),
            origen="snapshot_spf",
        ),
        ImputacionProceso(
            imputacion_id=imputacion.id,
            proceso="vidrio_interior",
            unidad="m2",
            cantidad=Decimal("20.00"),
            origen="snapshot_spf",
        ),
        ImputacionProceso(
            imputacion_id=imputacion.id,
            proceso="pulido",
            unidad="ml",
            cantidad=Decimal("150.00"),
            origen="snapshot_spf",
        ),
    ])
    db_session.commit()

    resumen = build_resumen_compensacion(db_session, acopio.id)
    rows = {row["proceso"]: row for row in resumen["rows"]}

    assert rows["vidrio_exterior"]["diferencia"] == -20
    assert rows["vidrio_exterior"]["importe"] == -200
    assert rows["vidrio_exterior"]["estado"] == "excedente_pedido"

    assert rows["vidrio_interior"]["diferencia"] == 30
    assert rows["vidrio_interior"]["importe"] == 150
    assert rows["pulido"]["diferencia"] == 50
    assert rows["pulido"]["importe"] == 100

    assert resumen["totals"]["positivo"] == 250
    assert resumen["totals"]["negativo"] == -200
    assert resumen["totals"]["saldo"] == 50
    assert resumen["warnings"] == []


def test_resumen_compensacion_no_duplica_camara_estructural_en_offset(db_session):
    acopio = Acopio(
        numero="COMP-OFFSET",
        fecha_alta=date.today(),
        total_m2=Decimal("120.00"),
        total_ml=Decimal("150.00"),
        total_pesos=Decimal("1000.00"),
        total_unidades=10,
        saldo_m2=Decimal("120.00"),
        saldo_ml=Decimal("150.00"),
        saldo_pesos=Decimal("1000.00"),
        saldo_unidades=10,
    )
    db_session.add(acopio)
    db_session.flush()

    db_session.add_all([
        AcopioItem(
            acopio_id=acopio.id,
            descripcion="DVH Camara 12 Estructural",
            cantidad=5,
            total_m2=Decimal("80.00"),
            total_ml=Decimal("100.00"),
            total_pesos=Decimal("600.00"),
            saldo_m2=Decimal("80.00"),
            saldo_ml=Decimal("100.00"),
            saldo_pesos=Decimal("600.00"),
            saldo_cantidad=5,
            proceso_camara_estructural=True,
        ),
        AcopioItem(
            acopio_id=acopio.id,
            descripcion="DVH Camara 12 Estructural Offset",
            cantidad=5,
            total_m2=Decimal("40.00"),
            total_ml=Decimal("50.00"),
            total_pesos=Decimal("400.00"),
            saldo_m2=Decimal("40.00"),
            saldo_ml=Decimal("50.00"),
            saldo_pesos=Decimal("400.00"),
            saldo_cantidad=5,
            proceso_camara_offset=True,
        ),
    ])

    pedido = Pedido(
        numero="22628",
        fecha=date.today(),
        total_m2=Decimal("20.00"),
        total_ml=Decimal("30.00"),
        total_pesos=Decimal("200.00"),
    )
    db_session.add(pedido)
    db_session.flush()

    imputacion_estructural = Imputacion(
        pedido_id=pedido.id,
        acopio_id=acopio.id,
        cantidad_m2=Decimal("10.00"),
        cantidad_ml=Decimal("20.00"),
        cantidad_pesos=Decimal("100.00"),
        cantidad_unidades=2,
        pedido_item_descripcion="DVH Camara 12 mm. Estructural",
    )
    imputacion_offset = Imputacion(
        pedido_id=pedido.id,
        acopio_id=acopio.id,
        cantidad_m2=Decimal("10.00"),
        cantidad_ml=Decimal("10.00"),
        cantidad_pesos=Decimal("100.00"),
        cantidad_unidades=2,
        pedido_item_descripcion="DVH Camara 12 mm. Estructural Offset",
    )
    db_session.add_all([imputacion_estructural, imputacion_offset])
    db_session.flush()

    db_session.add_all([
        ImputacionProceso(
            imputacion_id=imputacion_estructural.id,
            proceso="camara_estructural",
            unidad="ml",
            cantidad=Decimal("20.00"),
            origen="composicion_pedido",
        ),
        ImputacionProceso(
            imputacion_id=imputacion_offset.id,
            proceso="camara_estructural",
            unidad="ml",
            cantidad=Decimal("10.00"),
            origen="composicion_pedido",
        ),
        ImputacionProceso(
            imputacion_id=imputacion_offset.id,
            proceso="camara_offset",
            unidad="ml",
            cantidad=Decimal("10.00"),
            origen="composicion_pedido",
        ),
    ])
    db_session.commit()

    resumen = build_resumen_compensacion(db_session, acopio.id)
    rows = {row["proceso"]: row for row in resumen["rows"]}

    assert rows["camara_estructural"]["cantidad_pedidos"] == 20
    assert rows["camara_offset"]["cantidad_pedidos"] == 10
    assert rows["camara_estructural"]["pedidos"] == [
        {
            "imputacion_id": imputacion_estructural.id,
            "pedido_id": pedido.id,
            "pedido_numero": "22628",
            "cantidad": 20,
            "origen": "composicion_pedido",
        }
    ]
