from datetime import date
from decimal import Decimal

from models import (
    Acopio,
    AcopioItem,
    AcopioItemPrecioReferencia,
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


def test_resumen_compensacion_completa_procesos_faltantes_en_snapshot_monolitico(db_session):
    acopio = Acopio(
        numero="000212248",
        fecha_alta=date.today(),
        total_m2=Decimal("101.47"),
        total_ml=Decimal("220.00"),
        total_pesos=Decimal("1000.00"),
        total_unidades=69,
        saldo_m2=Decimal("101.47"),
        saldo_ml=Decimal("220.00"),
        saldo_pesos=Decimal("1000.00"),
        saldo_unidades=69,
    )
    db_session.add(acopio)
    db_session.flush()

    item = AcopioItem(
        acopio_id=acopio.id,
        numero_item=69,
        descripcion="Mirage 5 mm. Incoloro con Borde Pulido Brillante en maquina retilinea.",
        cantidad=69,
        total_m2=Decimal("101.47"),
        total_ml=Decimal("220.00"),
        total_pesos=Decimal("1000.00"),
        saldo_m2=Decimal("101.47"),
        saldo_ml=Decimal("220.00"),
        saldo_pesos=Decimal("1000.00"),
        saldo_cantidad=69,
        proceso_vidrio_interior=True,
        proceso_pulido=True,
    )
    db_session.add(item)
    db_session.flush()

    db_session.add_all([
        AcopioItemPrecioReferencia(
            acopio_id=acopio.id,
            acopio_item_id=item.id,
            concepto="vidrio_interior",
            unidad="m2",
            precio_base=Decimal("41092.12"),
            precio_actual=Decimal("41092.12"),
            habilitado=True,
            origen="manual",
        ),
        AcopioItemPrecioReferencia(
            acopio_id=acopio.id,
            acopio_item_id=item.id,
            concepto="pulido",
            unidad="ml",
            precio_base=Decimal("1.00"),
            precio_actual=Decimal("1.00"),
            habilitado=True,
            origen="manual",
        ),
    ])

    pedido = Pedido(
        numero="PED-212248",
        fecha=date.today(),
        total_m2=Decimal("101.47"),
        total_ml=Decimal("220.00"),
        total_pesos=Decimal("1000.00"),
    )
    db_session.add(pedido)
    db_session.flush()

    imputacion = Imputacion(
        pedido_id=pedido.id,
        acopio_id=acopio.id,
        acopio_item_id=item.id,
        cantidad_m2=Decimal("101.47"),
        cantidad_ml=Decimal("220.00"),
        cantidad_pesos=Decimal("1000.00"),
        cantidad_unidades=69,
        pedido_item_descripcion="Mirage 5 mm. Incoloro con Borde Pulido Brillante en maquina retilinea.",
    )
    db_session.add(imputacion)
    db_session.flush()

    # Snapshot historico incompleto: el pedido guardo Pulido, pero todavia no
    # guardaba Vidrio Interior para vidrios monoliticos.
    db_session.add(ImputacionProceso(
        imputacion_id=imputacion.id,
        proceso="pulido",
        unidad="ml",
        cantidad=Decimal("220.00"),
        origen="composicion_pedido",
    ))
    db_session.commit()

    resumen = build_resumen_compensacion(db_session, acopio.id)
    rows = {row["proceso"]: row for row in resumen["rows"]}

    assert rows["vidrio_interior"]["cantidad_acopio"] == 101.47
    assert rows["vidrio_interior"]["cantidad_pedidos"] == 101.47
    assert rows["vidrio_interior"]["diferencia"] == 0
    assert rows["vidrio_interior"]["pedidos"] == [
        {
            "imputacion_id": imputacion.id,
            "pedido_id": pedido.id,
            "pedido_numero": "PED-212248",
            "cantidad": 101.47,
            "origen": "prorrateado",
        }
    ]
    assert rows["vidrio_interior"]["items_valorizacion"][0]["cantidad_pedidos"] == 101.47
    assert rows["pulido"]["cantidad_pedidos"] == 220


def test_resumen_compensacion_usa_precio_por_item_y_concepto(db_session):
    acopio = Acopio(
        numero="COMP-ITEM",
        fecha_alta=date.today(),
        total_m2=Decimal("200.00"),
        total_ml=Decimal("0.00"),
        total_pesos=Decimal("1000.00"),
        total_unidades=10,
        saldo_m2=Decimal("200.00"),
        saldo_ml=Decimal("0.00"),
        saldo_pesos=Decimal("1000.00"),
        saldo_unidades=10,
    )
    db_session.add(acopio)
    db_session.flush()

    item_1 = AcopioItem(
        acopio_id=acopio.id,
        numero_item=1,
        descripcion="Vidrio exterior A",
        cantidad=5,
        total_m2=Decimal("100.00"),
        total_ml=Decimal("0.00"),
        total_pesos=Decimal("500.00"),
        saldo_m2=Decimal("100.00"),
        saldo_ml=Decimal("0.00"),
        saldo_pesos=Decimal("500.00"),
        saldo_cantidad=5,
        proceso_vidrio_exterior=True,
    )
    item_2 = AcopioItem(
        acopio_id=acopio.id,
        numero_item=2,
        descripcion="Vidrio exterior B",
        cantidad=5,
        total_m2=Decimal("100.00"),
        total_ml=Decimal("0.00"),
        total_pesos=Decimal("500.00"),
        saldo_m2=Decimal("100.00"),
        saldo_ml=Decimal("0.00"),
        saldo_pesos=Decimal("500.00"),
        saldo_cantidad=5,
        proceso_vidrio_exterior=True,
    )
    db_session.add_all([item_1, item_2])
    db_session.flush()

    db_session.add_all([
        AcopioItemPrecioReferencia(
            acopio_id=acopio.id,
            acopio_item_id=item_1.id,
            concepto="vidrio_exterior",
            unidad="m2",
            precio_base=Decimal("10.00"),
            precio_actual=Decimal("10.00"),
            habilitado=True,
            origen="manual",
        ),
        AcopioItemPrecioReferencia(
            acopio_id=acopio.id,
            acopio_item_id=item_2.id,
            concepto="vidrio_exterior",
            unidad="m2",
            precio_base=Decimal("20.00"),
            precio_actual=Decimal("20.00"),
            habilitado=True,
            origen="manual",
        ),
    ])

    pedido = Pedido(
        numero="23000",
        fecha=date.today(),
        total_m2=Decimal("200.00"),
        total_ml=Decimal("0.00"),
        total_pesos=Decimal("800.00"),
    )
    db_session.add(pedido)
    db_session.flush()

    db_session.add_all([
        Imputacion(
            pedido_id=pedido.id,
            acopio_id=acopio.id,
            acopio_item_id=item_1.id,
            cantidad_m2=Decimal("50.00"),
            cantidad_ml=Decimal("0.00"),
            cantidad_pesos=Decimal("200.00"),
            cantidad_unidades=2,
        ),
        Imputacion(
            pedido_id=pedido.id,
            acopio_id=acopio.id,
            acopio_item_id=item_2.id,
            cantidad_m2=Decimal("150.00"),
            cantidad_ml=Decimal("0.00"),
            cantidad_pesos=Decimal("600.00"),
            cantidad_unidades=8,
        ),
    ])
    db_session.commit()

    resumen = build_resumen_compensacion(db_session, acopio.id)
    row = {row["proceso"]: row for row in resumen["rows"]}["vidrio_exterior"]

    assert row["cantidad_acopio"] == 200
    assert row["cantidad_pedidos"] == 200
    assert row["diferencia"] == 0
    assert row["importe"] == -500
    assert resumen["totals"]["saldo"] == -500
    assert row["items_valorizacion"] == [
        {
            "item_id": item_1.id,
            "descripcion": "Vidrio exterior A",
            "cantidad_acopio": 100,
            "cantidad_pedidos": 50,
            "diferencia": 50,
            "precio_referencia": 10,
            "importe": 500,
            "precio_faltante": False,
        },
        {
            "item_id": item_2.id,
            "descripcion": "Vidrio exterior B",
            "cantidad_acopio": 100,
            "cantidad_pedidos": 150,
            "diferencia": -50,
            "precio_referencia": 20,
            "importe": -1000,
            "precio_faltante": False,
        },
    ]


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

import pytest

from integrations.spf.database import get_spf_db
from main import app
from services.acopio_service import update_saldos


@pytest.mark.parametrize(
    "precio,consumo,saldo_monetario,saldo_composiciones",
    [
        (Decimal("10"), Decimal("301.25"), 698.75, 60),
        (None, Decimal("301.25"), 698.75, 0),
        (Decimal("0"), Decimal("301.25"), 698.75, 0),
        (Decimal("10"), Decimal("1100.25"), -100.25, 60),
    ],
)
def test_saldos_monetarios_coinciden_entre_endpoints(
    db_session, client, precio, consumo, saldo_monetario, saldo_composiciones
):
    app.dependency_overrides[get_spf_db] = lambda: None
    acopio = Acopio(
        numero="SALDOS-1", fecha_alta=date.today(),
        total_m2=Decimal("10"), total_ml=Decimal("0"),
        total_pesos=Decimal("1000"), total_unidades=10,
        saldo_m2=Decimal("10"), saldo_ml=Decimal("0"),
        saldo_pesos=Decimal("1000"), saldo_unidades=10,
    )
    db_session.add(acopio)
    db_session.flush()
    item = AcopioItem(
        acopio_id=acopio.id, descripcion="Vidrio", cantidad=10,
        total_m2=Decimal("10"), total_ml=Decimal("0"), total_pesos=Decimal("1000"),
        saldo_m2=Decimal("10"), saldo_ml=Decimal("0"), saldo_pesos=Decimal("1000"),
        saldo_cantidad=10, proceso_vidrio_interior=True,
    )
    pedido = Pedido(numero="SALDOS-P1", fecha=date.today(), total_pesos=consumo)
    db_session.add_all([item, pedido])
    db_session.flush()
    if precio is not None:
        db_session.add(AcopioItemPrecioReferencia(
            acopio_id=acopio.id, acopio_item_id=item.id,
            concepto="vidrio_interior", unidad="m2",
            precio_base=precio, precio_actual=precio, habilitado=True, origen="manual",
        ))
    imputacion = Imputacion(
        pedido_id=pedido.id, acopio_id=acopio.id, acopio_item_id=item.id,
        cantidad_m2=Decimal("4"), cantidad_ml=Decimal("0"),
        cantidad_pesos=consumo, cantidad_unidades=4,
    )
    db_session.add(imputacion)
    db_session.commit()
    update_saldos(db_session, acopio.id)

    detalle_response = client.get(f"/acopios/{acopio.id}")
    resumen_response = client.get(f"/acopios/{acopio.id}/resumen-compensacion")
    assert detalle_response.status_code == resumen_response.status_code == 200
    detalle = detalle_response.json()
    resumen = resumen_response.json()
    totals = resumen["totals"]
    assert detalle["saldos"]["pesos"] == totals["saldo_monetario"] == saldo_monetario
    assert totals["saldo"] == saldo_composiciones
    assert totals["diferencia_valorizacion"] == float(
        Decimal(str(saldo_monetario)) - Decimal(str(saldo_composiciones))
    )
    assert totals["valorizacion_completa"] is (precio is not None)
    assert sum(row["importe"] for row in resumen["rows"]) == saldo_composiciones

    # Reference prices must not change the monetary balance or historical consumption.
    db_session.refresh(imputacion)
    assert imputacion.cantidad_pesos == consumo
    db_session.delete(imputacion)
    db_session.commit()
    update_saldos(db_session, acopio.id)
    detalle = client.get(f"/acopios/{acopio.id}").json()
    resumen = client.get(f"/acopios/{acopio.id}/resumen-compensacion").json()
    assert detalle["saldos"]["pesos"] == resumen["totals"]["saldo_monetario"] == 1000


def test_resumen_212871_conserva_saldo_y_detecta_valorizacion_pendiente(db_session, client):
    """El stock completo no puede confundirse con el cero de procesos sin precio."""
    app.dependency_overrides[get_spf_db] = lambda: None
    acopio = Acopio(
        numero='000212871', fecha_alta=date.today(),
        total_m2=Decimal('21.18'), total_ml=Decimal('56.68'), total_pesos=Decimal('2697174.53'), total_unidades=9,
        saldo_m2=Decimal('21.18'), saldo_ml=Decimal('56.68'), saldo_pesos=Decimal('2697174.53'), saldo_unidades=9,
    )
    db_session.add(acopio)
    db_session.flush()
    items = []
    for n, description, m2, ml, neto, qty, fason in [
        (1, 'Templado Float 10 mm + herrajes', '6.90', '24.40', '1357253.26', 4, True),
        (2, 'Templado Float 10 mm + freno', '2.99', '7.20', '618211.05', 1, True),
        (3, 'Templado Float 10 mm + bisagra', '3.38', '9.00', '347948.13', 2, True),
        (4, 'Laminado 4+4 Incoloro con filos matados', '7.91', '16.08', '373762.09', 2, False),
    ]:
        item = AcopioItem(
            acopio_id=acopio.id, numero_item=n, descripcion=description, cantidad=qty,
            total_m2=Decimal(m2), total_ml=Decimal(ml), total_pesos=Decimal(neto),
            saldo_m2=Decimal(m2), saldo_ml=Decimal(ml), saldo_pesos=Decimal(neto), saldo_cantidad=qty,
            proceso_fason_templado_exterior=fason, procesos_autodetectados=True,
        )
        db_session.add(item)
        items.append(item)
    db_session.commit()

    detail = client.get(f'/acopios/{acopio.id}').json()
    response = client.get(f'/acopios/{acopio.id}/resumen-compensacion')
    assert response.status_code == 200
    summary = response.json()
    assert summary['saldos_disponibles'] == detail['saldos'] == {
        'pesos': 2697174.53, 'm2': 21.18, 'ml': 56.68, 'unidades': 9,
    }
    control = summary['control_desacopios']
    assert [row['item_id'] for row in control['items']] == [item.id for item in items]
    assert control['items'][3]['contratado'] == {
        'm2': 7.91, 'ml': 16.08, 'pesos': 373762.09, 'unidades': 2,
    }
    assert control['items'][3]['disponible'] == control['items'][3]['contratado']
    assert control['totales']['disponible'] == detail['saldos']
    assert control['sin_item']['pedidos'] == []
    assert summary['totals']['saldo_monetario'] == 2697174.53
    assert summary['totals']['saldo_valorizado'] is None
    assert summary['totals']['tiene_valorizacion'] is False
    assert summary['totals']['valorizacion_completa'] is False
    assert summary['items_sin_composicion'] == [{
        'item_id': items[3].id, 'numero_item': 4, 'descripcion': items[3].descripcion,
        'cantidad_m2': 7.91, 'cantidad_ml': 16.08,
    }]
    assert any('Item 4 sin composicion' in warning for warning in summary['warnings'])
    rows = {row['proceso']: row for row in summary['rows']}
    assert rows['fason_templado_exterior']['cantidad_acopio'] == 13.27
    assert rows['fason_templado_exterior']['tiene_valorizacion'] is False
    assert rows['fason_templado_exterior']['precio_faltante'] is True
    assert db_session.query(Imputacion).count() == 0
    db_session.refresh(items[3])
    assert items[3].proceso_vidrio_interior is False
    assert items[3].proceso_vidrio_exterior is False

    # Completar precios de otros conceptos no puede ocultar el item sin composicion.
    for item in items[:3]:
        record = db_session.query(AcopioItemPrecioReferencia).filter_by(
            acopio_item_id=item.id, concepto='fason_templado_exterior').one()
        record.precio_base = record.precio_actual = Decimal('100')
        record.origen = 'manual'
    db_session.commit()
    summary = client.get(f'/acopios/{acopio.id}/resumen-compensacion').json()
    assert summary['control_desacopios'] == control
    assert summary['totals']['saldo'] == 1327
    assert summary['totals']['tiene_valorizacion'] is True
    assert summary['totals']['saldo_valorizado'] is None
    assert summary['totals']['valorizacion_completa'] is False
    assert summary['saldos_disponibles'] == detail['saldos']

    # Solo una asignacion explicita permite considerar completa la valorizacion.
    items[3].proceso_vidrio_interior = True
    db_session.add(AcopioItemPrecioReferencia(
        acopio_id=acopio.id, acopio_item_id=items[3].id, concepto='vidrio_interior', unidad='m2',
        precio_base=Decimal('0'), precio_actual=Decimal('0'), habilitado=True, origen='manual'))
    db_session.commit()
    summary = client.get(f'/acopios/{acopio.id}/resumen-compensacion').json()
    assert summary['totals']['valorizacion_completa'] is True
    assert summary['totals']['saldo_valorizado'] == 1327
    assert summary['items_sin_composicion'] == []
    assert summary['saldos_disponibles'] == detail['saldos']


def test_resumen_admite_cero_manual_sin_confundirlo_con_precio_ausente(db_session):
    acopio = Acopio(numero='CERO-EXPLICITO', fecha_alta=date.today(),
                    total_m2=Decimal('10'), saldo_m2=Decimal('10'),
                    total_pesos=Decimal('1000'), saldo_pesos=Decimal('1000'))
    db_session.add(acopio)
    db_session.flush()
    item = AcopioItem(acopio_id=acopio.id, descripcion='Vidrio', cantidad=1,
                      total_m2=Decimal('10'), saldo_m2=Decimal('10'),
                      total_pesos=Decimal('1000'), saldo_pesos=Decimal('1000'),
                      proceso_vidrio_interior=True)
    db_session.add(item)
    db_session.flush()
    db_session.add(AcopioItemPrecioReferencia(
        acopio_id=acopio.id, acopio_item_id=item.id, concepto='vidrio_interior', unidad='m2',
        precio_base=Decimal('0'), precio_actual=Decimal('0'), habilitado=True, origen='manual'))
    db_session.commit()
    summary = build_resumen_compensacion(db_session, acopio.id)
    assert summary['totals']['valorizacion_completa'] is True
    assert summary['totals']['tiene_valorizacion'] is True
    assert summary['totals']['saldo_valorizado'] == 0
    assert summary['saldos_disponibles']['pesos'] == 1000


@pytest.mark.parametrize("con_procesos", [False, True])
@pytest.mark.parametrize("con_global", [False, True])
def test_control_desacopios_independiente_de_valorizacion(
    db_session, client, con_procesos, con_global
):
    """Sin composición/precio, snapshots, ajustes y excesos no ocultan consumos."""
    app.dependency_overrides[get_spf_db] = lambda: None
    acopio = Acopio(
        numero="CONTROL-INDEPENDIENTE", fecha_alta=date.today(),
        total_m2=10, total_ml=20, total_pesos=1000, total_unidades=5,
        saldo_m2=10, saldo_ml=20, saldo_pesos=1000, saldo_unidades=5,
    )
    db_session.add(acopio)
    db_session.flush()
    items = [
        AcopioItem(
            acopio_id=acopio.id, numero_item=1, descripcion="Sin precio", cantidad=4,
            total_m2=8, total_ml=16, total_pesos=800,
            saldo_m2=8, saldo_ml=16, saldo_pesos=800, saldo_cantidad=4,
            proceso_vidrio_interior=con_procesos, proceso_pulido=con_procesos,
        ),
        AcopioItem(
            acopio_id=acopio.id, numero_item=2, descripcion="Sin conceptos", cantidad=1,
            total_m2=2, total_ml=4, total_pesos=200,
            saldo_m2=2, saldo_ml=4, saldo_pesos=200, saldo_cantidad=1,
        ),
    ]
    pedido = Pedido(numero="CONTROL-PEDIDO", fecha=date.today(), total_pesos=1050)
    db_session.add_all([*items, pedido])
    db_session.flush()
    imputaciones = []
    for item, m2, ml, pesos, unidades in [
        (items[0], "9", "18", "900", 5),
        (items[0], "-0.5", "-1", "-50", -1),
        (items[1], "1", "2", "100", 1),
        *([(None, "1", "2", "100", 1)] if con_global else []),
    ]:
        imp = Imputacion(
            acopio_id=acopio.id, acopio_item_id=item.id if item else None,
            pedido_id=pedido.id, cantidad_m2=Decimal(m2), cantidad_ml=Decimal(ml),
            cantidad_pesos=Decimal(pesos), cantidad_unidades=unidades,
        )
        db_session.add(imp)
        imputaciones.append(imp)
    db_session.flush()
    # Process snapshots must not multiply physical consumption.
    db_session.add(ImputacionProceso(
        imputacion_id=imputaciones[0].id, proceso="pulido", unidad="ml",
        cantidad=18, origen="composicion_pedido",
    ))
    db_session.commit()
    update_saldos(db_session, acopio.id)

    response = client.get(f"/acopios/{acopio.id}/resumen-compensacion")
    assert response.status_code == 200
    summary = response.json()
    control = summary["control_desacopios"]
    assert len(control["items"]) == 2
    row1, row2 = control["items"]
    assert row1["imputado"] == {"m2": 8.5, "ml": 17, "pesos": 850, "unidades": 4}
    assert row1["disponible"] == {"m2": -0.5, "ml": -1, "pesos": -50, "unidades": 0}
    assert row2["imputado"] == {"m2": 1, "ml": 2, "pesos": 100, "unidades": 1}
    assert row2["disponible"] == {"m2": 1, "ml": 2, "pesos": 100, "unidades": 0}
    assert [p["imputacion_id"] for p in row1["pedidos"]] == [i.id for i in imputaciones[:2]]
    assert row1["pedidos"][1]["cantidades"]["m2"] == -0.5
    assert all(p["pedido_numero"] == pedido.numero for p in row1["pedidos"])
    expected = {"m2": -0.5, "ml": -1, "pesos": -50, "unidades": -1} if con_global else {
        "m2": 0.5, "ml": 1, "pesos": 50, "unidades": 0,
    }
    detail = client.get(f"/acopios/{acopio.id}").json()
    assert control["totales"]["disponible"] == detail["saldos"] == expected
    assert summary["saldos_disponibles"] == expected
    assert len(control["sin_item"]["pedidos"]) == int(con_global)
    assert control["sin_item"]["imputado"]["m2"] == (1 if con_global else 0)
    ids = [
        p["imputacion_id"]
        for group in [*control["items"], control["sin_item"]]
        for p in group["pedidos"]
    ]
    assert sorted(ids) == sorted(i.id for i in imputaciones)
    assert len(ids) == len(set(ids))

    # Completing concepts and prices changes valuation only, never this ledger.
    items[0].proceso_vidrio_interior = True
    items[0].proceso_pulido = True
    db_session.commit()
    client.get(f"/acopios/{acopio.id}/resumen-compensacion")
    for record in db_session.query(AcopioItemPrecioReferencia).filter_by(acopio_id=acopio.id):
        record.precio_base = record.precio_actual = Decimal("100")
        record.origen = "manual"
    db_session.commit()
    updated = client.get(f"/acopios/{acopio.id}/resumen-compensacion").json()
    assert updated["control_desacopios"] == control
    assert updated["saldos_disponibles"] == expected

    # Removing a consumption must restore its quantities even without concepts.
    db_session.delete(imputaciones[2])
    db_session.commit()
    update_saldos(db_session, acopio.id)
    restored = client.get(f"/acopios/{acopio.id}/resumen-compensacion").json()
    assert restored["control_desacopios"]["items"][1]["pedidos"] == []
    assert restored["control_desacopios"]["items"][1]["disponible"] == {
        "m2": 2, "ml": 4, "pesos": 200, "unidades": 1,
    }
    assert restored["control_desacopios"]["totales"]["disponible"] == client.get(
        f"/acopios/{acopio.id}"
    ).json()["saldos"]